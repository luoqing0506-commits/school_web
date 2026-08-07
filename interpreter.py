# 无错语言 WucuoLang
# 版权 (C) 2026 薄情寡义
# 本程序是自由软件：你可以根据自由软件基金会发布的 GNU 通用公共许可证
# （GPL）第 3 版或（按你的选择）任何更新版本重新分发和/或修改它。
# 分发本程序的目的是希望它有用，但没有任何保证；甚至没有适销性或
# 特定用途的隐含保证。详见 GNU 通用公共许可证。
# 你应该已经收到 GNU 通用公共许可证的副本。如果没有，见
# <https://www.gnu.org/licenses/>。

# -*- coding: utf-8 -*-
"""
无错语言 解释器 (interpreter.py)
=================================
树遍历解释器：AST -> 执行结果。

设计：
  - 环境链（作用域嵌套）
  - 值类型：int / Dec / Fraction（数字塔）、str、bool、None（空）、list/dict（表）、function
  - 表：Python dict（键值对），数组用自动数字键
  - 错误：WucuoError（抛错）通过捕获 处理
"""

from number import (parse_number, num_add, num_sub, num_mul, num_div,
                    num_mod, num_neg, num_eq, num_lt, num_le, num_gt, num_ge,
                    num_str, num_is_zero, Num)

from typing import Any, Dict, List, Optional


class WucuoError(Exception):
    """语言级错误（抛错/运行时错误），可被 捕获 处理"""
    def __init__(self, value, trace=None):
        self.value = value  # 错误值（任意）
        self.trace = trace or []
        super().__init__(f"运行时错误: {value}")


class ReturnSignal(Exception):
    """函数返回信号"""
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    """跳出循环信号（未来支持）"""
    pass


class Environment:
    def __init__(self, parent: Optional["Environment"] = None):
        self.vars: Dict[str, Any] = {}
        self.parent = parent

    def define(self, name, value):
        self.vars[name] = value

    def assign(self, name, value):
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent:
            self.parent.assign(name, value)
        else:
            raise WucuoError(f"变量 '{name}' 未声明")

    def get(self, name):
        env = self
        while env:
            if name in env.vars:
                return env.vars[name]
            env = env.parent
        raise WucuoError(f"变量 '{name}' 未声明")


class Function:
    """用户定义的函数"""
    def __init__(self, name, params, body, closure, pure=False, interp=None):
        self.name = name
        self.params = params
        self.body = body
        self.closure = closure
        self.pure = pure
        self.interp = interp

    def __repr__(self):
        return f"<功能 {self.name}>"

    def __call__(self, *args):
        """让 Function 对象可直接调用（编译模式与模块互操作需要）"""
        return self.interp.call_value(self, list(args), self.closure)


# ============ 协程支持（加强版新增） ============
import threading

# 当前线程 -> 协程映射（让出() 用它找自己所在的协程）
CURRENT_COROUTINE = {}


class Coroutine:
    """协程：用独立线程 + 条件变量实现协作式调度。
    让出() 暂停当前线程等待恢复；恢复() 唤醒它。调用栈完整保留。

    状态机：
      suspended - 未启动 或 让出后暂停
      running   - 执行中
      dead      - 结束（有 result 或 error）
    同步标志：
      yield_ready - 协程刚让出，有值可取（主线程用它判断"有结果"）
      resumed     - 主线程已恢复协程（协程线程用它判断"被唤醒"）
    """

    def __init__(self, fn, args, closure_env, interp):
        self.fn = fn
        self.args = args
        self.interp = interp
        self.cond = threading.Condition()
        self.state = "suspended"
        self.started = False
        self.yield_ready = False
        self.resumed = False
        self.yield_value = None
        self.resume_value = None
        self.result = None
        self.error = None
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        CURRENT_COROUTINE[threading.get_ident()] = self
        with self.cond:
            self.state = "running"
        try:
            fn_env = Environment(self.fn.closure)
            if len(self.args) > len(self.fn.params):
                raise WucuoError(
                    f"函数 {self.fn.name or '匿名'} 最多接受 {len(self.fn.params)} 个参数")
            for i, p in enumerate(self.fn.params):
                if i < len(self.args):
                    fn_env.define(p["name"], self.args[i])
                elif p.get("default") is not None:
                    fn_env.define(p["name"], self.interp.eval_expr(p["default"], self.fn.closure))
                else:
                    raise WucuoError(f"函数 {self.fn.name or '匿名'} 缺少参数 '{p['name']}'")
            try:
                self.result = self.interp.exec_block(self.fn.body, fn_env)
            except ReturnSignal as r:
                self.result = r.value
        except WucuoError as e:
            self.error = e
        except Exception as e:
            self.error = WucuoError(f"协程内部错误: {e}")
        finally:
            with self.cond:
                self.state = "dead"
                self.cond.notify()
            CURRENT_COROUTINE.pop(threading.get_ident(), None)

    def start(self):
        self.thread.start()


class Interpreter:
    def __init__(self, builtins: Dict[str, Any], import_loader=None):
        self.globals = Environment()
        self.builtins = builtins
        self.import_loader = import_loader or (lambda path: {})
        self.exports = {}  # 顶层导出表（模块系统用）

        # 注册内置函数到全局
        for name, fn in builtins.items():
            self.globals.define(name, fn)

    # ------------------------------------------------------------------
    # 执行入口
    # ------------------------------------------------------------------
    def interpret(self, ast, collect_exports=False) -> Any:
        """执行程序。collect_exports=True 时收集顶层声明作为导出表（模块用）"""
        result = None
        for stmt in ast["body"]:
            result = self.exec_stmt(stmt, self.globals)
            # 模块导出：顶层声明（量/可变/功能/纯功能）自动进导出表
            if collect_exports and stmt["type"] in ("Let", "Mut", "FnDef", "PureFnDef"):
                try:
                    self.exports[stmt["name"]] = self.globals.get(stmt["name"])
                except Exception:
                    pass
        return result

    # ------------------------------------------------------------------
    # 语句
    # ------------------------------------------------------------------
    def exec_stmt(self, stmt, env: Environment) -> Any:
        t = stmt["type"]

        if t in ("Let", "Mut"):
            value = self.eval_expr(stmt["value"], env)
            names = stmt.get("names") or [stmt["name"]]
            if len(names) == 1:
                env.define(stmt["name"], value)
            else:
                # 解构赋值：值必须是表，按数字键顺序解包
                if not isinstance(value, dict):
                    raise WucuoError("解构赋值要求右侧是表", stmt.get("line"))
                items = list(value.values())
                if len(items) < len(names):
                    raise WucuoError(
                        f"解构失败：右侧表有 {len(items)} 个元素，需要 {len(names)} 个变量",
                        stmt.get("line"))
                for i, nm in enumerate(names):
                    env.define(nm, items[i])
            return value

        if t == "Assign":
            target = stmt["target"]
            value = self.eval_expr(stmt["value"], env)
            if target["type"] == "Var":
                env.assign(target["name"], value)
            elif target["type"] == "GetAttr":
                obj = self.eval_expr(target["obj"], env)
                self.set_attr(obj, target["name"], value, stmt.get("line"))
            elif target["type"] == "Index":
                obj = self.eval_expr(target["obj"], env)
                idx = self.eval_expr(target["index"], env)
                self.set_index(obj, idx, value, stmt.get("line"))
            else:
                raise WucuoError("无效的赋值目标", stmt.get("line"))
            return value

        if t == "FnDef":
            fn = Function(stmt["name"], stmt["params"], stmt["body"], env, pure=False, interp=self)
            env.define(stmt["name"], fn)
            return fn

        if t == "OpFnDef":
            fn = Function(stmt["name"], stmt["params"], stmt["body"], env, pure=False, interp=self)
            env.define(stmt["name"], fn)
            return fn

        if t == "PureFnDef":
            fn = Function(stmt["name"], stmt["params"], stmt["body"], env, pure=True, interp=self)
            env.define(stmt["name"], fn)
            return fn

        if t == "If":
            cond = self.is_truthy(self.eval_expr(stmt["cond"], env))
            if cond:
                return self.exec_block(stmt["then"], env)
            for elif_branch in stmt.get("elifs", []):
                if self.is_truthy(self.eval_expr(elif_branch["cond"], env)):
                    return self.exec_block(elif_branch["body"], env)
            if stmt.get("else"):
                return self.exec_block(stmt["else"], env)
            return None

        if t == "While":
            # 循环保护：防止 AI 写出无限循环（防错设计）
            max_iter = 1_000_000
            count = 0
            while self.is_truthy(self.eval_expr(stmt["cond"], env)):
                count += 1
                if count > max_iter:
                    raise WucuoError("循环超过 100 万次，可能死循环（已在第"
                                     f"{stmt.get('line','?')}行拦截）")
                self.exec_block(stmt["body"], env)
            return None

        if t == "ForEach":
            iterable = self.eval_expr(stmt["iterable"], env)
            var2 = stmt.get("var2")
            if var2:
                # 键值对遍历：对 键, 值 在 表
                if not isinstance(iterable, dict):
                    raise WucuoError("键值对遍历要求右侧是表", stmt.get("line"))
                items = list(iterable.items())
            elif isinstance(iterable, dict):
                # 遍历表：给值（数组表的值就是元素）
                items = [(None, v) for v in iterable.values()]
            elif isinstance(iterable, str):
                items = [(None, ch) for ch in iterable]
            elif isinstance(iterable, list):
                items = [(None, x) for x in iterable]
            else:
                raise WucuoError("对 ... 在 只能遍历 表 或 文本", stmt.get("line"))
            max_iter = 1_000_000
            count = 0
            for k, v in items:
                count += 1
                if count > max_iter:
                    raise WucuoError("遍历超过 100 万次，可能死循环")
                child = Environment(env)
                if var2:
                    child.define(stmt["var"], k)
                    child.define(var2, v)
                else:
                    child.define(stmt["var"], v)
                self.exec_block(stmt["body"], child)
            return None

        if t == "Return":
            value = self.eval_expr(stmt["value"], env) if stmt.get("value") else None
            raise ReturnSignal(value)

        if t == "Throw":
            value = self.eval_expr(stmt["value"], env)
            raise WucuoError(value, [stmt.get("line")])

        if t == "TryExpr":
            try:
                return {"成功": True, "值": self.eval_expr(stmt["expr"], env)}
            except WucuoError as e:
                return {"成功": False, "值": None, "错误": e.value}
            except Exception as e:
                return {"成功": False, "值": None, "错误": str(e)}

        if t == "TryBlock":
            try:
                self.exec_block(stmt["body"], env)
                return {"成功": True, "值": None}
            except WucuoError as e:
                return {"成功": False, "值": None, "错误": e.value}
            except Exception as e:
                return {"成功": False, "值": None, "错误": str(e)}

        if t == "Import":
            path = stmt["path"]
            mod = self.import_loader(path)
            return mod

        if t == "Print":
            parts = []
            for a in stmt["args"]:
                parts.append(self.format_value(self.eval_expr(a, env)))
            print(" ".join(parts))
            return None

        if t == "Assert":
            cond = self.eval_expr(stmt["cond"], env)
            if not self.is_truthy(cond):
                msg = self.eval_expr(stmt["msg"], env) if stmt.get("msg") else "断言失败"
                raise WucuoError(msg, stmt.get("line"))
            return None

        if t == "ExprStmt":
            return self.eval_expr(stmt["expr"], env)

        if t == "Block":
            return self.exec_block(stmt, env)

        raise WucuoError(f"未知语句: {t}")

    def exec_block(self, block, env: Environment) -> Any:
        """块：创建子作用域执行"""
        child = Environment(env)
        result = None
        for stmt in block["body"]:
            result = self.exec_stmt(stmt, child)
        return result

    # ------------------------------------------------------------------
    # 表达式
    # ------------------------------------------------------------------
    def eval_expr(self, expr, env: Environment) -> Any:
        t = expr["type"]

        if t == "Literal":
            kind = expr.get("kind", "number")
            if kind == "number":
                return parse_number(expr["value"])
            if kind == "string":
                return expr["value"]
            return expr["value"]  # bool/nil

        if t == "Template":
            # 模板字符串：${expr} 插值（支持函数调用/属性链/算术）
            import re
            text = expr["value"]
            def repl(m):
                inner = m.group(1)
                return self.format_value(self.eval_template_expr(inner, env))
            result = re.sub(r"\$\{([^}]+)\}", repl, text)
            return result

        if t == "Var":
            # 先查局部，再查内置
            try:
                return env.get(expr["name"])
            except WucuoError:
                if expr["name"] in self.builtins:
                    return self.builtins[expr["name"]]
                raise

        if t == "Self":
            # 自身：从环境链找（方法调用时绑定）
            try:
                return env.get("自身")
            except WucuoError:
                raise WucuoError("自身 只能在方法里使用（表.方法() 调用时）")

        if t == "Meta":
            # 元编程 @运算符：查找运算符实现函数
            name = expr["name"]
            if name in self.builtins:
                return self.builtins[name]
            raise WucuoError(f"未知运算符实现: {name}")

        if t == "BinOp":
            left = self.eval_expr(expr["left"], env)
            right = self.eval_expr(expr["right"], env)
            op = expr["op"]
            # 字符串 + 拼接
            if op == "+" and isinstance(left, str) and isinstance(right, str):
                return left + right
            # 数字运算（数字塔）
            if op == "+":
                return num_add(left, right)
            if op == "-":
                return num_sub(left, right)
            if op == "*":
                return num_mul(left, right)
            if op == "/":
                return num_div(left, right)
            if op == "%":
                return num_mod(left, right)
            if op == "==":
                return self.value_eq(left, right)
            if op == "!=":
                return not self.value_eq(left, right)
            if op == "<":
                return num_lt(left, right)
            if op == "<=":
                return num_le(left, right)
            if op == ">":
                return num_gt(left, right)
            if op == ">=":
                return num_ge(left, right)
            raise WucuoError(f"未知运算符: {op}")

        if t == "LogicOp":
            left = self.eval_expr(expr["left"], env)
            if expr["op"] == "和":
                return left if not self.is_truthy(left) else self.eval_expr(expr["right"], env)
            else:  # 或
                return left if self.is_truthy(left) else self.eval_expr(expr["right"], env)

        if t == "Pipe":
            # 管道：左侧值 | 右侧函数  ->  调用右侧函数，参数是左侧值
            left_val = self.eval_expr(expr["left"], env)
            right_val = self.eval_expr(expr["right"], env)
            if not callable(right_val) and not isinstance(right_val, Function):
                raise WucuoError("管道右侧必须是函数", expr.get("line"))
            return self.call_value(right_val, [left_val], env, expr.get("line"))

        if t == "UnaryOp":
            operand = self.eval_expr(expr["operand"], env)
            if expr["op"] == "-":
                return num_neg(operand)
            if expr["op"] == "非":
                return not self.is_truthy(operand)
            raise WucuoError(f"未知一元运算符: {expr['op']}")

        if t == "Call":
            # 方法调用：表.方法(...) 时把表作为 自身(this) 传入
            this_val = None
            if expr["callee"]["type"] == "GetAttr":
                this_val = self.eval_expr(expr["callee"]["obj"], env)
            callee = self.eval_expr(expr["callee"], env)
            args = [self.eval_expr(a, env) for a in expr["args"]]
            kwargs = {k: self.eval_expr(v, env) for k, v in expr.get("kwargs", {}).items()}
            if not callable(callee) and not isinstance(callee, Function):
                raise WucuoError(f"无法调用非函数值: {self.format_value(callee)}")
            return self.call_value(callee, args, env, expr.get("line"), this_val, kwargs)

        if t == "GetAttr":
            obj = self.eval_expr(expr["obj"], env)
            if isinstance(obj, dict):
                if expr["name"] not in obj:
                    raise WucuoError(f"表里没有键 '{expr['name']}'", expr.get("line"))
                return obj[expr["name"]]
            # FFI：Python 模块/对象的属性访问
            try:
                return getattr(obj, expr["name"])
            except AttributeError:
                raise WucuoError(f"对象没有属性 '{expr['name']}'", expr.get("line"))

        if t == "Index":
            obj = self.eval_expr(expr["obj"], env)
            idx = self.eval_expr(expr["index"], env)
            if isinstance(obj, dict):
                if idx not in obj:
                    raise WucuoError(f"表里没有键 {self.format_value(idx)}", expr.get("line"))
                return obj[idx]
            if isinstance(obj, str):
                if not isinstance(idx, int):
                    raise WucuoError("文本下标必须是整数", expr.get("line"))
                return obj[idx]
            raise WucuoError("下标访问只支持表或文本", expr.get("line"))

        if t == "Slice":
            # 切片 [开始:结束]
            obj = self.eval_expr(expr["obj"], env)
            start = self.eval_expr(expr["start"], env) if expr.get("start") is not None else None
            end = self.eval_expr(expr["end"], env) if expr.get("end") is not None else None
            if isinstance(obj, str):
                s = start if isinstance(start, int) else None
                e = end if isinstance(end, int) else None
                return obj[s:e]
            if isinstance(obj, dict):
                # 表切片：按数字键
                items = list(obj.values())
                s = start if isinstance(start, int) else None
                e = end if isinstance(end, int) else None
                sliced = items[s:e]
                return {i: sliced[i] for i in range(len(sliced))}
            raise WucuoError("切片只支持文本或表", expr.get("line"))

        if t == "Table":
            table = {}
            next_index = 0
            for entry in expr["entries"]:
                if entry["kind"] == "pair":
                    table[entry["key"]] = self.eval_expr(entry["value"], env)
                else:
                    # 数组元素：自动数字键
                    table[next_index] = self.eval_expr(entry["value"], env)
                    next_index += 1
            return table

        if t in ("FnLiteral", "PureFnLiteral", "OpFnLiteral"):
            return Function(None, expr["params"], expr["body"], env,
                            pure=(t == "PureFnLiteral"), interp=self)

        if t == "TryExpr":
            # 捕获(expr)：求值并捕获错误，返回结果表
            try:
                value = self.eval_expr(expr["expr"], env)
                return {"成功": True, "值": value}
            except WucuoError as e:
                return {"成功": False, "值": None, "错误": e.value}
            except Exception as e:
                return {"成功": False, "值": None, "错误": str(e)}

        if t == "ImportExpr":
            # 导入(路径)：加载模块，返回导出表
            return self.import_loader(expr["path"])

        raise WucuoError(f"未知表达式: {t}")

    def eval_template_expr(self, expr_text: str, env: Environment) -> Any:
        """模板插值表达式求值：复用 parser + interpreter 的完整表达式能力"""
        from parser import Parser, tokenize
        try:
            # 把插值内容当作表达式解析（包装成表达式语句）
            tokens = tokenize(expr_text)
            parser = Parser(tokens)
            expr = parser.parse_expr()
            return self.eval_expr(expr, env)
        except Exception:
            # 兜底：简单变量/属性链
            parts = expr_text.strip().split(".")
            value = env.get(parts[0])
            for p in parts[1:]:
                if isinstance(value, dict):
                    value = value[p]
                else:
                    raise WucuoError(f"无法访问 {p}")
            return value

    def eval_simple(self, expr_text: str, env: Environment) -> Any:
        """模板字符串里的简单表达式求值（变量/属性链）"""
        parts = expr_text.strip().split(".")
        value = env.get(parts[0])
        for p in parts[1:]:
            if isinstance(value, dict):
                value = value[p]
            else:
                raise WucuoError(f"无法访问 {p}")
        return value

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------
    def call_value(self, callee, args, env, line=None, this_val=None, kwargs=None):
        """调用函数值（内置或用户函数）。this_val 是方法调用时的 自身 绑定"""
        kwargs = kwargs or {}
        # 内置函数（Python callable）
        if callable(callee) and not isinstance(callee, Function):
            try:
                return callee(*args, **kwargs)
            except WucuoError:
                raise
            except Exception as e:
                raise WucuoError(f"内置函数出错: {e}", line)
        # 用户函数
        if isinstance(callee, Function):
            fn_env = Environment(callee.closure)
            if this_val is not None:
                fn_env.define("自身", this_val)
            if len(args) > len(callee.params):
                raise WucuoError(
                    f"函数 {callee.name or '匿名'} 最多接受 {len(callee.params)} 个参数，"
                    f"实际传了 {len(args)} 个", line)
            for i, p in enumerate(callee.params):
                if i < len(args):
                    fn_env.define(p["name"], args[i])
                elif p.get("default") is not None:
                    # 用默认参数（在函数闭包环境求值）
                    fn_env.define(p["name"], self.eval_expr(p["default"], callee.closure))
                else:
                    raise WucuoError(
                        f"函数 {callee.name or '匿名'} 缺少参数 '{p['name']}'", line)
            try:
                self.exec_block(callee.body, fn_env)
                return None
            except ReturnSignal as r:
                return r.value
        raise WucuoError(f"无法调用: {callee}", line)

    def is_truthy(self, value) -> bool:
        """真值规则：只有 假/空/0/空文本/空表 是假"""
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, Num)):
            return not num_is_zero(value)
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, dict):
            return len(value) > 0
        return True

    def value_eq(self, a, b) -> bool:
        if isinstance(a, Num) and isinstance(b, Num):
            return num_eq(a, b)
        if isinstance(a, dict) and isinstance(b, dict):
            return a is b  # 表比较身份
        return a == b

    def format_value(self, value) -> str:
        """值 -> 文本（打印用）"""
        if value is None:
            return "空"
        if isinstance(value, bool):
            return "真" if value else "假"
        if isinstance(value, Num):
            return num_str(value)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                parts.append(f"{k}: {self.format_value(v)}")
            return "{" + ", ".join(parts) + "}"
        if isinstance(value, Function):
            return f"<功能 {value.name or '匿名'}>"
        return str(value)

    def set_attr(self, obj, name, value, line=None):
        if not isinstance(obj, dict):
            raise WucuoError("只能给表设置属性", line)
        obj[name] = value

    def set_index(self, obj, idx, value, line=None):
        if isinstance(obj, dict):
            obj[idx] = value
        elif isinstance(obj, list):
            obj[idx] = value
        else:
            raise WucuoError("只能给表设置下标", line)

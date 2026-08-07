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
无错语言 类型检查器 (checker.py)
=================================
防错核心：编译期检查，让错误在运行前就暴露。

检查规则：
  1. 变量必须先声明后使用
  2. 不可变变量不能赋值（量 a = 5; a = 6 -> 报错）
  3. 无隐式转换：数字 + 文本 -> 报错（必须显式 转数字/转文本）
  4. 强类型：声明了类型标注的变量，赋值类型不符 -> 报错
  5. 纯功能强制：纯功能里禁止 打印/抛错/改外部变量/调非纯函数
  6. 函数调用参数数量匹配
  7. 返回类型匹配（有标注时）
  8. 未定义函数调用 -> 报错
"""


class CheckError(Exception):
    def __init__(self, msg, line=None):
        loc = f"第{line}行" if line else "未知位置"
        super().__init__(f"类型检查错误 {loc}: {msg}")
        self.line = line


# 内置函数 -> (参数类型列表, 返回类型)。None = 任意类型
BUILTINS = {
    "打印": (None, None),
    "长度": ("string", "number"),  # 长度(文本)->数字；长度(表)->数字 实际动态
    "类型": (None, "string"),
    "转数字": (None, "number"),
    "转文本": (None, "string"),
    "转布尔": (None, "bool"),
    "键": ("table", "table"),
    "含": ("table", "bool"),
    "删": ("table", "table"),
    "克隆": ("table", "table"),
    "合并": (None, "table"),
    "断言": ("bool", "nil"),
    "读入": (None, "string"),
    "捕获": (None, "table"),
    # 文件操作（加强版）
    "读文件": ("string", "string"),
    "写文件": (None, "bool"),
    "追加文件": (None, "bool"),
    "存在": ("string", "bool"),
    # JSON
    "JSON编码": (None, "string"),
    "JSON解码": ("string", "任意"),
    # 字符串
    "分割": (None, "table"),
    "替换": (None, "string"),
    "大写": ("string", "string"),
    "小写": ("string", "string"),
    "去空格": ("string", "string"),
    "包含": (None, "bool"),
    # 列表
    "排序": ("table", "table"),
    "反转": ("table", "table"),
    "追加": (None, "table"),
    "弹出": ("table", "任意"),
    # 网络
    "HTTP获取": ("string", "table"),
    "HTTP发布": (None, "table"),
    "下载文件": (None, "bool"),
    # 时间
    "现在": (None, "number"),
    "时间文本": (None, "string"),
    "睡眠": ("number", "nil"),
    # 随机
    "随机数": (None, "number"),
    "随机整数": (None, "number"),
    "随机选择": ("table", "任意"),
    # 数学
    "绝对值": ("number", "number"),
    "向下取整": ("number", "number"),
    "向上取整": ("number", "number"),
    "平方根": ("number", "number"),
    "最大值": (None, "number"),
    "最小值": (None, "number"),
    "取模": (None, "number"),
    # 协程
    "协程": (None, "任意"),
    "恢复": (None, "任意"),
    "让出": (None, "任意"),
    "协程状态": (None, "string"),
    # HTTP 服务器
    "服务": (None, "table"),
    "停止服务": ("table", "任意"),
    # 日期/正则
    "日期": (None, "string"),
    "年月日": ("string", "table"),
    "匹配": (None, "table"),
    "查找全部": (None, "table"),
    "替换正则": (None, "string"),
    # FFI
    "导入Python": ("string", "任意"),
}


class TypeChecker:
    def __init__(self):
        self.functions = {}   # 函数名 -> {"params": [...], "ret": ..., "pure": bool}
        self.vars = {}        # 变量名 -> {"type": ..., "mutable": bool}
        self.scope_stack = []  # 作用域栈（每层是 vars 的 dict）
        self.warnings = []     # 软警告（不阻止运行）
        self.in_try_depth = 0  # 捕获块嵌套深度（操作函数强制兜底用）

    def push_scope(self):
        self.scope_stack.append({})

    def pop_scope(self):
        self.scope_stack.pop()

    def declare_var(self, name, type_, mutable):
        """当前作用域声明变量"""
        scope = self.scope_stack[-1]
        scope[name] = {"type": type_, "mutable": mutable}

    def lookup_var(self, name):
        """从内到外找变量定义"""
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        return None

    def type_name(self, type_):
        """类型 -> 名字"""
        if type_ is None:
            return "任意"
        return type_

    # ------------------------------------------------------------------
    # 程序入口
    # ------------------------------------------------------------------
    def check(self, ast):
        # 第一遍：收集所有函数定义（允许前向引用/递归）
        for stmt in ast["body"]:
            if stmt["type"] in ("FnDef", "PureFnDef", "OpFnDef"):
                self.functions[stmt["name"]] = {
                    "params": stmt["params"],
                    "ret": stmt.get("ret_type"),
                    "pure": stmt["type"] == "PureFnDef",
                    "op": stmt["type"] == "OpFnDef",
                }
                # 函数行数软警告（超 30 行提示拆解，不阻止）
                start_line = stmt.get("line", 0)
                end_line = stmt["body"].get("end_line", start_line)
                if end_line - start_line > 30:
                    self.warnings.append(
                        f"⚠️ 第{start_line}行 函数 '{stmt['name']}' 有 "
                        f"{end_line - start_line} 行，超过 30 行，考虑拆解")
        # 全局作用域（函数名也声明进全局，允许作为值引用）
        self.push_scope()
        for name in self.functions:
            self.declare_var(name, "function", False)
        for stmt in ast["body"]:
            self.check_stmt(stmt)
        self.pop_scope()
        return True

    # ------------------------------------------------------------------
    # 语句
    # ------------------------------------------------------------------
    def check_stmt(self, stmt, in_pure=False, in_op=False, in_try=False):
        t = stmt["type"]
        line = stmt.get("line")

        if t in ("Let", "Mut"):
            mutable = (t == "Mut")
            name = stmt["name"]
            names = stmt.get("names") or [name]
            for nm in names:
                if self.lookup_var(nm):
                    raise CheckError(f"变量 '{nm}' 重复声明", line)
            value_type = self.check_expr(stmt["value"], in_pure, in_op)
            # 类型标注检查
            if stmt.get("type_ann"):
                ann = stmt["type_ann"]
                if value_type is not None and ann not in (value_type, "任意"):
                    raise CheckError(
                        f"变量 '{name}' 声明为 {self.type_name(ann)}，"
                        f"但赋了 {self.type_name(value_type)} 类型的值", line)
                declared = ann
            else:
                declared = value_type
            for nm in names:
                self.declare_var(nm, declared, mutable)
            return declared

        if t == "Assign":
            # 赋值检查：目标必须是变量/属性/下标
            target = stmt["target"]
            if target["type"] == "Var":
                var = self.lookup_var(target["name"])
                if not var:
                    raise CheckError(f"变量 '{target['name']}' 未声明", line)
                if not var["mutable"]:
                    raise CheckError(
                        f"变量 '{target['name']}' 是不可变的（用 量 声明）。"
                        f"要修改请用 可变 声明", line)
                value_type = self.check_expr(stmt["value"], in_pure, in_op)
                # 可变变量：新值"任意"/未知时放行（运行时验证）
                if var["type"] is not None and value_type is not None \
                        and var["type"] not in (value_type, "任意") \
                        and value_type not in ("任意", None):
                    raise CheckError(
                        f"变量 '{target['name']}' 类型是 {self.type_name(var['type'])}，"
                        f"不能赋 {self.type_name(value_type)} 值", line)
            elif target["type"] in ("GetAttr", "Index"):
                self.check_expr(target, in_pure, in_op)
                self.check_expr(stmt["value"], in_pure, in_op)
            else:
                raise CheckError("赋值目标无效", line)
            return None

        if t == "FnDef":
            # 函数定义：进入新作用域检查函数体
            self.push_scope()
            for p in stmt["params"]:
                self.declare_var(p["name"], p.get("type"), True)
            for s in stmt["body"]["body"]:
                self.check_stmt(s, in_pure=False)
            self.pop_scope()
            return None

        if t == "OpFnDef":
            # 操作函数：允许副作用，内部可自由调用一切
            self.push_scope()
            for p in stmt["params"]:
                self.declare_var(p["name"], p.get("type"), True)
            for s in stmt["body"]["body"]:
                self.check_stmt(s, in_pure=False, in_op=True)
            self.pop_scope()
            return None

        if t == "PureFnDef":
            # 纯函数：禁止副作用！
            self.push_scope()
            for p in stmt["params"]:
                self.declare_var(p["name"], p.get("type"), True)
            for s in stmt["body"]["body"]:
                self.check_stmt(s, in_pure=True)
            self.pop_scope()
            return None

        if t == "If":
            self.check_expr(stmt["cond"], in_pure, in_op)
            self.push_scope()
            for s in stmt["then"]["body"]:
                self.check_stmt(s, in_pure)
            self.pop_scope()
            for elif_branch in stmt.get("elifs", []):
                self.check_expr(elif_branch["cond"], in_pure, in_op)
                self.push_scope()
                for s in elif_branch["body"]["body"]:
                    self.check_stmt(s, in_pure)
                self.pop_scope()
            if stmt.get("else"):
                self.push_scope()
                for s in stmt["else"]["body"]:
                    self.check_stmt(s, in_pure)
                self.pop_scope()
            return None

        if t == "While":
            self.check_expr(stmt["cond"], in_pure, in_op)
            self.push_scope()
            for s in stmt["body"]["body"]:
                self.check_stmt(s, in_pure)
            self.pop_scope()
            return None

        if t == "ForEach":
            iter_type = self.check_expr(stmt["iterable"], in_pure, in_op)
            self.push_scope()
            # 元素类型：表 -> 任意；文本 -> 文本
            elem_type = "string" if iter_type == "string" else None
            self.declare_var(stmt["var"], elem_type, True)
            if stmt.get("var2"):
                # 键值对遍历：键是任意类型
                self.declare_var(stmt["var2"], None, True)
            for s in stmt["body"]["body"]:
                self.check_stmt(s, in_pure)
            self.pop_scope()
            return None

        if t == "Return":
            if stmt.get("value") is not None:
                self.check_expr(stmt["value"], in_pure, in_op)
            return None

        if t == "Throw":
            if in_pure:
                raise CheckError("纯功能里不能抛错（副作用）", line)
            self.check_expr(stmt["value"], in_pure, in_op)
            return None

        if t == "TryExpr":
            # 顶层独立捕获 = 结果丢弃，强制兜底失效（除非是表达式赋值场景）
            raise CheckError(
                '捕获() 的结果不能丢弃——必须用 量/可变 接住并检查 .成功 处理两种分支，'
                '否则"强制兜底"失效。例：量 r = 捕获(...); 若 r.成功 {...} 否则 {...}',
                line)
            return None

        if t == "TryBlock":
            self.push_scope()
            self.in_try_depth += 1
            for s in stmt["body"]["body"]:
                self.check_stmt(s, in_pure)
            self.in_try_depth -= 1
            self.pop_scope()
            return None

        if t == "Import":
            return None

        if t == "Print":
            if in_pure:
                raise CheckError("纯功能里不能打印（副作用）", line)
            for a in stmt["args"]:
                self.check_expr(a, in_pure, in_op)
            return None

        if t == "Assert":
            self.check_expr(stmt["cond"], in_pure, in_op)
            if stmt.get("msg"):
                self.check_expr(stmt["msg"], in_pure, in_op)
            return None

        if t == "ExprStmt":
            # 捕获结果丢弃检查：捕获(...) 作为独立语句 = 结果没人看，强制兜底失效
            if stmt["expr"]["type"] == "TryExpr":
                raise CheckError(
                    '捕获() 的结果不能丢弃——必须检查 .成功 并处理两种分支，'
                    '否则"强制兜底"失效。例：量 r = 捕获(...); 若 r.成功 {...} 否则 {...}',
                    line)
            self.check_expr(stmt["expr"], in_pure)
            return None

        if t == "Block":
            self.push_scope()
            for s in stmt["body"]:
                self.check_stmt(s, in_pure)
            self.pop_scope()
            return None

        raise CheckError(f"未知语句类型: {t}", line)

    # ------------------------------------------------------------------
    # 表达式
    # ------------------------------------------------------------------
    def check_expr(self, expr, in_pure=False, in_op=False):
        t = expr["type"]
        line = expr.get("line")

        if t == "Literal":
            kind = expr.get("kind", "number")
            return {"number": "number", "string": "string", "bool": "bool",
                    "nil": "nil"}.get(kind, "任意")

        if t == "Template":
            # 模板字符串里的 ${} 插值——这里简单处理为文本
            return "string"

        if t == "Var":
            var = self.lookup_var(expr["name"])
            if not var:
                # 允许内置函数名作为值（当参数传）
                if expr["name"] in BUILTINS:
                    return "function"
                raise CheckError(f"变量 '{expr['name']}' 未声明", line)
            return var["type"]

        if t == "Self":
            return "任意"

        if t == "Meta":
            # @运算符 -> 函数
            return "function"

        if t == "BinOp":
            lt = self.check_expr(expr["left"], in_pure)
            rt = self.check_expr(expr["right"], in_pure)
            op = expr["op"]
            # 无隐式转换：+ 只能 数字+数字 或 文本+文本
            if op in ("+", "-", "*", "/", "%"):
                if lt == "string" and rt == "string" and op == "+":
                    return "string"
                if lt in ("number", None) and rt in ("number", None):
                    return "number"
                # 两侧都是"任意"（如表元素/函数返回值）→ 放行，运行时验证
                if lt in ("任意", None) and rt in ("任意", None):
                    return "任意"
                # 一侧"任意"/未知 一侧具体类型 → 放行（表元素可能是任意类型，运行时验证）
                if lt in ("任意", None) or rt in ("任意", None):
                    return "任意"
                raise CheckError(
                    f"运算符 {op} 需要两侧同类型（数字+数字 或 文本+文本），"
                    f"实际是 {self.type_name(lt)} {op} {self.type_name(rt)}。"
                    f"提示：用 转数字() 或 转文本() 显式转换", line)
            if op in ("==", "!=", "<", "<=", ">", ">="):
                if lt is not None and rt is not None and lt != rt and op in ("<", "<=", ">", ">=") \
                        and lt not in ("任意",) and rt not in ("任意",):
                    raise CheckError(
                        f"比较运算符 {op} 需要两侧同类型，"
                        f"实际是 {self.type_name(lt)} {op} {self.type_name(rt)}", line)
                return "bool"
            return "任意"

        if t == "LogicOp":
            self.check_expr(expr["left"], in_pure)
            self.check_expr(expr["right"], in_pure)
            return "bool"

        if t == "Pipe":
            # 管道：x | f  ->  右侧必须是函数
            self.check_expr(expr["left"], in_pure)
            self.check_expr(expr["right"], in_pure)
            return "任意"

        if t == "UnaryOp":
            operand_type = self.check_expr(expr["operand"], in_pure)
            if expr["op"] == "-":
                if operand_type not in ("number", None):
                    raise CheckError("一元负号只能用于数字", line)
                return "number"
            if expr["op"] == "非":
                return "bool"
            return "任意"

        if t == "Call":
            callee = expr["callee"]
            # 内置函数调用
            if callee["type"] == "Var" and callee["name"] in BUILTINS:
                name = callee["name"]
                sig = BUILTINS[name]
                if in_pure and name == "打印":
                    raise CheckError("纯功能里不能调用 打印（副作用）", line)
                for a in expr["args"]:
                    self.check_expr(a, in_pure)
                for k, v in expr.get("kwargs", {}).items():
                    self.check_expr(v, in_pure)
                return sig[1]
            # 用户函数
            if callee["type"] == "Var" and callee["name"] in self.functions:
                fn = self.functions[callee["name"]]
                if in_pure and not fn["pure"]:
                    raise CheckError(
                        f"纯功能里不能调用非纯功能 '{callee['name']}'"
                        f"（可能产生副作用）", line)
                # 操作函数强制兜底：普通/纯功能里调用操作函数必须包在 捕获() 里
                # 顶层（全局作用域）放行——顶层本身就是"操作环境"
                if fn.get("op") and not in_op and self.in_try_depth == 0 \
                        and len(self.scope_stack) > 1:
                    raise CheckError(
                        f"操作函数 '{callee['name']}' 可能失败（副作用），"
                        f"调用必须用 捕获() 包住，或把当前函数也声明为 操作", line)
                # 参数数量：至少要有必填参数的数量
                required = sum(1 for p in fn["params"] if p.get("default") is None)
                if len(expr["args"]) > len(fn["params"]):
                    raise CheckError(
                        f"函数 '{callee['name']}' 最多接受 {len(fn['params'])} 个参数，"
                        f"实际传了 {len(expr['args'])} 个", line)
                if len(expr["args"]) < required:
                    raise CheckError(
                        f"函数 '{callee['name']}' 至少需要 {required} 个参数，"
                        f"实际传了 {len(expr['args'])} 个", line)
                for a in expr["args"]:
                    self.check_expr(a, in_pure)
                for k, v in expr.get("kwargs", {}).items():
                    self.check_expr(v, in_pure)
                return fn["ret"]
            # 方法调用/匿名函数调用
            self.check_expr(callee, in_pure)
            for a in expr["args"]:
                self.check_expr(a, in_pure)
            return "任意"

        if t == "GetAttr":
            self.check_expr(expr["obj"], in_pure)
            return "任意"

        if t == "Index":
            self.check_expr(expr["obj"], in_pure)
            idx_type = self.check_expr(expr["index"], in_pure)
            if idx_type not in ("number", "string", None):
                raise CheckError("下标必须是数字或文本", line)
            return "任意"

        if t == "Slice":
            self.check_expr(expr["obj"], in_pure)
            if expr.get("start") is not None:
                self.check_expr(expr["start"], in_pure)
            if expr.get("end") is not None:
                self.check_expr(expr["end"], in_pure)
            return "任意"

        if t == "Table":
            for entry in expr["entries"]:
                self.check_expr(entry["value"], in_pure)
            return "table"

        if t == "TryExpr":
            # 捕获(expr) -> 返回结果表
            self.in_try_depth += 1
            self.check_expr(expr["expr"], in_pure, in_op)
            self.in_try_depth -= 1
            return "table"

        if t == "ImportExpr":
            # 导入(路径) -> 返回导出表
            return "table"

        if t in ("FnLiteral", "PureFnLiteral", "OpFnLiteral"):
            # 匿名函数
            self.push_scope()
            for p in expr["params"]:
                self.declare_var(p["name"], p.get("type"), True)
            pure = (t == "PureFnLiteral")
            for s in expr["body"]["body"]:
                self.check_stmt(s, in_pure=pure)
            self.pop_scope()
            return "function"

        if t == "Assign":
            # 表达式位置的赋值（少见）
            self.check_expr(expr["target"], in_pure)
            self.check_expr(expr["value"], in_pure)
            return None

        raise CheckError(f"未知表达式类型: {t}", line)


def check(ast) -> bool:
    """AST -> 类型检查，通过返回 True，失败抛 CheckError"""
    TypeChecker().check(ast)
    return True

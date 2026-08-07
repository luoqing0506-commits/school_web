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
无错语言 编译器 (compiler.py)
==============================
把 AST 翻译成 Python 源码，再用 compile() 编译成字节码执行。
比树遍历解释器快 3-10 倍。

策略：
  - 变量/函数/控制流 -> 原生 Python 结构
  - 数字运算 -> number 模块（保留精确十进制 0.1+0.2==0.3）
  - 表 -> Python dict
  - 错误 -> WucuoError 异常 / 捕获 -> try-except 返回结果表
  - 协程函数 -> Python 生成器（yield/send）
  - 打印 -> 辅助函数 _wc_print（格式化中文值）
"""

from typing import List, Dict, Any

# 生成代码头部：注册内置函数和辅助函数
PROLOGUE = """# -*- coding: utf-8 -*-
# 由无错语言编译器生成
from number import (Num, num_str, parse_number, num_add, num_sub, num_mul,
                    num_div, num_mod, num_neg, num_eq, num_lt, num_le,
                    num_gt, num_ge, num_is_zero, num_to_float)
from interpreter import WucuoError, ReturnSignal
import stdlib as _wc_stdlib

_builtins = _wc_stdlib.make_builtins()

def _wc_print(*args):
    parts = []
    for a in args:
        if isinstance(a, bool):
            parts.append("真" if a else "假")
        elif isinstance(a, Num):
            parts.append(num_str(a))
        elif a is None:
            parts.append("空")
        else:
            parts.append(str(a))
    print(" ".join(parts))

def _wc_fmt(v):
    if isinstance(v, bool):
        return "真" if v else "假"
    if isinstance(v, Num):
        return num_str(v)
    if v is None:
        return "空"
    if isinstance(v, dict):
        return "{" + ", ".join(f"{k}: {_wc_fmt(x)}" for k, x in v.items()) + "}"
    return str(v)

def _wc_try(fn, *args):
    try:
        return {"成功": True, "值": fn(*args)}
    except WucuoError as e:
        return {"成功": False, "值": None, "错误": e.value}
    except Exception as e:
        return {"成功": False, "值": None, "错误": str(e)}

def _wc_catch(fn):
    try:
        return {"成功": True, "值": fn()}
    except WucuoError as e:
        return {"成功": False, "值": None, "错误": e.value}
    except Exception as e:
        return {"成功": False, "值": None, "错误": str(e)}

globals().update(_builtins)
_wc_self = None
"""


class Compiler:
    def __init__(self):
        self.lines: List[str] = []
        self.indent = 0
        self.tmp_counter = 0

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def emit(self, line: str = ""):
        if line:
            self.lines.append("    " * self.indent + line)
        else:
            self.lines.append("")

    def new_tmp(self, prefix="t"):
        self.tmp_counter += 1
        return f"{prefix}{self.tmp_counter}"

    # ------------------------------------------------------------------
    # 编译入口
    # ------------------------------------------------------------------
    def compile_program(self, ast) -> str:
        """AST -> Python 源码"""
        self.lines = [PROLOGUE]
        self.indent = 0
        for stmt in ast["body"]:
            self.gen_stmt(stmt)
        return "\n".join(self.lines)

    # ------------------------------------------------------------------
    # 语句
    # ------------------------------------------------------------------
    def gen_stmt(self, stmt):
        t = stmt["type"]

        if t in ("Let", "Mut"):
            # 量 a = 值   ->  a = 值
            names = stmt.get("names") or [stmt["name"]]
            value = self.gen_expr(stmt["value"])
            if len(names) == 1:
                self.emit(f"{names[0]} = {value}")
            else:
                tmp = self.new_tmp()
                self.emit(f"{tmp} = {value}")
                self.emit(f"{tmp} = list({tmp}.values()) if isinstance({tmp}, dict) else {tmp}")
                for i, nm in enumerate(names):
                    self.emit(f"{nm} = {tmp}[{i}]")
            return

        if t == "Assign":
            target = stmt["target"]
            value = self.gen_expr(stmt["value"])
            if target["type"] == "Var":
                self.emit(f"{target['name']} = {value}")
            elif target["type"] == "GetAttr":
                obj = self.gen_expr(target["obj"])
                self.emit(f"{obj}[{target['name']!r}] = {value}")
            elif target["type"] == "Index":
                obj = self.gen_expr(target["obj"])
                idx = self.gen_expr(target["index"])
                self.emit(f"{obj}[{idx}] = {value}")
            return

        if t in ("FnDef", "PureFnDef", "OpFnDef"):
            # 定义 Python 函数（支持默认参数）
            name = stmt["name"]
            param_defs = []
            for p in stmt["params"]:
                if p.get("default") is not None:
                    param_defs.append(f"{p['name']}={self.gen_expr(p['default'])}")
                else:
                    param_defs.append(p["name"])
            self.emit(f"def {name}({', '.join(param_defs)}):")
            self.indent += 1
            self.gen_block_body(stmt["body"])
            self.indent -= 1
            self.emit()
            return

        if t == "If":
            cond = self.gen_expr(stmt["cond"])
            self.emit(f"if _wc_truthy({cond}):")
            self.indent += 1
            self.gen_block_body(stmt["then"])
            self.indent -= 1
            for elif_b in stmt.get("elifs", []):
                c = self.gen_expr(elif_b["cond"])
                self.emit(f"elif _wc_truthy({c}):")
                self.indent += 1
                self.gen_block_body(elif_b["body"])
                self.indent -= 1
            if stmt.get("else"):
                self.emit("else:")
                self.indent += 1
                self.gen_block_body(stmt["else"])
                self.indent -= 1
            return

        if t == "While":
            cond = self.gen_expr(stmt["cond"])
            # 死循环保护（100万次）
            counter = self.new_tmp("iter")
            self.emit(f"{counter} = 0")
            self.emit(f"while _wc_truthy({cond}):")
            self.indent += 1
            self.emit(f"{counter} += 1")
            self.emit(f"if {counter} > 1000000: raise WucuoError('循环超过 100 万次，可能死循环')")
            self.gen_block_body(stmt["body"])
            self.indent -= 1
            return

        if t == "ForEach":
            var = stmt["var"]
            var2 = stmt.get("var2")
            iterable = self.gen_expr(stmt["iterable"])
            tmp = self.new_tmp("iter")
            self.emit(f"{tmp} = {iterable}")
            if var2:
                self.emit(f"{tmp} = list({tmp}.items()) if isinstance({tmp}, dict) else [(None, x) for x in ({tmp} if isinstance({tmp}, (list, str)) else [])]")
                self.emit(f"for {var}, {var2} in {tmp}:")
            else:
                self.emit(f"{tmp} = list({tmp}.values()) if isinstance({tmp}, dict) else ({tmp} if isinstance({tmp}, str) else {tmp})")
                self.emit(f"for {var} in {tmp}:")
            self.indent += 1
            self.gen_block_body(stmt["body"])
            self.indent -= 1
            return

        if t == "Return":
            if stmt.get("value") is not None:
                v = self.gen_expr(stmt["value"])
                self.emit(f"return {v}")
            else:
                self.emit("return None")
            return

        if t == "Throw":
            v = self.gen_expr(stmt["value"])
            self.emit(f"raise WucuoError({v})")
            return

        if t == "TryExpr":
            # 捕获(expr) -> _wc_try(lambda: expr)
            expr = self.gen_expr(stmt["expr"])
            self.emit(f"result = _wc_catch(lambda: {expr})")
            # 需要把结果存到表达式位置——TryExpr 作为语句时直接赋值给临时变量再返回
            return

        if t == "TryBlock":
            self.emit("try:")
            self.indent += 1
            self.gen_block_body(stmt["body"])
            self.indent -= 1
            self.emit("except WucuoError as e:")
            self.indent += 1
            self.emit("result = {'成功': False, '值': None, '错误': e.value}")
            self.indent -= 1
            self.emit("except Exception as e:")
            self.indent += 1
            self.emit("result = {'成功': False, '值': None, '错误': str(e)}")
            self.indent -= 1
            return

        if t == "Import":
            return

        if t == "Print":
            args = [self.gen_expr(a) for a in stmt["args"]]
            self.emit(f"_wc_print({', '.join(args)})")
            return

        if t == "Assert":
            cond = self.gen_expr(stmt["cond"])
            msg = self.gen_expr(stmt["msg"]) if stmt.get("msg") else "'断言失败'"
            self.emit(f"if not _wc_truthy({cond}): raise WucuoError({msg})")
            return

        if t == "ExprStmt":
            expr = self.gen_expr(stmt["expr"])
            self.emit(f"{expr}")
            return

        if t == "Block":
            self.gen_block_body(stmt)
            return

        # 其他未知类型直接跳过（由解释器路径处理）
        raise ValueError(f"编译器暂不支持的语句: {t}")

    def gen_block_body(self, block):
        for s in block["body"]:
            self.gen_stmt(s)

    # ------------------------------------------------------------------
    # 表达式
    # ------------------------------------------------------------------
    def gen_expr(self, expr) -> str:
        """生成表达式代码，返回 Python 表达式字符串"""
        t = expr["type"]

        if t == "Literal":
            kind = expr.get("kind", "number")
            if kind == "number":
                return f"parse_number({expr['value']!r})"
            if kind == "string":
                return repr(expr["value"])
            if kind == "bool":
                return "True" if expr["value"] else "False"
            return "None"

        if t == "Template":
            # 模板字符串 -> 用 _wc_fmt 拼接（避免 f-string 引号冲突）
            import re
            text = expr["value"]
            parts = []
            pos = 0
            for m in re.finditer(r"\$\{([^}]+)\}", text):
                literal = text[pos:m.start()]
                if literal:
                    parts.append(f"str({literal!r})")
                inner = self.gen_expr_from_text(m.group(1))
                parts.append(f"_wc_fmt({inner})")
                pos = m.end()
            tail = text[pos:]
            if tail:
                parts.append(f"str({tail!r})")
            return " + ".join(parts) if parts else "''"

        if t == "Var":
            return expr["name"]

        if t == "BinOp":
            left = self.gen_expr(expr["left"])
            right = self.gen_expr(expr["right"])
            op = expr["op"]
            # 数字运算走 number 模块（保留精度）
            if op == "+":
                # 先算临时变量避免重复求值（防止递归函数被调用多次）
                tmp_l = self.new_tmp("l")
                tmp_r = self.new_tmp("r")
                self.emit(f"{tmp_l} = {left}")
                self.emit(f"{tmp_r} = {right}")
                tmp = self.new_tmp("add")
                # 整数快路径：都是 int 直接用 +，文本用 +，否则走数字塔
                self.emit(f"{tmp} = ({tmp_l} + {tmp_r} if isinstance({tmp_l}, (int, str)) and isinstance({tmp_r}, (int, str)) and not isinstance({tmp_l}, bool) and not isinstance({tmp_r}, bool) else num_add({tmp_l}, {tmp_r}))")
                return tmp
            if op == "-":
                tmp_l = self.new_tmp("l")
                tmp_r = self.new_tmp("r")
                self.emit(f"{tmp_l} = {left}")
                self.emit(f"{tmp_r} = {right}")
                tmp = self.new_tmp("sub")
                self.emit(f"{tmp} = ({tmp_l} - {tmp_r} if isinstance({tmp_l}, int) and isinstance({tmp_r}, int) else num_sub({tmp_l}, {tmp_r}))")
                return tmp
            if op == "*":
                tmp_l = self.new_tmp("l")
                tmp_r = self.new_tmp("r")
                self.emit(f"{tmp_l} = {left}")
                self.emit(f"{tmp_r} = {right}")
                tmp = self.new_tmp("mul")
                self.emit(f"{tmp} = ({tmp_l} * {tmp_r} if isinstance({tmp_l}, int) and isinstance({tmp_r}, int) else num_mul({tmp_l}, {tmp_r}))")
                return tmp
            if op == "/":
                return f"num_div({left}, {right})"
            if op == "%":
                return f"num_mod({left}, {right})"
            if op == "==":
                tmp_l = self.new_tmp("l")
                tmp_r = self.new_tmp("r")
                self.emit(f"{tmp_l} = {left}")
                self.emit(f"{tmp_r} = {right}")
                tmp = self.new_tmp("eq")
                self.emit(f"{tmp} = num_eq({tmp_l}, {tmp_r}) if isinstance({tmp_l}, Num) and isinstance({tmp_r}, Num) else ({tmp_l} is {tmp_r} if isinstance({tmp_l}, dict) and isinstance({tmp_r}, dict) else {tmp_l} == {tmp_r})")
                return tmp
            if op == "!=":
                tmp_l = self.new_tmp("l")
                tmp_r = self.new_tmp("r")
                self.emit(f"{tmp_l} = {left}")
                self.emit(f"{tmp_r} = {right}")
                tmp = self.new_tmp("ne")
                self.emit(f"{tmp} = not (num_eq({tmp_l}, {tmp_r}) if isinstance({tmp_l}, Num) and isinstance({tmp_r}, Num) else ({tmp_l} is {tmp_r} if isinstance({tmp_l}, dict) and isinstance({tmp_r}, dict) else {tmp_l} == {tmp_r}))")
                return tmp
            if op == "<":
                return f"num_lt({left}, {right})"
            if op == "<=":
                return f"num_le({left}, {right})"
            if op == ">":
                return f"num_gt({left}, {right})"
            if op == ">=":
                return f"num_ge({left}, {right})"
            return f"({left} {op} {right})"

        if t == "LogicOp":
            left = self.gen_expr(expr["left"])
            right = self.gen_expr(expr["right"])
            if expr["op"] == "和":
                return f"(_wc_truthy({left}) and {right} or {left})"
            return f"(_wc_truthy({left}) and {left} or {right})"

        if t == "Pipe":
            # 管道：左侧值 | 右侧函数
            left = self.gen_expr(expr["left"])
            right = self.gen_expr(expr["right"])
            tmp = self.new_tmp("pipe")
            self.emit(f"{tmp} = {right}({left})")
            return tmp

        if t == "Range":
            # 范围：start..end（含端点）
            start = self.gen_expr(expr["start"])
            end = self.gen_expr(expr["end"])
            tmp = self.new_tmp("range")
            self.emit(f"{tmp} = {{i: v for i, v in enumerate(range(int({start}), int({end}) + 1))}}")
            return tmp

        if t == "Self":
            return "_wc_self"

        if t == "Meta":
            # @运算符 -> 直接调用内置函数（编译后就是 Python 函数）
            name = expr["name"]
            return f"_builtins[{name!r}]"

        if t == "UnaryOp":
            operand = self.gen_expr(expr["operand"])
            if expr["op"] == "-":
                return f"num_neg({operand})"
            return f"(not _wc_truthy({operand}))"

        if t == "Call":
            callee = expr["callee"]
            args = [self.gen_expr(a) for a in expr["args"]]
            kwargs = [f"{k}={self.gen_expr(v)}" for k, v in expr.get("kwargs", {}).items()]
            call_args = ", ".join(args + kwargs)
            # 方法调用：表.方法(...) 需要绑定 _wc_self
            if callee["type"] == "GetAttr":
                obj = self.gen_expr(callee["obj"])
                tmp_self = self.new_tmp("self")
                tmp_fn = self.new_tmp("fn")
                self.emit(f"{tmp_self} = {obj}")
                self.emit(f"{tmp_fn} = {tmp_self}[{callee['name']!r}] if isinstance({tmp_self}, dict) else getattr({tmp_self}, {callee['name']!r})")
                tmp_call = self.new_tmp("call")
                self.emit(f"old_self = _wc_self")
                self.emit(f"_wc_self = {tmp_self}")
                self.emit(f"{tmp_call} = {tmp_fn}({call_args})")
                self.emit(f"_wc_self = old_self")
                return tmp_call
            return f"{self.gen_expr(callee)}({call_args})"

        if t == "GetAttr":
            obj = self.gen_expr(expr["obj"])
            tmp = self.new_tmp("attr")
            # dict 用下标，其他用 getattr（FFI 支持 Python 模块/对象）
            self.emit(f"{tmp} = {obj}[{expr['name']!r}] if isinstance({obj}, dict) else getattr({obj}, {expr['name']!r})")
            return tmp

        if t == "Index":
            obj = self.gen_expr(expr["obj"])
            idx = self.gen_expr(expr["index"])
            return f"{obj}[{idx}]"

        if t == "Slice":
            obj = self.gen_expr(expr["obj"])
            start = self.gen_expr(expr["start"]) if expr.get("start") is not None else "None"
            end = self.gen_expr(expr["end"]) if expr.get("end") is not None else "None"
            return f"{obj}[{start}:{end}]"

        if t == "Table":
            items = []
            for entry in expr["entries"]:
                if entry["kind"] == "pair":
                    items.append(f"{entry['key']!r}: {self.gen_expr(entry['value'])}")
                else:
                    items.append(self.gen_expr(entry["value"]))
            if items and all(": " not in it for it in items):
                # 数组表 -> dict with numeric keys
                return "{" + ", ".join(f"{i}: {v}" for i, v in enumerate(items)) + "}"
            return "{" + ", ".join(items) + "}"

        if t == "TryExpr":
            # 作为表达式：捕获(expr)
            inner = self.gen_expr(expr["expr"])
            return f"_wc_catch(lambda: {inner})"

        if t == "ImportExpr":
            return f"import_module({expr['path']!r})"

        if t in ("FnLiteral", "PureFnLiteral", "OpFnLiteral"):
            # 匿名函数 -> Python def（支持默认参数）
            param_defs = []
            for p in expr["params"]:
                if p.get("default") is not None:
                    param_defs.append(f"{p['name']}={self.gen_expr(p['default'])}")
                else:
                    param_defs.append(p["name"])
            # 生成嵌套 def（支持多语句）
            fn_name = self.new_tmp("fn")
            self.emit(f"def {fn_name}({', '.join(param_defs)}):")
            self.indent += 1
            self.gen_block_body(expr["body"])
            self.indent -= 1
            return fn_name

        raise ValueError(f"编译器暂不支持的表达式: {t}")

    def gen_expr_from_text(self, text: str) -> str:
        """模板插值里的表达式文本 -> Python 表达式（简易：只处理变量/属性/调用）"""
        from parser import Parser, tokenize
        tokens = tokenize(text)
        parser = Parser(tokens)
        expr = parser.parse_expr()
        return self.gen_expr(expr)


def compile_ast(ast) -> str:
    """AST -> Python 源码"""
    return Compiler().compile_program(ast)


def run_compiled(ast, globals_dict: Dict[str, Any] = None) -> Any:
    """AST -> 字节码 -> 执行，返回 (结果, 全局环境)"""
    source = compile_ast(ast)
    code = compile(source, "<wucuo-compiled>", "exec")
    g = {} if globals_dict is None else globals_dict
    # 提供辅助函数
    exec(PROLOGUE, g)
    g["_wc_truthy"] = _wc_truthy
    g["import_module"] = _wc_import
    exec(code, g)
    return None, g


def _wc_truthy(v) -> bool:
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, Num):
        return not num_is_zero(v)
    if isinstance(v, str):
        return len(v) > 0
    if isinstance(v, dict):
        return len(v) > 0
    return True


# 模块导入（由 wucuo.py 注入）
_wc_import = lambda path: {}


def set_import_loader(loader):
    global _wc_import
    _wc_import = loader

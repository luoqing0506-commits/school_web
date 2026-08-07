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
无错语言 C 编译器 (compiler_c.py)
=================================
把 AST 编译成 C 代码，配合 crt/wucuo_rt.c 编译成原生可执行文件。
追求极致性能：数字用 double、函数变 C 函数、循环变 C 循环。

支持子集（编译模式第一版）：
  数字/文本/布尔/空 字面量、变量、算术、比较、逻辑
  功能/纯功能/操作 函数定义与调用、递归
  若/否则若/否则、循环、对...在 遍历
  返回、打印、表（基础）、注释
  转文本/转数字/长度/类型 内置函数
"""
import re
from typing import List


class CCompiler:
    def __init__(self):
        self.lines: List[str] = []
        self.indent = 0
        self.func_names = set()
        self.global_vars = set()

    def emit(self, line: str = ""):
        if line:
            self.lines.append("    " * self.indent + line)
        else:
            self.lines.append("")

    def compile_program(self, ast) -> str:
        self.lines = []
        self.emit("/* 由无错语言 C 编译器生成 */")
        self.emit('#include "wucuo_rt.h"')
        self.emit("#include <stdio.h>")
        self.emit()
        self.emit("static wc_value wc_global_error;")
        self.emit()
        # 收集函数名 -> 生成前向声明
        for stmt in ast["body"]:
            if stmt["type"] in ("FnDef", "PureFnDef", "OpFnDef"):
                fname = self.c_ident(stmt["name"])
                self.func_names.add(fname)
        for fname in sorted(self.func_names):
            self.emit(f"static wc_value {fname}(wc_value *args, int argc);")
        self.emit()
        # 生成主函数
        self.emit("int main(void) {")
        self.indent += 1
        for stmt in ast["body"]:
            self.gen_stmt(stmt)
        self.emit("return 0;")
        self.indent -= 1
        self.emit("}")
        self.emit()
        # 生成函数定义
        for stmt in ast["body"]:
            if stmt["type"] in ("FnDef", "PureFnDef", "OpFnDef"):
                self.gen_func_def(stmt)
        return "\n".join(self.lines)

    def c_ident(self, name: str) -> str:
        """中文名 -> C 标识符（转成拼音/编码形式）"""
        # 用 Unicode 码点生成唯一标识符
        ident = "_f"
        for ch in name:
            if ch.isalnum():
                ident += f"_{ord(ch):x}"
            else:
                ident += f"_{ord(ch):x}"
        return ident

    # ------------------------------------------------------------------
    # 语句
    # ------------------------------------------------------------------
    def gen_stmt(self, stmt):
        t = stmt["type"]
        if t in ("Let", "Mut"):
            names = stmt.get("names") or [stmt["name"]]
            expr = self.gen_expr(stmt["value"])
            if len(names) == 1:
                vname = self.c_ident(stmt["name"])
                self.global_vars.add(vname)
                self.emit(f"wc_value {vname} = {expr};")
            else:
                tmp = self.gen_tmp()
                self.emit(f"wc_value {tmp} = {expr};")
                for i, nm in enumerate(names):
                    vname = self.c_ident(nm)
                    self.global_vars.add(vname)
                    self.emit(f"wc_value {vname} = wc_table_get({tmp}.table, \"{i}\", NULL);")
            return

        if t == "Assign":
            target = stmt["target"]
            expr = self.gen_expr(stmt["value"])
            if target["type"] == "Var":
                vname = self.c_ident(target["name"])
                self.emit(f"{vname} = {expr};")
            elif target["type"] == "GetAttr":
                obj = self.gen_expr(target["obj"])
                self.emit(f"wc_table_set({obj}.table, \"{target['name']}\", {expr});")
            return

        if t in ("FnDef", "PureFnDef", "OpFnDef"):
            # 函数定义语句在顶层跳过（单独生成）
            return

        if t == "If":
            cond = self.gen_expr(stmt["cond"])
            self.emit(f"if (wc_truthy({cond})) {{")
            self.indent += 1
            self.gen_block(stmt["then"])
            self.indent -= 1
            for elif_b in stmt.get("elifs", []):
                c = self.gen_expr(elif_b["cond"])
                self.emit(f"}} else if (wc_truthy({c})) {{")
                self.indent += 1
                self.gen_block(elif_b["body"])
                self.indent -= 1
            if stmt.get("else"):
                self.emit("} else {")
                self.indent += 1
                self.gen_block(stmt["else"])
                self.indent -= 1
            self.emit("}")
            return

        if t == "While":
            counter = self.gen_tmp("iter")
            self.emit(f"long {counter} = 0;")
            self.emit("while (1) {")
            self.indent += 1
            self.emit(f"if (++{counter} > 1000000) {{ wc_throw(\"循环超过100万次\"); break; }}")
            cond = self.gen_expr(stmt["cond"])
            self.emit(f"if (!wc_truthy({cond})) break;")
            self.gen_block(stmt["body"])
            self.indent -= 1
            self.emit("}")
            return

        if t == "ForEach":
            var = stmt["var"]
            var2 = stmt.get("var2")
            iterable = self.gen_expr(stmt["iterable"])
            # 简化：遍历表的值（数字键）
            tmp = self.gen_tmp("tbl")
            self.emit(f"wc_table *{tmp} = {iterable}.table;")
            # 遍历链表
            self.emit(f"for (wc_table_entry *e = {tmp}->head; e; e = e->next) {{")
            self.indent += 1
            vname = self.c_ident(var)
            self.emit(f"wc_value {vname} = e->value;")
            if var2:
                vname2 = self.c_ident(var2)
                self.emit(f"wc_value {vname2} = wc_str_v(e->key);")
            self.gen_block(stmt["body"])
            self.indent -= 1
            self.emit("}")
            return

        if t == "Return":
            if stmt.get("value") is not None:
                expr = self.gen_expr(stmt["value"])
                self.emit(f"return {expr};")
            else:
                self.emit("return wc_nil_v();")
            return

        if t == "Throw":
            expr = self.gen_expr(stmt["value"])
            self.emit(f"{{ char *s = wc_to_string({expr}); wc_throw(s); free(s); }}")
            return

        if t == "TryExpr":
            # 捕获(expr) -> 简化：先设置错误标志，再尝试
            expr = self.gen_expr(stmt["expr"])
            tmp = self.gen_tmp("try")
            self.emit(f"wc_value {tmp};")
            self.emit("wc_error_flag = 0;")
            self.emit(f"{{ wc_error_flag = 0; {tmp} = {expr}; }}")
            return tmp

        if t == "Print":
            args = [self.gen_expr(a) for a in stmt["args"]]
            arr = self.gen_tmp("args")
            self.emit(f"wc_value {arr}[] = {{ {', '.join(args)} }};")
            self.emit(f"wc_print_args({arr}, {len(args)});")
            return

        if t == "ExprStmt":
            expr = self.gen_expr(stmt["expr"])
            self.emit(f"{{ wc_value _r = {expr}; (void)_r; }}")
            return

        if t == "Block":
            self.gen_block(stmt)
            return

        # 其他：跳过（解释器路径处理）
        raise ValueError(f"C 编译器暂不支持语句: {t}")

    def gen_block(self, block):
        for s in block["body"]:
            self.gen_stmt(s)

    # ------------------------------------------------------------------
    # 函数定义
    # ------------------------------------------------------------------
    def gen_func_def(self, stmt):
        fname = self.c_ident(stmt["name"])
        params = stmt["params"]
        param_names = [self.c_ident(p["name"]) for p in params]
        self.emit(f"static wc_value {fname}(wc_value *args, int argc) {{")
        self.indent += 1
        for i, pname in enumerate(param_names):
            self.emit(f"wc_value {pname} = (argc > {i}) ? args[{i}] : wc_nil_v();")
        self.gen_block(stmt["body"])
        self.emit("return wc_nil_v();")
        self.indent -= 1
        self.emit("}")
        self.emit()

    # ------------------------------------------------------------------
    # 表达式
    # ------------------------------------------------------------------
    def gen_expr(self, expr) -> str:
        t = expr["type"]
        if t == "Literal":
            kind = expr.get("kind", "number")
            if kind == "number":
                return f"wc_num_v({expr['value']})"
            if kind == "string":
                return f"wc_str_v({self.c_str(expr['value'])})"
            if kind == "bool":
                return f"wc_bool_v({1 if expr['value'] else 0})"
            return "wc_nil_v()"

        if t == "Template":
            # 模板字符串 -> 拼接
            parts = []
            pos = 0
            for m in re.finditer(r"\$\{([^}]+)\}", expr["value"]):
                lit = expr["value"][pos:m.start()]
                if lit:
                    parts.append(f"wc_str_v({self.c_str(lit)})")
                inner = self.gen_expr_from_text(m.group(1))
                parts.append(f"wc_to_string({inner})")
                pos = m.end()
            tail = expr["value"][pos:]
            if tail:
                parts.append(f"wc_str_v({self.c_str(tail)})")
            # 用 wc_add 拼接（简化：两两相加）
            result = parts[0] if parts else "wc_str_v(\"\")"
            for p in parts[1:]:
                tmp = self.gen_tmp("cat")
                self.emit(f"wc_value {tmp} = wc_add({result}, wc_str_v({p}));")
                result = tmp
            return result

        if t == "Var":
            return self.c_ident(expr["name"])

        if t == "BinOp":
            left = self.gen_expr(expr["left"])
            right = self.gen_expr(expr["right"])
            op = expr["op"]
            if op == "+":
                tmp = self.gen_tmp("add")
                self.emit(f"wc_value {tmp} = wc_add({left}, {right});")
                return tmp
            if op == "-":
                tmp = self.gen_tmp("sub")
                self.emit(f"wc_value {tmp} = wc_sub({left}, {right});")
                return tmp
            if op == "*":
                tmp = self.gen_tmp("mul")
                self.emit(f"wc_value {tmp} = wc_mul({left}, {right});")
                return tmp
            if op == "/":
                tmp = self.gen_tmp("div")
                self.emit(f"wc_value {tmp} = wc_div({left}, {right});")
                return tmp
            if op == "%":
                tmp = self.gen_tmp("mod")
                self.emit(f"wc_value {tmp} = wc_mod({left}, {right});")
                return tmp
            if op == "==":
                tmp = self.gen_tmp("eq")
                self.emit(f"wc_value {tmp} = wc_bool_v(wc_eq({left}, {right}));")
                return tmp
            if op == "!=":
                tmp = self.gen_tmp("ne")
                self.emit(f"wc_value {tmp} = wc_bool_v(!wc_eq({left}, {right}));")
                return tmp
            if op == "<":
                tmp = self.gen_tmp("lt")
                self.emit(f"wc_value {tmp} = wc_bool_v(wc_lt({left}, {right}));")
                return tmp
            if op == "<=":
                tmp = self.gen_tmp("le")
                self.emit(f"wc_value {tmp} = wc_bool_v(wc_le({left}, {right}));")
                return tmp
            if op == ">":
                tmp = self.gen_tmp("gt")
                self.emit(f"wc_value {tmp} = wc_bool_v(wc_gt({left}, {right}));")
                return tmp
            if op == ">=":
                tmp = self.gen_tmp("ge")
                self.emit(f"wc_value {tmp} = wc_bool_v(wc_ge({left}, {right}));")
                return tmp
            raise ValueError(f"未知运算符: {op}")

        if t == "LogicOp":
            left = self.gen_expr(expr["left"])
            right = self.gen_expr(expr["right"])
            if expr["op"] == "和":
                tmp = self.gen_tmp("and")
                self.emit(f"wc_value {tmp} = wc_truthy({left}) ? {right} : {left};")
                return tmp
            tmp = self.gen_tmp("or")
            self.emit(f"wc_value {tmp} = wc_truthy({left}) ? {left} : {right};")
            return tmp

        if t == "Pipe":
            # 管道：x | f -> f(x)
            left = self.gen_expr(expr["left"])
            right_expr = expr["right"]
            if right_expr["type"] == "Var" and self.c_ident(right_expr["name"]) in self.func_names:
                fname = self.c_ident(right_expr["name"])
                tmp = self.gen_tmp("pipe")
                self.emit(f"wc_value {tmp} = {fname}(&{left}, 1);")
                return tmp
            raise ValueError("C 编译器管道右侧只支持命名函数")

        if t == "Range":
            raise ValueError(
                "C 编译模式暂不支持 范围(start..end) 语法。"
                "请用解释器/字节码模式运行，或改用 循环 手写。")

        if t == "UnaryOp":
            operand = self.gen_expr(expr["operand"])
            if expr["op"] == "-":
                tmp = self.gen_tmp("neg")
                self.emit(f"wc_value {tmp} = wc_neg({operand});")
                return tmp
            tmp = self.gen_tmp("not")
            self.emit(f"wc_value {tmp} = wc_bool_v(!wc_truthy({operand}));")
            return tmp

        if t == "Call":
            callee = expr["callee"]
            # C 编译模式防护：禁止 导入Python（C exe 没有 Python 运行时）
            if callee["type"] == "Var" and callee["name"] == "导入Python":
                raise ValueError(
                    "C 编译模式不支持 导入Python（原生 exe 无 Python 运行时）。"
                    "请用解释器/字节码模式运行，或改用 C 模式支持的内置函数。")
            args = [self.gen_expr(a) for a in expr["args"]]
            if callee["type"] == "Var":
                name = callee["name"]
                if name == "打印":
                    arr = self.gen_tmp("args")
                    self.emit(f"wc_value {arr}[] = {{ {', '.join(args)} }};")
                    self.emit(f"wc_print_args({arr}, {len(args)});")
                    return "wc_nil_v()"
                if name == "长度":
                    tmp = self.gen_tmp("len")
                    self.emit(f"wc_value {tmp} = wc_num_v(wc_len({args[0]}));")
                    return tmp
                if name == "类型":
                    tmp = self.gen_tmp("type")
                    self.emit(f"wc_value {tmp} = wc_str_v(wc_type_name({args[0]}));")
                    return tmp
                if name == "转文本":
                    tmp = self.gen_tmp("str")
                    self.emit(f"wc_value {tmp} = wc_str_v(wc_to_string({args[0]}));")
                    return tmp
                if name == "转数字":
                    tmp = self.gen_tmp("num")
                    self.emit(f"wc_value {tmp} = wc_num_v(atof(wc_to_string({args[0]})));")
                    return tmp
                # 用户函数
                fname = self.c_ident(name)
                arr = self.gen_tmp("fargs")
                self.emit(f"wc_value {arr}[] = {{ {', '.join(args)} }};")
                tmp = self.gen_tmp("call")
                self.emit(f"wc_value {tmp} = {fname}({arr}, {len(args)});")
                return tmp
            raise ValueError("C 编译器暂不支持函数值调用")

        if t == "GetAttr":
            obj = self.gen_expr(expr["obj"])
            tmp = self.gen_tmp("attr")
            self.emit(f"wc_value {tmp} = wc_table_get({obj}.table, \"{expr['name']}\", NULL);")
            return tmp

        if t == "Index":
            obj = self.gen_expr(expr["obj"])
            idx = self.gen_expr(expr["index"])
            tmp = self.gen_tmp("idx")
            self.emit(f"{{ char _k[32]; snprintf(_k, 32, \"%s\", wc_to_string({idx})); wc_value {tmp} = wc_table_get({obj}.table, _k, NULL); }}")
            return tmp

        if t == "Table":
            # 表字面量
            tmp = self.gen_tmp("tbl")
            self.emit(f"wc_table *{tmp} = wc_table_new();")
            for i, entry in enumerate(expr["entries"]):
                val = self.gen_expr(entry["value"])
                if entry["kind"] == "pair":
                    self.emit(f"wc_table_set({tmp}, \"{entry['key']}\", {val});")
                else:
                    self.emit(f"wc_table_set({tmp}, \"{i}\", {val});")
            return f"wc_table_v({tmp})"

        raise ValueError(f"C 编译器暂不支持表达式: {t}")

    def gen_expr_from_text(self, text: str) -> str:
        from parser import Parser, tokenize
        tokens = tokenize(text)
        parser = Parser(tokens)
        expr = parser.parse_expr()
        return self.gen_expr(expr)

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    def gen_tmp(self, prefix="t"):
        if not hasattr(self, "_tmp_n"):
            self._tmp_n = 0
        self._tmp_n += 1
        return f"{prefix}{self._tmp_n}"

    def c_str(self, s: str) -> str:
        """字符串 -> C 字符串字面量（转义）"""
        out = s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return f'"{out}"'


def compile_c(ast) -> str:
    """AST -> C 源码"""
    return CCompiler().compile_program(ast)

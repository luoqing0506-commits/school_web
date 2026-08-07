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
无错语言 语法分析器 (parser.py)
================================
递归下降解析：token 流 -> AST。

AST 节点用 dict 表示，type 字段区分节点类型：
  Program / Let / Mut / FnDef / PureFnDef / If / While / ForEach
  Return / Throw / Try / ExprStmt / Block / Call / BinOp / UnaryOp
  Assign / Table / Index / GetAttr / SetAttr / Literal / Var / Print / Assert
"""

from dataclasses import dataclass
from typing import List, Optional

from lexer import Token, tokenize

# 类型关键字 -> 内部类型名
TYPE_NAMES = {"数字": "number", "文本": "string", "布尔": "bool", "空": "nil", "表": "table", "功能": "function"}

# 二元运算符优先级（越大越优先）
BINOP_PRECEDENCE = {
    "或": 1,
    "和": 2,
    "==": 3, "!=": 3,
    "<": 4, "<=": 4, ">": 4, ">=": 4,
    "+": 5, "-": 5,
    "*": 6, "/": 6, "%": 6,
}


class ParseError(Exception):
    def __init__(self, msg, token=None):
        loc = f"第{token.line}行第{token.col}列" if token else "未知位置"
        super().__init__(f"语法错误 {loc}: {msg}")
        self.token = token


class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0) -> Token:
        idx = min(self.pos + offset, len(self.tokens) - 1)
        return self.tokens[idx]

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        if t.type != "EOF":
            self.pos += 1
        return t

    def expect(self, type_: str, value: Optional[str] = None) -> Token:
        t = self.peek()
        if t.type != type_ or (value is not None and t.value != value):
            want = f"{type_}({value})" if value else type_
            raise ParseError(f"期望 {want}，实际得到 {t.type}({t.value})", t)
        return self.advance()

    def expect_op(self, value: str) -> Token:
        return self.expect("OP", value)

    def expect_punct(self, value: str) -> Token:
        return self.expect("PUNCT", value)

    # ------------------------------------------------------------------
    # 程序入口
    # ------------------------------------------------------------------
    def parse_program(self) -> dict:
        stmts = []
        while self.peek().type != "EOF":
            stmts.append(self.parse_stmt())
        return {"type": "Program", "body": stmts}

    # ------------------------------------------------------------------
    # 语句
    # ------------------------------------------------------------------
    def parse_stmt(self) -> dict:
        t = self.peek()
        if t.type == "LET":
            return self.parse_let(False)
        if t.type == "MUT":
            return self.parse_let(True)
        if t.type in ("FN", "PURE_FN", "OP_FN"):
            return self.parse_fn_def(t.type)
        if t.type == "IF":
            return self.parse_if()
        if t.type == "WHILE":
            return self.parse_while()
        if t.type == "FOR_EACH":
            return self.parse_for_each()
        if t.type == "RETURN":
            self.advance()
            expr = self.parse_expr() if self.peek().type != "PUNCT" or self.peek().value != "}" else None
            return {"type": "Return", "value": expr, "line": t.line}
        if t.type == "THROW":
            self.advance()
            expr = self.parse_expr()
            return {"type": "Throw", "value": expr, "line": t.line}
        if t.type == "TRY":
            return self.parse_try()
        if t.type == "IMPORT":
            self.advance()
            path = self.expect("STRING")
            return {"type": "Import", "path": path.value, "line": t.line}
        if t.type == "PRINT":
            self.advance()
            args = []
            # 打印(...) 带括号形式
            if self.peek().type == "PUNCT" and self.peek().value == "(":
                self.advance()
                while not (self.peek().type == "PUNCT" and self.peek().value == ")"):
                    args.append(self.parse_expr())
                    if self.peek().type == "PUNCT" and self.peek().value == ",":
                        self.advance()
                    else:
                        break
                self.expect_punct(")")
            else:
                # 打印 表达式（不带括号，简单形式）
                if self.peek().type != "PUNCT" or self.peek().value != "}":
                    args.append(self.parse_expr())
                    while self.peek().type == "PUNCT" and self.peek().value == ",":
                        self.advance()
                        args.append(self.parse_expr())
            return {"type": "Print", "args": args, "line": t.line}
        if t.type == "ASSERT":
            self.advance()
            cond = self.parse_expr()
            msg = None
            if self.peek().type == "PUNCT" and self.peek().value == ",":
                self.advance()
                msg = self.parse_expr()
            return {"type": "Assert", "cond": cond, "msg": msg, "line": t.line}
        if t.type == "PUNCT" and t.value == "{":
            # 裸块
            return self.parse_block()
        # 表达式语句（含赋值）
        return self.parse_expr_stmt()

    def parse_let(self, mutable: bool) -> dict:
        kw = self.advance()  # 量 / 可变
        name = self.expect("IDENT")
        # 多变量声明：量 a, b = 表达式（解构赋值）
        names = [name.value]
        if self.peek().type == "PUNCT" and self.peek().value == ",":
            while self.peek().type == "PUNCT" and self.peek().value == ",":
                self.advance()
                n2 = self.expect("IDENT")
                names.append(n2.value)
        # 可选类型标注
        type_ann = None
        if self.peek().type == "PUNCT" and self.peek().value == ":":
            self.advance()
            type_tok = self.expect("IDENT")
            type_ann = TYPE_NAMES.get(type_tok.value, type_tok.value)
        self.expect_op("=")
        value = self.parse_expr()
        return {"type": "Mut" if mutable else "Let",
                "name": name.value, "names": names, "type_ann": type_ann,
                "value": value, "line": kw.line}

    def parse_params(self):
        """解析参数列表：名字 / 名字: 类型 / 名字 = 默认值 / 名字: 类型 = 默认值"""
        params = []
        while not (self.peek().type == "PUNCT" and self.peek().value == ")"):
            pname = self.expect("IDENT")
            ptype = None
            if self.peek().type == "PUNCT" and self.peek().value == ":":
                self.advance()
                tt = self.expect("IDENT")
                ptype = TYPE_NAMES.get(tt.value, tt.value)
            default = None
            if self.peek().type == "OP" and self.peek().value == "=":
                self.advance()
                default = self.parse_expr()
            params.append({"name": pname.value, "type": ptype, "default": default})
            if self.peek().type == "PUNCT" and self.peek().value == ",":
                self.advance()
            elif self.peek().type == "PUNCT" and self.peek().value == ")":
                break
            else:
                raise ParseError("参数之间需要逗号", self.peek())
        return params

    def parse_fn_def(self, kind: str) -> dict:
        kw = self.advance()  # 功能 / 纯功能 / 操作
        name_tok = self.expect("IDENT")
        self.expect_punct("(")
        params = self.parse_params()
        self.expect_punct(")")
        # 返回类型（可选）
        ret_type = None
        if self.peek().type == "OP" and self.peek().value == "->":
            self.advance()
            tt = self.expect("IDENT")
            ret_type = TYPE_NAMES.get(tt.value, tt.value)
        body = self.parse_block()
        # kind: FN=普通, PURE_FN=纯功能, OP_FN=操作（副作用）
        if kind == "PURE_FN":
            node_type = "PureFnDef"
        elif kind == "OP_FN":
            node_type = "OpFnDef"
        else:
            node_type = "FnDef"
        return {"type": node_type,
                "name": name_tok.value, "params": params,
                "ret_type": ret_type, "body": body, "line": kw.line}

    def parse_if(self) -> dict:
        kw = self.advance()  # 若
        cond = self.parse_expr()
        then_block = self.parse_block()
        elifs = []
        else_block = None
        while self.peek().type == "ELIF":
            self.advance()
            c = self.parse_expr()
            b = self.parse_block()
            elifs.append({"cond": c, "body": b})
        if self.peek().type == "ELSE":
            self.advance()
            else_block = self.parse_block()
        return {"type": "If", "cond": cond, "then": then_block,
                "elifs": elifs, "else": else_block, "line": kw.line}

    def parse_while(self) -> dict:
        kw = self.advance()  # 循环
        cond = self.parse_expr()
        body = self.parse_block()
        return {"type": "While", "cond": cond, "body": body, "line": kw.line}

    def parse_for_each(self) -> dict:
        kw = self.advance()  # 对
        var = self.expect("IDENT")
        # 键值对遍历：对 键, 值 在 表
        var2 = None
        if self.peek().type == "PUNCT" and self.peek().value == ",":
            self.advance()
            var2 = self.expect("IDENT").value
        self.expect("IN", "在")  # 在
        iterable = self.parse_expr()
        body = self.parse_block()
        return {"type": "ForEach", "var": var.value, "var2": var2,
                "iterable": iterable, "body": body, "line": kw.line}

    def parse_try(self) -> dict:
        kw = self.advance()  # 捕获
        # 语法：捕获(可能失败的表达式) 或 捕获 { 语句块 }
        if self.peek().type == "PUNCT" and self.peek().value == "(":
            self.advance()
            expr = self.parse_expr()
            self.expect_punct(")")
            return {"type": "TryExpr", "expr": expr, "line": kw.line}
        # 块形式：捕获 { ... }（把块包成匿名函数）
        block = self.parse_block()
        return {"type": "TryBlock", "body": block, "line": kw.line}

    def parse_block(self) -> dict:
        open_tok = self.peek()
        self.expect_punct("{")
        stmts = []
        while not (self.peek().type == "PUNCT" and self.peek().value == "}"):
            if self.peek().type == "EOF":
                raise ParseError("块未闭合，缺少 }", self.peek())
            stmts.append(self.parse_stmt())
        close_tok = self.expect_punct("}")
        return {"type": "Block", "body": stmts,
                "end_line": close_tok.line}

    def parse_expr_stmt(self) -> dict:
        expr = self.parse_expr()
        # 赋值：expr = expr（只能对变量/属性/下标赋值）
        if self.peek().type == "OP" and self.peek().value == "=":
            self.advance()
            value = self.parse_expr()
            return {"type": "Assign", "target": expr, "value": value}
        return {"type": "ExprStmt", "expr": expr}

    # ------------------------------------------------------------------
    # 表达式（Pratt 解析，处理优先级）
    # ------------------------------------------------------------------
    def parse_expr(self, min_prec: int = 0) -> dict:
        left = self.parse_unary()
        while True:
            t = self.peek()
            if t.type == "OP" and t.value in BINOP_PRECEDENCE:
                prec = BINOP_PRECEDENCE[t.value]
                if prec < min_prec:
                    break
                self.advance()
                right = self.parse_expr(prec + 1)
                left = {"type": "BinOp", "op": t.value, "left": left, "right": right, "line": t.line}
            elif t.type in ("AND", "OR"):
                # 和 / 或（短路逻辑）
                prec = 1 if t.type == "OR" else 2
                if prec < min_prec:
                    break
                self.advance()
                right = self.parse_expr(prec + 1)
                left = {"type": "LogicOp", "op": "或" if t.type == "OR" else "和",
                        "left": left, "right": right, "line": t.line}
            elif t.type == "OP" and t.value == "|":
                # 管道：左边值传给右边函数
                prec = 0
                if prec < min_prec:
                    break
                self.advance()
                right = self.parse_expr(prec + 1)
                left = {"type": "Pipe", "left": left, "right": right, "line": t.line}
            else:
                break
        return left

    def parse_unary(self) -> dict:
        t = self.peek()
        if t.type == "OP" and t.value == "-":
            self.advance()
            operand = self.parse_unary()
            return {"type": "UnaryOp", "op": "-", "operand": operand, "line": t.line}
        if t.type == "NOT":
            self.advance()
            operand = self.parse_unary()
            return {"type": "UnaryOp", "op": "非", "operand": operand, "line": t.line}
        return self.parse_postfix()

    def parse_postfix(self) -> dict:
        expr = self.parse_primary()
        while True:
            t = self.peek()
            if t.type == "PUNCT" and t.value == "(":
                # 函数调用（支持关键字参数：名字 = 值，FFI 用）
                self.advance()
                args = []
                kwargs = {}
                while not (self.peek().type == "PUNCT" and self.peek().value == ")"):
                    # 关键字参数检测：IDENT = 值
                    if self.peek().type == "IDENT" and self.peek(1).type == "OP" and self.peek(1).value == "=":
                        kw_name = self.advance().value
                        self.advance()  # =
                        kw_val = self.parse_expr()
                        kwargs[kw_name] = kw_val
                    else:
                        args.append(self.parse_expr())
                    if self.peek().type == "PUNCT" and self.peek().value == ",":
                        self.advance()
                self.expect_punct(")")
                expr = {"type": "Call", "callee": expr, "args": args,
                        "kwargs": kwargs, "line": t.line}
            elif t.type == "PUNCT" and t.value == ".":
                # 属性访问
                self.advance()
                name = self.expect("IDENT")
                expr = {"type": "GetAttr", "obj": expr, "name": name.value, "line": t.line}
            elif t.type == "PUNCT" and t.value == "[":
                # 下标访问 或 切片 [开始:结束]
                self.advance()
                # 切片检测：先看是不是 [x:y] 形式
                if self.peek().type == "PUNCT" and self.peek().value == ":":
                    # [0:80] 省略开始
                    self.advance()
                    end = self.parse_expr() if not (self.peek().type == "PUNCT" and self.peek().value == "]") else None
                    self.expect_punct("]")
                    expr = {"type": "Slice", "obj": expr, "start": None, "end": end, "line": t.line}
                else:
                    # 可能是 [开始:结束] 或 [下标]
                    save = self.pos
                    try:
                        first = self.parse_expr()
                    except ParseError:
                        raise
                    if self.peek().type == "PUNCT" and self.peek().value == ":":
                        self.advance()
                        end = self.parse_expr() if not (self.peek().type == "PUNCT" and self.peek().value == "]") else None
                        self.expect_punct("]")
                        expr = {"type": "Slice", "obj": expr, "start": first, "end": end, "line": t.line}
                    else:
                        self.expect_punct("]")
                        expr = {"type": "Index", "obj": expr, "index": first, "line": t.line}
            else:
                break
        return expr

    def parse_primary(self) -> dict:
        t = self.peek()

        # 字面量
        if t.type == "NUMBER":
            self.advance()
            return {"type": "Literal", "value": t.value, "kind": "number", "line": t.line}
        if t.type == "STRING":
            self.advance()
            return {"type": "Literal", "value": t.value, "kind": "string", "line": t.line}
        if t.type == "TEMPLATE":
            self.advance()
            return {"type": "Template", "value": t.value, "line": t.line}
        if t.type == "TRUE":
            self.advance()
            return {"type": "Literal", "value": True, "kind": "bool", "line": t.line}
        if t.type == "FALSE":
            self.advance()
            return {"type": "Literal", "value": False, "kind": "bool", "line": t.line}
        if t.type == "NIL":
            self.advance()
            return {"type": "Literal", "value": None, "kind": "nil", "line": t.line}

        # 匿名函数：功能(x) { ... }
        if t.type in ("FN", "PURE_FN", "OP_FN"):
            kind = t.type
            self.advance()
            self.expect_punct("(")
            params = self.parse_params()
            self.expect_punct(")")
            ret_type = None
            if self.peek().type == "OP" and self.peek().value == "->":
                self.advance()
                tt = self.expect("IDENT")
                ret_type = TYPE_NAMES.get(tt.value, tt.value)
            body = self.parse_block()
            if kind == "PURE_FN":
                lit_type = "PureFnLiteral"
            elif kind == "OP_FN":
                lit_type = "OpFnLiteral"
            else:
                lit_type = "FnLiteral"
            return {"type": lit_type,
                    "params": params, "ret_type": ret_type, "body": body, "line": t.line}

        # 表字面量
        if t.type == "PUNCT" and t.value == "{":
            return self.parse_table()

        # 括号表达式
        if t.type == "PUNCT" and t.value == "(":
            self.advance()
            expr = self.parse_expr()
            self.expect_punct(")")
            return expr

        # 自身（this）—— 指向调用方法的表
        if t.type == "THIS":
            self.advance()
            return {"type": "Self", "line": t.line}

        # 捕获(表达式) —— 错误捕获，返回结果表
        if t.type == "TRY":
            self.advance()
            self.expect_punct("(")
            expr = self.parse_expr()
            self.expect_punct(")")
            return {"type": "TryExpr", "expr": expr, "line": t.line}

        # 导入("路径") —— 模块导入，返回导出表
        if t.type == "IMPORT":
            self.advance()
            self.expect_punct("(")
            path = self.expect("STRING")
            self.expect_punct(")")
            return {"type": "ImportExpr", "path": path.value, "line": t.line}

        # 元编程 @运算符：访问运算符实现（@add / @+ 等）
        if t.type == "META":
            self.advance()
            return {"type": "Meta", "name": t.value, "line": t.line}

        # 变量
        if t.type == "IDENT":
            self.advance()
            return {"type": "Var", "name": t.value, "line": t.line}

        raise ParseError(f"意外的 token: {t.type}({t.value})", t)

    def parse_table(self) -> dict:
        t = self.advance()  # {
        entries = []  # 有序列表: {"kind": "item"/"pair", "key":..., "value":...}
        while not (self.peek().type == "PUNCT" and self.peek().value == "}"):
            # 键值对：键: 值  或  数组元素：表达式
            first = self.parse_expr()
            if self.peek().type == "PUNCT" and self.peek().value == ":":
                self.advance()
                value = self.parse_expr()
                # 键必须是标识符/字符串/数字
                if first["type"] == "Var":
                    entries.append({"kind": "pair", "key": first["name"], "value": value})
                elif first["type"] == "Literal":
                    entries.append({"kind": "pair", "key": str(first["value"]), "value": value})
                else:
                    raise ParseError("表的键必须是标识符或字面量", t)
            else:
                entries.append({"kind": "item", "value": first})
            if self.peek().type == "PUNCT" and self.peek().value == ",":
                self.advance()
            elif self.peek().type == "PUNCT" and self.peek().value == "}":
                break
            else:
                raise ParseError("表元素之间需要逗号", self.peek())
        self.expect_punct("}")
        return {"type": "Table", "entries": entries, "line": t.line}


def parse(source: str) -> dict:
    """源码 -> AST"""
    tokens = tokenize(source)
    parser = Parser(tokens)
    return parser.parse_program()

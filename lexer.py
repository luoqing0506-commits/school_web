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
无错语言 词法分析器 (lexer.py)
==============================
把中文源码拆成 token 流。
中文关键字 + 英文标识符混用支持。

Token 类型：
  KEY       关键字（量/可变/功能/若/循环...）
  IDENT     标识符（变量名/函数名）
  NUMBER    数字（整数/小数，走数字塔）
  STRING    字符串（"..." '...' `模板`）
  OP        运算符（+ - * / % == != < > <= >= =）
  PUNCT     标点（( ) { } [ ] , . : ->）
  EOF       结束
"""

from dataclasses import dataclass
from typing import List, Optional

# 关键字表（全中文，一个任务一个写法）
KEYWORDS = {
    "量": "LET",
    "可变": "MUT",
    "功能": "FN",
    "纯功能": "PURE_FN",
    "操作": "OP_FN",
    "自身": "THIS",
    "若": "IF",
    "否则若": "ELIF",
    "否则": "ELSE",
    "循环": "WHILE",
    "对": "FOR_EACH",
    "在": "IN",
    "返回": "RETURN",
    "抛错": "THROW",
    "捕获": "TRY",
    "导入": "IMPORT",
    "真": "TRUE",
    "假": "FALSE",
    "空": "NIL",
    "和": "AND",
    "或": "OR",
    "非": "NOT",
    "在": "IN",
    "打印": "PRINT",
    "断言": "ASSERT",
}

# 多字符运算符（优先匹配长的）
MULTI_OPS = ["->", "==", "!=", "<=", ">=", ".."]

# 单字符运算符
SINGLE_OPS = set("+-*/%<>=!|")


@dataclass
class Token:
    type: str
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"{self.type}({self.value})@{self.line}:{self.col}"


class LexError(Exception):
    def __init__(self, msg, line, col):
        super().__init__(f"词法错误 第{line}行第{col}列: {msg}")
        self.line = line
        self.col = col


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def error(self, msg):
        raise LexError(msg, self.line, self.col)

    def peek(self, offset=0) -> str:
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ""

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def skip_whitespace_and_comments(self):
        """跳过空白、行注释 // 和块注释 /* */"""
        while self.pos < len(self.source):
            ch = self.peek()
            if ch in " \t\r\n":
                self.advance()
            elif ch == "/" and self.peek(1) == "/":
                # 行注释
                while self.pos < len(self.source) and self.peek() != "\n":
                    self.advance()
            elif ch == "/" and self.peek(1) == "*":
                # 块注释
                self.advance()  # /
                self.advance()  # *
                while self.pos < len(self.source):
                    if self.peek() == "*" and self.peek(1) == "/":
                        self.advance()
                        self.advance()
                        break
                    self.advance()
                else:
                    self.error("块注释未闭合")
            else:
                break

    def read_string(self, quote: str) -> str:
        """读取字符串字面量（支持转义）"""
        self.advance()  # 开引号
        result = []
        while self.pos < len(self.source):
            ch = self.advance()
            if ch == quote:
                return "".join(result)
            if ch == "\\":
                if self.pos >= len(self.source):
                    break
                esc = self.advance()
                escapes = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "'": "'"}
                result.append(escapes.get(esc, "\\" + esc))
            else:
                result.append(ch)
        self.error(f"字符串未闭合（缺少 {quote}）")

    def read_template(self) -> str:
        """读取模板字符串 `...`（原样保留，支持 ${expr} 插值由 parser 处理）"""
        self.advance()  # `
        result = []
        while self.pos < len(self.source):
            ch = self.advance()
            if ch == "`":
                return "".join(result)
            result.append(ch)
        self.error("模板字符串未闭合")

    def read_number(self) -> str:
        """读取数字（整数/小数），返回字面量文本"""
        start = self.pos
        if self.peek() in "+-":
            self.advance()
        while self.peek().isdigit():
            self.advance()
        if self.peek() == "." and self.peek(1).isdigit():
            self.advance()  # .
            while self.peek().isdigit():
                self.advance()
        return self.source[start:self.pos]

    def read_ident(self) -> str:
        """读取标识符（中文/英文/数字/下划线，不能数字开头）"""
        start = self.pos
        while self.pos < len(self.source):
            ch = self.peek()
            if ch.isalnum() or ch in "_":
                self.advance()
            else:
                break
        return self.source[start:self.pos]

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break

            line, col = self.line, self.col
            ch = self.peek()

            # 字符串
            if ch in "\"'":
                val = self.read_string(ch)
                self.tokens.append(Token("STRING", val, line, col))
                continue

            # 模板字符串
            if ch == "`":
                val = self.read_template()
                self.tokens.append(Token("TEMPLATE", val, line, col))
                continue

            # 数字（含正负号——负号单独处理避免歧义，这里只吃数字开头）
            if ch.isdigit():
                val = self.read_number()
                self.tokens.append(Token("NUMBER", val, line, col))
                continue

            # 标识符 / 关键字（中文或字母开头）
            if ch.isalpha() or ch == "_":
                val = self.read_ident()
                tok_type = KEYWORDS.get(val, "IDENT")
                self.tokens.append(Token(tok_type, val, line, col))
                continue

            # 元编程 @：@运算符名 或 @add（访问运算符实现/覆盖）
            if ch == "@":
                self.advance()
                val = self.read_ident()
                self.tokens.append(Token("META", "@" + val, line, col))
                continue

            # 多字符运算符
            matched_multi = None
            for op in MULTI_OPS:
                if self.source.startswith(op, self.pos):
                    matched_multi = op
                    break
            if matched_multi:
                for _ in matched_multi:
                    self.advance()
                self.tokens.append(Token("OP", matched_multi, line, col))
                continue

            # 单字符运算符
            if ch in SINGLE_OPS:
                self.advance()
                self.tokens.append(Token("OP", ch, line, col))
                continue

            # 标点
            if ch in "(){}[],.:":
                self.advance()
                self.tokens.append(Token("PUNCT", ch, line, col))
                continue

            self.error(f"无法识别的字符 '{ch}'")

        self.tokens.append(Token("EOF", "", self.line, self.col))
        return self.tokens


def tokenize(source: str) -> List[Token]:
    return Lexer(source).tokenize()

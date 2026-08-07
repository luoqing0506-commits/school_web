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
无错语言 Playground 入口（浏览器 Pyodide 版）
=============================================
浏览器里没有 threading / socket / 文件系统，所以：
  - 复用 number/lexer/parser/checker（纯逻辑，无依赖）
  - 用精简 builtins（无 threading 依赖）
  - 协程/网络/文件/服务器 在浏览器里不可用（报错提示）

用法（Pyodide 环境）：
  import wc_run
  result = wc_run.run("打印('你好')")
"""
import sys
import io
import os

# 确保能导入上级目录的核心模块（number/lexer/parser/checker/interpreter）
_PARENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

# 浏览器环境修正：不依赖 threading 的 stdlib 精简版
_BROWSER_BUILTINS = {}


def make_browser_builtins():
    """浏览器可用内置函数（无 threading/socket/文件依赖）"""
    from number import (num_str, parse_number, num_add, num_sub, num_mul,
                        num_div, num_mod, num_neg, num_eq, num_lt, num_le,
                        num_gt, num_ge, Num, num_is_zero)
    from interpreter import WucuoError
    import random
    import math

    b = {}

    def _打印(*args):
        parts = []
        for a in args:
            if isinstance(a, Num):
                parts.append(num_str(a))
            elif a is None:
                parts.append("空")
            elif isinstance(a, bool):
                parts.append("真" if a else "假")
            elif isinstance(a, dict):
                parts.append("{" + ", ".join(f"{k}: {v}" for k, v in a.items()) + "}")
            else:
                parts.append(str(a))
        return " ".join(parts)

    def _长度(x):
        if isinstance(x, dict):
            return len(x)
        return len(x)

    def _类型(x):
        if isinstance(x, Num):
            return "数字"
        if isinstance(x, bool):
            return "布尔"
        if isinstance(x, str):
            return "文本"
        if isinstance(x, dict):
            return "表"
        return "空"

    def _转数字(x):
        return parse_number(str(x))

    def _转文本(x):
        if isinstance(x, Num):
            return num_str(x)
        return str(x)

    def _转布尔(x):
        return bool(x)

    def _随机数(a, b):
        return random.uniform(a, b)

    def _随机整数(a, b):
        return random.randint(int(a), int(b))

    def _绝对值(x):
        return abs(x)

    def _平方根(x):
        return math.sqrt(x)

    def _最大值(*args):
        return max(args)

    def _最小值(*args):
        return min(args)

    def _现在():
        import time as t
        return int(t.time())

    b["打印"] = _打印
    b["长度"] = _长度
    b["类型"] = _类型
    b["转数字"] = _转数字
    b["转文本"] = _转文本
    b["转布尔"] = _转布尔
    b["随机数"] = _随机数
    b["随机整数"] = _随机整数
    b["绝对值"] = _绝对值
    b["平方根"] = _平方根
    b["最大值"] = _最大值
    b["最小值"] = _最小值
    b["现在"] = _现在
    return b


def run(source: str, timeout_ms: int = 5000) -> dict:
    """执行 wc 代码，返回 {输出, 错误} 或抛异常"""
    from lexer import tokenize
    from parser import parse
    from checker import TypeChecker
    from interpreter import Interpreter

    ast = parse(source)
    TypeChecker().check(ast)

    builtins = make_browser_builtins()
    interp = Interpreter(builtins)
    interp.builtins = builtins
    for name, fn in builtins.items():
        interp.globals.define(name, fn)

    # 重定向 stdout 捕获 打印 输出
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        interp.interpret(ast)
    finally:
        sys.stdout = old_stdout
    return {"输出": buf.getvalue(), "错误": None}


if __name__ == "__main__":
    # 本地测试
    r = run('打印("你好，世界！")\n量 x = 3\n打印(x * x)')
    print("输出:", repr(r["输出"]))
    assert "你好，世界！" in r["输出"]
    assert "9" in r["输出"]
    print("✅ Playground 核心可用")

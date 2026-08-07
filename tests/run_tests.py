# -*- coding: utf-8 -*-
"""
无错语言 测试套件 (tests/run_tests.py)
=======================================
覆盖：语言特性 + 防错规则。
运行：python tests/run_tests.py
"""

import sys
import os
import io
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lexer import LexError
from parser import parse, ParseError
from checker import check, CheckError
from interpreter import Interpreter, WucuoError
from stdlib import make_builtins

PASS = 0
FAIL = 0
FAILURES = []


def run_program(source, expect_error=False):
    """运行程序，返回 (退出码, 输出)"""
    ast = parse(source)
    check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            interp.interpret(ast)
        return 0, buf.getvalue()
    except WucuoError as e:
        if expect_error:
            return 1, buf.getvalue()
        raise


def expect_compile_error(source, needle=None):
    """期望编译期（语法/类型检查）报错"""
    try:
        ast = parse(source)
        check(ast)
        raise AssertionError("应该报错但没报")
    except (ParseError, CheckError) as e:
        if needle and needle not in str(e):
            raise AssertionError(f"报错内容不符: 期望含 '{needle}'，实际: {e}")
        return str(e)


def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  ✅ {name}")
    except AssertionError as e:
        FAIL += 1
        FAILURES.append((name, str(e)))
        print(f"  ❌ {name}: {e}")
    except Exception as e:
        FAIL += 1
        FAILURES.append((name, f"异常: {type(e).__name__}: {e}"))
        print(f"  ❌ {name}: 异常 {type(e).__name__}: {e}")


print("=" * 60)
print("一、语言特性")
print("=" * 60)

def t_hello():
    code, rc, out = None, 0, None
    src = '打印("你好，世界！")'
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "你好，世界！\n"
test("你好世界", t_hello)

def t_vars():
    src = '''
量 a = 5
量 b = 3
打印(a + b)
打印(a * b)
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "8\n15\n", repr(buf.getvalue())
test("变量与算术", t_vars)

def t_mutable():
    src = '''
可变 x = 1
x = x + 10
打印(x)
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "11\n"
test("可变变量", t_mutable)

def t_precision():
    src = '''
量 r = 0.1 + 0.2
打印(r)
量 ok = (0.1 + 0.2 == 0.3)
打印(ok)
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "0.3\n真\n", repr(buf.getvalue())
test("精确数字 0.1+0.2==0.3", t_precision)

def t_function():
    src = '''
功能 平方(x) -> 数字 {
    返回 x * x
}
打印(平方(9))
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "81\n"
test("函数与递归", t_function)

def t_recursion():
    src = '''
功能 阶乘(n) -> 数字 {
    若 n <= 1 {
        返回 1
    }
    返回 n * 阶乘(n - 1)
}
打印(阶乘(5))
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "120\n"
test("递归阶乘", t_recursion)

def t_if():
    src = '''
功能 评级(s) -> 文本 {
    若 s >= 90 { 返回 "优" }
    否则若 s >= 60 { 返回 "及格" }
    否则 { 返回 "差" }
}
打印(评级(95))
打印(评级(70))
打印(评级(30))
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "优\n及格\n差\n"
test("if/elif/else", t_if)

def t_while():
    src = '''
可变 i = 0
循环 i < 3 {
    i = i + 1
}
打印(i)
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "3\n"
test("while 循环", t_while)

def t_for_each():
    src = '''
对 x 在 {10, 20, 30} {
    打印(x)
}
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "10\n20\n30\n"
test("for-each 遍历", t_for_each)

def t_table():
    src = '''
量 u = { 名: "张三", 年龄: 18 }
打印(u.名)
打印(u["年龄"])
u.城市 = "北京"
打印(u.城市)
量 arr = { 1, 2, 3 }
打印(arr[0] + arr[1] + arr[2])
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "张三\n18\n北京\n6\n"
test("表（对象+数组）", t_table)

def t_anon_fn():
    src = '''
量 双倍 = 功能(x) -> 数字 { 返回 x * 2 }
打印(双倍(5))
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "10\n"
test("匿名函数", t_anon_fn)

def t_try():
    src = '''
量 r = 捕获(转数字("不是数字"))
若 r.成功 {
    打印("成功")
} 否则 {
    打印("失败:", r.错误)
}
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert "失败:" in buf.getvalue()
test("错误捕获", t_try)

def t_throw():
    src = '''
功能 危险(x) {
    若 x < 0 {
        抛错("负数不行")
    }
    返回 x
}
量 r = 捕获(危险(-5))
若 r.成功 { 打印("成功") } 否则 { 打印(r.错误) }
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "负数不行\n"
test("抛错+捕获", t_throw)

def t_template():
    src = '''
量 名 = "小明"
量 岁 = 16
打印(`我是${名}，${岁}岁`)
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "我是小明，16岁\n"
test("模板字符串", t_template)

def t_builtins():
    src = '''
打印(长度("你好世界"))
打印(类型(42))
打印(转数字("3.14"))
打印(含({a: 1}, "a"))
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "4\n数字\n3.14\n真\n", repr(buf.getvalue())
test("内置函数", t_builtins)

print()
print("=" * 60)
print("二、防错规则（AI 写不错）")
print("=" * 60)

def t_immutable():
    e = expect_compile_error('量 a = 5\na = 6\n', "不可变")
    assert "不可变" in e
test("不可变变量禁止赋值", t_immutable)

def t_undeclared():
    e = expect_compile_error('打印(x)\n', "未声明")
    assert "未声明" in e
test("未声明变量报错", t_undeclared)

def t_no_implicit():
    e = expect_compile_error('量 a = 1\n量 b = a + "x"\n', "转数字")
    assert "转数字" in e
test("无隐式转换（数字+文本）", t_no_implicit)

def t_pure_print():
    e = expect_compile_error('纯功能 f(x) {\n    打印(x)\n    返回 x\n}\n', "纯功能")
    assert "纯功能" in e
test("纯函数禁止打印", t_pure_print)

def t_pure_throw():
    e = expect_compile_error('纯功能 f(x) {\n    抛错("x")\n}\n', "纯功能")
    assert "纯功能" in e
test("纯函数禁止抛错", t_pure_throw)

def t_wrong_args():
    e = expect_compile_error('功能 f(a) { 返回 a }\n打印(f())\n', "参数")
    assert "参数" in e
test("参数数量检查", t_wrong_args)

def t_loop_protect():
    src = '''
可变 i = 0
循环 真 {
    i = i + 1
}
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    try:
        with redirect_stdout(io.StringIO()):
            interp.interpret(ast)
        raise AssertionError("应该拦住死循环")
    except WucuoError as e:
        assert "死循环" in str(e.value) or "100 万" in str(e.value)
test("死循环保护", t_loop_protect)

def t_comment():
    src = '''
// 这是注释
/* 块注释
   多行 */
打印("ok")
'''
    ast = parse(src); check(ast)
    interp = Interpreter(make_builtins())
    buf = io.StringIO()
    with redirect_stdout(buf):
        interp.interpret(ast)
    assert buf.getvalue() == "ok\n"
test("注释支持", t_comment)

print()
print("=" * 60)
print(f"结果: {PASS} 通过, {FAIL} 失败")
print("=" * 60)
if FAILURES:
    print("\n失败详情:")
    for name, msg in FAILURES:
        print(f"  ❌ {name}: {msg}")
    sys.exit(1)
else:
    print("全部通过！🎉")
    sys.exit(0)

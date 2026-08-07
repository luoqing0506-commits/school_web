# -*- coding: utf-8 -*-
"""
无错语言 编译模式测试 (tests/run_tests_compiled.py)
===================================================
验证字节码编译执行与解释器行为一致。
运行：python tests/run_tests_compiled.py
"""

import sys
import os
import io
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import parse
from checker import TypeChecker, CheckError
from compiler import compile_ast, run_compiled

PASS = 0
FAIL = 0
FAILURES = []


def run(src):
    """编译模式执行，返回输出"""
    ast = parse(src)
    TypeChecker().check(ast)
    buf = io.StringIO()
    g = {}
    with redirect_stdout(buf):
        run_compiled(ast, g)
    return buf.getvalue()


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
print("编译模式：语言特性")
print("=" * 60)

def t_hello():
    assert run('打印("你好")') == "你好\n"
test("你好世界", t_hello)

def t_vars():
    out = run('量 a = 5\n量 b = 3\n打印(a + b)\n打印(a * b)')
    assert out == "8\n15\n", repr(out)
test("变量与算术", t_vars)

def t_mutable():
    out = run('可变 x = 1\nx = x + 10\n打印(x)')
    assert out == "11\n", repr(out)
test("可变变量", t_mutable)

def t_precision():
    out = run('量 r = 0.1 + 0.2\n打印(r)\n打印(0.1 + 0.2 == 0.3)')
    assert out == "0.3\n真\n", repr(out)
test("精确数字", t_precision)

def t_function():
    out = run('功能 平方(x) -> 数字 {\n    返回 x * x\n}\n打印(平方(9))')
    assert out == "81\n", repr(out)
test("函数", t_function)

def t_recursion():
    out = run('功能 阶乘(n) -> 数字 {\n    若 n <= 1 {\n        返回 1\n    }\n    返回 n * 阶乘(n - 1)\n}\n打印(阶乘(5))')
    assert out == "120\n", repr(out)
test("递归", t_recursion)

def t_if():
    out = run('功能 评级(s) -> 文本 {\n    若 s >= 90 { 返回 "优" }\n    否则若 s >= 60 { 返回 "及格" }\n    否则 { 返回 "差" }\n}\n打印(评级(95))\n打印(评级(70))\n打印(评级(30))')
    assert out == "优\n及格\n差\n", repr(out)
test("if/elif/else", t_if)

def t_while():
    out = run('可变 i = 0\n循环 i < 3 {\n    i = i + 1\n}\n打印(i)')
    assert out == "3\n", repr(out)
test("while 循环", t_while)

def t_for_each():
    out = run('对 x 在 {10, 20, 30} {\n    打印(x)\n}')
    assert out == "10\n20\n30\n", repr(out)
test("for-each 遍历", t_for_each)

def t_kv_foreach():
    out = run('量 u = { 名: "张三", 年龄: 18 }\n对 k, v 在 u {\n    打印(k, "=", v)\n}')
    assert "名 = 张三" in out and "年龄 = 18" in out, repr(out)
test("键值对遍历", t_kv_foreach)

def t_table():
    out = run('量 u = { 名: "张三", 年龄: 18 }\n打印(u.名)\n打印(u["年龄"])\nu.城市 = "北京"\n打印(u.城市)')
    assert out == "张三\n18\n北京\n", repr(out)
test("表", t_table)

def t_slice():
    out = run('量 s = "无错语言真不错"\n打印(s[0:2])\n打印(s[2:4])')
    assert "无错" in out and "语言" in out, repr(out)
test("切片", t_slice)

def t_try():
    out = run('量 r = 捕获(转数字("不是数字"))\n若 r.成功 { 打印("成功") } 否则 { 打印("失败:", r.错误) }')
    assert "失败:" in out, repr(out)
test("捕获", t_try)

def t_throw():
    out = run('功能 危险(x) {\n    若 x < 0 {\n        抛错("负数不行")\n    }\n    返回 x\n}\n量 r = 捕获(危险(-5))\n若 r.成功 { 打印("成功") } 否则 { 打印(r.错误) }')
    assert out == "负数不行\n", repr(out)
test("抛错+捕获", t_throw)

def t_operation():
    # 操作函数 + 捕获兜底
    out = run('操作 查(x) -> 数字 {\n    若 x < 0 {\n        抛错("无效")\n    }\n    返回 x * 2\n}\n量 r = 捕获(查(-1))\n若 r.成功 { 打印(r.值) } 否则 { 打印("兜底:", r.错误) }\n量 r2 = 捕获(查(5))\n若 r2.成功 { 打印(r2.值) }')
    assert "兜底: 无效" in out and "10" in out, repr(out)
test("操作函数+兜底", t_operation)

def t_default_params():
    out = run('功能 打招呼(名字, 语气 = "你好") -> 文本 {\n    返回 语气 + 名字\n}\n打印(打招呼("小明"))\n打印(打招呼("小红", "早"))')
    assert "你好小明" in out and "早小红" in out, repr(out)
test("默认参数", t_default_params)

def t_multi_return():
    out = run('功能 算圆(r) -> 表 {\n    返回 { r * r, 2 * r }\n}\n量 面积, 周长 = 算圆(3)\n打印(面积)\n打印(周长)')
    assert "9" in out and "6" in out, repr(out)
test("多返回值", t_multi_return)

def t_template():
    out = run('量 名 = "小明"\n量 岁 = 16\n打印(`我是${名}，${岁}岁`)')
    assert out == "我是小明，16岁\n", repr(out)
test("模板字符串", t_template)

def t_builtins():
    out = run('打印(长度("你好世界"))\n打印(类型(42))\n打印(转数字("3.14"))\n打印(含({a: 1}, "a"))')
    assert "4\n数字\n3.14\n真\n" == out, repr(out)
test("内置函数", t_builtins)

def t_file_io():
    out = run('写文件("测试输出.txt", "内容123")\n量 内容 = 读文件("测试输出.txt")\n打印(内容)')
    assert "内容123" in out, repr(out)
    os.remove("测试输出.txt")
test("文件读写", t_file_io)

def t_loop_protect():
    src = '可变 i = 0\n循环 真 {\n    i = i + 1\n}'
    ast = parse(src)
    TypeChecker().check(ast)
    g = {}
    try:
        with redirect_stdout(io.StringIO()):
            run_compiled(ast, g)
        raise AssertionError("应该拦住死循环")
    except Exception as e:
        assert "100 万" in str(e) or "死循环" in str(e)
test("死循环保护", t_loop_protect)

print()
print("=" * 60)
print(f"结果: {PASS} 通过, {FAIL} 失败")
print("=" * 60)
if FAILURES:
    for name, msg in FAILURES:
        print(f"  ❌ {name}: {msg}")
    sys.exit(1)
else:
    print("编译模式全部通过！🎉")
    sys.exit(0)

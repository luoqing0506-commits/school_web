# -*- coding: utf-8 -*-
"""测试：AST -> C 源码 -> cl.exe 编译 -> 运行"""
import sys, os, subprocess, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser import parse
from checker import TypeChecker
from compiler_c import compile_c

CL = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.44.35207\bin\HostX64\x64\cl.exe"
VCDIR = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.44.35207"
WINSDK = r"C:\Program Files (x86)\Windows Kits\10"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
CRT = os.path.join(BASE, "crt")

SDK_VER = "10.0.28000.0"

# MSVC 编译环境（手动拼 INCLUDE/LIB 路径）
def get_msvc_env():
    include_paths = [
        os.path.join(VCDIR, "include"),
        os.path.join(WINSDK, "Include", SDK_VER, "ucrt"),
        os.path.join(WINSDK, "Include", SDK_VER, "um"),
        os.path.join(WINSDK, "Include", SDK_VER, "shared"),
    ]
    lib_paths = [
        os.path.join(VCDIR, "lib", "x64"),
        os.path.join(WINSDK, "Lib", SDK_VER, "ucrt", "x64"),
        os.path.join(WINSDK, "Lib", SDK_VER, "um", "x64"),
    ]
    return include_paths, lib_paths

def compile_and_run(src_code, name="test"):
    """编译 wc 程序为 C 并运行，返回 (输出, 用时)"""
    ast = parse(src_code)
    TypeChecker().check(ast)
    c_src = compile_c(ast)
    
    workdir = tempfile.mkdtemp(prefix="wucuo_c_")
    c_file = os.path.join(workdir, f"{name}.c")
    exe_file = os.path.join(workdir, f"{name}.exe")
    with open(c_file, "w", encoding="utf-8") as f:
        f.write(c_src)
    
    t0 = time.time()
    # 用 cl 编译（设置 INCLUDE/LIB 环境变量）
    include_paths, lib_paths = get_msvc_env()
    env = os.environ.copy()
    env["INCLUDE"] = ";".join(include_paths)
    env["LIB"] = ";".join(lib_paths)
    cmd = [CL, "/nologo", "/utf-8", "/EHsc", f"/I{CRT}", c_file, os.path.join(CRT, "wucuo_rt.c"), f"/Fe:{exe_file}"]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, env=env)
    if result.returncode != 0:
        return f"编译失败:\n{result.stdout}\n{result.stderr}", time.time() - t0
    
    t1 = time.time()
    run_result = subprocess.run([exe_file], capture_output=True, text=True, timeout=30)
    t2 = time.time()
    return run_result.stdout, t2 - t0

if __name__ == "__main__":
    # 测试1: 你好世界 + 变量
    src = '''
量 名字 = "张小明"
量 年龄 = 16
打印("我是", 名字, "今年", 年龄, "岁")
量 x = 5
量 y = 3
打印(x + y)
打印(x * y)
'''
    out, t = compile_and_run(src, "t1")
    print("测试1 输出:", repr(out))
    print("测试1 耗时:", round(t*1000, 1), "ms")
    assert "我是 张小明 今年 16 岁" in out
    assert "8" in out and "15" in out
    print("✅ 测试1 通过")

    # 测试2: 函数 + 递归
    src2 = '''
功能 阶乘(n) -> 数字 {
    若 n <= 1 {
        返回 1
    }
    返回 n * 阶乘(n - 1)
}
打印("5! =", 阶乘(5))
'''
    out2, t2 = compile_and_run(src2, "t2")
    print("测试2 输出:", repr(out2))
    assert "120" in out2
    print("✅ 测试2 通过")

    # 测试3: 循环
    src3 = '''
可变 总和 = 0
可变 i = 0
循环 i < 5 {
    总和 = 总和 + i
    i = i + 1
}
打印("总和 =", 总和)
'''
    out3, t3 = compile_and_run(src3, "t3")
    print("测试3 输出:", repr(out3))
    assert "10" in out3
    print("✅ 测试3 通过")

    # 性能对比：循环 50 万次（低于 100 万保护线）
    import time as _time
    perf_src = '''
可变 总和 = 0
可变 i = 0
循环 i < 500000 {
    总和 = 总和 + i
    i = i + 1
}
打印(总和)
'''
    # C 编译执行
    t0 = _time.time()
    out_c, t_c = compile_and_run(perf_src, "perf")
    print(f"\nC 编译: {round(t_c*1000, 1)} ms, 结果: {out_c.strip()}")
    # 字节码执行
    from compiler import run_compiled
    ast = parse(perf_src)
    TypeChecker().check(ast)
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    t0 = _time.time()
    with redirect_stdout(buf):
        run_compiled(ast)
    t_bc = _time.time() - t0
    print(f"字节码: {round(t_bc*1000, 1)} ms, 结果: {buf.getvalue().strip()}")
    # 解释器执行
    from interpreter import Interpreter
    from stdlib import make_builtins
    builtins = make_builtins()
    interp = Interpreter(builtins)
    builtins = make_builtins(interp)
    interp.builtins = builtins
    for nm, fn in builtins.items():
        interp.globals.define(nm, fn)
    buf2 = io.StringIO()
    t0 = _time.time()
    with redirect_stdout(buf2):
        interp.interpret(ast)
    t_int = _time.time() - t0
    print(f"解释器: {round(t_int*1000, 1)} ms, 结果: {buf2.getvalue().strip()}")
    print(f"\nC vs 解释器: {t_int/t_c:.1f}x")
    print(f"C vs 字节码: {t_bc/t_c:.1f}x")

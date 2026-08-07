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
无错语言 C 编译构建器 (build_c.py)
==================================
把 .wc 文件编译成原生 Windows exe（用 MSVC cl.exe）。
用法：python build_c.py 程序.wc [输出名]
"""
import sys
import os
import subprocess
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import parse
from checker import TypeChecker, CheckError
from compiler_c import compile_c

# MSVC 路径（备选编译器）
CL = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.44.35207\bin\HostX64\x64\cl.exe"
VCDIR = r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.44.35207"
WINSDK = r"C:\Program Files (x86)\Windows Kits\10"
SDK_VER = "10.0.28000.0"
BASE = os.path.dirname(os.path.abspath(__file__))
CRT = os.path.join(BASE, "crt")

# 自动检测 gcc（WinLibs / 系统路径）
def find_gcc():
    import glob
    candidates = []
    # WinGet 安装的 WinLibs
    pkg_root = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    candidates += glob.glob(os.path.join(pkg_root, "BrechtSanders.WinLibs*", "mingw64", "bin", "gcc.exe"))
    # 系统 PATH
    for p in os.environ.get("PATH", "").split(os.pathsep):
        g = os.path.join(p, "gcc.exe")
        if os.path.exists(g):
            candidates.append(g)
    return candidates[0] if candidates else None


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


def build(wc_file, out_exe=None):
    """编译 .wc 文件为 exe，返回 (exe路径, 错误信息)"""
    try:
        with open(wc_file, encoding="utf-8") as f:
            source = f.read()
        ast = parse(source)
        TypeChecker().check(ast)
        c_src = compile_c(ast)
    except ValueError as e:
        return None, f"❌ {e}"

    if out_exe is None:
        base = os.path.splitext(os.path.basename(wc_file))[0]
        out_exe = os.path.join(os.path.dirname(os.path.abspath(wc_file)), base + "_c.exe")

    workdir = tempfile.mkdtemp(prefix="wucuo_c_")
    c_file = os.path.join(workdir, "main.c")
    with open(c_file, "w", encoding="utf-8") as f:
        f.write(c_src)

    include_paths, lib_paths = get_msvc_env()
    env = os.environ.copy()
    env["INCLUDE"] = ";".join(include_paths)
    env["LIB"] = ";".join(lib_paths)

    gcc = find_gcc()
    if gcc:
        # gcc 编译：用英文临时目录避免中文路径问题
        out_tmp = os.path.join(workdir, "out.exe")
        cmd = [gcc, "-o", out_tmp, c_file, os.path.join(CRT, "wucuo_rt.c"), "-I", CRT, "-O2"]
    else:
        # MSVC 编译
        cmd = [CL, "/nologo", "/utf-8", "/EHsc", f"/I{CRT}", c_file,
               os.path.join(CRT, "wucuo_rt.c"), f"/Fe:{out_exe}"]
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=60, env=env)
    if result.returncode != 0:
        return None, f"C 编译失败:\n{result.stdout}\n{result.stderr}"
    if gcc:
        # 从临时目录拷回目标位置
        import shutil
        shutil.copy(out_tmp, out_exe)
    return out_exe, None


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: python build_c.py 程序.wc [输出exe名]")
        return 1
    wc_file = args[0]
    out_exe = args[1] if len(args) > 1 else None
    exe_path, err = build(wc_file, out_exe)
    if err:
        print(err)
        return 1
    print(f"✅ 编译成功: {exe_path}")
    print(f"   运行: {exe_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

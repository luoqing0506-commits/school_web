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
无错语言 (WucuoLang) 入口 CLI
=============================
用法：
  python wucuo.py 文件.wc      # 运行程序
  python wucuo.py --check 文件.wc   # 只做类型检查
  python wucuo.py --repl       # 交互式 REPL
  python wucuo.py --version    # 版本信息
"""

import sys
import os
import traceback

from lexer import LexError, tokenize
from parser import parse, ParseError
from checker import check, CheckError
from interpreter import Interpreter, WucuoError
from stdlib import make_builtins

VERSION = "0.1.0"


def run_source(source: str, filename: str = "<内存>", compile_mode: bool = False) -> int:
    """编译 + 检查 + 执行，返回退出码。compile_mode=True 时用字节码编译执行（快 4-7 倍）"""
    try:
        # 1. 词法
        tokenize(source)
        # 2. 语法
        ast = parse(source)
        # 3. 类型检查（防错核心）
        from checker import TypeChecker
        checker = TypeChecker()
        checker.check(ast)
        for w in checker.warnings:
            print(w)

        # 模块缓存：同一个文件只加载执行一次
        module_cache = {}

        def import_loader(path):
            # 相对当前文件目录解析导入
            base = os.path.dirname(os.path.abspath(filename))
            full = path if path.endswith(".wc") else path + ".wc"
            full_path = os.path.join(base, full)
            if not os.path.exists(full_path):
                raise WucuoError(f"导入失败: 找不到文件 {full_path}")
            # 缓存命中直接返回
            abs_path = os.path.abspath(full_path)
            if abs_path in module_cache:
                return module_cache[abs_path]
            with open(full_path, encoding="utf-8") as f:
                mod_src = f.read()
            # 递归执行模块（收集导出表）
            mod_builtins = make_builtins()
            mod_interp = Interpreter(mod_builtins, import_loader=import_loader)
            mod_builtins = make_builtins(mod_interp)
            mod_interp.builtins = mod_builtins
            for name, fn in mod_builtins.items():
                mod_interp.globals.define(name, fn)
            mod_ast = parse(mod_src)
            check(mod_ast)
            mod_interp.interpret(mod_ast, collect_exports=True)
            module_cache[abs_path] = mod_interp.exports
            return mod_interp.exports

        # 4. 执行（注入解释器实例，协程需要）
        if compile_mode:
            # 编译模式：AST -> Python 字节码（快 4-7 倍）
            from compiler import run_compiled, set_import_loader
            set_import_loader(import_loader)
            run_compiled(ast)
        else:
            builtins = make_builtins()
            interp = Interpreter(builtins, import_loader=import_loader)
            builtins = make_builtins(interp)
            interp.builtins = builtins
            for name, fn in builtins.items():
                interp.globals.define(name, fn)
            interp.interpret(ast)
        return 0
    except LexError as e:
        print(f"❌ {e}")
        return 1
    except ParseError as e:
        print(f"❌ {e}")
        return 1
    except CheckError as e:
        print(f"❌ {e}")
        return 1
    except WucuoError as e:
        print(f"❌ 未捕获的错误: {e.value}")
        return 1
    except RecursionError:
        print("❌ 递归太深（栈溢出）")
        return 1
    except Exception as e:
        print(f"❌ 内部错误: {e}")
        traceback.print_exc()
        return 1


def repl():
    """交互式命令行"""
    print(f"无错语言 WucuoLang v{VERSION} —— 输入代码，Ctrl+C 退出")
    print("（提示：量 x = 5 / 打印(x) / 功能 f(a) { 返回 a }）")
    builtins = make_builtins()
    interp = Interpreter(builtins)
    buffer = []
    while True:
        try:
            prompt = "… " if buffer else "无错> "
            line = input(prompt)
            if line.strip() == "退出":
                break
            buffer.append(line)
            src = "\n".join(buffer)
            try:
                ast = parse(src)
                buffer = []  # 语法完整，清缓冲
                check(ast)
                result = interp.interpret(ast)
                if result is not None and line.strip():
                    print(result)
            except ParseError:
                continue  # 语法不完整，继续读
        except (KeyboardInterrupt, EOFError):
            print()
            break


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print("无错语言 WucuoLang")
        print("用法:")
        print("  python wucuo.py 文件.wc        运行程序")
        print("  python wucuo.py --compile 文件.wc  字节码编译运行（快4-7倍）")
        print("  python wucuo.py --check 文件.wc  只做类型检查")
        print("  python wucuo.py --repl          交互式 REPL")
        print("  python wucuo.py --version       版本信息")
        return 0

    if args[0] == "--version":
        print(f"WucuoLang v{VERSION}")
        return 0

    if args[0] == "--repl":
        repl()
        return 0

    if args[0] == "--check":
        filename = args[1]
        with open(filename, encoding="utf-8") as f:
            source = f.read()
        try:
            ast = parse(source)
            check(ast)
            print(f"✅ 类型检查通过: {filename}")
            return 0
        except (ParseError, CheckError) as e:
            print(f"❌ {e}")
            return 1

    # 运行文件（支持 --compile 加速模式）
    filename = args[0]
    compile_mode = False
    if args[0] == "--compile":
        compile_mode = True
        if len(args) < 2:
            print("❌ --compile 需要文件名")
            return 1
        filename = args[1]
    try:
        with open(filename, encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"❌ 找不到文件: {filename}")
        return 1
    if compile_mode:
        print(f"[编译模式] 字节码加速: {filename}")
    return run_source(source, filename, compile_mode)


if __name__ == "__main__":
    sys.exit(main())

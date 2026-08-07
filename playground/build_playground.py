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
Playground 构建器 (build_playground.py)
=======================================
把无错语言核心模块源码内嵌进单文件 HTML，
生成 index.html —— 双击即用（联网加载 Pyodide CDN）。
"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
PLAYGROUND = os.path.dirname(os.path.abspath(__file__))

# 需要内嵌的核心模块（按依赖顺序）
MODULES = ["number", "lexer", "parser", "checker", "interpreter", "wc_run"]

# 关键：浏览器里没有 threading —— 给一个假的（协程功能不可用但导入不崩）
SHIM = """\
# 浏览器环境 shim：Pyodide 无 threading，提供假模块让 import 不崩
import sys, types
if 'threading' not in sys.modules:
    _fake = types.ModuleType('threading')
    _fake.get_ident = lambda: 1
    _fake.Lock = lambda: None
    _fake.Condition = type('Condition', (), {'__init__': lambda self, *a, **k: None,
        'acquire': lambda self, *a, **k: True, 'release': lambda self, *a, **k: None,
        '__enter__': lambda self, *a, **k: self, '__exit__': lambda self, *a, **k: None,
        'wait': lambda self, *a, **k: None, 'notify': lambda self, *a, **k: None})
    _fake.Event = type('Event', (), {'__init__': lambda self, *a, **k: None,
        'set': lambda self, *a, **k: None, 'wait': lambda self, *a, **k: True,
        'is_set': lambda self, *a, **k: True, 'clear': lambda self, *a, **k: None})
    sys.modules['threading'] = _fake
"""


def build():
    # 读取所有模块源码：核心模块在项目根，wc_run 在 playground
    modules_src = {}
    for m in MODULES:
        if m == "wc_run":
            path = os.path.join(PLAYGROUND, m + ".py")
        else:
            path = os.path.join(BASE, m + ".py")
        with open(path, encoding="utf-8") as f:
            modules_src[m] = f.read()

    # 读取 HTML 模板
    template_path = os.path.join(PLAYGROUND, "template.html")
    with open(template_path, encoding="utf-8") as f:
        template = f.read()

    # 生成内嵌数据
    js_modules = []
    for m in MODULES:
        # 转义反引号和 ${} 避免破坏 JS 模板
        src = modules_src[m].replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
        js_modules.append(f'    {{ name: {m!r}, src: `{src}` }}')
    modules_js = ",\n".join(js_modules)

    # shim 转义
    shim_js = SHIM.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    html = template.replace("/*__MODULES__*/", modules_js).replace("/*__SHIM__*/", shim_js)

    out_path = os.path.join(PLAYGROUND, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    size = os.path.getsize(out_path) / 1024
    print(f"✅ Playground 生成: {out_path} ({size:.1f} KB)")

    # 验证：内嵌源码必须能编译（防止转义破坏）
    for m, src in modules_src.items():
        compile(src, f"<{m}>", "exec")
    print("✅ 全部内嵌模块源码编译验证通过")


if __name__ == "__main__":
    build()

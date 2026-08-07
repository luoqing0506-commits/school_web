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
无错语言 内置函数 (builtins.py)
================================
打印 / 长度 / 类型 / 转数字 / 转文本 / 转布尔 / 键 / 含 / 删 / 克隆 / 合并 / 断言 / 读入
"""

from number import (Num, num_str, parse_number, num_eq, num_is_zero, num_to_float,
                    num_add, num_sub, num_mul, num_div, num_mod, num_neg,
                    num_lt, num_le, num_gt, num_ge)
from interpreter import WucuoError
import threading

# 解释器实例引用（协程需要）
_interp_ref = None


def make_builtins(interp=None):
    """构造内置函数表：名字 -> Python 函数"""
    global _interp_ref
    _interp_ref = interp
    b = {}

    def _打印(*args):
        from interpreter import Interpreter
        # 打印由解释器处理（多参数格式化），这里只兜底
        parts = []
        for a in args:
            if isinstance(a, Num):
                parts.append(num_str(a))
            elif a is None:
                parts.append("空")
            elif isinstance(a, bool):
                parts.append("真" if a else "假")
            else:
                parts.append(str(a))
        print(" ".join(parts))
        return None

    def _长度(x):
        if isinstance(x, str):
            return len(x)
        if isinstance(x, dict):
            return len(x)
        raise WucuoError("长度() 只支持文本或表")

    def _类型(x):
        if x is None:
            return "空"
        if isinstance(x, bool):
            return "布尔"
        if isinstance(x, Num):
            return "数字"
        if isinstance(x, str):
            return "文本"
        if isinstance(x, dict):
            return "表"
        return "功能"

    def _转数字(x):
        if isinstance(x, Num):
            return x
        if isinstance(x, str):
            try:
                return parse_number(x.strip())
            except Exception:
                raise WucuoError(f"无法把 '{x}' 转成数字")
        if isinstance(x, bool):
            return 1 if x else 0
        raise WucuoError(f"无法把 {_类型(x)} 转成数字")

    def _转文本(x):
        if isinstance(x, Num):
            return num_str(x)
        if x is None:
            return "空"
        if isinstance(x, bool):
            return "真" if x else "假"
        return str(x)

    def _转布尔(x):
        if isinstance(x, Num):
            return not num_is_zero(x)
        if isinstance(x, str):
            return len(x) > 0
        if isinstance(x, dict):
            return len(x) > 0
        return bool(x)

    def _键(t):
        if not isinstance(t, dict):
            raise WucuoError("键() 只支持表")
        return list(t.keys())

    def _含(t, k):
        if not isinstance(t, dict):
            raise WucuoError("含() 第一个参数必须是表")
        return k in t

    def _删(t, k):
        if not isinstance(t, dict):
            raise WucuoError("删() 第一个参数必须是表")
        if k in t:
            del t[k]
        return t

    def _克隆(t):
        if not isinstance(t, dict):
            raise WucuoError("克隆() 只支持表")
        return dict(t)  # 浅拷贝

    def _合并(dst, *srcs):
        if not isinstance(dst, dict):
            raise WucuoError("合并() 第一个参数必须是表")
        for s in srcs:
            if not isinstance(s, dict):
                raise WucuoError("合并() 参数必须是表")
            dst.update(s)
        return dst

    def _断言(cond, msg=None):
        if not cond:
            raise WucuoError(msg if msg is not None else "断言失败")
        return None

    def _读入():
        try:
            return input()
        except EOFError:
            return ""

    # ============ 文件操作（加强版新增） ============
    def _读文件(path):
        if not isinstance(path, str):
            raise WucuoError("读文件() 参数必须是文本路径")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise WucuoError(f"读文件失败: 找不到 {path}")
        except Exception as e:
            raise WucuoError(f"读文件失败: {e}")

    def _写文件(path, content):
        if not isinstance(path, str):
            raise WucuoError("写文件() 第一个参数必须是文本路径")
        if not isinstance(content, str):
            content = _转文本(content)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            raise WucuoError(f"写文件失败: {e}")

    def _追加文件(path, content):
        if not isinstance(path, str):
            raise WucuoError("追加文件() 第一个参数必须是文本路径")
        if not isinstance(content, str):
            content = _转文本(content)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            raise WucuoError(f"追加文件失败: {e}")

    def _存在(path):
        if not isinstance(path, str):
            raise WucuoError("存在() 参数必须是文本路径")
        import os
        return os.path.exists(path)

    # ============ JSON 操作（加强版新增） ============
    def _JSON编码(value):
        import json
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception as e:
            raise WucuoError(f"JSON编码失败: {e}")

    def _JSON解码(text):
        import json
        if not isinstance(text, str):
            raise WucuoError("JSON解码() 参数必须是文本")
        try:
            return json.loads(text)
        except Exception as e:
            raise WucuoError(f"JSON解码失败: {e}")

    # ============ 字符串操作（加强版新增） ============
    def _分割(text, sep):
        if not isinstance(text, str):
            raise WucuoError("分割() 第一个参数必须是文本")
        if not isinstance(sep, str):
            raise WucuoError("分割() 第二个参数必须是文本分隔符")
        parts = text.split(sep)
        return {i: parts[i] for i in range(len(parts))}

    def _替换(text, old, new):
        if not isinstance(text, str):
            raise WucuoError("替换() 第一个参数必须是文本")
        return text.replace(old, new)

    def _大写(text):
        if not isinstance(text, str):
            raise WucuoError("大写() 参数必须是文本")
        return text.upper()

    def _小写(text):
        if not isinstance(text, str):
            raise WucuoError("小写() 参数必须是文本")
        return text.lower()

    def _去空格(text):
        if not isinstance(text, str):
            raise WucuoError("去空格() 参数必须是文本")
        return text.strip()

    def _包含(text, sub):
        if not isinstance(text, str) or not isinstance(sub, str):
            raise WucuoError("包含() 参数必须是文本")
        return sub in text

    # ============ 列表操作（加强版新增） ============
    def _排序(t):
        if not isinstance(t, dict):
            raise WucuoError("排序() 参数必须是表")
        items = list(t.values())
        try:
            items.sort(key=lambda x: (num_to_float(x) if isinstance(x, Num) else x))
        except Exception:
            try:
                items.sort()
            except Exception as e:
                raise WucuoError(f"排序失败: {e}")
        return {i: items[i] for i in range(len(items))}

    def _反转(t):
        if not isinstance(t, dict):
            raise WucuoError("反转() 参数必须是表")
        items = list(t.values())
        items.reverse()
        return {i: items[i] for i in range(len(items))}

    def _追加(t, value):
        if not isinstance(t, dict):
            raise WucuoError("追加() 第一个参数必须是表")
        t[len(t)] = value
        return t

    def _弹出(t):
        if not isinstance(t, dict):
            raise WucuoError("弹出() 参数必须是表")
        if len(t) == 0:
            raise WucuoError("弹出() 表是空的")
        idx = len(t) - 1
        return t.pop(idx)

    # ============ 网络操作（加强版第二波新增） ============
    def _url_encode(url):
        """URL 里的非 ASCII 字符编码（中文路径/参数）"""
        import urllib.parse
        # 只编码路径和查询部分，保留 :// 和 / 等
        return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%")

    def _HTTP获取(url):
        import urllib.request
        import urllib.error
        if not isinstance(url, str):
            raise WucuoError("HTTP获取() 参数必须是文本 URL")
        url = _url_encode(url)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WucuoLang/0.2"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return {
                    "成功": True,
                    "状态": resp.status,
                    "内容": body,
                    "头": dict(resp.headers),
                }
        except urllib.error.HTTPError as e:
            return {"成功": False, "状态": e.code, "错误": str(e)}
        except Exception as e:
            return {"成功": False, "状态": 0, "错误": str(e)}

    def _HTTP发布(url, data=None, content_type="application/json"):
        import urllib.request
        import urllib.error
        import json
        if not isinstance(url, str):
            raise WucuoError("HTTP发布() 第一个参数必须是文本 URL")
        url = _url_encode(url)
        # 数据转 JSON 文本
        if data is not None and not isinstance(data, str):
            data = json.dumps(data, ensure_ascii=False)
        body_bytes = data.encode("utf-8") if isinstance(data, str) else None
        try:
            req = urllib.request.Request(url, data=body_bytes, method="POST",
                                         headers={"User-Agent": "WucuoLang/0.2",
                                                  "Content-Type": content_type})
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")
                return {
                    "成功": True,
                    "状态": resp.status,
                    "内容": resp_body,
                    "头": dict(resp.headers),
                }
        except urllib.error.HTTPError as e:
            return {"成功": False, "状态": e.code, "错误": str(e)}
        except Exception as e:
            return {"成功": False, "状态": 0, "错误": str(e)}

    def _下载文件(url, path):
        import urllib.request
        import urllib.error
        if not isinstance(url, str) or not isinstance(path, str):
            raise WucuoError("下载文件() 参数必须是文本")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "WucuoLang/0.2"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(path, "wb") as f:
                    f.write(resp.read())
            return True
        except Exception as e:
            raise WucuoError(f"下载文件失败: {e}")

    # ============ 时间/随机/数学（加强版第三波新增） ============
    import time as _time_mod
    import random as _random_mod
    import math as _math_mod

    def _现在():
        """当前时间戳（秒）"""
        return int(_time_mod.time())

    def _时间文本():
        """当前时间文本，如 2026-08-07 19:30:00"""
        return _time_mod.strftime("%Y-%m-%d %H:%M:%S")

    def _睡眠(秒):
        """暂停指定秒数"""
        if not isinstance(秒, Num):
            raise WucuoError("睡眠() 参数必须是数字")
        _time_mod.sleep(num_to_float(秒))
        return None

    def _随机数():
        """随机小数 [0, 1)"""
        return _random_mod.random()

    def _随机整数(最小, 最大):
        """随机整数 [最小, 最大]，含两端"""
        if not isinstance(最小, Num) or not isinstance(最大, Num):
            raise WucuoError("随机整数() 参数必须是数字")
        lo = int(num_to_float(最小))
        hi = int(num_to_float(最大))
        if lo > hi:
            lo, hi = hi, lo
        return _random_mod.randint(lo, hi)

    def _随机选择(表):
        """从表里随机选一个元素"""
        if not isinstance(表, dict) or len(表) == 0:
            raise WucuoError("随机选择() 参数必须是非空表")
        items = list(表.values())
        return _random_mod.choice(items)

    def _绝对值(x):
        if not isinstance(x, Num):
            raise WucuoError("绝对值() 参数必须是数字")
        return abs(x)

    def _向下取整(x):
        if not isinstance(x, Num):
            raise WucuoError("向下取整() 参数必须是数字")
        return _math_mod.floor(num_to_float(x))

    def _向上取整(x):
        if not isinstance(x, Num):
            raise WucuoError("向上取整() 参数必须是数字")
        return _math_mod.ceil(num_to_float(x))

    def _平方根(x):
        if not isinstance(x, Num):
            raise WucuoError("平方根() 参数必须是数字")
        if num_to_float(x) < 0:
            raise WucuoError("平方根() 参数不能为负")
        return _math_mod.sqrt(num_to_float(x))

    def _最大值(*args):
        if not args:
            raise WucuoError("最大值() 至少要一个参数")
        vals = [num_to_float(a) if isinstance(a, Num) else a for a in args]
        return max(vals)

    def _最小值(*args):
        if not args:
            raise WucuoError("最小值() 至少要一个参数")
        vals = [num_to_float(a) if isinstance(a, Num) else a for a in args]
        return min(vals)

    def _取模(a, b):
        if not isinstance(a, Num) or not isinstance(b, Num):
            raise WucuoError("取模() 参数必须是数字")
        return a % b

    # ============ 协程（加强版第四波新增） ============
    def _协程(fn, *args):
        from interpreter import Coroutine, CURRENT_COROUTINE, Function
        if not isinstance(fn, Function):
            raise WucuoError("协程() 第一个参数必须是功能")
        co = Coroutine(fn, list(args), fn.closure, _interp_ref)
        return co

    def _恢复(co, value=None):
        from interpreter import Coroutine
        if not isinstance(co, Coroutine):
            raise WucuoError("恢复() 参数必须是协程")
        with co.cond:
            co.resume_value = value
            if not co.started:
                co.started = True
                co.start()
            else:
                co.resumed = True
                co.cond.notify()
            # 等待协程让出或结束
            while not co.yield_ready and co.state != "dead":
                co.cond.wait()
            if co.yield_ready:
                co.yield_ready = False
                return co.yield_value
        # dead
        if co.error:
            raise co.error
        return co.result

    def _让出(value=None):
        from interpreter import CURRENT_COROUTINE
        co = CURRENT_COROUTINE.get(threading.get_ident())
        if co is None:
            raise WucuoError("让出() 只能在协程里调用")
        with co.cond:
            co.yield_value = value
            co.yield_ready = True
            co.state = "suspended"
            co.cond.notify()
            # 等待被恢复
            while not co.resumed:
                co.cond.wait()
            co.resumed = False
            return co.resume_value

    def _协程状态(co):
        from interpreter import Coroutine
        if not isinstance(co, Coroutine):
            raise WucuoError("协程状态() 参数必须是协程")
        return co.state

    # ============ HTTP 服务器（加强版第五波新增） ============
    def _服务(端口, 路由表):
        """起一个 HTTP 服务器：服务(端口, {路径: 处理函数})
        处理函数收到 {方法, 路径, 查询, 头, 体}，返回文本 或 {状态, 体, 头}"""
        import http.server
        import urllib.parse
        from interpreter import Function, ReturnSignal, Environment

        if not isinstance(端口, Num):
            raise WucuoError("服务() 第一个参数必须是端口数字")
        if not isinstance(路由表, dict):
            raise WucuoError("服务() 第二个参数必须是路由表")

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _handle(self):
                try:
                    # 解析查询参数
                    parsed = urllib.parse.urlparse(self.path)
                    query = dict(urllib.parse.parse_qsl(parsed.query))
                    # 读请求体
                    length = int(self.headers.get("Content-Length", 0) or 0)
                    body = self.rfile.read(length).decode("utf-8", errors="replace") if length else ""
                    req = {
                        "方法": self.command,
                        "路径": parsed.path,
                        "查询": query,
                        "头": dict(self.headers),
                        "体": body,
                    }
                    # 找路由处理函数
                    handler_fn = 路由表.get(parsed.path)
                    if handler_fn is None:
                        handler_fn = 路由表.get("*")  # 兜底路由
                    if handler_fn is None:
                        self.send_error(404, "not found")
                        return
                    # 执行处理函数（解释器 Function 或编译模式 Python 函数）
                    if isinstance(handler_fn, Function):
                        fn_env = Environment(handler_fn.closure)
                        fn_env.define("请求", req)
                        try:
                            result = _interp_ref.exec_block(handler_fn.body, fn_env)
                        except ReturnSignal as r:
                            result = r.value
                    elif callable(handler_fn):
                        # 编译模式：Python 函数，参数是 请求 表
                        result = handler_fn(req)
                    else:
                        self.send_error(404, "not found")
                        return
                    # 处理响应
                    status = 200
                    headers = {"Content-Type": "text/plain; charset=utf-8"}
                    if isinstance(result, dict):
                        if "状态" in result:
                            status = result["状态"]
                        if "体" in result:
                            result = result["体"]
                        elif "正文" in result:
                            result = result["正文"]
                        if "头" in result and isinstance(result["头"], dict):
                            headers.update({str(k): str(v) for k, v in result["头"].items()})
                    if not isinstance(result, str):
                        result = _转文本(result)
                    body_bytes = result.encode("utf-8")
                    self.send_response(status)
                    for k, v in headers.items():
                        self.send_header(k, v)
                    self.send_header("Content-Length", str(len(body_bytes)))
                    self.end_headers()
                    self.wfile.write(body_bytes)
                except Exception as e:
                    try:
                        self.send_error(500, str(e))
                    except Exception:
                        pass

            def do_GET(self):
                self._handle()

            def do_POST(self):
                self._handle()

            def do_PUT(self):
                self._handle()

            def do_DELETE(self):
                self._handle()

        server = http.server.ThreadingHTTPServer(("0.0.0.0", int(num_to_float(端口))), Handler)
        # 后台线程跑服务器，不阻塞程序
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return {"端口": int(num_to_float(端口)), "状态": "运行中"}

    def _停止服务(服务器):
        """停止 HTTP 服务器（需要保存 serve_forever 线程）"""
        # 简化：通过端口重建对象停止——实际用 server_close
        # 这里通过保存的全局表处理
        from interpreter import Function
        if isinstance(服务器, dict) and "端口" in 服务器:
            raise WucuoError("停止服务() 暂不支持，服务器随程序结束自动停止")
        raise WucuoError("停止服务() 参数必须是服务() 的返回值")

    # ============ 日期/正则（加强版第六波新增） ============
    import datetime as _dt_mod
    import re as _re_mod

    def _日期():
        """当前日期文本，如 2026-08-07"""
        return _dt_mod.date.today().isoformat()

    def _年月日(文本):
        """解析日期文本 -> {年, 月, 日}；失败抛错"""
        if not isinstance(文本, str):
            raise WucuoError("年月日() 参数必须是日期文本")
        try:
            d = _dt_mod.date.fromisoformat(文本.strip())
            return {"年": d.year, "月": d.month, "日": d.day}
        except Exception:
            raise WucuoError(f"无法解析日期: {文本}（格式应为 2026-08-07）")

    def _匹配(模式, 文本):
        """正则匹配：返回 {成功, 匹配}；不匹配返回 {成功: 假}"""
        if not isinstance(模式, str) or not isinstance(文本, str):
            raise WucuoError("匹配() 参数必须是文本")
        try:
            m = _re_mod.search(模式, 文本)
            if m:
                groups = {}
                for i, g in enumerate(m.groups()):
                    groups[i] = g if g is not None else ""
                return {"成功": True, "匹配": m.group(0), "分组": groups}
            return {"成功": False, "匹配": "", "分组": {}}
        except Exception as e:
            raise WucuoError(f"正则错误: {e}")

    def _查找全部(模式, 文本):
        """正则查找所有匹配：返回表"""
        if not isinstance(模式, str) or not isinstance(文本, str):
            raise WucuoError("查找全部() 参数必须是文本")
        try:
            matches = _re_mod.findall(模式, 文本)
            return {i: matches[i] for i in range(len(matches))}
        except Exception as e:
            raise WucuoError(f"正则错误: {e}")

    def _替换正则(模式, 替换, 文本):
        """正则替换：把文本里匹配 模式 的部分替换成 替换"""
        if not isinstance(模式, str) or not isinstance(替换, str) or not isinstance(文本, str):
            raise WucuoError("替换正则() 参数必须是文本")
        try:
            return _re_mod.sub(模式, 替换, 文本)
        except Exception as e:
            raise WucuoError(f"正则错误: {e}")

    # ============ 元编程：运算符实现（加强版新增） ============
    def _op_add(a, b):
        return num_add(a, b) if isinstance(a, Num) and isinstance(b, Num) else a + b

    def _op_sub(a, b):
        return num_sub(a, b)

    def _op_mul(a, b):
        return num_mul(a, b)

    def _op_div(a, b):
        return num_div(a, b)

    def _op_mod(a, b):
        return num_mod(a, b)

    def _op_neg(a):
        return num_neg(a)

    def _op_eq(a, b):
        return num_eq(a, b) if isinstance(a, Num) and isinstance(b, Num) else a == b

    def _op_lt(a, b):
        return num_lt(a, b)

    def _op_le(a, b):
        return num_le(a, b)

    def _op_gt(a, b):
        return num_gt(a, b)

    def _op_ge(a, b):
        return num_ge(a, b)

    # ============ FFI：导入 Python 库（架桥，吃掉全生态） ============
    def _导入Python(模块名):
        """导入 Python 模块，返回模块对象，可直接调用其函数/属性。
        例：量 os = 导入Python("os")  →  os.getcwd()"""
        import importlib
        if not isinstance(模块名, str):
            raise WucuoError("导入Python() 参数必须是文本模块名")
        try:
            return importlib.import_module(模块名)
        except ImportError as e:
            raise WucuoError(f"导入Python 失败: 找不到模块 '{模块名}'（{e}）")

    b["打印"] = _打印
    b["长度"] = _长度
    b["类型"] = _类型
    b["转数字"] = _转数字
    b["转文本"] = _转文本
    b["转布尔"] = _转布尔
    b["键"] = _键
    b["含"] = _含
    b["删"] = _删
    b["克隆"] = _克隆
    b["合并"] = _合并
    b["断言"] = _断言
    b["读入"] = _读入
    # 文件
    b["读文件"] = _读文件
    b["写文件"] = _写文件
    b["追加文件"] = _追加文件
    b["存在"] = _存在
    # JSON
    b["JSON编码"] = _JSON编码
    b["JSON解码"] = _JSON解码
    # 字符串
    b["分割"] = _分割
    b["替换"] = _替换
    b["大写"] = _大写
    b["小写"] = _小写
    b["去空格"] = _去空格
    b["包含"] = _包含
    # 列表
    b["排序"] = _排序
    b["反转"] = _反转
    b["追加"] = _追加
    b["弹出"] = _弹出
    # 网络
    b["HTTP获取"] = _HTTP获取
    b["HTTP发布"] = _HTTP发布
    b["下载文件"] = _下载文件
    # 时间
    b["现在"] = _现在
    b["时间文本"] = _时间文本
    b["睡眠"] = _睡眠
    # 随机
    b["随机数"] = _随机数
    b["随机整数"] = _随机整数
    b["随机选择"] = _随机选择
    # 数学
    b["绝对值"] = _绝对值
    b["向下取整"] = _向下取整
    b["向上取整"] = _向上取整
    b["平方根"] = _平方根
    b["最大值"] = _最大值
    b["最小值"] = _最小值
    b["取模"] = _取模
    # 协程
    b["协程"] = _协程
    b["恢复"] = _恢复
    b["让出"] = _让出
    b["协程状态"] = _协程状态
    # HTTP 服务器
    b["服务"] = _服务
    b["停止服务"] = _停止服务
    # 日期/正则
    b["日期"] = _日期
    b["年月日"] = _年月日
    b["匹配"] = _匹配
    b["查找全部"] = _查找全部
    b["替换正则"] = _替换正则
    # 元编程：运算符实现（@add @sub @mul @div @mod @neg @eq @lt @le @gt @ge）
    b["@add"] = _op_add
    b["@sub"] = _op_sub
    b["@mul"] = _op_mul
    b["@div"] = _op_div
    b["@mod"] = _op_mod
    b["@neg"] = _op_neg
    b["@eq"] = _op_eq
    b["@lt"] = _op_lt
    b["@le"] = _op_le
    b["@gt"] = _op_gt
    b["@ge"] = _op_ge
    # FFI
    b["导入Python"] = _导入Python
    return b

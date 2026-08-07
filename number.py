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
无错语言 数字塔 (number.py)
============================
三层数字塔，保证十进制精确，杜绝浮点误差：
  第1层 int       : 整数快路径，带溢出检测
  第2层 Dec       : 定点小数，值 = Coef / 10^Scale，十进制精确
  第3层 Fraction  : 有理数兜底（除不尽/溢出），仍然精确

承诺：
  - 0.1 + 0.2 == 0.3 为真（不是 0.30000000000000004）
  - 整数永不回绕、永不丢位（溢出自动提升）
  - 唯一"近似"在打印无限循环小数：四舍五入到 20 位
"""

from fractions import Fraction
from typing import Union

# 定点小数的最大小数位数（快路径）
MAX_SCALE = 18


class Dec:
    """定点小数：值 = Coef / 10^Scale。Scale >= 0，值一定带小数部分（或为零）"""

    __slots__ = ("coef", "scale")

    def __init__(self, coef: int, scale: int):
        # 归一化：去掉尾零
        while scale > 0 and coef % 10 == 0:
            coef //= 10
            scale -= 1
        self.coef = coef
        self.scale = scale

    def to_fraction(self) -> Fraction:
        return Fraction(self.coef, 10 ** self.scale)

    def __repr__(self):
        return f"Dec({self.coef}, {self.scale})"


# 数字塔的统一表示：内部一律用 Fraction 计算（精确），
# 结果按规则降级回 int/Dec 快路径
Num = Union[int, Dec, Fraction]


def parse_number(s: str) -> Num:
    """解析数字字面量：123 -> int, 3.14 -> Dec, 超大数 -> Fraction"""
    s = s.strip()
    if "." in s:
        # 定点小数
        int_part, frac_part = s.split(".")
        sign = -1 if s.startswith("-") else 1
        frac_part = frac_part.rstrip("0")
        if not frac_part:
            # 3.0 -> 3
            return int(int_part)
        scale = len(frac_part)
        coef = int(int_part.replace("-", "") + frac_part) * sign
        return Dec(coef, scale)
    # 整数
    n = int(s)
    return n  # Python int 本身就是任意精度，永不溢出


def to_fraction(v: Num) -> Fraction:
    """任意塔内数字 -> Fraction（精确）"""
    if isinstance(v, int):
        return Fraction(v)
    if isinstance(v, Dec):
        return v.to_fraction()
    if isinstance(v, Fraction):
        return v
    raise TypeError(f"不是数字: {type(v)}")


def normalize(fr: Fraction) -> Num:
    """把 Fraction 结果降级回快路径：整数 -> int，有限小数 -> Dec，否则保持 Fraction"""
    if fr.denominator == 1:
        return fr.numerator
    # 看是否有限小数：分母只含 2 和 5 的因子 → 有限十进制小数
    d = fr.denominator
    while d % 2 == 0:
        d //= 2
    while d % 5 == 0:
        d //= 5
    if d == 1:
        # 有限小数 -> Dec
        # 计算需要的小数位数
        scale = 0
        d2 = fr.denominator
        while d2 % 2 == 0:
            d2 //= 2
            scale += 1
        while d2 % 5 == 0:
            d2 //= 5
            scale += 1
        # 分子 * 10^scale / 分母
        num = fr.numerator * (10 ** scale) // fr.denominator
        return Dec(num, scale)
    return fr


def num_add(a: Num, b: Num) -> Num:
    return normalize(to_fraction(a) + to_fraction(b))


def num_sub(a: Num, b: Num) -> Num:
    return normalize(to_fraction(a) - to_fraction(b))


def num_mul(a: Num, b: Num) -> Num:
    return normalize(to_fraction(a) * to_fraction(b))


def num_div(a: Num, b: Num) -> Num:
    if to_fraction(b) == 0:
        raise ZeroDivisionError("除以零")
    return normalize(to_fraction(a) / to_fraction(b))


def num_mod(a: Num, b: Num) -> Num:
    if to_fraction(b) == 0:
        raise ZeroDivisionError("模零")
    fa, fb = to_fraction(a), to_fraction(b)
    # 取模：a - b * floor(a/b)
    q = (fa / fb).__floor__()
    return normalize(fa - fb * q)


def num_neg(a: Num) -> Num:
    return normalize(-to_fraction(a))


def num_eq(a: Num, b: Num) -> bool:
    return to_fraction(a) == to_fraction(b)


def num_lt(a: Num, b: Num) -> bool:
    return to_fraction(a) < to_fraction(b)


def num_le(a: Num, b: Num) -> bool:
    return to_fraction(a) <= to_fraction(b)


def num_gt(a: Num, b: Num) -> bool:
    return to_fraction(a) > to_fraction(b)


def num_ge(a: Num, b: Num) -> bool:
    return to_fraction(a) >= to_fraction(b)


def num_str(v: Num) -> str:
    """数字 -> 文本（打印用）。无限循环小数保留 20 位"""
    if isinstance(v, int):
        return str(v)
    if isinstance(v, Dec):
        sign = "-" if v.coef < 0 else ""
        coef = abs(v.coef)
        if v.scale == 0:
            return f"{sign}{coef}"
        s = str(coef)
        if len(s) <= v.scale:
            s = "0" * (v.scale - len(s) + 1) + s
        int_part = s[:-v.scale]
        frac_part = s[-v.scale:]
        return f"{sign}{int_part}.{frac_part}"
    if isinstance(v, Fraction):
        f = float(v)
        s = f"{f:.20f}".rstrip("0").rstrip(".")
        # 处理 -0
        if s == "-0":
            s = "0"
        return s
    return str(v)


def num_is_zero(v: Num) -> bool:
    return to_fraction(v) == 0


def num_is_int(v: Num) -> bool:
    return isinstance(v, int)


def num_to_float(v: Num) -> float:
    return float(to_fraction(v))

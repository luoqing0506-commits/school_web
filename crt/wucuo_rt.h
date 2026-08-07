/*
 * 无错语言 WucuoLang
 * 版权 (C) 2026 薄情寡义
 * 本程序是自由软件：你可以根据自由软件基金会发布的 GNU 通用公共许可证
 * （GPL）第 3 版或（按你的选择）任何更新版本重新分发和/或修改它。
 * 分发本程序的目的是希望它有用，但没有任何保证；甚至没有适销性或
 * 特定用途的隐含保证。详见 GNU 通用公共许可证。
 * 你应该已经收到 GNU 通用公共许可证的副本。如果没有，见
 * <https://www.gnu.org/licenses/>。
 */

/* ============================================================
 * 无错语言 C 运行时库 (wucuo_rt.h)
 * 编译模式用的最小运行时：数字/字符串/表/打印/错误
 * ============================================================ */
#ifndef WUCUO_RT_H
#define WUCUO_RT_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

/* ---------- 数字：用 double（编译模式追求速度） ---------- */
typedef double wc_num;

/* 前向声明 */
struct wc_table;
struct wc_value;

/* ---------- 值：数字/字符串/表/布尔/空 ---------- */
typedef struct wc_value {
    int type;           /* 0=数字 1=字符串 2=表 3=布尔 4=空 */
    wc_num num;
    char *str;
    struct wc_table *table;
    int boolean;
} wc_value;

typedef struct wc_table_entry {
    char *key;          /* 键（数字键转成字符串 "0","1"...） */
    wc_value value;
    struct wc_table_entry *next;
} wc_table_entry;

typedef struct wc_table {
    wc_table_entry *head;
    int size;
} wc_table;

/* ---------- 表操作 ---------- */
wc_table *wc_table_new(void);
void wc_table_set(wc_table *t, const char *key, wc_value v);
wc_value wc_table_get(wc_table *t, const char *key, int *found);
void wc_table_free(wc_table *t);

/* ---------- 值构造 ---------- */
wc_value wc_num_v(wc_num n);
wc_value wc_str_v(const char *s);
wc_value wc_table_v(wc_table *t);
wc_value wc_bool_v(int b);
wc_value wc_nil_v(void);

/* ---------- 值操作 ---------- */
wc_value wc_add(wc_value a, wc_value b);
wc_value wc_sub(wc_value a, wc_value b);
wc_value wc_mul(wc_value a, wc_value b);
wc_value wc_div(wc_value a, wc_value b);
wc_value wc_mod(wc_value a, wc_value b);
wc_value wc_neg(wc_value a);
int wc_eq(wc_value a, wc_value b);
int wc_lt(wc_value a, wc_value b);
int wc_le(wc_value a, wc_value b);
int wc_gt(wc_value a, wc_value b);
int wc_ge(wc_value a, wc_value b);
int wc_truthy(wc_value v);
char *wc_to_string(wc_value v);  /* 需要 free */

/* ---------- 内置函数 ---------- */
void wc_print_args(wc_value *args, int count);
wc_num wc_len(wc_value v);
const char *wc_type_name(wc_value v);

/* ---------- 错误处理 ---------- */
extern int wc_error_flag;
extern char wc_error_msg[256];
void wc_throw(const char *msg);

/* ---------- 精确小数格式化 ---------- */
void wc_num_to_str(wc_num n, char *buf, int bufsize);

#endif /* WUCUO_RT_H */

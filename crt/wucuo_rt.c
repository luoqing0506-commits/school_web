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
 * 无错语言 C 运行时库实现 (wucuo_rt.c)
 * ============================================================ */
#include "wucuo_rt.h"
#include <stdarg.h>

/* ---------- 错误处理 ---------- */
int wc_error_flag = 0;
char wc_error_msg[256] = {0};

void wc_throw(const char *msg) {
    wc_error_flag = 1;
    snprintf(wc_error_msg, sizeof(wc_error_msg), "%s", msg);
}

/* ---------- 表 ---------- */
wc_table *wc_table_new(void) {
    wc_table *t = (wc_table*)calloc(1, sizeof(wc_table));
    return t;
}

void wc_table_set(wc_table *t, const char *key, wc_value v) {
    if (!t) return;
    wc_table_entry *e = t->head;
    while (e) {
        if (strcmp(e->key, key) == 0) {
            /* 覆盖旧值 */
            if (e->value.type == 1) free(e->value.str);
            if (e->value.type == 2) wc_table_free(e->value.table);
            e->value = v;
            return;
        }
        e = e->next;
    }
    /* 新增 */
    wc_table_entry *ne = (wc_table_entry*)calloc(1, sizeof(wc_table_entry));
    ne->key = strdup(key);
    ne->value = v;
    ne->next = t->head;
    t->head = ne;
    t->size++;
}

wc_value wc_table_get(wc_table *t, const char *key, int *found) {
    if (found) *found = 0;
    if (!t) return wc_nil_v();
    wc_table_entry *e = t->head;
    while (e) {
        if (strcmp(e->key, key) == 0) {
            if (found) *found = 1;
            return e->value;
        }
        e = e->next;
    }
    return wc_nil_v();
}

void wc_table_free(wc_table *t) {
    if (!t) return;
    wc_table_entry *e = t->head;
    while (e) {
        wc_table_entry *next = e->next;
        free(e->key);
        if (e->value.type == 1) free(e->value.str);
        if (e->value.type == 2) wc_table_free(e->value.table);
        free(e);
        e = next;
    }
    free(t);
}

/* ---------- 值构造 ---------- */
wc_value wc_num_v(wc_num n) { wc_value v; v.type = 0; v.num = n; v.str = NULL; v.table = NULL; v.boolean = 0; return v; }
wc_value wc_str_v(const char *s) { wc_value v; v.type = 1; v.num = 0; v.str = s ? strdup(s) : NULL; v.table = NULL; v.boolean = 0; return v; }
wc_value wc_table_v(wc_table *t) { wc_value v; v.type = 2; v.num = 0; v.str = NULL; v.table = t; v.boolean = 0; return v; }
wc_value wc_bool_v(int b) { wc_value v; v.type = 3; v.num = 0; v.str = NULL; v.table = NULL; v.boolean = b; return v; }
wc_value wc_nil_v(void) { wc_value v; v.type = 4; v.num = 0; v.str = NULL; v.table = NULL; v.boolean = 0; return v; }

/* ---------- 值操作 ---------- */
wc_value wc_add(wc_value a, wc_value b) {
    if (a.type == 1 && b.type == 1) {
        char buf[1024];
        snprintf(buf, sizeof(buf), "%s%s", a.str ? a.str : "", b.str ? b.str : "");
        return wc_str_v(buf);
    }
    return wc_num_v(a.num + b.num);
}

wc_value wc_sub(wc_value a, wc_value b) { return wc_num_v(a.num - b.num); }
wc_value wc_mul(wc_value a, wc_value b) { return wc_num_v(a.num * b.num); }
wc_value wc_div(wc_value a, wc_value b) {
    if (b.num == 0) { wc_throw("除以零"); return wc_nil_v(); }
    return wc_num_v(a.num / b.num);
}
wc_value wc_mod(wc_value a, wc_value b) {
    if (b.num == 0) { wc_throw("模零"); return wc_nil_v(); }
    return wc_num_v((wc_num)((int64_t)a.num % (int64_t)b.num));
}
wc_value wc_neg(wc_value a) { return wc_num_v(-a.num); }

int wc_eq(wc_value a, wc_value b) {
    if (a.type == 0 && b.type == 0) return a.num == b.num;
    if (a.type == 1 && b.type == 1) return strcmp(a.str ? a.str : "", b.str ? b.str : "") == 0;
    if (a.type == 3 && b.type == 3) return a.boolean == b.boolean;
    if (a.type == 4 && b.type == 4) return 1;
    return 0;
}
int wc_lt(wc_value a, wc_value b) { return a.num < b.num; }
int wc_le(wc_value a, wc_value b) { return a.num <= b.num; }
int wc_gt(wc_value a, wc_value b) { return a.num > b.num; }
int wc_ge(wc_value a, wc_value b) { return a.num >= b.num; }

int wc_truthy(wc_value v) {
    switch (v.type) {
        case 0: return v.num != 0;
        case 1: return v.str && strlen(v.str) > 0;
        case 2: return v.table && v.table->size > 0;
        case 3: return v.boolean;
        default: return 0;
    }
}

/* ---------- 数字格式化（保留小数，去掉尾零） ---------- */
void wc_num_to_str(wc_num n, char *buf, int bufsize) {
    /* 整数显示为整数，小数去尾零 */
    if (n == (long long)n && n < 1e15 && n > -1e15) {
        snprintf(buf, bufsize, "%lld", (long long)n);
    } else {
        snprintf(buf, bufsize, "%.10g", n);
    }
}

char *wc_to_string(wc_value v) {
    char *buf = (char*)malloc(1024);
    switch (v.type) {
        case 0: wc_num_to_str(v.num, buf, 1024); break;
        case 1: snprintf(buf, 1024, "%s", v.str ? v.str : ""); break;
        case 2: snprintf(buf, 1024, "{表}"); break;
        case 3: snprintf(buf, 1024, "%s", v.boolean ? "真" : "假"); break;
        case 4: snprintf(buf, 1024, "空"); break;
        default: snprintf(buf, 1024, "?"); break;
    }
    return buf;
}

/* ---------- 打印 ---------- */
void wc_print_args(wc_value *args, int count) {
    for (int i = 0; i < count; i++) {
        char *s = wc_to_string(args[i]);
        printf("%s%s", s, (i < count - 1) ? " " : "");
        free(s);
    }
    printf("\n");
}

wc_num wc_len(wc_value v) {
    if (v.type == 1) return (wc_num)strlen(v.str ? v.str : "");
    if (v.type == 2) return (wc_num)(v.table ? v.table->size : 0);
    return 0;
}

const char *wc_type_name(wc_value v) {
    switch (v.type) {
        case 0: return "数字";
        case 1: return "文本";
        case 2: return "表";
        case 3: return "布尔";
        case 4: return "空";
        default: return "未知";
    }
}

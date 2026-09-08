#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤 3 · 生成转化端基准表：按 合作方式×广告类型×素材类型 分组，统计均值与 P25/P50/P75。

说明：飞桨原始数据没有曝光/点击/花费字段，所以本表产出的是【转化端 + 流量质量】基准；
曝光端（CTR/CPM/CPC）由 synthesize_curve.py 合成产出，两边在知识库里配合使用。

用法：在 scripts/ 目录下执行  python3 build_benchmark.py
产出：outputs/02-基准表-转化端.csv、outputs/02-基准表-转化端-draft.md
"""

import csv
import math
import os
import sys

# ============ 配置 ============
INPUT_CSV = "data/raw/ad_performance.csv"   # 兜底合成时改为 data/raw/ad_performance_synthetic.csv
MIN_GROUP_N = 8                              # 样本量门槛，低于则进"样本不足"节
# ==============================

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ALIASES = {
    "合作方式":   ["合作方式", "投放方式", "合作模式", "cooperation"],
    "广告类型":   ["广告类型", "广告形式", "ad_type"],
    "素材类型":   ["素材类型", "创意类型", "素材形式", "creative_type"],
    "日均UV":     ["日均uv", "日均uv量", "uv", "daily_uv"],
    "平均注册率": ["平均注册率", "注册率", "register_rate"],
    "平均搜索量": ["平均搜索量", "搜索量", "search_volume"],
    "访问深度":   ["访问深度", "访问页数", "visit_depth"],
    "平均停留时长": ["平均停留时长", "停留时长", "平均停留时间", "duration"],
    "订单转化率": ["订单转化率", "转化率", "下单转化率", "cvr", "conversion_rate"],
}
# 指标 → (中文名, 是否率刻度列)
METRICS = [
    ("订单转化率", True),
    ("平均注册率", True),
    ("平均搜索量", False),
    ("访问深度", False),
    ("平均停留时长", False),
    ("日均UV", False),
]


def read_csv(path):
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            if len(rows) >= 2:
                return rows[1:], [h.strip() for h in rows[0]], enc
            raise SystemExit(f"[错误] {path} 是空的")
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise SystemExit(f"[错误] {path} 解码失败")


def parse_float(text):
    s = str(text).strip().replace(",", "").replace("%", "").replace("元", "")
    if s in ("", "-", "--", "nan", "None", "NA"):
        return None
    try:
        v = float(s)
        return v if math.isfinite(v) else None
    except ValueError:
        return None


def locate(header_norm, aliases):
    for a in aliases:
        if a in header_norm:
            return header_norm.index(a)
    for a in aliases:
        for i, h in enumerate(header_norm):
            if a in h:
                return i
    return None


def percentile(sorted_vals, p):
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return sorted_vals[0]
    k = (n - 1) * p
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def fix_rate_scale(vals_by_col, groups):
    """率刻度自适应：中位数 > 0.5 判定为百分数刻度，统一 ÷100。
    同时改写全量列表与每组的记录值。返回修正说明。"""
    notes = []
    for name, is_rate in METRICS:
        if not is_rate:
            continue
        vals = vals_by_col.get(name, [])
        pos = [v for v in vals if v > 0]
        if not pos:
            continue
        med = sorted(pos)[len(pos) // 2]
        if med > 0.5:
            vals_by_col[name] = [v / 100.0 for v in vals]
            for recs in groups.values():
                for rec in recs:
                    if name in rec:
                        rec[name] = rec[name] / 100.0
            notes.append(f"{name}：检测为百分数刻度，已统一 ÷100")
        else:
            notes.append(f"{name}：小数刻度，未换算")
    return notes


def main():
    if not os.path.exists(INPUT_CSV):
        raise SystemExit(f"[错误] 找不到 {INPUT_CSV}（先跑 explore_data.py 或走兜底）")
    rows, header, enc = read_csv(INPUT_CSV)
    header_norm = [h.lower() for h in header]

    idx = {name: locate(header_norm, al) for name, al in ALIASES.items()}
    group_cols = [g for g in ("合作方式", "广告类型", "素材类型") if idx[g] is not None]
    if not group_cols:
        raise SystemExit("[错误] 连分组列（合作方式/广告类型/素材类型）都没识别到，请检查表头")

    vals_by_col = {name: [] for name, _ in METRICS}
    groups = {}
    for r in rows:
        gkey = " × ".join(r[idx[g]].strip() for g in group_cols)
        rec = {}
        for name, _ in METRICS:
            i = idx[name]
            if i is None:
                continue
            v = parse_float(r[i]) if i < len(r) else None
            if v is not None:
                rec[name] = v
                vals_by_col[name].append(v)
        groups.setdefault(gkey, []).append(rec)

    scale_notes = fix_rate_scale(vals_by_col, groups)
    # 全量数据的指标列表（总基准行用）
    all_vals = {name: sorted(vals_by_col[name]) for name, _ in METRICS if vals_by_col[name]}

    def agg(recs):
        out = []
        for name, _ in METRICS:
            v = sorted(rec[name] for rec in recs if name in rec)
            if not v:
                continue
            out.append((name, len(v), sum(v) / len(v),
                        percentile(v, 0.25), percentile(v, 0.5), percentile(v, 0.75)))
        return out

    big = {g: recs for g, recs in groups.items() if len(recs) >= MIN_GROUP_N}
    small = {g: recs for g, recs in groups.items() if len(recs) < MIN_GROUP_N}

    # ---- CSV（长表）----
    csv_rows = [["分组", "样本数", "指标", "均值", "P25", "P50", "P75"]]
    for name, _ in METRICS:
        v = all_vals.get(name)
        if v:
            csv_rows.append(["全部数据（总基准）", str(len(v)), name,
                             f"{sum(v)/len(v):.4g}", f"{percentile(v,0.25):.4g}",
                             f"{percentile(v,0.5):.4g}", f"{percentile(v,0.75):.4g}"])
    for g in sorted(big):
        for name, n_, mean, p25, p50, p75 in agg(big[g]):
            csv_rows.append([g, str(n_), name, f"{mean:.4g}", f"{p25:.4g}", f"{p50:.4g}", f"{p75:.4g}"])

    os.makedirs("outputs", exist_ok=True)
    csv_path = os.path.join("outputs", "02-基准表-转化端.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(csv_rows)

    # ---- draft md ----
    md = []
    ap = md.append
    ap(f"# 转化端基准表（draft · {'飞桨真实数据' if 'synthetic' not in INPUT_CSV else '合成兜底数据'}）")
    ap("")
    ap("## 口径说明（人工补全五要素后定稿）")
    ap("1. 指标定义：订单转化率 = 下单 UV ÷ 访问 UV；TODO 补齐其余指标定义")
    ap(f"2. 数据来源：TODO（真实：飞桨公共数据集 55268，下载日期____；合成：脚本生成，需声明）")
    ap(f"3. 分组维度：{' × '.join(group_cols)}；样本量门槛 n≥{MIN_GROUP_N}，不足者单列")
    ap("4. 分位数怎么读：P25–P75 = 建议区间；P50 = 典型水平")
    ap("5. 使用限制：TODO（样本不足组仅供方向参考；对用户一律'建议区间，非精确预测'）")
    ap("")
    for name, _ in METRICS:
        if name not in all_vals:
            continue
        ap(f"## {name} 参考区间")
        ap("")
        ap(f"| 分组 | 样本数 | P25 | P50（典型） | P75 | 均值 |")
        ap(f"|---|---|---|---|---|---|")
        v = all_vals[name]
        ap(f"| **全部数据（总基准）** | {len(v)} | {percentile(v,0.25):.4g} | {percentile(v,0.5):.4g} | {percentile(v,0.75):.4g} | {sum(v)/len(v):.4g} |")
        for g in sorted(big):
            rec = [x for x in agg(big[g]) if x[0] == name]
            if rec:
                _, n_, mean, p25, p50, p75 = rec[0]
                ap(f"| {g} | {n_} | {p25:.4g} | {p50:.4g} | {p75:.4g} | {mean:.4g} |")
        ap("")
    if small:
        ap(f"## 样本不足组（n<{MIN_GROUP_N}，仅供方向参考，不入主表）")
        ap("")
        ap(f"| 分组 | 样本数 | 订单转化率 P50 |")
        ap(f"|---|---|---|")
        for g in sorted(small):
            cvrs = sorted(rec["订单转化率"] for rec in small[g] if "订单转化率" in rec)
            p50 = f"{percentile(cvrs,0.5):.4g}" if cvrs else "-"
            ap(f"| {g} | {len(small[g])} | {p50} |")
        ap("")
    md_path = os.path.join("outputs", "02-基准表-转化端-draft.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")

    print(f"[完成] 分组 {len(groups)} 个：主表 {len(big)} 组，样本不足 {len(small)} 组")
    for note in scale_notes:
        print(f"  - {note}")
    print(f"  → {csv_path}")
    print(f"  → {md_path}")
    print("  下一步：运行 synthesize_curve.py 生成曝光端合成基准与出价曲线")


if __name__ == "__main__":
    main()

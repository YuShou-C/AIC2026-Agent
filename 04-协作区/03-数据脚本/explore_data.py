#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""步骤 2 · 数据探查：字段分布 / 缺失值 / 分组规模 / 率刻度检测，输出探查报告。

用法：在 scripts/ 目录下执行  python3 explore_data.py
产出：outputs/01-探查报告.md（人工看一遍，在报告末尾补"人工判断"）
"""

import csv
import math
import os
import sys

# ============ 配置（列名对不上时改这里） ============
INPUT_CSV = "data/raw/ad_performance.csv"

# 各业务列的候选名（先精确匹配，再包含匹配）
ALIASES = {
    "合作方式":   ["合作方式", "投放方式", "合作模式", "cooperation"],
    "广告类型":   ["广告类型", "广告形式", "ad_type", "广告位类型"],
    "素材类型":   ["素材类型", "创意类型", "素材形式", "creative_type"],
    "广告尺寸":   ["广告尺寸", "尺寸", "size"],
    "广告卖点":   ["广告卖点", "卖点", "selling_point"],
    "渠道代号":   ["渠道代号", "渠道", "channel", "channel_id"],
    "日均UV":     ["日均uv", "日均uv量", "uv", "daily_uv"],
    "平均注册率": ["平均注册率", "注册率", "register_rate"],
    "平均搜索量": ["平均搜索量", "搜索量", "search_volume"],
    "访问深度":   ["访问深度", "访问页数", "visit_depth"],
    "平均停留时长": ["平均停留时长", "停留时长", "平均停留时间", "duration"],
    "订单转化率": ["订单转化率", "转化率", "下单转化率", "cvr", "conversion_rate"],
    "投放总时间": ["投放总时间", "投放时间", "投放天数", "days"],
}
RATE_COLS = ["平均注册率", "订单转化率"]   # 需要做"百分数/小数刻度"检测的列
GROUP_COLS = ["合作方式", "广告类型", "素材类型"]  # 计划中的分组维度
# ====================================================

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def read_csv(path):
    for enc in ("utf-8-sig", "gbk"):
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                rows = list(csv.reader(f))
            if len(rows) >= 2:
                return rows[1:], [h.strip() for h in rows[0]], enc
            raise SystemExit(f"[错误] {path} 好像是空的或只有表头")
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise SystemExit(f"[错误] {path} 用 utf-8 / gbk 都解码失败，确认一下文件编码")


def parse_float(text):
    if text is None:
        return None
    s = str(text).strip().replace(",", "").replace("，", "").replace("%", "").replace("元", "")
    if s in ("", "-", "--", "nan", "None", "NA", "N/A", "null"):
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


def main():
    if not os.path.exists(INPUT_CSV):
        raise SystemExit(
            f"[错误] 找不到 {INPUT_CSV}\n"
            "  请先下载飞桨数据集（aistudio.baidu.com/datasetdetail/55268），\n"
            "  把 ad_performance.csv 放到 scripts/data/raw/ 文件夹；\n"
            "  若下载失败走兜底：先运行 make_synthetic_base.py，再把本文件顶部 INPUT_CSV 改为 data/raw/ad_performance_synthetic.csv"
        )
    rows, header, enc = read_csv(INPUT_CSV)
    header_norm = [h.lower() for h in header]
    n = len(rows)

    col_idx = {}
    missing = []
    for name, aliases in ALIASES.items():
        i = locate(header_norm, aliases)
        if i is None:
            missing.append(name)
        col_idx[name] = i

    # 逐列统计
    stats = {name: {"vals": [], "miss": 0, "uniq": set()} for name in ALIASES}
    for r in rows:
        for name, i in col_idx.items():
            if i is None:
                continue
            raw = r[i].strip() if i < len(r) else ""
            if raw == "":
                stats[name]["miss"] += 1
                continue
            stats[name]["uniq"].add(raw)
            v = parse_float(raw)
            if v is not None and "代号" not in name and name != "渠道代号":
                stats[name]["vals"].append(v)

    # 率刻度检测
    scale_notes = []
    for name in RATE_COLS:
        vals = sorted(stats[name]["vals"])
        if vals and percentile(vals, 0.5) > 0.5:
            scale_notes.append((name, "百分数刻度（如 5 表示 5%），下游脚本会自动 ÷100"))
        elif vals:
            scale_notes.append((name, "小数刻度（如 0.05 表示 5%）"))

    lines = []
    ap = lines.append
    ap(f"# 探查报告 · ad_performance.csv（自动生成）")
    ap(f"")
    ap(f"## 一、基本信息")
    ap(f"- 行数：{n}；列数：{len(header)}；编码：{enc}")
    ap(f"- 原始表头：`{', '.join(header)}`")
    ap(f"- 未识别到的业务列：{('、'.join(missing)) if missing else '无（13 个候选列全部识别）'}")
    if missing:
        ap(f"  - 若属列名差异：改 explore_data.py 顶部 ALIASES 里的候选名即可，不影响后续步骤")
    ap(f"")
    ap(f"## 二、逐列概览")
    ap(f"")
    ap(f"| 列 | 类型 | 缺失 | 唯一值 | P25 | P50 | P75 | 均值 |")
    ap(f"|---|---|---|---|---|---|---|---|")
    for name, i in col_idx.items():
        if i is None:
            ap(f"| {name} | 未识别 | - | - | - | - | - | - |")
            continue
        st = stats[name]
        is_id = ("代号" in name) or name == "渠道代号"
        v = sorted(st["vals"])
        if not v or is_id and len(st["uniq"]) > 50:
            ap(f"| {name} | 类别/ID | {st['miss']} | {len(st['uniq'])} | - | - | - | - |")
        else:
            ap(f"| {name} | 数值 | {st['miss']} | {len(st['uniq'])} | "
               f"{percentile(v,0.25):.4g} | {percentile(v,0.5):.4g} | {percentile(v,0.75):.4g} | "
               f"{sum(v)/len(v):.4g} |")
    ap(f"")
    ap(f"## 三、率刻度判定")
    if scale_notes:
        for name, note in scale_notes:
            ap(f"- **{name}**：{note}")
    else:
        ap(f"- 未检测到率列数值")
    ap(f"")
    ap(f"## 四、分组维度分布")
    for g in GROUP_COLS + ["广告尺寸", "广告卖点"]:
        i = col_idx.get(g)
        if i is None:
            ap(f"### {g}：未识别到此列")
            continue
        cnt = {}
        for r in rows:
            key = r[i].strip() if i < len(r) and r[i].strip() else "(空)"
            cnt[key] = cnt.get(key, 0) + 1
        ap(f"### {g}（{len(cnt)} 类）")
        for k, c in sorted(cnt.items(), key=lambda x: -x[1])[:10]:
            ap(f"- {k}：{c} 行（{c/n:.0%}）")
        ap(f"")

    # 交叉分组规模
    ap(f"## 五、交叉分组规模（合作方式 × 广告类型 × 素材类型）")
    idxs = [col_idx.get(g) for g in GROUP_COLS]
    if all(i is not None for i in idxs):
        cells = {}
        for r in rows:
            key = " × ".join(r[i].strip() for i in idxs)
            cells[key] = cells.get(key, 0) + 1
        big = {k: v for k, v in cells.items() if v >= 8}
        ap(f"- 共 {len(cells)} 个组合；样本量 ≥8 的有 **{len(big)}** 个（基准表只收录这些）")
        ap(f"")
        ap(f"| 组合 | 行数 |")
        ap(f"|---|---|")
        for k, c in sorted(cells.items(), key=lambda x: -x[1])[:30]:
            flag = "" if c >= 8 else "（样本不足）"
            ap(f"| {k} | {c}{flag} |")
        if len(cells) > 30:
            ap(f"| ……（其余 {len(cells)-30} 个略） | |")
    else:
        ap(f"- 分组列有缺失，跳过交叉统计")
    ap(f"")
    ap(f"## 六、人工判断（徐毅填写，2–3 句）")
    ap(f"- 数据整体质量：")
    ap(f"- 率刻度判定是否同意（第三节）：")
    ap(f"- 分组规模是否够用（第五节）：")
    ap(f"- 数据来源声明：☐ 飞桨原始下载（日期____）  ☐ 合成兜底数据")

    os.makedirs("outputs", exist_ok=True)
    out = os.path.join("outputs", "01-探查报告.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[完成] {n} 行数据探查完毕 → {out}")
    print(f"  - 未识别列：{missing if missing else '无'}")
    for name, note in scale_notes:
        print(f"  - {name}：{note}")
    print("  下一步：打开报告补'人工判断'，然后运行 build_benchmark.py")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兜底 · 生成与飞桨数据集同构的合成 CSV（889 行 × 13 字段，种子 42 可复现）。

什么时候用：飞桨 ad_performance.csv 下载失败时。
之后怎么做：把 build_benchmark.py / explore_data.py 顶部 INPUT_CSV 改为
  data/raw/ad_performance_synthetic.csv，后续流水线完全不变；
  探查报告"人工判断"里声明数据来源=合成。

用法：在 scripts/ 目录下执行  python3 make_synthetic_base.py
产出：data/raw/ad_performance_synthetic.csv
"""

import csv
import math
import os
import random
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SEED = 42
N_ROWS = 889
HEADER = ["渠道代号", "日均UV", "平均注册率", "平均搜索量", "访问深度", "平均停留时长",
          "订单转化率", "投放总时间", "素材类型", "广告类型", "合作方式", "广告尺寸", "广告卖点"]
MATERIALS = [("视频", 0.45), ("图文", 0.40), ("横幅", 0.15)]
AD_TYPES = [("信息流广告", 0.55), ("搜索广告", 0.30), ("开屏广告", 0.15)]
COOPS = [("roi", 0.25), ("cpc", 0.40), ("cpm", 0.25), ("cpd", 0.10)]
SIZES = [("640×200", 0.3), ("1080×720", 0.25), ("300×250", 0.2), ("1280×720", 0.15), ("960×640", 0.1)]
POINTS = ["品牌曝光", "限时优惠", "新品上市", "功能卖点", "价格优势", "口碑背书"]
ADT_CVR = {"信息流广告": 0.9, "搜索广告": 1.3, "开屏广告": 0.8}


def weighted(rng, pairs):
    x = rng.random()
    acc = 0.0
    for k, w in pairs:
        acc += w
        if x <= acc:
            return k
    return pairs[-1][0]


def clip(v, lo, hi):
    return max(lo, min(hi, v))


def main():
    rng = random.Random(SEED)
    os.makedirs("data/raw", exist_ok=True)
    rows = []
    for _ in range(N_ROWS):
        uv = int(clip(math.exp(rng.gauss(8.2, 0.9)), 500, 80000))
        reg = clip(rng.gauss(0.03, 0.012), 0.002, 0.09)
        depth = round(clip(rng.gauss(3.2, 1.2), 1, 10), 1)
        stay = int(clip(rng.gauss(180, 70), 15, 600))
        search = int(uv * clip(rng.gauss(0.02, 0.01), 0, 0.06))
        adt = weighted(rng, AD_TYPES)
        cvr = clip(0.006 + 0.0035 * depth + 0.00025 * stay / 10
                   + rng.gauss(0, 0.01), 0.001, 0.12) * ADT_CVR[adt]
        rows.append([
            str(rng.randint(100, 999)),
            str(uv),
            f"{reg:.4f}",
            str(search),
            f"{depth:.1f}",
            str(stay),
            f"{clip(cvr, 0.001, 0.12):.4f}",
            str(int(clip(rng.gauss(45, 15), 15, 90))),
            weighted(rng, MATERIALS),
            adt,
            weighted(rng, COOPS),
            weighted(rng, SIZES),
            rng.choice(POINTS),
        ])
    out = os.path.join("data", "raw", "ad_performance_synthetic.csv")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    print(f"[完成] 合成基础数据 {N_ROWS} 行 × 13 字段（种子 {SEED}，可复现）→ {out}")
    print("  下一步：把 explore_data.py / build_benchmark.py 顶部 INPUT_CSV 改为")
    print(f"        data/raw/ad_performance_synthetic.csv，然后照常跑流水线；")
    print("        所有产出与答辩口径须声明'合成数据'。")


if __name__ == "__main__":
    main()

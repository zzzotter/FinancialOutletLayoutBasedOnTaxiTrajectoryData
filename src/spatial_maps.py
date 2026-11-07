# -*- coding: utf-8 -*-
"""
绘制 4 张空间图（独立文件，300 dpi）:
  map_vitality.png  综合活力指数空间分布
  map_supply.png    金融供给可达性空间分布
  map_lisa.png      活力-供给双变量 LISA 显著分区
  map_potential.png 潜力区空间分布
数据: grid_mismatch_full.csv / potential_areas.csv
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False

df = pd.read_csv("grid_mismatch_full.csv")
pot = pd.read_csv("potential_areas.csv")

def grid(col):
    return df.pivot(index="row", columns="col", values=col).values

V = grid("V"); S = grid("S")
quad = grid("LISA_象限"); pval = grid("LISA_p")
edge = grid("边缘格")
N = 32
extent = [-0.5, N - 0.5, N - 0.5, -0.5]   # row0 在上方(最北)

def base_axes(ax, title):
    ax.set_title(title, fontsize=14, fontweight="bold", pad=10)
    ax.set_xlabel("网格列", fontsize=11)
    ax.set_ylabel("网格行", fontsize=11)
    ax.set_xticks(np.arange(0, N, 4)); ax.set_yticks(np.arange(0, N, 4))

# ---------- 图1 综合活力 ----------
fig, ax = plt.subplots(figsize=(8, 7), dpi=300)
im = ax.imshow(V, cmap="YlOrRd", extent=extent, vmin=0)
base_axes(ax, "综合活力指数空间分布")
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cb.set_label("综合活力指数", fontsize=11)
fig.tight_layout(); fig.savefig("map_vitality.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---------- 图2 供给可达性 ----------
fig, ax = plt.subplots(figsize=(8, 7), dpi=300)
im = ax.imshow(S, cmap="BuGn", extent=extent, vmin=0)
base_axes(ax, "金融网点供给可达性空间分布")
cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
cb.set_label("高斯核供给可达性", fontsize=11)
fig.tight_layout(); fig.savefig("map_supply.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---------- 图3 LISA 显著分区 ----------
# 编码: 0 不显著, 1 显著HH, 2 显著LH, 3 显著LL, 4 显著HL
code = np.zeros_like(quad, dtype=int)
sig = pval < 0.05
code[sig & (quad == 1)] = 1
code[sig & (quad == 2)] = 2
code[sig & (quad == 3)] = 3
code[sig & (quad == 4)] = 4
colors = ["#f0f0f0", "#d7191c", "#2c7bb6", "#08519c", "#f16913"]
labels = ["不显著", "HH 高活力-高供给", "LH 低活力-高供给",
          "LL 低活力-低供给", "HL 高活力-低供给"]
cmap = ListedColormap(colors)
fig, ax = plt.subplots(figsize=(8.4, 7), dpi=300)
ax.imshow(code, cmap=cmap, extent=extent, vmin=0, vmax=4)
ax.set_xticks(np.arange(-0.5, N, 1), minor=True)
ax.set_yticks(np.arange(-0.5, N, 1), minor=True)
ax.grid(which="minor", color="white", linewidth=0.3)
ax.tick_params(which="minor", length=0)
base_axes(ax, "活力-网点双变量 LISA 显著分区")
counts = [(code == k).sum() for k in range(5)]
handles = [Patch(facecolor=colors[k], edgecolor="gray", linewidth=0.4,
                 label=f"{labels[k]}（{counts[k]}）") for k in range(5)]
ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1),
          frameon=True, fontsize=10, title="空间关联类型", title_fontsize=10)
fig.tight_layout(); fig.savefig("map_lisa.png", dpi=300, bbox_inches="tight"); plt.close(fig)

# ---------- 图4 潜力区 ----------
pmask = np.zeros((N, N), dtype=int)
for _, r in pot.iterrows():
    pmask[int(r["row"]), int(r["col"])] = 1
fig, ax = plt.subplots(figsize=(8.4, 7), dpi=300)
ax.imshow(V, cmap="Greys", extent=extent, alpha=0.35, vmin=0)
pot_cmap = ListedColormap([(0, 0, 0, 0), "#d62728"])
ax.imshow(pmask, cmap=pot_cmap, extent=extent, vmin=0, vmax=1)
ax.set_xticks(np.arange(-0.5, N, 1), minor=True)
ax.set_yticks(np.arange(-0.5, N, 1), minor=True)
ax.grid(which="minor", color="white", linewidth=0.25)
ax.tick_params(which="minor", length=0)
base_axes(ax, "高活力-低供给潜力区空间分布")
n_pot = int(pmask.sum())
handles = [Patch(facecolor="#d62728", label=f"潜力区（{n_pot}）"),
           Patch(facecolor="#bdbdbd", label="其他网格（底图为活力）")]
ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.02, 1),
          frameon=True, fontsize=10)
fig.tight_layout(); fig.savefig("map_potential.png", dpi=300, bbox_inches="tight"); plt.close(fig)

print("已生成 4 张图:")
for f in ["map_vitality.png", "map_supply.png", "map_lisa.png", "map_potential.png"]:
    print("  ", f)
print("显著 HL 网格:", int(((code == 4)).sum()), "| 潜力区:", n_pot)

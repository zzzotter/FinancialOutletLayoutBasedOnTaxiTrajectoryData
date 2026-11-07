# -*- coding: utf-8 -*-
"""
工作日/周末 与 昼夜 活力对比图（学术出版风格）
输入: grid_mismatch_full.csv（由 mismatch_analysis.py 生成）
输出: compare_weekday_weekend.png / compare_day_night.png （300 dpi）
依赖: pandas numpy matplotlib
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D

# ---------- 全局样式 ----------
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 11
plt.rcParams["axes.edgecolor"] = "#444444"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["savefig.bbox"] = "tight"

C_HEAT = "viridis"
C_DIV = "RdBu_r"
C_NIGHT = "Blues"
GRID = 32
INPUT = "grid_mismatch_full.csv"

df = pd.read_csv(INPUT)
def mat(col):
    return df[col].values.reshape(GRID, GRID)

def style_ax(ax, title):
    ax.set_title(title, fontsize=12.5, fontweight="bold", pad=8)
    ax.set_xticks([0, 8, 16, 24, 31])
    ax.set_yticks([0, 8, 16, 24, 31])
    ax.tick_params(labelsize=8.5, colors="#555555", length=3)
    ax.set_xlabel("网格列", fontsize=9.5)
    ax.set_ylabel("网格行", fontsize=9.5)

def panel_tag(ax, tag):
    ax.text(-0.12, 1.08, tag, transform=ax.transAxes,
            fontsize=14, fontweight="bold", va="top", ha="left")


# =====================================================================
# Figure 1: 工作日 vs 周末
# =====================================================================
fig, axes = plt.subplots(2, 2, figsize=(12.5, 10.5))
fig.suptitle("图1  工作日与周末商圈活力对比", fontsize=15.5, fontweight="bold", y=0.98)

Vw, Ve = mat("V_工作日"), mat("V_周末")
im0 = axes[0, 0].imshow(Vw, cmap=C_HEAT)
style_ax(axes[0, 0], "（a）工作日综合活力")
panel_tag(axes[0, 0], "a")
fig.colorbar(im0, ax=axes[0, 0], shrink=0.86, label="活力指数")

im1 = axes[0, 1].imshow(Ve, cmap=C_HEAT)
style_ax(axes[0, 1], "（b）周末综合活力")
panel_tag(axes[0, 1], "b")
fig.colorbar(im1, ax=axes[0, 1], shrink=0.86, label="活力指数")

# 相对变化率
eps = 1e-3
rate = (Ve - Vw) / (Vw + eps)
vmax = np.percentile(np.abs(rate), 95)
norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
im2 = axes[1, 0].imshow(rate, cmap=C_DIV, norm=norm)
style_ax(axes[1, 0], "（c）周末相对工作日变化率")
panel_tag(axes[1, 0], "c")
fig.colorbar(im2, ax=axes[1, 0], shrink=0.86, label="相对变化率")

# 散点
ax = axes[1, 1]
normal = df[df["潜力区"] == 0]
pot = df[df["潜力区"] == 1]
ax.scatter(normal["V_工作日"], normal["V_周末"], s=18,
           c="#3b6ea5", alpha=0.45, edgecolors="none", label="一般网格")
ax.scatter(pot["V_工作日"], pot["V_周末"], s=42,
           c="#d62728", alpha=0.85, edgecolors="white", linewidths=0.5,
           label="潜力区（显著HL）")
lim = max(df["V_工作日"].max(), df["V_周末"].max())
ax.plot([0, lim], [0, lim], ls="--", lw=1.2, c="#333333", label="等值线 y=x")
ax.set_xlim(0, lim * 1.05); ax.set_ylim(0, lim * 1.05)
ax.set_xlabel("工作日活力", fontsize=10)
ax.set_ylabel("周末活力", fontsize=10)
ax.set_title("（d）工作日—周末活力散点", fontsize=12.5, fontweight="bold", pad=8)
ax.grid(True, ls=":", lw=0.6, c="#bbbbbb", alpha=0.7)
ax.legend(frameon=True, framealpha=0.92, edgecolor="#cccccc",
          fontsize=9.5, loc="upper left")
panel_tag(ax, "d")

fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig("compare_weekday_weekend.png", dpi=300)
plt.close(fig)


# =====================================================================
# Figure 2: 昼夜对比
# =====================================================================
fig, axes = plt.subplots(2, 2, figsize=(12.5, 10.5))
fig.suptitle("图2  白天与夜间商圈活力结构对比", fontsize=15.5, fontweight="bold", y=0.98)

day = (mat("V_早") + mat("V_中") + mat("V_晚")) / 3
night = mat("V_夜间")
share = mat("夜间份额")

im0 = axes[0, 0].imshow(day, cmap=C_HEAT)
style_ax(axes[0, 0], "（a）白天平均活力（早/中/晚）")
panel_tag(axes[0, 0], "a")
fig.colorbar(im0, ax=axes[0, 0], shrink=0.86, label="活力指数")

im1 = axes[0, 1].imshow(night, cmap=C_NIGHT)
style_ax(axes[0, 1], "（b）夜间活力（21:00–次日06:00）")
panel_tag(axes[0, 1], "b")
fig.colorbar(im1, ax=axes[0, 1], shrink=0.86, label="活力指数")

im2 = axes[1, 0].imshow(share, cmap=C_NIGHT)
style_ax(axes[1, 0], "（c）夜间活力份额")
panel_tag(axes[1, 0], "c")
fig.colorbar(im2, ax=axes[1, 0], shrink=0.86, label="夜间/全天")

# 分时段箱线图
ax = axes[1, 1]
periods = ["V_早", "V_中", "V_晚", "V_夜间"]
labels = ["早", "中", "晚", "夜间"]
data_box = [df[p].values for p in periods]
box_colors = ["#8fb3d9", "#5b8fc4", "#3b6ea5", "#2c3e50"]
box_kw = dict(patch_artist=True, widths=0.6,
              showfliers=True, medianprops=dict(color="#e67e22", lw=1.6),
              flierprops=dict(marker="o", markersize=3,
                              markerfacecolor="#999999", alpha=0.4,
                              markeredgecolor="none"),
              whiskerprops=dict(color="#555555", lw=1),
              capprops=dict(color="#555555", lw=1))
_mpl_ver = tuple(int(x) for x in matplotlib.__version__.split(".")[:2])
box_kw["tick_labels" if _mpl_ver >= (3, 9) else "labels"] = labels
bp = ax.boxplot(data_box, **box_kw)
for patch, c in zip(bp["boxes"], box_colors):
    patch.set_facecolor(c); patch.set_alpha(0.85)
    patch.set_edgecolor("#444444")
ax.set_ylabel("活力指数", fontsize=10)
ax.set_xlabel("时段", fontsize=10)
ax.set_title("（d）分时段活力分布", fontsize=12.5, fontweight="bold", pad=8)
ax.grid(True, axis="y", ls=":", lw=0.6, c="#bbbbbb", alpha=0.7)
legend_elem = [Line2D([0], [0], color="#e67e22", lw=2, label="中位数")]
ax.legend(handles=legend_elem, frameon=True, framealpha=0.92,
          edgecolor="#cccccc", fontsize=9.5, loc="upper right")
panel_tag(ax, "d")

fig.tight_layout(rect=[0, 0, 1, 0.96])
fig.savefig("compare_day_night.png", dpi=300)
plt.close(fig)

print("已生成: compare_weekday_weekend.png / compare_day_night.png (300 dpi)")

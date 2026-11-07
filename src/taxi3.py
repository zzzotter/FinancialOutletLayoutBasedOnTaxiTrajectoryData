# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
from matplotlib import rcParams
rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
rcParams['axes.unicode_minus'] = False

v = pd.read_csv("grid_vitality.csv")
g = pd.read_csv("grid_coordinate_mapping.csv")[["row","col","center_lat","center_lon"]]
df = v.merge(g, on=["row","col"])

# 关键: 流量门槛, 剔除近零网格(小分母导致比值虚高)
threshold = df["活力_全天"].median()          # 也可用绝对阈值如0.05
valid = df[df["活力_全天"] >= threshold].copy()
print("门槛=%.4f, 达标 %d 格, 剔除 %d 个近零网格"
      % (threshold, len(valid), len(df)-len(valid)))

valid["夜间结构份额"] = valid["活力_夜间"] / valid["活力_全天"]
cols = ["row","col","活力_全天","活力_夜间","夜间结构份额","center_lat","center_lon"]

print("\n== 夜间绝对活力 Top10(真正的夜间热点) ==")
print(valid.nlargest(10, "活力_夜间")[cols].round(4).to_string(index=False))
print("\n== 夜间结构份额 Top10(达标网格里夜间相对最突出) ==")
print(valid.nlargest(10, "夜间结构份额")[cols].round(4).to_string(index=False))

valid.to_csv("grid_vitality_valid.csv", index=False, encoding="utf-8-sig")

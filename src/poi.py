# -*- coding: utf-8 -*-
"""
银行 POI 诊断 + 清洗 + 网格落点 + 500米覆盖率
依赖: pandas, numpy  (pip install pandas numpy)
用途: 先诊断原始数据是否混入 ATM/杂项、坐标系是否为 GCJ-02, 再清洗落点
"""
import math
import numpy as np
import pandas as pd

# ============ 配置 ============
INPUT = "C:/Users/ASUS/Desktop/bank_poi(1).csv"         # 原始文件名, 按实际改
LAT_MIN, LAT_MAX = 39.8213, 39.9938
LON_MIN, LON_MAX = 116.2681, 116.4929
N = 32
BUFFER_M = 500.0

# ============ GCJ-02 <-> WGS84 ============
PI, A, EE = 3.1415926535897932384626, 6378240.0, 0.00669342162296594323
def _tlat(x, y):
    r = -100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
    r += (20*math.sin(6*x*PI)+20*math.sin(2*x*PI))*2/3
    r += (20*math.sin(y*PI)+40*math.sin(y/3*PI))*2/3
    r += (160*math.sin(y/12*PI)+320*math.sin(y*PI/30))*2/3
    return r
def _tlon(x, y):
    r = 300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
    r += (20*math.sin(6*x*PI)+20*math.sin(2*x*PI))*2/3
    r += (20*math.sin(x*PI)+40*math.sin(x/3*PI))*2/3
    r += (150*math.sin(x/12*PI)+300*math.sin(x/30*PI))*2/3
    return r
def wgs_to_gcj(lon, lat):
    if lon < 72.004 or lon > 137.8347 or lat < 0.8293 or lat > 55.8271:
        return lon, lat
    dlat = _tlat(lon-105, lat-35); dlon = _tlon(lon-105, lat-35)
    rad = lat/180*PI; magic = 1-EE*math.sin(rad)**2; sm = math.sqrt(magic)
    dlat = dlat*180/((A*(1-EE))/(magic*sm)*PI)
    dlon = dlon*180/(A/sm*math.cos(rad)*PI)
    return lon+dlon, lat+dlat
def gcj_to_wgs(glon, glat):
    if glon < 72.004 or glon > 137.8347 or glat < 0.8293 or glat > 55.8271:
        return glon, glat
    wlon, wlat = glon, glat
    for _ in range(30):
        clon, clat = wgs_to_gcj(wlon, wlat)
        elon, elat = clon-glon, clat-glat
        if abs(elon) < 1e-9 and abs(elat) < 1e-9:
            break
        wlon -= elon; wlat -= elat
    return wlon, wlat

# ============ 读取 ============
df = pd.read_csv(INPUT)
print("原始记录数:", len(df))
df["大类"] = df["typecode"].astype(str).str[:4]

# ============ Part 1: 诊断(看是否没洗干净) ============
print("\n" + "="*50)
print("【诊断1】typecode 大类分布(看是否混入 ATM/杂项)")
print("="*50)
label_map = {"1601":"银行网点","1603":"ATM/自助设备","1509":"典当等非银行金融"}
vc = df["大类"].value_counts()
for k, v in vc.items():
    print("  %s %-12s : %d 条" % (k, label_map.get(k,"其他杂项"), v))
n_bank = int((df["大类"]=="1601").sum())
n_atm = int((df["大类"]=="1603").sum())
n_other = len(df) - n_bank - n_atm
print("  -> 真正银行网点仅占 %.1f%%, 其余 %d 条为 ATM/杂项"
      % (100*n_bank/len(df), n_atm+n_other))

print("\n" + "="*50)
print("【诊断2】坐标系验证(看是否为未转换的 GCJ-02)")
print("="*50)
sample = df[df["name"].str.contains("国贸")].head(1)
for _, x in sample.iterrows():
    wlon, wlat = gcj_to_wgs(float(x["lng"]), float(x["lat"]))
    print("  点: %s" % x["name"])
    print("  原始坐标 (%.5f, %.5f)" % (x["lng"], x["lat"]))
    print("  转WGS   (%.5f, %.5f)" % (wlon, wlat))
    print("  偏移约 %.0f m -> 原始数据是 GCJ-02, 不转换会落错网格"
          % math.hypot((x["lng"]-wlon)*85400, (x["lat"]-wlat)*111320))

# ============ Part 2: 清洗(只保留 1601 银行网点) ============
bank = df[df["大类"]=="1601"].copy()
w = bank.apply(lambda x: gcj_to_wgs(float(x["lng"]), float(x["lat"])), axis=1)
bank["wgs_lon"] = [x[0] for x in w]
bank["wgs_lat"] = [x[1] for x in w]

dlat = (LAT_MAX-LAT_MIN)/N
dlon = (LON_MAX-LON_MIN)/N
def to_grid(lon, lat):
    if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
        return None, None
    return (min(int((LAT_MAX-lat)/dlat), 31),
            min(int((lon-LON_MIN)/dlon), 31))
g = bank.apply(lambda x: to_grid(x["wgs_lon"], x["wgs_lat"]), axis=1)
bank["row"] = [x[0] for x in g]
bank["col"] = [x[1] for x in g]
inside = bank.dropna(subset=["row"]).copy()
inside["row"] = inside["row"].astype(int)
inside["col"] = inside["col"].astype(int)
print("\n清洗后银行网点 %d 个, 落在四环网格内 %d 个(四环外剔除 %d 个)"
      % (len(bank), len(inside), len(bank)-len(inside)))

# ============ Part 3: 完整 32x32 网格 + 每格网点数 ============
grid_df = pd.DataFrame(
    [(r, c) for r in range(N) for c in range(N)], columns=["row", "col"])
cnt = inside.groupby(["row", "col"]).size().rename("bank_count").reset_index()
grid_df = grid_df.merge(cnt, on=["row", "col"], how="left").fillna({"bank_count":0})
grid_df["bank_count"] = grid_df["bank_count"].astype(int)

# 网格中心坐标
grid_df["center_lat"] = LAT_MAX - (grid_df["row"]+0.5)*dlat
grid_df["center_lon"] = LON_MIN + (grid_df["col"]+0.5)*dlon

# ============ Part 4: 500米覆盖率 ============
# 向量化计算每个网格中心到所有四环内网点的近似距离
plat = inside["wgs_lat"].values
plon = inside["wgs_lon"].values
count500 = np.zeros(len(grid_df), dtype=int)
for i, x in grid_df.iterrows():
    dy = (plat - x["center_lat"])*111320
    dx = (plon - x["center_lon"])*85400
    count500[i] = int((np.sqrt(dx*dx+dy*dy) <= BUFFER_M).sum())
grid_df["count_500m"] = count500
grid_df["covered_500m"] = (grid_df["count_500m"] > 0).astype(int)

# ============ Part 5: 归一化 ============
def minmax(s):
    lo, hi = s.min(), s.max()
    return (s-lo)/(hi-lo) if hi > lo else pd.Series(0, index=s.index)
grid_df["bank_count_norm"] = minmax(grid_df["bank_count"])
grid_df["count_500m_norm"] = minmax(grid_df["count_500m"])

grid_df.to_csv("grid_bank_coverage.csv", index=False, encoding="utf-8-sig")
inside.to_csv("bank_cleaned.csv", index=False, encoding="utf-8-sig")

print("\n" + "="*50)
print("【结果汇总】")
print("="*50)
print("  有网点的网格数: %d / 1024" % (grid_df["bank_count"] > 0).sum())
print("  500米覆盖的网格数: %d / 1024 (覆盖率 %.1f%%)"
      % (grid_df["covered_500m"].sum(), 100*grid_df["covered_500m"].mean()))
print("  单格网点最多: %d 个" % grid_df["bank_count"].max())
print("\n已输出:")
print("  grid_bank_coverage.csv  (每格网点数+500米覆盖+归一化)")
print("  bank_cleaned.csv        (清洗落点后的银行网点明细)")

# -*- coding: utf-8 -*-
"""
=====================================================================
城市商圈活力 - 银行网点错配分析（完整专业版, 含边缘效应修复）
项目: 基于出租车轨迹数据的城市商圈活力测度与金融网点布局优化
=====================================================================
方法体系:
  1. 综合活力指数 V: 分时段 inflow(到达/β) + outflow(离开/α) 加权,
     时段权重(夜间 1.5)跨时段聚合, 并区分工作日/周末
  2. 金融供给可达性 S: 高斯核距离衰减(默认 σ=500m), 使用【全量网点
     (含四环外)】计算, 修复研究边界截断导致的边缘效应
  3. z-score 标准化残差错配指数 M = z(V) - z(S)
  4. 双变量局部空间自相关(BiLISA): 999 次置换, 识别显著
     "高活力-低供给(HL)"潜力区, 替代人为阈值
  5. 申报书比值法 M_ratio = V/(S+ε) 保留为对照
  6. 前 10% 潜力区 + 多参数权重/带宽敏感性分析 + 边缘格标记
依赖: numpy pandas scipy libpysal esda
  pip install numpy pandas scipy libpysal esda
=====================================================================
"""
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# ===================== 全局配置 =====================
NPY_FILE = "TaxiBJ21.npy"          # 出租车数据
BANK_FILE = "bank_poi(1).csv"      # 原始银行 POI(脚本内部完成筛选+坐标转换)
SEED = 42
N = 32
LAT_MIN, LAT_MAX = 39.8213, 39.9938
LON_MIN, LON_MAX = 116.2681, 116.4929

# 基准权重参数(申报书口径)
ALPHA = 0.4          # 上车/离开(outflow)权重
BETA = 0.6           # 下车/到达(inflow)权重, 反映吸引力, 取值更高
NIGHT_W = 1.5        # 夜间时段权重
DAY_W = 1.0
SIGMA = 500.0        # 高斯核服务半径(米)
EPS = 1e-3           # 比值法防除零
P_ALPHA = 0.05       # LISA 显著性水平

# 时段槽位(每天48槽, 槽0=00:00)
PERIOD_SLOTS = {
    "早":   list(range(12, 18)),                 # 06:00-09:00
    "中":   list(range(18, 34)),                 # 09:00-17:00
    "晚":   list(range(34, 42)),                 # 17:00-21:00
    "夜间": list(range(42, 48)) + list(range(0, 12)),  # 21:00-次日06:00
}
PERIOD_ORDER = ["早", "中", "晚", "夜间"]

# 三段时间(起始日期, 天数, 起始槽)
SEGMENTS = [
    (datetime(2012, 11, 1), 30, 0),
    (datetime(2014, 11, 1), 29, 1440),
    (datetime(2015, 11, 1), 30, 2832),
]


# ===================== GCJ-02 <-> WGS84 =====================
PI_G, A_G, EE_G = 3.1415926535897932384626, 6378240.0, 0.00669342162296594323
def _tlat(x, y):
    r = -100+2*x+3*y+0.2*y*y+0.1*x*y+0.2*math.sqrt(abs(x))
    r += (20*math.sin(6*x*PI_G)+20*math.sin(2*x*PI_G))*2/3
    r += (20*math.sin(y*PI_G)+40*math.sin(y/3*PI_G))*2/3
    r += (160*math.sin(y/12*PI_G)+320*math.sin(y*PI_G/30))*2/3
    return r
def _tlon(x, y):
    r = 300+x+2*y+0.1*x*x+0.1*x*y+0.1*math.sqrt(abs(x))
    r += (20*math.sin(6*x*PI_G)+20*math.sin(2*x*PI_G))*2/3
    r += (20*math.sin(x*PI_G)+40*math.sin(x/3*PI_G))*2/3
    r += (150*math.sin(x/12*PI_G)+300*math.sin(x/30*PI_G))*2/3
    return r
def wgs_to_gcj(lon, lat):
    if lon < 72.004 or lon > 137.8347 or lat < 0.8293 or lat > 55.8271:
        return lon, lat
    dlat = _tlat(lon-105, lat-35); dlon = _tlon(lon-105, lat-35)
    rad = lat/180*PI_G; magic = 1-EE_G*math.sin(rad)**2; sm = math.sqrt(magic)
    dlat = dlat*180/((A_G*(1-EE_G))/(magic*sm)*PI_G)
    dlon = dlon*180/(A_G/sm*math.cos(rad)*PI_G)
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


# ===================== 时间索引 =====================
def build_slot_datetimes():
    dts = []
    for start, ndays, _ in SEGMENTS:
        for d in range(ndays):
            for s in range(48):
                dts.append(start + timedelta(days=d, minutes=30 * s))
    assert len(dts) == 4272
    return np.array(dts)


# ===================== 活力指数 =====================
def compute_vitality(data, slot_of_day, weekend_mask, alpha, beta, night_w):
    inflow = data[:, 0, :, :]
    outflow = data[:, 1, :, :]
    heat = beta * inflow + alpha * outflow

    v_period = {}
    for p in PERIOD_ORDER:
        sel = np.isin(slot_of_day, PERIOD_SLOTS[p])
        v_period[p] = heat[sel].mean(axis=0)

    weights = np.array([night_w if p == "夜间" else DAY_W for p in PERIOD_ORDER])
    V = sum(w * v_period[p] for w, p in zip(weights, PERIOD_ORDER)) / weights.sum()

    def aggregate(mask):
        vp = {}
        for p in PERIOD_ORDER:
            sel = mask & np.isin(slot_of_day, PERIOD_SLOTS[p])
            vp[p] = heat[sel].mean(axis=0)
        return sum(w * vp[p] for w, p in zip(weights, PERIOD_ORDER)) / weights.sum()

    V_workday = aggregate(~weekend_mask)
    V_weekend = aggregate(weekend_mask)
    night_share = v_period["夜间"] / (V + 1e-12)

    return {
        "V": V,
        "V_早": v_period["早"], "V_中": v_period["中"],
        "V_晚": v_period["晚"], "V_夜间": v_period["夜间"],
        "V_工作日": V_workday, "V_周末": V_weekend,
        "夜间份额": night_share,
    }


# ===================== 供给可达性 =====================
def compute_supply(grid_df, banks, sigma):
    """高斯核距离衰减, banks 为参与计算的全量网点(含四环外)"""
    plat = banks["wgs_lat"].values
    plon = banks["wgs_lon"].values
    S = np.zeros(len(grid_df))
    for i, x in grid_df.iterrows():
        dy = (plat - x["center_lat"]) * 111320.0
        dx = (plon - x["center_lon"]) * 85400.0
        d2 = dx * dx + dy * dy
        S[i] = np.sum(np.exp(-d2 / (2 * sigma * sigma)))
    return S


# ===================== 标准化工具 =====================
def zscore(a):
    return (a - a.mean()) / a.std(ddof=0)

def minmax(a):
    lo, hi = a.min(), a.max()
    return (a - lo) / (hi - lo) if hi > lo else np.zeros_like(a)


# ===================== 主流程 =====================
def main():
    np.random.seed(SEED)
    print("加载数据 ...")
    data = np.load(NPY_FILE)
    assert data.shape == (4272, 2, 32, 32), "数据形状异常"

    # ---- 银行 POI 清洗: 筛选1601 + GCJ转WGS + 落点 ----
    raw = pd.read_csv(BANK_FILE)
    raw["大类"] = raw["typecode"].astype(str).str[:4]
    banks = raw[raw["大类"] == "1601"].copy()
    w = banks.apply(lambda x: gcj_to_wgs(float(x["lng"]), float(x["lat"])), axis=1)
    banks["wgs_lon"] = [x[0] for x in w]
    banks["wgs_lat"] = [x[1] for x in w]

    dlat = (LAT_MAX - LAT_MIN) / N
    dlon = (LON_MAX - LON_MIN) / N
    def to_grid(lon, lat):
        if not (LAT_MIN <= lat <= LAT_MAX and LON_MIN <= lon <= LON_MAX):
            return None, None
        return (min(int((LAT_MAX-lat)/dlat), 31),
                min(int((lon-LON_MIN)/dlon), 31))
    g = banks.apply(lambda x: to_grid(x["wgs_lon"], x["wgs_lat"]), axis=1)
    banks["row"] = [x[0] for x in g]
    banks["col"] = [x[1] for x in g]
    inside = banks.dropna(subset=["row"]).copy()
    inside["row"] = inside["row"].astype(int)
    inside["col"] = inside["col"].astype(int)
    print("银行网点: 全量 %d (含四环外), 其中四环内 %d" % (len(banks), len(inside)))

    # 时间索引
    dts = build_slot_datetimes()
    slot_of_day = np.array([d.hour * 2 + d.minute // 30 for d in dts])
    weekend_mask = np.array([d.weekday() >= 5 for d in dts])

    # 完整 32x32 网格(row-major, 与 lat2W 一致)
    grid_df = pd.DataFrame(
        [(r, c) for r in range(N) for c in range(N)], columns=["row", "col"])
    grid_df["center_lat"] = LAT_MAX - (grid_df["row"] + 0.5) * dlat
    grid_df["center_lon"] = LON_MIN + (grid_df["col"] + 0.5) * dlon
    grid_df["边缘格"] = ((grid_df["row"].isin([0, N-1])) |
                        (grid_df["col"].isin([0, N-1]))).astype(int)

    # ---- 1. 活力 ----
    print("计算综合活力指数 ...")
    vit = compute_vitality(data, slot_of_day, weekend_mask, ALPHA, BETA, NIGHT_W)
    for k, v in vit.items():
        grid_df[k] = v.reshape(-1)
    v_thr = np.median(vit["V"])
    grid_df["达标"] = (grid_df["V"] >= v_thr).astype(int)

    # 本格网点数(仅四环内落点)
    cnt = inside.groupby(["row", "col"]).size().rename("bank_count").reset_index()
    grid_df = grid_df.merge(cnt, on=["row", "col"], how="left")
    grid_df["bank_count"] = grid_df["bank_count"].fillna(0).astype(int)

    # ---- 2. 供给可达性(全量网点, 修复边缘效应) ----
    print("计算高斯距离衰减供给可达性 (σ=%.0fm, 全量网点) ..." % SIGMA)
    grid_df["S"] = compute_supply(grid_df, banks, SIGMA)

    # ---- 3. z-score 残差错配 ----
    zV = zscore(grid_df["V"].values)
    zS = zscore(grid_df["S"].values)
    grid_df["zV"] = zV
    grid_df["zS"] = zS
    grid_df["M_残差"] = zV - zS

    # ---- 4. 双变量 LISA ----
    print("双变量 LISA 检验 (999 次置换) ...")
    import libpysal
    from esda.moran import Moran_Local_BV
    wq = libpysal.weights.lat2W(N, N, rook=False)
    wq.transform = "r"
    ml = Moran_Local_BV(zV, zS, wq, permutations=999, seed=SEED)
    grid_df["LISA_象限"] = ml.q
    grid_df["LISA_p"] = ml.p_sim
    quad_name = {1: "HH高活力高供给", 2: "LH低活力高供给",
                 3: "LL低活力低供给", 4: "HL高活力低供给"}
    grid_df["LISA_类型"] = grid_df["LISA_象限"].map(quad_name)
    grid_df["显著HL"] = ((grid_df["LISA_象限"] == 4) &
                         (grid_df["LISA_p"] < P_ALPHA)).astype(int)

    # ---- 5. 比值法对照 ----
    V_mm = minmax(grid_df["V"].values)
    S_mm = minmax(grid_df["S"].values)
    grid_df["V_mm"] = V_mm
    grid_df["S_mm"] = S_mm
    grid_df["M_比值"] = V_mm / (S_mm + EPS)
    grid_df["比值_潜力"] = ((grid_df["M_比值"] > 1.2) &
                           (grid_df["达标"] == 1)).astype(int)

    # ---- 6. 前 10% 潜力区 ----
    thr90 = np.quantile(grid_df["M_残差"], 0.9)
    grid_df["前10%门槛"] = (grid_df["M_残差"] >= thr90).astype(int)
    grid_df["潜力区"] = ((grid_df["前10%门槛"] == 1) &
                        (grid_df["显著HL"] == 1) &
                        (grid_df["达标"] == 1)).astype(int)

    # ===================== 敏感性分析 =====================
    print("敏感性分析 ...")
    beta_grid = [0.5, 0.6, 0.7]
    night_grid = [1.0, 1.5, 2.0]
    sigma_grid = [300.0, 500.0, 800.0]
    base_M = grid_df["M_残差"].values
    base_top = set(grid_df.loc[grid_df["潜力区"] == 1, ["row", "col"]]
                   .apply(tuple, axis=1))
    rows = []
    for b in beta_grid:
        for nw in night_grid:
            for sg in sigma_grid:
                v = compute_vitality(data, slot_of_day, weekend_mask,
                                     1-b, b, nw)
                V_ = v["V"].reshape(-1)
                S_ = compute_supply(grid_df, banks, sg)
                M_ = zscore(V_) - zscore(S_)
                rho = spearmanr(base_M, M_).statistic
                top = set(pd.DataFrame(
                    {"row": grid_df["row"], "col": grid_df["col"],
                     "M": M_, "ok": V_ >= np.median(V_)}
                ).query("M >= %f and ok" % np.quantile(M_, 0.9))
                    [["row", "col"]].apply(tuple, axis=1))
                overlap = len(top & base_top) / max(len(base_top), 1)
                is_base = (b == BETA and nw == NIGHT_W and sg == SIGMA)
                rows.append({
                    "beta下车权重": b, "夜间权重": nw, "sigma带宽": sg,
                    "Spearman相关": round(rho, 4),
                    "前10%与基准重叠率": round(overlap, 3),
                    "是否基准": "是" if is_base else "",
                })
    sens = pd.DataFrame(rows)

    # ===================== 输出 =====================
    grid_df.to_csv("grid_mismatch_full.csv", index=False, encoding="utf-8-sig")
    pot = grid_df[grid_df["潜力区"] == 1].sort_values("M_残差", ascending=False)
    pot.to_csv("potential_areas.csv", index=False, encoding="utf-8-sig")
    sens.to_csv("sensitivity_analysis.csv", index=False, encoding="utf-8-sig")
    banks.to_csv("banks_wgs_full.csv", index=False, encoding="utf-8-sig")

    # ===================== 汇总 =====================
    print("\n" + "=" * 60)
    print("分析结果汇总（边缘效应已修复）")
    print("=" * 60)
    print("活力门槛(中位数): %.4f, 达标网格 %d 个" % (v_thr, grid_df["达标"].sum()))
    print("显著 HL 网格: %d 个 (其中边缘格 %d 个)" %
          (grid_df["显著HL"].sum(),
           int(((grid_df["显著HL"] == 1) & (grid_df["边缘格"] == 1)).sum())))
    print("比值法识别潜力网格: %d 个" % grid_df["比值_潜力"].sum())
    print("最终潜力区: %d 个, M残差90分位=%.3f" %
          (grid_df["潜力区"].sum(), thr90))
    print("敏感性: Spearman %.3f ~ %.3f, 平均重叠率 %.3f" %
          (sens["Spearman相关"].min(), sens["Spearman相关"].max(),
           sens["前10%与基准重叠率"].mean()))
    print("\nTop10 潜力网格:")
    print(pot[["row", "col", "V", "S", "M_残差", "LISA_p",
               "M_比值", "边缘格"]].head(10).to_string(index=False))
    print("\n已输出: grid_mismatch_full.csv / potential_areas.csv / "
          "sensitivity_analysis.csv / banks_wgs_full.csv")


if __name__ == "__main__":
    main()

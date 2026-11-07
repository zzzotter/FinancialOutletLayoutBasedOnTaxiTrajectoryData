import numpy as np
import pandas as pd

data = np.load("C:/Users/ASUS/Downloads/TaxiBJ21.npy")
# 复用时间映射(若已存csv直接读)
t = pd.read_csv("time_slot_mapping.csv")
t["start_time"] = pd.to_datetime(t["start_time"])
t["hour"] = t["start_time"].dt.hour

inflow = data[:, 0]   # 以到达为主, 形状(4272,32,32)

def agg(mask):        # 给定槽位布尔掩码, 返回32x32相对活力
    sub = inflow[mask]
    return sub.mean(axis=0)

# 营业时段 8:00-22:00(槽16-43); 夜间 22:00-次日00:30
biz = t["hour"].between(8, 21).values
night = (t["hour"] >= 22).values | (t["hour"] == 0).values

rows = []
for r in range(32):
    for c in range(32):
        m = lambda mk: inflow[mk, r, c].mean()
        rows.append({
            "row": r, "col": c,
            "活力_全天": m(biz),
            "活力_工作日": m(biz & ~t["is_weekend"].values),
            "活力_周末": m(biz & t["is_weekend"].values),
            "活力_夜间": m(night),
            "夜间占比": m(night) / (m(biz) + 1e-9),
        })
vitality = pd.DataFrame(rows)
vitality.to_csv("grid_vitality.csv", index=False, encoding="utf-8-sig")
print(vitality.describe())

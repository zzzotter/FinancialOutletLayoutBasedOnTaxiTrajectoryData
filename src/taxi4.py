# -*- coding: utf-8 -*-
import datetime as dt
import numpy as np
import pandas as pd

SEGMENTS = [(dt.date(2012,11,1),30,0),
            (dt.date(2014,11,1),29,1440),
            (dt.date(2015,11,1),30,2832)]
# 早 06-09 | 中 09-17 | 晚 17-21 | 夜间 21-次日06
PERIOD_SLOTS = {"早": list(range(12,18)),
                "中": list(range(18,34)),
                "晚": list(range(34,42)),
                "夜间": list(range(42,48)) + list(range(0,12))}

def slot_meta(slot):
    for start, days, base in SEGMENTS:
        if base <= slot < base + days*48:
            off = slot - base
            d = start + dt.timedelta(days=off//48)
            return d, off % 48, d.weekday() >= 5
    raise ValueError("槽位越界")

def main(npy_path="C:/Users/ASUS/Downloads/TaxiBJ21.npy"):
    data = np.load(npy_path)
    n = data.shape[0]
    day_type = np.empty(n, dtype=object)
    period = np.empty(n, dtype=object)
    sod_arr = np.empty(n, dtype=int)
    for s in range(n):
        d, sod, we = slot_meta(s)
        day_type[s] = "周末" if we else "工作日"
        sod_arr[s] = sod
    for pname, slots in PERIOD_SLOTS.items():
        for sod in slots:
            period[sod_arr == sod] = pname

    records = []
    for r in range(32):
        for c in range(32):
            row = {"row": r, "col": c}
            for dn in ["工作日", "周末"]:
                for pn in ["早", "中", "晚", "夜间"]:
                    mask = (day_type == dn) & (period == pn)
                    for ch, cn in [(0,"inflow"),(1,"outflow")]:
                        row["%s_%s_%s" % (dn,pn,cn)] = float(data[mask,ch,r,c].mean())
            records.append(row)
    df = pd.DataFrame(records)

    heat = [x for x in df.columns if x not in ("row","col")]
    for col in heat:
        lo, hi = df[col].min(), df[col].max()
        df[col+"_norm"] = (df[col]-lo)/(hi-lo) if hi > lo else 0.0

    df.to_csv("grid_period_heat.csv", index=False, encoding="utf-8-sig")
    print("已输出 grid_period_heat.csv, 共 %d 列" % len(df.columns))

if __name__ == "__main__":
    main()

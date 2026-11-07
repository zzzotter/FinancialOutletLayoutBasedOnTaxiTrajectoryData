# -*- coding: utf-8 -*-
import numpy as np
import folium

# ===== 校准就改这四个参数 =====
LAT_MIN, LAT_MAX = 39.8213, 39.9938
LON_MIN, LON_MAX = 116.2681, 116.4929
N = 32
dlat = (LAT_MAX - LAT_MIN) / N
dlon = (LON_MAX - LON_MIN) / N

LANDMARKS = {
    "天安门": (39.9087, 116.3974), "国贸": (39.9085, 116.4577),
    "中关村": (39.9813, 116.3103), "北四环中路": (39.9850, 116.3900),
    "东四环中路": (39.9100, 116.4800), "南四环中路": (39.8300, 116.3800),
    "西四环中路": (39.9100, 116.2700),
}

data = np.load("C:/Users/ASUS/Downloads/TaxiBJ21.npy")
flow = data[:, 0, :, :].mean(axis=0)
nonzero = (flow > 0)

# 1. 边缘诊断
print("非零网格数: %d/1024" % nonzero.sum())
print("非零轮廓 最北row=%d 最南row=%d 最西col=%d 最东col=%d"
      % (np.where(nonzero)[0].min(), np.where(nonzero)[0].max(),
         np.where(nonzero)[1].min(), np.where(nonzero)[1].max()))
print("北缘 %.4f 南缘 %.4f 西缘 %.4f 东缘 %.4f"
      % (flow[0].mean(), flow[31].mean(), flow[:,0].mean(), flow[:,31].mean()))
print("内侧 row1 %.4f row30 %.4f" % (flow[1].mean(), flow[30].mean()))

# 2. 校准地图
m = folium.Map(location=[(LAT_MIN+LAT_MAX)/2, (LON_MIN+LON_MAX)/2],
               zoom_start=12, tiles="OpenStreetMap")
fmax = flow.max()
for r in range(N):
    for c in range(N):
        south = LAT_MAX-(r+1)*dlat; north = LAT_MAX-r*dlat
        west = LON_MIN+c*dlon; east = LON_MIN+(c+1)*dlon
        inten = float(flow[r, c])/fmax
        if nonzero[r, c]:
            color, fill, op = "red", "red", 0.08+0.5*inten
        else:
            color, fill, op = "gray", None, 0
        folium.Rectangle([[south,west],[north,east]], color=color, weight=0.6,
                         fill=fill is not None, fill_color=fill,
                         fill_opacity=op).add_to(m)
for name,(lat,lon) in LANDMARKS.items():
    folium.Marker([lat,lon], popup=name,
                  icon=folium.Icon(color="blue",icon="info-sign")).add_to(m)
m.save("calibrate_map.html")
print("已生成 calibrate_map.html")

# src/make_function_map.py
import pandas as pd
import folium
from pathlib import Path
from shapely.geometry import Polygon

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLASS_CSV = PROJECT_ROOT / "data" / "processed" / "grid_function_classification.csv"
GRID_CSV = PROJECT_ROOT / "data" / "processed" / "grid_coordinate_mapping.csv"
BANK_CSV = PROJECT_ROOT / "data" / "processed" / "bank_poi.csv"
HTML_DIR = PROJECT_ROOT / "outputs"

# 为不同类别分配颜色
COLOR_MAP = {
    "教育": "blue",
    "科技": "purple",
    "生活": "green",
    "服务": "orange",
    "混合型": "lightgray",
    "无 POI": "white"
}

def main():
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    
    df_class = pd.read_csv(CLASS_CSV, encoding="utf-8-sig")
    df_grid = pd.read_csv(GRID_CSV, encoding="utf-8-sig")
    
    # 将分类结果拼接到网格几何边界上
    df_grid["grid_id"] = df_grid["row"].astype(str) + "_" + df_grid["col"].astype(str)
    grid_geo = df_grid.merge(df_class[["grid_id", "grid_function", "total_poi"]], on="grid_id", how="left")
    
    # 初始化地图（北京中心）
    m = folium.Map(
        location=[39.90, 116.40], 
        zoom_start=11,
        tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        attr='高德地图'
    )
    
    print("正在渲染网格分类...")
    for _, r in grid_geo.iterrows():
        func = r["grid_function"] if pd.notna(r["grid_function"]) else "无 POI"
        color = COLOR_MAP.get(func, "gray")
        
        # 构造多边形
        poly = Polygon([
            (r["lon_west"], r["lat_south"]),
            (r["lon_east"], r["lat_south"]),
            (r["lon_east"], r["lat_north"]),
            (r["lon_west"], r["lat_north"])
        ])
        
        # 悬浮提示信息
        tooltip_text = f"网格: {r['grid_id']}<br>功能: {func}<br>POI总数: {int(r['total_poi'] if pd.notna(r['total_poi']) else 0)}"
        
        folium.GeoJson(
            poly,
            style_function=lambda x, c=color, f=func: {
                'color': 'black' if f == '混合型' else c,
                'weight': 0.5,
                'fillColor': c,
                'fillOpacity': 0.5 if f != '无 POI' else 0.1
            },
            tooltip=folium.Tooltip(tooltip_text)
        ).add_to(m)
        
    # 叠加银行网点（可选参考层）
    if BANK_CSV.exists():
        print("正在叠加银行点位...")
        bank_df = pd.read_csv(BANK_CSV, encoding="utf-8-sig")
        bank_df["lat_num"] = pd.to_numeric(bank_df["lat"], errors="coerce")
        bank_df["lng_num"] = pd.to_numeric(bank_df["lng"], errors="coerce")
        
        for _, r in bank_df.dropna(subset=["lat_num", "lng_num"]).iterrows():
            folium.CircleMarker(
                location=[r["lat_num"], r["lng_num"]],
                radius=2,
                color="red",
                fill=True,
                fill_opacity=0.8,
                tooltip=f"银行: {r.get('name', 'Unknown')}"
            ).add_to(m)

    out_map = HTML_DIR / "grid_function_map.html"
    m.save(str(out_map))
    print(f"交互地图已生成！请用浏览器打开: {out_map}")

if __name__ == "__main__":
    main()
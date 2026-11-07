# src/match_bank_to_grid.py
"""
将银行 POI 匹配到网格，并生成使用高德底图的可视化结果。
网格匹配逻辑：
lon_west <= lng < lon_east
lat_south <= lat < lat_north
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import folium
from shapely.geometry import Polygon

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BANK_CSV = PROJECT_ROOT / "data" / "processed" / "bank_poi_coordinate_check.csv"
GRID_CSV = PROJECT_ROOT / "data" / "processed" / "grid_coordinate_mapping.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
HTML_DIR = PROJECT_ROOT / "outputs"

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    print("读取数据...")
    if not BANK_CSV.exists():
        raise FileNotFoundError(f"找不到银行数据: {BANK_CSV}，请先运行 check_bank_coordinates.py")
    if not GRID_CSV.exists():
        raise FileNotFoundError(f"找不到网格数据: {GRID_CSV}")
        
    bank_df = pd.read_csv(BANK_CSV, encoding="utf-8-sig")
    grid_df = pd.read_csv(GRID_CSV, encoding="utf-8-sig")

    # 确保坐标是数值型
    bank_df["lng_num"] = pd.to_numeric(bank_df["lng"], errors="coerce")
    bank_df["lat_num"] = pd.to_numeric(bank_df["lat"], errors="coerce")
    
    # 默认未匹配状态
    bank_df["matched_row"] = None
    bank_df["matched_col"] = None
    bank_df["grid_id"] = None

    # 提取网格边界数组 (假设列名，如果与实际不符请在下方修改)
    # 预期列名: row, col, lon_west, lon_east, lat_south, lat_north
    lon_w = grid_df["lon_west"].values
    lon_e = grid_df["lon_east"].values
    lat_s = grid_df["lat_south"].values
    lat_n = grid_df["lat_north"].values
    rows = grid_df["row"].values
    cols = grid_df["col"].values

    print("正在执行空间网格匹配 (向量化)...")
    # 过滤掉无效坐标点
    valid_mask = bank_df["lng_num"].notna() & bank_df["lat_num"].notna()
    valid_banks = bank_df[valid_mask].copy()

    lngs = valid_banks["lng_num"].values[:, np.newaxis] # 形状 (N, 1)
    lats = valid_banks["lat_num"].values[:, np.newaxis] # 形状 (N, 1)

    # 向量化比较：利用 numpy 广播机制 (N, M) 矩阵
    in_lon = (lngs >= lon_w) & (lngs < lon_e)
    in_lat = (lats >= lat_s) & (lats < lat_n)
    match_matrix = in_lon & in_lat  # 形状 (N, M)，True 表示落在网格内

    # 找到每个点匹配的网格索引
    matched_indices = np.argmax(match_matrix, axis=1)
    has_match = np.any(match_matrix, axis=1)

    # 将结果写回 DataFrame
    valid_banks.loc[has_match, "matched_row"] = rows[matched_indices[has_match]]
    valid_banks.loc[has_match, "matched_col"] = cols[matched_indices[has_match]]
    valid_banks.loc[has_match, "grid_id"] = valid_banks.loc[has_match, "matched_row"].astype(str) + "_" + valid_banks.loc[has_match, "matched_col"].astype(str)

    # 将匹配结果更新回原始 DataFrame
    bank_df.update(valid_banks[["matched_row", "matched_col", "grid_id"]])

    # 保存全量匹配结果
    out_all = OUTPUT_DIR / "bank_poi_with_grid.csv"
    bank_df.to_csv(out_all, index=False, encoding="utf-8-sig")
    
    # 拆分已匹配和未匹配
    matched_df = bank_df[bank_df["grid_id"].notna()]
    unmatched_df = bank_df[bank_df["grid_id"].isna()]

    out_unmatched = OUTPUT_DIR / "unmatched_bank_poi.csv"
    unmatched_df.to_csv(out_unmatched, index=False, encoding="utf-8-sig")

    # 按网格统计
    if not matched_df.empty:
        grid_counts = matched_df.groupby(["matched_row", "matched_col"]).size().reset_index(name="bank_count")
        out_counts = OUTPUT_DIR / "bank_count_by_grid.csv"
        grid_counts.to_csv(out_counts, index=False, encoding="utf-8-sig")
        print(f"网格统计结果已保存至: {out_counts}")

    print("\n--- 匹配结果统计 ---")
    print(f"总输入记录数: {len(bank_df)}")
    print(f"成功匹配记录: {len(matched_df)}")
    print(f"未匹配记录数: {len(unmatched_df)}")
    print(f"全量结果已保存至: {out_all}")
    print(f"未匹配清单已保存至: {out_unmatched}")

    # ------------------ 生成可视化匹配地图 ------------------
    print("正在生成网格匹配可视化地图 (高德底图)...")
    
    # 动态计算网格中心点，作为地图初始中心
    center_lat = (grid_df["lat_south"].min() + grid_df["lat_north"].max()) / 2
    center_lng = (grid_df["lon_west"].min() + grid_df["lon_east"].max()) / 2

    # 使用高德底图
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=11,
        tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
        attr='高德地图'
    )

    # 1. 画网格（如果网格非常多，为了防止浏览器卡死，可以取消注释下面这行进行抽样）
    # grid_sample = grid_df.sample(min(1000, len(grid_df)), random_state=42)
    grid_sample = grid_df # 如果你的网格数量在 3000 以内，可以直接全画
    
    # 创建一个 FeatureGroup 方便统一管理网格层
    grid_layer = folium.FeatureGroup(name="Grid Boundaries")
    
    for _, r in grid_sample.iterrows():
        # 构造矩形边界
        poly = Polygon([
            (r["lon_west"], r["lat_south"]),
            (r["lon_east"], r["lat_south"]),
            (r["lon_east"], r["lat_north"]),
            (r["lon_west"], r["lat_north"])
        ])
        folium.GeoJson(
            poly,
            style_function=lambda x: {'color': 'black', 'weight': 0.5, 'fillOpacity': 0}
        ).add_to(grid_layer)
    grid_layer.add_to(m)

    # 2. 画银行点（为了性能，最多展示 2000 个点）
    bank_layer = folium.FeatureGroup(name="Bank POIs")
    plot_banks = matched_df.sample(min(2000, len(matched_df)), random_state=42) if len(matched_df) > 2000 else matched_df
    
    for _, r in plot_banks.iterrows():
        folium.CircleMarker(
            location=[r["lat_num"], r["lng_num"]],
            radius=3,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.7,
            popup=f"名称: {r.get('name', 'Unknown')}<br>网格: {r['grid_id']}"
        ).add_to(bank_layer)
    bank_layer.add_to(m)

    # 添加图层控制
    folium.LayerControl().add_to(m)

    out_map = HTML_DIR / "bank_grid_match_map.html"
    m.save(str(out_map))
    print(f"交互地图已保存至: {out_map}")

if __name__ == "__main__":
    main()
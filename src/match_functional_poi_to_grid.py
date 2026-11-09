# src/match_functional_poi_to_grid.py
import pandas as pd
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
POI_CSV = PROJECT_ROOT / "data" / "processed" / "4_else_clean.csv"
GRID_CSV = PROJECT_ROOT / "data" / "processed" / "grid_coordinate_mapping.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

def main():
    print("读取数据...")
    poi_df = pd.read_csv(POI_CSV, encoding="utf-8-sig")
    grid_df = pd.read_csv(GRID_CSV, encoding="utf-8-sig")

    # 确保坐标是数值型
    poi_df["lng_num"] = pd.to_numeric(poi_df["lng"], errors="coerce")
    poi_df["lat_num"] = pd.to_numeric(poi_df["lat"], errors="coerce")
    
    # 初始化列
    poi_df["matched_row"] = None
    poi_df["matched_col"] = None
    poi_df["grid_id"] = None

    # 提取网格边界
    lon_w = grid_df["lon_west"].values
    lon_e = grid_df["lon_east"].values
    lat_s = grid_df["lat_south"].values
    lat_n = grid_df["lat_north"].values
    rows = grid_df["row"].values
    cols = grid_df["col"].values

    print("正在执行空间网格匹配 (向量化)...")
    valid_mask = poi_df["lng_num"].notna() & poi_df["lat_num"].notna()
    valid_pois = poi_df[valid_mask].copy()

    lngs = valid_pois["lng_num"].values[:, np.newaxis]
    lats = valid_pois["lat_num"].values[:, np.newaxis]

    # 左闭右开匹配
    in_lon = (lngs >= lon_w) & (lngs < lon_e)
    in_lat = (lats >= lat_s) & (lats < lat_n)
    match_matrix = in_lon & in_lat

    matched_indices = np.argmax(match_matrix, axis=1)
    has_match = np.any(match_matrix, axis=1)

    # 写回结果
    valid_pois.loc[has_match, "matched_row"] = rows[matched_indices[has_match]]
    valid_pois.loc[has_match, "matched_col"] = cols[matched_indices[has_match]]
    valid_pois.loc[has_match, "grid_id"] = valid_pois.loc[has_match, "matched_row"].astype(str) + "_" + valid_pois.loc[has_match, "matched_col"].astype(str)

    poi_df.update(valid_pois[["matched_row", "matched_col", "grid_id"]])

    # 拆分并保存
    matched_df = poi_df[poi_df["grid_id"].notna()]
    unmatched_df = poi_df[poi_df["grid_id"].isna()]

    out_all = OUTPUT_DIR / "functional_poi_with_grid.csv"
    out_unmatched = OUTPUT_DIR / "unmatched_functional_poi.csv"
    
    poi_df.to_csv(out_all, index=False, encoding="utf-8-sig")
    unmatched_df.to_csv(out_unmatched, index=False, encoding="utf-8-sig")

    print(f"总输入: {len(poi_df)}，成功匹配: {len(matched_df)}，未匹配: {len(unmatched_df)}")
    print(f"结果已保存至: {out_all}")

if __name__ == "__main__":
    main()
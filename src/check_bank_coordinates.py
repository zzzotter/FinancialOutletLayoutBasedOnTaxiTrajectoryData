# src/check_bank_coordinates.py
"""
检查银行 POI 坐标质量：
1. 缺失值检查（lng/lat/poi_id）
2. 数值有效性检查（能否转为 float）
3. 范围粗筛（是否在北京范围内）
4. poi_id 重复检查
输出：
- data/processed/bank_poi_coordinate_check.csv (带检查状态)
- outputs/bank_poi_coordinate_check.html (点位分布图，抽样展示)
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import folium

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = PROJECT_ROOT / "data" / "processed" / "bank_poi.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"
HTML_DIR = PROJECT_ROOT / "outputs"

# 北京粗略边界（用于粗筛）
LNG_MIN, LNG_MAX = 115.4, 117.5
LAT_MIN, LAT_MAX = 39.4, 41.1

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    print(f"正在读取数据: {INPUT_CSV}")
    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    
    # 初始化检查状态
    df["check_status"] = "OK"
    df["error_reason"] = ""

    # 1. 缺失值检查
    missing_coords = df["lng"].isna() | df["lat"].isna()
    missing_id = df["poi_id"].isna() | (df["poi_id"] == "")
    df.loc[missing_coords, "check_status"] = "ERROR"
    df.loc[missing_coords, "error_reason"] += "缺失坐标; "
    df.loc[missing_id, "check_status"] = "ERROR"
    df.loc[missing_id, "error_reason"] += "缺失POI_ID; "

    # 2. 数值转换与有效性检查
    df["lng_num"] = pd.to_numeric(df["lng"], errors="coerce")
    df["lat_num"] = pd.to_numeric(df["lat"], errors="coerce")
    invalid_num = df["lng_num"].isna() | df["lat_num"].isna()
    df.loc[invalid_num, "check_status"] = "ERROR"
    df.loc[invalid_num, "error_reason"] += "坐标非数值; "

    # 3. 范围检查
    out_of_range = (
        (df["lng_num"] < LNG_MIN) | (df["lng_num"] > LNG_MAX) |
        (df["lat_num"] < LAT_MIN) | (df["lat_num"] > LAT_MAX)
    )
    df.loc[out_of_range, "check_status"] = "ERROR"
    df.loc[out_of_range, "error_reason"] += "坐标超出北京范围; "

    # 4. 重复检查
    duplicated_id = df.duplicated(subset=["poi_id"], keep=False) & ~missing_id
    df.loc[duplicated_id, "check_status"] = "WARNING"
    df.loc[duplicated_id, "error_reason"] += "poi_id重复; "

    # 统计报告
    print("\n--- 坐标检查统计 ---")
    print(f"总记录数: {len(df)}")
    print(f"正常记录: {len(df[df['check_status'] == 'OK'])}")
    print(f"警告记录: {len(df[df['check_status'] == 'WARNING'])}")
    print(f"错误记录: {len(df[df['check_status'] == 'ERROR'])}")

    # 保存检查结果
    out_csv = OUTPUT_DIR / "bank_poi_coordinate_check.csv"
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    print(f"检查结果已保存至: {out_csv}")

    # 5. 绘制交互地图（只画正常的点，最多画 2000 个防止卡顿）
    valid_df = df[(df["check_status"].isin(["OK", "WARNING"])) & df["lng_num"].notna()]
    if len(valid_df) > 2000:
        valid_df = valid_df.sample(2000, random_state=42)
        print(f"数据量较大，地图仅展示随机抽取的 2000 个点。")

    if not valid_df.empty:
        center_lat = valid_df["lat_num"].mean()
        center_lng = valid_df["lng_num"].mean()
        m = folium.Map(
    location=[center_lat, center_lng], 
    zoom_start=10,
    tiles='https://webrd02.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
    attr='高德地图'
)
        
        for _, row in valid_df.iterrows():
            folium.CircleMarker(
                location=[row["lat_num"], row["lng_num"]],
                radius=3,
                color="blue",
                fill=True,
                fill_opacity=0.6,
                popup=row.get("name", "Unknown")
            ).add_to(m)
        
        out_html = HTML_DIR / "bank_poi_coordinate_check.html"
        m.save(str(out_html))
        print(f"点位分布图已保存至: {out_html}")

if __name__ == "__main__":
    main()
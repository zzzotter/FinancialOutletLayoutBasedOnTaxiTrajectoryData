# src/clean_poi_4else.py
"""
清洗非银行（4 else）原始 POI 数据：
1. 删除重复记录（按 poi_id 去重）
2. 删除缺失坐标的记录
3. 统一字段格式（经纬度转 float，去空格）
4. 检查地点是否在北京市范围内（经纬度边界框粗筛）
5. 输出清洗后的 4_else_clean.csv
坐标系：保留高德原始 GCJ-02，不做转换。
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# --- 修改了这里的路径 ---
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "4_else.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "clean_4else_log.txt"

# 北京市经纬度粗略边界框（GCJ-02）
LNG_MIN, LNG_MAX = 115.4, 117.5
LAT_MIN, LAT_MAX = 39.4, 41.1


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_raw() -> pd.DataFrame:
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"未找到原始数据: {RAW_CSV}，请先运行 fetch_poi_4else.py")
    df = pd.read_csv(RAW_CSV, dtype=str, encoding="utf-8-sig")
    log(f"读取原始数据 {len(df)} 条")
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    original_len = len(df)

    # 1. 统一字段格式：去首尾空格
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()

    # 2. 经纬度转数值，无法转换的置为 NaN
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")

    # 3. 删除缺失坐标（poi_id 也建议非空）
    df = df.dropna(subset=["lng", "lat"])
    df = df[df["poi_id"].notna() & (df["poi_id"] != "")]
    log(f"删除缺失坐标/ID后: {len(df)} 条（原 {original_len} 条）")

    # 4. 按 poi_id 去重（同一 POI 可能被多个关键词多次召回）
    before_dedup = len(df)
    df = df.drop_duplicates(subset=["poi_id"], keep="first")
    log(f"按 poi_id 去重后: {len(df)} 条（删除 {before_dedup - len(df)} 条重复）")

    # 5. 北京市范围粗筛
    in_range = (
        (df["lng"] >= LNG_MIN) & (df["lng"] <= LNG_MAX) &
        (df["lat"] >= LAT_MIN) & (df["lat"] <= LAT_MAX)
    )
    out_of_range = df[~in_range]
    if len(out_of_range) > 0:
        log(f"发现 {len(out_of_range)} 条坐标超出北京市范围，已删除")
        log(f"  示例: {out_of_range[['name', 'lng', 'lat']].head(3).to_dict('records')}")
    df = df[in_range].copy()

    # 6. 重置索引
    df = df.reset_index(drop=True)
    log(f"清洗完成，最终 {len(df)} 条")
    return df


def save_output(df: pd.DataFrame) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 输出为一个文件 4_else_clean.csv
    out_path = PROCESSED_DIR / "4_else_clean.csv"
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    log(f"保存清洗后的非银行 POI: {len(df)} 条 -> {out_path}")

    # 输出各类别数量概览
    log("各类别数量：")
    for cat in ["教育", "科技", "生活", "服务"]:
        count = len(df[df['category'] == cat])
        log(f"  {cat}: {count} 条")


def main():
    log("=" * 50)
    log("开始清洗非银行（4 else）POI 数据")
    df = load_raw()
    df_clean = clean(df)
    save_output(df_clean)
    log(f"坐标系说明: 保留高德原始 GCJ-02，未做转换。")
    log("清洗结束")


if __name__ == "__main__":
    main()
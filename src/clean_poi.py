# src/clean_poi.py
"""
清洗原始 POI 数据：
1. 删除重复记录（按 poi_id 去重）
2. 删除缺失坐标的记录
3. 统一字段格式（经纬度转 float，去空格）
4. 检查地点是否在北京市范围内（经纬度边界框粗筛）
5. 按类别拆分为银行 POI 和功能 POI 两个交付文件
坐标系：保留高德原始 GCJ-02，不做转换。
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RAW_CSV = PROJECT_ROOT / "data" / "raw" / "raw_poi.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "clean_log.txt"

# 北京市经纬度粗略边界框（GCJ-02）
# 经度范围约 115.4 ~ 117.5，纬度范围约 39.4 ~ 41.1
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
        raise FileNotFoundError(f"未找到原始数据: {RAW_CSV}，请先运行 fetch_poi.py")
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

    # 6. 重置索引，保留关键字段
    df = df.reset_index(drop=True)
    log(f"清洗完成，最终 {len(df)} 条")
    return df


def split_and_save(df: pd.DataFrame) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 银行类
    bank_df = df[df["category"] == "银行"].copy()
    bank_path = PROCESSED_DIR / "bank_poi.csv"
    bank_df.to_csv(bank_path, index=False, encoding="utf-8-sig")
    log(f"保存银行 POI: {len(bank_df)} 条 -> {bank_path}")

    # 功能类（教育、科技、生活、服务）
    functional_categories = ["教育", "科技", "生活", "服务"]
    func_df = df[df["category"].isin(functional_categories)].copy()
    func_path = PROCESSED_DIR / "functional_poi.csv"
    func_df.to_csv(func_path, index=False, encoding="utf-8-sig")
    log(f"保存功能 POI: {len(func_df)} 条 -> {func_path}")

    # 输出各类别数量概览
    log("各类别数量：")
    for cat in ["银行"] + functional_categories:
        log(f"  {cat}: {len(df[df['category'] == cat])} 条")


def main():
    log("=" * 50)
    log("开始清洗 POI 数据")
    df = load_raw()
    df_clean = clean(df)
    split_and_save(df_clean)
    log(f"坐标系说明: 保留高德原始 GCJ-02，未做转换。")
    log("清洗结束")


if __name__ == "__main__":
    main()
# src/calculate_poi_shares.py
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_CSV = PROJECT_ROOT / "data" / "processed" / "functional_poi_with_grid.csv"
GRID_CSV = PROJECT_ROOT / "data" / "processed" / "grid_coordinate_mapping.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

def main():
    print("读取匹配后的数据...")
    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    grid_df = pd.read_csv(GRID_CSV, encoding="utf-8-sig")
    
    # 仅保留已匹配的
    df_matched = df[df["grid_id"].notna()].copy()

    # 透视表：每格各类数量
    counts_df = pd.crosstab(df_matched["grid_id"], df_matched["category"])
    
    # 补齐可能缺失的列
    for cat in ["教育", "科技", "生活", "服务"]:
        if cat not in counts_df.columns:
            counts_df[cat] = 0
            
    counts_df = counts_df[["教育", "科技", "生活", "服务"]]
    counts_df["total_poi"] = counts_df.sum(axis=1)

    # 生成完整的网格列表（包括没有 POI 的格子）
    grid_df["grid_id"] = grid_df["row"].astype(str) + "_" + grid_df["col"].astype(str)
    full_counts = grid_df[["grid_id", "row", "col"]].merge(counts_df, on="grid_id", how="left").fillna(0)
    
    # 计算占比
    shares_df = full_counts.copy()
    for cat in ["教育", "科技", "生活", "服务"]:
        shares_df[f"{cat}_share"] = shares_df.apply(
            lambda r: r[cat] / r["total_poi"] if r["total_poi"] > 0 else 0, axis=1
        )

    # 保存
    out_counts = OUTPUT_DIR / "poi_counts_by_grid.csv"
    out_shares = OUTPUT_DIR / "poi_shares_by_grid.csv"
    
    full_counts.to_csv(out_counts, index=False, encoding="utf-8-sig")
    shares_df.to_csv(out_shares, index=False, encoding="utf-8-sig")
    
    print(f"数量统计已保存: {out_counts}")
    print(f"占比统计已保存: {out_shares}")

if __name__ == "__main__":
    main()
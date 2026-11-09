# src/classify_grid_function.py
import pandas as pd
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SHARES_CSV = PROJECT_ROOT / "data" / "processed" / "poi_shares_by_grid.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

def determine_function(row):
    if row["total_poi"] == 0:
        return "无 POI"
    
    cats = ["教育", "科技", "生活", "服务"]
    shares = {cat: row[f"{cat}_share"] for cat in cats}
    
    max_cat = max(shares, key=shares.get)
    max_share = shares[max_cat]
    
    if max_share > 0.4:
        return max_cat
    else:
        return "混合型"

def main():
    print("读取占比数据...")
    df = pd.read_csv(SHARES_CSV, encoding="utf-8-sig")
    
    df["grid_function"] = df.apply(determine_function, axis=1)
    
    out_file = OUTPUT_DIR / "grid_function_classification.csv"
    df.to_csv(out_file, index=False, encoding="utf-8-sig")
    
    print(f"分类完成！结果已保存至: {out_file}")
    print("\n分类结果统计:")
    print(df["grid_function"].value_counts())

if __name__ == "__main__":
    main()
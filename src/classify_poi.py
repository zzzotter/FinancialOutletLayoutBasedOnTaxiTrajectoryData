# src/classify_poi.py
"""
整理类别并抽查：
1. 基于 POI 名称、高德 type/typecode、关键词，按规则重新判定类别
2. 规则优先级：高德类型编码 > 名称关键词 > 查询来源类别
3. 输出分类后的 bank_poi.csv 和 functional_poi.csv
4. 输出抽查样本 sample_for_review.csv 和分类规则文件 poi_category_rules.csv
坐标系：保持 GCJ-02 不变。
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
DOCS_DIR = PROJECT_ROOT / "docs"
LOG_DIR = PROJECT_ROOT / "logs"

BANK_CSV = PROCESSED_DIR / "bank_poi.csv"
FUNC_CSV = PROCESSED_DIR / "functional_poi.csv"
SAMPLE_CSV = DOCS_DIR / "sample_for_review.csv"
RULES_CSV = DOCS_DIR / "poi_category_rules.csv"
LOG_FILE = LOG_DIR / "classify_log.txt"

CATEGORIES = ["银行", "教育", "科技", "生活", "服务"]

# ---------- 分类规则 ----------
# 按优先级从高到低匹配。每条规则含：类别、匹配字段、匹配方式、说明。
# 匹配字段：name（POI 名称）、type（高德类型字符串）、typecode（高德类型编码前缀）
# 匹配方式：包含（contains）或前缀（startswith）

RULES = [
    # ---- 银行：高德金融类编码 1601xx，名称含银行/信用社/ATM ----
    {"category": "银行", "field": "typecode", "match": "1601", "mode": "startswith",
     "note": "高德金融保险服务-银行类编码"},
    {"category": "银行", "field": "name", "match": ["银行", "信用社", "农商行", "ATM"],
     "mode": "contains", "note": "名称含银行相关词"},

    # ---- 教育：高德科教文化 1412xx/1413xx 等，名称含学校/培训/教育 ----
    {"category": "教育", "field": "typecode", "match": ["1412", "1413", "1414"],
     "mode": "startswith", "note": "高德科教文化-学校/培训机构类编码"},
    {"category": "教育", "field": "name",
     "match": ["学校", "大学", "学院", "中学", "小学", "幼儿园", "培训", "教育",
               "党校", "技校", "职业学校"],
     "mode": "contains", "note": "名称含教育相关词"},

    # ---- 科技：名称含科技园/软件园/孵化器/研究院/众创空间 ----
    {"category": "科技", "field": "name",
     "match": ["科技园", "软件园", "孵化器", "众创空间", "研究院", "科技园",
               "高新技术", "创业园", "科创"],
     "mode": "contains", "note": "名称含科技载体相关词"},

    # ---- 生活：超市/便利店/菜市场/商场/购物中心/餐饮 ----
    {"category": "生活", "field": "typecode", "match": ["0601", "0602", "0604", "0501", "0505"],
     "mode": "startswith", "note": "高德购物/餐饮类编码"},
    {"category": "生活", "field": "name",
     "match": ["超市", "便利店", "菜市场", "商场", "购物中心", "餐饮", "餐厅",
               "饭店", "快餐", "咖啡", "奶茶"],
     "mode": "contains", "note": "名称含生活消费相关词"},

    # ---- 服务：政务/街道/派出所/社区/邮政/电信 ----
    {"category": "服务", "field": "name",
     "match": ["政务", "街道办", "派出所", "社区服务", "邮政", "电信", "营业厅",
               "便民服务", "服务中心"],
     "mode": "contains", "note": "名称含公共服务相关词"},
]


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def match_rule(row: pd.Series, rule: dict) -> bool:
    """判断单行是否命中某条规则。"""
    value = str(row.get(rule["field"], "") or "")
    if not value:
        return False
    targets = rule["match"] if isinstance(rule["match"], list) else [rule["match"]]
    if rule["mode"] == "startswith":
        return any(value.startswith(t) for t in targets)
    else:  # contains
        return any(t in value for t in targets)


def classify_row(row: pd.Series) -> tuple[str, str]:
    """按规则优先级判定类别，返回 (类别, 命中规则说明)。"""
    for rule in RULES:
        if match_rule(row, rule):
            return rule["category"], f"{rule['field']}:{rule['match']}({rule['note']})"
    # 规则未命中时，回退到查询时的来源类别
    fallback = row.get("category", "")
    if fallback in CATEGORIES:
        return fallback, "回退:查询来源类别"
    return "未分类", "未命中任何规则"


def load_raw() -> pd.DataFrame:
    if not RAW_CSV.exists():
        raise FileNotFoundError(f"未找到原始数据: {RAW_CSV}，请先运行 fetch_poi.py")
    df = pd.read_csv(RAW_CSV, dtype=str, encoding="utf-8-sig")
    # 基础清洗：去空格、删缺失坐标
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df = df.dropna(subset=["lng", "lat"])
    df = df.drop_duplicates(subset=["poi_id"], keep="first")
    log(f"载入并去重后 {len(df)} 条")
    return df


def apply_classification(df: pd.DataFrame) -> pd.DataFrame:
    results = df.apply(classify_row, axis=1)
    df["category_final"] = [r[0] for r in results]
    df["classify_rule"] = [r[1] for r in results]

    changed = (df["category_final"] != df["category"]).sum()
    log(f"类别判定完成，其中 {changed} 条与查询来源类别不同")

    # 记录类别变化明细，便于复查
    diff = df[df["category_final"] != df["category"]]
    if len(diff) > 0:
        log("类别修正示例（前 5 条）：")
        for _, r in diff.head(5).iterrows():
            log(f"  {r['name']}: {r['category']} -> {r['category_final']} ({r['classify_rule']})")

    unclassified = df[df["category_final"] == "未分类"]
    if len(unclassified) > 0:
        log(f"警告：{len(unclassified)} 条未分类，需人工处理")
        log(f"  示例: {unclassified[['name', 'type']].head(5).to_dict('records')}")

    return df


def save_outputs(df: pd.DataFrame) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    # 交付文件 1：银行 POI
    bank_df = df[df["category_final"] == "银行"].copy()
    bank_df.to_csv(BANK_CSV, index=False, encoding="utf-8-sig")
    log(f"保存银行 POI: {len(bank_df)} 条 -> {BANK_CSV}")

    # 交付文件 2：功能 POI
    func_df = df[df["category_final"].isin(["教育", "科技", "生活", "服务"])].copy()
    func_df.to_csv(FUNC_CSV, index=False, encoding="utf-8-sig")
    log(f"保存功能 POI: {len(func_df)} 条 -> {FUNC_CSV}")

    # 抽查样本：每个类别随机抽 10 条
    samples = []
    for cat in CATEGORIES:
        sub = df[df["category_final"] == cat]
        n = min(10, len(sub))
        if n > 0:
            samples.append(sub.sample(n=n, random_state=42))
    if samples:
        sample_df = pd.concat(samples, ignore_index=True)
        sample_df.to_csv(SAMPLE_CSV, index=False, encoding="utf-8-sig")
        log(f"保存抽查样本 {len(sample_df)} 条 -> {SAMPLE_CSV}")

    # 分类规则文件
    rules_df = pd.DataFrame([
        {
            "priority": i + 1,
            "category": r["category"],
            "field": r["field"],
            "match": "|".join(r["match"]) if isinstance(r["match"], list) else r["match"],
            "mode": r["mode"],
            "note": r["note"],
        }
        for i, r in enumerate(RULES)
    ])
    rules_df.to_csv(RULES_CSV, index=False, encoding="utf-8-sig")
    log(f"保存分类规则 {len(rules_df)} 条 -> {RULES_CSV}")

    # 类别数量概览
    log("最终各类别数量：")
    for cat in CATEGORIES:
        log(f"  {cat}: {len(df[df['category_final'] == cat])} 条")


def main():
    log("=" * 50)
    log("开始整理类别并生成抽查样本")
    df = load_raw()
    df = apply_classification(df)
    save_outputs(df)
    log("坐标系说明: 保持 GCJ-02 不变")
    log("整理完成")


if __name__ == "__main__":
    main()
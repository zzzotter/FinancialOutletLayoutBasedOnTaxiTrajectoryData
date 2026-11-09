# src/fetch_poi_4else.py
"""
按北京市各区 + 非银行关键词分批查询高德 POI，输出原始结果。
依赖: requests, python-dotenv
输出: data/raw/4_else.csv, logs/fetch_4else_log.txt
坐标系: GCJ-02（高德返回的 location 为“经度,纬度”）
"""

import csv
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# 把项目根目录加入 sys.path，方便导入 config 下的模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.district import BEIJING_DISTRICTS  # noqa: E402
from config.keyword_4else import KEYWORDS_4ELSE  # noqa: E402

# ---------- 配置 ----------
load_dotenv(PROJECT_ROOT / ".env")
AMAP_KEY = os.getenv("AMAP_KEY")

API_URL = "https://restapi.amap.com/v5/place/text"
PAGE_SIZE = 25            # v5 接口单页最大 25
MAX_PAGES = 8             # 200 / 25 = 8，单次查询翻页硬上限
REQUEST_INTERVAL = 0.35   # 秒，控制 QPS，避免触发限流
TIMEOUT = 15

RAW_DIR = PROJECT_ROOT / "data" / "raw"
LOG_DIR = PROJECT_ROOT / "logs"
RAW_CSV = RAW_DIR / "4_else.csv"
LOG_FILE = LOG_DIR / "fetch_4else_log.txt"

FIELDNAMES = [
    "category", "keyword", "district", "adcode_query",
    "poi_id", "name", "type", "typecode",
    "address", "lng", "lat", "adcode_poi",
    "cityname", "pname", "source", "query_time",
]

def log(msg: str) -> None:
    """同时打印到终端和日志文件。"""
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def check_key() -> None:
    if not AMAP_KEY:
        raise ValueError(
            "未找到 AMAP_KEY。请确认项目根目录 .env 文件中有 AMAP_KEY=你的Key"
        )
    log("Key 已加载（长度: %d）" % len(AMAP_KEY))

def search_page(keyword: str, adcode: str, page: int) -> dict:
    """调用一次关键字搜索，返回解析后的 JSON。"""
    params = {
        "key": AMAP_KEY,
        "keywords": keyword,
        "region": adcode,
        "city_limit": "true",
        "page_size": PAGE_SIZE,
        "page_num": page,
        "show_fields": "business,address",
    }
    resp = requests.get(API_URL, params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "1":
        raise RuntimeError(
            f"高德返回失败: status={data.get('status')}, "
            f"info={data.get('info')}, infocode={data.get('infocode')}"
        )
    return data

def parse_pois(data: dict, category: str, keyword: str, district: str,
               adcode_query: str, query_time: str) -> list[dict]:
    """把一次响应中的 pois 列表转成扁平记录。"""
    records = []
    for poi in data.get("pois", []):
        location = poi.get("location", "")
        lng, lat = "", ""
        if location and "," in location:
            lng, lat = location.split(",", 1)

        records.append({
            "category": category,
            "keyword": keyword,
            "district": district,
            "adcode_query": adcode_query,
            "poi_id": poi.get("id", ""),
            "name": poi.get("name", ""),
            "type": poi.get("type", ""),
            "typecode": poi.get("typecode", ""),
            "address": poi.get("address", ""),
            "lng": lng,
            "lat": lat,
            "adcode_poi": poi.get("adcode", ""),
            "cityname": poi.get("cityname", ""),
            "pname": poi.get("pname", ""),
            "source": "amap",
            "query_time": query_time,
        })
    return records

def fetch_all() -> list[dict]:
    """遍历所有类别、关键词、区，分页采集。"""
    all_records: list[dict] = []
    query_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_combos = sum(len(kws) for kws in KEYWORDS_4ELSE.values()) * len(BEIJING_DISTRICTS)
    combo_idx = 0

    for category, keywords in KEYWORDS_4ELSE.items():
        for keyword in keywords:
            for district, adcode in BEIJING_DISTRICTS.items():
                combo_idx += 1
                prefix = f"[{combo_idx}/{total_combos}] {category} | {keyword} | {district}"
                log(f"{prefix} 开始查询")

                combo_records = []
                try:
                    for page in range(1, MAX_PAGES + 1):
                        data = search_page(keyword, adcode, page)
                        pois = data.get("pois", [])
                        if not pois:
                            break
                        combo_records.extend(
                            parse_pois(data, category, keyword, district,
                                       adcode, query_time)
                        )
                        if len(pois) < PAGE_SIZE:
                            break  # 最后一页
                        time.sleep(REQUEST_INTERVAL)
                except Exception as e:
                    log(f"{prefix} 查询失败: {e}，跳过该组合")
                    continue

                all_records.extend(combo_records)
                log(f"{prefix} 返回 {len(combo_records)} 条，累计 {len(all_records)} 条")
                time.sleep(REQUEST_INTERVAL)  # 组合之间也稍作间隔

    return all_records

def save_csv(records: list[dict]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(RAW_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(records)
    log(f"已保存 {len(records)} 条到 {RAW_CSV}")

def main():
    check_key()
    log("=" * 50)
    log("开始分批查询高德 POI (非银行 4 类)")
    log(f"区数量: {len(BEIJING_DISTRICTS)}，类别数: {len(KEYWORDS_4ELSE)}")
    records = fetch_all()
    save_csv(records)
    log("查询结束")

if __name__ == "__main__":
    main()
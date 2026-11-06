import os
from dotenv import load_dotenv

load_dotenv()  # 读取同目录下的 .env 文件
amap_key = os.getenv("AMAP_KEY")

if not amap_key:
    raise ValueError("未找到 AMAP_KEY，请检查 .env 文件")
"""
演示：抓取一个产品详情页 + 提取规格参数（找 JS 中嵌入的 JSON 数据）
"""
import httpx
from bs4 import BeautifulSoup
import json
import re

def main():
    url = "https://www.hikvision.com/en/products/HiLook-IP-Products/Network-Cameras/Value-Camera/ipc-b120ha/"

    print("📄 抓取产品详情页...")
    resp = httpx.get(url, timeout=30, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0"})
    print(f"   状态码: {resp.status_code}")
    print(f"   页面大小: {len(resp.text)} bytes")
    print()

    soup = BeautifulSoup(resp.text, "lxml")

    title = soup.find("h1") or soup.find("title")
    if title:
        print(f"📌 产品标题: {title.get_text(strip=True)}")
    print()

    found = 0
    print("📋 方式1: 查 <table> 标签")
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                key = cells[0].get_text(strip=True)
                val = cells[1].get_text(strip=True)
                if key and val and len(key) < 80:
                    print(f"  {key}: {val[:120]}")
                    found += 1

    print(f"  表格提取: {found} 个")

    print("\n📋 方式2: 搜 JS JSON 中的 selectParameters")
    for script in soup.find_all("script"):
        text = script.string or ""
        if "selectParameters" in text:
            match = re.search(r'selectParameters["\']:\s*(\{.*?\})["\'],', text, re.DOTALL)
            if not match:
                match = re.search(r'"selectParameters"\s*:\s*(\{.*?\})\s*[,}]', text, re.DOTALL)
            if match:
                try:
                    params = json.loads(match.group(1))
                    for k, v in params.items():
                        val = ", ".join(v) if isinstance(v, list) else v
                        print(f"  {k}: {val}")
                        found += 1
                except json.JSONDecodeError as e:
                    print(f"  JSON解析失败: {e}")
                    # 截取一段看看
                    raw = match.group(1)[:300]
                    print(f"  原始数据: {raw}...")
            break

    print(f"\n📊 共提取 {found} 个参数")

if __name__ == "__main__":
    main()

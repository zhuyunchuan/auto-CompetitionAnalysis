"""
实时抓取演示 — 从 Hikvision JSON API 拉一页产品数据
"""
import httpx
import json
import sys

def main():
    url = "https://www.hikvision.com/content/hikvision/en/products/IP-Products/Network-Cameras/jcr:content/root/responsivegrid/search_list_copy.json"

    print("🌐 实时抓取演示: Hikvision JSON API")
    print(f"  请求: {url}")
    print()

    resp = httpx.get(url, timeout=30, follow_redirects=True)
    print(f"📡 状态码: {resp.status_code}")
    print(f"📦 响应大小: {len(resp.text)} bytes")
    print()

    data = resp.json()

    products = data.get("productList", data.get("products", []))
    if not products:
        for key in data:
            val = data[key]
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                products = val
                break

    print(f"📋 本次返回 {len(products)} 个产品")
    print()

    # 系列过滤取前几个
    count = 0
    for p in products:
        series = p.get("series", "")
        subseries = p.get("subseries", "")
        model = p.get("productModel", "")
        title = p.get("title", "")
        page_path = p.get("detailPath", p.get("pagePath", ""))
        url2 = f"https://www.hikvision.com{page_path}" if page_path else "(无URL)"
        print(f"  #{count+1} 型号: {model}")
        print(f"     名称: {title}")
        print(f"     系列: {series} > {subseries}")
        print(f"     URL: {url2}")
        print()
        count += 1
        if count >= 5:
            break

    print(f"🔍 第一个产品完整字段: {json.dumps(products[0], indent=2, ensure_ascii=False)[:500]}...")

if __name__ == "__main__":
    main()

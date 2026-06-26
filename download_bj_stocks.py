# -*- coding: utf-8 -*-
"""
北交所股票下载器
用法: python3 download_bj_stocks.py
"""
import os, sys, json, time, requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}

def main():
    print("=" * 60)
    print("📊 北交所上市公司数据下载")
    print("=" * 60)
    print()
    print("📥 拉取北交所股票...")

    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': '1', 'pz': '5', 'po': '1', 'np': '1',
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': '2', 'invt': '2', 'fid': 'f12',
        'fs': 'm:0+t:81+s:2048',
        'fields': 'f12,f14,f100,f102,f103,f124',
    }

    try:
        r = requests.get(url, params=params, headers=H, timeout=30)
        if r.status_code != 200:
            print(f"  ❌ HTTP {r.status_code}")
            return
        data = r.json()
    except Exception as e:
        print(f"  ❌ {e}")
        return

    total = data['data']['total']
    print(f"  北交所总计: {total} 家")

    all_stocks = []
    page_size = 100
    total_pages = (total + page_size - 1) // page_size

    for page in range(1, total_pages + 1):
        params['pn'] = str(page)
        params['pz'] = str(page_size)
        try:
            r = requests.get(url, params=params, headers=H, timeout=30)
            page_data = r.json()
            for item in page_data.get('data', {}).get('diff', []):
                code = str(item.get('f12', '')).strip()
                name = str(item.get('f14', '')).strip()
                if not code or not name:
                    continue
                all_stocks.append({
                    'code': f"bj.{code}",
                    'name': name,
                    'short_code': code,
                    'board': '北交所',
                    'market': '北交所',
                    'listing_date': str(item.get('f124', '') or ''),
                    'industry': str(item.get('f100', '') or ''),
                    'province': str(item.get('f102', '') or ''),
                    'city': str(item.get('f103', '') or ''),
                    'status': 'active',
                })
            if page % 5 == 0:
                print(f"  ... page {page}/{total_pages}")
            time.sleep(0.3)
        except Exception as e:
            print(f"  Page {page} error: {e}")
            time.sleep(1)

    print(f"  ✅ 北交所: {len(all_stocks)} stocks")

    cache_path = os.path.join(CACHE_DIR, 'bj_stocks.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(all_stocks, f, ensure_ascii=False)

    print(f"\n💾 已缓存至: {cache_path}")
    print(f"   总计: {len(all_stocks)} 家")
    print("\n💡 下一步: python3 import_bj_stocks.py")

if __name__ == '__main__':
    main()

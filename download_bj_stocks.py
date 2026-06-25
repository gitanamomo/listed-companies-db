# -*- coding: utf-8 -*-
"""
北交所股票下载器
用法: python3 download_bj_stocks.py
依赖: requests
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from download_stocks import fetch_eastmoney_page, HEADERS, classify_board_simple

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

import requests


def fetch_bj_stocks():
    """从东方财富拉取全部北交所股票"""
    print("📥 拉取北交所股票...")

    # First check total count
    data = fetch_eastmoney_page(1, 5)
    if not data or 'data' not in data:
        print("  ❌ 东方财富 API 不可用")
        return []

    # Use 北交所-specific market filter: m:0+t:81+s:2048
    # But fetch_eastmoney_page uses hardcoded fs. We need to query 北交所 specifically.
    # Let's use the clist endpoint directly with 北交所 params
    
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': '1', 'pz': '5',
        'po': '1', 'np': '1',
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': '2', 'invt': '2', 'fid': 'f12',
        'fs': 'm:0+t:81+s:2048',
        'fields': 'f12,f13,f14,f100,f102,f103,f124',
    }

    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    if r.status_code != 200:
        print(f"  HTTP {r.status_code}")
        return []

    data = r.json()
    if 'data' not in data or not data['data']:
        print("  No data")
        return []

    total = data['data']['total']
    print(f"  北交所总计: {total} 家")

    if total == 0:
        return []

    all_stocks = []
    page_size = 100
    total_pages = (total + page_size - 1) // page_size

    for page in range(1, total_pages + 1):
        params['pn'] = str(page)
        params['pz'] = str(page_size)
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            page_data = r.json()
            if page_data.get('data') and page_data['data'].get('diff'):
                for item in page_data['data']['diff']:
                    code = str(item.get('f12', '')).strip()
                    name = str(item.get('f14', '')).strip()
                    if not code or not name:
                        continue

                    all_stocks.append({
                        'code': f"bj.{code}",
                        'name': name,
                        'short_code': code,
                        'board': classify_board_simple(code),
                        'market': '北交所',
                        'listing_date': str(item.get('f124', '')) if item.get('f124') else '',
                        'industry': str(item.get('f100', '') or ''),
                        'province': str(item.get('f103', '') or ''),
                        'city': str(item.get('f102', '') or ''),
                        'status': 'active',
                    })

            if page % 5 == 0:
                print(f"  ... page {page}/{total_pages}")
            time.sleep(0.4)
        except Exception as e:
            print(f"  Page {page} error: {e}")
            time.sleep(2)

    print(f"  ✅ 北交所: {len(all_stocks)} stocks")
    return all_stocks


def main():
    print("=" * 60)
    print("📊 北交所上市公司数据下载")
    print("=" * 60)
    print()

    stocks = fetch_bj_stocks()
    if not stocks:
        print("\n❌ 下载失败，请检查网络连接")
        return

    # Save cache
    cache_path = os.path.join(CACHE_DIR, 'bj_stocks.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)

    print(f"\n💾 已缓存至: {cache_path}")
    print(f"   总计: {len(stocks)} 家")

    # Quick stats
    boards = {}
    for s in stocks:
        boards[s['board']] = boards.get(s['board'], 0) + 1
    print(f"   板块: {boards}")

    print("\n💡 下一步: python3 import_bj_stocks.py")


if __name__ == '__main__':
    main()

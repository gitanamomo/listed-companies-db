# -*- coding: utf-8 -*-
"""
全量A股下载器（深交所 + 东方财富 + 北交所）
- 下载全部A股基本数据（股票代码、名称、行业、板块、交易所、上市日期）
- 生成 .cache/baostock_all.json 供 import_all.py 使用
- 导出 fetch_eastmoney_page / HEADERS / classify_board_simple 供其他脚本调用
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import baostock as bs

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://quote.eastmoney.com/',
}


def classify_board_simple(code):
    """根据股票代码判断板块（无前缀纯数字版本）"""
    code = str(code).strip()
    if code.startswith('688') or code.startswith('689'):
        return '科创板'
    if code.startswith('300') or code.startswith('301'):
        return '创业板'
    if code.startswith('8') or code.startswith('4'):
        return '北交所'
    return '主板'


def fetch_eastmoney_page(page, page_size, market_filter=""):
    """从东方财富API拉取一页A股数据"""
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': str(page),
        'pz': str(page_size),
        'po': '1', 'np': '1',
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': '2', 'invt': '2', 'fid': 'f12',
        'fs': market_filter or 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
        'fields': 'f12,f13,f14,f100,f102,f103,f124,f128,f140',
    }
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  fetch_eastmoney_page error: {e}")
        return None


def download_baostock():
    """使用baostock下载全量A股基本信息，缓存到本地"""
    print("📥 下载全量A股 (baostock)...")
    bs.login()
    rs = bs.query_stock_basic()
    data_list = []
    while (rs.error_code == '0') and rs.next():
        data_list.append(rs.get_row_data())
    bs.logout()

    if not data_list:
        print("  ❌ baostock 无数据返回")
        return []

    stocks = []
    for row in data_list:
        code_raw = row[0].strip()
        name = row[1].strip()
        listing_date = row[2].strip()
        out_date = row[3].strip()
        stype = row[4].strip()

        # 跳过B股、指数、基金等
        if stype != '1':
            continue

        # 确定市场和板块
        if code_raw.startswith('sh'):
            market = '上交所'
            short = code_raw.replace('sh.', '')
        elif code_raw.startswith('sz'):
            market = '深交所'
            short = code_raw.replace('sz.', '')
        elif code_raw.startswith('bj'):
            market = '北交所'
            short = code_raw.replace('bj.', '')
        else:
            continue

        # 跳过退市超过1年且无代码的
        board = classify_board_simple(short)
        status = 'delisted' if out_date else 'active'

        stocks.append({
            'code': code_raw,
            'name': name,
            'short_code': short,
            'board': board,
            'market': market,
            'listing_date': listing_date,
            'out_date': out_date,
            'industry': '',
            'province': '',
            'city': '',
            'status': status,
        })

    # 缓存
    cache_path = os.path.join(CACHE_DIR, 'baostock_all.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False)

    active = [s for s in stocks if s['status'] == 'active']
    delisted = [s for s in stocks if s['status'] == 'delisted']
    print(f"  ✅ 总计: {len(stocks)}  (活跃: {len(active)}, 退市: {len(delisted)})")
    print(f"  💾 缓存: {cache_path}")
    return stocks


def enrich_from_eastmoney(stocks):
    """用东方财富数据补充行业和省市信息"""
    print("📥 补充行业/省市 (东方财富)...")
    url = 'https://push2.eastmoney.com/api/qt/clist/get'

    # 先获取总数
    data = fetch_eastmoney_page(1, 5)
    if not data or 'data' not in data or not data['data']:
        print("  ⚠️ 东方财富 API 不可用，跳过补充")
        return

    total = data['data']['total']
    page_size = 100
    total_pages = (total + page_size - 1) // page_size

    # 构建代码索引
    code_map = {}
    for s in stocks:
        code_map[s['short_code']] = s

    updated = 0
    for page in range(1, total_pages + 1):
        page_data = fetch_eastmoney_page(page, page_size)
        if not page_data or 'data' not in page_data:
            continue
        diff = page_data.get('data', {}).get('diff', [])
        if not diff:
            continue

        for item in diff:
            code = str(item.get('f12', '')).strip()
            if code in code_map:
                s = code_map[code]
                s['industry'] = str(item.get('f100', '') or '')
                s['province'] = str(item.get('f102', '') or '')
                s['city'] = str(item.get('f103', '') or '')
                updated += 1

        if page % 10 == 0:
            print(f"  ... page {page}/{total_pages}")
        time.sleep(0.3)

    print(f"  ✅ 补充了 {updated} 家公司信息")


def main():
    print("=" * 60)
    print("📊 全量A股上市公司数据下载")
    print("=" * 60)
    print()

    stocks = download_baostock()
    if not stocks:
        print("\n❌ 下载失败，请检查网络连接")
        return

    enrich_from_eastmoney(stocks)

    # 重新保存（含东方财富补充数据）
    cache_path = os.path.join(CACHE_DIR, 'baostock_all.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False)

    print(f"\n💾 最终缓存: {cache_path}")
    print(f"   总计: {len(stocks)} 家")
    active = [s for s in stocks if s['status'] == 'active']
    print(f"   活跃: {len(active)} 家")

    # 板块统计
    from collections import Counter
    board_cnt = Counter(s['board'] for s in active)
    print(f"   板块: {dict(board_cnt)}")

    print("\n💡 下一步: python3 import_all.py")


if __name__ == '__main__':
    main()

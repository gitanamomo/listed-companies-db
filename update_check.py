# -*- coding: utf-8 -*-
"""
月度更新脚本：检测新增/退市/变更
- 从东方财富获取最新A股列表
- 与数据库比对，识别新增和退市
- 支持 --apply 应用变更
- 记录 update_log / update_runs
"""
import os, sys, json, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from database import get_db

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://quote.eastmoney.com/',
}

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def normalize_code(code):
    """归一化股票代码，去掉交易所前缀"""
    return str(code).replace('sh.', '').replace('sz.', '').replace('bj.', '')


def get_tracked_codes():
    """获取数据库中所有活跃公司的代码（归一化）"""
    db = get_db()
    rows = db.execute("SELECT stock_code FROM companies WHERE status='active'").fetchall()
    db.close()
    return set(normalize_code(r[0]) for r in rows)


def fetch_current_stocks():
    """从东方财富获取当前A股列表（沪深北）"""
    print("📥 获取最新A股列表 (东方财富)...")

    all_stocks = []
    # 沪深A股
    fs_params = [
        ('m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23', '沪深A股'),
        ('m:0+t:81+s:2048', '北交所'),
    ]

    for fs, label in fs_params:
        print(f"  {label}...")
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': '1', 'pz': '20',
            'po': '1', 'np': '1',
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': '2', 'invt': '2', 'fid': 'f12',
            'fs': fs,
            'fields': 'f12,f14,f100,f102,f103,f124',
        }

        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            data = r.json()
            if not data.get('data'):
                continue

            total = data['data']['total']
            if total == 0:
                continue

            page_size = 100
            total_pages = (total + page_size - 1) // page_size

            for page in range(1, total_pages + 1):
                params['pn'] = str(page)
                params['pz'] = str(page_size)
                try:
                    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
                    page_data = r.json()
                    diff = page_data.get('data', {}).get('diff', [])
                    if diff:
                        for item in diff:
                            code = str(item.get('f12', '')).strip()
                            if not code:
                                continue

                            stock = {
                                'code': code,
                                'name': str(item.get('f14', '')),
                                'industry': str(item.get('f100', '') or ''),
                                'province': str(item.get('f102', '') or ''),
                                'city': str(item.get('f103', '') or ''),
                                'listing_date': str(item.get('f124', '') or ''),
                            }

                            # 确定市场
                            if code.startswith(('6', '5', '9')):
                                stock['market'] = '上交所'
                            elif code.startswith(('0', '2', '3')):
                                stock['market'] = '深交所'
                            elif code.startswith(('8', '4')):
                                stock['market'] = '北交所'

                            all_stocks.append(stock)

                    if page % 5 == 0:
                        print(f"    ... page {page}/{total_pages}")
                    time.sleep(0.3)
                except Exception as e:
                    print(f"    Page {page} error: {e}")
                    time.sleep(1)

        except Exception as e:
            print(f"  {label} error: {e}")

    # 去重（按code）
    seen = {}
    for s in all_stocks:
        seen[s['code']] = s
    all_stocks = list(seen.values())

    print(f"  ✅ 获取到 {len(all_stocks)} 只股票")
    return all_stocks


def check_for_changes(fetched):
    """比对新旧数据，检测新增和退市"""
    print("\n🔍 比对数据...")

    tracked_codes = get_tracked_codes()
    print(f"  数据库: {len(tracked_codes)} 家")

    fetched_codes = set()
    fetched_map = {}
    for c in fetched:
        code = normalize_code(c.get('code', ''))
        if code:
            fetched_codes.add(code)
            fetched_map[code] = c

    print(f"  当前市: {len(fetched_codes)} 家")

    # 新增 = 东方财富有，数据库没有
    new_codes = fetched_codes - tracked_codes
    # 退市 = 数据库有，东方财富没有
    delisted_codes = tracked_codes - fetched_codes

    new_listings = []
    for code in new_codes:
        c = fetched_map.get(code, {})
        new_listings.append({
            'code': code,
            'name': c.get('name', '?'),
            'city': c.get('city', ''),
            'province': c.get('province', ''),
            'industry': c.get('industry', ''),
            'listing_date': c.get('listing_date', ''),
        })

    # 获取退市公司的名称
    db = get_db()
    delisted_info = []
    for code in delisted_codes:
        # 尝试完整代码和短码匹配
        row = db.execute(
            "SELECT stock_name, city FROM companies WHERE stock_code=? OR stock_code=?",
            (code, code)
        ).fetchone()
        if row:
            delisted_info.append({'code': code, 'name': row['stock_name'], 'city': row['city']})
    db.close()

    changes = {
        'new_listings': new_listings,
        'delistings': delisted_info,
    }

    # 打印结果
    if new_listings:
        print(f"\n  🆕 新增 {len(new_listings)} 家:")
        for c in new_listings[:20]:
            print(f"     {c['code']} {c['name']} ({c.get('city', '?')})")

    if delisted_info:
        print(f"\n  👋 退市 {len(delisted_info)} 家:")
        for c in delisted_info[:20]:
            print(f"     {c['code']} {c['name']} ({c.get('city', '?')})")

    if not new_listings and not delisted_info:
        print("\n  ✅ 无变更，数据库与最新数据一致")

    return changes


def run_update(apply_changes=False):
    """主入口：获取最新数据并比对"""
    print("=" * 60)
    print("📊 月度更新检查")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    print()

    # 获取最新股票列表
    fetched = fetch_current_stocks()
    if not fetched:
        print("\n❌ 无法获取最新数据，请检查网络连接")
        return None

    # 比对变更
    changes = check_for_changes(fetched)

    # 应用变更
    if apply_changes and (changes['new_listings'] or changes['delistings']):
        db = get_db()
        now = datetime.now().isoformat()

        for c in changes['new_listings']:
            db.execute("""
                INSERT INTO companies (stock_code, stock_name, city, province, industry,
                                       listing_date, board, market, status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, '主板', '', 'active', CURRENT_TIMESTAMP)
            """, (c['code'], c['name'], c.get('city', ''),
                 c.get('province', ''), c.get('industry', ''),
                 c.get('listing_date', '')))

            db.execute("""
                INSERT INTO update_log (stock_code, stock_name, city, change_type,
                    change_detail, new_value, detected_at)
                VALUES (?, ?, ?, 'new_listing', '新上市公司', ?, ?)
            """, (c['code'], c['name'], c.get('city', ''),
                  json.dumps(c, ensure_ascii=False), now))

        for c in changes['delistings']:
            db.execute("UPDATE companies SET status='delisted', last_updated=CURRENT_TIMESTAMP WHERE stock_code=?",
                       (c['code'],))
            db.execute("""
                INSERT INTO update_log (stock_code, stock_name, city, change_type,
                    change_detail, old_value, detected_at)
                VALUES (?, ?, ?, 'delisting', '退市', ?, ?)
            """, (c['code'], c['name'], c.get('city', ''), c['name'], now))

        db.execute("""
            INSERT INTO update_runs (total_checked, new_listings, delistings, changes, run_at)
            VALUES (?, ?, ?, 0, ?)
        """, (len(fetched), len(changes['new_listings']), len(changes['delistings']), now))

        db.commit()
        db.close()
        print(f"\n✅ 变更已应用（新增 {len(changes['new_listings'])} 家，退市 {len(changes['delistings'])} 家）")

    elif not apply_changes and (changes['new_listings'] or changes['delistings']):
        print(f"\n💡 使用 --apply 确认并应用变更")

    print(f"\n{'='*60}")
    print(f"下次建议检查: {datetime.now().strftime('%Y-%m')}-15")
    print(f"{'='*60}")

    return changes


if __name__ == '__main__':
    apply = '--apply' in sys.argv or '-a' in sys.argv
    run_update(apply_changes=apply)

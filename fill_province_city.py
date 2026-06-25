# -*- coding: utf-8 -*-
"""
并发查询省市信息（akshare）
- 15线程并发查询公司省份/城市
- 覆盖广东、福建、湖南三省
- 更新 SQLite 数据库
"""
import os, sys, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import akshare as ak
from database import get_db

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listed_companies.db")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "province_city_cache.json")


def load_cache():
    """加载本地缓存"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """保存本地缓存"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def query_stock_info(code):
    """通过akshare查询单只股票的省份城市"""
    try:
        # 用 stock_individual_info_em 查询个股信息
        short = code.replace('sh.', '').replace('sz.', '').replace('bj.', '')
        df = ak.stock_individual_info_em(symbol=short)
        if df is None or df.empty:
            return None

        info = {}
        for _, row in df.iterrows():
            key = str(row['item']).strip()
            val = str(row['value']).strip() if row['value'] else ''
            if key == '省份':
                info['province'] = val
            elif key == '城市':
                info['city'] = val
            elif key == '注册地址':
                info['reg_address'] = val
        return info if info else None
    except Exception as e:
        return None


def fill_missing():
    """并发填充缺失的省市信息"""
    print("🔍 查询缺失省市信息的公司...")
    cache = load_cache()

    db = get_db()
    # 查询 province 或 city 为空的活跃公司
    rows = db.execute("""
        SELECT id, stock_code, stock_name
        FROM companies
        WHERE status='active'
          AND (province IS NULL OR province = '' OR city IS NULL OR city = '')
        ORDER BY stock_code
    """).fetchall()
    db.close()

    missing = [dict(r) for r in rows]
    print(f"  共 {len(missing)} 家公司缺省市信息")

    if not missing:
        print("  ✅ 所有公司省市信息完整")
        return

    # 过滤已缓存的
    to_query = []
    for comp in missing:
        code = comp['stock_code']
        if code in cache:
            continue
        to_query.append(comp)

    print(f"  需查询: {len(to_query)} 家 (已缓存: {len(missing) - len(to_query)})")

    if not to_query:
        # 只更新已缓存的
        update_from_cache(missing, cache)
        return

    # 15线程并发查询
    print(f"  🧵 15线程并发查询中...")
    success = 0
    fail = 0
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(query_stock_info, c['stock_code']): c for c in to_query}
        for i, future in enumerate(as_completed(futures)):
            comp = futures[future]
            try:
                result = future.result(timeout=15)
                if result:
                    cache[comp['stock_code']] = result
                    success += 1
                else:
                    fail += 1
            except Exception:
                fail += 1

            if (success + fail) % 50 == 0:
                print(f"    ... {success + fail}/{len(to_query)} (成功: {success})")

    print(f"  ✅ 查询完成: 成功 {success}, 失败 {fail}")

    # 保存缓存
    save_cache(cache)

    # 更新数据库
    update_from_cache(missing, cache)


def update_from_cache(missing_companies, cache):
    """将缓存中的省市信息写入数据库"""
    db = get_db()
    updated = 0

    for comp in missing_companies:
        code = comp['stock_code']
        info = cache.get(code)
        if not info:
            continue

        province = info.get('province', '') or ''
        city = info.get('city', '') or ''
        reg_addr = info.get('reg_address', '') or ''

        if not province and not city:
            continue

        db.execute("""
            UPDATE companies
            SET province = COALESCE(NULLIF(?, ''), province),
                city = COALESCE(NULLIF(?, ''), city),
                reg_address = COALESCE(NULLIF(?, ''), reg_address),
                last_updated = CURRENT_TIMESTAMP
            WHERE stock_code = ?
        """, (province, city, reg_addr, code))
        updated += 1

    db.commit()
    db.close()
    print(f"  ✅ 数据库更新: {updated} 家")


def main():
    print("=" * 60)
    print("📍 A股上市公司省市信息补充")
    print("=" * 60)
    print()
    fill_missing()
    print("\n💡 下一步: python3 refresh.py")


if __name__ == '__main__':
    fill_missing()

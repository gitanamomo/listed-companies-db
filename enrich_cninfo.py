# -*- coding: utf-8 -*-
"""
cninfo 数据补充：城市/省份 + 公司全称 + 官网 + 主营业务
- 10线程并发查询
- 从注册地址提取省份+城市
"""
import os, sys, json, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import akshare as ak
from database import get_db

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "cninfo_cache.json")
os.makedirs(CACHE_DIR, exist_ok=True)

PROVINCE_MAP = {
    '北京':'北京','上海':'上海','天津':'天津','重庆':'重庆',
    '广东':'广东','广西':'广西','浙江':'浙江','江苏':'江苏',
    '福建':'福建','山东':'山东','安徽':'安徽','江西':'江西',
    '湖南':'湖南','湖北':'湖北','河南':'河南','河北':'河北',
    '山西':'山西','陕西':'陕西','四川':'四川','贵州':'贵州',
    '云南':'云南','海南':'海南','辽宁':'辽宁','吉林':'吉林',
    '黑龙江':'黑龙江','甘肃':'甘肃','青海':'青海','西藏':'西藏',
    '宁夏':'宁夏','新疆':'新疆','内蒙古':'内蒙古',
}

def extract_location(addr):
    """从注册地址提取省份和城市"""
    if not addr:
        return '', ''
    province = ''
    city = ''
    for p, full in PROVINCE_MAP.items():
        if p in addr:
            province = full
            # Find city after province
            idx = addr.index(p)
            rest = addr[idx+len(p):]
            # Match city pattern: XX市 or XX自治州 etc
            m = re.search(r'([\u4e00-\u9fa5]{2,4}?(?:市|县|区|自治州|盟))', rest)
            if m:
                city = m.group(1)
            break
    # Special handling for 直辖市
    if province in ('北京','上海','天津','重庆'):
        city = province + '市'
    return province, city

def query_one(code):
    """查询单只股票的 cninfo 信息"""
    try:
        short = code.replace('sh.','').replace('sz.','').replace('bj.','')
        df = ak.stock_profile_cninfo(symbol=short)
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        addr = str(row.get('注册地址', '') or '')
        province, city = extract_location(addr)
        return {
            'full_name': str(row.get('公司名称', '') or ''),
            'reg_address': addr,
            'website': str(row.get('官方网站', '') or ''),
            'main_biz': str(row.get('主营业务', '') or ''),
            'province': province,
            'city': city,
        }
    except Exception as e:
        return None

def main():
    print("=" * 60)
    print("📥 cninfo 数据补充（省/市 + 全称 + 公司详情）")
    print("=" * 60)
    print()

    # Load cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)

    # Find companies missing city info
    db = get_db()
    rows = db.execute("""
        SELECT id, stock_code, stock_name
        FROM companies
        WHERE status='active' AND (city IS NULL OR city = '')
        ORDER BY stock_code
    """).fetchall()
    db.close()

    missing = [dict(r) for r in rows]
    print(f"  缺城市信息: {len(missing)} 家")

    # Filter by cache
    to_query = [c for c in missing if c['stock_code'] not in cache]
    print(f"  需查询: {len(to_query)} (已缓存: {len(missing) - len(to_query)})")

    if not to_query:
        print("  ✅ 无需查询")
        update_db(missing, cache)
        return

    # 10 thread concurrent
    success = 0
    fail = 0
    print(f"  🧵 10线程并发查询中...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(query_one, c['stock_code']): c for c in to_query}
        for i, future in enumerate(as_completed(futures)):
            comp = futures[future]
            try:
                result = future.result(timeout=30)
                if result and result.get('city'):
                    cache[comp['stock_code']] = result
                    success += 1
                else:
                    fail += 1
            except Exception:
                fail += 1

            if (success + fail) % 200 == 0:
                pct = (success + fail) * 100 // len(to_query)
                print(f"    ... {success + fail}/{len(to_query)} ({pct}%) 成功:{success}")
            import sys; sys.stdout.flush()

    print(f"  ✅ 查询完成: 成功 {success}, 失败 {fail}")

    # Save cache
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False)

    # Update DB
    update_db(missing, cache)


def update_db(missing, cache):
    """写入数据库"""
    db = get_db()
    updated = 0

    for comp in missing:
        code = comp['stock_code']
        info = cache.get(code)
        if not info:
            continue

        fields = {}
        if info.get('province'):
            fields['province'] = info['province']
        if info.get('city'):
            fields['city'] = info['city']
        if info.get('full_name'):
            fields['full_name'] = info['full_name']
        if info.get('website'):
            fields['website'] = info['website']
        if info.get('main_biz'):
            fields['main_biz'] = info['main_biz']
        if info.get('reg_address'):
            fields['reg_address'] = info['reg_address']

        if not fields:
            continue

        sets = ', '.join(f"{k}=?" for k in fields) + ', last_updated=CURRENT_TIMESTAMP'
        vals = list(fields.values()) + [code]

        db.execute(f"UPDATE companies SET {sets} WHERE stock_code=?", vals)
        updated += 1

        if updated % 500 == 0:
            db.commit()

    db.commit()
    db.close()
    print(f"  ✅ 数据库更新: {updated} 家")

    # Show stats
    db = get_db()
    with_city = db.execute("SELECT COUNT(*) FROM companies WHERE status='active' AND city IS NOT NULL AND city!=''").fetchone()[0]
    total = db.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0]
    db.close()
    print(f"  城市覆盖率: {with_city}/{total} ({with_city*100//total}%)")


if __name__ == '__main__':
    main()

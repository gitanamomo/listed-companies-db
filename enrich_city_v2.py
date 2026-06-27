# -*- coding: utf-8 -*-
"""
城市数据补全 V2 — 从 cninfo 注册地址提取省份/城市
- 增量存档，中断可续
- 每个公司查询后立即写入 JSON 缓存 + 数据库
"""
import functools
# Force unbuffered output
print_orig = print
print = functools.partial(print, flush=True)
import os, sys, json, time, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db
import akshare as ak

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'city_cache.json')

PROVINCES = ['北京','上海','天津','重庆','广东','广西','浙江','江苏','福建','山东',
    '安徽','江西','湖南','湖北','河南','河北','山西','陕西','四川','贵州','云南',
    '海南','辽宁','吉林','黑龙江','甘肃','青海','西藏','宁夏','新疆','内蒙古']

def extract_city_province(addr):
    """从注册地址提取省份和城市"""
    if not addr:
        return '', ''
    prov = ''
    city = ''
    for p in PROVINCES:
        if p in addr:
            prov = p
            idx = addr.index(p)
            rest = addr[idx + len(p):]
            # Match city: XX市, XX自治州, XX地区
            m = re.search(r'([\u4e00-\u9fa5]{2,4}?(?:市|自治州|地区|盟|新区))', rest)
            if m:
                c = m.group(1)
                # Filter out non-city patterns
                if '市' in c and len(c) <= 6:
                    city = c.replace('市', '')
            break
    if prov in ('北京','上海','天津','重庆'):
        city = prov
    return prov, city

def main():
    print("=" * 60)
    print("📍 城市数据补全 V2 (cninfo)")
    print("=" * 60)

    # Load cache
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE) as f:
            cache = json.load(f)
        print(f"\n  已有缓存: {len(cache)} 条")

    # Find companies needing city
    db = get_db()
    rows = db.execute("""
        SELECT stock_code, stock_name FROM companies
        WHERE status='active' AND (city IS NULL OR city = '')
        ORDER BY stock_code
    """).fetchall()
    db.close()
    
    missing = [(r['stock_code'], r['stock_name']) for r in rows if r['stock_code'] not in cache]
    print(f"  缺城市: {len(rows)} 家, 需查询: {len(missing)} 家\n")

    if not missing:
        print("  ✅ 全部已有城市数据")
        return

    total = len(missing)
    done = 0
    errors = 0

    for i, (code, name) in enumerate(missing):
        short = code.replace('sh.','').replace('sz.','').replace('bj.','')
        try:
            df = ak.stock_profile_cninfo(symbol=short)
            if df is not None and not df.empty:
                row = df.iloc[0]
                addr = str(row.get('注册地址','') or '')
                full_name = str(row.get('公司名称','') or '')
                website = str(row.get('官方网站','') or '')
                web_url = website if website and website != 'nan' else ''
                province, city = extract_city_province(addr)
                cache[code] = {
                    'province': province,
                    'city': city,
                    'full_name': full_name,
                    'website': web_url,
                    'reg_address': addr[:200]
                }
                if city:
                    done += 1
            else:
                errors += 1

        except Exception as e:
            errors += 1

        # Save cache every 50 records
        if (i + 1) % 50 == 0:
            import tempfile
            tmpf = tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(CACHE), delete=False, suffix='.json', encoding='utf-8')
            json.dump(cache, tmpf, ensure_ascii=False)
            tmpf.close()
            os.replace(tmpf.name, CACHE)
            pct = (i + 1) * 100 // total
            print(f"  ... {i+1}/{total} ({pct}%) city:{done} err:{errors}")

        time.sleep(1.8)  # Rate limit

    # Final save
    with open(CACHE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False)

    print(f"\n  ✅ 查询完成: city={done}, errors={errors}")

    # Update database
    print("\n📝 更新数据库...")
    db = get_db()
    updated = 0
    for code, info in cache.items():
        if not info.get('city') and not info.get('province'):
            continue
        sets = []
        vals = []
        for field in ['province','city','full_name','website','reg_address']:
            v = info.get(field, '')
            if v:
                sets.append(f"{field}=?")
                vals.append(v)
        if not sets:
            continue
        vals.append(code)
        sql = f"UPDATE companies SET {', '.join(sets)}, last_updated=CURRENT_TIMESTAMP WHERE stock_code=?"
        db.execute(sql, vals)
        updated += 1

    db.commit()
    with_city = db.execute("SELECT COUNT(*) FROM companies WHERE status='active' AND city IS NOT NULL AND city!=''").fetchone()[0]
    with_prov = db.execute("SELECT COUNT(*) FROM companies WHERE status='active' AND province IS NOT NULL AND province!=''").fetchone()[0]
    total_active = db.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0]
    db.close()

    print(f"\n{'='*50}")
    print(f"  活跃公司: {total_active:,}")
    print(f"  有城市: {with_city:,} ({with_city*100//max(total_active,1)}%)")
    print(f"  有省份: {with_prov:,} ({with_prov*100//max(total_active,1)}%)")
    print(f"{'='*50}")

if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
城市数据补全 V3 — 批量版，带超时保护
- 按市场分批：先查询上交所+深交所（跳过北交所）
- 每批 200 条，独立进程，增量保存
"""
import os, sys, json, time, re, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_db

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'city_cache.json')
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'city_enrich.log')

PROVINCES = ['北京','上海','天津','重庆','广东','广西','浙江','江苏','福建','山东',
    '安徽','江西','湖南','湖北','河南','河北','山西','陕西','四川','贵州','云南',
    '海南','辽宁','吉林','黑龙江','甘肃','青海','西藏','宁夏','新疆','内蒙古']

BATCH = 50
TIMEOUT = 8  # seconds per API call

def extract_city_province(addr):
    if not addr:
        return '', ''
    for p in PROVINCES:
        if p in addr:
            idx = addr.index(p)
            rest = addr[idx + len(p):]
            m = re.search(r'([\u4e00-\u9fa5]{2,4}?(?:市|自治州|地区|盟|新区))', rest)
            city = ''
            if m:
                c = m.group(1)
                if '市' in c and len(c) <= 6:
                    city = c.replace('市', '')
            if p in ('北京','上海','天津','重庆'):
                city = p
            return p, city
    return '', ''

def timeout_handler(signum, frame):
    raise TimeoutError("API timeout")

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def main():
    log("=" * 50)
    log("📍 城市数据补全 V3 (批量版)")

    # Load cache
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding='utf-8') as f:
            cache = json.load(f)
    log(f"  已有缓存: {len(cache)} 条")

    # Find companies needing city (skip 北交所)
    db = get_db()
    rows = db.execute("""
        SELECT stock_code, stock_name, market FROM companies
        WHERE status='active' AND (city IS NULL OR city = '')
        AND market != '北交所'
        ORDER BY stock_code
    """).fetchall()
    db.close()

    missing = [(r['stock_code'], r['stock_name'], r['market']) for r in rows if r['stock_code'] not in cache]
    total = len(missing)
    log(f"  缺城市(非北交所): {len(rows)} 家, 需查询: {total} 家")

    if not missing:
        log("  ✅ 全部已有城市数据")
        return

    # Process this batch
    batch = missing[:BATCH]
    log(f"  本批处理: {len(batch)} 家 (BATCH={BATCH})")

    # Lazy import akshare
    import akshare as ak
    signal.signal(signal.SIGALRM, timeout_handler)

    done = 0
    errors = 0
    timeouts = 0
    t0 = time.time()

    for i, (code, name, market) in enumerate(batch):
        short = code.replace('sh.','').replace('sz.','').replace('bj.','')
        try:
            signal.alarm(TIMEOUT)
            df = ak.stock_profile_cninfo(symbol=short)
            signal.alarm(0)

            if df is not None and not df.empty and len(df) > 0:
                row = df.iloc[0]
                addr = str(row.get('注册地址', '') or '')
                full_name = str(row.get('公司名称', '') or '')
                website = str(row.get('官方网站', '') or '')
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

        except TimeoutError:
            signal.alarm(0)
            timeouts += 1
            errors += 1
        except Exception as e:
            signal.alarm(0)
            errors += 1
            err_msg = str(e)[:80]
            if i < 5:
                log(f"  ERR#{i}: {short} {name} — {err_msg}")

        # Save cache every 20 records
        if (i + 1) % 20 == 0:
            import tempfile
            tmpf = tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(CACHE), delete=False, suffix='.json', encoding='utf-8')
            json.dump(cache, tmpf, ensure_ascii=False)
            tmpf.close()
            os.replace(tmpf.name, CACHE)
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            log(f"  {i+1}/{len(batch)} city:{done} err:{errors} t/o:{timeouts} {rate:.1f}/s")

        time.sleep(1.8)

    # Final save for this batch
    import tempfile
    tmpf = tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(CACHE), delete=False, suffix='.json', encoding='utf-8')
    json.dump(cache, tmpf, ensure_ascii=False)
    tmpf.close()
    os.replace(tmpf.name, CACHE)

    elapsed = time.time() - t0
    remaining = total - len(batch)
    log(f"  ✅ 本批完成: city={done} err={errors} t/o={timeouts} 耗时{elapsed:.0f}s")
    if remaining > 0:
        log(f"  ⏳ 剩余: {remaining} 家 (再次运行继续)")

if __name__ == '__main__':
    main()

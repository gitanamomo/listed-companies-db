#!/usr/bin/env python3
"""
F10 批量补充 Runner — 每次 20 条，独立进程，死循环直到跑完
用法: python3 enrich_f10_runner.py [循环次数，默认10]
"""
import os, sys, json, time, re, signal, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'f10_enrich.json')
from database import get_db

import requests
H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://emweb.securities.eastmoney.com/'}
API = 'https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax'

PROVINCES = ['北京','上海','天津','重庆','广东','广西','浙江','江苏','福建','山东',
    '安徽','江西','湖南','湖北','河南','河北','山西','陕西','四川','贵州','云南',
    '海南','辽宁','吉林','黑龙江','甘肃','青海','西藏','宁夏','新疆','内蒙古']

def extract_city(addr):
    if not addr: return ''
    for p in PROVINCES:
        if p in addr:
            rest = addr[addr.index(p) + len(p):]
            m = re.search(r'([\u4e00-\u9fa5]{2,4}?(?:市|自治州|地区|盟|新区))', rest)
            if m:
                c = m.group(1)
                if '市' in c and len(c) <= 6:
                    return c.replace('市', '')
            break
    return ''

def timeout_handler(signum, frame):
    raise TimeoutError("timeout")

signal.signal(signal.SIGALRM, timeout_handler)

BATCH = 20
TIMEOUT = 10

max_loops = int(sys.argv[1]) if len(sys.argv) > 1 else 10

for loop in range(max_loops):
    print(f"\n=== Loop {loop+1}/{max_loops} ===", flush=True)

    # Load cache
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding='utf-8') as f:
            cache = json.load(f)

    # Find missing
    db = get_db()
    rows = db.execute("""
        SELECT stock_code, stock_name, market FROM companies
        WHERE status='active' AND market != '北交所'
          AND (city IS NULL OR city = '' OR full_name IS NULL OR full_name = ''
               OR website IS NULL OR website = '' OR reg_address IS NULL OR reg_address = '')
        ORDER BY stock_code
    """).fetchall()
    db.close()

    need = [(r['stock_code'], r['stock_name'], r['market']) for r in rows if r['stock_code'] not in cache]
    batch = need[:BATCH]

    if not batch:
        print("✅ 全部完成！写入数据库...")
        # Apply all cache to DB
        db = get_db()
        for code, info in cache.items():
            up = {}
            if info.get('city'): up['city'] = info['city']
            if info.get('full_name'): up['full_name'] = info['full_name']
            w = info.get('website','')
            if w and w != '-' and w != '暂无': up['website'] = w
            if info.get('reg_address'): up['reg_address'] = info['reg_address']
            if info.get('province'): up['province'] = info['province']
            if not up: continue
            sets = ', '.join(f"{k}=?" for k in up)
            vals = list(up.values()) + [code]
            conds = ' OR '.join(f"({k} IS NULL OR {k}='')" for k in up)
            db.execute(f"UPDATE companies SET {sets}, last_updated=CURRENT_TIMESTAMP WHERE stock_code=? AND ({conds})", vals)
        db.commit()

        for f in ['city','full_name','website','reg_address']:
            cnt = db.execute(f"SELECT COUNT(*) FROM companies WHERE status='active' AND {f} IS NOT NULL AND {f}!=''").fetchone()[0]
            total = db.execute('SELECT COUNT(*) FROM companies WHERE status="active"').fetchone()[0]
            print(f"  {f}: {cnt}/{total} ({cnt*100//total}%)")
        db.close()
        break

    print(f"查询 {len(batch)} 家，缓存已有 {len(cache)}", flush=True)

    done_city = errs = 0
    t0 = time.time()

    for i, (code, name, market) in enumerate(batch):
        short = code.replace('sh.','').replace('sz.','').replace('bj.','')
        mkt = {'上交所':'SH','深交所':'SZ'}.get(market, 'SZ')
        sec = f'{mkt}{short}'

        try:
            signal.alarm(TIMEOUT)
            r = requests.get(API, params={'code': sec}, headers=H, timeout=TIMEOUT+3)
            signal.alarm(0)

            if r.status_code == 200:
                j = r.json().get('jbzl', {})
                if j:
                    addr = j.get('zcdz','') or j.get('bgdz','')
                    cache[code] = {
                        'province': j.get('qy',''),
                        'city': extract_city(addr),
                        'full_name': j.get('gsmc',''),
                        'website': j.get('gswz','') or '',
                        'reg_address': addr[:200],
                    }
                    if cache[code]['city']:
                        done_city += 1
                else:
                    errs += 1
            else:
                errs += 1
        except TimeoutError:
            signal.alarm(0); errs += 1
        except:
            signal.alarm(0); errs += 1

        time.sleep(0.3)

    # Apply cache to DB immediately
    db = get_db()
    for code2, info2 in cache.items():
        up = {}
        if info2.get('city'): up['city'] = info2['city']
        if info2.get('full_name'): up['full_name'] = info2['full_name']
        w = info2.get('website','')
        if w and w != '-' and w != '暂无': up['website'] = w
        if info2.get('reg_address'): up['reg_address'] = info2['reg_address']
        if info2.get('province'): up['province'] = info2['province']
        if not up: continue
        sets2 = ', '.join(f'{k}=?' for k in up)
        vals2 = list(up.values()) + [code2]
        conds2 = ' OR '.join(f'({k} IS NULL OR {k}="")' for k in up)
        db.execute(f'UPDATE companies SET {sets2}, last_updated=CURRENT_TIMESTAMP WHERE stock_code=? AND ({conds2})', vals2)
    db.commit()
    db.close()

    # Save
    import tempfile
    tmpf = tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(CACHE), delete=False, suffix='.json', encoding='utf-8')
    json.dump(cache, tmpf, ensure_ascii=False)
    tmpf.close()
    os.replace(tmpf.name, CACHE)

    elapsed = time.time() - t0
    print(f"  city:{done_city} err:{errs} {elapsed:.0f}s | 缓存总计:{len(cache)}", flush=True)

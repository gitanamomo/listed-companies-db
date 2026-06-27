#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
东方财富 F10 批量补充：城市、公司全称、官网、注册地址
- API: CompanySurveyAjax (一次请求拿全部)
- 跳过北交所 (cninfo / eastmoney 均无数据)
- 增量缓存，中断可续
- 每 20 条保存一次
"""
import os, sys, json, time, re, signal, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from database import get_db

CACHE    = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'f10_enrich.json')
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'f10_enrich.log')

H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://emweb.securities.eastmoney.com/'}
API  = 'https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax'
BATCH = 100
DELAY = 0.3
TIMEOUT_SEC = 12

PROVINCES = ['北京','上海','天津','重庆','广东','广西','浙江','江苏','福建','山东',
    '安徽','江西','湖南','湖北','河南','河北','山西','陕西','四川','贵州','云南',
    '海南','辽宁','吉林','黑龙江','甘肃','青海','西藏','宁夏','新疆','内蒙古']

DIRECT_CITIES = {'北京','上海','天津','重庆','深圳'}

# ── helpers ────────────────────────────────────────────

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + '\n')

def extract_city(addr):
    """从地址提取城市名（不带'市'后缀）"""
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
    raise TimeoutError("API timeout")

signal.signal(signal.SIGALRM, timeout_handler)

# ── main ───────────────────────────────────────────────

def main():
    global updated
    log("=" * 50)
    log("📋 F10 批量补充 V1")

    # Load cache
    cache = {}
    if os.path.exists(CACHE):
        with open(CACHE, encoding='utf-8') as f:
            cache = json.load(f)
    log(f"  缓存: {len(cache)} 条")

    # Load DB — find companies missing data (skip 北交所)
    db = get_db()
    rows = db.execute("""
        SELECT stock_code, stock_name, market FROM companies
        WHERE status='active'
          AND market != '北交所'
          AND (city IS NULL OR city = ''
               OR full_name IS NULL OR full_name = ''
               OR website IS NULL OR website = ''
               OR reg_address IS NULL OR reg_address = '')
        ORDER BY stock_code
    """).fetchall()
    db.close()

    all_missing = [(r['stock_code'], r['stock_name'], r['market']) for r in rows]
    need_query = [(c, n, m) for c, n, m in all_missing if c not in cache]
    total = len(need_query)
    log(f"  需查询: {total} 家 (已缓存 {len(all_missing)-total})")

    if total == 0:
        log("  ✅ 无需查询，全部已缓存")
        apply_to_db(cache)
        return

    # Process batch
    batch = need_query[:BATCH]
    log(f"  本批: {len(batch)} 家")

    done_city = 0
    errors = 0
    t0 = time.time()

    for i, (code, name, market) in enumerate(batch):
        short = code.replace('sh.','').replace('sz.','').replace('bj.','')
        mkt_prefix = {'上交所': 'SH', '深交所': 'SZ', '北交所': 'BJ'}.get(market, 'SZ')
        sec = f'{mkt_prefix}{short}'

        try:
            signal.alarm(TIMEOUT_SEC)
            r = requests.get(API, params={'code': sec}, headers=H, timeout=TIMEOUT_SEC+5)
            signal.alarm(0)

            if r.status_code == 200:
                jbzl = r.json().get('jbzl', {})
                if jbzl:
                    addr = jbzl.get('zcdz', '') or jbzl.get('bgdz', '')
                    city = extract_city(addr)
                    prov = jbzl.get('qy', '')  # province from API (more reliable)

                    cache[code] = {
                        'province': prov,
                        'city': city,
                        'full_name': jbzl.get('gsmc', ''),
                        'website': jbzl.get('gswz', '') or '',
                        'reg_address': addr[:200],
                    }
                    if city:
                        done_city += 1
                else:
                    errors += 1
            else:
                # 403 / rate limit
                if r.status_code == 403:
                    log(f"  ⚠️ 403 at #{i+1}, 暂停 5s")
                    time.sleep(5)
                errors += 1

        except TimeoutError:
            signal.alarm(0)
            errors += 1
        except Exception:
            signal.alarm(0)
            errors += 1

        # Save every 20
        if (i + 1) % 20 == 0:
            save_cache(cache)
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            log(f"  {i+1}/{len(batch)} city:{done_city} err:{errors} {rate:.1f}/s")

        time.sleep(DELAY)

    # Final save
    save_cache(cache)
    elapsed = time.time() - t0
    remaining = total - len(batch)
    log(f"  ✅ 本批: city={done_city} err={errors} 耗时{elapsed:.0f}s")
    if remaining > 0:
        log(f"  ⏳ 剩余: {remaining} 家 (再次运行继续)")

    # Apply to DB
    apply_to_db(cache)


def save_cache(cache):
    import tempfile
    tmpf = tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(CACHE),
                                       delete=False, suffix='.json', encoding='utf-8')
    json.dump(cache, tmpf, ensure_ascii=False)
    tmpf.close()
    os.replace(tmpf.name, CACHE)


def apply_to_db(cache):
    log("\n📝 写入数据库...")
    db = get_db()
    city_cnt = name_cnt = web_cnt = addr_cnt = 0

    for code, info in cache.items():
        updates = {}
        if info.get('city'):
            updates['city'] = info['city']
        if info.get('full_name'):
            updates['full_name'] = info['full_name']
        if info.get('website'):
            # Clean: skip placeholder values
            w = info['website']
            if w and w != '-' and w != '暂无':
                updates['website'] = w
        if info.get('reg_address'):
            updates['reg_address'] = info['reg_address']
        if info.get('province'):
            updates['province'] = info['province']

        if not updates:
            continue

        sets = ', '.join(f"{k}=?" for k in updates)
        vals = list(updates.values()) + [code]
        cond_parts = [f"({k} IS NULL OR {k}='')" for k in updates]
        where_cond = ' OR '.join(cond_parts)
        db.execute(
            f"UPDATE companies SET {sets}, last_updated=CURRENT_TIMESTAMP WHERE stock_code=? "
            f"AND ({where_cond})",
            vals
        )

        if 'city' in updates: city_cnt += 1
        if 'full_name' in updates: name_cnt += 1
        if 'website' in updates: web_cnt += 1
        if 'reg_address' in updates: addr_cnt += 1

    db.commit()

    # Final stats
    total = db.execute('SELECT COUNT(*) FROM companies WHERE status="active"').fetchone()[0]
    for field in ['city','full_name','website','reg_address']:
        cnt = db.execute(f'SELECT COUNT(*) FROM companies WHERE status="active" AND {field} IS NOT NULL AND {field}!=""').fetchone()[0]
        log(f"  {field}: {cnt}/{total} ({cnt*100//total}%)")

    db.close()
    log(f"  本次写入: city={city_cnt} full_name={name_cnt} website={web_cnt} reg_address={addr_cnt}")


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""Bank data enrichment downloader v2
Usage: python3 download_bank_data.py [--financials]"""
import sys, os, json, time, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings; warnings.filterwarnings('ignore')

BANK_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BANK_DIR)
DB_PATH = os.path.join(PARENT_DIR, 'listed_companies.db')
CACHE_FILE = os.path.join(BANK_DIR, '.cache', 'bank_details.json')

def q_cninfo(sc):
    try:
        import akshare as ak
        c = sc.replace('sh.','').replace('sz.','').replace('bj.','')
        df = ak.stock_profile_cninfo(symbol=c)
        if df is None or len(df)==0: return sc, {'_e':'no_data'}
        r = df.iloc[0]
        return sc, {
            'fn': str(r.get('company_name','') or r.get('公司中文名称','') or r.get('公司名称','') or ''),
            'oa': str(r.get('office_address','') or r.get('办公地址','') or ''),
            'ra': str(r.get('reg_address','') or r.get('注册地址','') or ''),
            'web': str(r.get('website','') or r.get('公司网址','') or r.get('网址','') or '')}
    except Exception as e: return sc, {'_e': type(e).__name__}

def q_fin(sc, nm):
    try:
        import akshare as ak
        c = sc.replace('sh.','').replace('sz.','').replace('bj.','')
        df = ak.stock_individual_info_em(symbol=c)
        r = {}
        if df is not None and len(df)>0:
            for _, row in df.iterrows():
                k, v = str(row.get('item','')), str(row.get('value',''))
                if '总市值' in k: r['mcap'] = v
                elif '总资产' in k: r['ta'] = v
                elif '净利润' in k: r['np'] = v
                elif '营业收入' in k: r['rev'] = v
                elif '员工' in k: r['emp'] = v
        return sc, r
    except Exception as e: return sc, {'_e': type(e).__name__}

def lb(): 
    with open(os.path.join(BANK_DIR, 'banks.json')) as f: return json.load(f)

def sb(b): 
    with open(os.path.join(BANK_DIR, 'banks.json'), 'w', encoding='utf-8') as f: 
        json.dump(b, f, ensure_ascii=False, indent=2)

def lc():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f: return json.load(f)
    return {'d':{}, 'f':{}}

def sv(d, f):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w', encoding='utf-8') as fh: 
        json.dump({'d':d, 'f':f}, fh, ensure_ascii=False, indent=2)

def gn(banks):
    nd, nf = [], []
    for b in banks:
        m = []
        if not b.get('full_name'): m.append('fn')
        if not b.get('hq_address'): m.append('addr')
        if not b.get('website'): m.append('web')
        if m: nd.append((b['stock_code'], b['stock_name'], m))
        f = b.get('financials_2025', {})
        if f.get('total_assets') is None: nf.append((b['stock_code'], b['stock_name']))
    return nd, nf

def apply(ch, fc=None):
    if fc is None: fc = {}
    banks = lb()
    conn = sqlite3.connect(DB_PATH)
    upd = {}
    for code, data in ch.items():
        if not data or '_e' in data: continue
        for col, key in [('full_name','fn'),('office_address','oa'),('website','web')]:
            val = data.get(key, '')
            if val:
                ex = conn.execute(f'SELECT {col} FROM companies WHERE stock_code=?',(code,)).fetchone()
                if ex and (not ex[0] or ex[0]==''):
                    conn.execute(f'UPDATE companies SET {col}=?,last_updated=CURRENT_TIMESTAMP WHERE stock_code=?',(val,code))
                    upd[col] = upd.get(col,0)+1
    conn.commit(); conn.close()
    for b in banks:
        c = b['stock_code']
        if c in ch and ch[c] and '_e' not in ch[c]:
            d = ch[c]
            if not b.get('full_name'): b['full_name'] = d.get('fn','')
            if not b.get('hq_address'): b['hq_address'] = d.get('oa','')
            if not b.get('website'): b['website'] = d.get('web','')
        if c in fc and fc[c] and '_e' not in fc[c]:
            if 'financials_2025' not in b: b['financials_2025'] = {}
            b['financials_2025'].update({k:v for k,v in fc[c].items() if not k.startswith('_')})
    sb(banks)
    p1 = sum(1 for b in banks if b.get('hq_address'))
    p2 = sum(1 for b in banks if b.get('full_name'))
    p3 = sum(1 for b in banks if b.get('financials_2025',{}).get('total_assets'))
    print(f'DB: {upd}')
    print(f'banks.json: addr {p1}/{len(banks)} name {p2}/{len(banks)} fin {p3}/{len(banks)}')

def main():
    rich = '--financials' in sys.argv or '-f' in sys.argv
    print('='*60)
    print('Bank Enrich v2')
    print('='*60)
    banks = lb()
    nd, nf = gn(banks)
    print()
    print(f'{len(banks)} banks | need details={len(nd)} | need fin={len(nf)}')
    if nd:
        print('Missing:')
        for _, name, m in nd[:12]: print(f'  {name}: {m}')
        if len(nd) > 12: print(f'  ... +{len(nd)-12} more')
    if (not nd) and (not nf or not rich):
        print()
        print('All complete!')
        return
    ch = lc()
    tqd = [(c,n,m) for c,n,m in nd if c not in ch['d']]
    tqf = [(c,n) for c,n in nf if c not in ch['f']] if rich else []
    print(f'Cache: d={len(nd)-len(tqd)} f={len(nf)-len(tqf)}')
    print(f'Query: d={len(tqd)} f={len(tqf)}')
    tq = len(tqd)+len(tqf)
    if tq==0: return apply(ch['d'], ch['f'])
    yn = input(f'{tq} API calls? (y/N): ').strip().lower()
    if yn!='y': return print('Cancelled')
    if tqd:
        print(f'[1/{2 if rich else 1}] Details...')
        w,t0=8,time.time()
        with ThreadPoolExecutor(max_workers=w) as ex:
            fs={ex.submit(q_cninfo,c):c for c,n,m in tqd}
            d=0
            for f in as_completed(fs):
                c,data=f.result();ch['d'][c]=data;d+=1
                if d%5==0: 
                    ok=sum(1 for v in ch['d'].values() if v and '_e' not in v)
                    print(f'  {d}/{len(tqd)} ok:{ok} {time.time()-t0:.0f}s')
        print(f'  Done {time.time()-t0:.0f}s')
    if tqf:
        print(f'[2/2] Financials...')
        w,t0=8,time.time()
        with ThreadPoolExecutor(max_workers=w) as ex:
            fs={ex.submit(q_fin,c,n):c for c,n in tqf}
            d=0
            for f in as_completed(fs):
                c,data=f.result();ch['f'][c]=data;d+=1
                if d%5==0:
                    ok=sum(1 for v in ch['f'].values() if v and '_e' not in v)
                    print(f'  {d}/{len(tqf)} ok:{ok} {time.time()-t0:.0f}s')
        print(f'  Done {time.time()-t0:.0f}s')
    sv(ch['d'],ch['f']);apply(ch['d'],ch['f'])
    print()
    print('Complete!')

if __name__=='__main__': main()

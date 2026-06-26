import json, time, requests, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
BASE = 'https://push2.eastmoney.com/api/qt/clist/get'
fs = 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23'
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.cache', 'eastmoney_city.json')

# Download
r = requests.get(BASE, params={'pn':'1','pz':'5','po':'1','np':'1','ut':'bd1d9ddb04089700cf9c27f6f7426281','fltt':'2','invt':'2','fid':'f12','fs':fs,'fields':'f12,f14,f102,f103'}, headers=H, timeout=30)
data = r.json()
total = data['data']['total']
print(f"Downloading {total} stocks...")

city_map = {}
province_map = {}
for page in range(1, (total + 99) // 100 + 1):
    try:
        r = requests.get(BASE, params={'pn':str(page),'pz':'100','po':'1','np':'1','ut':'bd1d9ddb04089700cf9c27f6f7426281','fltt':'2','invt':'2','fid':'f12','fs':fs,'fields':'f12,f14,f102,f103'}, headers=H, timeout=30)
        for item in r.json().get('data',{}).get('diff',[]):
            code = str(item.get('f12','')).strip()
            prov = str(item.get('f102','') or '').strip()
            cty = str(item.get('f103','') or '').strip()
            if code:
                if prov: province_map[code] = prov
                if cty: city_map[code] = cty
        if page % 10 == 0: print(f"  page {page}/{(total+99)//100}")
    except Exception as e:
        print(f"  Page {page}: {e}")
    time.sleep(0.2)

# Save
os.makedirs(os.path.dirname(CACHE), exist_ok=True)
with open(CACHE, 'w') as f:
    json.dump({'city': city_map, 'province': province_map}, f, ensure_ascii=False)
print(f"Saved: {len(city_map)} cities, {len(province_map)} provinces")

# Update DB
from database import get_db
db = get_db()

city_updated = 0
for code, cty in city_map.items():
    cur = db.execute("UPDATE companies SET city=?, last_updated=CURRENT_TIMESTAMP WHERE status='active' AND (city IS NULL OR city='') AND (stock_code LIKE ? OR stock_code = ?)", (cty, f'%.{code}', code))
    city_updated += cur.rowcount

prov_updated = 0
for code, prov in province_map.items():
    cur = db.execute("UPDATE companies SET province=?, last_updated=CURRENT_TIMESTAMP WHERE status='active' AND (province IS NULL OR province='') AND (stock_code LIKE ? OR stock_code = ?)", (prov, f'%.{code}', code))
    prov_updated += cur.rowcount

db.commit()

total = db.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0]
with_city = db.execute("SELECT COUNT(*) FROM companies WHERE status='active' AND city IS NOT NULL AND city!=''").fetchone()[0]
with_prov = db.execute("SELECT COUNT(*) FROM companies WHERE status='active' AND province IS NOT NULL AND province!=''").fetchone()[0]

# Show city distribution
cty_dist = db.execute("SELECT city, COUNT(*) as cnt FROM companies WHERE status='active' AND city!='' GROUP BY city ORDER BY cnt DESC LIMIT 15").fetchall()

db.close()

print(f"\n{'='*50}")
print(f"Active: {total:,}")
print(f"With city: {with_city:,} ({with_city*100//total}%)")
print(f"With province: {with_prov:,} ({with_prov*100//total}%)")
print(f"\nTop cities:")
for r in cty_dist:
    print(f"  {r['city']:10s} {r['cnt']:>5}")

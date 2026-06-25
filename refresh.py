# -*- coding: utf-8 -*-
"""
一键刷新脚本
运行后：更新数据库 → 导出JSON → 离线看板 → 精选看板V2 → 检索数据
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
origin = os.path.dirname(os.path.abspath(__file__))

from database import init_db, export_for_dashboard, get_stats


def refresh():
    print("🔄 刷新上市公司数据看板...")
    print()

    # Step 1: Init DB
    print("📦 Step 1/4: 初始化数据库...")
    init_db()

    # Step 2: Export dashboard data
    print("📤 Step 2/4: 导出看板数据...")
    json_path = export_for_dashboard()
    with open(json_path) as f:
        data = json.load(f)
    data_json = json.dumps(data, ensure_ascii=False)

    # Step 3: Generate offline dashboard
    print("🎨 Step 3/4: 生成离线看板...")
    tpath = os.path.join(origin, 'dashboard.html')
    if not os.path.exists(tpath):
        print('❌ 找不到看板模板')
    else:
        with open(tpath, 'r', encoding='utf-8') as f:
            html = f.read()
        inline = f'<script>const INLINE_DATA = {data_json};</script>'
        html = html.replace('</head>', f'{inline}\n</head>')
        old_load = """async function loadData() {\n  try {\n    const resp = await fetch('dashboard_data.json');\n    allData = await resp.json();\n    renderAll();\n  } catch(e) {\n    console.error('Failed to load data:', e);\n    if (typeof INLINE_DATA !== 'undefined') { allData = INLINE_DATA; renderAll(); }\n  }\n}"""
        new_load = """function loadData() {\n  if (typeof INLINE_DATA !== 'undefined') {\n    allData = INLINE_DATA;\n    renderAll();\n    return;\n  }\n  fetch('dashboard_data.json')\n    .then(r => r.json())\n    .then(d => { allData = d; renderAll(); })\n    .catch(e => console.error('Failed to load data:', e));\n}"""
        html = html.replace(old_load, new_load)
        with open('dashboard_offline.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("  ✅ dashboard_offline.html")

    # Generate search data
    print("🔍 生成检索数据...")
    lean = []
    for c in data['companies']:
        lean.append({
            'code': c.get('stock_code',''), 'name': c.get('stock_name',''),
            'industry': c.get('industry',''), 'city': c.get('city',''),
            'province': c.get('province',''), 'board': c.get('board',''),
            'market': c.get('market',''), 'date': c.get('listing_date',''),
            'match': c.get('match_type',''), 'wsw': c.get('wsw_match',''),
            'curated': c.get('is_curated',0),
        })
    with open('search_data.json', 'w') as f:
        json.dump(lean, f, ensure_ascii=False)
    print(f"  ✅ search_data.json: {len(lean):,} companies")

    # Step 4: Generate curated dashboard
    print("🎯 Step 4/4: 生成精选看板V2...")
    curated = [c for c in data['companies'] if c.get('is_curated')]
    banks = {}
    bp = os.path.join(origin, 'bank', 'banks.json')
    if os.path.exists(bp):
        with open(bp) as f:
            for b in json.load(f):
                sc = b.get('short_code','')
                if sc: banks[sc] = b
    for c in curated:
        short = c['stock_code'].replace('sh.','').replace('sz.','').replace('bj.','')
        bi = banks.get(short)
        c['is_bank'] = bool(bi)
        if bi:
            c['bank_type'] = bi.get('bank_type','')
            c['swift_code'] = bi.get('swift_code','')
            c['hq_city'] = bi.get('hq_city','')
    with open('curated_data.json', 'w') as f:
        json.dump(curated, f, ensure_ascii=False, default=str)
    print(f"  ✅ curated_data.json: {len(curated)} companies ({sum(1 for c in curated if c.get('is_bank'))} banks)")

    # Stats
    stats = get_stats()
    print()
    print("=" * 50)
    print("✅ 刷新完成！")
    print(f"   📊 活跃公司：{stats['total']:,} 家")
    boards = {b['board']: b['cnt'] for b in stats.get('by_board', [])}
    print(f"   🏢 板块分布：{boards}")
    markets = {m['market']: m['cnt'] for m in stats.get('by_market', [])}
    print(f"   🏛 交易所：{markets}")
    print()
    print("💡 双击 dashboard_offline.html — 全量离线看板")
    print("💡 双击 curated_dashboard.html — 7城精选看板")
    print("💡 双击 search_dashboard.html — 5,535家检索看板")
    print("=" * 50)


if __name__ == '__main__':
    refresh()

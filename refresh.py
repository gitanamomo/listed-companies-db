# -*- coding: utf-8 -*-
"""
一键刷新脚本
运行后：更新数据库 → 导出JSON → 生成离线看板
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, export_for_dashboard, get_stats


def refresh():
    """刷新所有数据"""
    print("🔄 刷新上市公司数据看板...")
    print()

    # Step 1: Ensure DB is initialized
    print("📦 Step 1/3: 初始化数据库...")
    init_db()

    # Step 2: Export dashboard data
    print("📤 Step 2/3: 导出看板数据...")
    json_path = export_for_dashboard()

    # Step 3: Generate offline dashboard
    print("🎨 Step 3/3: 生成离线看板...")

    # Load data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data_json = json.dumps(data, ensure_ascii=False)

    # Read dashboard template
    tpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard.html')
    if not os.path.exists(tpath):
        print('❌ 找不到看板模板')
        return
    with open(tpath, 'r', encoding='utf-8') as f:
        html = f.read()

    # Inject inline data
    inline = f'<script>const INLINE_DATA = {data_json};</script>'
    html = html.replace('</head>', f'{inline}\n</head>')

    # Patch loadData to prioritize inline data (for offline use)
    old_load = """async function loadData() {
  try {
    const resp = await fetch('dashboard_data.json');
    allData = await resp.json();
    renderAll();
  } catch(e) {
    console.error('Failed to load data:', e);
    if (typeof INLINE_DATA !== 'undefined') { allData = INLINE_DATA; renderAll(); }
  }
}"""

    new_load = """function loadData() {
  if (typeof INLINE_DATA !== 'undefined') {
    allData = INLINE_DATA;
    renderAll();
    return;
  }
  fetch('dashboard_data.json')
    .then(r => r.json())
    .then(d => { allData = d; renderAll(); })
    .catch(e => console.error('Failed to load data:', e));
}"""

    html = html.replace(old_load, new_load)

    with open('dashboard_offline.html', 'w', encoding='utf-8') as f:
        f.write(html)

    # Stats
    stats = get_stats()
    print()
    print("=" * 50)
    print("✅ 刷新完成！")
    print(f"   📊 活跃公司：{stats['total']} 家")
    boards = {b['board']: b['cnt'] for b in stats.get('by_board', [])}
    print(f"   🏢 板块分布：{boards}")
    markets = {m['market']: m['cnt'] for m in stats.get('by_market', [])}
    print(f"   🏛  交易所：{markets}")
    print(f"   🌆 覆盖城市：{len(stats['by_city'])} 个")
    print(f"   📁 离线看板：dashboard_offline.html")
    print(f"   📁 数据文件：dashboard_data.json")
    print(f"   📁 SQLite库：listed_companies.db")
    print()
    print("💡 双击 dashboard_offline.html 即可在浏览器中查看")
    print("=" * 50)


if __name__ == '__main__':
    refresh()

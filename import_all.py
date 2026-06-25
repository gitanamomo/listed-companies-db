# -*- coding: utf-8 -*-
"""
全量A股导入：合并baostock数据 + 行业信息 + 精选匹配 → SQLite
"""
import sys, os, json, re, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, export_for_dashboard, get_stats
import sqlite3

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def load_baostock_data():
    """Load cached baostock data"""
    fpath = os.path.join(CACHE_DIR, 'baostock_all.json')
    if not os.path.exists(fpath):
        print("❌ baostock_all.json not found. Run download_stocks.py first.")
        return None
    with open(fpath) as f:
        return json.load(f)


def load_szse_industry():
    """Extract industry info from SZSE cached page files"""
    industry_map = {}
    for fname in os.listdir(CACHE_DIR):
        m = re.search(r'szse_p(\d+)\.json', fname)
        if not m:
            continue
        fpath = os.path.join(CACHE_DIR, fname)
        try:
            with open(fpath) as f:
                data = json.load(f)
            for tab in data:
                if tab.get('metadata', {}).get('name') == 'A股列表':
                    for item in tab.get('data', []):
                        code = item.get('agdm', '').strip()
                        ind = item.get('sshymc', '').strip()
                        if code and ind and ind != '-':
                            industry_map[f'sz.{code}'] = ind
                    break
        except Exception:
            pass
    print(f"  SZSE industry map: {len(industry_map)} stocks")
    return industry_map


def backup_db():
    """Backup existing database"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listed_companies.db")
    if os.path.exists(db_path):
        import shutil
        backup = db_path + f'.backup_{int(time.time())}'
        shutil.copy2(db_path, backup)
        print(f"  Backed up to {os.path.basename(backup)}")


def main():
    print("=" * 60)
    print("📊 全量A股数据导入")
    print("=" * 60)
    print()

    # Load data
    print("Step 1/5: 加载数据源...")
    stocks = load_baostock_data()
    if not stocks:
        return
    print(f"  baostock: {len(stocks)} stocks")

    szse_industry = load_szse_industry()

    # Init DB
    print("\nStep 2/5: 初始化数据库...")
    backup_db()
    init_db()

    # Merge with existing curated data
    print("\nStep 3/5: 合并现有精选数据...")
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listed_companies.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Save existing curated data
    curated = {}
    existing_rows = conn.execute(
        "SELECT stock_code, wsw_match, match_type, is_curated, city, main_biz, website "
        "FROM companies WHERE wsw_match IS NOT NULL OR match_type IS NOT NULL OR is_curated=1"
    ).fetchall()
    for row in existing_rows:
        curated[row['stock_code']] = dict(row)
    print(f"  保留精选数据: {len(curated)} stocks")

    # Import
    print("\nStep 4/5: 导入数据库...")
    new_count = 0
    update_count = 0

    for s in stocks:
        code = s['code']
        name = s['name']
        board = s['board']
        market = s['market']
        listing_date = s.get('listing_date', '')
        industry = szse_industry.get(code, s.get('industry', ''))
        short_code = s.get('short_code', code.replace('sh.','').replace('sz.','').replace('bj.',''))

        # Check if exists (try both full and short code)
        existing = conn.execute(
            "SELECT id FROM companies WHERE stock_code=? OR stock_code=?",
            (code, short_code)
        ).fetchone()

        # Look up curated data by both code formats
        curated_data = curated.get(code) or curated.get(short_code, {})

        if existing:
            conn.execute("""
                UPDATE companies SET
                    stock_name=?, board=?, market=?, listing_date=?,
                    industry=COALESCE(NULLIF(?, ''), industry),
                    last_updated=CURRENT_TIMESTAMP
                WHERE stock_code=?
            """, (name, board, market, listing_date, industry, code))
            update_count += 1
        else:
            conn.execute("""
                INSERT INTO companies
                    (stock_code, stock_name, board, market, listing_date, industry,
                     city, status, wsw_match, match_type, is_curated,
                     main_biz, website, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?,
                        ?, ?, CURRENT_TIMESTAMP)
            """, (
                code, name, board, market, listing_date, industry,
                curated_data.get('city', ''),
                curated_data.get('wsw_match'),
                curated_data.get('match_type'),
                curated_data.get('is_curated', 0),
                curated_data.get('main_biz'),
                curated_data.get('website'),
            ))
            new_count += 1

        if (new_count + update_count) % 1000 == 0:
            print(f"  ... {new_count + update_count} processed")

    conn.commit()
    conn.close()
    print(f"  ✅ 新导入: {new_count}, 更新: {update_count}")

    # Export
    print("\nStep 5/5: 导出看板数据...")
    export_for_dashboard()

    # Stats
    stats = get_stats()
    print()
    print("=" * 60)
    print("✅ 导入完成！")
    print(f"   📊 活跃公司: {stats['total']} 家")
    print(f"   🏢 板 块: 主板 {stats.get('by_board', {})}")
    print(f"   🌆 城 市: {len(stats['by_city'])} 个")
    print(f"   🏭 行 业: {len(stats['by_industry'])} 个")
    print("=" * 60)


if __name__ == '__main__':
    main()

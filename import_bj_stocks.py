# -*- coding: utf-8 -*-
"""
导入北交所股票到数据库 + 更新看板
用法: python3 import_bj_stocks.py
前提: 已运行 download_bj_stocks.py 生成 .cache/bj_stocks.json
"""
import sys, os, json, time, sqlite3
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, export_for_dashboard, get_stats

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")


def backup_db():
    """备份数据库"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listed_companies.db")
    if os.path.exists(db_path):
        import shutil
        backup = db_path + f'.backup_{int(time.time())}'
        shutil.copy2(db_path, backup)
        print(f"  💾 已备份: {os.path.basename(backup)}")


def load_bj_data():
    """加载缓存的北交所数据"""
    fpath = os.path.join(CACHE_DIR, 'bj_stocks.json')
    if not os.path.exists(fpath):
        print("❌ bj_stocks.json 不存在，请先运行 download_bj_stocks.py")
        return None
    with open(fpath) as f:
        return json.load(f)


def import_to_db(stocks):
    """导入北交所股票到数据库"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listed_companies.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    new_count = 0
    update_count = 0
    skip_count = 0

    for s in stocks:
        code = s['code']
        name = s['name']
        board = s['board']
        market = s['market']
        listing_date = s.get('listing_date', '')
        industry = s.get('industry', '')
        province = s.get('province', '')
        city = s.get('city', '')

        # Check if exists
        existing = conn.execute(
            "SELECT id FROM companies WHERE stock_code=? OR stock_code=?",
            (code, s.get('short_code', ''))
        ).fetchone()

        if existing:
            conn.execute("""
                UPDATE companies SET
                    stock_name=?, board=?, market=?, listing_date=?,
                    industry=COALESCE(NULLIF(?, ''), industry),
                    province=COALESCE(NULLIF(?, ''), province),
                    city=COALESCE(NULLIF(?, ''), city),
                    last_updated=CURRENT_TIMESTAMP
                WHERE stock_code=?
            """, (name, board, market, listing_date, industry, province, city, code))
            update_count += 1
        else:
            conn.execute("""
                INSERT INTO companies
                    (stock_code, stock_name, board, market, listing_date,
                     industry, province, city, status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
            """, (code, name, board, market, listing_date, industry, province, city))
            new_count += 1

    conn.commit()
    conn.close()

    print(f"  🆕 新增: {new_count}, 📝 更新: {update_count}, ⏭  跳过: {skip_count}")
    return new_count, update_count


def main():
    print("=" * 60)
    print("📊 北交所数据导入")
    print("=" * 60)
    print()

    # Load data
    print("Step 1/4: 加载数据...")
    stocks = load_bj_data()
    if not stocks:
        return
    print(f"  北交所: {len(stocks)} 家")

    # Init DB
    print("\nStep 2/4: 初始化数据库...")
    backup_db()
    init_db()

    # Import
    print("\nStep 3/4: 导入数据库...")
    new, upd = import_to_db(stocks)

    # Export
    print("\nStep 4/4: 导出看板...")
    export_for_dashboard()

    # Final stats
    stats = get_stats()
    boards = {b['board']: b['cnt'] for b in stats.get('by_board', [])}
    markets = {m['market']: m['cnt'] for m in stats.get('by_market', [])}

    print()
    print("=" * 60)
    print("✅ 导入完成！")
    print(f"   📊 活跃公司: {stats['total']} 家")
    print(f"   🏢 板块分布: {boards}")
    print(f"   🏛  交易所: {markets}")
    print(f"   🌆 覆盖城市: {len(stats['by_city'])} 个")
    print("=" * 60)
    print()
    print("💡 下一步可选:")
    print("   python3 refresh.py       # 刷新离线看板")
    print("   python3 fill_province_city.py  # 补充省市信息")


if __name__ == '__main__':
    main()

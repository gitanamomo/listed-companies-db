# -*- coding: utf-8 -*-
"""
上市公司数据库管理模块
- SQLite数据库建表、导入、查询、更新
- 变更日志记录
"""
import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "listed_companies.db")


def get_db():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrate_schema():
    """迁移/扩展数据库表结构，添加新字段"""
    conn = get_db()
    existing = [r[1] for r in conn.execute("PRAGMA table_info(companies)").fetchall()]
    migrations = [
        ("province", "VARCHAR(20)", ""),
        ("market", "VARCHAR(10)", ""),
        ("out_date", "DATE", ""),
        ("is_curated", "BOOLEAN DEFAULT 0", "0"),
    ]
    for col, ctype, default in migrations:
        if col not in existing:
            try:
                conn.execute(f"ALTER TABLE companies ADD COLUMN {col} {ctype}")
                if default:
                    conn.execute(f"UPDATE companies SET {col} = {default}")
            except Exception as e:
                print(f"  Migration {col}: {e}")

    conn.commit()
    conn.close()
    print("Schema migration complete")


def init_db():
    """初始化数据库表结构 + 自动迁移"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code VARCHAR(20) NOT NULL,
            stock_name VARCHAR(100) NOT NULL,
            full_name VARCHAR(200),
            main_biz TEXT,
            website VARCHAR(200),
            reg_address TEXT,
            office_address TEXT,
            industry VARCHAR(50),
            province VARCHAR(20),
            city VARCHAR(20) NOT NULL,
            market VARCHAR(10),
            board VARCHAR(20),
            listing_date DATE,
            out_date DATE,
            wsw_match TEXT,
            match_type VARCHAR(20),
            is_curated BOOLEAN DEFAULT 0,
            status VARCHAR(20) DEFAULT 'active',
            first_seen DATE DEFAULT CURRENT_DATE,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(stock_code)
        );

        CREATE TABLE IF NOT EXISTS update_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_code VARCHAR(20),
            stock_name VARCHAR(100),
            city VARCHAR(20),
            change_type VARCHAR(30) NOT NULL,
            change_detail TEXT,
            old_value TEXT,
            new_value TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed BOOLEAN DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS update_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_checked INTEGER,
            new_listings INTEGER DEFAULT 0,
            delistings INTEGER DEFAULT 0,
            changes INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'success',
            error_msg TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_companies_city ON companies(city);
        CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
        CREATE INDEX IF NOT EXISTS idx_companies_industry ON companies(industry);
        CREATE INDEX IF NOT EXISTS idx_companies_board ON companies(board);
        CREATE INDEX IF NOT EXISTS idx_update_log_detected ON update_log(detected_at);
    """)
    conn.commit()
    conn.close()

    # Run migration for existing databases
    migrate_schema()

    # Add indexes that depend on migrated columns
    conn = get_db()
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_companies_province ON companies(province)")
    except:
        pass
    conn.commit()
    conn.close()

    print("数据库初始化完成")


def import_companies(companies_data, city):
    """批量导入公司数据（UPSERT，避免覆盖已有字段）"""
    conn = get_db()
    inserted = 0
    updated = 0
    for comp in companies_data:
        code, name, biz, web, addr, industry, match, mtype = comp
        # Determine board from code
        if code.startswith('688'):
            board = '科创板'
        elif code.startswith('300') or code.startswith('301'):
            board = '创业板'
        elif code.startswith('8') or code.startswith('4'):
            board = '北交所'
        else:
            board = '主板'

        try:
                conn.execute("""
                    INSERT INTO companies
                        (stock_code, stock_name, main_biz, website, reg_address,
                         industry, city, board, wsw_match, match_type,
                         status, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
                    ON CONFLICT(stock_code) DO UPDATE SET
                        stock_name=excluded.stock_name, main_biz=excluded.main_biz,
                        website=excluded.website, reg_address=excluded.reg_address,
                        industry=excluded.industry, city=excluded.city,
                        board=excluded.board, wsw_match=excluded.wsw_match,
                        match_type=excluded.match_type, status='active',
                        last_updated=CURRENT_TIMESTAMP
                """, (code, name, biz, web, addr, industry, city, board, match, mtype))
                inserted += 1
        except Exception as e:
                print(f"Error importing {code} {name}: {e}")

    conn.commit()
    conn.close()
    return inserted


def import_all_stocks(stocks_data):
    """批量导入全量A股数据（stock_code, stock_name, industry, board, market, listing_date, out_date）"""
    conn = get_db()
    new_count = 0
    update_count = 0
    delisted_count = 0

    for row in stocks_data:
        code, name, industry, board, market, listing_date, out_date = row

        # Determine status
        status = 'delisted' if out_date else 'active'

        try:
            existing = conn.execute(
                "SELECT id, wsw_match, match_type, is_curated FROM companies WHERE stock_code=?",
                (code,)
            ).fetchone()

            if existing:
                # Update existing: refresh name, industry, board, market, listing_date
                # but preserve curated fields
                conn.execute("""
                    UPDATE companies SET
                        stock_name=?, industry=COALESCE(NULLIF(?, ''), industry),
                        board=?, market=?, listing_date=?, out_date=?,
                        status=?, last_updated=CURRENT_TIMESTAMP
                    WHERE stock_code=?
                """, (name, industry, board, market, listing_date, out_date, status, code))
                update_count += 1
            else:
                conn.execute("""
                    INSERT INTO companies
                        (stock_code, stock_name, industry, board, market,
                         listing_date, out_date, city, status, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, CURRENT_TIMESTAMP)
                """, (code, name, industry, board, market, listing_date, out_date, status))
                new_count += 1

                if status == 'delisted':
                    delisted_count += 1

        except Exception as e:
            print(f"  Error importing {code} {name}: {e}")

    conn.commit()
    conn.close()
    print(f"  New: {new_count}, Updated: {update_count}, Delisted: {delisted_count}")
    return new_count, update_count


def get_stats():
    """获取统计概览"""
    conn = get_db()
    stats = {}

    # Total companies
    stats['total'] = conn.execute("SELECT COUNT(*) FROM companies WHERE status='active'").fetchone()[0]

    # By city
    rows = conn.execute("""
        SELECT city, COUNT(*) as cnt,
               SUM(CASE WHEN match_type='具体对标' THEN 1 ELSE 0 END) as specific,
               SUM(CASE WHEN match_type='方向匹配' THEN 1 ELSE 0 END) as direction
        FROM companies WHERE status='active' AND city != ''
        GROUP BY city ORDER BY cnt DESC
    """).fetchall()
    stats['by_city'] = [dict(r) for r in rows]

    # By board
    rows = conn.execute("""
        SELECT board, COUNT(*) as cnt FROM companies WHERE status='active'
        GROUP BY board ORDER BY cnt DESC
    """).fetchall()
    stats['by_board'] = [dict(r) for r in rows]

    # By market
    rows = conn.execute("""
        SELECT market, COUNT(*) as cnt FROM companies WHERE status='active'
        GROUP BY market ORDER BY cnt DESC
    """).fetchall()
    stats['by_market'] = [dict(r) for r in rows]

    # By industry
    rows = conn.execute("""
        SELECT industry, COUNT(*) as cnt FROM companies WHERE status='active' AND industry != ''
        GROUP BY industry ORDER BY cnt DESC LIMIT 30
    """).fetchall()
    stats['by_industry'] = [dict(r) for r in rows]

    # By match type
    rows = conn.execute("""
        SELECT match_type, COUNT(*) as cnt FROM companies WHERE status='active'
        GROUP BY match_type
    """).fetchall()
    stats['by_match'] = [dict(r) for r in rows]

    # Recent changes (last 30 days)
    rows = conn.execute("""
        SELECT * FROM update_log
        WHERE detected_at >= date('now', '-30 days')
        ORDER BY detected_at DESC LIMIT 20
    """).fetchall()
    stats['recent_changes'] = [dict(r) for r in rows]

    # Last update run
    row = conn.execute("SELECT * FROM update_runs ORDER BY run_at DESC LIMIT 1").fetchone()
    stats['last_update'] = dict(row) if row else None

    conn.close()
    return stats


def get_all_companies():
    """获取所有活跃公司数据"""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM companies WHERE status='active'
        ORDER BY city, industry, stock_code
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_for_dashboard():
    """导出JSON数据供看板使用"""
    data = {
        'stats': get_stats(),
        'companies': get_all_companies(),
        'exported_at': datetime.now().isoformat(),
    }

    # Convert date objects to strings
    for comp in data['companies']:
        for k, v in comp.items():
            if isinstance(v, datetime) or hasattr(v, 'isoformat'):
                try:
                    comp[k] = v.isoformat() if v else None
                except:
                    pass

    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_data.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Dashboard data exported to {json_path}")
    return json_path


if __name__ == '__main__':
    init_db()
    print("Database ready.")

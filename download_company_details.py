# -*- coding: utf-8 -*-
"""
补充公司详细信息：全称、办公地址、官网、网站
===========================================
用法：python3 download_company_details.py
依赖：akshare
数据源：akshare stock_profile_cninfo（cninfo 巨潮资讯网）
目标：193 家精选公司（当前仅深圳39家有完整数据）

运行后自动：
1. 查询 cninfo 获取公司详情
2. 解析中文全称、注册地址、办公地址、网站
3. 更新 listed_companies.db
4. 重新导出 curated_dashboard.html
"""
import sys, os, json, time, re, sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import warnings; warnings.filterwarnings('ignore')

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(PROJECT_DIR, '.cache', 'company_details_cache.json')


def query_cninfo(stock_code):
    """查询cninfo获取公司详细信息"""
    try:
        import akshare as ak
        clean = stock_code.replace('sh.', '').replace('sz.', '').replace('bj.', '')
        df = ak.stock_profile_cninfo(symbol=clean)
        if df is None or len(df) == 0:
            return stock_code, None
        
        row = df.iloc[0]
        return stock_code, {
            'full_name': str(row.get('公司中文名称', '') or row.get('公司名称', '') or ''),
            'reg_address': str(row.get('注册地址', '') or ''),
            'office_address': str(row.get('办公地址', '') or ''),
            'website': str(row.get('公司网址', '') or row.get('网址', '') or ''),
            'main_biz': str(row.get('主营业务', '') or ''),
            'legal_rep': str(row.get('法人代表', '') or ''),
            'postal_code': str(row.get('邮编', '') or ''),
            'telephone': str(row.get('电话', '') or ''),
        }
    except Exception as e:
        print(f"    {stock_code} query error: {type(e).__name__}")
        return stock_code, None


def get_missing_companies():
    """获取缺少详细信息的精选公司"""
    conn = sqlite3.connect(os.path.join(PROJECT_DIR, 'listed_companies.db'))
    conn.row_factory = sqlite3.Row
    
    # Companies that need details (prioritize curated, then all)
    rows = conn.execute("""
        SELECT stock_code, stock_name, full_name, office_address, website, main_biz
        FROM companies 
        WHERE status='active' AND is_curated=1
        ORDER BY province, city
    """).fetchall()
    conn.close()
    
    to_update = []
    has_full = 0
    has_office = 0
    
    for r in rows:
        need_full = not r['full_name']
        need_office = not r['office_address']
        need_web = not r['website']
        need_biz = not r['main_biz']
        
        if need_full or need_office or need_web or need_biz:
            to_update.append((r['stock_code'], r['stock_name']))
        else:
            if r['full_name']: has_full += 1
            if r['office_address']: has_office += 1
    
    print(f"精选公司 {len(rows)} 家:")
    print(f"  已有全称:    {has_full}/{len(rows)}")
    print(f"  已有办公地址: {has_office}/{len(rows)}")
    print(f"  需查询:      {len(to_update)} 家")
    return to_update


def load_cache():
    """加载本地缓存"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """保存本地缓存"""
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def update_database(updates):
    """将查询结果写入数据库"""
    conn = sqlite3.connect(os.path.join(PROJECT_DIR, 'listed_companies.db'))
    
    updated_fields = {'full_name': 0, 'office_address': 0, 'website': 0, 'main_biz': 0}
    
    for code, data in updates.items():
        if not data:
            continue
        
        fields = []
        values = []
        
        for col in ['full_name', 'office_address', 'website', 'main_biz']:
            val = data.get(col, '')
            if val:
                # Check if DB already has this value
                existing = conn.execute(
                    f"SELECT {col} FROM companies WHERE stock_code=?", (code,)
                ).fetchone()
                if existing and (not existing[0] or existing[0] == ''):
                    fields.append(f"{col}=?")
                    values.append(val)
                    updated_fields[col] += 1
        
        if fields:
            fields.append("last_updated=CURRENT_TIMESTAMP")
            values.append(code)
            sql = f"UPDATE companies SET {', '.join(fields)} WHERE stock_code=?"
            conn.execute(sql, values)
    
    conn.commit()
    conn.close()
    
    print(f"\n数据库更新:")
    for f, cnt in updated_fields.items():
        print(f"  {f}: +{cnt}")


def main():
    print("=" * 60)
    print("📋 补充公司详细信息")
    print("=" * 60)
    print()
    
    to_update = get_missing_companies()
    if not to_update:
        print("✅ 所有精选公司已有完整信息！")
        return
    
    if input(f"\n确认查询 {len(to_update)} 家公司？(y/N): ").strip().lower() != 'y':
        print("已取消")
        return
    
    # Load cache
    cache = load_cache()
    to_query = [(c, n) for c, n in to_update if c not in cache]
    print(f"  缓存命中: {len(to_update) - len(to_query)}, 需查询: {len(to_query)}")
    
    if not to_query:
        print("✅ 所有数据已在缓存中")
        update_database(cache)
        return
    
    # Parallel query
    workers = 10
    start = time.time()
    print(f"\n开始查询（{workers}线程）...")
    print("-" * 60)
    
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(query_cninfo, c): c for c, n in to_query}
        done = 0
        for future in as_completed(futures):
            code, data = future.result()
            cache[code] = data
            done += 1
            if done % 20 == 0:
                elapsed = time.time() - start
                found = sum(1 for v in cache.values() if v)
                print(f"  {done}/{len(to_query)} | 有效: {found} | {elapsed:.0f}s")
    
    # Save cache
    save_cache(cache)
    
    elapsed = time.time() - start
    found = sum(1 for v in cache.values() if v is not None)
    print(f"\n📊 查询完成: {found}/{len(to_query)} 有效 | {elapsed:.0f}s")
    
    # Update database
    update_database(cache)
    
    # Re-export dashboard
    print("\n📤 重新导出看板...")
    import subprocess
    subprocess.run([sys.executable, 'export_curated_dashboard.py'], cwd=PROJECT_DIR)
    
    print("\n✅ 完成！双击 curated_dashboard.html 查看更新后的看板")


if __name__ == '__main__':
    main()

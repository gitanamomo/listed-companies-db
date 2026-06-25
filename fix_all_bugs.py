#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

DIR = os.path.dirname(os.path.abspath(__file__))

def patch(fn, old, new, desc):
    fp = os.path.join(DIR, fn)
    with open(fp, 'r', encoding='utf-8') as f:
        c = f.read()
    if old not in c:
        print(f'⚠️  {fn}: {desc} — 未匹配')
        return
    c = c.replace(old, new)
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(c)
    print(f'✅ {fn}: {desc}')

def main():
    print('=' * 60)
    print('🔧 上市公司数据项目一键修复')
    print('=' * 60)

    patch('database.py', 
        '''    listing_date = None  # Will be populated by update script

        try:
            conn.execute("""
                INSERT OR REPLACE INTO companies
                    (stock_code, stock_name, main_biz, website, reg_address, industry, city, board,
                     listing_date, wsw_match, match_type, status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', CURRENT_TIMESTAMP)
            """, (code, name, biz, web, addr, industry, city, board, listing_date, match, mtype))''',
        '''        try:
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
            """, (code, name, biz, web, addr, industry, city, board, match, mtype))''',
        'P0-2: INSERT OR REPLACE → UPSERT')

    patch('update_check.py',
        '    return set(r[0] for r in rows)',
        '    return set(normalize_code(r[0]) for r in rows)',
        'P0-3: get_tracked_codes 归一化')

    patch('update_check.py',
        'def get_tracked_codes():',
        '''def normalize_code(code):
    return str(code).replace('sh.','').replace('sz.','').replace('bj.','')

def get_tracked_codes():''',
        'P0-3: 添加 normalize_code()')

    patch('update_check.py',
        '''    fetched_codes = set()
    fetched_map = {}
    for c in fetched_companies:
        code = c.get('code', '')
        if code:
            fetched_codes.add(code)
            fetched_map[code] = c''',
        '''    fetched_codes = set()
    fetched_map = {}
    for c in fetched_companies:
        code = normalize_code(c.get('code', ''))
        if code:
            fetched_codes.add(code)
            fetched_map[code] = c''',
        'P0-3: check_for_changes 归一化')

    fp = os.path.join(DIR, 'build_final_excel.py')
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    for code, name in [('688036', '传音控股'), ('300681', '英搏尔')]:
        if content.count(f'"{code}"') > 1:
            first = content.find(f'"{code}"')
            second = content.find(f'"{code}"', first + 20)
            if second > 0:
                ls = content.rfind('\n', 0, second)
                le = content.find('\n', second)
                if ls > 0 and le > ls:
                    content = content[:ls] + content[le:]
                    print(f'✅ build_final_excel.py: 删除 {name}({code}) 重复')
    with open(fp, 'w', encoding='utf-8') as f:
        f.write(content)

    patch('import_all.py', '        except:\n            pass',
          '        except Exception:\n            pass',
          'P2: bare except 修复')

    patch('refresh.py',
        "    with open('dashboard.html', 'r', encoding='utf-8') as f:\n        html = f.read()",
        '''    tpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dashboard.html')
    if not os.path.exists(tpath):
        print('❌ 找不到看板模板')
        return
    with open(tpath, 'r', encoding='utf-8') as f:
        html = f.read()''',
        'P2: refresh.py 文件检查')

    patch('import_data.py',
        "sys.path.insert(0, '/Volumes/Gina2T/项目开发/TRAE/上市公司数据')",
        "sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))",
        'P2: import_data.py 硬编码路径')

    patch('build_final_excel.py',
        'output_path = "/Volumes/Gina2T/项目开发/TRAE/上市公司数据/7城上市公司精选_十五五匹配.xlsx"',
        'output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "7城上市公司精选_十五五匹配.xlsx")',
        'P2: build_final_excel.py 硬编码路径')

    for fn, c in [('requirements.txt', 'baostock>=0.9.2\nakshare>=1.18.0\nopenpyxl>=3.1.0\nrequests>=2.28.0\npandas>=2.0.0\n'),
                  ('.gitignore', '*.db\n*.db.backup_*\n.cache/\n__pycache__/\n*.pyc\ndashboard_data.json\ndashboard_offline.html\n.DS_Store\n')]:
        p = os.path.join(DIR, fn)
        if not os.path.exists(p):
            with open(p, 'w') as f:
                f.write(c)
            print(f'✅ {fn} 已创建')

    print('\n✅ 全部修复完成！')

if __name__ == '__main__':
    main()

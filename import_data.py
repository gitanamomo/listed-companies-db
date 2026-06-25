# -*- coding: utf-8 -*-
"""
导入现有210家公司数据到SQLite数据库
运行此脚本一次即可
"""
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, import_companies

# Import all company data from build_final_excel.py
from build_final_excel import ALL_CITIES

init_db()

total = 0
for city, companies in ALL_CITIES:
    n = import_companies(companies, city)
    print(f"{city}: 导入 {n} 家公司")
    total += n

print(f"\n总计导入 {total} 家公司")

# Export for dashboard
from database import export_for_dashboard, get_stats
export_for_dashboard()

stats = get_stats()
print(f"\n数据库概览:")
print(f"  活跃公司: {stats['total']}")
cities_str = ', '.join(c["city"] + ":" + str(c["cnt"]) for c in stats["by_city"])
print(f"  城市分布: {cities_str}")

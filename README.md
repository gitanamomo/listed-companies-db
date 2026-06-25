# A股上市公司数据库

7城上市公司精选 + 十五五规划匹配 + 全量 A 股数据库

## 数据概览

| 指标 | 数值 |
|------|------|
| 活跃公司 | 5,208 家 |
| 上交所 | 2,316 家 |
| 深交所 | 2,892 家 |
| 北交所 | 待导入 |
| 板块 | 主板 3,202 · 创业板 1,397 · 科创板 609 |
| 覆盖城市 | 472 个 |
| 行业分类 | 91 个 |
| 城市覆盖率 | 99.8% |
| 精选公司 | 193 家（7城 + 十五五匹配） |

精选 7 城：深圳 · 广州 · 佛山 · 珠海 · 福州 · 厦门 · 长沙

## 项目结构

```
上市公司数据/
├── database.py              # SQLite 数据库核心：建表、导入、统计、导出
├── download_stocks.py       # 全量 A 股下载器（深交所 + 东方财富 + 北交所）
├── download_bj_stocks.py    # 北交所专用下载器
├── import_all.py            # 全量导入：缓存 → SQLite
├── import_data.py           # 精选公司导入（从 build_final_excel.py）
├── import_bj_stocks.py      # 北交所专用导入器
├── fill_province_city.py    # 并发查询省市信息（akshare）
├── build_final_excel.py     # 生成 7城精选 Excel（含十五五匹配）
├── update_check.py          # 月度更新脚本：检测新增/退市/变更
├── refresh.py               # 一键刷新：DB → JSON → 离线看板
├── fix_all_bugs.py          # 一键修复脚本（已执行）
├── monthly_update.sh        # 月度更新 Shell 封装
├── dashboard.html           # 在线看板模板
├── dashboard_offline.html   # 离线看板（含内嵌数据）
├── dashboard_data.json      # 看板 JSON 数据源
├── listed_companies.db      # SQLite 主数据库
├── requirements.txt         # Python 依赖
├── .gitignore               # Git 忽略规则
├── .cache/                  # API 缓存目录
│   ├── baostock_all.json
│   ├── province_city_cache.json
│   └── bj_stocks.json       # 北交所数据（待生成）
└── README.md                # 本文件
```

## 数据库表结构

### companies — 上市公司主表

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | VARCHAR(20) | 股票代码（sh.xxx / sz.xxx / bj.xxx） |
| stock_name | VARCHAR(100) | 股票简称 |
| full_name | VARCHAR(200) | 公司全称 |
| main_biz | TEXT | 主营业务 |
| website | VARCHAR(200) | 官网 |
| reg_address | TEXT | 注册地址 |
| industry | VARCHAR(50) | 行业分类 |
| province | VARCHAR(20) | 省份 |
| city | VARCHAR(20) | 城市 |
| market | VARCHAR(10) | 交易所（上交所/深交所/北交所） |
| board | VARCHAR(20) | 板块（主板/创业板/科创板/北交所） |
| listing_date | DATE | 上市日期 |
| wsw_match | TEXT | 十五五匹配方向 |
| match_type | VARCHAR(20) | 匹配类型 |
| is_curated | BOOLEAN | 是否精选公司 |
| status | VARCHAR(20) | 状态（active/delisted） |

### update_log — 变更日志

记录每次检测到的新增、退市、变更事件

### update_runs — 更新记录

记录每次 update_check.py 的运行结果

## 快速开始

### 安装依赖
```bash
pip install -r requirements.txt
```

### 数据结构
```bash
# 基础数据（沪深）
python3 download_stocks.py    # 下载全量 A 股（约 5,200 家）
python3 import_all.py         # 导入数据库 + 导出看板

# 北交所数据（待网络可用时执行）
python3 download_bj_stocks.py
python3 import_bj_stocks.py

# 补充省市信息（异步 15 线程，约 2 分钟）
python3 fill_province_city.py

# 刷新看板
python3 refresh.py            # 重新生成 dashboard_offline.html
```

### 月度更新
```bash
# 检测变更（不写入）
python3 update_check.py

# 检测并应用变更
python3 update_check.py --apply
```

### 查看离线看板
双击 `dashboard_offline.html` 即可在浏览器中查看

## 数据源

| 数据源 | 用途 | 覆盖 |
|--------|------|------|
| baostock | 全量 A 股列表、上市日期、退市日期 | 沪深 |
| 深交所官网 | A 股列表、行业分类 | 深交所 |
| 东方财富 API | 城市信息、省份信息 | 沪深北 |
| akshare (cninfo) | 注册地址 → 省市提取 | 全市场 |
| 新浪财经 | 备用数据源 | 沪深 |

## 改动记录

| 日期 | 说明 |
|------|------|
| 2026-06-08 | 修复 database.py 缩进语法错误（P0 阻塞） |
| 2026-06-08 | 修复 import_data.py f-string 转义错误 |
| 2026-06-08 | 升级地址解析器，支持县级市/自治州城市提取 |
| 2026-06-08 | 城市覆盖率从 89% 提升至 99.8%（+529 家） |
| 2026-06-08 | 新增北交所下载/导入脚本 |
| 2026-06-08 | download_stocks.py 集成北交所支持 |
| 2026-06-08 | 补丁脚本 fix_all_bugs.py 全部生效 |
| 2026-06-07 | 全量 A 股导入（5,208 家） |
| 2026-06-07 | 离线看板开发 |

## 待办

- [ ] 北交所数据导入（约 280 家，需网络）
- [ ] 12 家缺城市公司补充（需网络）
- [ ] 补充公司全称 / 官网字段
- [ ] REST API 接口

## 修改指南

- 新增数据源：在 `download_stocks.py` 添加 `fetch_xxx()` 函数
- 新增数据库字段：
  1. 在 `database.py` 的 `migrate_schema()` 添加迁移
  2. 在 `init_db()` 的 `CREATE TABLE` 添加字段
  3. 运行 `python3 -c "from database import init_db; init_db()"`
- 修改看板：编辑 `dashboard.html`，运行 `python3 refresh.py` 重新生成离线版

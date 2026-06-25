# A股上市公司数据库

7城上市公司精选 + 十五五规划匹配 + 全量 A 股数据库

## 数据概览

| 指标 | 数值 |
|------|------|
| 活跃公司 | 5,535 家 |
| 上交所 | 2,456 家 |
| 深交所 | 3,079 家 |
| 北交所 | 待导入 (网络受限) |
| 板块 | 主板 3,483 · 创业板 1,439 · 科创板 613 |
| 覆盖城市 | 7 个 |
| 行业分类 | 30 个 |
| 精选公司 | 194 家（7城 + 十五五匹配） |

精选 7 城：深圳 · 广州 · 佛山 · 珠海 · 福州 · 厦门 · 长沙

## 项目结构

```
上市公司数据/
├── database.py              # SQLite 数据库核心：建表、导入、统计、导出
├── download_stocks.py       # 全量 A 股下载器（baostock + 东方财富）
├── download_bj_stocks.py    # 北交所专用下载器（东方财富 API）
├── import_all.py            # 全量导入：缓存 → SQLite
├── import_data.py           # 精选公司导入（从 build_final_excel.py）
├── import_bj_stocks.py      # 北交所专用导入器
├── fill_province_city.py    # 并发查询省市信息（akshare，15线程）
├── build_final_excel.py     # 生成 7城精选 Excel（含十五五匹配）
├── build_excel_step1.py     # 数据处理中间步骤
├── download_company_details.py # 公司详情补充下载器
├── update_check.py          # 月度更新脚本：检测新增/退市/变更
├── refresh.py               # 一键刷新：DB → JSON → 离线看板
├── fix_all_bugs.py          # 一键修复脚本
├── save_todos.py            # 待办清单生成器
├── monthly_update.sh        # 月度更新 Shell 封装
├── dashboard.html           # 在线看板模板
├── dashboard_offline.html   # 离线看板（含内嵌数据）
├── curated_dashboard.html   # 精选7城看板V2（银行联动 + CSV导出）
├── curated_data.json        # 精选公司 JSON 数据源
├── dashboard_data.json      # 全量看板 JSON 数据源
├── listed_companies.db      # SQLite 主数据库
├── requirements.txt         # Python 依赖
├── .gitignore               # Git 忽略规则
├── .cache/                  # API 缓存目录
│   └── baostock_all.json    # baostock 全量A股缓存
├── bank/                    # 中国上市银行子模块
│   ├── index.html           # 38家银行离线看板
│   ├── banks.json           # 银行数据（含SWIFT、总行、财务模板）
│   ├── foreign_banks.json   # 12家外资银行
│   └── download_bank_data.py # 银行数据补充脚本
└── README.md                # 本文件
```

## 精选看板 V2 新功能

- **银行联动** — 自动识别上市银行，展示 SWIFT Code、银行类型、总行地址
- **CSV 导出** — 按当前筛选条件一键导出，含中文表头
- **多维度筛选** — 城市、板块、十五五匹配类型 + 关键词搜索
- **动态统计** — 筛选结果实时更新统计卡片

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
| office_address | TEXT | 办公地址 |
| industry | VARCHAR(50) | 行业分类 |
| province | VARCHAR(20) | 省份 |
| city | VARCHAR(20) | 城市 |
| market | VARCHAR(10) | 交易所（上交所/深交所/北交所） |
| board | VARCHAR(20) | 板块（主板/创业板/科创板/北交所） |
| listing_date | DATE | 上市日期 |
| out_date | DATE | 退市日期 |
| wsw_match | TEXT | 十五五匹配方向 |
| match_type | VARCHAR(20) | 匹配类型 |
| is_curated | BOOLEAN | 是否精选公司 |
| status | VARCHAR(20) | 状态（active/delisted） |

### update_log — 变更日志

记录每次检测到的新增、退市、变更事件

### update_runs — 更新记录

记录每次 update_check.py 的运行结果

## 待办事项

- [ ] **北交所数据** — 东方财富 API 返回 502，需网络正常后运行 `download_bj_stocks.py`
- [ ] **行业/省市补充** — 同上，需网络后运行 `fill_province_city.py`
- [ ] **配置 GitHub 远程仓库** — 当前无 remote
- [ ] **定时自动更新** — cron + 日志通知
- [ ] **RESTful API** — FastAPI 查询接口

## 改动记录

| 日期 | 版本 | 内容 |
|------|------|------|
| 2026-06-25 | v2.0 | P0急救：恢复数据库 + 重建3个损坏脚本 + 修复缩进bug + Git重建；导入5,535家全量A股；精选看板V2（银行联动+CSV导出） |
| 2026-06-08 | v1.5 | 新增银行子模块（38家+12家外资银行）；补全银行全称 |
| 2026-06-07 | v1.0 | 初始版本：7城精选 + 十五五匹配 + 看板 |

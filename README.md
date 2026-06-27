# A 股上市公司数据库

全量 A 股（含北交所）数据采集、存储、检索与可视化。覆盖沪深北三市 5,868 家活跃公司。

## 数据概览

| 指标 | 数值 | 覆盖率 |
|------|------|--------|
| 活跃公司 | 5,868 家 | — |
| 上交所 / 深交所 / 北交所 | 2,456 / 3,079 / 333 | — |
| 省份 | 5,857 | **99%** |
| 行业 | 5,541 | **94%** |
| 公司全称 | 1,768 | 30% |
| 官网 | 1,769 | 30% |
| 注册地址 | 1,769 | 30% |
| 城市 | 906 | 15% |
| 主营业务 | 194 | 3% |

精选 7 城：深圳 · 广州 · 佛山 · 珠海 · 福州 · 厦门 · 长沙（194 家，含十五五规划匹配）

## 项目结构

### 核心脚本

| 文件 | 用途 |
|------|------|
| `database.py` | SQLite 核心：建表、导入、查询、导出 |
| `refresh.py` | 一键刷新：DB → JSON → 离线看板 |
| `update_check.py` | 月度更新：检测新增 / 退市 / 变更 |
| `monthly_update.sh` | Shell 封装，适合 cron / launchd 调度 |

### 数据下载 & 导入

| 文件 | 用途 |
|------|------|
| `download_stocks.py` | 全量 A 股下载（baostock + 东方财富） |
| `download_bj_stocks.py` | 北交所专用下载器（东方财富 API） |
| `import_all.py` | 全量导入：缓存 → SQLite |
| `import_data.py` | 精选公司导入（7 城 + 十五五） |
| `import_bj_stocks.py` | 北交所专用导入器 |
| `download_company_details.py` | 公司详情补充下载器 |

### 数据补充（enrich）

| 文件 | 用途 | 状态 |
|------|------|------|
| **`enrich_f10_runner.py`** | 🔥 **主用**：东方财富 F10 API，一次补 city / full_name / website / reg_address，20 条/轮，中断可续 | ✅ 推荐 |
| `enrich_f10_batch.py` | 同上，100 条大批次版 | 备用 |
| `fill_province_city.py` | 原版省市填充（akshare `stock_individual_info_em`，15 线程） | ⚠️ API 已失效 |
| `enrich_eastmoney.py` | 东方财富批量 API — **注意：字段映射有误，f102/f103 是概念标签不是城市** | ❌ 勿用 |
| `enrich_city_v2.py` | cninfo 逐条查询版 | 慢且不稳定 |
| `enrich_city_v3.py` | cninfo 批量版（带超时） | 同上 |
| `enrich_cninfo.py` | cninfo 并发版（10 线程） | 同上 |
| `test_city_api.py` | API 连通性测试 | 调试用 |

### 看板（HTML）

| 文件 | 说明 |
|------|------|
| `curated_dashboard.html` | 精选 7 城看板 V2：银行联动 + CSV 导出 + 多维度筛选 |
| `search_dashboard.html` | 全量检索看板：市场 / 板块 / **省份** / 行业 / 城市筛选 |
| `dashboard_offline.html` | 全量离线看板（内嵌数据，无需网络） |
| `dashboard.html` | 在线看板模板 |

### 看板数据源

| 文件 | 大小 | 说明 |
|------|------|------|
| `curated_data.json` | ~127 KB | 精选公司 |
| `search_data.json` | ~1.3 MB | 全量搜索数据 |
| `dashboard_data.json` | ~3.5 MB | 全量看板数据 |

### 子模块

| 路径 | 说明 |
|------|------|
| `bank/` | 中国上市银行子模块：38 家银行离线看板 + 12 家外资银行，含 SWIFT / 总行 / 财务模板 |
| `obsidian/` | Obsidian Vault：194 家公司 Markdown + 3 个 Dataview 看板 |
| `.cache/` | API 缓存（JSON），避免重复请求 |

### 其他

| 文件 | 用途 |
|------|------|
| `build_final_excel.py` | 生成 7 城精选 Excel（含十五五匹配） |
| `build_excel_step1.py` | 数据处理中间步骤 |
| `fix_all_bugs.py` | 一键修复脚本（数据库语法错误等） |
| `save_todos.py` | 待办清单生成器 |
| `requirements.txt` | Python 依赖 |

### 原始数据文件

| 文件 | 说明 |
|------|------|
| `7城上市公司精选_十五五匹配.xlsx` | 精选 194 家 Excel |
| `A＋B股列表.xlsx` | A+B 股汇总 |
| `深圳辖区上市公司名录（2026年3月）.xls` | 深圳辖区名单 |

## 数据库

`listed_companies.db` — SQLite，3.4 MB，单表 `companies`。

### companies 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `stock_code` | VARCHAR(20) | 格式：`sh.600519` / `sz.000001` / `bj.832317` |
| `stock_name` | VARCHAR(100) | 股票简称 |
| `full_name` | VARCHAR(200) | 公司全称 |
| `main_biz` | TEXT | 主营业务 |
| `website` | VARCHAR(200) | 官网 |
| `reg_address` | TEXT | 注册地址 |
| `office_address` | TEXT | 办公地址 |
| `industry` | VARCHAR(50) | 行业分类 |
| `province` | VARCHAR(20) | 省份 |
| `city` | VARCHAR(20) | 城市（无「市」后缀） |
| `market` | VARCHAR(10) | 交易所：上交所 / 深交所 / 北交所 |
| `board` | VARCHAR(20) | 板块：主板 / 创业板 / 科创板 / 北交所 |
| `listing_date` | DATE | 上市日期 |
| `status` | VARCHAR(10) | active / delisted |
| `city_level` | VARCHAR(10) | 城市等级 |
| `fifteen_five_match` | VARCHAR(50) | 十五五匹配类型 |
| `curated` | TINYINT | 是否精选公司（0/1） |
| `last_updated` | TIMESTAMP | 最后更新时间 |

## 使用指南

### 补充数据（推荐方式）

```bash
cd "/Volumes/Gina2T/项目开发/上市公司数据"

# 运行 F10 Runner（20条/轮，自动写DB，中断可续）
python3 enrich_f10_runner.py 999
# Ctrl+C 随时停止，已写入的数据不会丢
```

### 刷新看板

```bash
python3 refresh.py
```

### 直接看数据

在浏览器中打开：
- `curated_dashboard.html` — 精选 7 城看板
- `search_dashboard.html` — 全量搜索（支持省份筛选）
- `dashboard_offline.html` — 全量离线看板
- `bank/index.html` — 银行业看板

### 从零重建

```bash
python3 download_stocks.py      # 全量 A 股
python3 download_bj_stocks.py   # 北交所
python3 import_all.py           # 导入数据库
python3 import_bj_stocks.py     # 北交所导入
python3 enrich_f10_runner.py 999  # 补充省市/全称/官网/地址
python3 refresh.py              # 刷新看板
```

## 版本记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.5 | 2026-06-27 | F10 批量补充脚本：city / full_name / website / reg_address + 省份筛选器 + GitHub 仓库重建 |
| v2.4 | 2026-06-25 | 北交所 333 家入库 + 省市数据 + 城市字段清洗 |
| v2.3 | 2026-06-08 | 全量 A 股 5,535 家导入 + 行业分类 |
| v2.2 | 2026-06-07 | 精选看板 V2：银行联动 + CSV 导出 |
| v2.1 | 2026-06-06 | 数据库恢复 + 修复损坏文件 |

## 注意事项

- 东方财富 `push2` 批量 API 的 `f102` / `f103` 字段是**板块/概念标签**，不是省份/城市，**不要用** `enrich_eastmoney.py`
- `akshare` 的 `stock_individual_info_em` 当前有 bug（Length mismatch），不可用
- baostock 不提供城市字段
- cninfo API (`stock_profile_cninfo`) 可用但不稳定（连接错误率 ~50%）
- 北交所 333 家暂无城市数据（所有已知数据源均不支持）
- PTY session 约 5-15 分钟会断，但 `enrich_f10_runner.py` 每轮自动写 DB，数据不丢

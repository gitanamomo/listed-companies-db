# 上市公司数据项目 · 待办清单

> 最后更新: 2026-06-25 (v2.1)

---

## ✅ 已完成

- [x] P0急救：恢复数据库 + 重建3个损坏脚本 + 修复database.py缩进bug + Git重建
- [x] P1-1：全量A股导入 — 5,535家活跃公司入库
- [x] P1-3：行业数据补全 — baostock query_stock_industry 补充5,014家，覆盖率94%
- [x] P2：精选看板V2 — 银行联动（SWIFT/银行类型）+ CSV导出
- [x] 全量检索看板 — search_dashboard.html（表格/卡片双视图 + 排序 + 筛选）
- [x] Obsidian Vault — 194家公司Markdown + 3个Dataview看板
- [x] README更新至v2.1 + Git提交5次
- [x] refresh.py 重写 — 一键生成全部看板

---

## ⏸ 待办（需网络）

- [ ] **北交所数据** — 运行 `python3 download_bj_stocks.py` → `python3 import_bj_stocks.py`
  - 东方财富API当前返回502，需网络正常时重试
  - 预计补充 ~280家北交所公司

- [ ] **城市/省份信息** — 运行 `python3 fill_province_city.py`
  - 当前仅194家精选公司有城市信息
  - 剩余~5,341家需 akshare 并发查询
  - 可用 `python3 fill_province_city.py` 15线程并发

- [ ] **公司详情补全** — 运行 `python3 download_company_details.py`
  - 补充 full_name / website / main_biz / office_address

---

## 📋 待办（无需网络）

- [ ] **配置 GitHub 远程仓库** — `git remote add origin <url>` → `git push -u origin main`

- [ ] **定时自动更新** — 设置 cron 定时执行 `python3 refresh.py` + `python3 update_check.py`
  - 示例: `0 9 1 * * cd /path && python3 refresh.py && python3 update_check.py --apply`

- [ ] **RESTful API** — 用 FastAPI 构建查询接口
  - 端点: GET /companies?city=深圳&board=科创板
  - 端点: GET /company/000001

- [ ] **Dashboard 离线版增强** — dashboard_offline.html 加入行业筛选、排序

- [ ] **银行看板更新** — bank/index.html 拉取最新银行财务数据

- [ ] **Obsidian 数据刷新** — 数据更新后重新运行 vault 生成脚本

---

## 💡 下次启动

```bash
cd /Volumes/Gina2T/项目开发/上市公司数据
# 先试网络
python3 -c "import baostock as bs; bs.login(); print('OK'); bs.logout()"
# 网络通的话：
python3 download_bj_stocks.py && python3 import_bj_stocks.py
python3 fill_province_city.py
python3 refresh.py
# 用 refresh.py 重新生成 Obsidian 文件
```

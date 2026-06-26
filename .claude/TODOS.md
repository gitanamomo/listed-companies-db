# 上市公司数据项目 · 待办清单

> 最后更新: 2026-06-26

## ✅ 已完成（本轮）

- [x] 北交所数据准备 — 重写 download_bj_stocks.py（摆脱东财 API 依赖问题）
- [x] 城市信息补充准备 — 新建 enrich_cninfo.py（cninfo逐个查询） + enrich_eastmoney.py（东财批量下载）

## ⏸ 待办（需网络正常）

- [ ] **北交所数据导入** — 运行 `python3 download_bj_stocks.py`
  - 东财 API 间歇性 502/空响应，需等 API 恢复
  - 预计补充 ~265-333 家北交所公司

- [ ] **城市/省份信息** — 运行 `python3 enrich_eastmoney.py`
  - 东财批量模式：54 页 × 100 条，2 分钟可完成全量 5.5K
  - 备用: `python3 enrich_cninfo.py`（逐个查询，~50 分钟）

- [ ] **公司详情补全** — cninfo 可补充 full_name/website/main_biz

## 📋 待办（无需网络）

- [ ] **配置 GitHub 远程仓库** — `git remote add origin <url>`
- [ ] **定时自动更新** — cron + refresh + update_check
- [ ] **RESTful API** — FastAPI 查询接口
- [ ] **看板增强** — dashboard_offline.html 加入行业筛选
- [ ] **Obsidian 数据刷新** — `python3 refresh.py` 后复制 obsidian/ 到 vault

## 💡 下次启动

```bash
cd /Volumes/Gina2T/项目开发/上市公司数据
# 先测网络
python3 -c "import requests; r=requests.get('https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=1&po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f12&fs=m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14',headers={'User-Agent':'Mozilla/5.0'},timeout=10); print(f'HTTP {r.status_code}')"
# API通了就：
python3 enrich_eastmoney.py && python3 download_bj_stocks.py && python3 import_bj_stocks.py && python3 refresh.py
```

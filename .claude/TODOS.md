# 上市公司数据项目 · 待办清单

> 最后更新: 2026-06-08

---

## 第一阶段：修复 database.py 语法错误（阻塞项）

**database.py** 第 141~142 行有缩进错误，导致 `import_all.py` 和 `fill_province_city.py` 都无法运行。

**修复方法：**
打开 `/Volumes/Gina2T/项目开发/上市公司数据/database.py`，找到如下代码（约第 140~143 行）：

```python
        else:
            board = '主板'

        # Try to extract listing date from existing data if available
            try:
            conn.execute("""
```

将其改为：

```python
        else:
            board = '主板'

        try:
            conn.execute("""
```

即：**删掉注释行 `# Try to extract listing date...`，并将 `try:` 的缩进减少 4 格**，使其与上面的 `board = '主板'` 对齐。

---

## 第二阶段：执行修复脚本并导入数据

按顺序执行：

### 1. 先验证语法

```bash
cd /Volumes/Gina2T/项目开发/上市公司数据/
python3 -c "from database import init_db; print('语法正确')"
```

### 2. 执行全量导入

```bash
python3 import_all.py
```

预期输出：
```
📊 全量A股数据导入
Step 1/5: 加载数据源...
  baostock: 5207 stocks
  SZSE industry map: 2892 stocks
Step 2/5: 初始化数据库...
Step 3/5: 合并现有精选数据...
  保留精选数据: ~193 stocks
Step 4/5: 导入数据库...
  ... 1000 processed
  ... 2000 processed
  ✅ 新导入: ~5207, 更新: 0
Step 5/5: 导出看板数据...
Dashboard data exported to dashboard_data.json
```

### 3. 填充省份/城市

```bash
python3 fill_province_city.py
```

预期：15 线程并发，约 1.6 分钟完成，覆盖广东/福建/湖南 1,183 家公司。

### 4. 重新执行修复脚本（确认所有补丁生效）

```bash
python3 fix_all_bugs.py
```

---

## 第三阶段：补充上交所行业分类

当前只有深交所 ~2,892 家公司有 `industry` 字段，上交所 ~2,316 家和北交所 ~280 家行业为空。

需要用 akshare 或 baostock 补充，具体方案待后续规划。

---

## 第四阶段：数据库完善方向

- [ ] 补充 `full_name` / `website` / `main_biz` 等字段
- [ ] restful API 接口查询数据库
- [ ] 自定义看板根据需要生成

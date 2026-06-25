#!/bin/bash
# ============================================================
# 上市公司数据 · 月度自动更新脚本
# 由 crontab 每月15日触发
# 日志输出到 monthly_update.log
# ============================================================
set -e

PROJECT_DIR="/Volumes/Gina2T/项目开发/TRAE/上市公司数据"
LOG_FILE="$PROJECT_DIR/monthly_update.log"
PYTHON="python3"

echo "============================================" >> "$LOG_FILE"
echo "月度更新开始: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "============================================" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# Step 1: 检测并应用变更（新增/退市）
echo "" >> "$LOG_FILE"
echo "[1/2] 运行 update_check.py --apply ..." >> "$LOG_FILE"
$PYTHON update_check.py --apply >> "$LOG_FILE" 2>&1 || {
    echo "⚠️  update_check 失败，继续执行 refresh" >> "$LOG_FILE"
}

# Step 2: 刷新看板（数据库→JSON→离线HTML）
echo "" >> "$LOG_FILE"
echo "[2/2] 运行 refresh.py ..." >> "$LOG_FILE"
$PYTHON refresh.py >> "$LOG_FILE" 2>&1 || {
    echo "❌ refresh 失败" >> "$LOG_FILE"
}

echo "" >> "$LOG_FILE"
echo "月度更新完成: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

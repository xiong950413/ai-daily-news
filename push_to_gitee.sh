#!/bin/bash
# 将 /workspace/ai-daily-news 推送到 Gitee
# 用法: ./push_to_gitee.sh <token>
# 依赖: 已完成 git init + commit（若未提交则自动提交所有变更）
set -e
TOKEN="${1:-bf2161cce4f304d5f44873ccaf11de43}"
REPO="https://helixiong:${TOKEN}@gitee.com/helixiong/ai-daily-news.git"
cd /workspace/ai-daily-news
git config user.name "helixiong" 2>/dev/null || true
git config user.email "helixiong@gitee.com" 2>/dev/null || true
git add -A
if ! git diff --cached --quiet; then
  git commit -m "docs: $(date +%Y-%m-%d) AI 行业资讯速览（定时任务自动更新）"
fi
git push "$REPO" main 2>&1 | grep -v "bf2161" || true
echo "PUSH_DONE"

#!/bin/bash
# 简单的提交脚本 - 在终端中执行此脚本

set -e  # 遇到错误立即退出

echo "📤 开始上传TASKS.md到GitHub..."

# 设置git用户信息
git config user.name "Claude Sonnet 4.5"
git config user.email "noreply@anthropic.com"

# 添加文件
echo "📦 添加TASKS.md到暂存区..."
git add TASKS.md

# 查看状态
echo "📋 当前状态:"
git status --short

# 提交
echo "💾 提交更改..."
git commit -m "docs: 添加详细任务列表

- 基于技术方案v0.2拆分的完整开发任务
- 8个Agent并行开发策略
- Phase 0-4详细任务清单
- 验收标准和风险应对

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# 推送
echo "🚀 推送到GitHub (origin/main)..."
git push origin main

echo "✅ 完成！TASKS.md已成功上传到GitHub"
echo "🔗 查看仓库: https://github.com/zhuyunchuan/auto-CompetitionAnalysis"

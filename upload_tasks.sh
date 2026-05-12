#!/bin/bash
# 上传任务列表到GitHub

echo "📤 准备上传任务列表到GitHub..."

# 添加TASKS.md到暂存区
git add TASKS.md

# 检查是否有其他修改的文件
echo "📋 当前状态:"
git status

# 提交
echo "💾 提交TASKS.md..."
git commit -m "docs: 添加详细任务列表

- 基于技术方案v0.2拆分的完整开发任务
- 8个Agent并行开发策略
- Phase 0-4详细任务清单
- 验收标准和风险应对

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# 推送到GitHub
echo "🚀 推送到GitHub..."
git push origin main

echo "✅ 完成！"

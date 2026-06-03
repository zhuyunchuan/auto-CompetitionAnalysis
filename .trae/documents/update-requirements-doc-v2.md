# 计划：需求文档升级 v1.0 → v2.0（整合"先爬虫再分析"两阶段架构）

## Summary

将现有需求文档 `docs/需求文档_竞品参数抓取系统_v1.0.md` 升级为 v2.0，核心变化：
1. 重新定位为 **"先爬虫，再分析"** 的两阶段系统
2. **两套系统并重描述**：Node.js Playwright（数据采集层）+ Python pipeline（分析层）
3. **新增竞品分析需求章节**：跨品牌型号对标、参数差异分析、分析报告生成
4. 将分析阶段从 Out of Scope 移入 Phase 2 In Scope

## Current State Analysis

### 现有文档（v1.0）
- 路径：`docs/需求文档_竞品参数抓取系统_v1.0.md`（442 行）
- 定位：仅描述"数据抓取与结构化整理"
- 架构：以 Node.js Playwright 脚本为主，Python 仅提及 `normalize_specs.py`
- Out of Scope 包含：跨品牌对标、竞争结论自动生成、大模型分析
- 未提及 Python pipeline（src/ 目录）的 9-Agent 架构

### 两套并行系统现状
1. **Node.js Playwright 脚本**（scripts/ 目录）：
   - 实际在用的数据采集工具
   - 5 个核心脚本（层级发现 × 2 + 批量抓取 × 2 + 宽表转换 × 1）
   - 统一 CLI 入口：`run.mjs` + `run.bat`
   - 最新结果：Hikvision 688/706 (97.4%)，Dahua 192/192 (100%)

2. **Python Pipeline**（src/ 目录）：
   - 9-Agent 并行开发，53 个 Python 文件，~13,715 行代码
   - 模块：core / storage / adapters / crawler / extractor / quality / pipeline / export / manual / mappings
   - SQLite + Parquet 存储，OpenClaw DAG 编排
   - 当前状态：基础框架已就绪，可作为分析层核心基础设施

## Proposed Changes

### 文件：`docs/需求文档_竞品参数抓取系统_v2.0.md`（新建）

> 由于 v2.0 结构变化较大，创建新文件而非原地修改 v1.0。

#### 变更 1：文档信息升级
- 版本号：v1.0 → v2.0
- 日期：2026-05-19 → 2026-05-29
- 定位：从"参数自动抓取与结构化整理系统"改为"参数自动抓取与竞品分析系统"

#### 变更 2：背景与目标重构
- 2.1 背景：增加竞品分析的必要性说明
- 2.2 目标：新增"跨品牌参数对标与差异分析"目标
- 2.3 核心原则：将"先抓全、再清洗、后分析"拆分为明确的两阶段原则
  - 新增原则：**爬虫与分析解耦** — 采集层不依赖分析层，分析层可独立迭代
  - 新增原则：**两阶段可独立运行** — Phase 1 可独立产出数据资产，Phase 2 可基于已有数据运行

#### 变更 3：覆盖范围扩展
- 3.1 品牌覆盖：保持不变
- 3.2 In Scope 扩展：
  - Phase 1（数据采集）：原有 6 项保持
  - Phase 2（竞品分析）：新增 3 项（型号对标、参数差异、报告生成）
- 3.3 Out of Scope 收窄：
  - 大模型策略分析仍为 Out of Scope
  - 移除"跨品牌竞争结论自动生成"（改为 Phase 2 In Scope）

#### 变更 4：技术架构重大调整
- 5.1 整体架构图重绘为双层架构：
  ```
  ┌─────────────────────────────────────────────────┐
  │         Phase 1: 数据采集层 (Node.js)            │
  │  结构发现 → 批量规格抓取 → 宽表转换              │
  │  入口: run.mjs / run.bat                         │
  └──────────────────────┬──────────────────────────┘
                         │ CSV/JSONL 数据交付
  ┌──────────────────────▼──────────────────────────┐
  │         Phase 2: 竞品分析层 (Python Pipeline)    │
  │  数据导入 → 标准化 → 对标匹配 → 差异分析 → 报告  │
  │  入口: src/pipeline/                             │
  └─────────────────────────────────────────────────┘
  ```
- 5.2 技术栈表格扩展：
  - Node.js Playwright → 数据采集层
  - Python Pipeline → 分析层（SQLite + Parquet + Excel）
- 5.3 关键脚本表格扩展为两部分：
  - 数据采集脚本（Node.js）：原有 5 个
  - 分析处理脚本（Python）：描述 Python pipeline 核心模块

#### 变更 5：新增章节 — Phase 2 竞品分析需求
新增以下章节（在原第 7 章"技术问题"之前插入）：

**新增 7. Phase 2: 竞品分析需求**
- 7.1 跨品牌型号对标匹配
  - 对标维度：分辨率、镜头类型、补光方式、码流数、AI 功能、防护等级
  - 匹配策略：基于参数相似度的多维度评分
  - 输出：对标关系表（hikvision_model ↔ dahua_model, confidence_score）
- 7.2 参数差异分析
  - 分析维度：关键参数逐项对比
  - 差异类型：参数缺失、数值差异、功能缺失/多余
  - 输出：差异矩阵（每对对标型号 × 每个参数维度）
- 7.3 竞品分析报告生成
  - 报告内容：对标总览、参数差异明细、系列覆盖度分析
  - 输出格式：Excel 多 Sheet 报告
  - 报告结构：
    1. 对标总览 Sheet（品牌-系列-型号匹配概览）
    2. 参数差异明细 Sheet（逐型号逐参数对比）
    3. 系列覆盖度 Sheet（各品牌系列布局对比）
    4. 数据质量 Sheet（异常数据标注）
    5. 运行摘要 Sheet（分析运行统计）

#### 变更 6：数据模型扩展
- 新增数据模型描述：
  - `model_mapping`：跨品牌型号对标关系
  - `param_diff`：参数差异记录
  - `analysis_report_meta`：分析报告元数据
- 保留原有数据模型（层级结构 JSON、长表 CSV、宽表 CSV）

#### 变更 7：Python Pipeline 模块描述
新增一个完整章节描述 Python pipeline 的架构：
- 模块清单：core / storage / adapters / crawler / extractor / quality / pipeline / export / manual / mappings
- 存储方案：SQLite（在线数据）+ Parquet（批次快照）
- DAG 任务链：discover → collect → extract → normalize → quality → merge_manual → export → notify
- 在 Phase 2 中的角色：数据标准化 + 对标分析 + 报告导出的核心引擎

#### 变更 8：执行流程重构
将原来 3 Phase 扩展为 5 Phase：
```
Phase 1: 层级结构发现（Node.js）
Phase 2: 批量规格抓取（Node.js）
Phase 3: 宽表生成（Node.js + Python）
Phase 4: 数据导入与标准化（Python Pipeline）
Phase 5: 竞品分析与报告生成（Python Pipeline）
```

#### 变更 9：后续规划更新
- Phase 1：✅ 基础抓取 + 宽表输出（已完成）
- Phase 2：🔄 竞品分析（型号对标 + 差异分析 + 报告生成）— 本次新增
- Phase 3：跨品牌深度分析（系列布局对比、产品定位策略）
- Phase 4：大模型辅助分析与趋势报告

#### 变更 10：已知问题与待办保留
- 原 v1.0 第 7 章"技术问题与修复"保留（内容不变）
- 原 v1.0 第 9 章"已知问题与待办"保留（内容不变）

## 章节结构对照（v1.0 → v2.0）

| v1.0 章节 | v2.0 章节 | 变化说明 |
|-----------|-----------|---------|
| 1. 文档信息 | 1. 文档信息 | 版本号升级 |
| 2. 背景与目标 | 2. 背景与目标 | 新增分析目标 |
| 3. 覆盖范围 | 3. 覆盖范围 | In Scope 扩展 |
| 4. 数据源与抓取策略 | 4. 数据源与抓取策略 | 不变 |
| 5. 技术架构 | 5. 技术架构 | 双层架构重绘 |
| - | **6. Python Pipeline 架构** | **新增** |
| - | **7. Phase 2 竞品分析需求** | **新增** |
| 6. 数据模型与输出格式 | 8. 数据模型与输出格式 | 新增分析相关模型 |
| 7. 技术问题与修复 | 9. 技术问题与修复 | 保留 |
| 8. 当前抓取结果 | 10. 当前抓取结果 | 保留 |
| 9. 已知问题与待办 | 11. 已知问题与待办 | 保留 |
| 10. 执行流程 | 12. 执行流程 | 5 Phase 重构 |
| 11. 交付物清单 | 13. 交付物清单 | 新增分析交付物 |
| 12. 脚本环境依赖 | 14. 脚本环境依赖 | 新增 Python 依赖 |
| 13. 后续规划 | 15. 后续规划 | Phase 2 细化 |

## Assumptions & Decisions

1. **新建 v2.0 文件**：结构变化大，不覆盖 v1.0，保留历史版本
2. **输出格式**：分析报告以 Excel 多 Sheet 为主（与现有 Python pipeline 的 Excel 导出能力一致）
3. **LLM 分析**仍为 Out of Scope（Phase 4）
4. **Python pipeline 定位**：Phase 2 分析层核心，承接 Node.js 爬虫输出的 CSV/JSONL 数据
5. **两阶段解耦**：Phase 1 可独立运行和产出，Phase 2 基于已有数据运行

## Verification Steps

1. 确认新文档结构与上述章节对照表一致
2. 确认两套系统（Node.js + Python）均得到充分描述
3. 确认新增的竞品分析需求章节包含：对标匹配、差异分析、报告生成
4. 确认 Out of Scope 与 In Scope 的调整合理
5. 确认文档内容与实际代码（scripts/ 和 src/）一致

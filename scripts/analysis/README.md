# 竞品参数分析模块 (Phase 2)

## 目录

- [概述](#概述)
- [模块架构](#模块架构)
- [安装依赖](#安装依赖)
- [快速使用](#快速使用)
- [输出格式](#输出格式)
- [设计文档](#设计文档)

---

## 概述

该模块实现了竞品参数自动抓取系统的 **Phase 2 竞品分析** 功能，包括跨品牌型号对标匹配、参数差异分析、Excel 报告生成。

## 模块架构

```
scripts/analysis/
├── __init__.py          # 模块初始化
├── README.md            # 本文件
├── model_matcher.py     # 型号对标匹配 (Step 1)
├── param_comparator.py  # 参数差异分析 (Step 2)
├── analysis_report.py   # Excel 报告生成 (Step 3)
├── run_analysis.py      # 统一 CLI 入口
└── docs/                # 相关需求与设计文档
    ├── 需求文档_竞品参数抓取系统_v2.0.md
    ├── 需求文档_竞品参数抓取系统_v1.0.md
    ├── PRD_v0.7_竞品参数抓取与整理.md
    ├── 技术方案_v0.2_云端竞品参数抓取系统.md
    ├── 整体技术设计_v0.2_并行开发拆分.md
    └── field_dictionary_v1.md
```

## 安装依赖

```bash
cd D:\work\auto-CompetitionAnalysis
pip install -r requirements.txt
# 主要依赖：pandas, openpyxl, numpy
```

## 快速使用

### 方式 1：一键全流程 (推荐)

```bash
cd D:\work\auto-CompetitionAnalysis\scripts\analysis

# 使用默认宽表数据运行全流程
python run_analysis.py all

# 自定义参数
python run_analysis.py all --threshold 0.6 --top-k 3 --output-dir ../../results/my_analysis
```

### 方式 2：分步执行

```bash
# Step 1: 仅型号对标匹配
python run_analysis.py match --hk-csv ../../delivery/宽表/hikvision_specs_wide.csv --dahua-csv ../../delivery/宽表/dahua_specs_wide.csv --output-dir ../../results/analysis_20260602

# Step 2: 仅参数差异分析 (基于 Step 1 结果)
python run_analysis.py compare --mapping-csv ../../results/analysis_20260602/model_mapping.csv

# Step 3: 仅 Excel 报告生成
python run_analysis.py report --mapping-csv ../../results/analysis_20260602/model_mapping.csv --diff-csv ../../results/analysis_20260602/param_diff.csv --output ../../results/analysis_20260602/competitor_analysis.xlsx
```

### 方式 3：查看帮助

```bash
python run_analysis.py -h
```

## 输出格式

运行后将在输出目录生成以下文件：

| 文件 | 说明 |
|------|------|
| `model_mapping.csv` | 跨品牌型号对标关系表 |
| `param_diff.csv` | 参数差异明细 |
| `analysis_meta.json` | 分析运行元数据 |
| `competitor_analysis.xlsx` | Excel 多 Sheet 分析报告 |

Excel 报告包含 5 个 Sheet：
1. 对标总览
2. 参数差异明细
3. 系列覆盖度对比
4. 数据质量摘要
5. 运行统计

## 设计文档

详细需求和设计请查看 `docs/` 目录下的以下文档：

- [需求文档 v2.0](./docs/需求文档_竞品参数抓取系统_v2.0.md)：最新需求文档
- [需求文档 v1.0](./docs/需求文档_竞品参数抓取系统_v1.0.md)：旧版需求文档
- [PRD v0.7](./docs/PRD_v0.7_竞品参数抓取与整理.md)：产品需求文档
- [技术方案 v0.2](./docs/技术方案_v0.2_云端竞品参数抓取系统.md)：技术方案
- [整体技术设计 v0.2](./docs/整体技术设计_v0.2_并行开发拆分.md)：架构设计
- [字段字典 v1](./docs/field_dictionary_v1.md)：字段定义

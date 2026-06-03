# PRD v0.7 - 竞品参数抓取与整理（云端 OpenClaw）

## 1. 文档信息
- 文档版本：v0.7
- 日期：2026-04-18
- 项目阶段：Phase 1（仅抓取与整理）
- 部署模式：云端运行（非本地电脑）

## 2. 背景与目标
### 2.1 背景
当前需要持续跟踪 Hikvision 与 Dahua 网络摄像机产品参数，并沉淀为结构化数据，支持后续人工分析与策略研判。

### 2.2 目标
1. 周期性抓取两家官网目标产品的完整层级与参数信息。
2. 将抓取结果标准化并输出为可直接使用的 Excel。
3. 支持人工补录与复核，形成可持续迭代的数据资产。
4. 对异常数据进行识别与标注，便于优先处理。

## 3. 范围定义
### 3.1 In Scope（本期范围）
1. 云端部署与运行：使用现有 OpenClaw 云服务器。
2. 双品牌抓取：
   - Hikvision：Network Cameras 下目标系列（如 Value / Pro / PT）及其页面可见子系列与型号。
   - Dahua：Network Cameras 下目标系列（含 WizSense 2 / WizSense 3）及其页面可见子系列与型号。
3. 层级动态发现：不维护静态系列/子系列字典，每次运行从页面实时发现。
4. 参数抽取：按最小字段集抽取并标准化。
5. Excel 输出：产品目录、参数明细、人工补录、质量异常、运行摘要。
6. 人工复核：支持人工修改与补录后回写。

### 3.2 Out of Scope（本期不做）
1. Hikvision 与 Dahua 的型号对标关系自动匹配。
2. 跨品牌竞争结论自动生成。
3. 大模型策略分析（后续阶段接入）。

## 4. 关键业务原则
1. 先抓全、再清洗、后分析：先保障覆盖率与结构化质量。
2. 层级优先：任何型号必须绑定层级路径。
3. 页面即真相：系列/子系列以官网页面当期可见结构为准。
4. 人工可介入：人工补录和修订优先级高于机器抽取。

## 5. 数据源与抓取对象
### 5.1 Hikvision
- 入口页面：
  - https://www.hikvision.com/en/products/IP-Products/Network-Cameras/?category=Network+Products&subCategory=Network+Cameras&checkedSubSeries=null
- 详情页示例：
  - https://www.hikvision.com/hk/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/ds-2cd20123g2-liuy-s-l--rb-/

### 5.2 Dahua
- 入口页面：
  - https://www.dahuasecurity.com/products/network-products/network-cameras
- 覆盖目标：
  - WizSense 3
  - WizSense 2
  - 页面动态发现的相关子系列与型号

### 5.3 人工输入源
1. 人工补录型号（官网无对应页面）。
2. 人工修订字段值（纠偏抽取结果）。

## 6. 层级模型（统一）
所有产品记录均必须包含：
- `brand`
- `series_l1`
- `series_l2`（子系列）
- `product_model`
- `product_url`
- `locale`
- `snapshot_date`

示例路径：
- `Hikvision -> Pro -> EasyIP 4.0 with ColorVu -> DS-xxxx`

## 7. 最小字段集（MVP）
1. `Image Sensor`
2. `Max. Resolution`
3. `Lens Type`
4. `Aperture`
5. `Supplement Light Type`
6. `Supplement Light Range`
7. `Main Stream Max FPS@Resolution`（例如 `20fps (4608 x 2592)`）
8. `Stream Count`（例如出现 Third Stream 则为 3）
9. `Interface`（接口项集合）
10. `Deep Learning Function Categories`（大类集合）
11. `Approval.Protection`
12. `Approval.Anti-Corrosion Protection`

## 8. 功能需求
### 8.1 层级发现
1. 自动发现品牌站点中的 `series_l1`。
2. 在每个 `series_l1` 下自动发现 `series_l2`。
3. 在每个子系列下发现全部产品型号列表。
4. 记录发现时间、来源和状态。

### 8.2 产品抓取
1. 抓取产品详情页参数。
2. 支持增量抓取（新型号、参数变化、历史复抓）。
3. 失败重试与错误日志。

### 8.3 参数抽取与标准化
1. 标准字段映射（中英别名、层级字段路径）。
2. 单位归一化（fps、分辨率、距离等）。
3. 多值字段标准化（Interface、Deep Learning 分类）。

### 8.4 异常识别（本期）
本期异常为数据质量与结构异常，不涉及跨品牌对标。
1. `missing_field`：关键字段缺失。
2. `parse_failed`：字段解析失败。
3. `unit_abnormal`：单位或格式异常。
4. `duplicate_model`：同层级重复型号。
5. `subseries_empty`：子系列存在但无产品。
6. `hierarchy_changed`：系列/子系列本期新增或消失。

### 8.5 人工复核与补录
1. 支持人工新增产品及参数。
2. 支持人工修订抓取字段值。
3. 所有人工变更需记录操作人、时间、原因。

### 8.6 报表导出
1. 输出 Excel 文件（固定 Sheet 结构）。
2. 字段列稳定，便于透视与二次分析。

## 9. 非功能需求
1. 稳定性：单次任务成功率 >= 95%。
2. 可追溯：保留任务日志、页面来源 URL、抓取时间。
3. 可维护：页面结构变更可快速修复选择器。
4. 可扩展：后续可追加字段、品牌和 LLM 分析模块。
5. 合规：遵守目标站点条款、限速与访问礼貌策略。

## 10. 云端架构与 OpenClaw 任务编排
### 10.1 部署要求
1. 运行位置：云服务器。
2. 执行入口：OpenClaw 定时任务。
3. 存储：默认轻量方案 `SQLite + Parquet + Excel 产物 + 日志目录`。

### 10.2 存储策略（轻量优先）
1. 在线结构化数据：`SQLite`（单文件部署，低运维成本）。
2. 批次快照与分析副本：`Parquet`（按 `run_id` 分目录）。
3. 报表交付：`Excel`（固定 Sheet 结构）。
4. 迁移触发：当高并发写入、复杂查询、数据量持续增长时升级 `PostgreSQL`。

### 10.3 任务 DAG（建议）
1. `discover_hierarchy`
   - 输出品牌/系列/子系列清单与状态。
2. `crawl_product_catalog`
   - 输出型号目录与详情页链接。
3. `extract_and_normalize_specs`
   - 输出参数标准化长表。
4. `merge_manual_inputs`
   - 合并人工补录与修订。
5. `detect_data_quality_issues`
   - 输出异常数据表（基于人工修订后的最终数据）。
6. `export_excel_report`
   - 导出 Excel。
7. `notify_run_summary`
   - 输出运行摘要（成功、失败、新增层级、异常统计）。

### 10.4 调度频率
1. 支持双周任务。
2. 支持月度任务。
3. 两种频率可配置切换。

## 11. 数据表设计（逻辑）
### 11.1 `hierarchy_snapshot`
- `run_id`
- `brand`
- `series_l1`
- `series_l2`
- `series_source`（`page_discovered` / `manual`）
- `series_status`（`active` / `disappeared`）
- `discovered_at`

### 11.2 `product_catalog`
- `run_id`
- `brand`
- `series_l1`
- `series_l2`
- `product_model`
- `product_name`
- `product_url`
- `locale`
- `first_seen_at`
- `last_seen_at`
- `catalog_status`

### 11.3 `product_specs_long`
- `run_id`
- `brand`
- `series_l1`
- `series_l2`
- `product_model`
- `field_code`
- `field_name`
- `raw_value`
- `normalized_value`
- `unit`
- `value_type`
- `source_url`
- `extract_confidence`
- `is_manual_override`
- `updated_at`

### 11.4 `manual_inputs`
- `input_id`
- `brand`
- `series_l1`
- `series_l2`
- `product_model`
- `field_code`
- `manual_value`
- `operator`
- `reason`
- `created_at`

### 11.5 `data_quality_issues`
- `run_id`
- `brand`
- `series_l1`
- `series_l2`
- `product_model`
- `issue_type`
- `field_code`
- `issue_detail`
- `severity`
- `status`
- `owner`
- `created_at`

### 11.6 `run_summary`
- `run_id`
- `schedule_type`（`biweekly` / `monthly`）
- `started_at`
- `ended_at`
- `catalog_count`
- `spec_field_count`
- `issue_count`
- `new_series_count`
- `disappeared_series_count`
- `success_rate`
- `status`

### 11.7 存储配置（默认与扩展）
1. 默认（Phase 1）：`SQLite + Parquet`。
2. 扩展（Phase 2+）：`PostgreSQL + Parquet`，用于更高并发与更复杂查询。

## 12. Excel 交付规范
每次任务导出一个 Excel，包含以下 Sheet：
1. `hikvision_catalog`
2. `hikvision_specs`
3. `dahua_catalog`
4. `dahua_specs`
5. `manual_append`
6. `data_quality_issues`
7. `run_summary`

### 12.1 `*_catalog` 关键列
- 品牌
- 一级系列
- 二级系列
- 型号
- 产品名称
- 产品链接
- 首次发现时间
- 最近发现时间
- 状态

### 12.2 `*_specs` 关键列
- 品牌
- 一级系列
- 二级系列
- 型号
- 字段编码
- 字段名称
- 原始值
- 标准值
- 单位
- 来源 URL
- 置信度
- 是否人工修订
- 更新时间

## 13. 验收标准（Phase 1）
1. 覆盖率：目标系列与子系列下型号抓取覆盖率 >= 95%。
2. 抽取率：最小字段集抽取成功率 >= 90%。
3. 可靠性：连续 2 个调度周期任务成功率 >= 95%。
4. 可追溯：每条参数可追溯至来源 URL 与批次 `run_id`。
5. 可操作：Excel 可直接筛选/透视，人工补录可回写。

## 14. 风险与应对
1. 页面结构变化导致解析失败
   - 应对：选择器版本化 + 告警 + 回滚最近稳定解析规则。
2. 多语言页面字段差异
   - 应对：字段别名词典 + locale 标记。
3. 反爬限制导致抓取中断
   - 应对：限速、重试、会话管理、任务分片执行。
4. 型号命名不规范导致重复
   - 应对：型号标准化规则（去空格、大小写、符号归一）。

## 15. 里程碑（建议）
1. M1（1 周）：完成抓取链路与层级发现、目录数据落库。
2. M2（第 2 周）：完成参数抽取与标准化、异常识别。
3. M3（第 3 周）：完成 Excel 导出、人工补录回写、首轮双周运行。
4. M4（第 4 周）：稳定性优化并切换到正式调度（双周或月度）。

## 16. 后续阶段（预留）
1. 型号对标关系接入（由业务提供映射）。
2. 跨品牌参数差异分析与评分。
3. 大模型竞品策略总结（系列布局、参数演进、产品定位）。

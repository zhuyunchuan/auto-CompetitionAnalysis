# 任务列表 - 竞品参数抓取系统

基于技术方案文档 v0.2 和整体技术设计 v0.2 拆分的开发任务。

## 任务拆分概览

### 并行开发策略（9个Agent）

**Phase 1 - 基础设施（必须先完成）**
- Agent-A (Core): 核心模块（类型、配置、常量、日志）
- Agent-B (Storage): 存储层（SQLite schema、Repository、Parquet）

**Phase 2 - 可并行开发（依赖Phase 1）**
- Agent-C (Hikvision): Hikvision适配器（层级发现、产品抓取）
- Agent-D (Dahua): Dahua适配器（层级发现、产品抓取）
- Agent-E (Extractor): 抽取器和标准化引擎
- Agent-F (Quality): 质量检测规则和引擎
- Agent-I (Crawler): HTTP客户端、页面抓取器

**Phase 3 - 集成编排（串联全链路）**
- Agent-G (Pipeline): OpenClaw DAG任务编排

**Phase 4 - 交付层**
- Agent-H (Export): Excel导出、人工补录

---

## 详细任务清单

### Phase 0: 创建项目骨架和基础设施

- [ ] 创建项目目录结构
  ```
  src/
    core/
    storage/
    adapters/
    crawler/
    extractor/
    quality/
    pipeline/
    export/
    manual/
  tests/
  docs/
  ```

- [ ] 创建基础配置文件
  - `requirements.txt`
  - `config.yaml`
  - `Dockerfile`
  - `docker-compose.yml`
  - `.gitignore`
  - `README.md`

- [ ] 冻结联调契约文档
  - `docs/field_dictionary_v1.md`（12个最小字段集、别名、类型、单位、比较规则）

---

### Agent-A: 核心模块 (src/core/*)

- [ ] 定义统一数据对象类型 (`types.py`)
  - [ ] `HierarchyNode`: brand, series_l1, series_l2, source, status, discovered_at
  - [ ] `CatalogItem`: brand, series_l1, series_l2, model, name, url, locale
  - [ ] `SpecRecord`: run_id, brand, series_l1, series_l2, model, field_code, raw_value, normalized_value, unit, source_url, confidence
  - [ ] `QualityIssue`: run_id, brand, series_l1, series_l2, model, issue_type, field_code, detail, severity

- [ ] 实现配置加载系统 (`config.py`)
  - [ ] 支持YAML配置文件加载
  - [ ] 支持环境变量覆盖
  - [ ] 配置验证和默认值处理
  - [ ] 调度模式配置 (biweekly/monthly)
  - [ ] 品牌配置 (Hikvision/Dahua入口URL、白名单)
  - [ ] 爬虫配置 (并发数、超时、重试次数)
  - [ ] 存储配置 (SQLite路径、Parquet目录、Artifact目录)

- [ ] 定义通用常量 (`constants.py`)
  - [ ] 品牌常量 (HIKVISION, DAHUA)
  - [ ] Locale常量 (EN, ZH_HK, etc.)
  - [ ] 字段编码常量 (12个最小字段集)
  - [ ] 异常类型常量 (6种异常类型)
  - [ ] 严重级别常量 (P1, P2, P3)
  - [ ] 状态常量 (ACTIVE, DISAPPEARED, etc.)

- [ ] 实现日志系统 (`logging.py`)
  - [ ] JSON格式结构化日志
  - [ ] 日志字段: run_id, task_name, brand, series_l1, series_l2, product_model, event, status, error_message, duration_ms
  - [ ] 日志级别配置
  - [ ] 文件和控制台输出

---

### Agent-B: 存储层 (src/storage/*)

- [ ] 设计并实现SQLite schema (`schema.py`)
  - [ ] `hierarchy_snapshot` 表 + 索引 (run_id, brand, series_l1, series_l2)
  - [ ] `product_catalog` 表 + 唯一索引 (brand, series_l1, series_l2, product_model, locale)
  - [ ] `product_specs_long` 表 + 索引 (run_id, brand, product_model, field_code)
  - [ ] `manual_inputs` 表 + 索引 (brand, product_model, field_code, created_at)
  - [ ] `data_quality_issues` 表 + 索引 (run_id, issue_type, severity, status)
  - [ ] `run_summary` 表 + 索引 (started_at, schedule_type, status)

- [ ] 实现数据库连接和初始化 (`db.py`)
  - [ ] SQLite连接池管理
  - [ ] 数据库初始化脚本
  - [ ] 数据库迁移机制
  - [ ] 连接健康检查

- [ ] 实现Repository层
  - [ ] `repo_hierarchy.py`: 层级快照CRUD操作
  - [ ] `repo_catalog.py`: 产品目录CRUD操作
  - [ ] `repo_specs.py`: 规格记录CRUD操作
  - [ ] `repo_issues.py`: 质量问题CRUD操作
  - [ ] 批量插入和更新方法
  - [ ] 查询优化

- [ ] 实现Parquet存储 (`parquet_store.py`)
  - [ ] 按run_id分目录存储
  - [ ] 表数据导出到Parquet
  - [ ] 元数据管理
  - [ ] 存储空间管理

---

### Agent-C: Hikvision适配器 (src/adapters/hikvision_adapter.py)

- [ ] 实现层级发现
  - [ ] `discover_series()`: 发现一级系列
  - [ ] `discover_subseries(series_l1)`: 发现二级系列
  - [ ] 页面选择器定位和解析
  - [ ] 容错处理和重试

- [ ] 实现产品列表抓取
  - [ ] `list_products(series_l1, series_l2)`: 获取产品列表
  - [ ] 提取型号、名称、详情页URL
  - [ ] 分页处理
  - [ ] 去重逻辑

- [ ] 实现详情页抓取
  - [ ] `fetch_product_detail(url)`: 获取详情页HTML
  - [ ] 动态渲染处理 (playwright)
  - [ ] HTML缓存机制
  - [ ] 错误处理和重试

- [ ] 单元测试
  - [ ] 层级发现测试
  - [ ] 产品列表抓取测试
  - [ ] 详情页抓取测试

---

### Agent-D: Dahua适配器 (src/adapters/dahua_adapter.py)

- [ ] 实现层级发现
  - [ ] `discover_series()`: 发现一级系列
  - [ ] `discover_subseries(series_l1)`: 发现二级系列
  - [ ] 页面选择器定位和解析
  - [ ] 容错处理和重试

- [ ] 实现产品列表抓取
  - [ ] `list_products(series_l1, series_l2)`: 获取产品列表
  - [ ] 提取型号、名称、详情页URL
  - [ ] 分页处理
  - [ ] 去重逻辑

- [ ] 实现详情页抓取
  - [ ] `fetch_product_detail(url)`: 获取详情页HTML
  - [ ] 动态渲染处理 (playwright)
  - [ ] HTML缓存机制
  - [ ] 错误处理和重试

- [ ] 单元测试
  - [ ] 层级发现测试
  - [ ] 产品列表抓取测试
  - [ ] 详情页抓取测试

---

### Agent-E: 抽取器和标准化模块 (src/extractor/*)

- [ ] 实现字段注册表 (`field_registry.py`)
  - [ ] 定义12个最小字段集
    - image_sensor
    - max_resolution
    - lens_type
    - aperture
    - supplement_light_type
    - supplement_light_range
    - main_stream_max_fps_resolution
    - stream_count
    - interface_items
    - deep_learning_function_categories
    - approval_protection
    - approval_anti_corrosion_protection
  - [ ] 字段别名映射 (中英文、多locale)
  - [ ] 字段权重和优先级

- [ ] 实现规格抽取器 (`spec_extractor.py`)
  - [ ] `extract_specs(html, context)`: 从HTML提取字段
  - [ ] Hikvision页面解析逻辑
  - [ ] Dahua页面解析逻辑
  - [ ] 置信度计算
  - [ ] 原始值记录

- [ ] 实现标准化引擎 (`normalizer.py`)
  - [ ] 字段名标准化
  - [ ] 单位归一化 (fps、分辨率、距离等)
  - [ ] 多值字段序列化 (JSON数组)
  - [ ] 数值格式化

- [ ] 实现解析器 (`parsers/`)
  - [ ] `resolution_parser.py`: 分辨率解析 (宽x高)
  - [ ] `stream_parser.py`: 流参数解析 (FPS@分辨率)
  - [ ] `range_parser.py`: 范围值解析 (距离、焦距等)

- [ ] 单元测试
  - [ ] 各字段抽取测试
  - [ ] 标准化规则测试
  - [ ] 解析器测试

---

### Agent-F: 质量检测模块 (src/quality/*)

- [ ] 实现异常检测规则 (`issue_rules.py`)
  - [ ] `missing_field`: 关键字段缺失检测
  - [ ] `parse_failed`: 字段解析失败检测
  - [ ] `unit_abnormal`: 单位或格式异常检测
  - [ ] `duplicate_model`: 同层级重复型号检测
  - [ ] `subseries_empty`: 子系列存在但无产品检测
  - [ ] `hierarchy_changed`: 系列/子系列变化检测

- [ ] 实现异常检测器 (`issue_detector.py`)
  - [ ] 执行所有检测规则
  - [ ] 生成QualityIssue对象
  - [ ] 严重级别判定 (P1/P2/P3)
  - [ ] 问题汇总和统计

- [ ] 单元测试
  - [ ] 各检测规则测试
  - [ ] 严重级别判定测试

---

### Agent-I: 爬虫基础设施 (src/crawler/*)

- [ ] 实现HTTP客户端 (`http_client.py`)
  - [ ] 限速控制 (3-5并发)
  - [ ] 重试机制 (3次，指数退避 2s/5s/10s)
  - [ ] 会话管理和Cookie处理
  - [ ] UA轮换
  - [ ] 随机抖动 (300-1200ms)
  - [ ] 超时控制 (30s)

- [ ] 实现页面抓取器 (`page_fetcher.py`)
  - [ ] 静态页面抓取 (httpx)
  - [ ] 动态渲染支持 (playwright)
  - [ ] HTML缓存
  - [ ] 错误处理和降级
  - [ ] 页面快照保存

- [ ] 单元测试
  - [ ] HTTP客户端测试
  - [ ] 页面抓取器测试

---

### Agent-G: Pipeline和DAG编排 (src/pipeline/*)

- [ ] 实现各个Task
  - [ ] `tasks_discover.py`: 层级发现任务
  - [ ] `tasks_collect.py`: 产品目录收集任务
  - [ ] `tasks_extract.py`: 参数抽取任务
  - [ ] `tasks_merge_manual.py`: 人工补录合并任务
  - [ ] `tasks_quality.py`: 质量检测任务（在 merge_manual 之后执行）
  - [ ] `tasks_export.py`: Excel导出任务
  - [ ] 任务状态跟踪
  - [ ] 错误处理和重试

- [ ] 实现DAG编排器 (`dag.py`)
  - [ ] 定义任务依赖关系
  - [ ] 任务调度执行
  - [ ] 失败重试策略
  - [ ] 告警机制
  - [ ] run_id生成和管理

- [ ] 集成测试
  - [ ] DAG流程测试
  - [ ] 任务依赖测试
  - [ ] 错误恢复测试

---

### Agent-H: 导出和人工补录模块 (src/export/*, src/manual/*)

- [ ] 实现Excel导出器 (`excel_writer.py`)
  - [ ] 固定7个Sheet结构
    - hikvision_catalog
    - hikvision_specs
    - dahua_catalog
    - dahua_specs
    - manual_append
    - data_quality_issues
    - run_summary
  - [ ] 列顺序固定
  - [ ] 格式化和样式
  - [ ] 文件命名: `competitor_specs_<run_id>.xlsx`

- [ ] 实现运行摘要写入器 (`run_summary_writer.py`)
  - [ ] 统计成功、失败数量
  - [ ] 新增层级统计
  - [ ] 异常统计
  - [ ] 成功率计算

- [ ] 实现人工补录导入器 (`manual_importer.py`)
  - [ ] 从Excel读取manual_append sheet
  - [ ] 数据验证
  - [ ] 必填字段检查

- [ ] 实现覆盖服务 (`override_service.py`)
  - [ ] 人工值覆盖机器值
  - [ ] 记录is_manual_override标志
  - [ ] 操作日志记录
  - [ ] 批量覆盖支持

- [ ] 单元测试
  - [ ] Excel导出测试
  - [ ] 人工补录测试
  - [ ] 覆盖逻辑测试

---

### 测试和集成

- [ ] 单元测试
  - [ ] 各模块单元测试
  - [ ] 测试覆盖率 >= 70%

- [ ] 集成测试
  - [ ] 小样本运行测试 (每品牌2个子系列，每子系列3个型号)
  - [ ] DAG各节点产物验证
  - [ ] Excel模板验证

- [ ] 回归测试
  - [ ] 历史样例集
  - [ ] 页面模板升级验证

- [ ] 端到端测试
  - [ ] 完整流程测试
  - [ ] 双周任务模拟
  - [ ] 数据质量验证

---

## 验收标准（每个Agent）

1. 单元测试覆盖核心逻辑（至少成功路径 + 1个异常路径）
2. 不引入跨模块循环依赖
3. 提交前通过 `ruff + pytest`
4. 输出变更清单：文件路径 + 接口变化点

---

## 关键集成契约（冻结后不可变）

1. **field_code字典**: `docs/field_dictionary_v1.md`
2. **SQLite schema**: `src/storage/schema.py`
3. **数据类型**: `src/core/types.py`
4. **Adapter接口**: `src/adapters/base_adapter.py`
5. **Excel列结构**: `src/export/excel_writer.py`

---

## 建议执行时间表

```
Week 1: Agent-A + Agent-B (基础设施)
Week 2: Agent-C/D + Agent-I + Agent-E/F (并行)
Week 3: Agent-G (DAG编排) + Agent-H (导出)
Week 4: 集成联调 + 端到端测试
```

---

## 风险与应对

1. **页面结构变化导致解析失败**
   - 应对：选择器版本化 + 告警 + 回滚最近稳定解析规则

2. **多语言页面字段差异**
   - 应对：字段别名字典 + locale标记

3. **反爬限制导致抓取中断**
   - 应对：限速、重试、会话管理、任务分片执行

4. **型号命名不规范导致重复**
   - 应对：型号标准化规则（去空格、大小写、符号归一）

5. **并行开发冲突**
   - 应对：严格按模块写入域分工，不跨目录改动

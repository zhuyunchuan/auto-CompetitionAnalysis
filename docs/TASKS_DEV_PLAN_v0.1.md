# 任务拆分 - DEV_PLAN v0.1（扩展系列与产品图片）

来源文档：[DEV_PLAN_v0.1_扩展系列与产品图片.md](file:///workspace/docs/DEV_PLAN_v0.1_扩展系列与产品图片.md)

目标：在不重构现有 pipeline 的前提下，扩展 Hikvision/Dahua 系列覆盖，并新增产品主图 `image_url` 字段贯通（采集 → 存储 → 导出）。

---

## 0. 决策与冻结项（必须先定）

- [ ] Dahua 系列层级表达方式（二选一并全链路统一）
  - 方案 A：`series_l1 = "WizSense 2" / "WizSense 3"`（推荐：最直观，少改动）
  - 方案 B：`series_l1 = "WizSense"`，`series_l2 = "2" / "3"`
- [ ] Hikvision 系列命名与输出规则（Pro / Value / HiLook 的 `series_l1/series_l2` 期望值）
- [ ] 权威入口 URL 的配置方式（硬编码常量 or 写入 `config.yaml` 并支持环境变量覆盖）

交付物：
- 冻结后的命名/配置规则，写入该文件“0. 决策与冻结项”下方（用最终选项替换勾选项）。

---

## 1. 子任务拆分（可并行开发）

### T1. Hikvision 系列入口扩展（Pro / Value / HiLook）

依赖：0 决策与冻结项（Hikvision 命名与入口配置方式）

- [ ] 在 `src/adapters/hikvision_adapter.py` 增加“series → url”权威入口映射（至少覆盖 3 个给定入口）
- [ ] 保留现有 API 优先路径；当 API 缺失/失败时走 HTML 兜底解析
- [ ] 兜底解析需能产出 `CatalogItem`（型号、名称、详情页 URL、locale、series_l1/series_l2）
- [ ] 最小验证：至少能在 catalog 阶段产出新增系列的产品条目（数量可少，但链路可通）

验收：
- 运行一次最小样例后，导出的 `hikvision_catalog` sheet 中出现 Pro / Value / HiLook 对应系列条目。

---

### T2. Dahua 系列入口扩展（WizSense 2 / WizSense 3）

依赖：0 决策与冻结项（Dahua 层级表达方式）

- [ ] 在 `src/adapters/dahua_adapter.py` 增加“series → url”入口映射（至少覆盖 2 个给定入口）
- [ ] 目录抓取优先从入口页面解析型号与详情页 URL，降低对首页层级解析的依赖
- [ ] 将系列归类写入统一的 `series_l1/series_l2`（与 0 决策一致）
- [ ] 最小验证：至少能在 catalog 阶段产出两条系列的产品条目

验收：
- 导出的 `dahua_catalog` sheet 中出现 WizSense 2 / WizSense 3（或等价表达）系列条目。

---

### T3. 数据模型与存储升级（`image_url`）

依赖：无（可与 T1/T2 并行）

- [ ] `src/core/types.py`：`CatalogItem` 增加 `image_url: Optional[str] = None`
- [ ] `src/storage/schema.py`：`product_catalog` 增加 `image_url` 列（可空）
- [ ] `src/storage/repo_catalog.py`：写入/读取/查询对象字段贯通（包含 `image_url`）
- [ ] 轻量迁移方案落地（二选一）
  - 启动自检列，不存在则 `ALTER TABLE product_catalog ADD COLUMN image_url TEXT`
  - 或提供一次性迁移脚本（要求：部署流程可执行且可重复运行）

验收：
- 旧库升级后不丢数据，且 `image_url` 列可写入、可查询。

---

### T4. 图片解析与回写（从详情页 HTML 解析主图）

依赖：T3（字段与 repo 贯通）

- [ ] 定义“从 HTML 提取图片 URL”的通用方法（优先级建议：`og:image` → `twitter:image` → 页面主图 `<img>`）
- [ ] 在详情抓取链路中回写 `product_catalog.image_url`
  - 失败不阻断：解析不到写空并记录 warning 级日志
- [ ] Hikvision 页面结构增加少量特判（以离线 HTML fixture 为准）

验收：
- 至少 Hikvision 示例产品可解析出主图 URL（例如 `assets.hikvision.com`），并在 Excel catalog sheet 的 `image_url` 列出现。

---

### T5. Pipeline 串联与任务层改动

依赖：T1/T2/T3/T4（集成任务，建议后置）

- [ ] `src/pipeline/tasks_discover.py`：确保新入口系列可进入后续 catalog 流程（必要时补充 discover 入口策略）
- [ ] `src/pipeline/tasks_collect.py`：CatalogItem 对象构造与落库字段同步（含 `image_url` 初始为空）
- [ ] `src/crawler/detail_collector.py` / `src/pipeline` 中的 detail 抓取流程：在拿到 HTML 后触发图片解析与回写

验收：
- 一次最小运行能产生：新系列 catalog 条目 + image_url 回写 + 后续 extract/quality/export 不被阻断。

---

### T6. 导出层同步（Excel 增加 `image_url` 列）

依赖：T3（字段贯通）

- [ ] `src/export/excel_writer.py`：`hikvision_catalog` / `dahua_catalog` 增加 `image_url` 列（空值允许）
- [ ] `src/pipeline/tasks_export.py`：导出任务字段映射同步

验收：
- 导出的 Excel 中，两个 catalog sheet 均包含 `image_url` 列，旧数据为空不影响导出。

---

### T7. 测试与离线样例（必须补齐）

依赖：可与 T1-T6 并行推进，建议最后统一收口

- [ ] 新增/更新离线 fixture（HTML 快照）：
  - Hikvision：Pro / Value / HiLook 至少各 1 个入口页面样例（用于目录解析）
  - Dahua：WizSense 2 / WizSense 3 至少各 1 个入口页面样例
  - 产品详情页：至少 1 个可解析出图片的 Hikvision 详情页样例
- [ ] 单测覆盖：
  - 入口解析与目录解析（Hikvision/Dahua）
  - 图片解析（优先级策略）
  - DB 新列写入与 repo 读写
  - Excel 导出列存在性
- [ ] 端到端最小样例跑通（离线 HTML 或最小线上抓取）

验收：
- 测试能够在 CI 环境下稳定通过；端到端最小样例产生包含 `image_url` 的 Excel。

---

## 2. 推荐执行顺序（降低返工）

1. T3（模型/存储）→ T6（导出）先打通数据承载与输出面。
2. T1 + T2 并行（两品牌入口扩展）。
3. T4（图片解析回写）接入详情链路。
4. T5（pipeline 收口）统一联调。
5. T7（fixture + 单测 + 最小 e2e）补齐稳定性。

---

## 3. DoD（统一验收口径）

- Hikvision：Pro / Value / HiLook 均能产出 `product_catalog`（可通过导出的 `hikvision_catalog` 观察）。
- Dahua：WizSense 2 / WizSense 3 均能产出 `product_catalog`（可通过导出的 `dahua_catalog` 观察）。
- 图片：`product_catalog.image_url` 至少对一个 Hikvision 样例有值；解析失败不阻断 run。
- 兼容：旧库可通过轻量迁移补列后正常运行（自动修复或明确可执行的迁移命令）。

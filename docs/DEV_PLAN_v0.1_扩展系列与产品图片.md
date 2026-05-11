# 开发计划 v0.1：扩展系列与产品图片（Hikvision / Dahua）

## 背景与目标

基于当前仓库的抓取流水线，做如下扩展：

1. **Hikvision**：增加抓取系列覆盖范围，包含：
   - Pro
   - Value
   - HiLook
   - 给定入口链接（作为权威入口/兜底入口）：
     - https://www.hikvision.com/en/products/HiLook-IP-Products/Network-Cameras/?category=HiLook+IP+Products&subCategory=Network+Cameras&series=Value+Series&checkedSubSeries=NONE
     - https://www.hikvision.com/en/products/IP-Products/Network-Cameras/Pro-Series-EasyIP-/?category=Network+Products&subCategory=Network+Cameras&series=Pro+Series&checkedSubSeries=NONE
     - https://www.hikvision.com/en/products/IP-Products/Network-Cameras/value-series/?category=Network+Products&subCategory=Network+Cameras&series=Value+Series&checkedSubSeries=NONE
2. **Dahua**：增加抓取系列覆盖范围，包含：
   - WizSense 2
   - WizSense 3
   - 给定入口链接（作为权威入口/兜底入口）：
     - https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-3-series
     - https://www.dahuasecurity.com/products/network-products/network-cameras/wizsense-2-series
3. **产品图片**：补充产品主图 `image_url`，来源为每个产品详情页（例如：Hikvision 产品页包含主图链接）。

## 设计原则

- **最小侵入**：优先复用现有 pipeline（discover → catalog → detail → extract → quality → export），在必要处扩展数据模型与解析逻辑。
- **可回退与不阻断**：图片解析与新入口解析失败不应阻断整个 run；无法解析则置空，并通过日志/质量检测暴露问题。
- **避免强依赖 Playwright**：尽可能基于已抓取的 HTML 快照解析图片与目录；保留 Playwright 作为回退而非唯一通路。

## 影响范围（模块）

- 适配器：`src/adapters/hikvision_adapter.py`、`src/adapters/dahua_adapter.py`
- 编排与任务：`src/pipeline/tasks_discover.py`、`src/pipeline/tasks_collect.py`
- 存储与类型：`src/storage/schema.py`、`src/storage/repo_catalog.py`、`src/core/types.py`
- 导出：`src/export/excel_writer.py`、`src/pipeline/tasks_export.py`
- 测试：`tests/`（新增/更新）

## 关键改动点（方案）

### 1）Hikvision：系列与入口扩展

- 在 Hikvision 适配器中新增“权威入口映射（series → url）”，将给定链接作为：
  - HiLook 入口（独立于现有 IP Products）
  - Pro / Value 的明确系列入口
- `discover_series / discover_subseries / list_products`：
  - 保留现有 **API 优先**策略（若 API 覆盖到该系列则直接使用）。
  - 若 API 失败或缺失该系列，则使用给定链接执行 HTML 解析兜底，确保产出 `CatalogItem`。

### 2）Dahua：WizSense 2/3 固化入口

- 为 Dahua 适配器新增“series → url”映射，至少包含 wizsense-2-series 与 wizsense-3-series。
- 层级发现阶段确保能产生：
  - `series_l1 = "WizSense 2"` / `series_l1 = "WizSense 3"`（或统一为 `"WizSense"` 并用 `series_l2` 区分，需在实现时择一并统一全链路）。
- 目录抓取阶段优先从这些入口页面抓取型号与详情页 URL，减少依赖首页解析。

### 3）产品图片（image_url）贯通全链路

- **数据模型**：
  - `product_catalog` 表新增 `image_url`（可空）。
  - `CatalogItem`（`src/core/types.py`）新增 `image_url` 字段，写入/读取贯通 repo。
  - Excel 的 `*_catalog` sheet 增加 `image_url` 列。
- **图片解析**：
  - 在 `fetch_product_detail` 任务中拿到 HTML 后解析主图 URL，并将其回写到对应 `product_catalog` 记录。
  - 解析优先级建议：
    1) `<meta property="og:image" ...>`
    2) `<meta name="twitter:image" ...>`
    3) 页面主图容器下 `<img>`（按品牌页面结构做少量特判）
  - 解析不到不报错，写空并记录 warning。

### 4）数据库兼容策略（无迁移框架）

- 当前 `init_database()` 通过 `create_all()` 建表，不会自动对已有库加列。
- 需要增加轻量迁移策略（二选一）：
  - 启动时自检列是否存在，不存在则 `ALTER TABLE product_catalog ADD COLUMN image_url TEXT`；
  - 或提供一次性脚本/命令在部署时执行。

## 任务拆分（可执行清单）

### A. 现状确认（适配器入口与解析路径）

- 确认 Hikvision 当前系列来源（API / HTML / Playwright）与 series allowlist 机制。
- 确认 Dahua 当前 WizSense 系列发现方式与目录解析方式（tab HTML 缓存/链接正则）。
- 输出“修改点定位清单”。

### B. Hikvision 扩展（Pro / Value / HiLook）

- 增加 HiLook 入口与系列映射。
- 对给定系列链接实现目录解析兜底（独立于 API）。
- 验证能够在 catalog 中新增对应系列的产品条目。

### C. Dahua 扩展（WizSense 2 / WizSense 3）

- 增加 WizSense 2/3 入口映射。
- 目录抓取优先从给定入口抓取产品链接。
- 验证能够在 catalog 中新增两条系列的产品条目。

### D. 数据模型与存储（image_url）

- `product_catalog`：增加 `image_url` 列；repo 写入/读取与查询接口同步。
- `CatalogItem`：增加 `image_url` 字段并贯通写入流程。
- 增加轻量迁移（自检 + ALTER）。

### E. 图片抽取与回写

- 在 `fetch_product_detail` 中解析图片 URL 并回写到 `product_catalog.image_url`。
- 对 Hikvision 示例页面结构编写解析规则与离线单测。

### F. 导出同步

- Excel 的 catalog sheet 增加 `image_url` 列，旧数据为空时正常导出。

### G. 测试与验证

- 单测覆盖：
  - Hikvision/HiLook/Pro/Value 入口解析与目录解析（离线 fixture）。
  - Dahua WizSense 2/3 入口解析与目录解析（离线 fixture）。
  - 图片解析（离线 fixture）。
  - DB 新列写入与 Excel 导出列存在。
- 端到端验证：
  - 用离线 HTML 快照或最小样例跑一次 `run_manual_pipeline`，确认新系列与图片字段贯通。

## 验收标准（Definition of Done）

- Hikvision：
  - Pro / Value / HiLook 三类系列均可产出 `product_catalog` 记录（可通过 run_summary 与导出的 Excel catalog sheet 观察）。
- Dahua：
  - WizSense 2 / WizSense 3 均可产出 `product_catalog` 记录。
- 图片：
  - `product_catalog.image_url` 有值（至少 Hikvision 示例产品可解析出 `assets.hikvision.com` 图片链接），无法解析的条目不阻断流程。
  - Excel 的 `hikvision_catalog` / `dahua_catalog` 包含 `image_url` 列。
- 兼容性：
  - 旧库可通过轻量迁移补列后正常运行，未迁移时能给出明确错误或自动修复。


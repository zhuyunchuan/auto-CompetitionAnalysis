# Field Dictionary v1

本文档定义 Phase 1 的最小字段集与抽取标准，作为并行开发冻结契约。

## 1. 字段定义
| field_code | field_name | required | value_type | canonical_unit | comparison_rule |
|---|---|---|---|---|---|
| image_sensor | Image Sensor | yes | text | n/a | exact_or_alias |
| max_resolution | Max. Resolution | yes | text | px | normalized_resolution |
| lens_type | Lens Type | yes | text | n/a | exact_or_alias |
| aperture | Aperture | yes | text | f | normalized_aperture |
| supplement_light_type | Supplement Light Type | yes | text | n/a | exact_or_alias |
| supplement_light_range | Supplement Light Range | yes | number_or_text | m | normalized_distance |
| main_stream_max_fps_resolution | Main Stream Max FPS@Resolution | yes | text | fps+px | normalized_fps_resolution |
| stream_count | Stream Count | yes | integer | count | numeric_compare |
| interface_items | Interface | yes | list_text | n/a | set_compare |
| deep_learning_function_categories | Deep Learning Function Categories | yes | list_text | n/a | set_compare |
| approval_protection | Approval.Protection | yes | text | grade | exact_or_alias |
| approval_anti_corrosion_protection | Approval.Anti-Corrosion Protection | yes | text | grade | exact_or_alias |

## 2. 多语言别名（最小集）
| field_code | aliases |
|---|---|
| image_sensor | Image Sensor; 图像传感器 |
| max_resolution | Max. Resolution; 最大分辨率 |
| lens_type | Lens Type; 镜头类型 |
| aperture | Aperture; 光圈 |
| supplement_light_type | Supplement Light Type; 补光灯类型 |
| supplement_light_range | Supplement Light Range; 补光距离 |
| main_stream_max_fps_resolution | Main Stream; 主码流; Main Stream Max FPS@Resolution |
| stream_count | Stream Count; 码流数量; Third Stream |
| interface_items | Interface; 接口 |
| deep_learning_function_categories | Deep Learning Function; 深度学习功能 |
| approval_protection | Protection; 防护 |
| approval_anti_corrosion_protection | Anti-Corrosion Protection; 防腐等级 |

## 3. 标准化规则（摘要）
1. `max_resolution`
- 提取 `width x height`，统一为 `WIDTHxHEIGHT`（示例：`4608x2592`）。

2. `main_stream_max_fps_resolution`
- 结构化拆分：`fps_value`, `resolution_width`, `resolution_height`。
- 标准展示：`<fps>fps (<width>x<height>)`。

3. `supplement_light_range`
- 距离统一转 `m`；无法转换时保留原值并标记 `unit_abnormal`。

4. `interface_items` 与 `deep_learning_function_categories`
- 存储为 JSON 数组；比较时按集合比较（忽略顺序）。

## 4. 缺失与异常判定
1. `missing_field`
- `required=yes` 字段为空或未抽取到。

2. `parse_failed`
- 字段命中但解析器失败（例如正则或结构化拆解失败）。

3. `unit_abnormal`
- 单位无法识别或单位换算失败。

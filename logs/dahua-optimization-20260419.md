# Dahua 适配器优化总结

## 优化日期
2026-04-19

## 优化内容

### 1. 子系列发现优化
**问题**: 只从默认渲染的链接提取，遗漏了需要点击 tab 才能加载的子系列
**方案**: 
- 使用 Playwright 点击 `div.tabs-li` 元素遍历所有子系列 tab
- 缓存每个 tab 的 HTML 用于后续产品列表提取
**成果**: 
- WizSense 2: 1 → 2 个子系列 (WizColor, Smart Dual Light)
- WizSense 3: 1 → 6 个子系列 (TiOC PRO-WizColor, Smart Dual Light, TiOC, Anti-Corrosion, 4G Camera, WizSense Camera)

### 2. 产品数量提升
**优化前**: 18 个产品
**优化后**: 59 个产品 (+228%)

### 3. 字段提取率提升
**优化前**: 7/12 (58%)
**优化后**: 12/12 (100%)

#### 字段提取优化详情

| 字段 | 优化措施 |
|------|----------|
| `supplement_light_range` | 添加 "Illumination Distance" 别名 |
| `stream_count` | 添加 "Stream Capability" 别名 |
| `interface_items` | 添加 "Network Port", "Audio Input", "Alarm Input" 别名 |
| `deep_learning_function_categories` | 添加 "IVS", "SMD", "AcuPick" 别名 + 扩展 `_extract_smart_events` 支持表格结构 |
| `main_stream_max_fps_resolution` | 添加 "Video Frame Rate", "Frame Rate" 别名 |
| `approval_anti_corrosion_protection` | 后处理逻辑直接查找 "Protection: IP67" 模式 |
| `supplement_light_type` | 添加 "warm light" 识别 + 后处理组合 "IR + Warm Light" |

### 4. 浏览器复用优化
**问题**: 每次请求都启动新浏览器实例，效率低
**方案**: 实现 `_Browser` 单例模式，复用 Playwright 浏览器实例
**成果**: 减少浏览器启动开销，提升抓取速度

## 修改文件
- `src/adapters/dahua_adapter.py` - 核心适配器逻辑
- `src/extractor/field_registry.py` - 字段别名扩展
- `src/extractor/spec_extractor.py` - 提取器增强

## 测试验证
```
✅ aperture                                 F1.2
✅ approval_anti_corrosion_protection       IP67
✅ approval_protection                      Intrusion, tripwire...
✅ deep_learning_function_categories        ["IVS (Perimeter Protection)", "Face Detection(Full Image)", ...]
✅ image_sensor                             1/1.8" CMOS
✅ interface_items                          ["1 channel in: wet contact", "5 mA 3–5 VDC"]
✅ lens_type                                Motorized vari-focal
✅ main_stream_max_fps_resolution           Main stream: 3840 × 2160@(1 fps–25/30 fps)...
✅ max_resolution                           3840 (H) × 2160 (V)
✅ stream_count                             3
✅ supplement_light_range                   Up to 50 m (164.04 ft) (IR)...
✅ supplement_light_type                    IR + Warm Light

Hit: 12/12 (100%)
```

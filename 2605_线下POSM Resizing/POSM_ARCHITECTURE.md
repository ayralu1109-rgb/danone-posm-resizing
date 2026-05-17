# POSM 自动排版系统 — 架构文档

> 版本：0.2  
> 更新日期：2026-05-17  
> 配套需求文档：`POC_miniprd.md`

---

## 1. 系统概览

```
输入物料
  ├── Master BG（大尺寸背景图，PNG，200 DPI）
  ├── 元素 PNGs（1/2/3/4/6，含透明通道）
  └── 规格表（Excel，城市 × 尺寸）
         │
         ▼
  ┌─────────────────────────────┐
  │   Processing Engine         │  main.py
  │   Step 1–6 主流程           │
  └──────────┬──────────────────┘
             │ 调用 Template 公共接口
             ▼
  ┌─────────────────────────────┐
  │   Template Package          │  template/
  │   bg_crop.py                │  ← 背景裁切
  │   element_layout.py         │  ← 元素定位
  │   layer_order.py            │  ← 图层顺序
  └─────────────────────────────┘
         │
         ▼
输出物料（per city）
  └── {城市}_{尺寸}mm.zip
        ├── {城市}_{尺寸}mm.svg
        └── assets/
              ├── bg.png
              └── 1/2/3/4/6 元素 PNGs
```

**设计原则：**
- Processing Engine 只调用 Template 的公共接口，不感知内部实现
- 换活动/换背景 = 替换整个 Template 包，Processing Engine 不动
- 元素原始文件全程不修改；背景允许裁切 + 等比缩小（禁止放大）

---

## 2. 处理流程（Step 1–6）

| Step | 名称 | 输入 | 输出 | 执行者 |
|---|---|---|---|---|
| 1 | 读取规格 | Excel | `List[CitySpec]` | Processing Engine |
| 2 | 背景裁切 | Master BG + 画布尺寸 | `assets/bg.png` | `Template.crop_bg()` |
| 3 | 成品框计算 | 画布 + 成品框尺寸 | `(trim_x, trim_y)` | Processing Engine |
| 4a | 元素坐标计算 | 成品框 + 元素原始尺寸 | `layout dict` | `Template.compute_layout()` |
| 4b | 元素复制 | 元素 PNG 源文件 | `assets/元素.png` | Processing Engine |
| 5 | 构建 SVG | layout + 画布尺寸 | `.svg` 文件 | Processing Engine |
| 6 | 打包输出 | SVG + assets/ | `.zip` 文件 | Processing Engine |

异常（canvas > BG、元素需放大、锚点越界）在 Step 2/4a 抛出，Processing Engine 捕获后整行跳过并记录，全批次结束后汇总输出。

---

## 3. Template 公共接口

Template 包（`template/`）暴露三个函数，是 Processing Engine 与 Template 之间的**唯一契约**：

### 3.1 `crop_bg(bg_src_path, canvas_w_px, canvas_h_px, output_path) → str`

背景内容驱动裁切。

**行为：**
1. 根据 `canvas_w_px / canvas_h_px` 比例和 Template 内的 `CONTENT_REF_W/H` 计算 Viewport
2. 以罐心锚点将 Viewport 定位到主底图，`Image.crop()` 裁切
3. 若 Viewport > 画布，`Image.resize(LANCZOS)` 缩放至目标画布尺寸
4. 写入 `dpi=(200, 200)`，保存到 `output_path`

**异常：**
- `ValueError`：主底图小于 Viewport、或裁切框越界 → Processing Engine 捕获，整行跳过

### 3.2 `compute_layout(trim_w_px, trim_h_px, trim_offset_x, trim_offset_y, element_sizes) → dict`

元素定位计算。

**返回：** `{filename: {"x": int, "y": int, "w": int, "h": int}}`，坐标为画布绝对像素。

**异常：**
- `UpscaleError(element_name, original_w, target_w)`：任意元素需放大时抛出 → Processing Engine 捕获，整行跳过

### 3.3 `get_element_render_order() → list[str]`

返回元素文件名的 SVG 渲染顺序（bottom → top），不含 bg.png 和成品框。

---

## 4. Template 可配置参数

每套活动/素材对应一套 Template。以下参数在 `template/` 内部定义，Processing Engine 不感知：

### 4.1 背景裁切参数（`bg_crop.py`）

| 参数 | 类型 | PoC 当前值 | 说明 |
|---|---|---|---|
| `CAN_CX` | int (px) | `3280` | 罐心在主底图的 X 坐标 |
| `CAN_CY` | int (px) | `5935` | 罐心在主底图的 Y 坐标 |
| `CAN_TARGET_X` | float | `0.311` | 罐心落在 Viewport 宽度的百分比 |
| `CAN_TARGET_Y` | float | `0.638` | 罐心落在 Viewport 高度的百分比 |
| `CONTENT_REF_W_MM` | float | `960.0` | 最小内容参考框宽度（mm）|
| `CONTENT_REF_H_MM` | float | `1110.0` | 最小内容参考框高度（mm）|
| `SOURCE_DPI` | int | `200` | 主底图及输出 DPI |

**`CONTENT_REF_W/H` 的来源：** 主底图中包含完整活动内容（罐子 + Helix + 买点文案）的最小视野，由参考文件 `5罐子+背景+helix+买点.png`（960×1110mm）定义。

### 4.2 元素定位参数（`element_layout.py`）

| 参数 | PoC 当前值 | 说明 |
|---|---|---|
| 元素 1 宽度 | 60% 成品框 W | 顶部联合 logo |
| 元素 2 宽度 | 90% 成品框 W | 标题文字 |
| 元素 6 宽度 | 27.5% 成品框 W | 原装进口徽章 |
| 元素 3 宽度 | 85% 成品框 W | 脚注 |
| 元素 4 宽度 | 17.5% 成品框 W | 右下角 logo |

> ⚠️ **待评审**：背景 Viewport 缩放后，罐子在画布中的视觉尺寸随之变化，而元素定位规则基于成品框固定百分比，两者的视觉对齐关系（尤其元素 6 与罐子的相对位置）需要专项验证。

### 4.3 图层顺序（`layer_order.py`）

从底到顶固定顺序，返回值为 `element_layout.py` 中 `_RULES` 的 key 顺序：

```
bg.png → 2标题无蒙版 → 6原装进口 → 1顶部联合logo → 3脚注 → 4右下角logo → 成品框
```

---

## 5. 数据结构

### `CitySpec`（`main.py`）
每个城市/规格一个实例，由 Excel 解析生成。

| 字段 | 类型 | 说明 |
|---|---|---|
| `city` | str | 城市名 |
| `canvas_w_mm` / `canvas_h_mm` | float | 画布尺寸（mm），对应 Excel 画面尺寸 |
| `trim_w_mm` / `trim_h_mm` | float | 成品框尺寸（mm），对应 Excel 可视尺寸 |

派生属性（property）：`canvas_w_px`、`canvas_h_px`、`trim_w_px`、`trim_h_px`、`slug`

### `ExceptionRecord`（`main.py`）
跳过行的记录，收集后在全批次结束时汇总输出。

---

## 6. 关键设计决策记录

| 决策 | 选择 | 理由 | 替代方案 |
|---|---|---|---|
| 输出格式 | SVG + assets ZIP | 内存占用低、原始像素保留、AI 可编辑 | PNG 合成（内存高、不可逆） |
| 背景裁切 | 内容驱动 Viewport + Resize | 保证不同尺寸均能看到完整活动内容 | 纯锚点裁切（窄幅内容被截断） |
| 背景缩放插值 | Lanczos | 最高质量下采样，文字/细节保留好 | Bilinear（较快但质量稍低）|
| 元素处理 | 复制原文件，SVG 引用 | 零像素损失，文件轻量 | Pillow paste 合成（像素修改，不可逆） |
| SVG 尺寸单位 | `width/height` 用 mm，`viewBox` 用 px | Illustrator/PS 以正确物理尺寸打开 | 无单位 px（AI 按 72 DPI 解读，偏大 2.78×） |
| 禁止放大 | 元素 PNG 禁止；背景允许等比缩小 | 元素放大会损失印刷质量；背景缩小是内容驱动的必要操作 | 全禁（导致窄幅城市被跳过） |

---

## 7. 已知限制与待处理项

| # | 类型 | 描述 | 状态 |
|---|---|---|---|
| L-01 | 待评审 | 元素定位规则（成品框 %）与背景缩放后罐子视觉位置的对齐关系 | 📋 待专项评审 |
| L-02 | 待验证 | 罐心锚点坐标 (3280, 5935) 需在 PS/AI 中人工复核 | 📋 待确认 |
| L-03 | 待扩展 | 元素比例规则（5.2）精确数值需更多训练图验证 | 📋 待补充 |
| L-04 | 边界 | 排版规则为手工 Brief，暂不涉及 AI 视觉自动识别 | 已知限制 |
| L-05 | 边界 | SVG 为 RGB 色彩空间，印刷交付需经 Illustrator 转 CMYK | 已知限制 |

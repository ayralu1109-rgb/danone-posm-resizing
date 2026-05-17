# POSM 自动排版系统 — 架构文档

> 版本：0.3 · 更新日期：2026-05-18 · 配套需求：`POC_miniprd.md`

---

## 1. 系统概览

```
输入物料
  ├── Master BG（bg2000*2000.png，200 DPI，2000×2000mm）
  ├── 元素 PNGs（1/2/3/4/6，含透明通道）
  └── 规格表（Excel，城市 × 画布/成品框尺寸）
         │
         ▼
  ┌──────────────────────────────┐
  │   Processing Engine          │  main.py
  │   Step 1–6 主流程            │
  └──────────┬───────────────────┘
             │  调用 Template 公共接口（唯一契约）
             ▼
  ┌──────────────────────────────┐
  │   Template Package           │  template/
  │   bg_crop.py      背景裁切   │
  │   element_layout.py 元素定位 │
  │   layer_order.py  图层顺序   │
  └──────────────────────────────┘
         │
         ▼
输出（per city）
  └── {城市}_{尺寸}mm.zip
        ├── {城市}_{尺寸}mm.svg
        └── assets/
              ├── bg.png
              └── 1/2/3/4/6 元素 PNGs
```

**设计原则：**
- Processing Engine 只调用 Template 公共接口，不感知内部实现
- 换活动/换背景 = 替换 Template 包，Processing Engine 不动
- 元素原始文件全程不修改；背景允许裁切 + 等比缩小，禁止放大

---

## 2. 处理流程（Step 1–6）

| Step | 名称 | 输入 | 输出 | 执行者 |
|---|---|---|---|---|
| 1 | 读取规格 | Excel | `List[CitySpec]` | Processing Engine |
| 2 | 背景裁切 | Master BG + 画布尺寸 | `assets/bg.png` | `Template.crop_bg()` |
| 3 | 成品框定位 | 画布 + 成品框尺寸 | `(trim_x, trim_y)` | Processing Engine |
| 4a | 元素坐标计算 | 成品框 + 元素原始尺寸 | `layout dict` | `Template.compute_layout()` |
| 4b | 元素复制 | 元素 PNG 源文件 | `assets/元素.png` | Processing Engine |
| 5 | 构建 SVG | layout + 画布尺寸 | `.svg` 文件 | Processing Engine |
| 6 | 打包输出 | SVG + assets/ | `.zip` 文件 | Processing Engine |

异常（主底图不足、元素需放大、锚点越界）在 Step 2/4a 抛出，Processing Engine 捕获后整行跳过并记录，全批次结束后汇总输出。

---

## 3. Template 公共接口

Template 包（`template/`）暴露三个函数，是与 Processing Engine 的**唯一契约**。

### 3.1 `crop_bg(bg_src_path, canvas_w_px, canvas_h_px, output_path) → str`

背景锚点裁切。

**行为：**
1. 计算裁切区：`crop_w = CONTENT_REF_W_PX / CONTENT_FILL_RATIO`，`crop_h` 按画布宽高比推导
2. 锚点定位：罐心 `(CAN_CX, CAN_CY)` 落在裁切区的 `(CAN_TARGET_X, CAN_TARGET_Y)` 处
3. `Image.crop()` + `Image.resize(LANCZOS)` 缩放至画布尺寸
4. 写入 `dpi=(200, 200)`，保存到 `output_path`

**异常：**
- `ValueError`：主底图小于裁切区，或裁切框越界 → Processing Engine 整行跳过

### 3.2 `compute_layout(trim_w_px, trim_h_px, trim_offset_x, trim_offset_y, element_sizes) → dict`

元素定位计算。

**返回：** `{filename: {"x": int, "y": int, "w": int, "h": int}}`，坐标为画布绝对像素。

**异常：**
- `UpscaleError(element_name, original_w, target_w)`：任意元素需放大时抛出 → Processing Engine 整行跳过

### 3.3 `get_element_render_order() → list[str]`

返回元素文件名的 SVG 渲染顺序（bottom → top），不含 bg.png 和成品框。

---

## 4. Template 可配置参数

每套活动/素材对应一套 Template。以下参数在 `template/` 内部定义，Processing Engine 不感知。

### 4.1 背景裁切参数（`bg_crop.py`）

| 参数 | PoC 当前值 | 说明 |
|---|---|---|
| `CAN_CX` | `6568` px（≈ 834mm） | 罐心在主底图的 X 坐标 |
| `CAN_CY` | `9183` px（≈ 1166mm） | 罐心在主底图的 Y 坐标 |
| `CAN_TARGET_X` | `0.311` | 罐心落在裁切区宽度的 31.1% 处 |
| `CAN_TARGET_Y` | `0.638` | 罐心落在裁切区高度的 63.8% 处 |
| `CONTENT_REF_W_MM` | `960.0` mm | 内容参考框宽度（`5罐子+背景+helix+买点.png` 的物理宽） |
| `CONTENT_FILL_RATIO` | `1.036` | 参考框宽 / 裁切区宽。= 1.036 时内容块占画布约 90% |
| `SOURCE_DPI` | `200` | 主底图及输出 DPI |

> **CONTENT_FILL_RATIO 说明：** 参考框（960mm）内实际内容块（罐子左缘→文案右缘）≈ 835mm（87% of 960mm）。目标内容块占画布 90% → 裁切区宽 = 835/0.90 ≈ 928mm → ratio = 960/928 ≈ 1.036。  
> 📋 **TODO（T-05）**：当前值基于 328/420mm 画布视觉验证，宽格式（580mm+）需重新校准。

### 4.2 元素定位参数（`element_layout.py`）

| 元素 | 目标宽度（成品框 W 的 %） | PoC 取值 |
|---|---|---|
| 1 顶部联合 logo | 55–65% | 60% |
| 2 标题文字 | 85–95% | 90% |
| 6 原装进口 | 25–30% | 27.5% |
| 3 脚注 | 80–90% | 85% |
| 4 右下角 logo | 15–20% | 17.5% |

### 4.3 图层顺序（`layer_order.py`）

```
bg.png → 2标题无蒙版 → 6原装进口 → 1顶部联合logo → 3脚注 → 4右下角logo → 成品框
```

---

## 5. 数据结构

### `CitySpec`（`main.py`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `city` | str | 城市名 |
| `canvas_w_mm` / `canvas_h_mm` | float | 画布尺寸（mm） |
| `trim_w_mm` / `trim_h_mm` | float | 成品框尺寸（mm） |

派生属性（property）：`canvas_w_px`、`canvas_h_px`、`trim_w_px`、`trim_h_px`、`slug`

---

## 6. 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| 输出格式 | SVG + assets ZIP | 原始像素保留、AI 可编辑、内存占用低 |
| 背景裁切 | 锚点裁切 + Lanczos resize | 不同尺寸画布均能看到完整内容；resize 保证最高下采样质量 |
| 裁切比例参数 | `CONTENT_FILL_RATIO` 在 Template 内定义 | 换活动只改 Template，Processing Engine 不动 |
| 元素处理 | 复制原文件，SVG 路径引用 | 零像素损失，文件轻量 |
| SVG 尺寸单位 | `width/height` 用 mm，`viewBox` 用 px | Illustrator 以正确物理尺寸打开（避免 72DPI 误解读） |
| 调试属性 | `data-*-mm` 附加到所有 `<image>/<rect>` | 不影响渲染，Inspector 可直接读取毫米尺寸 |

---

## 7. 已知限制与待处理项

| # | 类型 | 描述 | 状态 |
|---|---|---|---|
| T-01 | 待验证 | 元素排版视觉验证（元素+背景合成整体效果） | 📋 待做 |
| T-02 | 待验证 | 元素比例规则精确数值（当前基于 7 张训练图） | 📋 待补充 |
| T-03 | 待开发 | Excel 输入数据校验（可视尺寸 > 画面尺寸时提前报错） | 📋 待开发 |
| T-04 | 待决策 | UpscaleError 处理策略：严格跳过 vs 半成品输出 | 📋 待决策 |
| T-05 | 待校准 | `CONTENT_FILL_RATIO` 宽格式（580mm+）动态校准 | 📋 待未来 |
| T-06 | 待确认 | 罐心坐标 `(6568, 9183)` 需在 PS/AI 中人工核验 | 📋 待确认 |
| L-01 | 已知限制 | 排版规则为手工 Brief，暂不涉及 AI 视觉自动识别 | 已知 |
| L-02 | 已知限制 | SVG 为 RGB，印刷交付需在 Illustrator 转 CMYK | 已知 |

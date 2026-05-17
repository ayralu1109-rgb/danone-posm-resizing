# POSM 自动排版 — Bug List

> 更新日期：2026-05-14

---

## BUG-001 · SVG 在 Illustrator / Photoshop 中画布尺寸偏大 2.78 倍

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复 |
| **发现日期** | 2026-05-14 |
| **修复日期** | 2026-05-14 |
| **影响文件** | `main.py` → `build_svg()` |

### 现象

SVG 拖入 Illustrator / Photoshop 后，画布显示为约 **1167mm × 1583mm**，而非预期的 **420mm × 570mm**。宽高比例正确，但物理尺寸约为预期的 2.78 倍。

### 根本原因

SVG 规范中，`width`/`height` 属性如果写成**无单位数字**（如 `width="3307"`），不同软件对"1个单位等于多少英寸"有不同假设：

| 软件 | 假设 | 换算结果 |
|---|---|---|
| 现代浏览器 | 1px = 1/96 英寸（CSS px） | 3307 ÷ 96 × 25.4 = **874mm** |
| Illustrator / PS | 1px = 1pt = 1/72 英寸 | 3307 ÷ 72 × 25.4 = **1167mm** ← 实际观察值 |
| 我们的意图 | 1px = 1/200 英寸（200 DPI） | 3307 ÷ 200 × 25.4 = **420mm** ✓ |

SVG 文件本身没有 DPI 元数据，所以 Illustrator 按自己的默认值（72 DPI）读取，导致画布被放大了 `200 ÷ 72 ≈ 2.78` 倍。

### 修复方案

在 SVG 根元素的 `width`/`height` 属性中**明确写入 mm 单位**，同时保留 `viewBox` 的像素坐标系不变：

```xml
<!-- 修复前 -->
<svg width="3307" height="4488" viewBox="0 0 3307 4488">

<!-- 修复后 -->
<svg width="420mm" height="570mm" viewBox="0 0 3307 4488">
```

- `width`/`height`（mm）→ 告诉 Illustrator 物理画布是多大
- `viewBox`（px）→ 内部坐标系保持 200 DPI 精度，元素位置不受影响
- 反推 DPI：`3307px ÷ (420mm ÷ 25.4) = 200 DPI` ✓

---

---

## BUG-002 · 裁切后的 bg.png DPI 元数据丢失（72 PPI → 应为 200 PPI）

| 字段 | 内容 |
|---|---|
| **状态** | ✅ 已修复 |
| **发现日期** | 2026-05-14 |
| **修复日期** | 2026-05-14 |
| **影响文件** | `template/bg_crop.py` → `crop_bg()` |

### 现象

生成的 `assets/bg.png` 在 Illustrator / Photoshop 中显示为 **72 PPI**，而原始主底图为 200 PPI。像素数据本身未被修改，但 DPI 元数据丢失。

### 根本原因

Pillow 的 `Image.crop()` 会保留内存中的 DPI 信息，但 `.save(path, format="PNG")` 在未显式传入 `dpi` 参数时，**不会将 DPI 写入 PNG 的 `pHYs` 元数据块**，导致保存后 DPI 信息消失，软件回退默认值 72 PPI。

### 修复方案

在 `save()` 调用时显式传入 `dpi` 参数：

```python
# 修复前
cropped.save(output_path, format="PNG")

# 修复后
cropped.save(output_path, format="PNG", dpi=(200, 200))
```

像素数据全程未被修改，修复仅补写了 `pHYs` 元数据块。

<!-- 新 bug 追加在此处 -->

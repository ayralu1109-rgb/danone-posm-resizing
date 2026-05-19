import json
import os
from PIL import Image

def mm_to_px(mm: float, dpi: int = 200) -> int:
    return int(round(mm * dpi / 25.4))

def get_element_sizes(png_dir: str):
    sizes = {}
    elements = [
        "1顶部联合 logo.png",
        "2标题无蒙版.png",
        "3脚注.png",
        "4右下角 logo.png",
        "6原装进口.png"
    ]
    for el in elements:
        path = os.path.join(png_dir, el)
        if os.path.exists(path):
            with Image.open(path) as img:
                sizes[el] = img.size
        else:
            print(f"Warning: {el} not found in {png_dir}, using mock size.")
            sizes[el] = (1000, 300) # Mock size
    return sizes

def compute_dynamic_layout(trim_w_px: int, trim_h_px: int, trim_offset_x: int, trim_offset_y: int, element_sizes: dict):
    """
    基于锚点和伴生关系的动态排版算法
    """
    W = trim_w_px
    H = trim_h_px
    ox = trim_offset_x
    oy = trim_offset_y
    
    layout = {}
    
    # ---------------------------------------------------------
    # 核心锚点 1：标题 (Element 2)
    # ---------------------------------------------------------
    el_name = "2标题无蒙版.png"
    ow, oh = element_sizes[el_name]
    tw = int(W * 0.85) # 占成品框宽度 85%
    tw = min(tw, ow)   # 【硬性约束】绝对禁止拉伸
    th = int(oh * tw / ow)
    x2 = ox + int(W * 0.04) # 距左侧安全边距 4%
    y2 = oy + int(H * 0.12) # 距顶部 12%
    layout[el_name] = {"x": x2, "y": y2, "w": tw, "h": th}
    
    # ---------------------------------------------------------
    # 伴生元素 A：顶部联合Logo (Element 1)
    # ---------------------------------------------------------
    el_name = "1顶部联合 logo.png"
    ow, oh = element_sizes[el_name]
    # 【关联约束】宽度为“标题宽度的 60%”
    tw = int(layout["2标题无蒙版.png"]["w"] * 0.6) 
    tw = min(tw, ow)
    th = int(oh * tw / ow)
    
    x1 = ox + int((W - tw) / 2) # X轴绝对居中
    # 【碰撞约束】Y轴基于标题向上推（间距设定为标题高度的15%）
    y1 = int(y2 - th - layout["2标题无蒙版.png"]["h"] * 0.15)
    # 【防出界兜底】如果算出来超出安全区顶部，强行压在距离顶部 2% 的安全线内
    y1 = max(y1, oy + int(H * 0.02))
    layout[el_name] = {"x": x1, "y": y1, "w": tw, "h": th}
    
    # ---------------------------------------------------------
    # 伴生元素 B：原装进口 (Element 6)
    # ---------------------------------------------------------
    el_name = "6原装进口.png"
    ow, oh = element_sizes[el_name]
    # 【关联约束】宽度等于“标题宽度的 30%”
    tw = int(layout["2标题无蒙版.png"]["w"] * 0.3)
    tw = min(tw, ow)
    th = int(oh * tw / ow)
    
    x6 = x2 # X轴与标题左对齐
    # 【碰撞约束】在标题正下方，向下推（间距设定为标题高度的10%）
    y6 = y2 + layout["2标题无蒙版.png"]["h"] + int(layout["2标题无蒙版.png"]["h"] * 0.1)
    layout[el_name] = {"x": x6, "y": y6, "w": tw, "h": th}
    
    # ---------------------------------------------------------
    # 核心锚点 2：脚注 (Element 3) - 底部独立锚点
    # ---------------------------------------------------------
    el_name = "3脚注.png"
    ow, oh = element_sizes[el_name]
    tw = int(W * 0.85)
    tw = min(tw, ow)
    th = int(oh * tw / ow)
    x3 = x2
    y3 = oy + H - th - int(H * 0.04) # 固定在底部安全线（往上推 4%）
    layout[el_name] = {"x": x3, "y": y3, "w": tw, "h": th}
    
    # ---------------------------------------------------------
    # 伴生元素 C：右下角Logo (Element 4)
    # ---------------------------------------------------------
    el_name = "4右下角 logo.png"
    ow, oh = element_sizes[el_name]
    # 【关联约束】宽度等于“脚注宽度的 20%”
    tw = int(layout["3脚注.png"]["w"] * 0.2)
    tw = min(tw, ow)
    th = int(oh * tw / ow)
    
    x4 = ox + W - tw - int(W * 0.04) # 靠右停靠
    # 【碰撞约束】底部严格与“脚注的底部”在同一水平线上
    y4 = layout["3脚注.png"]["y"] + layout["3脚注.png"]["h"] - th
    layout[el_name] = {"x": x4, "y": y4, "w": tw, "h": th}
    
    return layout

if __name__ == "__main__":
    png_dir = "png元素"
    print(f"正在读取 {png_dir} 中真实元素的像素尺寸...")
    element_sizes = get_element_sizes(png_dir)
    print("真实元素尺寸:", element_sizes)
    print("-" * 50)
    
    # 测试城市 1：湛江
    # 画布：420x570mm，成品框：405x555mm
    z_canvas_w, z_canvas_h = mm_to_px(420), mm_to_px(570)
    z_trim_w, z_trim_h = mm_to_px(405), mm_to_px(555)
    z_ox = (z_canvas_w - z_trim_w) // 2
    z_oy = (z_canvas_h - z_trim_h) // 2
    
    print("\n【测试场景 1：湛江】")
    print(f"  - 画布尺寸: 420x570mm ({z_canvas_w}x{z_canvas_h} px)")
    print(f"  - 成品框尺寸: 405x555mm ({z_trim_w}x{z_trim_h} px)")
    print(f"  - 偏移: x={z_ox}, y={z_oy}")
    
    z_layout = compute_dynamic_layout(z_trim_w, z_trim_h, z_ox, z_oy, element_sizes)
    print("  - 动态排版结果:")
    print(json.dumps(z_layout, indent=4, ensure_ascii=False))

    # 测试城市 2：汕头
    # 画布：328x470mm，成品框：292x440mm
    s_canvas_w, s_canvas_h = mm_to_px(328), mm_to_px(470)
    s_trim_w, s_trim_h = mm_to_px(292), mm_to_px(440)
    s_ox = (s_canvas_w - s_trim_w) // 2
    s_oy = (s_canvas_h - s_trim_h) // 2
    
    print("\n【测试场景 2：汕头】")
    print(f"  - 画布尺寸: 328x470mm ({s_canvas_w}x{s_canvas_h} px)")
    print(f"  - 成品框尺寸: 292x440mm ({s_trim_w}x{s_trim_h} px)")
    print(f"  - 偏移: x={s_ox}, y={s_oy}")
    
    s_layout = compute_dynamic_layout(s_trim_w, s_trim_h, s_ox, s_oy, element_sizes)
    print("  - 动态排版结果:")
    print(json.dumps(s_layout, indent=4, ensure_ascii=False))

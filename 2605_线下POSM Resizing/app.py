"""
app.py  —  POSM 自动排版演示界面
=========================================
启动：python3 app.py
浏览器打开：http://localhost:8080
"""

from __future__ import annotations

import io
import logging
import os
import signal
import shutil
import tempfile
import zipfile
from pathlib import Path

from flask import Flask, jsonify, request, send_file

# 复用 main.py 中的处理逻辑
from main import (
    BG_PATH,
    ELEMENTS_DIR,
    CitySpec,
    _load_element_sizes,
    process_city,
)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")

# 预加载元素尺寸（只读一次）
ELEMENT_SIZES = _load_element_sizes(ELEMENTS_DIR)

# 各元素目标宽度占成品框宽的比例（与 element_layout.py 保持一致）
_ELEM_TRIM_W_RATIOS: dict[str, float] = {
    "title.png":       0.85,
    "top_logo.png":    0.85 * 0.50,
    "imported.png":    0.15,
    "footnote.png":    0.72,
    "corner_logo.png": 0.12,
}
_DPI = 200

# 计算成品框宽度上限：对所有元素，orig_w / ratio 就是最大 trim_w_px
# 取最小值（最严格约束），换算为 mm 并向下取整
TRIM_MAX_W_MM: int = int(min(
    ELEMENT_SIZES[fname][0] / ratio * (25.4 / _DPI)
    for fname, ratio in _ELEM_TRIM_W_RATIOS.items()
    if fname in ELEMENT_SIZES
))
logging.info("元素像素约束：成品框宽度上限 = %d mm", TRIM_MAX_W_MM)

# ---------------------------------------------------------------------------
# HTML 页面（单文件，无需 templates/ 目录）
# ---------------------------------------------------------------------------
PAGE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>POSM 自动排版</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif;
      background: #f0f2f5;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }

    .card {
      background: #fff;
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(0,0,0,.08);
      padding: 40px 48px;
      width: 100%;
      max-width: 540px;
    }

    .logo {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 28px;
    }
    .logo-dot {
      width: 10px; height: 10px; border-radius: 50%;
      background: linear-gradient(135deg,#0066cc,#00aaff);
    }
    .logo span { font-size: 13px; color: #888; letter-spacing: .04em; text-transform: uppercase; }

    h1 { font-size: 22px; font-weight: 700; color: #111; margin-bottom: 6px; }
    .subtitle { font-size: 13px; color: #888; margin-bottom: 32px; }

    .section-label {
      font-size: 11px;
      font-weight: 600;
      color: #0066cc;
      letter-spacing: .08em;
      text-transform: uppercase;
      margin-bottom: 10px;
    }

    .size-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 20px;
    }
    .size-row input[type=number] {
      flex: 1;
      border: 1.5px solid #e0e0e0;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 16px;
      color: #111;
      outline: none;
      transition: border-color .15s;
      -moz-appearance: textfield;
    }
    .size-row input[type=number]::-webkit-inner-spin-button,
    .size-row input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; }
    .size-row input[type=number]:focus { border-color: #0066cc; }
    .size-sep { font-size: 18px; color: #bbb; flex-shrink: 0; }
    .size-unit { font-size: 13px; color: #999; flex-shrink: 0; }

    .field { margin-bottom: 24px; }
    .field label { display: block; font-size: 13px; font-weight: 600; color: #444; margin-bottom: 8px; }
    .field input[type=text] {
      width: 100%;
      border: 1.5px solid #e0e0e0;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 15px;
      color: #111;
      outline: none;
      transition: border-color .15s;
    }
    .field input[type=text]:focus { border-color: #0066cc; }

    .hint { font-size: 11px; color: #bbb; margin-top: 4px; }

    .divider { border: none; border-top: 1px solid #f0f0f0; margin: 28px 0; }

    .btn {
      width: 100%;
      padding: 13px;
      border: none;
      border-radius: 10px;
      font-size: 16px;
      font-weight: 600;
      cursor: pointer;
      transition: opacity .15s, transform .1s;
    }
    .btn:active { transform: scale(.98); }
    .btn-primary {
      background: linear-gradient(135deg, #0066cc, #0088ff);
      color: #fff;
    }
    .btn-primary:disabled { opacity: .5; cursor: not-allowed; }

    /* Result area */
    #result { margin-top: 24px; display: none; }

    .result-success {
      background: #f0faf4;
      border: 1.5px solid #34c759;
      border-radius: 10px;
      padding: 16px 20px;
    }
    .result-error {
      background: #fff2f2;
      border: 1.5px solid #ff3b30;
      border-radius: 10px;
      padding: 16px 20px;
    }
    .result-title { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
    .result-success .result-title { color: #1a7a3d; }
    .result-error   .result-title { color: #c0392b; }
    .result-body { font-size: 13px; color: #555; line-height: 1.6; }

    .btn-download {
      display: inline-block;
      margin-top: 14px;
      padding: 10px 22px;
      background: #34c759;
      color: #fff;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 600;
      text-decoration: none;
      transition: opacity .15s;
    }
    .btn-download:hover { opacity: .88; }

    /* Spinner */
    .spinner {
      display: inline-block;
      width: 16px; height: 16px;
      border: 2px solid rgba(255,255,255,.4);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin .7s linear infinite;
      vertical-align: middle;
      margin-right: 8px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Stats row */
    .stats { display: flex; gap: 16px; margin-top: 12px; }
    .stat { background: #f7f9fc; border-radius: 8px; padding: 10px 14px; flex: 1; }
    .stat-label { font-size: 10px; color: #999; text-transform: uppercase; letter-spacing: .06em; }
    .stat-value { font-size: 15px; font-weight: 700; color: #111; margin-top: 2px; }
  </style>
</head>
<body>
<div class="card">

  <div class="logo">
    <div class="logo-dot"></div>
    <span>Danone POSM Auto-Layout</span>
  </div>

  <h1>线下 POSM 自动排版</h1>
  <p class="subtitle">输入城市与两个尺寸，一键生成 SVG 交付包</p>

  <form id="form">

    <div class="field">
      <label>城市名称</label>
      <input type="text" id="city" placeholder="例：湛江" required/>
    </div>

    <div class="section-label">① 画面尺寸（画布 / 大尺寸）</div>
    <div class="size-row">
      <input type="number" id="cw" placeholder="宽度" min="150" step="0.1" required/>
      <span class="size-sep">×</span>
      <input type="number" id="ch" placeholder="高度" min="150" step="0.1" required/>
      <span class="size-unit">mm</span>
    </div>
    <p class="hint" style="margin-top:-14px;margin-bottom:4px;">背景将从主底图居中裁切至此尺寸</p>
    <p id="canvas-warn" class="hint" style="margin-bottom:20px;color:#ff3b30;display:none;"></p>

    <div class="section-label">② 可视尺寸（成品框 / 小尺寸）</div>
    <div class="size-row">
      <input type="number" id="tw" placeholder="宽度" min="150" step="0.1" required/>
      <span class="size-sep">×</span>
      <input type="number" id="th" placeholder="高度" min="150" step="0.1" required/>
      <span class="size-unit">mm</span>
    </div>
    <p class="hint" style="margin-top:-14px;margin-bottom:4px;">红色成品框居中叠加，元素定位基准（宽度最大 __TRIM_MAX_W_MM__ mm）</p>
    <p id="trim-warn" class="hint" style="margin-bottom:24px;color:#ff3b30;display:none;"></p>

    <hr class="divider"/>
    <button class="btn btn-primary" type="submit" id="submitBtn">生成 ZIP 交付包</button>
  </form>

  <div id="result"></div>
</div>

<script>
const form       = document.getElementById('form');
const resultDiv  = document.getElementById('result');
const submitBtn  = document.getElementById('submitBtn');
const canvasWarn = document.getElementById('canvas-warn');
const trimWarn   = document.getElementById('trim-warn');
const MIN_MM          = 150;
const TRIM_MIN_RATIO  = 0.80;   // 可视尺寸最小为画面尺寸的 80%（真实数据下限 ~88%，此处留安全余量）
const TRIM_MAX_W_MM   = __TRIM_MAX_W_MM__;  // 由元素 PNG 原始像素决定的成品框宽度上限

function validateFields() {
  const cw = parseFloat(document.getElementById('cw').value);
  const ch = parseFloat(document.getElementById('ch').value);
  const tw = parseFloat(document.getElementById('tw').value);
  const th = parseFloat(document.getElementById('th').value);
  let hasError = false;

  // 画面尺寸校验
  let canvasMsg = '';
  if (cw > 0 && cw < MIN_MM) canvasMsg = `⚠️ 宽度不能小于 ${MIN_MM}mm`;
  else if (ch > 0 && ch < MIN_MM) canvasMsg = `⚠️ 高度不能小于 ${MIN_MM}mm`;
  else if (cw > 0 && ch > 0 && cw >= ch) canvasMsg = '⚠️ 高度必须大于宽度（仅支持竖版）';
  canvasWarn.textContent = canvasMsg;
  canvasWarn.style.display = canvasMsg ? 'block' : 'none';
  if (canvasMsg) hasError = true;

  // 可视尺寸校验
  let trimMsg = '';
  if (tw > 0 && tw < MIN_MM) {
    trimMsg = `⚠️ 宽度不能小于 ${MIN_MM}mm`;
  } else if (th > 0 && th < MIN_MM) {
    trimMsg = `⚠️ 高度不能小于 ${MIN_MM}mm`;
  } else if (tw > 0 && th > 0 && tw >= th) {
    trimMsg = '⚠️ 高度必须大于宽度（仅支持竖版）';
  } else if (cw > 0 && tw > 0 && tw >= cw) {
    trimMsg = '⚠️ 可视宽度必须小于画面宽度';
  } else if (ch > 0 && th > 0 && th >= ch) {
    trimMsg = '⚠️ 可视高度必须小于画面高度';
  } else if (cw > 0 && tw > 0 && tw < cw * TRIM_MIN_RATIO) {
    const minW = Math.ceil(cw * TRIM_MIN_RATIO);
    trimMsg = `⚠️ 可视宽度偏小（最小约 ${minW}mm，即画面宽度的 ${Math.round(TRIM_MIN_RATIO*100)}%）`;
  } else if (ch > 0 && th > 0 && th < ch * TRIM_MIN_RATIO) {
    const minH = Math.ceil(ch * TRIM_MIN_RATIO);
    trimMsg = `⚠️ 可视高度偏小（最小约 ${minH}mm，即画面高度的 ${Math.round(TRIM_MIN_RATIO*100)}%）`;
  } else if (tw > 0 && tw > TRIM_MAX_W_MM) {
    trimMsg = `⚠️ 可视宽度超出上限（当前 ${tw}mm，最大 ${TRIM_MAX_W_MM}mm）——元素 PNG 原始像素不足，放大会模糊`;
  }
  trimWarn.textContent = trimMsg;
  trimWarn.style.display = trimMsg ? 'block' : 'none';
  if (trimMsg) hasError = true;

  submitBtn.disabled = hasError;
}

['cw','ch','tw','th'].forEach(id =>
  document.getElementById(id).addEventListener('input', validateFields)
);

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const city = document.getElementById('city').value.trim();
  const cw   = parseFloat(document.getElementById('cw').value);
  const ch   = parseFloat(document.getElementById('ch').value);
  const tw   = parseFloat(document.getElementById('tw').value);
  const th   = parseFloat(document.getElementById('th').value);

  if (cw >= ch) {
    showError('画面尺寸：高度必须大于宽度（仅支持竖版）。');
    return;
  }
  if (tw >= th) {
    showError('可视尺寸：高度必须大于宽度（仅支持竖版）。');
    return;
  }
  if ([cw, ch, tw, th].some(v => v < MIN_MM)) {
    showError(`所有尺寸不能小于 ${MIN_MM}mm。`);
    return;
  }

  if (tw >= cw || th >= ch) {
    showError('可视尺寸必须小于画面尺寸，请检查输入。');
    return;
  }
  if (tw < cw * TRIM_MIN_RATIO) {
    showError(`可视宽度 ${tw}mm 偏小（画面宽 ${cw}mm，可视宽应 ≥ ${Math.ceil(cw * TRIM_MIN_RATIO)}mm）。`);
    return;
  }
  if (th < ch * TRIM_MIN_RATIO) {
    showError(`可视高度 ${th}mm 偏小（画面高 ${ch}mm，可视高应 ≥ ${Math.ceil(ch * TRIM_MIN_RATIO)}mm）。`);
    return;
  }
  if (tw > TRIM_MAX_W_MM) {
    showError(`可视宽度 ${tw}mm 超出上限（最大 ${TRIM_MAX_W_MM}mm）——元素 PNG 原始像素不足，放大会模糊。`);
    return;
  }

  submitBtn.disabled = true;
  submitBtn.innerHTML = '<span class="spinner"></span>处理中…';
  resultDiv.style.display = 'none';

  try {
    const resp = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ city, cw, ch, tw, th }),
    });
    const data = await resp.json();

    if (data.ok) {
      showSuccess(data);
    } else {
      showError(data.error);
    }
  } catch (err) {
    showError('网络错误：' + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = '生成 ZIP 交付包';
  }
});

function showSuccess(data) {
  resultDiv.innerHTML = `
    <div class="result-success">
      <div class="result-title">✅ 生成成功</div>
      <div class="result-body">${data.slug}</div>
      <div class="stats">
        <div class="stat">
          <div class="stat-label">画布</div>
          <div class="stat-value">${data.canvas_px}</div>
        </div>
        <div class="stat">
          <div class="stat-label">成品框</div>
          <div class="stat-value">${data.trim_px}</div>
        </div>
      </div>
      <a class="btn-download" href="/download/${data.zip_name}" download>
        ⬇ 下载 ${data.zip_name}
      </a>
    </div>`;
  resultDiv.style.display = 'block';
}

function showError(msg) {
  resultDiv.innerHTML = `
    <div class="result-error">
      <div class="result-title">⚠️ 生成失败</div>
      <div class="result-body">${msg}</div>
    </div>`;
  resultDiv.style.display = 'block';
}
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    html = PAGE_HTML.replace("__TRIM_MAX_W_MM__", str(TRIM_MAX_W_MM))
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/generate", methods=["POST"])
def generate():
    body = request.get_json(force=True)

    try:
        city = str(body["city"]).strip()
        cw   = float(body["cw"])
        ch   = float(body["ch"])
        tw   = float(body["tw"])
        th   = float(body["th"])
    except (KeyError, ValueError) as exc:
        return jsonify(ok=False, error=f"参数错误：{exc}"), 400

    # 尺寸校验：四个值均 ≥ 150mm，竖版，且可视尺寸在合理范围内（80%~100% 画面尺寸）
    MIN_MM        = 150.0
    TRIM_MIN_RATIO = 0.80   # 真实数据下限约 88%，此处取 80% 作为宽松安全下限
    for label, val in [("画面宽度", cw), ("画面高度", ch), ("可视宽度", tw), ("可视高度", th)]:
        if val < MIN_MM:
            return jsonify(ok=False, error=f"{label} {val:.0f}mm 过小，最小允许值为 {MIN_MM:.0f}mm"), 400
    if cw >= ch:
        return jsonify(ok=False, error=f"画面尺寸必须是竖版（高 > 宽），当前 {cw:.0f}×{ch:.0f}mm"), 400
    if tw >= th:
        return jsonify(ok=False, error=f"可视尺寸必须是竖版（高 > 宽），当前 {tw:.0f}×{th:.0f}mm"), 400
    if tw >= cw:
        return jsonify(ok=False, error=f"可视宽度（{tw:.0f}mm）必须小于画面宽度（{cw:.0f}mm）"), 400
    if th >= ch:
        return jsonify(ok=False, error=f"可视高度（{th:.0f}mm）必须小于画面高度（{ch:.0f}mm）"), 400
    if tw < cw * TRIM_MIN_RATIO:
        return jsonify(ok=False, error=(
            f"可视宽度 {tw:.0f}mm 偏小（画面宽 {cw:.0f}mm，"
            f"可视宽应 ≥ {cw * TRIM_MIN_RATIO:.0f}mm，即画面宽的 {TRIM_MIN_RATIO*100:.0f}%）"
        )), 400
    if th < ch * TRIM_MIN_RATIO:
        return jsonify(ok=False, error=(
            f"可视高度 {th:.0f}mm 偏小（画面高 {ch:.0f}mm，"
            f"可视高应 ≥ {ch * TRIM_MIN_RATIO:.0f}mm，即画面高的 {TRIM_MIN_RATIO*100:.0f}%）"
        )), 400
    if tw > TRIM_MAX_W_MM:
        return jsonify(ok=False, error=(
            f"可视宽度 {tw:.0f}mm 超出上限 {TRIM_MAX_W_MM}mm——"
            f"元素 PNG 原始像素不足（放大会模糊）。请缩小成品框宽度。"
        )), 400

    spec = CitySpec(
        city=city,
        canvas_w_mm=cw,
        canvas_h_mm=ch,
        trim_w_mm=tw,
        trim_h_mm=th,
    )

    # Use a temp directory as the output target for this request
    tmp_dir = Path(tempfile.mkdtemp(prefix="posm_"))

    try:
        process_city(
            spec=spec,
            bg_path=BG_PATH,
            elements_dir=ELEMENTS_DIR,
            element_sizes=ELEMENT_SIZES,
            output_dir=tmp_dir,
        )
    except Exception as exc:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(ok=False, error=str(exc)), 200

    zip_name = f"{spec.slug}.zip"
    zip_path = tmp_dir / zip_name

    if not zip_path.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return jsonify(ok=False, error="ZIP 未生成，请检查日志"), 200

    # Move ZIP to a stable location so /download can serve it
    stable_dir = Path(__file__).parent / "output"
    stable_dir.mkdir(exist_ok=True)
    dest = stable_dir / zip_name
    shutil.move(str(zip_path), str(dest))
    shutil.rmtree(tmp_dir, ignore_errors=True)

    return jsonify(
        ok=True,
        slug=spec.slug,
        zip_name=zip_name,
        canvas_px=f"{spec.canvas_w_px} × {spec.canvas_h_px} px",
        trim_px=f"{spec.trim_w_px} × {spec.trim_h_px} px",
    )


@app.route("/health")
def health():
    return jsonify(status="ok"), 200


@app.route("/download/<path:filename>")
def download(filename: str):
    zip_path = Path(__file__).parent / "output" / filename
    if not zip_path.exists():
        return "文件不存在", 404
    return send_file(str(zip_path), as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _handle_sigterm(signum, frame):
    logging.info("Received SIGTERM, shutting down gracefully...")
    raise SystemExit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _handle_sigterm)
    port = int(os.environ.get("PORT", 8080))
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║  POSM 自动排版演示界面已启动           ║")
    print(f"  ║  浏览器打开 → http://localhost:{port}    ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    app.run(host="0.0.0.0", port=port, debug=False)

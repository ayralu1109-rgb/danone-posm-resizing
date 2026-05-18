"""
app.py  —  POSM 自动排版演示界面
=========================================
启动：python3 app.py
浏览器打开：http://localhost:5000
"""

from __future__ import annotations

import io
import logging
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
      <input type="number" id="cw" placeholder="宽" min="1" step="0.1" required/>
      <span class="size-sep">×</span>
      <input type="number" id="ch" placeholder="高" min="1" step="0.1" required/>
      <span class="size-unit">mm</span>
    </div>
    <p class="hint" style="margin-top:-14px;margin-bottom:4px;">背景将从主底图居中裁切至此尺寸</p>
    <p id="orientation-warn" class="hint" style="margin-bottom:20px;color:#ff3b30;display:none;">
      ⚠️ 仅支持竖版（高 &gt; 宽）。横版 / 方形暂不支持。
    </p>

    <div class="section-label">② 可视尺寸（成品框 / 小尺寸）</div>
    <div class="size-row">
      <input type="number" id="tw" placeholder="宽" min="1" step="0.1" required/>
      <span class="size-sep">×</span>
      <input type="number" id="th" placeholder="高" min="1" step="0.1" required/>
      <span class="size-unit">mm</span>
    </div>
    <p class="hint" style="margin-top:-14px;margin-bottom:24px;">红色成品框居中叠加，元素定位基准</p>

    <hr class="divider"/>
    <button class="btn btn-primary" type="submit" id="submitBtn">生成 ZIP 交付包</button>
  </form>

  <div id="result"></div>
</div>

<script>
const form       = document.getElementById('form');
const resultDiv  = document.getElementById('result');
const submitBtn  = document.getElementById('submitBtn');
const orientWarn = document.getElementById('orientation-warn');

function checkOrientation() {
  const cw = parseFloat(document.getElementById('cw').value);
  const ch = parseFloat(document.getElementById('ch').value);
  const isLandscapeOrSquare = cw > 0 && ch > 0 && cw >= ch;
  orientWarn.style.display = isLandscapeOrSquare ? 'block' : 'none';
  submitBtn.disabled = isLandscapeOrSquare;
}
document.getElementById('cw').addEventListener('input', checkOrientation);
document.getElementById('ch').addEventListener('input', checkOrientation);

form.addEventListener('submit', async (e) => {
  e.preventDefault();

  const city = document.getElementById('city').value.trim();
  const cw   = parseFloat(document.getElementById('cw').value);
  const ch   = parseFloat(document.getElementById('ch').value);
  const tw   = parseFloat(document.getElementById('tw').value);
  const th   = parseFloat(document.getElementById('th').value);

  if (cw >= ch) {
    showError('仅支持竖版（高 > 宽）。横版 / 方形暂不支持。');
    return;
  }

  if (tw >= cw || th >= ch) {
    showError('可视尺寸必须小于画面尺寸，请检查输入。');
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
    return PAGE_HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


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


@app.route("/download/<path:filename>")
def download(filename: str):
    zip_path = Path(__file__).parent / "output" / filename
    if not zip_path.exists():
        return "文件不存在", 404
    return send_file(str(zip_path), as_attachment=True, download_name=filename)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║  POSM 自动排版演示界面已启动           ║")
    print("  ║  浏览器打开 → http://localhost:8080    ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    app.run(host="0.0.0.0", port=8080, debug=False)

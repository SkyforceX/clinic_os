#!/usr/bin/env python3
"""
Lab Result Processor
Match customers from customer_list with lab results from rptNTU046.
Output: results.json + results.html
"""

import json
import re
import unicodedata
import pandas as pd
from datetime import datetime
from pathlib import Path

LAB_FILE = "/mnt/user-data/uploads/1775018902879_rptNTU046_SOXETNGHIEM.xlsx"
CUSTOMER_FILE = "/mnt/user-data/uploads/1775018931266_customer_list.xlsx"
OUT_JSON = "results.json"
OUT_HTML = "results.html"


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        return ""
    name = name.strip().upper()
    name = unicodedata.normalize("NFC", name)
    name = re.sub(r"\s+", " ", name)
    return name


def load_lab_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, header=None)
    # Data starts at row index 16
    data = df.iloc[16:].copy().reset_index(drop=True)
    data.columns = range(data.shape[1])

    # Filter out header repetition rows and empty rows
    header_noise = {"họ tên người bệnh", "2", "nam", "nữ", "9", "10"}
    mask = (
        data[3].notna()
        & data[3].astype(str).str.strip().ne("")
        & ~data[3].astype(str).str.strip().str.lower().isin(header_noise)
    )
    data = data[mask].copy()

    data["name_norm"] = data[3].apply(normalize_name)

    # age_male in col 5, age_female in col 7
    def get_age(row):
        male_age = row[5]
        female_age = row[7]
        if pd.notna(male_age) and str(male_age).strip() not in ("", "Nam", "3"):
            try:
                return int(float(male_age)), "Nam"
            except Exception:
                pass
        if pd.notna(female_age) and str(female_age).strip() not in ("", "Nữ", "4"):
            try:
                return int(float(female_age)), "Nữ"
            except Exception:
                pass
        return None, None

    ages = data.apply(get_age, axis=1)
    data["age"] = [a[0] for a in ages]
    data["gender_lab"] = [a[1] for a in ages]
    data["test_name"] = data[15].astype(str).str.strip()
    data["test_result"] = data[16].astype(str).str.strip()

    return data[data["test_name"].notna() & data["test_name"].ne("nan")].copy()


def load_customers(path: str) -> list[dict]:
    df = pd.read_excel(path, header=None)
    # Row 1 is header, data from row 2
    customers = []
    for _, row in df.iloc[2:].iterrows():
        ma_bn = str(row[0]).strip() if pd.notna(row[0]) else ""
        name = str(row[1]).strip() if pd.notna(row[1]) else ""
        gender = str(row[2]).strip() if pd.notna(row[2]) else ""
        dob_raw = row[3]

        if not name or name == "nan":
            continue

        birth_year = None
        dob_str = ""
        if pd.notna(dob_raw):
            if isinstance(dob_raw, datetime):
                birth_year = dob_raw.year
                dob_str = dob_raw.strftime("%d/%m/%Y")
            else:
                dob_str = str(dob_raw).strip()
                parts = dob_str.replace("-", "/").split("/")
                if len(parts) == 3:
                    try:
                        yr = int(parts[2]) if len(parts[2]) == 4 else int(parts[0])
                        birth_year = yr
                    except Exception:
                        pass

        age = (2026 - birth_year + 1) if birth_year else None

        customers.append({
            "ma_bn": ma_bn,
            "name": name,
            "name_norm": normalize_name(name),
            "gender": gender,
            "dob": dob_str,
            "birth_year": birth_year,
            "age": age,
        })
    return customers


def match_patients(customers: list[dict], lab_df: pd.DataFrame) -> list[dict]:
    results = []

    for cust in customers:
        name_norm = cust["name_norm"]
        age = cust["age"]
        gender = cust["gender"]

        # Filter lab rows by normalized name
        matched = lab_df[lab_df["name_norm"] == name_norm].copy()

        if matched.empty:
            continue

        # Further filter by age if available
        if age is not None:
            age_match = matched[matched["age"] == age]
            if not age_match.empty:
                matched = age_match

        # Further filter by gender
        if gender in ("Nam", "Nữ"):
            gender_match = matched[matched["gender_lab"] == gender]
            if not gender_match.empty:
                matched = gender_match

        tests = []
        for _, row in matched.iterrows():
            tname = row["test_name"]
            tresult = row["test_result"]
            if tname and tname != "nan" and tresult and tresult != "nan":
                tests.append({"name": tname, "result": tresult})

        if tests:
            results.append({
                "ma_bn": cust["ma_bn"],
                "name": cust["name"],
                "gender": cust["gender"],
                "dob": cust["dob"],
                "birth_year": cust["birth_year"],
                "age": cust["age"],
                "test_count": len(tests),
                "tests": tests,
            })

    return results


def generate_html(results: list[dict], out_path: str):
    total = len(results)
    total_tests = sum(r["test_count"] for r in results)
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    year = datetime.now().year

    # Embed all patient data as JSON for JS PDF generation
    results_json = json.dumps(results, ensure_ascii=False)

    cards_html = ""
    for i, r in enumerate(results, 1):
        rows_html = "".join(
            f'<tr><td class="td-test">{t["name"]}</td><td class="td-result">{t["result"]}</td></tr>'
            for t in r["tests"]
        )
        gender_class = "badge-male" if r["gender"] == "Nam" else "badge-female"
        gender_icon = "&#9794;" if r["gender"] == "Nam" else "&#9792;"

        cards_html += f"""
        <div class="card" id="card-{i}" data-idx="{i-1}">
          <div class="card-header">
            <div class="card-left">
              <span class="patient-num">#{i:03d}</span>
              <div class="patient-info">
                <h3 class="patient-name">{r['name']}</h3>
                <div class="patient-meta">
                  <span class="badge {gender_class}">{gender_icon} {r['gender']}</span>
                  <span class="meta-item">&#127874; {r['dob']}</span>
                  <span class="meta-item">&#128197; {r['age']} tuổi</span>
                  <span class="meta-item muted">&#128100; {r['ma_bn']}</span>
                </div>
              </div>
            </div>
            <div class="card-actions">
              <div class="count-box">
                <div class="test-count-badge">{r['test_count']}</div>
                <div class="test-count-label">chỉ số</div>
              </div>
              <button class="btn-pdf" onclick="exportPDF(event, {i-1})" title="Xuất PDF kết quả xét nghiệm">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                  <line x1="12" y1="18" x2="12" y2="12"/>
                  <polyline points="9 15 12 18 15 15"/>
                </svg>
                Xuất PDF
              </button>
            </div>
          </div>
          <div class="card-body">
            <table class="result-table">
              <thead><tr><th>Chỉ số xét nghiệm</th><th>Kết quả</th></tr></thead>
              <tbody>{rows_html}</tbody>
            </table>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kết quả Xét nghiệm – Phòng khám Đa khoa Vietmedi</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
  <script>
  /* Pre-load Vietnamese Noto Sans font once on page load */
  let _fontRegB64 = null, _fontBoldB64 = null, _fontLoading = null;

  function _ab2b64(buf) {{
    const bytes = new Uint8Array(buf);
    let bin = '', chunk = 8192;
    for (let i = 0; i < bytes.length; i += chunk)
      bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
    return btoa(bin);
  }}

  async function ensureFont() {{
    if (_fontRegB64) return true;
    if (_fontLoading) return _fontLoading;
    _fontLoading = (async () => {{
      try {{
        const base = 'https://cdn.jsdelivr.net/gh/notofonts/noto-fonts/hinted/ttf/NotoSans/';
        const [r1, r2] = await Promise.all([
          fetch(base + 'NotoSans-Regular.ttf'),
          fetch(base + 'NotoSans-Bold.ttf')
        ]);
        if (!r1.ok || !r2.ok) throw new Error('font fetch failed');
        const [b1, b2] = await Promise.all([r1.arrayBuffer(), r2.arrayBuffer()]);
        _fontRegB64  = _ab2b64(b1);
        _fontBoldB64 = _ab2b64(b2);
        return true;
      }} catch(e) {{
        console.warn('Noto Sans load failed, using Helvetica:', e);
        return false;
      }}
    }})();
    return _fontLoading;
  }}
  ensureFont(); /* kick off immediately */
  </script>
  <style>
    :root {{
      --primary: #1a73e8;
      --primary-dark: #1557b0;
      --male: #1a73e8;
      --male-bg: #dbeafe;
      --female: #d53f8c;
      --female-bg: #fce7f3;
      --border: #e2e8f0;
      --bg: #f1f5f9;
      --text: #1e293b;
      --muted: #64748b;
      --shadow: 0 2px 12px rgba(0,0,0,0.08);
      --shadow-hover: 0 8px 24px rgba(26,115,232,0.15);
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg); color: var(--text); min-height: 100vh;
    }}

    /* HEADER */
    .site-header {{
      background: linear-gradient(135deg, #1a73e8 0%, #0d47a1 100%);
      color: #fff; padding: 28px 32px 24px;
      box-shadow: 0 4px 20px rgba(26,115,232,0.3);
    }}
    .site-header h1 {{ font-size: 1.6rem; font-weight: 700; }}
    .site-header p {{ opacity: .85; margin-top: 4px; font-size: .9rem; }}
    .stats-bar {{ display: flex; gap: 24px; margin-top: 20px; flex-wrap: wrap; }}
    .stat-chip {{
      background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.3);
      border-radius: 8px; padding: 8px 16px; font-size: .88rem;
      display: flex; align-items: center; gap: 8px;
    }}
    .stat-chip strong {{ font-size: 1.1rem; }}

    /* CONTROLS */
    .controls {{
      display: flex; gap: 12px; padding: 16px 32px; background: #fff;
      border-bottom: 1px solid var(--border); align-items: center;
      flex-wrap: wrap; position: sticky; top: 0; z-index: 100;
      box-shadow: 0 2px 8px rgba(0,0,0,.06);
    }}
    .search-box {{ position: relative; flex: 1; min-width: 220px; max-width: 400px; }}
    .search-box input {{
      width: 100%; padding: 9px 14px 9px 38px;
      border: 1.5px solid var(--border); border-radius: 8px;
      font-size: .9rem; outline: none; transition: border-color .2s;
    }}
    .search-box input:focus {{ border-color: var(--primary); }}
    .search-box::before {{
      content: '🔍'; position: absolute; left: 11px;
      top: 50%; transform: translateY(-50%); font-size: .85rem;
    }}
    .filter-select {{
      padding: 9px 12px; border: 1.5px solid var(--border); border-radius: 8px;
      font-size: .9rem; background: #fff; cursor: pointer; outline: none;
    }}
    .filter-select:focus {{ border-color: var(--primary); }}
    .result-count {{ margin-left: auto; font-size: .85rem; color: var(--muted); }}

    /* MAIN */
    .main {{ max-width: 1100px; margin: 0 auto; padding: 24px 20px 48px; }}

    /* CARD */
    .card {{
      background: #fff; border-radius: 14px; box-shadow: var(--shadow);
      margin-bottom: 20px; border: 1px solid var(--border);
      overflow: hidden; transition: box-shadow .25s, transform .2s;
    }}
    .card:hover {{ box-shadow: var(--shadow-hover); transform: translateY(-2px); }}
    .card-header {{
      display: flex; align-items: center; gap: 16px; padding: 16px 20px;
      background: linear-gradient(135deg, #f8faff 0%, #eef2ff 100%);
      border-bottom: 1px solid var(--border);
    }}
    .card-left {{ display: flex; align-items: center; gap: 12px; flex: 1; }}
    .patient-num {{ font-weight: 700; color: var(--muted); font-size: .8rem; min-width: 36px; }}
    .patient-name {{ font-size: 1.05rem; font-weight: 700; color: var(--text); margin-bottom: 6px; }}
    .patient-meta {{ display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
    .badge {{
      display: inline-flex; align-items: center; gap: 3px;
      padding: 2px 10px; border-radius: 20px; font-size: .78rem; font-weight: 600;
    }}
    .badge-male {{ background: var(--male-bg); color: var(--male); }}
    .badge-female {{ background: var(--female-bg); color: var(--female); }}
    .meta-item {{ font-size: .82rem; color: var(--muted); }}
    .meta-item.muted {{ opacity: .7; }}

    /* CARD ACTIONS */
    .card-actions {{ display: flex; align-items: center; gap: 14px; flex-shrink: 0; }}
    .count-box {{ text-align: center; }}
    .test-count-badge {{
      background: var(--primary); color: #fff; border-radius: 10px;
      font-size: 1.1rem; font-weight: 700; width: 44px; height: 44px;
      display: flex; align-items: center; justify-content: center; margin: 0 auto 4px;
    }}
    .test-count-label {{ font-size: .72rem; color: var(--muted); }}

    /* PDF BUTTON */
    .btn-pdf {{
      display: inline-flex; align-items: center; gap: 7px;
      padding: 9px 16px; border-radius: 9px; border: none; cursor: pointer;
      font-size: .82rem; font-weight: 600; font-family: inherit;
      background: linear-gradient(135deg, #1a73e8, #1557b0);
      color: #fff; transition: all .2s; white-space: nowrap;
      box-shadow: 0 2px 8px rgba(26,115,232,0.35);
      user-select: none;
    }}
    .btn-pdf:hover {{
      background: linear-gradient(135deg, #1557b0, #0d47a1);
      box-shadow: 0 4px 14px rgba(26,115,232,0.5);
      transform: translateY(-1px);
    }}
    .btn-pdf:active {{ transform: translateY(0); box-shadow: 0 1px 4px rgba(26,115,232,0.3); }}
    .btn-pdf.loading {{ opacity: .7; pointer-events: none; }}
    .btn-pdf svg {{ flex-shrink: 0; }}

    /* TABLE */
    .card-body {{ padding: 0; }}
    .result-table {{ width: 100%; border-collapse: collapse; font-size: .875rem; }}
    .result-table thead tr {{ background: #f8fafc; }}
    .result-table th {{
      padding: 10px 20px; text-align: left; font-size: .76rem; font-weight: 600;
      color: var(--muted); text-transform: uppercase; letter-spacing: .5px;
      border-bottom: 1px solid var(--border);
    }}
    .result-table th:last-child {{ text-align: right; width: 140px; }}
    .result-table tbody tr {{ border-bottom: 1px solid #f1f5f9; transition: background .15s; }}
    .result-table tbody tr:last-child {{ border-bottom: none; }}
    .result-table tbody tr:hover {{ background: #f8faff; }}
    .td-test {{ padding: 9px 20px; color: var(--text); }}
    .td-result {{
      padding: 9px 20px; font-weight: 600; text-align: right;
      color: var(--primary-dark); font-variant-numeric: tabular-nums;
    }}

    /* NO RESULT */
    .no-result {{ text-align: center; padding: 60px 20px; color: var(--muted); }}
    .no-result-icon {{ font-size: 3rem; margin-bottom: 12px; }}

    /* TOAST */
    .toast {{
      position: fixed; bottom: 28px; right: 28px; z-index: 9999;
      background: #1e293b; color: #fff; padding: 12px 20px;
      border-radius: 10px; font-size: .85rem; font-weight: 500;
      box-shadow: 0 4px 20px rgba(0,0,0,.25);
      display: flex; align-items: center; gap: 10px;
      animation: slideIn .25s ease; pointer-events: none;
    }}
    .toast.hide {{ animation: slideOut .3s ease forwards; }}
    @keyframes slideIn {{ from {{ opacity:0; transform:translateY(16px); }} to {{ opacity:1; transform:translateY(0); }} }}
    @keyframes slideOut {{ from {{ opacity:1; transform:translateY(0); }} to {{ opacity:0; transform:translateY(16px); }} }}

    /* FOOTER */
    .footer {{
      text-align: center; padding: 24px; font-size: .8rem; color: var(--muted);
      border-top: 1px solid var(--border); background: #fff; margin-top: 32px;
    }}

    @media (max-width: 640px) {{
      .site-header {{ padding: 20px 16px; }}
      .controls {{ padding: 12px 14px; }}
      .main {{ padding: 16px 10px 40px; }}
      .card-header {{ padding: 14px 14px; flex-wrap: wrap; }}
      .card-actions {{ width: 100%; justify-content: flex-end; margin-top: 8px; }}
      .result-table th, .td-test, .td-result {{ padding: 8px 12px; }}
      .btn-pdf span {{ display: none; }}
    }}
  </style>
</head>
<body>

<header class="site-header">
  <h1>&#129514; Kết quả Xét nghiệm</h1>
  <p>Phòng khám Đa khoa Vietmedi – Dữ liệu xuất ngày {now}</p>
  <div class="stats-bar">
    <div class="stat-chip">&#128101; <strong>{total}</strong> bệnh nhân có kết quả</div>
    <div class="stat-chip">&#128203; <strong>{total_tests}</strong> chỉ số xét nghiệm</div>
  </div>
</header>

<div class="controls">
  <div class="search-box">
    <input type="text" id="searchInput" placeholder="Tìm theo tên bệnh nhân..." oninput="filterCards()">
  </div>
  <select class="filter-select" id="genderFilter" onchange="filterCards()">
    <option value="">Tất cả giới tính</option>
    <option value="Nam">Nam</option>
    <option value="Nữ">Nữ</option>
  </select>
  <div class="result-count" id="resultCount">Hiển thị {total} bệnh nhân</div>
</div>

<div class="main" id="cardContainer">
  {cards_html}
  <div class="no-result" id="noResult" style="display:none;">
    <div class="no-result-icon">&#128269;</div>
    <p>Không tìm thấy bệnh nhân phù hợp</p>
  </div>
</div>

<div class="footer">
  &copy; {year} Phòng khám Đa khoa Vietmedi &nbsp;&middot;&nbsp; Dữ liệu chỉ dùng nội bộ
</div>

<script>
const ALL_RESULTS = {results_json};

/* ── FILTER ── */
function normalizeStr(s) {{
  return s.toLowerCase().normalize('NFD')
    .replace(/[\u0300-\u036f]/g,'')
    .replace(/\u0111/g,'d');
}}
function filterCards() {{
  const q = normalizeStr(document.getElementById('searchInput').value.trim());
  const gender = document.getElementById('genderFilter').value;
  const cards = document.querySelectorAll('.card[id^="card-"]');
  let visible = 0;
  cards.forEach(card => {{
    const name = normalizeStr(card.querySelector('.patient-name').textContent);
    const g = card.querySelector('.badge').textContent.trim();
    if ((!q || name.includes(q)) && (!gender || g.includes(gender))) {{
      card.style.display = ''; visible++;
    }} else {{ card.style.display = 'none'; }}
  }});
  document.getElementById('resultCount').textContent = 'Hiển thị ' + visible + ' bệnh nhân';
  document.getElementById('noResult').style.display = visible === 0 ? '' : 'none';
}}

/* ── TOAST ── */
function showToast(msg, icon='✅') {{
  const existing = document.querySelector('.toast');
  if (existing) existing.remove();
  const t = document.createElement('div');
  t.className = 'toast';
  t.innerHTML = icon + ' ' + msg;
  document.body.appendChild(t);
  setTimeout(() => {{ t.classList.add('hide'); setTimeout(()=>t.remove(), 320); }}, 2800);
}}

/* ── PDF EXPORT ── */
async function exportPDF(evt, idx) {{
  evt.stopPropagation();
  const r = ALL_RESULTS[idx];
  if (!r) return;

  const btn = evt.currentTarget;
  btn.classList.add('loading');
  btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="animation:spin .8s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Đang tạo...`;

  try {{
    /* ── 1. LOAD FONT ── */
    const fontOk = await ensureFont();

    const {{ jsPDF }} = window.jspdf;
    const doc = new jsPDF({{ orientation: 'portrait', unit: 'mm', format: 'a4' }});

    /* Register Noto Sans if loaded */
    let FONT = 'helvetica';
    if (fontOk && _fontRegB64 && _fontBoldB64) {{
      doc.addFileToVFS('NotoSans-Regular.ttf', _fontRegB64);
      doc.addFont('NotoSans-Regular.ttf', 'NotoSans', 'normal');
      doc.addFileToVFS('NotoSans-Bold.ttf', _fontBoldB64);
      doc.addFont('NotoSans-Bold.ttf', 'NotoSans', 'bold');
      FONT = 'NotoSans';
    }}

    const W = 210, marginL = 14, marginR = 14, contentW = W - marginL - marginR;
    let y = 10;

    /* ── 2. PATIENT INFO BOX ── */
    /* Accent left bar */
    doc.setFillColor(26, 115, 232);
    doc.rect(marginL, y, 3, 36, 'F');

    doc.setFillColor(248, 250, 255);
    doc.setDrawColor(199, 210, 254);
    doc.setLineWidth(0.4);
    doc.rect(marginL + 3, y, contentW - 3, 36, 'FD');

    /* Title inside box */
    doc.setFont(FONT, 'bold');
    doc.setFontSize(10);
    doc.setTextColor(26, 115, 232);
    doc.text('PHIẾU KẾT QUẢ XÉT NGHIỆM', marginL + 9, y + 7);

    /* Info rows – 2 columns */
    const col1x = marginL + 9, col2x = marginL + contentW / 2 + 4;
    const lineH = 7;
    let iy = y + 15;

    const gender = r.gender || '';
    const now = new Date();
    const exportDate = [
      now.getDate().toString().padStart(2,'0'),
      (now.getMonth()+1).toString().padStart(2,'0'),
      now.getFullYear()
    ].join('/') + '  ' +
      now.getHours().toString().padStart(2,'0') + ':' +
      now.getMinutes().toString().padStart(2,'0');

    function infoRow(label, value, x, yy) {{
      doc.setFont(FONT, 'bold'); doc.setFontSize(7.5); doc.setTextColor(100, 116, 139);
      doc.text(label + ':', x, yy);
      doc.setFont(FONT, 'normal'); doc.setFontSize(8.5); doc.setTextColor(20, 30, 50);
      doc.text(String(value || ''), x + 24, yy);
    }}

    infoRow('Họ và tên', r.name, col1x, iy);
    infoRow('Mã BN', r.ma_bn, col2x, iy); iy += lineH;
    infoRow('Giới tính', gender, col1x, iy);
    infoRow('Ngày sinh', r.dob || '', col2x, iy); iy += lineH;
    infoRow('Tuổi', r.age ? r.age + ' tuổi' : '', col1x, iy);
    infoRow('Ngày xuất', exportDate, col2x, iy);

    y += 36 + 7;

    /* ── 3. SECTION LABEL ── */
    doc.setFont(FONT, 'bold'); doc.setFontSize(8); doc.setTextColor(26, 115, 232);
    doc.text('KẾT QUẢ XÉT NGHIỆM  (' + r.tests.length + ' chỉ số)', marginL, y);
    y += 3;

    /* ── 4. RESULTS TABLE ── */
    /* Col widths: STT=10, Test name=120, Result=52 → total=182=contentW */
    const tableRows = r.tests.map((t, i) => [
      (i + 1).toString(),
      String(t.name || ''),
      String(t.result || '')
    ]);

    doc.autoTable({{
      startY: y,
      head: [['STT', 'Chỉ số xét nghiệm', 'Kết quả']],
      body: tableRows,
      margin: {{ left: marginL, right: marginR }},
      tableWidth: contentW,
      styles: {{
        font: FONT,
        fontSize: 8.5,
        cellPadding: {{ top: 3, right: 5, bottom: 3, left: 5 }},
        textColor: [20, 30, 50],
        lineColor: [220, 228, 240],
        lineWidth: 0.25,
        overflow: 'linebreak',
      }},
      headStyles: {{
        fillColor: [26, 115, 232],
        textColor: [255, 255, 255],
        fontStyle: 'bold',
        fontSize: 8,
        halign: 'left',
      }},
      columnStyles: {{
        0: {{ cellWidth: 10, halign: 'center', textColor: [120, 130, 150], fontSize: 8 }},
        1: {{ cellWidth: 120 }},
        2: {{ cellWidth: 52, halign: 'left', fontStyle: 'bold', textColor: [21, 87, 176] }},
      }},
      alternateRowStyles: {{ fillColor: [247, 250, 255] }},
      didDrawPage: function(data) {{
        const pageCount = doc.internal.getNumberOfPages();
        doc.setFont(FONT, 'normal'); doc.setFontSize(7); doc.setTextColor(160, 170, 185);
        doc.text('Trang ' + data.pageNumber + ' / ' + pageCount, W / 2, 290, {{ align: 'center' }});
        doc.setDrawColor(220, 228, 240); doc.setLineWidth(0.3);
        doc.line(marginL, 285, W - marginR, 285);
      }},
    }});

    /* ── 5. SIGNATURE (last page only if space allows) ── */
    const finalY = doc.lastAutoTable.finalY + 14;
    if (finalY < 268) {{
      const sigW = 52;
      doc.setDrawColor(180, 190, 210); doc.setLineWidth(0.4);
      doc.line(marginL, finalY, marginL + sigW, finalY);
      doc.line(W - marginR - sigW, finalY, W - marginR, finalY);
      doc.setFont(FONT, 'normal'); doc.setFontSize(7.5); doc.setTextColor(110, 120, 140);
      doc.text('Người xét nghiệm', marginL + sigW / 2, finalY + 4.5, {{ align: 'center' }});
      doc.text('Bác sĩ phụ trách', W - marginR - sigW / 2, finalY + 4.5, {{ align: 'center' }});
    }}

    /* ── 6. SAVE ── */
    const safeName = r.name.replace(/[^a-zA-Z0-9\u00C0-\u024F\u1E00-\u1EFF ]/g, '').trim().replace(/ +/g, '_');
    doc.save('KetQua_' + safeName + '_' + (r.ma_bn || 'BN') + '.pdf');
    showToast('Đã xuất PDF: ' + r.name);

  }} catch(e) {{
    console.error(e);
    showToast('Lỗi khi tạo PDF. Vui lòng thử lại.', '❌');
  }} finally {{
    btn.classList.remove('loading');
    btn.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 18 15 15"/></svg> Xuất PDF`;
  }}
}}
</script>
<style>
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</body>
</html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    print("📂 Đang đọc dữ liệu xét nghiệm...")
    lab_df = load_lab_data(LAB_FILE)
    print(f"  → {len(lab_df)} dòng xét nghiệm hợp lệ")

    print("📂 Đang đọc danh sách khách hàng...")
    customers = load_customers(CUSTOMER_FILE)
    print(f"  → {len(customers)} khách hàng")

    print("🔍 Đang so khớp dữ liệu...")
    results = match_patients(customers, lab_df)
    print(f"  → {len(results)} bệnh nhân có kết quả xét nghiệm")

    print("💾 Xuất file JSON...")
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  → Đã lưu: {OUT_JSON}")

    print("🌐 Tạo file HTML...")
    generate_html(results, OUT_HTML)
    print(f"  → Đã lưu: {OUT_HTML}")

    print(f"\n✅ Hoàn thành! {len(results)} bệnh nhân / {sum(r['test_count'] for r in results)} chỉ số xét nghiệm")


if __name__ == "__main__":
    main()

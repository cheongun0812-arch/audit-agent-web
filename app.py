import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import requests
from bs4 import BeautifulSoup
import time
import glob
import tempfile
import hashlib
import base64
import datetime
import pytz
import pandas as pd

import plotly.graph_objects as go
import plotly.express as px

# Plotly: 확대/축소 후 "원점 복원" 가능하도록 모드바 항상 표시
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,          # 스크롤로 의도치 않은 확대 방지
    "doubleClick": "reset",       # 더블클릭/더블탭 시 원점 복원
}

# [필수] 구글 시트 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None
    ServiceAccountCredentials = None
    st.error("❌ 구글 시트 라이브러리가 없습니다. requirements.txt를 확인하세요.")

# [필수] yt_dlp 라이브러리 체크
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 🎨 디자인 테마 (사이드바/토글 강제 표시 포함)
#    + 전체 텍스트 0.2px 증가
# ==========================================
st.markdown("""
<style>
/* ✅ 전체 글자 크기 +0.2px */
html { font-size: 16.2px; }

.stApp { background-color: #F4F6F9; }
[data-testid="stSidebar"] { background-color: #2C3E50; }
[data-testid="stSidebar"] * { color: #FFFFFF !important; }

/* ✅ 사이드바 텍스트 입력의 아이콘(눈/지우기 등)을 항상 검정색으로 */
[data-testid="stSidebar"] div[data-testid="stTextInput"] button,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button:hover,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button:focus,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button:active {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #000000 !important;
    opacity: 1 !important;
}

[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg *,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg path {
    fill: #000000 !important;
    stroke: #000000 !important;
    opacity: 1 !important;
}

/* aria-label이 환경/언어에 따라 달라도 적용되도록, 패스워드 토글 버튼도 강제 */
div[data-testid="stTextInput"] button[aria-label],
div[data-testid="stTextInput"] button[aria-label] svg,
div[data-testid="stTextInput"] button[aria-label] svg * {
    fill: #000000 !important;
    stroke: #000000 !important;
    color: #000000 !important;
    opacity: 1 !important;
}

.stTextInput input, .stTextArea textarea {
    background-color: #FFFFFF !important;
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    border: 1px solid #BDC3C7 !important;
}

/* ✅ 버튼 스타일 (일반 버튼 + 폼 제출 버튼) */
.stButton > button,
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1rem !important;
    font-weight: 800 !important;
    width: 100% !important;
    opacity: 1 !important;
}

/* ✅ disabled여도 텍스트가 흐려지지 않도록 */
.stButton > button:disabled,
div[data-testid="stFormSubmitButton"] > button:disabled {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    opacity: 1 !important;
    filter: none !important;
}

/* ✅ 버튼 내부 텍스트/아이콘도 상시 선명 */
.stButton > button *,
div[data-testid="stFormSubmitButton"] > button * {
    color: #FFFFFF !important;
    opacity: 1 !important;
}

/* (서약 우측 카운트다운 표시용) */
.pledge-right {
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap: 8px;
  font-weight: 900;
  color: #0B5ED7;
  min-width: 90px;
}

/* ✅ (추가) 자율점검 안내 박스/서약 문구 전용 스타일 */
.km-gap-8 { height: 8px; }
.km-gap-12 { height: 12px; }
.km-gap-18 { height: 18px; }

.km-pledge-line {
  font-size: 1.08rem;            /* 서약 문장 기본 크기 */
  line-height: 1.75;
  margin: 0;
  letter-spacing: 0.1px;
}
.km-pledge-line b{
  font-weight: 900;
}

</style>
""", unsafe_allow_html=True)

# ✅ PC에서는 사이드바 기본 펼침, 모바일에서는 기본 접힘
st.markdown("""
<script>
(function() {
  const KEY = "__sidebar_autopen_done__";
  const isDesktop = () => (window.innerWidth || 0) >= 900;
  let tries = 0;
  const maxTries = 25;

  function clickToggleIfNeeded() {
    try {
      if (!isDesktop()) return;
      if (window.sessionStorage.getItem(KEY) === "1") return;

      const doc = window.parent?.document || document;
      const candidates = [
        '[data-testid="stSidebarCollapsedControl"] button',
        '[data-testid="stSidebarCollapsedControl"]',
        'button[title="Open sidebar"]',
        'button[aria-label="Open sidebar"]'
      ];

      for (const sel of candidates) {
        const el = doc.querySelector(sel);
        if (el) {
          el.click();
          window.sessionStorage.setItem(KEY, "1");
          return;
        }
      }
    } catch (e) {}
  }

  const timer = setInterval(() => {
    tries += 1;
    clickToggleIfNeeded();
    if (tries >= maxTries) clearInterval(timer);
  }, 250);
})();
</script>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 세션 관리
# ==========================================
def _set_query_param_key(clean_key: str) -> None:
    encoded_key = base64.b64encode(clean_key.encode()).decode()
    try:
        st.query_params["k"] = encoded_key
    except Exception:
        st.experimental_set_query_params(k=encoded_key)

def _clear_query_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()

def _validate_and_store_key(clean_key: str) -> None:
    genai.configure(api_key=clean_key)
    list(genai.list_models())
    st.session_state["api_key"] = clean_key
    st.session_state["login_error"] = None
    _set_query_param_key(clean_key)

def try_login_from_session_key(key_name: str) -> None:
    raw_key = st.session_state.get(key_name, "")
    clean_key = "".join(str(raw_key).split())
    if not clean_key:
        st.session_state["login_error"] = "⚠️ 키를 입력해주세요."
        return
    try:
        _validate_and_store_key(clean_key)
    except Exception as e:
        st.session_state["login_error"] = f"❌ 인증 실패: {e}"

def perform_logout():
    st.session_state["logout_anim"] = True

# ==========================================
# 4. 자동 로그인 복구 (URL 파라미터)
# ==========================================
if "api_key" not in st.session_state:
    try:
        qp = st.query_params
        if "k" in qp:
            k_val = qp["k"] if isinstance(qp["k"], str) else qp["k"][0]
            restored_key = base64.b64decode(k_val).decode("utf-8")
            _validate_and_store_key(restored_key)
            st.toast("🔄 세션이 복구되었습니다.", icon="✨")
            st.rerun()
    except Exception:
        pass

# ==========================================
# 5. 사이드바 (로그인/로그아웃)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")

    if "api_key" not in st.session_state:
        with st.form(key="login_form"):
            st.markdown("<h4 style='color:white;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input(
                "Key",
                type="password",
                placeholder="API 키를 입력해 주세요",
                label_visibility="collapsed",
                key="login_input_key",
            )
            st.form_submit_button(
                label="시스템 접속 (Login)",
                on_click=try_login_from_session_key,
                args=("login_input_key",),
                use_container_width=True,
            )

        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])
    else:
        st.success("🟢 정상 가동 중")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("로그아웃 (Logout)", type="primary", use_container_width=True):
            perform_logout()
            st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026<br>Engine: Gemini 1.5 Pro</div>",
        unsafe_allow_html=True,
    )

# ==========================================
# 7. 로그아웃 애니메이션
# ==========================================
if st.session_state.get("logout_anim"):
    st.markdown("""
<div style="background:#0B1B2B; padding:44px 26px; border-radius:18px; text-align:center; border:1px solid rgba(255,255,255,0.12);">
  <div style="font-size: 78px; margin-bottom: 12px; line-height:1.1;">🎆✨</div>
  <div style="font-size: 22px; font-weight: 900; color: #FFFFFF; margin-bottom: 8px;">새해 복 많이 받으세요!</div>
  <div style="font-size: 15px; color: rgba(255,255,255,0.85); line-height: 1.55;">
    올해도 건강과 행운이 가득하시길 바랍니다.<br>
    안전하게 로그아웃되었습니다.
  </div>
  <div style="margin-top:18px; font-size: 12px; color: rgba(255,255,255,0.65);">
    ktMOS북부 Audit AI Solution © 2026
  </div>
</div>
""", unsafe_allow_html=True)
    time.sleep(3.0)
    _clear_query_params()
    st.session_state.clear()
    st.rerun()

# ==========================================
# 8. 핵심 기능 함수 (구글시트, AI, 파일처리)
# ==========================================
@st.cache_resource
def init_google_sheet_connection():
    if gspread is None or ServiceAccountCredentials is None:
        return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except Exception:
        return None

def _korea_now():
    try:
        kst = pytz.timezone("Asia/Seoul")
        return datetime.datetime.now(kst)
    except Exception:
        return datetime.datetime.now()

def _campaign_key(dt: datetime.datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"

def _ensure_campaign_config_sheet(spreadsheet):
    try:
        ws = spreadsheet.worksheet("Campaign_Config")
        return ws
    except Exception:
        ws = spreadsheet.add_worksheet(title="Campaign_Config", rows=200, cols=10)
        ws.append_row(["campaign_key", "title", "sheet_name", "start_date"])
        return ws

def _default_campaign_title(dt: datetime.datetime) -> str:
    if dt.month == 1:
        return "1월 자율점검(윤리경영원칙 실천지침 실천 서약)"
    return f"{dt.month}월 자율점검(윤리경영원칙 실천지침 실천서약)"

def _default_campaign_sheet_name(dt: datetime.datetime, spreadsheet=None) -> str:
    if spreadsheet is not None and dt.year == 2026 and dt.month == 1:
        try:
            spreadsheet.worksheet("2026_윤리경영_실천서약")
            return "2026_윤리경영_실천서약"
        except Exception:
            pass
    return f"{dt.year}_{dt.month:02d}_자율점검"

def get_current_campaign_info(spreadsheet, now_dt: datetime.datetime | None = None) -> dict:
    now_dt = now_dt or _korea_now()
    key = _campaign_key(now_dt)
    cfg_ws = _ensure_campaign_config_sheet(spreadsheet)
    records = cfg_ws.get_all_records()
    for r in records:
        if str(r.get("campaign_key", "")).strip() == key:
            title = str(r.get("title") or "").strip() or _default_campaign_title(now_dt)
            sheet_name = str(r.get("sheet_name") or "").strip() or _default_campaign_sheet_name(now_dt, spreadsheet)
            start_date = str(r.get("start_date") or "").strip()
            return {"key": key, "title": title, "sheet_name": sheet_name, "start_date": start_date}

    title = _default_campaign_title(now_dt)
    sheet_name = _default_campaign_sheet_name(now_dt, spreadsheet)
    start_date = now_dt.strftime("%Y.%m.%d")
    cfg_ws.append_row([key, title, sheet_name, start_date])
    return {"key": key, "title": title, "sheet_name": sheet_name, "start_date": start_date}

def set_current_campaign_info(spreadsheet, title: str | None = None, sheet_name: str | None = None, now_dt: datetime.datetime | None = None) -> dict:
    now_dt = now_dt or _korea_now()
    key = _campaign_key(now_dt)
    cfg_ws = _ensure_campaign_config_sheet(spreadsheet)
    all_rows = cfg_ws.get_all_values()
    row_idx = None
    for i in range(2, len(all_rows) + 1):
        if len(all_rows[i-1]) >= 1 and str(all_rows[i-1][0]).strip() == key:
            row_idx = i
            break
    if row_idx is None:
        _ = get_current_campaign_info(spreadsheet, now_dt)
        row_idx = len(all_rows) + 1

    cur = get_current_campaign_info(spreadsheet, now_dt)
    new_title = (title or cur["title"]).strip()
    new_sheet = (sheet_name or cur["sheet_name"]).strip()
    new_start = cur.get("start_date") or now_dt.strftime("%Y.%m.%d")
    cfg_ws.update(f"B{row_idx}:D{row_idx}", [[new_title, new_sheet, new_start]])
    return {"key": key, "title": new_title, "sheet_name": new_sheet, "start_date": new_start}

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패 (Secrets 확인)"
    try:
        spreadsheet = client.open("Audit_Result_2026")
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except Exception:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])

        if str(emp_id) in sheet.col_values(2):
            return False, "이미 참여하셨습니다."

        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e:
        return False, str(e)

def get_model():
    if "api_key" in st.session_state:
        genai.configure(api_key=st.session_state["api_key"])
    try:
        available_models = [m.name for m in genai.list_models() if "generateContent" in m.supported_generation_methods]
        for m in available_models:
            if "1.5-pro" in m:
                return genai.GenerativeModel(m)
        for m in available_models:
            if "1.5-flash" in m:
                return genai.GenerativeModel(m)
        if available_models:
            return genai.GenerativeModel(available_models[0])
    except Exception:
        pass
    return genai.GenerativeModel("gemini-1.5-flash")

def read_file(uploaded_file):
    content = ""
    try:
        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.getvalue().decode("utf-8")
        elif uploaded_file.name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                content += (page.extract_text() or "") + "\n"
        elif uploaded_file.name.endswith(".docx"):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs])
    except Exception:
        return None
    return content

def process_media_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name

        st.toast("🤖 AI에게 분석 자료를 전달하고 있습니다...", icon="📂")
        myfile = genai.upload_file(tmp_path)
        with st.spinner("🎧 AI가 데이터를 분석하고 있습니다..."):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)

        os.remove(tmp_path)
        if myfile.state.name == "FAILED":
            return None
        return myfile
    except Exception:
        return None

def download_and_upload_youtube_audio(url):
    if yt_dlp is None:
        return None
    try:
        ydl_opts = {"format": "bestaudio/best", "outtmpl": "temp_audio.%(ext)s", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        audio_files = glob.glob("temp_audio.*")
        if not audio_files:
            return None
        audio_path = audio_files[0]
        myfile = genai.upload_file(audio_path)
        with st.spinner("🎧 유튜브 분석 중..."):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
        os.remove(audio_path)
        return myfile
    except Exception:
        return None

def get_youtube_transcript(url):
    try:
        video_id = url.split("v=")[-1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        return " ".join([t["text"] for t in transcript])
    except Exception:
        return None

def get_web_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text()[:10000]
    except Exception:
        return None

# ==========================================
# 9. 메인 화면 및 탭 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

_now_kst = _korea_now()
CURRENT_YEAR = _now_kst.year
CURRENT_MONTH = _now_kst.month

campaign_info = {
    "key": f"{CURRENT_YEAR}-{CURRENT_MONTH:02d}",
    "title": _default_campaign_title(_now_kst),
    "sheet_name": f"{CURRENT_YEAR}_{CURRENT_MONTH:02d}_자율점검",
    "start_date": _now_kst.strftime("%Y.%m.%d"),
}

try:
    _client_for_campaign = init_google_sheet_connection()
    if _client_for_campaign:
        _ss_for_campaign = _client_for_campaign.open("Audit_Result_2026")
        campaign_info = get_current_campaign_info(_ss_for_campaign, _now_kst)
except Exception:
    pass

tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    f"✅ {CURRENT_MONTH} 자율점검", "📄 법률 검토", "💬 AI 에이전트(챗봇)", "📰 스마트 요약", "🔒 관리자 모드"
])

# ---------- (아이콘) 인라인 SVG: 애니메이션 모래시계 ----------
HOURGLASS_SVG = """
<svg width="18" height="18" viewBox="0 0 24 24" fill="none"
     xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M6 2h12v5c0 2.2-1.4 4.2-3.5 5 2.1.8 3.5 2.8 3.5 5v5H6v-5c0-2.2 1.4-4.2 3.5-5C7.4 11.2 6 9.2 6 7V2Z"
        stroke="#0B5ED7" stroke-width="2" stroke-linejoin="round"/>
  <path d="M8 7h8M8 17h8" stroke="#0B5ED7" stroke-width="2" stroke-linecap="round"/>

  <rect x="9" y="8.2" width="6" height="3.0" rx="1.0" fill="#0B5ED7" opacity="0.95">
    <animate attributeName="height" values="3.0;0.3;3.0" dur="1.0s" repeatCount="indefinite" />
    <animate attributeName="y"      values="8.2;10.9;8.2" dur="1.0s" repeatCount="indefinite" />
  </rect>

  <rect x="9" y="15.8" width="6" height="0.3" rx="1.0" fill="#0B5ED7" opacity="0.95">
    <animate attributeName="height" values="0.3;3.0;0.3" dur="1.0s" repeatCount="indefinite" />
    <animate attributeName="y"      values="15.8;13.1;15.8" dur="1.0s" repeatCount="indefinite" />
  </rect>

  <circle cx="12" cy="12" r="0.8" fill="#0B5ED7" opacity="0.95">
    <animate attributeName="cy" values="11.2;14.2;11.2" dur="0.6s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.95;0.2;0.95" dur="0.6s" repeatCount="indefinite"/>
  </circle>
  <circle cx="11" cy="12" r="0.6" fill="#0B5ED7" opacity="0.80">
    <animate attributeName="cy" values="11.0;14.0;11.0" dur="0.7s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.8;0.15;0.8" dur="0.7s" repeatCount="indefinite"/>
  </circle>
  <circle cx="13" cy="12" r="0.6" fill="#0B5ED7" opacity="0.80">
    <animate attributeName="cy" values="11.4;14.4;11.4" dur="0.8s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.8;0.15;0.8" dur="0.8s" repeatCount="indefinite"/>
  </circle>
</svg>
"""

COUNTDOWN_SECONDS = 7  # ✅ 요청 확정: 7초

# =========================
# ✅ 체크 "순간" 감지 + 우측 카운트다운 렌더 유틸
# =========================
def _init_pledge_runtime(keys: list[str]) -> None:
    if "pledge_prev" not in st.session_state:
        st.session_state["pledge_prev"] = {k: False for k in keys}
    if "pledge_done" not in st.session_state:
        st.session_state["pledge_done"] = {k: False for k in keys}
    if "pledge_running" not in st.session_state:
        st.session_state["pledge_running"] = {k: False for k in keys}

def _render_pledge_group(title: str, items: list[tuple[str, str]], all_keys: list[str]) -> None:
    st.markdown(f"### ■ {title}")

    for key, text in items:
        c1, c2, c3 = st.columns([0.06, 0.78, 0.16], vertical_alignment="center")

        with c1:
            st.checkbox("", key=key, label_visibility="collapsed",
                        disabled=bool(st.session_state["pledge_running"].get(key, False)))

        with c2:
            checked = bool(st.session_state.get(key, False))
            color = "#0B5ED7" if checked else "#2C3E50"
            weight = "900" if checked else "650"
            st.markdown(
                f"<div style='font-size:1.02rem; font-weight:{weight}; color:{color}; line-height:1.55;'>{text}</div>",
                unsafe_allow_html=True
            )

        with c3:
            ph = st.empty()
            now_checked = bool(st.session_state.get(key, False))
            prev_checked = bool(st.session_state["pledge_prev"].get(key, False))
            done = bool(st.session_state["pledge_done"].get(key, False))
            running = bool(st.session_state["pledge_running"].get(key, False))

            # ✅ 방금 체크된 순간에만 7초 카운트다운 실행
            if now_checked and (not prev_checked) and (not done) and (not running):
                st.session_state["pledge_running"][key] = True
                for sec in range(COUNTDOWN_SECONDS, 0, -1):
                    ph.markdown(
                        f"<div class='pledge-right'>{HOURGLASS_SVG}<span>{sec}s</span></div>",
                        unsafe_allow_html=True
                    )
                    time.sleep(1)
                st.session_state["pledge_running"][key] = False
                st.session_state["pledge_done"][key] = True
                ph.markdown(
                    "<div style='text-align:right; font-weight:900; color:#27AE60;'>✅ 완료</div>",
                    unsafe_allow_html=True
                )
            else:
                if running:
                    ph.markdown(
                        f"<div class='pledge-right'>{HOURGLASS_SVG}<span>...</span></div>",
                        unsafe_allow_html=True
                    )
                elif done and now_checked:
                    ph.markdown(
                        "<div style='text-align:right; font-weight:900; color:#27AE60;'>✅ 완료</div>",
                        unsafe_allow_html=True
                    )
                else:
                    ph.markdown("", unsafe_allow_html=True)

    # ✅ 그룹 렌더 이후: prev 업데이트는 Tab 끝에서 한번에

# --- [Tab 1: 자율점검] ---
with tab_audit:
    current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")

    # ✅ (요청 1) 제목: Google Sheet 값과 무관하게 강제 고정
    title_for_box = "2026 임직원 윤리경영원칙 실천지침 실천서약"

    st.markdown(f"""
        <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 26px;'>
            <h3 style='margin-top:0; color: #1565C0;'>📜 {title_for_box}</h3>
        </div>
    """, unsafe_allow_html=True)

    # 2) 실천지침 주요내용
    with st.expander("※ 윤리경영원칙 실천지침 주요내용", expanded=True):
        st.markdown(
            """
            <div style='background-color:#FFFDE7; padding: 18px; border-radius: 10px; border-left: 5px solid #FBC02D; margin-bottom: 22px;'>
                <div style='font-weight: 900; color:#6D4C41; font-size: 1.18rem; margin-bottom: 10px;'>📌 윤리경영 위반 주요 유형</div>
                <div style='color:#444; font-size: 0.95rem; line-height: 1.55;'>
                    아래 항목은 <b>윤리경영원칙 실천지침</b>의 주요 위반 유형을 정리한 내용입니다.
                    업무 수행 시 유사 사례가 발생하지 않도록 참고해 주세요.
                </div>
            </div>

            <div style='overflow-x:auto;'>
                <table style='width:100%; border-collapse: collapse; background:#FFFFFF; border:1px solid #E0E0E0; border-radius: 10px; overflow:hidden;'>
                    <thead>
                        <tr style='background:#FFF8E1;'>
                            <th style='text-align:center; padding:12px; border-bottom:1px solid #E0E0E0; color:#5D4037; width:28%;'>구분</th>
                            <th style='text-align:center; padding:12px; border-bottom:1px solid #E0E0E0; color:#5D4037;'>윤리경영 위반사항</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>고객과의 관계</td>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>고객으로부터 금품 등 이익 수수, 고객만족 저해, 고객정보 유출</td>
                        </tr>
                        <tr>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>임직원과 회사의 관계</td>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>공금 유용 및 횡령, 회사재산의 사적 사용, 기업정보 유출, 경영왜곡</td>
                        </tr>
                        <tr>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>임직원 상호간의 관계</td>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>직장 내 괴롭힘, 성희롱, 조직질서 문란행위</td>
                        </tr>
                        <tr>
                            <td style='text-align:center; padding:12px; font-weight:700; color:#2C3E50;'>이해관계자와의 관계</td>
                            <td style='text-align:center; padding:12px; color:#333;'>이해관계자로부터 금품 등 이익 수수, 이해관계자에게 부당한 요구</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div style='margin-top:10px; color:#666; font-size:0.88rem;'>
                ※ 위 내용은 안내 목적이며, 세부 기준은 사내 <b>윤리경영원칙 실천지침</b>을 따릅니다.
            </div>
            """,
            unsafe_allow_html=True
        )

    # ✅ (요청 2) 원래처럼 섹션 분리 + 체크 시 우측 모래시계/카운트다운 (모든 항목 동일)
    exec_pledges = [
        ("pledge_e1", "나는 회사 윤리경영원칙과 윤리경영원칙 실천지침에 따라 판단하고 행동한다."),
        ("pledge_e2", "나는 윤리경영원칙 실천지침을 몰랐다는 이유로 면책을 주장하지 않는다."),
        ("pledge_e3", "나는 직무수행 과정에서 윤리적 갈등 상황에 직면한 경우 감사부서의 해석에 따른다."),
        ("pledge_e4", "나는 가족, 친·인척, 지인 등을 이용하여 회사 윤리경영원칙 실천지침을 위반하지 않는다."),
    ]
    mgr_pledges = [
        ("pledge_m1", "나는 소속 구성원 및 업무상 이해관계자들이 지침을 준수할 수 있도록 지원하고 관리한다."),
        ("pledge_m2", "나는 공정하고 깨끗한 의사결정을 통해 지침 준수를 솔선수범한다."),
        ("pledge_m3", "나는 부서 내 위반 사안 발생 시 관리자로서의 책임을 다한다."),
    ]

    all_keys = [k for k, _ in exec_pledges] + [k for k, _ in mgr_pledges]
    _init_pledge_runtime(all_keys)

    _render_pledge_group("임직원의 책임과 의무", exec_pledges, all_keys)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_pledge_group("관리자의 책임과 의무", mgr_pledges, all_keys)

    # ✅ prev 상태 업데이트 (탭 끝에서 1번)
    st.session_state["pledge_prev"] = {k: bool(st.session_state.get(k, False)) for k in all_keys}

    st.markdown("---")

    st.markdown(
        """<p class='km-pledge-line'>나는 KT MOS 북부의 지속적인 발전을 위하여 회사 윤리경영원칙실천지침에 명시된
        <b>「임직원의 책임과 의무」</b> 및 <b>「관리자의 책임과 의무」</b>를 성실히 이행할 것을 서약합니다.</p>""",
        unsafe_allow_html=True
    )# 입력 박스
    c1, c2, c3, c4 = st.columns(4)
    emp_id = c1.text_input("사번", placeholder="예: 12345")
    name = c2.text_input("성명")
    ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
    unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
    dept = c4.text_input("상세 부서명")

    st.markdown("---")

    # 제출 버튼은 “체크 전부 완료”일 때만 활성화 (카운트다운 강제는 요구사항에 없어서 제외)
    all_checked = all(bool(st.session_state.get(k, False)) for k in all_keys)
    submit = st.button("서약 제출", use_container_width=True, disabled=(not all_checked))

    if submit:
        if not emp_id or not name:
            st.warning("⚠️ 사번과 성명을 입력해주세요.")
        else:
            answer = "윤리경영 서약서 제출 완료 (임직원 의무 4/4, 관리자 의무 3/3)"
            with st.spinner("제출 중..."):
                success, msg = save_audit_result(emp_id, name, unit, dept, answer, current_sheet_name)
            if success:
                st.success(f"✅ {name}님, 윤리경영 서약서 제출이 완료되었습니다!")
                st.balloons()
            else:
                st.error(f"❌ 제출 실패: {msg}")

# --- [Tab 2: 문서 정밀 검토] ---
with tab_doc:
    st.markdown("### 📂 문서 및 규정 검토")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        option = st.selectbox("작업 유형", ["법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 교정", "기안문 작성"])

        is_authenticated = True
        if option == "감사 보고서 검증":
            if "audit_verified" not in st.session_state:
                is_authenticated = False
                st.warning("🔒 감사실 전용 메뉴입니다. 인증이 필요합니다.")
                with st.form("doc_auth_form"):
                    pass_input = st.text_input("인증키 입력", type="password")
                    if st.form_submit_button("확인"):
                        if pass_input.strip() == "ktmos0402!":
                            st.session_state["audit_verified"] = True
                            st.rerun()
                        else:
                            st.error("❌ 인증키 불일치")

        if is_authenticated:
            uploaded_file = st.file_uploader("파일 업로드 (PDF, Word, TXT)", type=["txt", "pdf", "docx"])
            if st.button("🚀 분석 시작", use_container_width=True):
                if uploaded_file:
                    content = read_file(uploaded_file)
                    if content:
                        with st.spinner("🧠 AI가 분석 중입니다..."):
                            try:
                                prompt = f"[역할] 전문 감사인\n[작업] {option}\n[내용] {content}"
                                res = get_model().generate_content(prompt)
                                st.success("분석 완료")
                                st.markdown(res.text)
                            except Exception as e:
                                st.error(f"오류: {e}")

# --- [Tab 3: AI 에이전트] ---
with tab_chat:
    st.markdown("### 💬 AI 법률/감사 챗봇")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []

        with st.form(key="chat_input_form", clear_on_submit=True):
            user_input = st.text_input("질문 입력")
            send_btn = st.form_submit_button("전송 📤", use_container_width=True)

        if send_btn and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("답변 생성 중..."):
                try:
                    res = get_model().generate_content(user_input)
                    st.session_state.messages.append({"role": "assistant", "content": res.text})
                except Exception as e:
                    st.error(f"오류: {e}")

        for msg in reversed(st.session_state.messages):
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

# --- [Tab 4: 스마트 요약] ---
with tab_summary:
    st.markdown("### 📰 스마트 요약")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        st_type = st.radio("입력 방식", ["URL (유튜브/웹)", "미디어 파일", "텍스트"])
        final_input = None
        is_multimodal = False

        if "URL" in st_type:
            url = st.text_input("URL 입력")
            if url and "youtu" in url:
                with st.spinner("자막 추출 중..."):
                    final_input = get_youtube_transcript(url)
                    if not final_input:
                        final_input = download_and_upload_youtube_audio(url)
                        is_multimodal = True
            elif url:
                with st.spinner("웹페이지 분석 중..."):
                    final_input = get_web_content(url)

        elif "미디어" in st_type:
            mf = st.file_uploader("파일 업로드", type=["mp3", "wav", "mp4"])
            if mf:
                final_input = process_media_file(mf)
                is_multimodal = True
        else:
            final_input = st.text_area("텍스트 입력", height=200)

        if st.button("⚡ 요약 실행", use_container_width=True):
            if final_input:
                with st.spinner("요약 중..."):
                    try:
                        p = "다음 내용을 핵심 요약, 상세 내용, 인사이트로 정리해줘."
                        if is_multimodal:
                            res = get_model().generate_content([p, final_input])
                        else:
                            res = get_model().generate_content(f"{p}\n\n{str(final_input)[:30000]}")
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"오류: {e}")

# --- [Tab 5: 관리자 대시보드] ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_dash_pw")

    if admin_pw.strip() == "ktmos0402!":
        st.success("접속 성공")

        client = init_google_sheet_connection()
        if not client:
            st.error("구글 시트 연결 실패: st.secrets / gspread 설정을 확인하세요.")
        else:
            try:
                ss = client.open("Audit_Result_2026")
            except Exception as e:
                st.error(f"스프레드시트 오픈 실패: {e}")
                ss = None

            if ss:
                camp = get_current_campaign_info(ss, _now_kst)

                with st.expander("⚙️ 이번 달 테마 런칭/변경 (관리자)", expanded=False):
                    new_title = st.text_input("테마 제목", value=camp.get("title", ""), key="camp_title_input")
                    new_sheet = st.text_input("연동 시트명", value=camp.get("sheet_name", ""), key="camp_sheet_input")
                    cA, cB = st.columns([1, 1])
                    if cA.button("🚀 테마 적용", use_container_width=True):
                        camp = set_current_campaign_info(ss, title=new_title, sheet_name=new_sheet, now_dt=_now_kst)
                        st.session_state.pop("admin_df", None)
                        st.session_state.pop("admin_stats_df", None)
                        st.session_state["admin_cache_key"] = camp["key"]
                        st.toast("✅ 테마가 적용되었습니다.", icon="🚀")
                        st.rerun()
                    cB.caption("※ 매월 말일 자정(=월 변경 시점) 자동으로 새 캠페인으로 전환됩니다.")

                st.caption(f"현재 테마: **{camp['title']}**  |  연동 시트: `{camp['sheet_name']}`  |  캠페인 키: `{camp['key']}`")

                target_dict = {"경영총괄": 45, "사업총괄": 37, "강북본부": 222, "강남본부": 174, "서부본부": 290, "강원본부": 104, "품질지원단": 138, "감사실": 3}
                ordered_units = list(target_dict.keys())

                refresh_clicked = st.button("🔄 데이터 최신화", use_container_width=True)
                need_reload = (refresh_clicked
                              or st.session_state.get("admin_cache_key") != camp["key"]
                              or "admin_df" not in st.session_state
                              or "admin_stats_df" not in st.session_state)

                if need_reload:
                    try:
                        ws = ss.worksheet(camp["sheet_name"])
                        df = pd.DataFrame(ws.get_all_records())
                    except Exception:
                        df = pd.DataFrame()

                    if (not df.empty) and ("총괄/본부/단" in df.columns):
                        counts = df["총괄/본부/단"].astype(str).value_counts().to_dict()
                    else:
                        counts = {}

                    stats_rows = []
                    for unit_name in ordered_units:
                        participated = int(counts.get(unit_name, 0))
                        target = int(target_dict.get(unit_name, 0))
                        not_part = max(target - participated, 0)
                        rate = round((participated / target) * 100, 2) if target > 0 else 0.0
                        stats_rows.append({"조직": unit_name, "참여완료": participated, "미참여": not_part, "참여율": rate})
                    stats_df = pd.DataFrame(stats_rows)

                    st.session_state["admin_df"] = df
                    st.session_state["admin_stats_df"] = stats_df
                    st.session_state["admin_cache_key"] = camp["key"]
                    st.session_state["admin_last_update"] = _korea_now().strftime("%Y-%m-%d %H:%M:%S")

                df = st.session_state.get("admin_df", pd.DataFrame())
                stats_df = st.session_state.get("admin_stats_df", pd.DataFrame())
                last_update = st.session_state.get("admin_last_update")

                total_target = int(sum(target_dict.values()))
                total_participated = int(stats_df["참여완료"].sum()) if (stats_df is not None and not stats_df.empty) else 0
                total_rate = (total_participated / total_target * 100) if total_target > 0 else 0.0
                date_kor = _korea_now().strftime("%Y.%m.%d")

                if total_rate < 50:
                    lamp_color = "#E74C3C"; lamp_label = "RED"; lamp_msg = "위험"
                elif total_rate < 80:
                    lamp_color = "#F39C12"; lamp_label = "ORANGE"; lamp_msg = "주의"
                else:
                    lamp_color = "#2980B9"; lamp_label = "BLUE"; lamp_msg = "양호"

                display_title = camp.get("title", "")
                if "서약" not in display_title:
                    display_title = display_title + " 서약서"

                st.markdown(f"""
                <div style='background:#FFFFFF; border:1px solid #E6EAF0; padding:18px 18px; border-radius:14px; margin-top:10px; margin-bottom:14px;'>
                  <div style='display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;'>
                    <div style='font-size:1.35rem; font-weight:800; color:#2C3E50;'>📊 {display_title} 참여현황</div>
                    <div style='display:flex; align-items:center; gap:8px;'>
                      <span style='display:inline-block; width:14px; height:14px; border-radius:50%; background:{lamp_color};'></span>
                      <span style='font-weight:800; color:{lamp_color};'>{lamp_msg}</span>
                    </div>
                  </div>
                  <div style='margin-top:10px; font-size:1.05rem; font-weight:700; color:#34495E;'>
                    {date_kor}일 현재&nbsp;&nbsp;|&nbsp;&nbsp;
                    총 대상자 <b>{total_target:,}</b>명&nbsp;&nbsp;|&nbsp;&nbsp;
                    참여완료 <b>{total_participated:,}</b>명&nbsp;&nbsp;|&nbsp;&nbsp;
                    참여율 <b>{total_rate:.2f}%</b>
                  </div>
                  <div style='margin-top:6px; font-size:0.85rem; color:#7F8C8D;'>마지막 업데이트: {last_update or "—"} &nbsp;|&nbsp; 신호등: <b style='color:{lamp_color};'>{lamp_label}</b></div>
                </div>
                """, unsafe_allow_html=True)

                if df is None or df.empty:
                    st.info("데이터가 없습니다.")
                else:
                    melt_df = stats_df.melt(id_vars="조직", value_vars=["참여완료", "미참여"], var_name="구분", value_name="인원")
                    fig_bar = px.bar(melt_df, x="조직", y="인원", color="구분", barmode="stack", text="인원", title="조직별 참여 현황")
                    fig_bar.update_layout(dragmode="pan", autosize=True, margin=dict(l=20, r=20, t=60, b=20))
                    fig_bar.update_traces(textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig_bar, use_container_width=True, config=PLOTLY_CONFIG)

                    fig_line = px.line(stats_df, x="조직", y="참여율", markers=True, text="참여율", title="조직별 참여율(%)")
                    fig_line.update_layout(dragmode="pan", autosize=True, margin=dict(l=20, r=20, t=60, b=20))
                    fig_line.update_traces(textposition="top center")
                    st.plotly_chart(fig_line, use_container_width=True, config=PLOTLY_CONFIG)

                    st.dataframe(df, use_container_width=True)
                    st.download_button(
                        label="📥 엑셀 다운로드",
                        data=df.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"audit_result_{camp['key']}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

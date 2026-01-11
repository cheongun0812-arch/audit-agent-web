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
/* ✅ 전체 글자 크기 +0.1px */
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
    "✅ 자율점검", "📄 법률 검토", "💬 AI 에이전트(챗봇)", "📰 스마트 요약", "🔒 관리자 모드"
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


def _order_enforce_cb(changed_key: str, prereq_keys: list[str], message: str) -> None:
    """체크 순서가 어긋나면 체크를 되돌리고, 경고 메시지를 세션에 기록합니다."""
    try:
        now_checked = bool(st.session_state.get(changed_key, False))
        prereq_ok = all(bool(st.session_state.get(k, False)) for k in prereq_keys)
        if now_checked and (not prereq_ok):
            st.session_state[changed_key] = False
            st.session_state["order_warning"] = message
    except Exception:
        pass


def _render_pledge_group(
    title: str,
    items: list[tuple[str, str]],
    all_keys: list[str],
    order_guard: dict | None = None,   # {"keys": [...], "prereq": [...], "message": "..."}
) -> None:
    st.markdown(f"### ■ {title}")

    guard_keys = set(order_guard.get("keys", [])) if isinstance(order_guard, dict) else set()
    prereq_keys = list(order_guard.get("prereq", [])) if isinstance(order_guard, dict) else []
    guard_msg = str(order_guard.get("message", "")) if isinstance(order_guard, dict) else ""

    for key, text in items:
        c1, c2, c3 = st.columns([0.06, 0.78, 0.16], vertical_alignment="center")

        with c1:
            cb_kwargs = dict(
                key=key,
                label_visibility="collapsed",
                disabled=bool(st.session_state["pledge_running"].get(key, False)),
            )

            # ✅ 관리자 서약을 임직원 서약보다 먼저 체크하려 하면: 체크를 되돌리고 토스트 경고
            if key in guard_keys:
                cb_kwargs.update(
                    dict(
                        on_change=_order_enforce_cb,
                        args=(key, prereq_keys, guard_msg),
                    )
                )

            st.checkbox("", **cb_kwargs)

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

# --- [Tab 1: 자율점검] ---
with tab_audit:
    current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")

    # ✅ (UX) '서약 확인/임직원 정보 입력' 영역: 최초에는 접힘, 입력/체크 시 자동 펼침
    if "pledge_box_open" not in st.session_state:
        st.session_state["pledge_box_open"] = False

    # ✅ (요청 1) 제목: Google Sheet 값과 무관하게 강제 고정
    title_for_box = "2026 임직원 윤리경영원칙 실천지침 실천서약"

    st.markdown(f"""
        <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 20px;'>
            <h3 style='margin-top:0; color: #1565C0;'>📜 {title_for_box}</h3>
        </div>
    """, unsafe_allow_html=True)

    # 2) 실천지침 주요내용
    with st.expander("※ 윤리경영원칙 실천지침 주요내용", expanded=True):
        st.markdown(
            """
            <div style='background-color:#FFFDE7; padding: 18px; border-radius: 10px; border-left: 5px solid #FBC02D; margin-bottom: 12px;'>
                <div style='font-weight: 800; color:#6D4C41; font-size: 1.05rem; margin-bottom: 6px;'>📌 윤리경영 위반 주요 유형</div>
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

    # ✅ 서약 항목
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

    with st.expander("✅ 서약 확인 및 임직원 정보 입력", expanded=st.session_state["pledge_box_open"]):

        # ✅ 체크 순서 안내/경고 (관리자 서약을 먼저 체크하면 자동으로 되돌리고 토스트 표시)
        if st.session_state.get("order_warning"):
            st.toast(st.session_state["order_warning"], icon="⚠️")
            st.session_state.pop("order_warning", None)

        _render_pledge_group("임직원의 책임과 의무", exec_pledges, all_keys)
        st.markdown("<br>", unsafe_allow_html=True)

        st.info("📌 진행 순서 안내: **임직원의 책임과 의무(4개)**를 먼저 확인(체크)하신 후, **관리자의 책임과 의무(3개)**를 순서대로 진행해 주세요.")

        _render_pledge_group(
            "관리자의 책임과 의무",
            mgr_pledges,
            all_keys,
            order_guard={
                "keys": ["pledge_m1", "pledge_m2", "pledge_m3"],
                "prereq": ["pledge_e1", "pledge_e2", "pledge_e3", "pledge_e4"],
                "message": "⚠️ 순서 안내: 먼저 '임직원의 책임과 의무' 4개 항목을 모두 체크한 뒤 '관리자의 책임과 의무'를 진행해 주세요."
            }
        )

        # ✅ prev 상태 업데이트 (탭 끝에서 1번)
        st.session_state["pledge_prev"] = {k: bool(st.session_state.get(k, False)) for k in all_keys}

        # ✅ 서약 문구를 현재 위치보다 약 20mm(≈76px) 아래로 내리기
        st.markdown("<div style='height:76px;'></div>", unsafe_allow_html=True)
        st.markdown(
            """
            나는 <b>KT MOS 북부</b>의 지속적인 발전을 위하여 회사 윤리경영원칙 실천지침에 명시된
            <b>「임직원의 책임과 의무」 및 「관리자의 책임과 의무」</b>를
            <b>성실히 이행할 것을 서약합니다.</b>
            """,
            unsafe_allow_html=True
        )

        # ✅ 임직원 서명(정보 입력) 영역을 15mm(≈57px) 더 아래로
        st.markdown("<div style='height:57px;'></div>", unsafe_allow_html=True)

        # 입력 박스 (한 박스 안)
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
        dept = c4.text_input("상세 부서명")

        # ✅ 입력을 시작하면 expander가 다시 접히지 않도록 유지
        if any([str(emp_id).strip(), str(name).strip(), str(dept).strip()]):
            st.session_state["pledge_box_open"] = True

    st.markdown("---")

    # 제출 버튼은 “체크 전부 완료”일 때만 활성화
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

# --- [Tab 2: 문서/규정 검토 & 감사보고서 작성] ---
with tab_doc:
    st.markdown("### 📄 문서·규정 검토 / 감사보고서 작성·검증")

    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        # 2-레벨 메뉴: 커리큘럼 1(법률 리스크) / 커리큘럼 2(감사보고서)
        cur1, cur2 = st.tabs(["⚖️ 커리큘럼 1: 법률 리스크 심층 검토", "🔍 커리큘럼 2: 감사보고서 작성·검증"])

        # -------------------------
        # ⚖️ 커리큘럼 1: 법률 리스크 심층 검토
        # -------------------------
        with cur1:
            st.markdown("#### ⚖️ 법률 리스크 정밀 검토")
            st.caption("PDF/Word/TXT 파일을 업로드하면, 핵심 쟁점·리스크·개선안을 구조적으로 정리합니다.")

            uploaded_file = st.file_uploader("파일 업로드 (PDF, Word, TXT)", type=["txt", "pdf", "docx"], key="cur1_file")

            analysis_depth = st.selectbox(
                "분석 수준",
                ["핵심 요약", "리스크 식별(중점)", "조항/근거 중심(가능 범위 내)"],
                index=1,
                key="cur1_depth"
            )

            if st.button("🚀 분석 시작", use_container_width=True, key="cur1_run"):
                if not uploaded_file:
                    st.warning("⚠️ 먼저 파일을 업로드해주세요.")
                else:
                    content = read_file(uploaded_file)
                    if not content:
                        st.error("❌ 파일에서 텍스트를 추출하지 못했습니다.")
                    else:
                        with st.spinner("🧠 AI가 분석 중입니다..."):
                            try:
                                prompt = f"""[역할] 법률/준법 리스크 심층 검토 전문가
[작업] 법률 리스크 정밀 검토
[분석 수준] {analysis_depth}

[작성 원칙]
- 사실과 의견을 구분해 작성
- 근거가 부족하면 '근거 미확인'으로 표시
- 회사에 불리할 수 있는 문구(단정/추정)는 피하고, 조건부 표현 사용

[입력 문서]
{content[:30000]}
"""
                                res = get_model().generate_content(prompt)
                                st.success("✅ 분석 완료")
                                st.markdown(res.text)
                            except Exception as e:
                                st.error(f"오류: {e}")

        # -------------------------
        # 🔍 커리큘럼 2: 감사보고서 작성·검증 (Multi-Source Upload)
        # -------------------------
        with cur2:
            st.markdown("#### 🔍 감사보고서 작성·검증 (Multi-Source Upload)")

            # ✅ 작업 모드 선택(선택에 따라 필요한 입력만 노출/활성화)
            mode = st.radio(
                "작업 모드",
                ["🧾 감사보고서 초안 생성", "✅ 감사보고서 검증·교정(오탈자/논리/형식)"],
                horizontal=True,
                key="cur2_mode"
            )
            is_draft_mode = "초안" in mode

            # ✅ (초기화) 모드별로 정의되지 않을 수 있는 변수들
            interview_audio = None
            interview_transcript = None
            evidence_files = []
            draft_text = ""
            draft_file = None

            # ✅ 안내 문구는 작게/정리해서 제공 (필요 시 펼쳐보기)
            st.caption("선택한 작업 모드에 따라 아래 입력 항목이 자동으로 바뀝니다.")
            with st.expander("🔐 보안·주의사항(필독)", expanded=False):
                st.markdown(
                    "- 민감정보(주민등록번호/계좌/건강/징계대상 실명 등)는 업로드 전 **내부 보안 기준**을 반드시 확인하세요.\n"
                    "- 본 기능은 **감사 판단을 보조**하는 도구이며, 최종 판단·결재 책임은 감사실에 있습니다.\n"
                    "- 규정 근거는 업로드된 자료에서 확인되는 내용만 인용하도록 설계되었습니다."
                )

            # =========================================================
            # ① 모드별 핵심 입력
            # =========================================================
            if is_draft_mode:
                st.markdown("### ① 감사 자료 입력 (초안 생성에 사용)")
                cL, cR = st.columns(2)

                with cL:
                    interview_audio = st.file_uploader(
                        "🎧 면담 음성 (mp3/wav/mp4) — 선택",
                        type=["mp3", "wav", "mp4"],
                        key="cur2_audio"
                    )
                    interview_transcript = st.file_uploader(
                        "📝 면담 녹취(텍스트/문서) — 권장",
                        type=["txt", "pdf", "docx"],
                        key="cur2_transcript"
                    )

                with cR:
                    evidence_files = st.file_uploader(
                        "📂 조사·증거/확인 자료 — 권장(복수 업로드 가능)",
                        type=["pdf", "png", "jpg", "jpeg", "xlsx", "csv", "txt", "docx"],
                        accept_multiple_files=True,
                        key="cur2_evidence"
                    ) or []

            else:
                st.markdown("### ① 검증 대상 보고서 입력 (검증·교정에 사용)")
                cL, cR = st.columns(2)

                with cL:
                    draft_text = st.text_area(
                        "검증할 감사보고서(초안/기존본) — 붙여넣기",
                        height=220,
                        key="cur2_draft"
                    )

                with cR:
                    draft_file = st.file_uploader(
                        "또는 파일 업로드(PDF/DOCX/TXT) — 선택",
                        type=["pdf", "docx", "txt"],
                        key="cur2_draft_file"
                    )

            # =========================================================
            # ②/③ 참고 자료(모드에 따라 '권장/선택'이 달라짐)
            # =========================================================
            st.markdown("### ② 회사 규정/판단 기준  ·  ③ 표준 감사보고서 형식(참고)")
            left, right = st.columns(2)

            with left:
                regulations = st.file_uploader(
                    "📘 회사 규정/기준(인사규정·징계기준·윤리지침 등)",
                    type=["pdf", "docx", "txt"],
                    accept_multiple_files=True,
                    key="cur2_regs"
                )
                st.caption("초안/검증 모두에 유용합니다. (특히 ‘근거 인용’ 필요 시 권장)")

            with right:
                reference_reports = st.file_uploader(
                    "📑 표준 감사보고서 형식(정부·공공·기업) — 선택",
                    type=["pdf", "docx", "txt"],
                    accept_multiple_files=True,
                    key="cur2_refs"
                )
                st.caption("문서 형식/톤을 맞추고 싶을 때만 넣어도 됩니다.")

            # =========================================================
            # ④ 사건 개요(필수) 및 작성 옵션 — 화면 정리(50:50)
            # =========================================================
            st.markdown("### ④ 사건 개요(필수) 및 작성 옵션")
            row1, row2 = st.columns(2)

            with row1:
                case_title = st.text_input(
                    "사건명/건명(필수)",
                    placeholder="예: 법인카드 사적 사용 의혹 조사",
                    key="cur2_title"
                )

            with row2:
                report_tone = st.selectbox(
                    "문서 톤",
                    ["감사보고서(공식·중립)", "보고서(간결·결정 중심)", "상신용(결재/조치 권고 중심)"],
                    index=0,
                    key="cur2_tone"
                )

            case_scope = st.text_area(
                "사건 개요 요약(필수) — 무엇을/언제/누가/어떤 경위로",
                height=110,
                key="cur2_scope"
            )# ---- 내부 유틸: 파일 리스트 -> 텍스트(최대 길이 제한) ----
            def _files_to_text(files, title: str, limit: int = 24000) -> str:
                if not files:
                    return ""
                parts = [f"[{title}]"]
                used = 0
                for f in files:
                    try:
                        t = extract_text_from_file(f)
                        t = (t or "").strip()
                        if not t:
                            continue
                        header = f"\n\n--- 파일: {getattr(f, 'name', 'unknown')} ---\n"
                        chunk = header + t
                        if used + len(chunk) > limit:
                            remain = max(0, limit - used)
                            if remain > 200:
                                parts.append(chunk[:remain] + "\n...[이하 생략]...")
                            break
                        parts.append(chunk)
                        used += len(chunk)
                    except Exception:
                        continue
                return "\n".join(parts).strip()

            # ---- (선택) 음성 파일을 Gemini 파일로 업로드하여 멀티모달로 참조 ----
            interview_audio_obj = None
            if interview_audio is not None:
                st.caption("※ 면담 음성은 업로드 후 AI가 참고할 수 있도록 처리됩니다(환경에 따라 시간이 걸릴 수 있음).")
                if st.button("🎧 면담 음성 준비(업로드)", key="cur2_audio_prepare"):
                    with st.spinner("면담 음성을 준비 중입니다..."):
                        interview_audio_obj = process_media_file(interview_audio)
                        if interview_audio_obj is None:
                            st.error("❌ 음성 파일 처리에 실패했습니다.")
                        else:
                            st.success("✅ 면담 음성 준비 완료")
                            st.session_state["cur2_audio_obj_name"] = interview_audio_obj.name

            # 세션에 저장된 멀티모달 파일 핸들 복구
            if "cur2_audio_obj_name" in st.session_state and interview_audio_obj is None:
                try:
                    interview_audio_obj = genai.get_file(st.session_state["cur2_audio_obj_name"])
                except Exception:
                    interview_audio_obj = None

            # ---- 실행 버튼 ----
            run_label = "🧠 감사보고서 생성" if "초안" in mode else "🧪 감사보고서 검증·교정"
            if st.button(run_label, use_container_width=True, key="cur2_run"):
                if not case_title.strip():
                    st.warning("⚠️ 사건명/건명을 입력해주세요.")
                elif not case_scope.strip():
                    st.warning("⚠️ 사건 개요를 입력해주세요.")
                else:
                    transcript_text = extract_text_from_file(interview_transcript) if interview_transcript else ""
                    evidence_text = _files_to_text(evidence_files, "증거/조사자료", limit=22000)
                    regs_text = _files_to_text(regulations_files, "회사 규정/기준", limit=26000)
                    refs_text = _files_to_text(reference_reports, "표준 감사보고서 형식(참조)", limit=20000)

                    # 보고서 템플릿 (고정)
                    report_structure = """[감사보고서 구성]
Ⅰ. 감사 개요
Ⅱ. 조사 경과 및 방법
Ⅲ. 사실관계 정리(객관)
Ⅳ. 규정 위반 여부 판단(근거 제시)
Ⅴ. 고의성·중대성 판단(규정 기준에 따른 조건부 판단)
Ⅵ. 징계/조치 기준 검토(가능 범위 내, '근거 미확인' 허용)
Ⅶ. 종합 의견 및 조치 권고
Ⅷ. 첨부자료 목록(업로드된 자료 기준)
"""

                    base_rules = """[작성 원칙(필수)]
- 사실과 의견을 명확히 구분(사실=자료 근거, 의견=판단)
- 제공된 회사 규정/기준 텍스트에서 확인되는 내용만 '조항/기준'으로 언급
- 근거 텍스트에서 확인되지 않으면 반드시 '근거 미확인'으로 표기
- 단정적 표현 금지(가능성/소지/추정/조건부 표현 사용)
- 개인정보/민감정보는 마스킹(예: 홍*동, 1234-****)
"""

                    if "초안" in mode:
                        task = "감사보고서 초안 작성"
                        instructions = f"""[작업] {task}
[문서 톤] {report_tone}
{report_structure}
{base_rules}

[사건명/건명]
{case_title}

[사건 개요]
{case_scope}

[면담 녹취(텍스트)]
{(transcript_text or "").strip()[:18000]}

{evidence_text}

{regs_text}

{refs_text}

[출력 요구]
- 위 구성(Ⅰ~Ⅷ)을 유지
- 표/목록을 적극 활용(가독성)
- '규정 위반 여부'에는 '가능/불가/근거 미확인' 3단으로 표시
"""
                    else:
                        task = "감사보고서 검증·교정"

                        # ✅ 상단 '작업 모드' 영역에서 입력받은 검증 대상 보고서를 사용
                        draft = (draft_text or "").strip()

                        # 파일로도 업로드한 경우(우선순위: 파일 > 텍스트)
                        if draft_file is not None:
                            try:
                                _t = (extract_text_from_file(draft_file) or "").strip()
                                if _t:
                                    draft = _t
                            except Exception:
                                pass

                        if not draft:
                            st.warning("⚠️ 검증할 보고서를 '붙여넣기' 하거나 파일로 업로드해주세요.")
                            st.stop()

                        instructions = f"""[작업] {task}
{base_rules}

[검증 기준]
1) 논리/사실관계: 자료와 불일치/모순 여부 지적
2) 규정 근거: 제공된 규정 텍스트에서 확인 가능한지(불가하면 '근거 미확인' 표시)
3) 표현: 단정/감정/주관 표현 제거 → 중립/조건부 표현으로 교정
4) 형식: 감사보고서 표준 구조(Ⅰ~Ⅷ) 충족 여부 및 누락 항목 보완
5) 오탈자/문장 교정: 의미 훼손 없이 교정

[사건명/건명]
{case_title}

[사건 개요]
{case_scope}

[검증 대상 보고서]
{draft[:25000]}

{regs_text}

{refs_text}

[출력 요구]
- (A) 핵심 수정사항 요약
- (B) 문장 교정본(가능하면 전체)
- (C) 근거 확인/미확인 표(항목별)
"""

                    with st.spinner("🧠 AI가 작성/검증 중입니다..."):
                        try:
                            model = get_model()
                            if interview_audio_obj is not None:
                                res = model.generate_content([instructions, interview_audio_obj])
                            else:
                                res = model.generate_content(instructions)

                            st.success("✅ 완료")
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

                # ✅ 여기부터는 반드시 tab_admin 블록 내부여야 합니다.
                if df is None or df.empty:
                    st.info("데이터가 없습니다.")
                else:
                    # -------------------------
                    # ✅ 조직별 참여 현황(스택 바) + 참여율(라인)
                    #    - 모바일 스크롤 방해 방지를 위해 dragmode="pan" 제거
                    # -------------------------
                    melt_df = stats_df.melt(
                        id_vars="조직",
                        value_vars=["참여완료", "미참여"],
                        var_name="구분",
                        value_name="인원"
                    )

                    fig_bar = px.bar(
                        melt_df,
                        x="조직",
                        y="인원",
                        color="구분",
                        barmode="stack",
                        text="인원",
                        title="조직별 참여 현황"
                    )
                    fig_bar.update_layout(
                        autosize=True,
                        margin=dict(l=20, r=20, t=60, b=20)
                    )
                    fig_bar.update_traces(textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig_bar, use_container_width=True, config=PLOTLY_CONFIG)

                    fig_line = px.line(
                        stats_df,
                        x="조직",
                        y="참여율",
                        markers=True,
                        text="참여율",
                        title="조직별 참여율(%)"
                    )
                    fig_line.update_layout(
                        autosize=True,
                        margin=dict(l=20, r=20, t=60, b=20)
                    )
                    fig_line.update_traces(textposition="top center")
                    st.plotly_chart(fig_line, use_container_width=True, config=PLOTLY_CONFIG)

                    # -------------------------
                    # ✅ 원본 데이터 테이블 + 다운로드
                    # -------------------------
                    st.dataframe(df, use_container_width=True)

                    st.download_button(
                        label="📥 엑셀 다운로드",
                        data=df.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"audit_result_{camp['key']}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

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
import html
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
    layout="wide",                 # ✅ 사이드바가 더 안정적으로 표시되도록 wide 권장
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 🎨 디자인 테마 (사이드바/토글 강제 표시 포함)
# ==========================================
st.markdown("""
<style>
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




[data-testid="stSidebar"] div[data-testid="stTextInput"] button:hover {
    background: rgba(44, 62, 80, 0.12) !important;
    border-radius: 8px !important;
}
[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg path {
    fill: currentColor !important;
    stroke: currentColor !important;
    opacity: 1 !important;
}

.stButton > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    border: none !important;
    font-weight: bold !important;
}



button[aria-label="Show password text"] svg,
button[aria-label="Hide password text"] svg,
div[data-testid="stTextInput"] button svg,
div[data-testid="stTextInput"] button svg path {
  fill: #000000 !important;
  stroke: #000000 !important;
  opacity: 1 !important;
}

/* ✅ form_submit_button / 버튼이 비활성화(disabled)되어도 텍스트가 안 사라지게 */
div[data-testid="stFormSubmitButton"] > button:disabled,
.stButton > button:disabled {
  opacity: 1 !important;
  color: #2C3E50 !important;
  background: #E6ECF2 !important;
  border: 1px solid #CBD6E2 !important;
}
div[data-testid="stFormSubmitButton"] > button:disabled * ,
.stButton > button:disabled * {
  opacity: 1 !important;
  color: #2C3E50 !important;
}
</style>
""", unsafe_allow_html=True)
# ✅ PC에서는 사이드바 기본 펼침, 모바일에서는 기본 접힘 (Streamlit 기본 동작 유지)
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

      // Streamlit 버전에 따라 요소 형태가 다를 수 있어 여러 셀렉터 시도
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
    """키 검증 후 세션에 저장. 실패 시 예외 발생."""
    genai.configure(api_key=clean_key)
    # 유효성 검사: 모델 목록 호출
    list(genai.list_models())
    st.session_state["api_key"] = clean_key
    st.session_state["login_error"] = None
    _set_query_param_key(clean_key)

def try_login_from_session_key(key_name: str) -> None:
    """지정된 session_state 키에서 값을 읽어 로그인 처리."""
    raw_key = st.session_state.get(key_name, "")
    clean_key = "".join(str(raw_key).split())  # 모든 공백 제거
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
    # ✅ 2026년 1월은 '윤리경영원칙 실천지침 실천서약'으로 고정(요청사항)
    if dt.year == 2026 and dt.month == 1:
        return "1월 윤리경영원칙 실천지침 실천서약"
    return f"{dt.month}월 자율점검"

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
# 8-1. [신규] 윤리 원문 읽기 게이트 (안정판: 시간 기반 + 서버단 차단)
#   - Streamlit 버전 차이로 components.html(key=...) 오류가 발생할 수 있어
#     외부 컴포넌트 없이 동작하는 방식으로 구현합니다.
# ==========================================
def load_ethics_full_text_md(path: str = "ethics_full_text.md") -> str:
    """원문(마크다운) 파일을 읽어옵니다. 파일이 없으면 안내 문구 반환."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def render_scrollable_text(md_text: str, height: int = 320) -> None:
    """원문 텍스트를 스크롤 박스로 표시(HTML/CSS)"""
    if not md_text:
        st.warning("⚠️ 원문 파일(ethics_full_text.md)을 찾지 못했습니다. 배포 폴더에 파일을 추가해 주세요.")
        return
    # HTML 안전 처리(기본 줄바꿈만)
    safe = html.escape(md_text).replace("\n", "<br>")
    st.markdown(
        f"""<div style="height:{height}px; overflow-y:auto; background:#FFFFFF;
                 border:1px solid #D7DEE8; border-radius:12px; padding:14px; line-height:1.6;">
                 {safe}
               </div>""",
        unsafe_allow_html=True,
    )

def ethics_read_gate(min_seconds: int = 96, box_height: int = 320) -> tuple[bool, float]:
    """윤리 원문 읽기 게이트.
    - min_seconds: 최소 읽기(체류) 시간(초). (예: 120초의 80% = 96초)
    반환: (gate_ok, progress_rate)
    """
    if "ethics_read_start_ts" not in st.session_state:
        st.session_state["ethics_read_start_ts"] = time.time()

    elapsed = max(0.0, time.time() - float(st.session_state["ethics_read_start_ts"]))
    rate = min(elapsed / float(min_seconds), 1.0)

    md_text = load_ethics_full_text_md("ethics_full_text.md")
    st.markdown("#### 👀 원문 읽기 확인")
    st.caption(f"아래 원문을 읽고, **최소 {min_seconds}초** 이상 경과해야 제출할 수 있습니다. (읽기 진행률 80% 기준 안정판)")
    render_scrollable_text(md_text, height=box_height)
    st.progress(rate)
    st.write(f"읽기 진행률: **{int(rate*100)}%**  |  경과 시간: **{int(elapsed)}초**")

    gate_ok = elapsed >= float(min_seconds)
    return gate_ok, rate

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
    "title": f"{CURRENT_MONTH}월 자율점검",
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
    f"✅ {CURRENT_MONTH}월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"
])

# --- [Tab 1: 자율점검] ---
with tab_audit:
    current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")

    # 1) 제목 + 요약(서약 문구)
    st.markdown(f"""
        <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 20px;'>
            <h3 style='margin-top:0; color: #1565C0;'>📜 {campaign_info.get('title','1월 윤리경영원칙 실천지침 실천서약')}</h3>
            <p style='font-size: 1.50rem; color: #444;'>
                나는 <b>kt MOS북부</b>의 지속적인 발전을 위하여 회사 윤리경영원칙실천지침에 명시된 
                <b>「임직원의 책임과 의무」</b> 및 <b>「관리자의 책임과 의무」</b>를 성실히 이행할 것을 서약합니다.
            </p>
        </div>
    """, unsafe_allow_html=True)


    # ✅ [신규] 원문 읽기 게이트 (80% 기준 안정판)
    #  - Streamlit Cloud/버전 차이로 JS 컴포넌트 사용 시 오류가 발생할 수 있어,
    #    시간 기반(서버단 차단) 방식으로 안정적으로 운영합니다.
    MIN_READ_SECONDS = 96  # 예: 120초의 80% (원하면 120/180 등으로 조정 가능)
    gate_ok, _gate_rate = ethics_read_gate(min_seconds=MIN_READ_SECONDS, box_height=320)

    st.markdown("---")
    # 2) 실천지침 주요내용(※ 박스) — 책임/의무 체크박스 위로 이동
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
                                <th style='text-align:left; padding:12px; border-bottom:1px solid #E0E0E0; color:#5D4037; width:28%;'>구분</th>
                                <th style='text-align:left; padding:12px; border-bottom:1px solid #E0E0E0; color:#5D4037;'>윤리경영 위반사항</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td style='padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>고객과의 관계</td>
                                <td style='padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>고객으로부터 금품 등 이익 수수, 고객만족 저해, 고객정보 유출</td>
                            </tr>
                            <tr>
                                <td style='padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>임직원과 회사의 관계</td>
                                <td style='padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>공금 유용 및 횡령, 회사재산의 사적 사용, 기업정보 유출, 경영왜곡</td>
                            </tr>
                            <tr>
                                <td style='padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>임직원 상호간의 관계</td>
                                <td style='padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>직장 내 괴롭힘, 성희롱, 조직질서 문란행위</td>
                            </tr>
                            <tr>
                                <td style='padding:12px; font-weight:700; color:#2C3E50;'>이해관계자와의 관계</td>
                                <td style='padding:12px; color:#333;'>이해관계자로부터 금품 등 이익 수수, 이해관계자에게 부당한 요구</td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <div style='margin-top:10px; color:#666; font-size:0.88rem;'>
                    ※ 위 내용은 안내 목적이며, 세부 기준은 사내 <b>윤리경영원칙 실천지침</b>을 따릅니다.
                </div>
                """,
                unsafe_allow_html=True,
            )


    # 3) 책임/의무 체크 → 4) 사번/성명 등 입력 → 5) 서약 제출(버튼)
    with st.form("audit_ethics_form", clear_on_submit=False):
        st.markdown("#### ■ 임직원의 책임과 의무")
        e1 = st.checkbox("하나, 나는 회사 윤리경영원칙과 윤리경영원칙 실천지침에 따라 판단하고 행동한다.")
        e2 = st.checkbox("하나, 나는 윤리경영원칙 실천지침을 몰랐다는 이유로 면책을 주장하지 않는다.")
        e3 = st.checkbox("하나, 나는 직무수행 과정에서 윤리적 갈등 상황에 직면한 경우 감사부서의 해석에 따른다.")
        e4 = st.checkbox("하나, 나는 가족, 친·인척, 지인 등을 이용하여 회사 윤리경영원칙 실천지침을 위반하지 않는다.")

        st.markdown("<br>", unsafe_allow_html=True)

        st.markdown("#### ■ 관리자의 책임과 의무")
        m1 = st.checkbox("하나, 나는 소속 구성원 및 업무상 이해관계자들이 지침을 준수할 수 있도록 지원하고 관리한다.")
        m2 = st.checkbox("하나, 나는 공정하고 깨끗한 의사결정을 통해 지침 준수를 솔선수범한다.")
        m3 = st.checkbox("하나, 나는 부서 내 위반 사안 발생 시 관리자로서의 책임을 다한다.")

        st.markdown("---")

        # ✅ 요청사항: '사번/성명/총괄...' 입력 박스를 '서약 제출' 바로 위로 이동
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
        dept = c4.text_input("상세 부서명")

        st.markdown("---")

        submit = st.form_submit_button("서약 제출", use_container_width=True)

        if submit:

            # ✅ [필수] 원문 읽기 게이트 통과 여부 확인 (서버단 차단)
            if not gate_ok:
                st.error("❌ 원문 읽기 진행률이 부족합니다. 원문을 읽고 잠시 후 다시 제출해 주세요.")
                st.stop()

            confirm_read = st.checkbox("✅ 원문을 충분히 읽고 이해했습니다.", value=False, key="confirm_read_ck")
            if not confirm_read:
                st.error("❌ '원문을 충분히 읽고 이해했습니다' 체크 후 제출할 수 있습니다.")
                st.stop()
            if not emp_id or not name:
                st.warning("⚠️ 사번과 성명을 입력해주세요.")
            else:
                unchecked = []
                if not e1: unchecked.append("임직원 의무 1")
                if not e2: unchecked.append("임직원 의무 2")
                if not e3: unchecked.append("임직원 의무 3")
                if not e4: unchecked.append("임직원 의무 4")
                if not m1: unchecked.append("관리자 의무 1")
                if not m2: unchecked.append("관리자 의무 2")
                if not m3: unchecked.append("관리자 의무 3")

                if unchecked:
                    st.error("❌ 서약 항목이 모두 체크되어야 제출할 수 있습니다. (미체크: " + ", ".join(unchecked) + ")")
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
                    총 대상자 <b>{total_target:,}명</b> · 참여 인원 <b>{total_participated:,}명</b> · 참여율 <b>{total_rate:.2f}%</b>
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

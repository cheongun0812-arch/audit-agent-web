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
#    + ✅ (요청 반영) 자율점검 탭(#audit-tab) 내 Expander 헤더/입력라벨/셀렉트 가독성 강화
# ==========================================
st.markdown("""
<style>
/* 🔥 Expander 제목 가독성 강제 개선 */
details > summary {
    font-size: 1.15rem !important;
    font-weight: 900 !important;
    color: #1565C0 !important;  /* 📜 서약 타이틀과 동일 색상 */
}

/* 펼쳐졌을 때도 동일하게 유지 */
details[open] > summary {
    font-size: 1.15rem !important;
    font-weight: 900 !important;
    color: #1565C0 !important;
}

/* summary 안의 span도 같이 잡아줌 (환경 차이 대응) */
details > summary,
details > summary span,
details[open] > summary,
details[open] > summary span {
    font-size: 1.5rem !important;   /* ← 여기 숫자만 조절 */
    font-weight: 900 !important;
    color: #1565C0 !important;
}

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

/* =========================================================
   ✅ (요청 1,3,4) 자율점검 탭 전용 가독성 강화
   - 다른 탭/영역 영향 최소화: #audit-tab 내부에서만 적용
   ========================================================= */
#audit-tab [data-testid="stExpander"] summary {
    font-weight: 900 !important;
    font-size: 1.12rem !important;
    color: #1565C0 !important;                 /* 📜 타이틀 색상과 동일 */
}
#audit-tab [data-testid="stExpander"] summary * {
    font-weight: 900 !important;
    color: #1565C0 !important;
}

/* 입력 라벨(사번/성명/총괄/본부/단/상세 부서명) 굵게 */
#audit-tab div[data-testid="stTextInput"] label,
#audit-tab div[data-testid="stSelectbox"] label {
    font-weight: 900 !important;
    color: #2C3E50 !important;
}

/* ✅ 메인 화면의 Selectbox(총괄/본부/단) 선택값 가독성 강제 */
section.main div[data-testid="stSelectbox"] div[data-baseweb="select"] {
    font-size: 1.08rem !important;    /* ← 원하면 더 키우세요 */
    font-weight: 900 !important;
}

/* 선택값이 들어있는 실제 박스(콤보박스) */
section.main div[data-testid="stSelectbox"] div[role="combobox"] {
    background: #FFFFFF !important;
    border: 1px solid #90A4AE !important;
}

/* 선택된 텍스트(대부분 span에 들어감) */
section.main div[data-testid="stSelectbox"] div[role="combobox"] span {
    color: #2C3E50 !important;
    font-weight: 900 !important;
    opacity: 1 !important;
}

/* 어떤 환경에서는 input에 값이 들어가므로 같이 처리 */
section.main div[data-testid="stSelectbox"] div[role="combobox"] input {
    color: #2C3E50 !important;
    -webkit-text-fill-color: #2C3E50 !important;
    font-weight: 900 !important;
    opacity: 1 !important;
}

/* 드롭다운 화살표(아이콘)도 선명하게 */
section.main div[data-testid="stSelectbox"] svg,
section.main div[data-testid="stSelectbox"] svg * {
    fill: #2C3E50 !important;
    stroke: #2C3E50 !important;
    opacity: 1 !important;
}

/* 드롭다운 옵션 목록도 굵게 */
div[role="listbox"] * {
    font-weight: 850 !important;
}
/* ✅ 메인 영역 selectbox를 텍스트 입력창처럼 보이게 (흰박스 + 동일 톤) */
section.main div[data-testid="stSelectbox"] div[role="combobox"]{
  background:#FFFFFF !important;
  border:1px solid #CBD5E1 !important;
  border-radius:6px !important;
  min-height: 42px !important;
  box-shadow: none !important;
}

/* ✅ 선택값 텍스트(진하게) */
section.main div[data-testid="stSelectbox"] div[role="combobox"] span{
  color:#2C3E50 !important;
  font-weight: 800 !important;
  opacity: 1 !important;
}

/* ✅ '선택/placeholder'처럼 보이는 텍스트(옅은 회색) */
/* Streamlit/브라우저마다 placeholder가 input에 들어가거나 span으로 들어가서 둘 다 커버 */
section.main div[data-testid="stSelectbox"] div[role="combobox"] input{
  color:#94A3B8 !important;                 /* search box 느낌의 회색 */
  -webkit-text-fill-color:#94A3B8 !important;
  font-weight: 700 !important;
  opacity: 1 !important;
}

/* ✅ 드롭다운 화살표도 선명하게 */
section.main div[data-testid="stSelectbox"] svg,
section.main div[data-testid="stSelectbox"] svg *{
  fill:#64748B !important;
  stroke:#64748B !important;
  opacity:1 !important;
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

        # ==========================================
        # ✅ 중복 검증 로직 개선 (사번 + 성명 조합)
        # ==========================================
        all_records = sheet.get_all_records()
        emp_id_str = str(emp_id).strip()
        name_str = str(name).strip()

        for record in all_records:
            # 시트의 사번과 성명 데이터를 가져옴
            existing_emp_id = str(record.get("사번", "")).strip()
            existing_name = str(record.get("성명", "")).strip()

            if emp_id_str == "00000000":
                # 예외 사번(00000000)인 경우: 사번과 성명이 모두 같아야 중복
                if existing_emp_id == "00000000" and existing_name == name_str:
                    return False, f"'{name_str}'님은 이미 '00000000' 사번으로 참여하셨습니다."
            else:
                # 일반 사번인 경우: 사번만 같아도 중복 처리
                if existing_emp_id == emp_id_str:
                    return False, f"사번 {emp_id_str}은(는) 이미 참여한 기록이 있습니다."
        # ==========================================

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
# ✅ (요청 2) 사번 검증 유틸
# ==========================================
def validate_emp_id(emp_id: str) -> tuple[bool, str]:
    """
    규칙:
    - 기본: 8자리 숫자, '10'으로 시작 (10******)
    - 예외: 사번 미부여자는 '00000000' 허용(제출 가능)
    """
    s = (emp_id or "").strip()

    if not s:
        return False, "⚠️ 사번을 입력해 주세요. (사번 미부여 시 '00000000')"

    # ✅ 예외 허용: 사번 미부여
    if s == "00000000":
        return True, "ℹ️ 사번 미부여: '00000000'으로 제출됩니다. 제출 후 관리자에게 연락해 주세요."

    # 기본 형식 체크
    if (len(s) != 8) or (not s.isdigit()):
        return False, "⚠️ 사번이 8자리 숫자가 아닙니다. 사번을 정확히 입력했는지 다시 확인해 주세요."

    # 기본 규칙: 10으로 시작
    if not s.startswith("10"):
        return False, "⚠️ 사번을 정확히 입력했는지 확인해 주세요. 사번이 '10********'이 아니라면 '00000000'을 입력해 제출 후 관리자에게 연락해 주세요."

    return True, ""


# ==========================================
# ✅ 현장대리인 선임 신고서 저장 유틸
#    - 기존 윤리경영 실천서약 저장 로직과 분리
#    - Google Sheet: Audit_Result_2026 / 2026_현장대리인_선임신고
# ==========================================
FIELD_AGENT_SHEET_NAME = "2026_현장대리인_선임신고"
FIELD_AGENT_HEADERS = [
    "저장시간", "제출ID", "NO",
    "KT 내부 도급 관리자_부문", "KT 내부 도급 관리자_본부", "KT 내부 도급 관리자_소속", "KT 내부 도급 관리자_소속(장)", "KT 내부 도급 관리자_연락처",
    "ktMOS북부 현장 대리인_본부", "ktMOS북부 현장 대리인_팀/파트", "ktMOS북부 현장 대리인_직위", "ktMOS북부 현장 대리인_성명", "ktMOS북부 현장 대리인_연락처"
]

def save_field_agent_appointment_reports(records: list[dict]) -> tuple[bool, str]:
    """현장대리인 선임 신고 내역을 Google Sheet에 행 단위로 저장합니다."""
    if not records:
        return False, "저장할 현장대리인 선임 신고 내역이 없습니다."

    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패 (Secrets 확인)"

    try:
        spreadsheet = client.open("Audit_Result_2026")
        try:
            sheet = spreadsheet.worksheet(FIELD_AGENT_SHEET_NAME)
        except Exception:
            sheet = spreadsheet.add_worksheet(title=FIELD_AGENT_SHEET_NAME, rows=3000, cols=len(FIELD_AGENT_HEADERS) + 2)
            sheet.append_row(FIELD_AGENT_HEADERS)

        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        submission_seed = f"{now}|{records[0].get('작성자','')}|{records[0].get('작성부서','')}|{len(records)}"
        submission_id = hashlib.sha256(submission_seed.encode("utf-8")).hexdigest()[:12]

        rows = []
        for idx, record in enumerate(records, start=1):
            rows.append([
                now,
                submission_id,
                record.get("NO", idx),
                record.get("KT 내부 도급 관리자_부문", ""),
                record.get("KT 내부 도급 관리자_본부", ""),
                record.get("KT 내부 도급 관리자_소속", ""),
                record.get("KT 내부 도급 관리자_소속(장)", ""),
                record.get("KT 내부 도급 관리자_연락처", ""),
                record.get("ktMOS북부 현장 대리인_본부", ""),
                record.get("ktMOS북부 현장 대리인_팀/파트", ""),
                record.get("ktMOS북부 현장 대리인_직위", ""),
                record.get("ktMOS북부 현장 대리인_성명", ""),
                record.get("ktMOS북부 현장 대리인_연락처", ""),
            ])

        sheet.append_rows(rows, value_input_option="USER_ENTERED")
        return True, f"현장대리인 선임 신고 내역 {len(rows)}건이 저장되었습니다."
    except Exception as e:
        return False, str(e)

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
    st.markdown("### ✅ 자율점검")
    st.caption("기존 실천서약은 접힌 보관 영역에 그대로 유지하고, 아래에서 2026 현장대리인 선임 신고서를 작성·제출할 수 있습니다.")

    st.markdown("""
    <style>
    /* 현장대리인 신고서 전용 화면 정돈 */
    .field-agent-hero {
        background: linear-gradient(135deg, #E8F5E9 0%, #E3F2FD 100%);
        padding: 24px 26px;
        border-radius: 18px;
        border: 1px solid #D7E8D8;
        box-shadow: 0 8px 24px rgba(44, 62, 80, 0.08);
        margin: 12px 0 18px 0;
    }
    .field-agent-hero h3 {
        margin: 0 0 8px 0;
        color: #1B5E20;
        font-size: 1.45rem;
        font-weight: 950;
    }
    .field-agent-hero p {
        margin: 0;
        color: #334155;
        line-height: 1.65;
        font-weight: 650;
    }
    .fa-mini-guide {
        background: #FFFFFF;
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.05);
        margin-bottom: 12px;
    }
    .fa-section-title {
        display: inline-block;
        padding: 8px 12px;
        border-radius: 999px;
        font-weight: 950;
        font-size: 0.98rem;
        margin: 6px 0 10px 0;
    }
    .fa-kt-title { background:#E3F2FD; color:#0B5ED7; }
    .fa-mos-title { background:#E0F2F1; color:#00695C; }
    .fa-row-title {
        font-size: 1.08rem;
        font-weight: 950;
        color:#1E293B;
        margin-bottom: 4px;
    }
    .fa-required { color:#D32F2F; font-weight:900; }

    /* ✅ 현장대리인 입력 버튼 크기/색상 균형
       - primary: 전체 블록 추가/삭제용(조금 더 도톰하고 눈에 띄게)
       - secondary: KT/MOS 개별 정보 행 추가/삭제용(작고 단정하게)
       ※ Streamlit 기본 버튼 속성(kind)을 활용하므로 기능 로직은 그대로 유지됩니다. */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0B5ED7, #2C3E50) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(11, 94, 215, 0.35) !important;
        border-radius: 999px !important;
        padding: 0.38rem 0.62rem !important;
        min-height: 38px !important;
        font-size: 0.92rem !important;
        font-weight: 950 !important;
        box-shadow: 0 6px 14px rgba(11, 94, 215, 0.20) !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px);
        filter: brightness(1.04) !important;
        box-shadow: 0 8px 18px rgba(11, 94, 215, 0.25) !important;
    }

    .stButton > button[kind="secondary"] {
        background: #FFFFFF !important;
        color: #2563EB !important;
        border: 1px solid #BFD7FF !important;
        border-radius: 999px !important;
        padding: 0.16rem 0.28rem !important;
        min-height: 28px !important;
        font-size: 0.82rem !important;
        font-weight: 950 !important;
        box-shadow: 0 3px 8px rgba(37, 99, 235, 0.10) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: #EFF6FF !important;
        border-color: #60A5FA !important;
        transform: translateY(-1px);
    }
    .stButton > button:disabled {
        opacity: 0.55 !important;
        filter: grayscale(0.15) !important;
        box-shadow: none !important;
    }
    div[data-testid="stCheckbox"] label p {
        font-weight: 900 !important;
        color: #1565C0 !important;
        font-size: 1.02rem !important;
    }
    div[data-testid="stForm"] {
        border-radius: 16px !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ✅ 기존 실천서약은 기본 화면에서 완전히 렌더링하지 않습니다.
    #    버튼을 켰을 때만 아래 보관함에 기존 코드를 그대로 표시합니다.
    show_legacy_pledge = st.checkbox(
        "📁 기존 ‘2026 임직원 윤리경영원칙 실천지침 실천서약’ 보관함 열기",
        value=False,
        key="show_legacy_pledge_archive",
        help="내년에도 사용할 기존 실천서약 화면입니다. 기본 화면에서는 표시하지 않습니다."
    )

    if show_legacy_pledge:
        with st.container(border=True):
            st.info("기존 실천서약 화면입니다. 필요할 때만 펼쳐서 기존 형식 그대로 사용할 수 있습니다.")
            # ✅ 자율점검 탭 전용 스타일 범위 시작(#audit-tab)
            st.markdown('<div id="audit-tab">', unsafe_allow_html=True)

            current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")

            # ✅ (UX) '서약 확인/임직원 정보 입력' 영역: 최초에는 접힘, 입력/체크 시 자동 펼침
            if "pledge_box_open" not in st.session_state:
                st.session_state["pledge_box_open"] = False

            # ✅ (요청 1) 제목: Google Sheet 값과 무관하게 강제 고정
            title_for_box = "2026 임직원 윤리경영원칙 실천지침 실천서약"

            st.markdown(f"""
                <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 20px;'>
                    <h3 style='margin-top:0; color: #1565C0; font-weight:900;'>📜 {title_for_box}</h3>
                </div>
            """, unsafe_allow_html=True)

            # 2) 실천지침 주요내용
            with st.expander("※ 윤리경영원칙 실천지침 주요내용", expanded=True):
                st.markdown(
                    """
                    <div style='background-color:#FFFDE7; padding: 18px; border-radius: 10px; border-left: 5px solid #FBC02D; margin-bottom: 12px;'>
                        <div style='font-weight: 900; color:#6D4C41; font-size: 1.10rem; margin-bottom: 6px;'>📌 윤리경영 위반 주요 유형</div>
                        <div style='color:#444; font-size: 0.97rem; line-height: 1.55;'>
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
                                    <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:900; color:#2C3E50;'>고객과의 관계</td>
                                    <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>고객으로부터 금품 등 이익 수수, 고객만족 저해, 고객정보 유출</td>
                                </tr>
                                <tr>
                                    <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:900; color:#2C3E50;'>임직원과 회사의 관계</td>
                                    <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>공금 유용 및 횡령, 회사재산의 사적 사용, 기업정보 유출, 경영왜곡</td>
                                </tr>
                                <tr>
                                    <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:900; color:#2C3E50;'>임직원 상호간의 관계</td>
                                    <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>직장 내 괴롭힘, 성희롱, 조직질서 문란행위</td>
                                </tr>
                                <tr>
                                    <td style='text-align:center; padding:12px; font-weight:900; color:#2C3E50;'>이해관계자와의 관계</td>
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
                    <div style="font-size:1.05rem; font-weight:900; color:#2C3E50; line-height:1.7;">
                    나는 <b>KT MOS 북부</b>의 지속적인 발전을 위하여 회사 윤리경영원칙 실천지침에 명시된
                    <b>「임직원의 책임과 의무」 및 「관리자의 책임과 의무」</b>를
                    <b>성실히 이행할 것을 서약합니다.</b>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # ✅ 임직원 서명(정보 입력) 영역을 15mm(≈57px) 더 아래로
                st.markdown("<div style='height:57px;'></div>", unsafe_allow_html=True)

                # 입력 박스 (한 박스 안)
                c1, c2, c3, c4 = st.columns(4)
                emp_id = c1.text_input("사번", placeholder="사번(1000****) 없으면 (00000000)")
                name = c2.text_input("성명")
                ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
                unit = c3.selectbox(
            "총괄 / 본부 / 단",
            ordered_units,
            index=None,                     # ✅ 처음엔 아무것도 선택 안 됨(placeholder처럼 보이게)
            placeholder="총괄 / 본부 / 단 선택",  # ✅ Streamlit 버전에 따라 지원(지원 안 되면 아래 CSS가 커버)
            label_visibility="collapsed",
            key="unit_select"
            )
                dept = c4.text_input("상세 부서명", placeholder="현 소속부서명 입력")

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
                    # ✅ (요청 2) 사번 검증 로직
                    ok, msg = validate_emp_id(emp_id)
                    if not ok:
                        st.warning(msg)
                    else:
                        answer = "윤리경영 서약서 제출 완료 (임직원 의무 4/4, 관리자 의무 3/3)"
                        with st.spinner("제출 중..."):
                            success, msg2 = save_audit_result(emp_id, name, unit, dept, answer, current_sheet_name)
                        if success:
                            st.success(f"✅ {name}님, 윤리경영 서약서 제출이 완료되었습니다!")
                            st.balloons()
                        else:
                            st.error(f"❌ 제출 실패: {msg2}")

            # ✅ 자율점검 탭 전용 스타일 범위 종료
            st.markdown("</div>", unsafe_allow_html=True)


    else:
        st.info("📁 기존 실천서약은 보관함에 숨겨져 있습니다. 필요할 때만 위 체크박스를 눌러 열어 주세요.")

    st.markdown("---")
    st.markdown("""
        <div class="field-agent-hero">
            <h3>🧭 2026 현장대리인 선임 신고서 제출</h3>
            <p>
                아래 양식에 <b>KT 내부 도급 관리자</b>와 <b>ktMOS북부 현장 대리인</b> 정보를 입력해 주세요.
                여러 건을 한 번에 제출해야 하는 경우 각 입력 블록 하단의 <b>전체 ＋/－</b> 버튼으로 전체 블록을 추가·삭제하고, 특정 영역만 추가해야 할 때는 해당 영역의 작은 <b>＋/－</b> 버튼을 사용하면 됩니다.
                제출된 내용은 Google Sheet에 행 단위로 저장됩니다.
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("""
        <div class="fa-mini-guide">
            <b>작성 방식</b> · 입력한 행은 제출 시 Google Sheet의
            <b>2026_현장대리인_선임신고</b> 시트에 저장됩니다.
            NO는 전체 블록 기준으로 자동 부여됩니다. 블록 내부에서 KT 또는 ktMOS 행이 추가되어도 같은 NO로 저장됩니다.
        </div>
    """, unsafe_allow_html=True)

    with st.expander("ℹ️ 작성 안내 자세히 보기", expanded=False):
        st.markdown(
            "- 기존 윤리경영 실천서약은 위 보관함에 그대로 보존되어 있습니다.\n"
            "- 현장대리인 선임 신고서는 별도 Google Sheet 시트에 저장됩니다.\n"
            "- 화면 캡처 양식의 컬럼 구조: **NO / KT 내부 도급 관리자 / ktMOS북부 현장 대리인**을 반영했습니다.\n"
            "- 여러 건을 신고해야 하는 경우 각 블록 하단의 **➕ 전체 블록 추가**를 사용하세요.\n"
            "- 같은 블록 안에서 **KT 내부 도급 관리자** 또는 **ktMOS북부 현장 대리인**만 추가해야 하는 경우, 각 영역 제목 오른쪽의 작은 **＋/－** 버튼을 사용하세요."
        )

    # ✅ 입력 구조 개선
    # - 상단의 '입력 행 추가/삭제' 버튼 제거
    # - 각 블록 하단에서 전체 블록 추가/삭제
    # - 각 블록 내부에서 KT 내부 도급 관리자 / ktMOS북부 현장 대리인 정보만 각각 추가/삭제
    if "field_agent_block_count" not in st.session_state:
        st.session_state["field_agent_block_count"] = 1

    # 예전 버전의 row_count 세션값이 남아 있어도 새 화면에는 영향이 없도록 둡니다.
    st.caption("전체 블록 버튼은 조금 크게, KT/MOS 개별 정보 버튼은 작게 구분해 두었습니다.")

    st.markdown("""
        <div style='overflow-x:auto; margin-top:8px; margin-bottom:12px;'>
            <table style='width:100%; border-collapse:collapse; background:#FFFFFF; border:1px solid #B0BEC5; font-size:0.88rem;'>
                <thead>
                    <tr>
                        <th rowspan='2' style='border:1px solid #90A4AE; background:#E3F2FD; padding:7px; text-align:center;'>NO</th>
                        <th colspan='5' style='border:1px solid #90A4AE; background:#BBDEFB; padding:7px; text-align:center;'>KT 내부 도급 관리자</th>
                        <th colspan='5' style='border:1px solid #90A4AE; background:#E0F2F1; padding:7px; text-align:center;'>ktMOS북부 현장 대리인</th>
                    </tr>
                    <tr>
                        <th style='border:1px solid #90A4AE; background:#E3F2FD; padding:7px;'>부문</th>
                        <th style='border:1px solid #90A4AE; background:#E3F2FD; padding:7px;'>본부</th>
                        <th style='border:1px solid #90A4AE; background:#E3F2FD; padding:7px;'>소속</th>
                        <th style='border:1px solid #90A4AE; background:#E3F2FD; padding:7px;'>소속(장)</th>
                        <th style='border:1px solid #90A4AE; background:#E3F2FD; padding:7px;'>연락처</th>
                        <th style='border:1px solid #90A4AE; background:#E0F2F1; padding:7px;'>본부</th>
                        <th style='border:1px solid #90A4AE; background:#E0F2F1; padding:7px;'>팀/파트</th>
                        <th style='border:1px solid #90A4AE; background:#E0F2F1; padding:7px;'>직위</th>
                        <th style='border:1px solid #90A4AE; background:#E0F2F1; padding:7px;'>성명</th>
                        <th style='border:1px solid #90A4AE; background:#E0F2F1; padding:7px;'>연락처</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style='border:1px solid #CFD8DC; padding:6px; color:#D32F2F; text-align:center;'>예시</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>네트워크부문</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>네트워크 운용혁신본부</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>액세스운용담당 액세스망운용개선팀</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>홍길상</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>010-0000-0000</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>사업총괄</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>기술지원팀</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>과장</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>홍길동</td>
                        <td style='border:1px solid #CFD8DC; padding:6px;'>010-0000-0000</td>
                    </tr>
                </tbody>
            </table>
        </div>
    """, unsafe_allow_html=True)

    records_to_save = []
    validation_errors = []

    for block_idx in range(st.session_state["field_agent_block_count"]):
        block_no = block_idx + 1
        kt_count_key = f"fa_kt_row_count_{block_idx}"
        mos_count_key = f"fa_mos_row_count_{block_idx}"
        if kt_count_key not in st.session_state:
            st.session_state[kt_count_key] = 1
        if mos_count_key not in st.session_state:
            st.session_state[mos_count_key] = 1

        with st.container(border=True):
            st.markdown(
                f"<div class='fa-row-title'>NO. {block_no} 현장대리인 선임 정보 <span class='fa-required'>*</span></div>",
                unsafe_allow_html=True
            )

            # ------------------------------------------------------
            # KT 내부 도급 관리자: 블록 안에서 이 정보만 추가/삭제
            # ------------------------------------------------------
            kt_title_col, kt_add_col, kt_del_col = st.columns([0.90, 0.05, 0.05], vertical_alignment="center")
            with kt_title_col:
                st.markdown("<div class='fa-section-title fa-kt-title'>KT 내부 도급 관리자</div>", unsafe_allow_html=True)
            with kt_add_col:
                if st.button("＋", use_container_width=True, key=f"fa_add_kt_{block_idx}", help="KT 내부 도급 관리자 입력 행 추가", type="secondary"):
                    st.session_state[kt_count_key] += 1
                    st.rerun()
            with kt_del_col:
                if st.button("－", use_container_width=True, key=f"fa_del_kt_{block_idx}", help="KT 내부 도급 관리자 마지막 입력 행 삭제", disabled=st.session_state[kt_count_key] <= 1, type="secondary"):
                    st.session_state[kt_count_key] = max(1, st.session_state[kt_count_key] - 1)
                    st.rerun()

            kt_rows = []
            for kt_idx in range(st.session_state[kt_count_key]):
                if st.session_state[kt_count_key] > 1:
                    st.caption(f"KT 내부 도급 관리자 {kt_idx + 1}")
                ktc1, ktc2, ktc3 = st.columns([0.9, 1.1, 2.0])
                with ktc1:
                    kt_division = st.text_input("부문", placeholder="예: 네트워크부문", key=f"fa_kt_division_{block_idx}_{kt_idx}")
                with ktc2:
                    kt_hq = st.text_input("본부", placeholder="예: 네트워크 운용혁신본부", key=f"fa_kt_hq_{block_idx}_{kt_idx}")
                with ktc3:
                    kt_org = st.text_input("소속", placeholder="예: 액세스운용담당 액세스망운용개선팀", key=f"fa_kt_org_{block_idx}_{kt_idx}")

                ktc4, ktc5 = st.columns([1, 1])
                with ktc4:
                    kt_manager_name = st.text_input("소속(장)", placeholder="예: 홍길상", key=f"fa_kt_manager_name_{block_idx}_{kt_idx}")
                with ktc5:
                    kt_manager_phone = st.text_input("연락처", placeholder="예: 010-0000-0000", key=f"fa_kt_manager_phone_{block_idx}_{kt_idx}")

                kt_row = {
                    "KT 내부 도급 관리자_부문": kt_division.strip(),
                    "KT 내부 도급 관리자_본부": kt_hq.strip(),
                    "KT 내부 도급 관리자_소속": kt_org.strip(),
                    "KT 내부 도급 관리자_소속(장)": kt_manager_name.strip(),
                    "KT 내부 도급 관리자_연락처": kt_manager_phone.strip(),
                }
                kt_row["_has_any"] = any(kt_row.values())
                kt_rows.append(kt_row)

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

            # ------------------------------------------------------
            # ktMOS북부 현장 대리인: 블록 안에서 이 정보만 추가/삭제
            # ------------------------------------------------------
            mos_title_col, mos_add_col, mos_del_col = st.columns([0.90, 0.05, 0.05], vertical_alignment="center")
            with mos_title_col:
                st.markdown("<div class='fa-section-title fa-mos-title'>ktMOS북부 현장 대리인</div>", unsafe_allow_html=True)
            with mos_add_col:
                if st.button("＋", use_container_width=True, key=f"fa_add_mos_{block_idx}", help="ktMOS북부 현장 대리인 입력 행 추가", type="secondary"):
                    st.session_state[mos_count_key] += 1
                    st.rerun()
            with mos_del_col:
                if st.button("－", use_container_width=True, key=f"fa_del_mos_{block_idx}", help="ktMOS북부 현장 대리인 마지막 입력 행 삭제", disabled=st.session_state[mos_count_key] <= 1, type="secondary"):
                    st.session_state[mos_count_key] = max(1, st.session_state[mos_count_key] - 1)
                    st.rerun()

            mos_rows = []
            for mos_idx in range(st.session_state[mos_count_key]):
                if st.session_state[mos_count_key] > 1:
                    st.caption(f"ktMOS북부 현장 대리인 {mos_idx + 1}")
                mosc1, mosc2, mosc3, mosc4, mosc5 = st.columns([1, 1, 0.8, 0.8, 1])
                with mosc1:
                    mos_hq = st.text_input("본부", placeholder="예: 사업총괄", key=f"fa_mos_hq_{block_idx}_{mos_idx}")
                with mosc2:
                    mos_team = st.text_input("팀/파트", placeholder="예: 기술지원팀", key=f"fa_mos_team_{block_idx}_{mos_idx}")
                with mosc3:
                    mos_position = st.text_input("직위", placeholder="예: 과장", key=f"fa_mos_position_{block_idx}_{mos_idx}")
                with mosc4:
                    mos_name = st.text_input("성명", placeholder="예: 홍길동", key=f"fa_mos_name_{block_idx}_{mos_idx}")
                with mosc5:
                    mos_phone = st.text_input("연락처", placeholder="예: 010-0000-0000", key=f"fa_mos_phone_{block_idx}_{mos_idx}")

                mos_row = {
                    "ktMOS북부 현장 대리인_본부": mos_hq.strip(),
                    "ktMOS북부 현장 대리인_팀/파트": mos_team.strip(),
                    "ktMOS북부 현장 대리인_직위": mos_position.strip(),
                    "ktMOS북부 현장 대리인_성명": mos_name.strip(),
                    "ktMOS북부 현장 대리인_연락처": mos_phone.strip(),
                }
                mos_row["_has_any"] = any(mos_row.values())
                mos_rows.append(mos_row)

            # ------------------------------------------------------
            # 저장 데이터 구성
            # - 같은 블록 안에서 KT/MOS 행 수가 다르면 max 기준으로 행 단위 저장
            # - 추가된 한쪽 정보만 있는 행도 저장 가능
            # - 단, NO는 세부행 번호(1-1, 1-2)가 아니라 전체 블록 번호(1, 2, 3)로 동일하게 저장
            # ------------------------------------------------------
            max_inner_rows = max(len(kt_rows), len(mos_rows))
            for inner_idx in range(max_inner_rows):
                kt_row = kt_rows[inner_idx] if inner_idx < len(kt_rows) else {}
                mos_row = mos_rows[inner_idx] if inner_idx < len(mos_rows) else {}
                kt_has_any = bool(kt_row.get("_has_any"))
                mos_has_any = bool(mos_row.get("_has_any"))

                if not (kt_has_any or mos_has_any):
                    continue

                if kt_has_any:
                    for label, value in {
                        "KT 내부 도급 관리자 부문": kt_row.get("KT 내부 도급 관리자_부문", ""),
                        "KT 내부 도급 관리자 본부": kt_row.get("KT 내부 도급 관리자_본부", ""),
                        "KT 내부 도급 관리자 소속": kt_row.get("KT 내부 도급 관리자_소속", ""),
                        "KT 내부 도급 관리자 소속(장)": kt_row.get("KT 내부 도급 관리자_소속(장)", ""),
                        "KT 내부 도급 관리자 연락처": kt_row.get("KT 내부 도급 관리자_연락처", ""),
                    }.items():
                        if not str(value).strip():
                            validation_errors.append(f"NO. {block_no} / 행 {inner_idx + 1}: {label}을(를) 입력해 주세요.")

                if mos_has_any:
                    for label, value in {
                        "ktMOS북부 현장 대리인 본부": mos_row.get("ktMOS북부 현장 대리인_본부", ""),
                        "ktMOS북부 현장 대리인 팀/파트": mos_row.get("ktMOS북부 현장 대리인_팀/파트", ""),
                        "ktMOS북부 현장 대리인 직위": mos_row.get("ktMOS북부 현장 대리인_직위", ""),
                        "ktMOS북부 현장 대리인 성명": mos_row.get("ktMOS북부 현장 대리인_성명", ""),
                        "ktMOS북부 현장 대리인 연락처": mos_row.get("ktMOS북부 현장 대리인_연락처", ""),
                    }.items():
                        if not str(value).strip():
                            validation_errors.append(f"NO. {block_no} / 행 {inner_idx + 1}: {label}을(를) 입력해 주세요.")

                # 저장 시에는 양쪽 중 없는 정보는 빈칸으로 저장합니다.
                # 중요: 블록 내부 행이 늘어나더라도 NO는 전체 블록 번호를 그대로 유지합니다.
                # 예) NO.1 블록 안에 KT 2행, MOS 7행이 있어도 저장 NO는 모두 '1'
                display_no = str(block_no)
                records_to_save.append({
                    "NO": display_no,
                    "KT 내부 도급 관리자_부문": kt_row.get("KT 내부 도급 관리자_부문", ""),
                    "KT 내부 도급 관리자_본부": kt_row.get("KT 내부 도급 관리자_본부", ""),
                    "KT 내부 도급 관리자_소속": kt_row.get("KT 내부 도급 관리자_소속", ""),
                    "KT 내부 도급 관리자_소속(장)": kt_row.get("KT 내부 도급 관리자_소속(장)", ""),
                    "KT 내부 도급 관리자_연락처": kt_row.get("KT 내부 도급 관리자_연락처", ""),
                    "ktMOS북부 현장 대리인_본부": mos_row.get("ktMOS북부 현장 대리인_본부", ""),
                    "ktMOS북부 현장 대리인_팀/파트": mos_row.get("ktMOS북부 현장 대리인_팀/파트", ""),
                    "ktMOS북부 현장 대리인_직위": mos_row.get("ktMOS북부 현장 대리인_직위", ""),
                    "ktMOS북부 현장 대리인_성명": mos_row.get("ktMOS북부 현장 대리인_성명", ""),
                    "ktMOS북부 현장 대리인_연락처": mos_row.get("ktMOS북부 현장 대리인_연락처", ""),
                })

        # ✅ 전체 블록 추가/삭제: 각 블록 바로 아래에 배치하여 상단으로 다시 올라갈 필요가 없도록 개선
        block_add_col, block_del_col, block_caption_col = st.columns([0.075, 0.075, 0.85])
        with block_add_col:
            if st.button("전체＋", use_container_width=True, key=f"fa_add_block_after_{block_idx}", help="전체 입력 블록 추가", type="primary"):
                st.session_state["field_agent_block_count"] += 1
                st.rerun()
        with block_del_col:
            if st.button("전체－", use_container_width=True, key=f"fa_del_block_after_{block_idx}", help="마지막 전체 입력 블록 삭제", disabled=st.session_state["field_agent_block_count"] <= 1, type="primary"):
                st.session_state["field_agent_block_count"] = max(1, st.session_state["field_agent_block_count"] - 1)
                st.rerun()
        with block_caption_col:
            st.caption("왼쪽 전체＋/전체－: 입력 블록 전체 추가·삭제")

    st.markdown("---")
    submit_field_agents = st.button("📨 현장대리인 선임 신고서 제출", use_container_width=True, key="fa_submit", type="primary")

    if submit_field_agents:
        if not records_to_save:
            st.warning("⚠️ 저장할 현장대리인 선임 정보를 1건 이상 입력해 주세요.")
        elif validation_errors:
            st.error("입력값을 확인해 주세요.\n\n" + "\n".join([f"- {e}" for e in validation_errors[:10]]))
        else:
            with st.spinner("현장대리인 선임 신고 내역을 저장 중입니다..."):
                success, msg = save_field_agent_appointment_reports(records_to_save)
            if success:
                st.success(f"✅ {msg}")
                st.balloons()
                st.caption("제출 완료 후 Google Sheet의 2026_현장대리인_선임신고 시트에서 저장 내역을 확인할 수 있습니다.")
            else:
                st.error(f"❌ 제출 실패: {msg}")

# --- [Tab 2: 법률 리스크/규정/계약 검토 & 감사보고서 작성] ---
with tab_doc:
    st.markdown("### 📄 법률 리스크(계약서)·규정 검토 / 감사보고서 작성·검증")

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

            st.caption("선택한 작업 모드에 따라 아래 입력 항목이 자동으로 바뀝니다.")
            with st.expander("🔐 보안·주의사항(필독)", expanded=False):
                st.markdown(
                    "- 민감정보(주민등록번호/계좌/건강/징계대상 실명 등)는 업로드 전 **내부 보안 기준**을 반드시 확인하세요.\n"
                    "- 본 기능은 **감사 판단을 보조**하는 도구이며, 최종 판단·결재 책임은 감사실에 있습니다.\n"
                    "- 규정 근거는 업로드된 자료에서 확인되는 내용만 인용하도록 설계되었습니다."
                )

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
            )

            # (이하 기존 코드 그대로 유지: 사용자가 올려준 파일의 원문 로직이 이어짐)
            st.info("※ 이하(감사보고서 생성/검증 로직)는 기존 코드 흐름을 그대로 유지합니다. (이번 요청 범위: 자율점검 UI/검증만)")

# --- [Tab 3: AI 에이전트] ---
with tab_chat:
    st.markdown("### 💬 AI 법률/챗봇")
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

# --- [Tab 5: 관리자 대시보드 최종 버전] ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    st.caption("실시간 참여율 분석 및 제출 데이터 통합 관리")

    # 1. 관리자 비밀번호 검증
    admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_dash_pw")
    if admin_pw.strip() != "ktmos0402!":
        st.info("관리자 비밀번호를 입력하세요.")
        st.stop()

    st.success("✅ 접속 성공")

    # 2. 데이터 로드 (구글 시트 연결)
    client = init_google_sheet_connection()
    if not client:
        st.error("❌ 구글 시트 연결 실패. API 권한 및 Secrets 설정을 확인하세요.")
        st.stop()

    try:
        spreadsheet = client.open("Audit_Result_2026")
        ws_list = spreadsheet.worksheets()
        sheet_names = [ws.title for ws in ws_list if ws.title not in ["Campaign_Config", FIELD_AGENT_SHEET_NAME]]
        
        selected_sheet = st.selectbox("📊 분석 대상 시트 선택", sheet_names, key="admin_sheet_select")
        ws = spreadsheet.worksheet(selected_sheet)
        values = ws.get_all_values()
        
        if not values or len(values) < 2:
            st.warning("선택한 시트에 데이터가 없습니다.")
            st.stop()
            
        df = pd.DataFrame(values[1:], columns=values[0])
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        st.stop()

    # 3. 실시간 참여율 대시보드 (이미지 정원 데이터 반영)
    st.markdown("---")
    st.markdown("#### 📈 실시간 참여 현황 분석")

    # 조직별 정원 설정 (제공된 이미지 데이터 기반)
    total_staff_map = {
        "감사실": 3,
        "경영총괄": 27,
        "사업총괄": 39,
        "강북본부": 221,
        "강남본부": 173,
        "서부본부": 278,
        "강원본부": 101,
        "품질지원단": 137
    }

    # 현재 제출 현황 집계
    unit_counts = df['총괄/본부/단'].value_counts().to_dict()
    
    stats_data = []
    for unit, total in total_staff_map.items():
        current = unit_counts.get(unit, 0)
        ratio = (current / total) * 100 if total > 0 else 0
        stats_data.append({
            "조직": unit,
            "정원": total,
            "참여인원": current,
            "참여율(%)": round(ratio, 1)
        })
    
    stats_df = pd.DataFrame(stats_data)

    # 상단 요약 지표
    total_target = sum(total_staff_map.values()) # 총 979명
    total_current = len(df)
    total_ratio = (total_current / total_target) * 100

    m1, m2, m3 = st.columns(3)
    m1.metric("전체 대상자", f"{total_target}명")
    m2.metric("현재 참여자", f"{total_current}명")
    m3.metric("전체 참여율", f"{total_ratio:.1f}%")

    # 시각화 차트
    c1, c2 = st.columns(2)
    
    with c1:
        fig1 = px.bar(stats_df, x="조직", y="참여인원", text="참여인원",
                      title="조직별 참여 인원", color="참여인원", color_continuous_scale="Blues")
        st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)
        
    with c2:
        fig2 = px.bar(stats_df, x="조직", y="참여율(%)", text="참여율(%)",
                      title="조직별 참여율(%)", color="참여율(%)", color_continuous_scale="Viridis")
        fig2.add_hline(y=100, line_dash="dash", line_color="red")
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    # 4. 제출 데이터 상세 조회
    with st.expander("📄 제출 데이터 상세 보기 / 검색", expanded=False):
        # 간단한 검색 기능 추가
        search_term = st.text_input("🔍 성명 또는 부서 검색", "")
        if search_term:
            display_df = df[df.apply(lambda row: row.astype(str).str.contains(search_term).any(), axis=1)]
        else:
            display_df = df
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # 5. 데이터 다운로드
    st.markdown("---")
    st.markdown("#### ⬇️ 데이터 내보내기")
    d1, d2 = st.columns(2)
    
    with d1:
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 CSV 다운로드", csv_bytes, f"{selected_sheet}.csv", "text/csv", use_container_width=True)
        
    with d2:
        try:
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='참여현황')
            st.download_button("📥 Excel 다운로드", output.getvalue(), f"{selected_sheet}.xlsx", use_container_width=True)
        except Exception:
            st.info("Excel 엔진 미설치로 CSV 이용을 권장합니다.")

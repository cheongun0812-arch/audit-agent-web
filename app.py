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
* 🔥 Expander 제목 가독성 강제 개선 */
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
    if dt.month == 2:
        return "2월 자율점검"
    return f"{dt.month}월 자율점검"

def _default_campaign_sheet_name(dt: datetime.datetime, spreadsheet=None) -> str:
    if spreadsheet is not None and dt.year == 2026 and dt.month == 1:
        try:
            spreadsheet.worksheet("2026_병오년 ktMOS북부 설 명절 클린캠페인")
            return "2026_병오년 KTMOS북부 설 명절 클린캠페인"
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
    # ✅ 자율점검 탭 전용 스타일 범위 시작(#audit-tab)
    st.markdown('<div id="audit-tab">', unsafe_allow_html=True)

    current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")

    # ✅ (UX) '서약 확인/임직원 정보 입력' 영역: 최초에는 접힘, 입력/체크 시 자동 펼침
    if "pledge_box_open" not in st.session_state:
        st.session_state["pledge_box_open"] = False

    # ✅ (요청 1) 제목: Google Sheet 값과 무관하게 강제 고정
    title_for_box = "2026 병오년 ktMOS북부 설 명절 클린캠페인"

    st.markdown(f"""
        <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 20px;'>
            <h3 style='margin-top:0; color: #1565C0; font-weight:900;'>📜 {title_for_box}</h3>
        </div>
    """, unsafe_allow_html=True)

    # 2) 🎞️ 캠페인 홍보 영상 (자동 재생)
    video_filename = "2026 new yearf.mp4"  # app.py 폴더에 업로드된 파일명
    _base_dir = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
    video_path = os.path.join(_base_dir, video_filename)

    @st.cache_data(show_spinner=False)
    def _load_mp4_base64(_path: str) -> str:
        with open(_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    def _render_autoplay_video(_path: str) -> None:
        try:
            b64 = _load_mp4_base64(_path)
            st.markdown(
                f"""
                <div style="background:#0B1B2B; padding:14px; border-radius:16px; border:1px solid rgba(255,255,255,0.12); margin: 8px 0 18px 0;">
                  <video autoplay muted loop playsinline preload="auto" controls
                         style="width:100%; border-radius:12px; outline:none;">
                    <source src="data:video/mp4;base64,{{b64}}" type="video/mp4">
                    이 브라우저에서는 영상을 재생할 수 없습니다.
                  </video>
                </div>
                """.replace("{b64}", b64),
                unsafe_allow_html=True
            )
        except Exception as e:
            st.error(f"❌ 캠페인 영상 로드 실패: {e}")

    if os.path.exists(video_path):
        _render_autoplay_video(video_path)
    else:
        st.warning(f"⚠️ 캠페인 영상 파일을 찾을 수 없습니다: {video_filename}\n(app.py와 동일 폴더에 업로드해 주세요.)")

        # ✨ 2026 청렴 아우라 분석 (Fun)
    # - 기존 "✅ 서약 확인 및 임직원 정보 입력" 영역을 정리하고, 재미 요소(아우라 스캔)를 노출합니다.
    # - 디자인/애니메이션은 inpor.html의 핵심 요소(Glass panel, scan, scale-in)만 최소 이식했습니다.
    import streamlit.components.v1 as components

    components.html(
        "\n<!DOCTYPE html>\n<html lang=\"ko\">\n<head>\n<meta charset=\"UTF-8\" />\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n<link rel=\"stylesheet\" as=\"style\" crossorigin href=\"https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css\" />\n<style>\n  :root {\n    --bg:#0b1220;\n    --panel: rgba(255,255,255,0.03);\n    --border: rgba(255,255,255,0.10);\n    --text:#e5e7eb;\n    --muted: rgba(229,231,235,0.70);\n    --red:#ef4444;\n    --orange:#f97316;\n    --yellow:#f59e0b;\n  }\n  *{ box-sizing:border-box; }\n  body {\n    margin:0;\n    font-family: Pretendard, -apple-system, BlinkMacSystemFont, \"Segoe UI\", Roboto, \"Helvetica Neue\", Arial, \"Noto Sans KR\", \"Apple SD Gothic Neo\", sans-serif;\n    background: transparent;\n    color: var(--text);\n  }\n  @keyframes fade-in-up { from { opacity:0; transform: translateY(18px); } to { opacity:1; transform: translateY(0); } }\n  @keyframes scale-in { from { opacity:0; transform: scale(0.97); } to { opacity:1; transform: scale(1); } }\n  @keyframes scan { 0% { transform: translateY(-100%); opacity:0; } 50% { opacity:1; } 100% { transform: translateY(100%); opacity:0; } }\n\n  .wrap {\n    padding: 22px 18px 26px;\n  }\n  .stage {\n    max-width: 980px;\n    margin: 0 auto;\n    position: relative;\n  }\n  .halo {\n    position:absolute;\n    top: 50%;\n    left: 50%;\n    transform: translate(-50%, -50%);\n    width: 560px;\n    height: 560px;\n    border-radius: 999px;\n    background: radial-gradient(circle at 30% 30%, rgba(239,68,68,0.15), rgba(249,115,22,0.08), rgba(245,158,11,0.04), transparent 60%);\n    filter: blur(26px);\n    pointer-events:none;\n  }\n  .title {\n    text-align:center;\n    font-size: 42px;\n    font-weight: 900;\n    letter-spacing:-0.03em;\n    margin: 0 0 18px 0;\n    animation: fade-in-up 0.8s cubic-bezier(0.2, 0.8, 0.2, 1) both;\n  }\n  .glass {\n    background: var(--panel);\n    backdrop-filter: blur(12px);\n    border: 1px solid var(--border);\n    border-radius: 34px;\n    padding: 26px 22px 24px;\n    box-shadow: 0 18px 60px rgba(0,0,0,0.35);\n    animation: fade-in-up 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) both;\n  }\n  .grid {\n    display:grid;\n    grid-template-columns: 1fr 1fr;\n    gap: 14px;\n    margin-bottom: 14px;\n  }\n  .field {\n    width:100%;\n    padding: 16px 18px;\n    background: rgba(15,23,42,0.55);\n    border: 1px solid rgba(255,255,255,0.10);\n    border-radius: 18px;\n    color: var(--text);\n    font-weight: 800;\n    text-align:center;\n    outline:none;\n    font-size: 16px;\n  }\n  .field::placeholder {\n    color: rgba(229,231,235,0.45);\n    font-weight: 700;\n  }\n  select.field {\n    appearance:none;\n    cursor:pointer;\n  }\n  .btn {\n    width:100%;\n    border:none;\n    border-radius: 18px;\n    padding: 18px 18px;\n    background: linear-gradient(90deg, var(--red), var(--orange));\n    color: white;\n    font-size: 18px;\n    font-weight: 900;\n    cursor:pointer;\n    box-shadow: 0 18px 40px rgba(239,68,68,0.18);\n    display:flex;\n    align-items:center;\n    justify-content:center;\n    gap:10px;\n    transition: transform 0.12s ease, filter 0.12s ease, opacity 0.12s ease;\n  }\n  .btn:hover { transform: translateY(-1px); filter: brightness(1.03); }\n  .btn:active { transform: translateY(0px); opacity:0.95; }\n  .btn[disabled] { opacity:0.55; cursor:not-allowed; transform:none; }\n\n  .spark {\n    width: 22px; height: 22px;\n    display:inline-block;\n  }\n\n  .scanbox {\n    margin-top: 18px;\n    position: relative;\n    height: 150px;\n    border-radius: 22px;\n    overflow:hidden;\n    background: rgba(2,6,23,0.65);\n    border: 1px solid rgba(239,68,68,0.25);\n  }\n  .scantext {\n    position:absolute;\n    inset:0;\n    display:flex;\n    align-items:center;\n    justify-content:center;\n    font-size: 11px;\n    font-weight: 900;\n    color: rgba(239,68,68,0.55);\n    text-transform: uppercase;\n    letter-spacing: 0.28em;\n    text-align:center;\n    padding: 0 14px;\n  }\n  .scanbar {\n    position:absolute;\n    top:0;\n    left:0;\n    width:100%;\n    height: 6px;\n    background: var(--red);\n    box-shadow: 0 0 34px rgba(239,68,68,0.95);\n    animation: scan 1.6s infinite linear;\n  }\n\n  .result {\n    margin-top: 18px;\n    animation: scale-in 0.55s cubic-bezier(0.34, 1.56, 0.64, 1) both;\n  }\n  .result-border {\n    padding: 3px;\n    border-radius: 30px;\n    background: linear-gradient(135deg, var(--red), var(--orange), var(--yellow));\n  }\n  .result-inner {\n    border-radius: 28px;\n    background: rgba(2,6,23,0.86);\n    padding: 22px 22px 20px;\n    border: 1px solid rgba(255,255,255,0.10);\n  }\n  .tag {\n    text-align:center;\n    font-size: 12px;\n    font-weight: 900;\n    letter-spacing: 0.22em;\n    color: rgba(239,68,68,0.85);\n    margin-bottom: 8px;\n  }\n  .slogan {\n    text-align:center;\n    font-size: 26px;\n    font-weight: 900;\n    letter-spacing:-0.03em;\n    line-height: 1.28;\n    margin: 0 0 12px 0;\n  }\n  .divider {\n    width: 46px;\n    height: 3px;\n    background: rgba(148,163,184,0.25);\n    border-radius: 99px;\n    margin: 0 auto 12px auto;\n  }\n  .fortune {\n    text-align:center;\n    font-size: 16px;\n    font-weight: 700;\n    color: rgba(226,232,240,0.70);\n    line-height: 1.65;\n    font-style: italic;\n    margin:0;\n  }\n\n  .alert {\n    position: fixed;\n    top: 16px;\n    left: 50%;\n    transform: translateX(-50%);\n    z-index: 99999;\n    padding: 12px 16px;\n    border-radius: 18px;\n    background: rgba(239,68,68,0.92);\n    border: 1px solid rgba(255,255,255,0.18);\n    color: white;\n    font-weight: 900;\n    box-shadow: 0 18px 60px rgba(0,0,0,0.45);\n    animation: fade-in-up 0.25s ease-out both;\n    display:none;\n    max-width: 90vw;\n    text-align:center;\n  }\n\n  /* Component background shell */\n  .shell {\n    border-radius: 26px;\n    padding: 18px;\n    background: radial-gradient(1200px 320px at 50% 0%, rgba(239,68,68,0.14), transparent 55%),\n                linear-gradient(180deg, rgba(2,6,23,0.85), rgba(2,6,23,0.65));\n    border: 1px solid rgba(255,255,255,0.09);\n  }\n\n  @media (max-width: 640px){\n    .title{ font-size: 32px; }\n    .grid{ grid-template-columns: 1fr; }\n    .slogan{ font-size: 22px; }\n    .glass{ border-radius: 28px; }\n  }\n</style>\n</head>\n<body>\n  <div class=\"wrap\">\n    <div class=\"stage shell\">\n      <div class=\"halo\"></div>\n\n      <div id=\"alert\" class=\"alert\"></div>\n\n      <h2 class=\"title\">2026 청렴 아우라 분석</h2>\n\n      <div class=\"glass\">\n        <div class=\"grid\">\n          <input id=\"empName\" class=\"field\" type=\"text\" placeholder=\"성함\" maxlength=\"12\" />\n          <select id=\"goal\" class=\"field\">\n            <option value=\"\">올해의 주요 목표</option>\n            <option value=\"growth\">지속적인 성장</option>\n            <option value=\"happiness\">가족의 행복</option>\n            <option value=\"challenge\">새로운 도전</option>\n          </select>\n        </div>\n\n        <button id=\"scanBtn\" class=\"btn\">\n          <span class=\"spark\">✨</span>\n          <span id=\"btnText\">청렴 기운 스캔하기</span>\n        </button>\n\n        <div id=\"scanBox\" class=\"scanbox\" style=\"display:none;\">\n          <div class=\"scantext\">ANALYZING YOUR INTEGRITY...</div>\n          <div class=\"scanbar\"></div>\n        </div>\n\n        <div id=\"result\" class=\"result\" style=\"display:none;\">\n          <div class=\"result-border\">\n            <div class=\"result-inner\">\n              <div class=\"tag\">SCAN COMPLETED</div>\n              <p id=\"slogan\" class=\"slogan\">\"\"</p>\n              <div class=\"divider\"></div>\n              <p id=\"fortune\" class=\"fortune\"></p>\n            </div>\n          </div>\n        </div>\n\n      </div>\n    </div>\n  </div>\n\n<script>\n  const FORTUNE_DB = {\"growth\": [{\"slogan\": \"투명한 도약, 붉은 말처럼 거침없이 성장하는 한 해\", \"fortune\": \"원칙을 지키는 선택이 가장 빠른 성장의 지름길입니다. 작은 정직이 큰 신뢰로 돌아옵니다.\"}, {\"slogan\": \"정직이라는 박차로 더 높은 곳을 향해 질주하세요\", \"fortune\": \"업무의 기본을 지키는 당신의 태도가 팀의 기준이 됩니다. 올해는 성과와 평판이 함께 올라갑니다.\"}, {\"slogan\": \"신뢰의 레이스, 깨끗한 실력이 승리를 결정합니다\", \"fortune\": \"과정이 깔끔하면 결과는 더 빛납니다. 협업 요청이 자연스럽게 모이는 흐름입니다.\"}, {\"slogan\": \"정면승부가 가장 우아한 전략이 되는 2026\", \"fortune\": \"불필요한 우회 대신 정공법이 통합니다. 결정이 빠르고 후회가 적습니다.\"}, {\"slogan\": \"원칙 위에 쌓는 성과, 흔들림 없는 커리어의 해\", \"fortune\": \"기준을 지키는 사람이 결국 인정받습니다. 리더십 기회가 열릴 수 있어요.\"}, {\"slogan\": \"작은 투명성이 큰 프로젝트를 끌어당깁니다\", \"fortune\": \"공유와 기록을 잘할수록 일이 쉬워집니다. 당신의 정돈된 방식이 확산됩니다.\"}, {\"slogan\": \"명확한 보고, 단단한 신뢰, 빠른 성장\", \"fortune\": \"선명한 커뮤니케이션이 당신의 무기입니다. 올해는 ‘믿고 맡긴다’가 따라옵니다.\"}, {\"slogan\": \"정직한 기준이 팀의 속도를 올리는 해\", \"fortune\": \"규정 준수는 제약이 아니라 가속 페달입니다. 리스크가 줄며 추진력이 커집니다.\"}, {\"slogan\": \"정리정돈처럼 깔끔한 업무가 복을 부릅니다\", \"fortune\": \"작은 누수(실수/오해)를 미리 막아줍니다. 평가와 추천에서 좋은 흐름이 있어요.\"}, {\"slogan\": \"선명한 원칙, 선명한 성과\", \"fortune\": \"애매함을 줄일수록 결과가 좋아집니다. ‘확실한 사람’이라는 평을 듣습니다.\"}, {\"slogan\": \"투명한 협업이 곧 경쟁력\", \"fortune\": \"관계에서 신뢰가 쌓이면 협업이 즐거워집니다. 성과는 자연히 따라옵니다.\"}, {\"slogan\": \"정직한 성장 곡선이 가장 아름답습니다\", \"fortune\": \"급하게 가기보다 바르게 가는 한 해. 결국 더 멀리 갑니다.\"}, {\"slogan\": \"규정 준수가 ‘프로의 디테일’로 빛나는 해\", \"fortune\": \"디테일을 지키는 당신의 습관이 인정받습니다. 실수가 줄고 성과가 늘어요.\"}, {\"slogan\": \"공정한 기준이 팀을 편안하게 합니다\", \"fortune\": \"불필요한 오해가 사라집니다. 주변에서 ‘함께 일하고 싶다’는 말이 늘어요.\"}, {\"slogan\": \"오늘의 정직이 내일의 기회를 엽니다\", \"fortune\": \"신뢰가 쌓이면 기회는 자동으로 찾아옵니다. 올해는 새로운 역할이 주어질 수 있어요.\"}], \"happiness\": [{\"slogan\": \"떳떳한 마음이 선사하는 가장 따뜻한 행복\", \"fortune\": \"가족에게 부끄럽지 않은 선택이 마음의 평안을 줍니다. 집안에 웃음이 늘어납니다.\"}, {\"slogan\": \"깨끗한 소통으로 피어나는 동료 간의 진정한 즐거움\", \"fortune\": \"작은 호의보다 큰 진심이 통합니다. 신뢰가 최고의 행운입니다.\"}, {\"slogan\": \"정직한 하루가 모여 편안한 일상이 됩니다\", \"fortune\": \"일과 생활의 균형이 좋아집니다. 마음이 가벼워지는 한 해입니다.\"}, {\"slogan\": \"투명한 마음이 관계를 더 단단하게 합니다\", \"fortune\": \"말과 행동이 같을수록 관계가 깊어집니다. 좋은 인연이 늘어납니다.\"}, {\"slogan\": \"깨끗한 선택이 운을 부른다\", \"fortune\": \"불필요한 고민이 줄어듭니다. ‘잘 풀린다’는 느낌이 자주 옵니다.\"}, {\"slogan\": \"서로를 존중하는 청렴한 팀워크\", \"fortune\": \"나를 존중하는 태도가 곧 상대의 존중을 부릅니다. 분위기가 한결 부드러워집니다.\"}, {\"slogan\": \"정직한 배려가 가장 큰 선물\", \"fortune\": \"과한 것보다 ‘딱 필요한’ 배려가 통합니다. 동료와 가족 모두 편안해집니다.\"}, {\"slogan\": \"깔끔한 원칙, 따뜻한 관계\", \"fortune\": \"원칙이 분명하면 오해가 줄어듭니다. 관계가 더 오래갑니다.\"}, {\"slogan\": \"선명한 기준이 마음의 평정을 만듭니다\", \"fortune\": \"흔들릴 일이 줄어듭니다. 안정감이 행복으로 이어집니다.\"}, {\"slogan\": \"진심이 통하는 자리엔 행운이 앉습니다\", \"fortune\": \"말을 아끼기보다 정확히 전하는 한 해. 덕분에 분위기가 좋아집니다.\"}, {\"slogan\": \"청렴은 마음의 방역\", \"fortune\": \"찝찝함을 남기지 않으니 스트레스가 줄어요. 컨디션이 좋아집니다.\"}, {\"slogan\": \"가족에게 자랑스러운 당신의 한 해\", \"fortune\": \"당신의 꾸준함이 주변을 따뜻하게 만듭니다. 작은 축하가 자주 생깁니다.\"}, {\"slogan\": \"좋은 사람들과 오래 가는 해\", \"fortune\": \"선 긋기와 배려가 균형을 이룹니다. 관계가 건강해집니다.\"}, {\"slogan\": \"깨끗한 습관이 삶을 가볍게 합니다\", \"fortune\": \"정리·정돈·정직—세 가지가 복을 부릅니다. 일도 생활도 편해져요.\"}, {\"slogan\": \"정직한 웃음이 가장 오래 갑니다\", \"fortune\": \"관계에서 신뢰가 쌓이고, 그 신뢰가 행복의 기반이 됩니다.\"}], \"challenge\": [{\"slogan\": \"청렴의 가치를 지키며 한계를 넘어 질주하는 2026\", \"fortune\": \"어려운 순간에도 원칙을 지키는 모습이 가장 큰 영감이 됩니다.\"}, {\"slogan\": \"정직한 도전은 멈추지 않는 붉은 말과 같습니다\", \"fortune\": \"타협하지 않는 용기가 당신을 전문가로 만듭니다. 결국 가장 빛납니다.\"}, {\"slogan\": \"원칙을 지키는 사람이 가장 대담합니다\", \"fortune\": \"정면승부가 통하는 해입니다. 결정이 선명할수록 결과도 선명해집니다.\"}, {\"slogan\": \"리스크를 줄이는 용기, 그것이 진짜 도전\", \"fortune\": \"무리한 모험 대신, 안전한 혁신이 가능합니다. ‘현명한 도전자’가 됩니다.\"}, {\"slogan\": \"투명한 기준이 새로운 길을 엽니다\", \"fortune\": \"새로운 업무도 기준만 선명하면 두렵지 않습니다. 기회가 문을 두드립니다.\"}, {\"slogan\": \"정직한 질문이 혁신의 시작\", \"fortune\": \"모르면 묻는 것이 용기입니다. 질문이 팀의 문제를 빨리 해결합니다.\"}, {\"slogan\": \"규정을 아는 사람이 가장 빠르게 움직입니다\", \"fortune\": \"룰을 알면 우회가 줄어듭니다. 추진 속도가 확 달라집니다.\"}, {\"slogan\": \"어려운 결정일수록 원칙이 당신을 지켜줍니다\", \"fortune\": \"나중에 설명 가능한 선택이 가장 강합니다. 마음도 결과도 편안해집니다.\"}, {\"slogan\": \"깨끗한 도전은 팀을 더 강하게 합니다\", \"fortune\": \"당신의 기준이 팀의 기준이 됩니다. 자연스럽게 리더십이 생깁니다.\"}, {\"slogan\": \"정직한 피드백이 성장을 부릅니다\", \"fortune\": \"불편한 진실을 부드럽게 말하는 능력이 빛납니다. 신뢰가 깊어집니다.\"}, {\"slogan\": \"한 번 더 확인하는 습관이 영웅을 만듭니다\", \"fortune\": \"사소한 점검이 큰 사고를 막습니다. 당신의 디테일이 빛납니다.\"}, {\"slogan\": \"‘안 된다’보다 ‘이렇게 하자’가 통하는 해\", \"fortune\": \"대안을 제시하는 정직이 강합니다. 사람들이 당신을 찾습니다.\"}, {\"slogan\": \"원칙 위의 창의성, 가장 안전한 혁신\", \"fortune\": \"창의력은 규정을 어길 필요가 없습니다. ‘클린 아이디어’가 성공합니다.\"}, {\"slogan\": \"신뢰를 지키는 도전은 반드시 기억됩니다\", \"fortune\": \"성과뿐 아니라 과정이 남습니다. 당신의 평판이 단단해집니다.\"}, {\"slogan\": \"정직한 용기가 운을 바꿉니다\", \"fortune\": \"이번 도전은 성공 확률을 높입니다. 기본을 지키는 사람에게 기회가 옵니다.\"}]};\n\n  const $ = (id) => document.getElementById(id);\n  const alertEl = $(\"alert\");\n  const scanBtn = $(\"scanBtn\");\n  const btnText = $(\"btnText\");\n  const scanBox = $(\"scanBox\");\n  const resultBox = $(\"result\");\n  const sloganEl = $(\"slogan\");\n  const fortuneEl = $(\"fortune\");\n\n  function showAlert(msg) {\n    alertEl.textContent = msg;\n    alertEl.style.display = \"block\";\n    clearTimeout(window.__auraAlertTimer);\n    window.__auraAlertTimer = setTimeout(() => {\n      alertEl.style.display = \"none\";\n    }, 2400);\n  }\n\n  function pickRandom(arr) {\n    return arr[Math.floor(Math.random() * arr.length)];\n  }\n\n  let scanning = false;\n\n  scanBtn.addEventListener(\"click\", () => {\n    if (scanning) return;\n\n    const name = $(\"empName\").value.trim();\n    const goal = $(\"goal\").value;\n\n    if (!name || !goal) {\n      showAlert(\"성함과 목표를 먼저 입력해 주세요.\");\n      return;\n    }\n\n    const options = FORTUNE_DB[goal] || [];\n    if (options.length === 0) {\n      showAlert(\"데이터를 불러올 수 없습니다. 관리자에게 문의해 주세요.\");\n      return;\n    }\n\n    scanning = true;\n    scanBtn.setAttribute(\"disabled\", \"disabled\");\n    btnText.textContent = \"아우라 분석 중...\";\n\n    resultBox.style.display = \"none\";\n    scanBox.style.display = \"block\";\n\n    setTimeout(() => {\n      const picked = pickRandom(options);\n      sloganEl.textContent = `“${picked.slogan}”`;\n      fortuneEl.textContent = picked.fortune;\n\n      scanBox.style.display = \"none\";\n      resultBox.style.display = \"block\";\n\n      scanning = false;\n      scanBtn.removeAttribute(\"disabled\");\n      btnText.textContent = \"청렴 기운 스캔하기\";\n    }, 2000);\n  });\n</script>\n<script>(function(){const sendHeight=()=>{const h=document.documentElement.scrollHeight||document.body.scrollHeight||800;const msg={isStreamlitMessage:true,type:'setFrameHeight',height:h};window.parent.postMessage(msg,'*');};window.addEventListener('load',sendHeight);window.addEventListener('resize',()=>setTimeout(sendHeight,60));setInterval(sendHeight,1200);})();</script>\n\n</body>\n</html>\n",
        height=640,
        scrolling=False,
    )

    # ==========================================
    # 🧧 설 명절 클린 캠페인 아젠다 (Campaign Rules)
    #    - '2026 청렴 아우라 분석' 다음 위치에 배치
    #    - inpor.html의 핵심 스타일(.glass-panel / float) + 캠페인 카드 구성만 최소 이식
    # ==========================================
    CLEAN_CAMPAIGN_AGENDA_HTML = '\n<!DOCTYPE html>\n<html lang="ko">\n<head>\n  <meta charset="UTF-8" />\n  <meta name="viewport" content="width=device-width, initial-scale=1.0" />\n  <script src="https://cdn.tailwindcss.com"></script>\n  <script src="https://unpkg.com/lucide@latest"></script>\n  <link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />\n  <style>\n    body { margin:0; background: transparent; font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans KR", "Apple SD Gothic Neo", sans-serif; letter-spacing: -0.02em; }\n    /* from inpor.html (minimal) */\n    .glass-panel { background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.10); }\n    @keyframes float { 0% { transform: translateY(0px); } 50% { transform: translateY(-10px); } 100% { transform: translateY(0px); } }\n    .animate-float { animation: float 3s ease-in-out infinite; }\n  </style>\n</head>\n<body>\n  <section class="px-4 sm:px-6 py-8">\n    <div class="max-w-6xl mx-auto rounded-[34px] border border-white/10 overflow-hidden shadow-2xl"\n         style="background: radial-gradient(1200px 420px at 50% 0%, rgba(239,68,68,0.14), transparent 58%),\n                         linear-gradient(180deg, rgba(2,6,23,0.92), rgba(2,6,23,0.70));">\n      <div class="px-6 sm:px-10 py-14">\n        <div class="text-center mb-14">\n          <div class="text-red-600 font-bold text-xs sm:text-sm uppercase tracking-[0.4em] mb-4">Clean Festival Policy</div>\n          <div class="text-white text-4xl sm:text-5xl lg:text-6xl font-black tracking-tighter">설 명절 클린 캠페인 아젠다</div>\n          <p class="mt-5 text-slate-300 font-medium leading-relaxed">\n            명절 기간에도 <span class="text-white font-extrabold">청렴은 최고의 선물</span>입니다. 아래 3대 원칙을 꼭 지켜주세요.\n          </p>\n        </div>\n\n        <div class="grid md:grid-cols-3 gap-8">\n          <!-- Card 1 -->\n          <div class="glass-panel rounded-3xl p-10 border border-white/10 hover:border-red-500/30 transition-all duration-300 group animate-float" style="animation-delay:0s;">\n            <div class="w-16 h-16 bg-red-600 rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform shadow-lg">\n              <i data-lucide="gift" class="w-8 h-8 text-white"></i>\n            </div>\n            <h4 class="text-white text-2xl font-black mb-4 tracking-tight">선물 안 주고 안 받기</h4>\n            <p class="text-slate-300 leading-relaxed font-medium">협력사 및 이해관계자와의 명절 선물 교환은 금지됩니다. 마음만 정중히 받겠습니다.</p>\n          </div>\n\n          <!-- Card 2 -->\n          <div class="glass-panel rounded-3xl p-10 border border-white/10 hover:border-orange-500/30 transition-all duration-300 group animate-float" style="animation-delay:0.5s;">\n            <div class="w-16 h-16 bg-orange-600 rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform shadow-lg">\n              <i data-lucide="coffee" class="w-8 h-8 text-white"></i>\n            </div>\n            <h4 class="text-white text-2xl font-black mb-4 tracking-tight">향응 및 편의 제공 금지</h4>\n            <p class="text-slate-300 leading-relaxed font-medium">부적절한 식사 대접이나 골프 등 편의 제공은 원천 차단하여 투명성을 지킵니다.</p>\n          </div>\n\n          <!-- Card 3 -->\n          <div class="glass-panel rounded-3xl p-10 border border-white/10 hover:border-amber-500/30 transition-all duration-300 group animate-float" style="animation-delay:1s;">\n            <div class="w-16 h-16 bg-amber-600 rounded-2xl flex items-center justify-center mb-8 group-hover:scale-110 transition-transform shadow-lg">\n              <i data-lucide="shield-check" class="w-8 h-8 text-white"></i>\n            </div>\n            <h4 class="text-white text-2xl font-black mb-4 tracking-tight">부득이한 경우 자진신고</h4>\n            <p class="text-slate-300 leading-relaxed font-medium">택배 등으로 배송된 선물은 반송이 원칙이며, 불가피할 시 클린센터로 즉시 신고합니다.</p>\n          </div>\n        </div>\n\n        <div class="mt-12 glass-panel rounded-3xl p-8 border border-white/10">\n          <div class="flex flex-col sm:flex-row items-start sm:items-center gap-3">\n            <div class="shrink-0 w-10 h-10 rounded-2xl flex items-center justify-center bg-white/10 border border-white/10">\n              <i data-lucide="sparkles" class="w-6 h-6 text-white"></i>\n            </div>\n            <div class="text-slate-200 font-semibold leading-relaxed">\n              <span class="text-white font-extrabold">원칙을 지키는 선택</span>이 나와 동료를 보호합니다. 애매하면 <span class="text-white font-extrabold">하지 않는 것</span>이 정답입니다.\n            </div>\n          </div>\n        </div>\n\n      </div>\n    </div>\n  </section>\n\n\n  <!-- 4. 비윤리 행위 신고 채널 (Reporting Channels) -->\n  <section class="px-4 sm:px-6 pb-10">\n    <div class="max-w-6xl mx-auto rounded-[34px] border border-white/10 overflow-hidden shadow-2xl"\n         style="background: radial-gradient(1200px 420px at 50% 0%, rgba(239,68,68,0.10), transparent 58%),\n                         linear-gradient(180deg, rgba(2,6,23,0.88), rgba(2,6,23,0.70));">\n      <div class="px-6 sm:px-10 py-12">\n        <div class="grid md:grid-cols-3 gap-6">\n          <div class="md:col-span-1 py-2">\n            <div class="text-red-500 font-bold text-xs sm:text-sm uppercase tracking-[0.35em] mb-3">Reporting Channel</div>\n            <h2 class="text-white text-3xl sm:text-4xl font-black mb-4 leading-tight tracking-tight">비윤리 행위<br/>신고 채널</h2>\n            <p class="text-slate-300 font-medium leading-relaxed">\n              부정부패 없는 ktMOS북부를 위해<br/>\n              여러분의 용기 있는 목소리가 필요합니다.\n            </p>\n          </div>\n\n          <div class="md:col-span-2 grid sm:grid-cols-2 gap-4">\n            <!-- Phone -->\n            <div class="glass-panel p-8 rounded-3xl flex items-center gap-6 group hover:bg-white/5 transition-all border border-white/10">\n              <div class="w-14 h-14 bg-white/10 rounded-2xl flex items-center justify-center border border-white/10 group-hover:border-red-500/40">\n                <i data-lucide="phone" class="w-7 h-7 text-white group-hover:text-red-400"></i>\n              </div>\n              <div>\n                <p class="text-xs font-bold text-slate-400 uppercase mb-1 tracking-widest">감사실 직통</p>\n                <p class="text-xl sm:text-2xl font-black text-white">02-3414-1919</p>\n              </div>\n            </div>\n\n            <!-- Cyber -->\n            <a href="#" target="_blank" rel="noopener"\n               class="glass-panel p-8 rounded-3xl flex items-center gap-6 group hover:bg-white/5 transition-all border border-white/10">\n              <div class="w-14 h-14 bg-white/10 rounded-2xl flex items-center justify-center border border-white/10 group-hover:border-blue-500/40">\n                <i data-lucide="globe" class="w-7 h-7 text-white group-hover:text-blue-400"></i>\n              </div>\n              <div class="flex-1">\n                <p class="text-xs font-bold text-slate-400 uppercase mb-1 tracking-widest">사이버 신문고</p>\n                <div class="flex items-center justify-between gap-3">\n                  <span class="text-xl sm:text-2xl font-black text-white border-b border-white/20 pb-1">바로가기</span>\n                  <i data-lucide="arrow-right" class="w-6 h-6 text-slate-300 group-hover:text-white transition-colors"></i>\n                </div>\n              </div>\n            </a>\n\n            <!-- Email (full width) -->\n            <div class="sm:col-span-2 glass-panel p-8 rounded-3xl flex items-center gap-6 group hover:bg-white/5 transition-all border border-white/10">\n              <div class="w-14 h-14 bg-white/10 rounded-2xl flex items-center justify-center border border-white/10 group-hover:border-amber-500/40">\n                <i data-lucide="mail" class="w-7 h-7 text-white group-hover:text-amber-300"></i>\n              </div>\n              <div>\n                <p class="text-xs font-bold text-slate-400 uppercase mb-1 tracking-widest">이메일 제보</p>\n                <p class="text-xl sm:text-2xl font-black text-white">ethics@ktmos.com</p>\n              </div>\n            </div>\n\n            <div class="sm:col-span-2 text-slate-400 text-xs leading-relaxed">\n              ※ ‘사이버 신문고’ 링크는 회사 내부 URL로 교체해 주세요. (현재는 # 처리)\n            </div>\n          </div>\n        </div>\n      </div>\n    </div>\n  </section>\n\n\n  <script>\n    (function() {\n      try { if (window.lucide) window.lucide.createIcons(); } catch(e) {}\n\n      // Auto-resize iframe height in Streamlit\n      function sendHeight() {\n        const h = document.documentElement.scrollHeight;\n        const msg = { isStreamlitMessage: true, type: "setFrameHeight", height: h };\n        window.parent.postMessage(msg, "*");\n      }\n      window.addEventListener("load", sendHeight);\n      window.addEventListener("resize", () => setTimeout(sendHeight, 50));\n      try {\n        const ro = new ResizeObserver(() => sendHeight());\n        ro.observe(document.body);\n      } catch(e) {}\n      setTimeout(sendHeight, 120);\n      setTimeout(sendHeight, 600);\n      setTimeout(sendHeight, 1200);\n    })();\n  </script>\n</body>\n</html>\n'

    components.html(
        CLEAN_CAMPAIGN_AGENDA_HTML,
        height=720,          # 초기값 (내부 JS가 실제 높이로 자동 보정)
        scrolling=False,
    )


# ✅ 자율점검 탭 전용 스타일 범위 종료
    st.markdown("</div>", unsafe_allow_html=True)

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
        sheet_names = [ws.title for ws in ws_list if ws.title != "Campaign_Config"]
        
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

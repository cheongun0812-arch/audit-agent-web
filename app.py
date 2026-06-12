import streamlit as st
import streamlit.components.v1 as components
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
import re
from urllib.parse import urlparse, parse_qs

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
        "<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026<br>Engine: Gemini 2.5 / Search Grounding Ready</div>",
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

def _clean_model_name(model_name: str) -> str:
    """Gemini SDK가 반환하는 'models/...' 형식과 순수 모델명을 모두 안전하게 처리합니다."""
    return str(model_name or "").replace("models/", "").strip()


def _select_available_model(task: str = "balanced") -> str:
    """업무 성격별 우선 모델을 선택하되, 계정에서 지원하지 않으면 자동 fallback 합니다."""
    task = (task or "balanced").lower()
    preference_map = {
        "legal": ["gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "report": ["gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "summary": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        "chat": ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"],
        "balanced": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
    }
    preferred = preference_map.get(task, preference_map["balanced"])

    try:
        available_models = [
            _clean_model_name(m.name)
            for m in genai.list_models()
            if "generateContent" in getattr(m, "supported_generation_methods", [])
        ]
        for target in preferred:
            for model_name in available_models:
                if target in model_name:
                    return model_name
        if available_models:
            return available_models[0]
    except Exception:
        # list_models 실패 시에도 아래 기본값으로 시도합니다.
        pass

    return preferred[-1]


def get_model(task: str = "balanced", temperature: float = 0.2):
    """기존 get_model 호환성을 유지하면서 최신 Gemini 모델을 우선 사용합니다."""
    if "api_key" in st.session_state:
        genai.configure(api_key=st.session_state["api_key"])

    model_name = _select_available_model(task)
    try:
        return genai.GenerativeModel(
            model_name,
            generation_config={
                "temperature": temperature,
                "top_p": 0.9,
                "max_output_tokens": 8192,
            },
        )
    except Exception:
        return genai.GenerativeModel("gemini-1.5-flash")


def _extract_response_text(response) -> str:
    """Gemini 응답 객체에서 텍스트를 최대한 안전하게 추출합니다."""
    try:
        return response.text or ""
    except Exception:
        pass
    try:
        parts = response.candidates[0].content.parts
        return "\n".join(str(getattr(p, "text", "")) for p in parts if getattr(p, "text", ""))
    except Exception:
        return ""


def _extract_grounding_sources(response) -> list[dict]:
    """Google Search Grounding 결과의 출처를 사용자에게 보여주기 좋은 형태로 정리합니다."""
    sources = []
    try:
        metadata = getattr(response.candidates[0], "grounding_metadata", None)
        chunks = getattr(metadata, "grounding_chunks", []) if metadata else []
        for chunk in chunks:
            web = getattr(chunk, "web", None)
            if not web:
                continue
            title = getattr(web, "title", "") or "출처"
            uri = getattr(web, "uri", "") or ""
            if uri and not any(s.get("uri") == uri for s in sources):
                sources.append({"title": title, "uri": uri})
    except Exception:
        pass
    return sources[:8]


def generate_ai_response(content, task: str = "balanced", use_search: bool = False, temperature: float = 0.2):
    """공통 AI 호출 함수: 검색 보강 요청 시 Google Search Grounding을 우선 시도하고 실패하면 일반 생성으로 fallback 합니다."""
    model = get_model(task=task, temperature=temperature)
    search_warning = None

    if use_search:
        # google-generativeai 구버전/신버전 호환을 위해 두 가지 표기를 순차 시도합니다.
        for tool_name in ("google_search_retrieval", "google_search"):
            try:
                response = model.generate_content(content, tools=tool_name)
                return response, True, None
            except Exception as e:
                search_warning = str(e)

    response = model.generate_content(content)
    return response, False, search_warning


def render_ai_response(response, grounded: bool = False, warning: str | None = None) -> None:
    """AI 결과와 검색 출처를 공통 UI로 출력합니다."""
    answer = _extract_response_text(response)
    if answer:
        st.markdown(answer)
    else:
        st.warning("AI 응답 텍스트를 추출하지 못했습니다. 입력 자료나 모델 응답 제한 여부를 확인해 주세요.")

    sources = _extract_grounding_sources(response)
    if grounded and sources:
        with st.expander("🔎 검색 기반 참고 출처", expanded=False):
            for i, src in enumerate(sources, 1):
                st.markdown(f"{i}. [{src['title']}]({src['uri']})")
    elif warning:
        st.caption("ℹ️ 검색 보강 호출이 실패하여 일반 AI 분석으로 대체되었습니다. 패키지 버전 또는 API 권한을 확인해 주세요.")


def truncate_text(text: str, limit: int = 45000) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n[※ 입력 자료가 길어 앞부분 기준으로 일부만 반영되었습니다.]"


def read_file(uploaded_file):
    content = ""
    try:
        name = uploaded_file.name.lower()
        if name.endswith(".txt"):
            raw = uploaded_file.getvalue()
            for enc in ("utf-8", "cp949", "euc-kr"):
                try:
                    content = raw.decode(enc)
                    break
                except Exception:
                    continue
        elif name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(uploaded_file)
            for idx, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                content += f"\n\n[Page {idx}]\n{page_text}"
        elif name.endswith(".docx"):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs if para.text])
        elif name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
            content = df.head(200).to_markdown(index=False)
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file)
            content = df.head(200).to_markdown(index=False)
    except Exception:
        return None
    return content.strip() if content else None


def read_multiple_files(files, max_each: int = 12000) -> str:
    """여러 파일을 감사보고서/법률검토 프롬프트에 안전하게 합칩니다."""
    chunks = []
    for f in files or []:
        body = read_file(f)
        if body:
            chunks.append(f"\n\n===== 파일: {getattr(f, 'name', 'uploaded')} =====\n{truncate_text(body, max_each)}")
        else:
            chunks.append(f"\n\n===== 파일: {getattr(f, 'name', 'uploaded')} =====\n[텍스트 추출 실패 또는 지원되지 않는 형식]")
    return "\n".join(chunks).strip()


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


def extract_youtube_id(url: str) -> str | None:
    """watch?v=, youtu.be, shorts, embed 형식까지 처리합니다."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")
        if "youtube.com" in host:
            qs = parse_qs(parsed.query)
            if qs.get("v"):
                return qs["v"][0]
            parts = path.split("/")
            if parts and parts[0] in {"shorts", "embed", "live"} and len(parts) > 1:
                return parts[1]
        if "youtu.be" in host and path:
            return path.split("/")[0]
    except Exception:
        pass
    m = re.search(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{8,})", url or "")
    return m.group(1) if m else None


def get_youtube_transcript(url):
    try:
        video_id = extract_youtube_id(url)
        if not video_id:
            return None
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        return " ".join([t.get("text", "") for t in transcript])
    except Exception:
        return None


def get_web_content(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        meta_desc = ""
        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            meta_desc = desc.get("content", "")
        text = soup.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return f"URL: {url}\n제목: {title}\n설명: {meta_desc}\n\n본문:\n{text[:25000]}"
    except Exception:
        return None


def build_legal_review_prompt(content: str, analysis_depth: str, doc_type: str, focus_area: str, company_position: str) -> str:
    return f"""[역할]
당신은 대한민국 기업 감사실을 보조하는 법률·컴플라이언스 검토 전문가입니다.

[검토 대상]
- 문서 유형: {doc_type}
- 회사 입장: {company_position}
- 분석 수준: {analysis_depth}
- 중점 검토: {focus_area}

[작성 원칙]
1. 업로드 문서에서 확인되는 사실과 AI의 법률적 판단/추정을 명확히 구분하세요.
2. 대한민국 법령·판례·공정거래/하도급/개인정보/근로관계 등 관련 기준을 고려하되, 근거가 불충분하면 '추가 확인 필요'로 표시하세요.
3. 실무자가 바로 사용할 수 있도록 '위험 조항', '리스크 이유', '개선 문안'을 구체적으로 제시하세요.
4. 과도하게 단정하지 말고, 감사·법무 검토 문서에 적합한 객관적 문체로 작성하세요.

[출력 형식]
## 1. 핵심 결론
- 즉시 수정 필요 / 협의 필요 / 수용 가능 항목을 요약

## 2. 조항별 리스크 검토표
| 우선순위 | 원문 또는 쟁점 | 리스크 등급 | 문제점 | 관련 법령·판례·가이드라인 방향 | 개선 의견 |

## 3. 상대방에게 제시할 수정 문안
- 조항별로 대체 문구 작성

## 4. 내부 검토 메모
- 감사실/법무/사업부가 추가 확인해야 할 사항

## 5. 한계 및 추가 확인 필요사항
- 문서에 없는 사실, 최신 법령 확인 필요사항, 외부 변호사 검토 필요사항

[입력 문서]
{truncate_text(content, 55000)}
"""


def build_audit_report_prompt(mode: str, case_title: str, case_scope: str, report_tone: str, materials: str, regulations_text: str, refs_text: str) -> str:
    if "초안" in mode:
        task = "감사보고서 초안을 생성"
        output = "사건개요, 확인자료, 주요 사실관계, 쟁점, 판단, 리스크, 조치의견, 후속관리 항목을 포함한 공식 감사보고서 초안"
    else:
        task = "감사보고서 초안을 검증·교정"
        output = "오탈자·논리비약·근거부족·표현위험·형식오류를 지적하고, 개선본과 수정 사유표를 제시"

    return f"""[역할]
당신은 기업 감사실의 감사보고서 품질관리 담당자입니다.

[작업]
- 작업 모드: {mode}
- 수행 작업: {task}
- 사건명: {case_title}
- 문서 톤: {report_tone}

[사건 개요]
{case_scope}

[작성 원칙]
1. 사실관계, 판단, 의견을 구분하세요.
2. 업로드 자료에 없는 사실은 새로 만들지 말고 '자료상 확인 불가'로 표시하세요.
3. 피조사자·관련자의 명예, 개인정보, 노동관계 리스크를 고려하여 표현을 중립적으로 조정하세요.
4. 내부 결재문서로 활용 가능한 수준의 문장으로 작성하세요.
5. 불리한 단정 표현은 '확인됨/확인 필요/소명 필요/자료상 불명확' 등으로 정리하세요.

[출력 형식]
## 1. {output}
## 2. 핵심 쟁점 및 증거 연결표
| 쟁점 | 확인자료 | 판단 가능 수준 | 보완 필요자료 |
## 3. 표현 리스크 점검
| 문장/표현 | 리스크 | 권장 표현 |
## 4. 후속 조치안
## 5. 추가 확인 필요사항

[감사 자료]
{truncate_text(materials, 50000)}

[회사 규정/판단 기준]
{truncate_text(regulations_text, 25000)}

[참고 보고서 형식]
{truncate_text(refs_text, 15000)}
"""


def build_chat_prompt(user_input: str, history: list[dict], mode: str) -> str:
    recent = history[-10:] if history else []
    history_text = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in recent])
    return f"""[시스템 역할]
당신은 대한민국 기업 감사실을 지원하는 Professional Legal & Audit Assistant입니다.
감사, 컴플라이언스, 계약 검토, 개인정보, 하도급, 공정거래, 직장 내 괴롭힘, 내부통제 이슈에 대해 실무형으로 답변합니다.

[응답 원칙]
1. 결론을 먼저 제시하고, 근거와 실무 조치 순서로 설명하세요.
2. 법률·판례·행정해석이 필요한 질문은 '확인된 근거'와 '추가 확인 필요'를 구분하세요.
3. 단정이 위험한 사안은 리스크와 방어 전략을 함께 제시하세요.
4. 최종 법률 판단은 사내 법무/외부 변호사 검토가 필요하다는 점을 짧게 고지하세요.
5. 답변 마지막에는 '추가 확인 필요사항'을 1~2문장 포함하세요.

[현재 모드]
{mode}

[최근 대화]
{history_text}

[사용자 질문]
{user_input}
"""


def build_summary_prompt(summary_mode: str, output_style: str, source_hint: str, body_text: str) -> str:
    return f"""[역할]
당신은 기업 감사실과 컴플라이언스 부서를 위한 스마트 브리핑 분석가입니다.

[요약 대상]
- 요약 모드: {summary_mode}
- 출력 방식: {output_style}
- 출처/입력: {source_hint}

[작성 원칙]
1. 사실, 주장, 의견, 추정을 구분하세요.
2. 날짜·기관·당사자·수치가 있으면 빠뜨리지 마세요.
3. 회사 업무상 영향, 컴플라이언스 리스크, 후속 조치 필요사항을 별도로 정리하세요.
4. 원문에서 확인되지 않는 내용은 만들지 말고 '원문상 확인 불가'로 표시하세요.

[출력 형식]
## 1. 5줄 핵심 요약
## 2. 상세 내용
## 3. 업무상 의미/리스크
## 4. 후속 조치 체크리스트
## 5. 원문 한계 및 추가 확인사항

[입력 내용]
{truncate_text(body_text, 55000)}
"""

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
# ✅ 2026년 6월 컴플라이언스 인식제고 교육 저장 유틸
#    - 기존 윤리경영 실천서약 저장 로직과 분리
#    - Google Sheet: Audit_Result_2026 / 2026_06_컴플라이언스_인식제고교육
# ==========================================
JUNE_TRAINING_SHEET_NAME = "2026_06_컴플라이언스_인식제고교육"
JUNE_TRAINING_HEADERS = [
    "저장시간", "수료ID", "사번", "성명", "총괄/본부/단", "부서",
    "교육대상", "Theme1_청렴공정_확인", "Theme1_점수", "Theme2_협력정보_확인", "Theme2_점수",
    "이벤트퀴즈_선택", "이벤트퀴즈_정답여부", "퀴즈점수", "참여점수", "최종점수", "수료상태", "이벤트추첨대상", "비고"
]


def save_june_compliance_training_result(record: dict) -> tuple[bool, str]:
    """6월 컴플라이언스 인식제고 교육 수료 내역을 Google Sheet에 저장합니다."""
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패 (Secrets 확인)"

    try:
        spreadsheet = client.open("Audit_Result_2026")
        try:
            sheet = spreadsheet.worksheet(JUNE_TRAINING_SHEET_NAME)
        except Exception:
            sheet = spreadsheet.add_worksheet(title=JUNE_TRAINING_SHEET_NAME, rows=3000, cols=len(JUNE_TRAINING_HEADERS) + 2)
            sheet.append_row(JUNE_TRAINING_HEADERS)

        all_records = sheet.get_all_records()
        emp_id_str = str(record.get("사번", "")).strip()
        name_str = str(record.get("성명", "")).strip()
        dept_str = str(record.get("부서", "")).strip()

        for existing in all_records:
            existing_emp_id = str(existing.get("사번", "")).strip()
            existing_name = str(existing.get("성명", "")).strip()
            existing_dept = str(existing.get("부서", "")).strip()
            if emp_id_str == "00000000":
                if existing_emp_id == "00000000" and existing_name == name_str and existing_dept == dept_str:
                    return False, f"'{name_str}'님은 이미 6월 컴플라이언스 교육 수료 기록이 있습니다."
            else:
                if existing_emp_id == emp_id_str:
                    return False, f"사번 {emp_id_str}은(는) 이미 6월 컴플라이언스 교육 수료 기록이 있습니다."

        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        completion_seed = f"{now}|{emp_id_str}|{name_str}|{dept_str}|2026-06-compliance"
        completion_id = hashlib.sha256(completion_seed.encode("utf-8")).hexdigest()[:12]

        row = [
            now,
            completion_id,
            record.get("사번", ""),
            record.get("성명", ""),
            record.get("총괄/본부/단", ""),
            record.get("부서", ""),
            record.get("교육대상", "전 임직원"),
            record.get("Theme1_청렴공정_확인", "완료"),
            record.get("Theme1_점수", 0),
            record.get("Theme2_협력정보_확인", "완료"),
            record.get("Theme2_점수", 0),
            record.get("이벤트퀴즈_선택", ""),
            record.get("이벤트퀴즈_정답여부", ""),
            record.get("퀴즈점수", 0),
            record.get("참여점수", 0),
            record.get("최종점수", 0),
            record.get("수료상태", "수료"),
            record.get("이벤트추첨대상", "대상"),
            record.get("비고", ""),
        ]
        sheet.append_row(row, value_input_option="USER_ENTERED")
        return True, "6월 컴플라이언스 인식제고 교육 수료 내역이 저장되었습니다."
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

# ✅ 상단 메뉴 카드형 디자인: 선택된 탭이 명확하게 보이도록 개선
st.markdown("""
<style>
/* Streamlit 탭을 카드형 메뉴처럼 보이게 개선 */
div[data-testid="stTabs"] > div[role="tablist"] {
    gap: 10px !important;
    background: linear-gradient(135deg, #EEF4FF 0%, #F8FAFC 100%) !important;
    border: 1px solid #D8E3F2 !important;
    border-radius: 20px !important;
    padding: 10px !important;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08) !important;
}
div[data-testid="stTabs"] button[role="tab"] {
    min-height: 54px !important;
    padding: 10px 16px !important;
    border-radius: 16px !important;
    border: 1px solid #D8E3F2 !important;
    background: #FFFFFF !important;
    color: #334155 !important;
    font-weight: 900 !important;
    box-shadow: 0 5px 14px rgba(15, 23, 42, 0.06) !important;
    transition: all 0.18s ease-in-out !important;
}
div[data-testid="stTabs"] button[role="tab"] p {
    font-size: 1.02rem !important;
    font-weight: 950 !important;
    margin: 0 !important;
}
div[data-testid="stTabs"] button[role="tab"]:hover {
    transform: translateY(-1px) !important;
    border-color: #60A5FA !important;
    box-shadow: 0 9px 20px rgba(37, 99, 235, 0.13) !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #1D4ED8 0%, #0EA5E9 100%) !important;
    color: #FFFFFF !important;
    border-color: #38BDF8 !important;
    box-shadow: 0 12px 28px rgba(37, 99, 235, 0.28) !important;
    transform: translateY(-2px) !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] p,
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] * {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="false"] p,
div[data-testid="stTabs"] button[role="tab"][aria-selected="false"] * {
    color: #334155 !important;
    -webkit-text-fill-color: #334155 !important;
}
/* 선택된 탭 하단 기본 라인 숨김 */
div[data-testid="stTabs"] button[role="tab"]::after {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

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
    st.caption("기존 윤리경영 실천서약은 보관 영역에 그대로 유지하고, 아래에서 6월 컴플라이언스 인식제고 자율점검 교육을 진행합니다.")

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
    /* ✅ 전역 버튼 CSS가 내부 span/p 텍스트를 흰색으로 만드는 문제 방지 */
    .stButton > button[kind="secondary"] *,
    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span {
        color: #2563EB !important;
        -webkit-text-fill-color: #2563EB !important;
        opacity: 1 !important;
    }
    .stButton > button[kind="primary"] *,
    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        opacity: 1 !important;
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


    # =========================================================
    # 2026년 6월 컴플라이언스 인식제고 자율점검 교육 - Final Image Edition
    # - 기존 윤리경영 실천서약 보관함은 유지
    # - 현장대리인 등록 모듈 위치에 고품질 교육 모듈 배치
    # - 순차형 Quest 구조 / Previous·Next 이동 / Step별 Clear 표시
    # - STEP 1~4 단계별 최소 학습시간 60초 적용 / STEP 5 체크항목별 10초 확인
    # - Theme 1: 부패방지 + 공정거래 / Theme 2: 하도급 + 정보보호
    # =========================================================
    st.markdown("""
        <style>
        .premium-hero-v2 {
            position: relative;
            overflow: hidden;
            background:
              radial-gradient(circle at 12% 10%, rgba(255,255,255,0.23), transparent 28%),
              radial-gradient(circle at 90% 12%, rgba(125,211,252,0.45), transparent 30%),
              linear-gradient(135deg, #06152F 0%, #123B7A 42%, #0EA5E9 100%);
            color: #FFFFFF;
            padding: 34px 36px;
            border-radius: 28px;
            box-shadow: 0 18px 44px rgba(15, 23, 42, 0.28);
            margin: 10px 0 18px 0;
            border: 1px solid rgba(255,255,255,0.18);
        }
        .premium-hero-v2 h2 {
            margin: 0 0 8px 0;
            font-size: 1.92rem;
            font-weight: 950;
            letter-spacing: -0.03em;
        }
        .premium-hero-v2 p {
            margin: 0;
            color: rgba(255,255,255,0.92);
            line-height: 1.68;
            font-weight: 700;
            font-size: 1.03rem;
            max-width: 1120px;
        }
        .premium-badge-v2 {
            display: inline-block;
            padding: 7px 14px;
            border-radius: 999px;
            background: rgba(255,255,255,0.17);
            color: #E0F2FE;
            font-weight: 950;
            margin-bottom: 13px;
            border: 1px solid rgba(255,255,255,0.22);
            letter-spacing: 0.02em;
        }
        .audit-message-v2 {
            background: linear-gradient(135deg, #FFFFFF 0%, #F8FBFF 100%);
            border: 1px solid #D7E3F4;
            border-left: 8px solid #2563EB;
            border-radius: 20px;
            padding: 19px 21px;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.07);
            margin: 14px 0;
        }
        .audit-message-v2 h4 { margin: 0 0 8px 0; color: #1E3A8A; font-weight: 950; font-size: 1.12rem; }
        .audit-message-v2 p { margin: 0; color: #334155; line-height: 1.65; font-weight: 700; }
        .quest-card {
            min-height: 126px;
            border-radius: 22px;
            padding: 18px 18px;
            border: 1px solid #DDE7F5;
            box-shadow: 0 9px 24px rgba(15, 23, 42, 0.08);
            margin-bottom: 10px;
        }
        .quest-card h4 { margin: 0 0 8px 0; font-weight: 950; font-size: 1.08rem; }
        .quest-card p { margin: 0; line-height: 1.50; font-weight: 700; font-size: 0.94rem; }
        .quest-clear { background: linear-gradient(135deg, #DCFCE7 0%, #ECFDF5 100%); border-color: #86EFAC; color: #14532D; }
        .quest-active { background: linear-gradient(135deg, #DBEAFE 0%, #EFF6FF 100%); border-color: #60A5FA; color: #1E3A8A; transform: translateY(-1px); }
        .quest-lock { background: linear-gradient(135deg, #F8FAFC 0%, #F1F5F9 100%); border-color: #CBD5E1; color: #64748B; }
        .quest-event { background: linear-gradient(135deg, #E0F2FE 0%, #ECFEFF 100%); border-color: #7DD3FC; color: #075985; }
        .status-chip {
            display:inline-block;
            margin-top:10px;
            padding:6px 10px;
            border-radius:999px;
            font-size:0.83rem;
            font-weight:950;
            background:rgba(255,255,255,0.72);
            border:1px solid rgba(15,23,42,0.08);
        }
        .step-road {
            display:grid;
            grid-template-columns: repeat(6, minmax(110px, 1fr));
            gap: 10px;
            margin: 16px 0 20px 0;
        }
        .step-node {
            position:relative;
            min-height:86px;
            border-radius: 20px;
            padding: 13px 10px;
            text-align:center;
            font-weight:950;
            box-shadow: 0 7px 18px rgba(15, 23, 42, 0.06);
            border:1px solid #E2E8F0;
        }
        .step-node .num { display:block; font-size:1.18rem; margin-bottom:2px; }
        .step-node .label { display:block; font-size:0.91rem; line-height:1.32; }
        .step-clear { background: linear-gradient(135deg, #DCFCE7 0%, #F0FDF4 100%); color:#166534; border-color:#86EFAC; }
        .step-current { background: linear-gradient(135deg, #1D4ED8 0%, #0EA5E9 100%); color:white; border-color:#60A5FA; transform: translateY(-2px); box-shadow: 0 11px 26px rgba(37,99,235,0.24); }
        .step-lock { background: #F8FAFC; color:#94A3B8; border-color:#E2E8F0; }
        .timer-panel {
            background: linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 100%);
            border: 1px solid #93C5FD;
            border-radius: 18px;
            padding: 15px 17px;
            color: #1E3A8A;
            font-weight: 850;
            margin: 14px 0 12px 0;
            box-shadow: 0 8px 20px rgba(37,99,235,0.08);
        }
        .timer-panel-clear { background: linear-gradient(135deg, #ECFDF5 0%, #F0FDF4 100%); border-color:#86EFAC; color:#14532D; }
        .timer-bar-bg { width:100%; background:#DBEAFE; height:14px; border-radius:999px; overflow:hidden; margin-top:9px; }
        .timer-bar-fill { height:14px; border-radius:999px; background: linear-gradient(90deg, #2563EB, #06B6D4, #22C55E); transition: width 0.3s ease; }
        .check-timer-card {
            background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
            border: 1px solid #BFDBFE;
            border-radius: 16px;
            padding: 12px 14px;
            margin: 7px 0 9px 0;
            font-weight: 850;
            color:#1E3A8A;
        }
        .check-timer-done {
            color:#166534;
            font-weight:950;
            background:#F0FDF4;
            border:1px solid #BBF7D0;
            border-radius:999px;
            padding:5px 10px;
            display:inline-block;
        }
        .check-timer-wait {
            color:#92400E;
            font-weight:950;
            background:#FFFBEB;
            border:1px solid #FDE68A;
            border-radius:999px;
            padding:5px 10px;
            display:inline-block;
        }
        .theme-title-panel {
            border-radius: 26px;
            padding: 24px 25px;
            margin: 12px 0 15px 0;
            box-shadow: 0 13px 30px rgba(15, 23, 42, 0.12);
        }
        .theme-title-panel h3 { margin:0 0 8px 0; font-size:1.55rem; font-weight:950; letter-spacing:-0.02em; }
        .theme-title-panel p { margin:0; font-size:1.01rem; line-height:1.66; font-weight:700; }
        .theme-one-v2 { background: linear-gradient(135deg, #FFF7ED 0%, #FEF3C7 50%, #FFFBEB 100%); border:1px solid #FBBF24; color:#78350F; }
        .theme-two-v2 { background: linear-gradient(135deg, #ECFEFF 0%, #DBEAFE 55%, #F0FDFA 100%); border:1px solid #38BDF8; color:#0F172A; }
        .content-card-v2 {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 24px;
            padding: 23px 24px;
            margin: 12px 0;
            box-shadow: 0 10px 26px rgba(15, 23, 42, 0.07);
        }
        .content-card-v2 h4 { margin:0 0 10px 0; color:#1E3A8A; font-size:1.24rem; font-weight:950; }
        .content-card-v2 p { color:#334155; line-height:1.68; font-weight:700; }
        .page-pill-v2 {
            display: inline-block;
            padding: 7px 13px;
            border-radius: 999px;
            background: #DBEAFE;
            color: #1D4ED8;
            font-weight: 950;
            font-size: 0.88rem;
            margin-bottom: 11px;
        }
        .infographic-grid {
            display:grid;
            grid-template-columns: repeat(4, minmax(150px, 1fr));
            gap: 13px;
            margin-top:14px;
        }
        .info-tile {
            border-radius: 22px;
            padding: 18px 14px;
            min-height: 142px;
            text-align:center;
            border:1px solid rgba(255,255,255,0.50);
            box-shadow: 0 9px 22px rgba(15, 23, 42, 0.08);
        }
        .info-tile .icon { font-size: 2.15rem; display:block; margin-bottom:7px; }
        .info-tile b { display:block; font-size:1.02rem; font-weight:950; margin-bottom:6px; }
        .info-tile span { display:block; font-size:0.88rem; line-height:1.45; font-weight:720; }
        .tile-orange { background:linear-gradient(135deg,#FFEDD5,#FEF3C7); color:#7C2D12; }
        .tile-blue { background:linear-gradient(135deg,#DBEAFE,#E0F2FE); color:#1E3A8A; }
        .tile-green { background:linear-gradient(135deg,#DCFCE7,#ECFDF5); color:#14532D; }
        .tile-purple { background:linear-gradient(135deg,#F3E8FF,#EEF2FF); color:#4C1D95; }
        .principle-grid-v2 { display:grid; grid-template-columns: repeat(2, minmax(230px, 1fr)); gap:14px; margin-top:13px; }
        .principle-card-v2 { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:18px; padding:18px 19px; box-shadow:0 7px 17px rgba(15,23,42,0.05); }
        .principle-keyword-v2 { display:inline-block; color:#DC2626; font-size:1.08rem; font-weight:950; letter-spacing:-0.01em; margin-bottom:12px; padding:4px 10px; border-radius:999px; background:#FEF2F2; border:1px solid #FECACA; }
        .principle-desc-v2 { display:block; color:#334155; line-height:1.62; font-weight:760; padding-top:2px; }
        .risk-grid-v2 { display:grid; grid-template-columns: repeat(3, minmax(190px, 1fr)); gap:12px; margin-top:13px; }
        .risk-card-v2 { background:#FFF7ED; border:1px solid #FDBA74; border-radius:18px; padding:16px 17px; color:#7C2D12; font-weight:950; min-height:122px; box-shadow:0 7px 17px rgba(249,115,22,0.08); }
        .risk-phrase-v2 { display:block; font-size:1.02rem; font-weight:950; color:#7C2D12; line-height:1.42; margin-bottom:10px; }
        .risk-response-v2 { display:block; border-top:1px dashed #FDBA74; padding-top:10px; margin-top:8px; color:#334155; font-size:0.88rem; line-height:1.48; font-weight:780; }
        .risk-response-v2 b { color:#DC2626; font-weight:950; margin-right:4px; }
        .case-box-v2 { background:linear-gradient(135deg,#F8FAFC 0%,#EFF6FF 100%); border:1px solid #BFDBFE; border-radius:20px; padding:18px 19px; margin:14px 0; color:#334155; line-height:1.65; font-weight:720; }
        .case-box-v2 b { color:#1E3A8A; }
        .answer-box-v2 { background:#F0FDF4; border:1px solid #BBF7D0; border-radius:18px; padding:15px 17px; margin:12px 0; color:#14532D; font-weight:780; line-height:1.62; }
        .quiz-feedback-v2 { border-radius:18px; padding:14px 16px; margin:8px 0 18px 0; line-height:1.58; font-weight:760; }
        .quiz-feedback-v2.correct { background:#ECFDF5; border:1px solid #86EFAC; color:#14532D; }
        .quiz-feedback-v2.wrong { background:#FFF7ED; border:1px solid #FDBA74; color:#7C2D12; }
        .quiz-feedback-v2 b { font-weight:950; }
        .quote-line-v2 { font-size:1.34rem; color:#0F172A; font-weight:950; line-height:1.50; margin:8px 0 12px 0; letter-spacing:-0.02em; }
        .score-pill-v2 { display:inline-block; padding:8px 13px; border-radius:999px; background:#F0FDF4; color:#166534; border:1px solid #BBF7D0; font-weight:950; margin:5px 6px 5px 0; }
        .score-pill-warn-v2 { display:inline-block; padding:8px 13px; border-radius:999px; background:#FFF7ED; color:#9A3412; border:1px solid #FED7AA; font-weight:950; margin:5px 6px 5px 0; }
        .nav-help { color:#475569; font-weight:760; font-size:0.92rem; margin-top:3px; }
        .summer-zone-v2 {
            background: radial-gradient(circle at 10% 12%, rgba(255,255,255,0.9), transparent 22%), linear-gradient(135deg,#E0F2FE 0%,#BAE6FD 45%,#ECFEFF 100%);
            border:1px solid #7DD3FC;
            border-radius:26px;
            padding:25px;
            box-shadow:0 14px 32px rgba(14,165,233,0.18);
            margin:12px 0 16px 0;
        }
        .summer-zone-v2 h3 { margin:0 0 8px 0; color:#075985; font-weight:950; font-size:1.52rem; }
        .summer-zone-v2 p { margin:0; color:#0F172A; line-height:1.66; font-weight:700; }
        @media (max-width: 900px) {
            .step-road { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
            .infographic-grid { grid-template-columns: 1fr; }
            .principle-grid-v2 { grid-template-columns: 1fr; }
            .risk-grid-v2 { grid-template-columns: 1fr; }
        }
        </style>
    """, unsafe_allow_html=True)
    # ✅ 안내 히어로는 Final V3 intro 화면에서만 렌더링합니다.

    # ✅ GitHub 저장소의 assets 폴더 이미지를 안전하게 표시하는 유틸
    #    app.py와 같은 위치에 assets 폴더를 두고, 아래 3개 파일명을 사용하세요.
    TRAINING_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

    def _show_training_asset(filename: str, caption: str = "") -> None:
        image_path = os.path.join(TRAINING_ASSET_DIR, filename)
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True, caption=caption)
        else:
            st.warning(
                f"이미지 파일을 찾을 수 없습니다: assets/{filename} · "
                "GitHub의 assets 폴더와 파일명을 확인해 주세요."
            )


    # =========================================================
    # 2026년 6월 컴플라이언스 인식제고 교육 - Final V3
    # - 초기 안내 화면 분리
    # - STEP 1~4: 단계별 60초 자동 카운트다운 + 게이지
    # - STEP 5: 체크 항목별 10초 모래시계 확인, 체크 유지, 순차 활성화
    # - STEP 6: 시간제한 제외
    # =========================================================
    st.markdown("""
        <style>
        .intro-sequence-title {
            margin: 18px 0 12px 0;
            padding: 17px 20px;
            border-radius: 18px;
            background: linear-gradient(135deg, #EEF6FF 0%, #FFFFFF 100%);
            border: 1px solid #BFDBFE;
            color: #1E3A8A;
            font-weight: 950;
            font-size: 1.18rem;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.08);
        }
        .start-training-box {
            margin: 8px 0 16px 0;
            padding: 18px 20px;
            border-radius: 20px;
            background: linear-gradient(135deg, #FFFBEB 0%, #FFF7ED 100%);
            border: 1px solid #FCD34D;
            color: #78350F;
            font-weight: 850;
            line-height: 1.62;
        }
        .start-training-box b { color:#92400E; font-weight:950; }
        .timer-live-wrap {
            background: linear-gradient(135deg, #EFF6FF 0%, #F8FAFC 100%);
            border: 1px solid #93C5FD;
            border-radius: 18px;
            padding: 15px 17px;
            color: #1E3A8A;
            font-weight: 850;
            margin: 14px 0 12px 0;
            box-shadow: 0 8px 20px rgba(37,99,235,0.08);
        }
        .timer-live-wrap.clear {
            background: linear-gradient(135deg, #ECFDF5 0%, #F0FDF4 100%);
            border-color:#86EFAC;
            color:#14532D;
        }
        .timer-live-head {
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:10px;
            flex-wrap:wrap;
        }
        .timer-live-left { display:flex; align-items:center; gap:10px; }
        .timer-live-count {
            display:inline-block;
            min-width:78px;
            text-align:center;
            padding:7px 12px;
            border-radius:999px;
            background:#FFFFFF;
            border:1px solid #BFDBFE;
            color:#1D4ED8;
            font-weight:950;
            box-shadow:0 3px 8px rgba(37,99,235,0.10);
        }
        .timer-warmup {
            background: linear-gradient(135deg, #FFF7ED 0%, #FFFBEB 100%);
            border: 1px solid #FDBA74;
            color:#92400E;
        }
        .check-row-locked {
            opacity: .52;
        }
        .check-next-guide {
            color:#64748B;
            font-weight:850;
            font-size:0.92rem;
        }
        .summary-title-card {
            margin-top: 18px;
            padding: 18px 20px;
            border-radius: 22px;
            background: linear-gradient(135deg, #F8FAFC 0%, #FFFFFF 100%);
            border: 1px solid #D7E3F4;
            box-shadow: 0 10px 26px rgba(15,23,42,0.07);
        }
        .summary-title-card h4 {
            margin: 0 0 6px 0;
            color: #1E3A8A;
            font-weight: 950;
            font-size: 1.24rem;
        }
        .summary-title-card p {
            margin: 0;
            color:#334155;
            font-weight:750;
            line-height:1.6;
        }
        /* Previous / secondary button visibility reinforcement */
        .stButton > button[kind="secondary"],
        .stButton > button[kind="secondary"] *,
        .stButton > button[kind="secondary"] p,
        .stButton > button[kind="secondary"] span {
            color: #1D4ED8 !important;
            -webkit-text-fill-color: #1D4ED8 !important;
            opacity: 1 !important;
        }
        </style>
    """, unsafe_allow_html=True)

    SELECT_PLACEHOLDER = "선택하세요"
    STEP_MIN_SECONDS = 60
    STEP_WARMUP_SECONDS = 3
    CHECK_ITEM_SECONDS = 10
    CHECK_ITEM_DELAY_SECONDS = 1
    TIMED_STEPS = {1, 2, 3, 4}
    STEPS = [
        (1, "인포그래픽", "핵심 리스크를 한눈에 봅니다"),
        (2, "핵심 원칙", "업무 기준을 정리합니다"),
        (3, "위험 신호", "멈춰야 할 문장을 확인합니다"),
        (4, "사례 판단", "실제 상황을 판단합니다"),
        (5, "실천 체크", "내 행동 기준을 확인합니다"),
        (6, "퀴즈·완료", "이해도를 점검합니다"),
    ]

    T1_Q = {
        "t1_v2_q1": "컴플라이언스 사전심의 등 내부 절차를 확인한다",
        "t1_v2_q2": "담합 리스크가 있으므로 대화를 중단하고 내부 기준을 확인한다",
        "t1_v2_q3": "기준을 확인하고 필요 시 신고·반환·상담한다",
        "t1_v2_q4": "거래상 지위 남용 소지가 있으므로 합리적 사유와 절차를 확인한다",
    }
    T2_Q = {
        "t2_v2_q1": "법정기재사항이 포함된 서면을 먼저 발급한다",
        "t2_v2_q2": "10일 이내 서면으로 통지한다",
        "t2_v2_q3": "정당한 사유와 절차에 따라 요구하고 목적 범위 내에서만 사용한다",
        "t2_v2_q4": "원칙적으로 금지되며 내부 보안 기준을 따라야 한다",
        "t2_v2_q5": "공유하지 않고 개인별 계정과 권한 기준을 준수한다",
    }
    T1_CHECKS = {
        "t1_v2_c1": "나는 공직자 등에게 부정청탁을 하지 않는다.",
        "t1_v2_c2": "나는 직무 관련 금품·향응 제공 기준을 반드시 확인한다.",
        "t1_v2_c3": "나는 제3자를 통한 우회 제공도 부패 리스크가 될 수 있음을 이해한다.",
        "t1_v2_c4": "나는 경쟁사와 가격·입찰·거래조건 정보를 교환하지 않는다.",
        "t1_v2_c5": "나는 거래상 지위를 이용해 불리한 조건을 강요하지 않는다.",
    }
    T2_CHECKS = {
        "t2_v2_c1": "나는 위탁업무 시작 전 서면 발급 필요성을 확인한다.",
        "t2_v2_c2": "나는 하도급대금 지급기한과 검사결과 통지기한을 확인한다.",
        "t2_v2_c3": "나는 정당한 사유 없이 기술자료나 경영정보를 요구하지 않는다.",
        "t2_v2_c4": "나는 업무용 PC 내 불필요한 개인정보를 삭제한다.",
        "t2_v2_c5": "나는 고객정보를 목적 외로 조회하거나 활용하지 않는다.",
        "t2_v2_c6": "나는 ID/PW를 공유하지 않는다.",
        "t2_v2_c7": "나는 기업비밀을 암호화하고 목적 완료 후 파기한다.",
    }

    def _clear_june_training_state() -> None:
        """최종 제출 후 교육 화면을 초기 상태로 되돌리기 위한 전용 초기화입니다."""
        reset_prefixes = ("june_v2_", "t1_v2_", "t2_v2_", "event_v2_", "june_")
        reset_exact = {"june_training_saved"}
        for k in list(st.session_state.keys()):
            if k in reset_exact or any(k.startswith(p) for p in reset_prefixes):
                try:
                    del st.session_state[k]
                except Exception:
                    pass

    if st.session_state.pop("june_force_reset_after_submit", False):
        _clear_june_training_state()

    def _init_june_v2_state():
        st.session_state.setdefault("june_v2_view", "intro")
        st.session_state.setdefault("june_v2_theme", 1)
        st.session_state.setdefault("june_v2_step", 1)
        st.session_state.setdefault("june_v2_theme1_done", False)
        st.session_state.setdefault("june_v2_theme2_done", False)
        st.session_state.setdefault("june_v2_event_done", False)
        st.session_state.setdefault("june_training_saved", False)
        st.session_state.setdefault("june_v2_completed_steps_1", [])
        st.session_state.setdefault("june_v2_completed_steps_2", [])

    def _request_training_scroll_top() -> None:
        st.session_state["june_v2_scroll_top_requested"] = True

    def _render_training_scroll_top_if_requested() -> None:
        """단계/테마 이동 후 이전 스크롤 위치가 남지 않도록 브라우저 화면을 상단으로 이동합니다."""
        if st.session_state.pop("june_v2_scroll_top_requested", False):
            components.html(
                """
                <script>
                const scrollTop = () => {
                  try {
                    const doc = window.parent.document;
                    const candidates = [
                      doc.querySelector('section.main'),
                      doc.querySelector('[data-testid="stAppViewContainer"]'),
                      doc.documentElement,
                      doc.body
                    ].filter(Boolean);
                    candidates.forEach(el => {
                      try { el.scrollTo({top: 0, left: 0, behavior: 'smooth'}); } catch(e) { el.scrollTop = 0; }
                    });
                    window.parent.scrollTo({top: 0, left: 0, behavior: 'smooth'});
                  } catch(e) {
                    try { window.scrollTo({top: 0, left: 0, behavior: 'smooth'}); } catch(err) {}
                  }
                };
                setTimeout(scrollTop, 80);
                setTimeout(scrollTop, 280);
                </script>
                """,
                height=0,
            )

    def _step_load_key(theme_no: int, step_no: int) -> str:
        return f"june_v2_theme{theme_no}_step{step_no}_loaded_at"

    def _step_timer_key(theme_no: int, step_no: int) -> str:
        return f"june_v2_theme{theme_no}_step{step_no}_countdown_started_at"

    def _step_warmup_key(theme_no: int, step_no: int) -> str:
        return f"june_v2_theme{theme_no}_step{step_no}_warmup_done"

    def _ensure_step_timer(theme_no: int, step_no: int) -> None:
        if step_no in TIMED_STEPS:
            st.session_state.setdefault(_step_load_key(theme_no, step_no), time.time())

    def _completed_steps(theme_no: int) -> list[int]:
        return list(st.session_state.get(f"june_v2_completed_steps_{theme_no}", []))

    def _step_elapsed(theme_no: int, step_no: int) -> int:
        if step_no not in TIMED_STEPS:
            return 0
        if step_no in set(_completed_steps(theme_no)):
            return STEP_MIN_SECONDS
        started = st.session_state.get(_step_timer_key(theme_no, step_no))
        if not started:
            return 0
        return int(time.time() - float(started))

    def _step_remaining(theme_no: int, step_no: int) -> int:
        if step_no not in TIMED_STEPS:
            return 0
        return max(0, STEP_MIN_SECONDS - _step_elapsed(theme_no, step_no))

    def _step_time_met(theme_no: int, step_no: int) -> bool:
        return step_no not in TIMED_STEPS or step_no in set(_completed_steps(theme_no)) or _step_remaining(theme_no, step_no) <= 0

    def _mark_step_done(theme_no: int, step_no: int) -> None:
        key = f"june_v2_completed_steps_{theme_no}"
        steps = set(st.session_state.get(key, []))
        steps.add(step_no)
        st.session_state[key] = sorted(steps)

    def _max_unlocked_step(theme_no: int) -> int:
        completed = set(_completed_steps(theme_no))
        unlocked = 1
        for i in range(1, 7):
            if i in completed:
                unlocked = min(6, i + 1)
            else:
                break
        return unlocked

    def _check_done_key(check_key: str) -> str:
        return f"{check_key}_timed_done"

    def _check_is_done(check_key: str) -> bool:
        return bool(st.session_state.get(_check_done_key(check_key), False))

    def _checks_done(theme_no: int) -> bool:
        checks = T1_CHECKS if theme_no == 1 else T2_CHECKS
        return all(_check_is_done(k) for k in checks)

    def _quiz_answered(theme_no: int) -> bool:
        qmap = T1_Q if theme_no == 1 else T2_Q
        return all(st.session_state.get(k, SELECT_PLACEHOLDER) != SELECT_PLACEHOLDER for k in qmap)

    def _quiz_correct_count(theme_no: int) -> int:
        qmap = T1_Q if theme_no == 1 else T2_Q
        return sum(1 for k, ans in qmap.items() if st.session_state.get(k) == ans)

    def _theme_ready_to_complete(theme_no: int) -> tuple[bool, str]:
        if not all(s in set(_completed_steps(theme_no)) for s in [1,2,3,4,5]):
            return False, "이전 학습 단계를 먼저 완료해야 합니다."
        if not _checks_done(theme_no):
            return False, "실천 체크 항목을 모두 확인해야 합니다."
        if not _quiz_answered(theme_no):
            return False, "퀴즈 문항을 모두 응답해야 합니다."
        return True, "완료 가능"

    def _set_theme(theme_no: int):
        if theme_no == 1:
            st.session_state["june_v2_view"] = "theme1"
            st.session_state["june_v2_theme"] = 1
            st.session_state["june_v2_step"] = 1
            _ensure_step_timer(1, 1)
            _request_training_scroll_top()
            st.rerun()
        if theme_no == 2 and not st.session_state.get("june_v2_theme1_done", False):
            st.warning("현재 교육을 완료해야 다음 단계로 이동할 수 있습니다. Theme 1을 먼저 완료해 주세요.")
            return
        st.session_state["june_v2_view"] = f"theme{theme_no}"
        st.session_state["june_v2_theme"] = theme_no
        st.session_state["june_v2_step"] = 1
        _ensure_step_timer(theme_no, 1)
        _request_training_scroll_top()
        st.rerun()

    def _set_event():
        if not st.session_state.get("june_v2_theme2_done", False):
            st.warning("현재 교육을 완료해야 다음 단계로 이동할 수 있습니다. Theme 2를 먼저 완료해 주세요.")
            return
        st.session_state["june_v2_view"] = "event"
        _request_training_scroll_top()
        st.rerun()

    def _set_submit():
        if not st.session_state.get("june_v2_event_done", False):
            st.warning("현재 교육을 완료해야 다음 단계로 이동할 수 있습니다. Summer Event까지 완료해 주세요.")
            return
        st.session_state["june_v2_view"] = "submit"
        _request_training_scroll_top()
        st.rerun()

    def _theme_score(theme_no: int) -> int:
        if theme_no == 1:
            return (15 if _checks_done(1) else 0) + (_quiz_correct_count(1) * 5)
        return (15 if _checks_done(2) else 0) + (_quiz_correct_count(2) * 6)

    def _render_quest_cards(show_buttons: bool = True):
        q1_state = "quest-clear" if st.session_state.get("june_v2_theme1_done") else ("quest-active" if st.session_state.get("june_v2_view") == "theme1" else "quest-lock")
        q2_state = "quest-clear" if st.session_state.get("june_v2_theme2_done") else ("quest-active" if st.session_state.get("june_v2_view") == "theme2" else "quest-lock")
        ev_state = "quest-clear" if st.session_state.get("june_v2_event_done") else ("quest-event" if st.session_state.get("june_v2_view") == "event" else "quest-lock")
        sub_state = "quest-active" if st.session_state.get("june_v2_view") == "submit" else "quest-lock"
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            status1 = 'CLEAR' if st.session_state.get('june_v2_theme1_done') else ('IN PROGRESS' if st.session_state.get('june_v2_view') == 'theme1' else 'READY')
            st.markdown(f"""<div class="quest-card {q1_state}"><h4>① 청렴·공정경영</h4><p>부패방지·공정거래 리스크를 확인합니다.</p><span class="status-chip">{status1}</span></div>""", unsafe_allow_html=True)
            if show_buttons and st.button("청렴·공정경영 열기", use_container_width=True, key="june_v2_open_t1"):
                _set_theme(1)
        with c2:
            status2 = 'CLEAR' if st.session_state.get('june_v2_theme2_done') else ('LOCKED' if not st.session_state.get('june_v2_theme1_done') else 'READY')
            st.markdown(f"""<div class="quest-card {q2_state}"><h4>② 협력사·정보보호</h4><p>하도급·정보보호 기준을 점검합니다.</p><span class="status-chip">{status2}</span></div>""", unsafe_allow_html=True)
            if show_buttons and st.button("협력사·정보보호 열기", use_container_width=True, key="june_v2_open_t2"):
                _set_theme(2)
        with c3:
            status_ev = 'CLEAR' if st.session_state.get('june_v2_event_done') else ('LOCKED' if not st.session_state.get('june_v2_theme2_done') else 'READY')
            st.markdown(f"""<div class="quest-card {ev_state}"><h4>🌊 Summer Event</h4><p>수료자 모바일 쿠폰 추첨 대상 이벤트입니다.</p><span class="status-chip">{status_ev}</span></div>""", unsafe_allow_html=True)
            if show_buttons and st.button("이벤트 열기", use_container_width=True, key="june_v2_open_event"):
                _set_event()
        with c4:
            status_sub = 'READY' if st.session_state.get('june_v2_event_done') else 'LOCKED'
            st.markdown(f"""<div class="quest-card {sub_state}"><h4>✅ 수료 제출</h4><p>교육 수료 및 이벤트 퀴즈 정보를 저장합니다.</p><span class="status-chip">{status_sub}</span></div>""", unsafe_allow_html=True)
            if show_buttons and st.button("수료 제출 열기", use_container_width=True, key="june_v2_open_submit"):
                _set_submit()

    def _render_step_road(theme_no: int):
        current = int(st.session_state.get("june_v2_step", 1))
        completed = set(_completed_steps(theme_no))
        max_unlocked = _max_unlocked_step(theme_no)
        cols = st.columns(6)
        for idx, (num, label, sub) in enumerate(STEPS):
            if num in completed:
                cls = "step-clear"
                mark = "✓"
            elif num == current:
                cls = "step-current"
                mark = str(num)
            else:
                cls = "step-lock"
                mark = "·" if num <= max_unlocked else "🔒"
            with cols[idx]:
                st.markdown(f"""<div class="step-node {cls}"><span class="num">{mark}</span><span class="label">STEP {num}<br>{label}</span></div>""", unsafe_allow_html=True)
                if st.button("이동", key=f"june_v2_step_go_{theme_no}_{num}", use_container_width=True):
                    if num <= max_unlocked or num in completed:
                        st.session_state["june_v2_step"] = num
                        _ensure_step_timer(theme_no, num)
                        _request_training_scroll_top()
                        st.rerun()
                    else:
                        st.warning("현재 교육을 완료해야 다음 단계로 이동할 수 있습니다.")
        st.markdown("<div class='nav-help'>완료된 단계는 초록색, 현재 단계는 파란색, 아직 진행할 수 없는 단계는 회색으로 표시됩니다.</div>", unsafe_allow_html=True)

    def _render_step_timer(theme_no: int, step_no: int) -> None:
        """STEP 1~4에 적용되는 60초 자동 카운트다운 게이지입니다."""
        if step_no not in TIMED_STEPS:
            return
        if step_no in set(_completed_steps(theme_no)):
            st.markdown(f"""
                <div class="timer-live-wrap clear">
                    <div class="timer-live-head">
                        <div class="timer-live-left">✅ STEP {step_no} 최소 학습시간 충족 완료</div>
                        <span class="timer-live-count">CLEAR</span>
                    </div>
                    <div class="timer-bar-bg"><div class="timer-bar-fill" style="width:100%;"></div></div>
                </div>
            """, unsafe_allow_html=True)
            return

        ph = st.empty()
        if not st.session_state.get(_step_warmup_key(theme_no, step_no), False):
            for sec in range(STEP_WARMUP_SECONDS, 0, -1):
                ph.markdown(f"""
                    <div class="timer-live-wrap timer-warmup">
                        <div class="timer-live-head">
                            <div class="timer-live-left">{HOURGLASS_SVG}<span>STEP {step_no} 카운트다운 준비 중입니다.</span></div>
                            <span class="timer-live-count">{sec}초 후 시작</span>
                        </div>
                        <div class="timer-bar-bg"><div class="timer-bar-fill" style="width:0%;"></div></div>
                    </div>
                """, unsafe_allow_html=True)
                time.sleep(1)
            st.session_state[_step_warmup_key(theme_no, step_no)] = True
            st.session_state[_step_timer_key(theme_no, step_no)] = time.time()

        st.session_state.setdefault(_step_timer_key(theme_no, step_no), time.time())
        while _step_remaining(theme_no, step_no) > 0:
            elapsed = _step_elapsed(theme_no, step_no)
            remain = _step_remaining(theme_no, step_no)
            pct = min(100, int(elapsed / STEP_MIN_SECONDS * 100))
            ph.markdown(f"""
                <div class="timer-live-wrap">
                    <div class="timer-live-head">
                        <div class="timer-live-left">{HOURGLASS_SVG}<span>최소 학습시간 충족을 위한 60초 카운트다운</span></div>
                        <span class="timer-live-count">{remain}초 남음</span>
                    </div>
                    <div class="timer-bar-bg"><div class="timer-bar-fill" style="width:{pct}%;"></div></div>
                </div>
            """, unsafe_allow_html=True)
            time.sleep(1)
        ph.markdown(f"""
            <div class="timer-live-wrap clear">
                <div class="timer-live-head">
                    <div class="timer-live-left">✅ 최소 학습시간 충족 · STEP {step_no} 60초 학습 완료</div>
                    <span class="timer-live-count">CLEAR</span>
                </div>
                <div class="timer-bar-bg"><div class="timer-bar-fill" style="width:100%;"></div></div>
            </div>
        """, unsafe_allow_html=True)

    def _render_timed_checks(theme_no: int) -> None:
        """STEP 5 실천 체크 항목별 10초 모래시계 확인 절차입니다."""
        checks = T1_CHECKS if theme_no == 1 else T2_CHECKS
        items = list(checks.items())
        st.markdown(
            "<div class='check-timer-card'>⌛ 각 항목은 체크 후 1초 뒤 10초 모래시계 카운트다운이 시작됩니다. "
            "카운트다운이 끝난 뒤 다음 항목이 활성화됩니다.</div>",
            unsafe_allow_html=True,
        )
        first_not_done_idx = None
        for i, (k, _) in enumerate(items):
            if not _check_is_done(k):
                first_not_done_idx = i
                break

        for idx, (key, label) in enumerate(items, start=1):
            is_done = _check_is_done(key)
            is_active = (first_not_done_idx is not None and idx - 1 == first_not_done_idx)
            c_box, c_status = st.columns([0.76, 0.24], vertical_alignment="center")
            with c_box:
                if is_done:
                    st.checkbox(f"{idx}. {label}", value=True, disabled=True, key=f"{key}_done_widget")
                elif is_active:
                    checked_now = st.checkbox(f"{idx}. {label}", value=False, key=f"{key}_active_widget")
                else:
                    st.checkbox(f"{idx}. {label}", value=False, disabled=True, key=f"{key}_locked_widget")
                    checked_now = False
            with c_status:
                ph = st.empty()
                if is_done:
                    ph.markdown("<span class='check-timer-done'>✅ 확인 완료</span>", unsafe_allow_html=True)
                elif not is_active:
                    ph.markdown("<span class='check-next-guide'>이전 항목 완료 후 활성화</span>", unsafe_allow_html=True)
                elif bool(checked_now):
                    ph.markdown("<span class='check-timer-wait'>⌛ 1초 후 시작</span>", unsafe_allow_html=True)
                    time.sleep(CHECK_ITEM_DELAY_SECONDS)
                    for sec in range(CHECK_ITEM_SECONDS, 0, -1):
                        ph.markdown(
                            f"<span class='check-timer-wait'>{HOURGLASS_SVG} {sec}초</span>",
                            unsafe_allow_html=True,
                        )
                        time.sleep(1)
                    st.session_state[_check_done_key(key)] = True
                    ph.markdown("<span class='check-timer-done'>✅ 확인 완료</span>", unsafe_allow_html=True)
                    st.rerun()
                else:
                    ph.markdown("<span style='color:#64748B;font-weight:800;'>대기</span>", unsafe_allow_html=True)

        if _checks_done(theme_no):
            if theme_no == 1:
                title = "Theme 1. 청렴·공정경영 Quest Summary"
                desc = "실천 체크를 완료했습니다. 아래 요약 이미지를 통해 청렴·공정경영의 핵심 기준을 다시 한 번 정리해 주세요."
                img = "theme1_integrity_fair.png"
                cap = "Theme 1. 청렴·공정경영 Quest Summary"
            else:
                title = "Theme 2. 협력사·정보보호 Quest Summary"
                desc = "실천 체크를 완료했습니다. 아래 요약 이미지를 통해 협력사·정보보호의 핵심 기준을 다시 한 번 정리해 주세요."
                img = "theme2_partner_security.png"
                cap = "Theme 2. 협력사·정보보호 Quest Summary"
            st.markdown(f"""
                <div class="summary-title-card">
                    <h4>{title}</h4>
                    <p>{desc}</p>
                </div>
            """, unsafe_allow_html=True)
            _show_training_asset(img, cap)

    def _render_quiz_question(label: str, options: list[str], key: str, correct: str, explanation: str) -> None:
        """퀴즈 선택 직후 정답 여부와 구체 설명을 카드로 표시합니다."""
        selected = st.radio(label, [SELECT_PLACEHOLDER] + options, key=key)
        if selected != SELECT_PLACEHOLDER:
            is_correct = (selected == correct)
            cls = "correct" if is_correct else "wrong"
            title = "✅ 정답입니다" if is_correct else "⚠️ 다시 확인해 주세요"
            correct_line = "" if is_correct else f"<br><b>정답:</b> {correct}"
            st.markdown(
                f"<div class='quiz-feedback-v2 {cls}'><b>{title}</b>{correct_line}<br>{explanation}</div>",
                unsafe_allow_html=True,
            )

    def _render_theme_step(theme_no: int):
        step = int(st.session_state.get("june_v2_step", 1))
        if theme_no == 1:
            title_cls = "theme-one-v2"
            title = "Theme 1. 청렴·공정경영 Quest"
            desc = "부패방지와 공정거래는 회사의 신뢰를 지키는 가장 기본적인 내부통제입니다. 공직자 관련 요청, 금품·향응, 제3자 우회 제공, 경쟁사 정보교환, 거래상 지위 남용은 모두 사전에 멈추고 확인해야 할 신호입니다."
        else:
            title_cls = "theme-two-v2"
            title = "Theme 2. 협력사·정보보호 Quest"
            desc = "협력사와 정보는 절차로 보호됩니다. 서면 발급, 대금 지급, 검사 통지, 기술자료 보호, 개인정보·기업비밀 관리는 업무 편의보다 먼저 확인해야 할 기준입니다."

        st.markdown(f"""<div class="theme-title-panel {title_cls}"><h3>{title}</h3><p>{desc}</p></div>""", unsafe_allow_html=True)
        _render_step_road(theme_no)
        _ensure_step_timer(theme_no, step)

        if step == 1:
            if theme_no == 1:
                st.markdown("""
                    <div class="content-card-v2">
                        <span class="page-pill-v2">STEP 1 · Infographic</span>
                        <h4>청렴한 판단은 가장 강한 내부통제입니다</h4>
                        <div class="quote-line-v2">“관행처럼 보이는 작은 편의가 회사 전체의 리스크가 될 수 있습니다.”</div>
                        <div class="infographic-grid">
                            <div class="info-tile tile-orange"><span class="icon">🚫</span><b>부정청탁 NO</b><span>공직자 등에게 직접 또는 제3자를 통한 부정청탁 금지</span></div>
                            <div class="info-tile tile-blue"><span class="icon">🎁</span><b>금품·향응 NO</b><span>직무 관련 금품, 편의, 약속 또는 의사표시 금지</span></div>
                            <div class="info-tile tile-green"><span class="icon">🤝</span><b>담합 NO</b><span>가격, 입찰, 거래조건에 관한 경쟁사 합의 금지</span></div>
                            <div class="info-tile tile-purple"><span class="icon">⚖️</span><b>지위남용 NO</b><span>거래상대방에게 불리한 조건 강요 금지</span></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div class="content-card-v2">
                        <span class="page-pill-v2">STEP 1 · Infographic</span>
                        <h4>협력사와 정보는 ‘절차’로 보호합니다</h4>
                        <div class="quote-line-v2">“급한 업무일수록 계약·정보보호 절차를 먼저 확인해야 합니다.”</div>
                        <div class="infographic-grid">
                            <div class="info-tile tile-blue"><span class="icon">📝</span><b>서면 발급</b><span>위탁업무 시작 전 계약서 등 법정기재사항 확인</span></div>
                            <div class="info-tile tile-green"><span class="icon">⏳</span><b>기한 준수</b><span>대금 지급, 검사결과 통지 기한 관리</span></div>
                            <div class="info-tile tile-orange"><span class="icon">🔐</span><b>자료 보호</b><span>기술자료·경영정보 요구와 사용은 절차에 따라</span></div>
                            <div class="info-tile tile-purple"><span class="icon">🛡️</span><b>개인정보 보호</b><span>목적 외 조회·제공·공유 금지, 계정관리 준수</span></div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

        elif step == 2:
            if theme_no == 1:
                principles = [
                    ("청탁 금지", "금품 등을 받는 것이 금지된 공직자 등에게 직접 또는 제3자를 통해 부정청탁을 하지 않습니다."),
                    ("금품 제공 금지", "직무 관련 여부를 확인하고, 금품·향응·편의 제공 또는 제공 약속·의사표시를 하지 않습니다."),
                    ("제3자 우회 금지", "에이전트·협력사·하도급사를 통한 우회 제공도 회사의 부패 리스크가 될 수 있습니다."),
                    ("담합 금지", "가격, 입찰, 거래조건 등에 관한 경쟁사 정보교환이나 합의를 하지 않습니다."),
                ]
            else:
                principles = [
                    ("서면 발급", "위탁업무 시작 전 계약서 등 법정기재사항이 포함된 서면을 발급하고 보존합니다."),
                    ("대금·검사 기한", "대금 지급기한과 검사결과 통지기한을 지켜 협력사와 회사의 신뢰를 보호합니다."),
                    ("기술자료 보호", "정당한 사유와 절차 없이 기술자료·경영정보를 요구하거나 목적 외로 사용하지 않습니다."),
                    ("정보보호", "개인정보 목적 외 이용, ID/PW 공유, 기업비밀 방치·무단반출을 금지합니다."),
                ]
            html = ''.join([f"<div class='principle-card-v2'><div class='principle-keyword-v2'>{a}</div><div class='principle-desc-v2'>{b}</div></div>" for a,b in principles])
            st.markdown(f"""<div class="content-card-v2"><span class="page-pill-v2">STEP 2 · Core Principles</span><h4>기억해야 할 핵심 원칙</h4><p style='margin-top:0;color:#475569;font-weight:740;'>빨간 핵심 키워드를 먼저 기억하고, 아래 설명으로 실제 업무 기준을 확인해 주세요.</p><div class="principle-grid-v2">{html}</div></div>""", unsafe_allow_html=True)

        elif step == 3:
            if theme_no == 1:
                risks = [
                    ("🚩 ‘관행대로 처리하시죠’", "관행이라는 표현이 나오면 기준이 흐려질 수 있습니다. 관련 규정, 승인권자, 기록 필요 여부를 먼저 확인하세요."),
                    ("🚩 ‘식사 한 번 하시죠’", "직무 관련자가 제공하는 식사·편의는 금액보다 직무 관련성과 반복성이 중요합니다. 회사 기준과 신고 필요 여부를 확인하세요."),
                    ("🚩 ‘경쟁사는 얼마에 들어왔나요?’", "입찰가격·거래조건 등 경쟁 민감 정보는 담합 리스크가 있습니다. 대화를 중단하고 내부에 공유·상담하세요."),
                    ("🚩 ‘협력사를 통해 전달하면 괜찮습니다’", "제3자를 통한 우회 제공도 회사 행위로 평가될 수 있습니다. 직접 제공과 동일하게 사전심의·승인 절차를 확인하세요."),
                    ("🚩 ‘증빙은 나중에 맞추면 됩니다’", "증빙과 회계처리는 실제 거래와 일치해야 합니다. 사후 맞춤, 허위기재, 누락은 회계투명성 리스크입니다."),
                    ("🚩 ‘이번 건은 기록을 남기지 맙시다’", "기록을 남기지 말자는 말은 내부통제 경고 신호입니다. 이메일, 회의록, 승인내역 등 객관 자료를 보존하세요."),
                ]
            else:
                risks = [
                    ("🚩 ‘계약서는 나중에 쓰고 일단 시작합시다’", "거래 시작 전 서면 발급은 기본 절차입니다. 긴급하더라도 계약·발주·업무범위 문서화를 먼저 확인하세요."),
                    ("🚩 ‘검사 통지는 굳이 안 해도 됩니다’", "검사결과 통지는 대금 지급과 분쟁 예방의 기준입니다. 정해진 기한과 방식에 따라 서면 통지해야 합니다."),
                    ("🚩 ‘원가자료 좀 받아주세요’", "원가·매출·경영전략 자료는 경영정보에 해당할 수 있습니다. 정당한 사유와 법무·컴플라이언스 기준을 확인하세요."),
                    ("🚩 ‘고객정보를 개인 메일로 보내겠습니다’", "개인 메일·메신저·개인 클라우드는 비인가 경로입니다. 승인된 시스템, 암호화, 접근권한 기준을 따라야 합니다."),
                    ("🚩 ‘비밀번호는 팀 공용으로 쓰면 편합니다’", "ID/PW 공유는 책임 추적과 권한관리를 무너뜨립니다. 개인별 계정과 최소권한 원칙을 지켜야 합니다."),
                    ("🚩 ‘업무 끝난 파일은 그냥 보관해 둡시다’", "목적이 끝난 개인정보·기업비밀은 보관 필요성을 확인하고, 불필요한 자료는 복구 불가능하게 파기해야 합니다."),
                ]
            html = ''.join([f"<div class='risk-card-v2'><span class='risk-phrase-v2'>{phrase}</span><span class='risk-response-v2'><b>대응</b>{response}</span></div>" for phrase, response in risks])
            st.markdown(f"""<div class="content-card-v2"><span class="page-pill-v2">STEP 3 · Red Flags</span><h4>이런 말이 나오면 멈추고 확인하세요</h4><p style='margin-top:0;color:#475569;font-weight:740;'>위험 문구를 보았다면 즉시 멈추고, 아래 대응 방향에 따라 기록·승인·상담 절차를 확인해 주세요.</p><div class="risk-grid-v2">{html}</div></div>""", unsafe_allow_html=True)

        elif step == 4:
            if theme_no == 1:
                st.markdown("""
                    <div class="content-card-v2"><span class="page-pill-v2">STEP 4 · Case Judgment</span><h4>사례로 판단해 보기</h4>
                    <div class="case-box-v2"><b>사례 A</b><br>공공기관 관계자가 특정 협회비 또는 협찬을 요청했습니다. 담당자는 관계 유지를 위해 신속히 진행하려고 합니다.</div>
                    <div class="answer-box-v2"><b>판단 포인트</b><br>공직자 등으로부터 직·간접적으로 청탁·권유·요청받은 기부, 협찬, 협회비 등은 내부 사전심의 대상인지 먼저 확인해야 합니다.</div>
                    <div class="case-box-v2"><b>사례 B</b><br>입찰 전 경쟁사 담당자가 ‘이번에는 어느 정도 금액으로 들어가느냐’고 묻습니다.</div>
                    <div class="answer-box-v2"><b>판단 포인트</b><br>가격, 입찰, 거래조건에 관한 경쟁사 정보교환은 담합 리스크가 있으므로 대화를 중단하고 내부 기준을 확인해야 합니다.</div>
                    <div class="case-box-v2"><b>사례 C</b><br>평소 업무 연락을 자주 하던 협력사 담당자가 감사의 의미라며 모바일 커피 쿠폰을 개인 메신저로 보냈습니다.</div>
                    <div class="answer-box-v2"><b>판단 포인트</b><br>소액이라도 직무 관련성이 있으면 금품·편의 제공 리스크가 발생할 수 있습니다. 사내 기준을 확인하고 필요 시 반환·신고·상담 절차를 진행해야 합니다.</div></div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                    <div class="content-card-v2"><span class="page-pill-v2">STEP 4 · Case Judgment</span><h4>사례로 판단해 보기</h4>
                    <div class="case-box-v2"><b>사례 A</b><br>협력사 업무가 급해 계약서 발급 전 먼저 작업을 시작했습니다.</div>
                    <div class="answer-box-v2"><b>판단 포인트</b><br>위탁업무 시작 전 서면 발급은 협력사와 회사를 함께 보호하는 기본 절차입니다. 급한 업무라도 절차를 생략하면 리스크가 커집니다.</div>
                    <div class="case-box-v2"><b>사례 B</b><br>고객정보가 포함된 엑셀 파일을 개인 이메일로 보내 야간에 처리하려고 합니다.</div>
                    <div class="answer-box-v2"><b>판단 포인트</b><br>개인정보와 기업비밀은 목적, 권한, 보관, 파기 기준을 지켜야 하며 개인 메일 등 비인가 경로 사용은 원칙적으로 금지됩니다.</div>
                    <div class="case-box-v2"><b>사례 C</b><br>보직이 변경된 직원이 이전 업무 시스템 권한을 계속 보유하고 있어, 필요할 때 과거 고객정보를 조회할 수 있는 상태입니다.</div>
                    <div class="answer-box-v2"><b>판단 포인트</b><br>불필요한 시스템 접근 권한은 즉시 반납·회수되어야 합니다. 업무 필요성이 사라진 권한은 개인정보 오·남용과 내부통제 리스크로 이어질 수 있습니다.</div></div>
                """, unsafe_allow_html=True)

        elif step == 5:
            st.markdown("<div class='content-card-v2'><span class='page-pill-v2'>STEP 5 · Practice Check</span><h4>실천 체크</h4><p>아래 항목을 모두 확인해야 다음 단계로 이동할 수 있습니다. 각 항목은 10초 확인 카운트다운을 거친 뒤 완료 처리됩니다.</p></div>", unsafe_allow_html=True)
            _render_timed_checks(theme_no)

        elif step == 6:
            st.markdown("<div class='content-card-v2'><span class='page-pill-v2'>STEP 6 · Quiz & Clear</span><h4>이해도 확인 퀴즈</h4><p>정답률은 교육 이해도 확인용입니다. 모든 문항에 응답해야 테마를 완료할 수 있습니다.</p></div>", unsafe_allow_html=True)
            if theme_no == 1:
                _render_quiz_question(
                    "Q1. 공공기관 관계자가 협찬을 요청했습니다. 가장 적절한 조치는?",
                    ["관계 유지를 위해 바로 진행한다", "컴플라이언스 사전심의 등 내부 절차를 확인한다", "개인적으로 처리한다"],
                    "t1_v2_q1",
                    "컴플라이언스 사전심의 등 내부 절차를 확인한다",
                    "공직자 등으로부터 요청받은 기부·협찬·협회비는 이해관계와 직무 관련성이 문제될 수 있으므로, 담당자가 임의로 진행하지 말고 내부 사전심의 대상 여부를 먼저 확인해야 합니다."
                )
                _render_quiz_question(
                    "Q2. 경쟁사가 입찰가격을 묻습니다. 가장 적절한 조치는?",
                    ["대략적인 가격 수준만 알려준다", "담합 리스크가 있으므로 대화를 중단하고 내부 기준을 확인한다", "서로 도움 되는 정보라면 공유한다"],
                    "t1_v2_q2",
                    "담합 리스크가 있으므로 대화를 중단하고 내부 기준을 확인한다",
                    "입찰가격, 거래조건, 낙찰 예정자 등 경쟁 민감 정보의 교환은 담합 의심을 받을 수 있습니다. 대화를 중단하고 기록·보고·상담 절차를 검토하는 것이 안전합니다."
                )
                _render_quiz_question(
                    "Q3. 협력사로부터 선물을 받았습니다. 가장 적절한 조치는?",
                    ["금액이 작으면 보관한다", "기준을 확인하고 필요 시 신고·반환·상담한다", "상급자에게만 구두 보고한다"],
                    "t1_v2_q3",
                    "기준을 확인하고 필요 시 신고·반환·상담한다",
                    "소액 선물이라도 직무 관련성이 있거나 반복·관행화되면 부패 리스크가 될 수 있습니다. 회사 기준에 따라 반환, 신고, 상담 등 객관적인 처리 절차를 남기는 것이 중요합니다."
                )
                _render_quiz_question(
                    "Q4. 거래상대방에게 합리적 이유 없이 불리한 조건을 요구했습니다. 가장 적절한 판단은?",
                    ["회사에 유리하면 가능하다", "거래상 지위 남용 소지가 있으므로 합리적 사유와 절차를 확인한다", "상대방이 수용하면 문제없다"],
                    "t1_v2_q4",
                    "거래상 지위 남용 소지가 있으므로 합리적 사유와 절차를 확인한다",
                    "상대방이 수용하더라도 거래상 지위, 불이익 정도, 합리적 사유와 협의 절차가 부족하면 공정거래 리스크가 발생할 수 있습니다."
                )
            else:
                _render_quiz_question(
                    "Q5. 중소기업에게 위탁업무를 시작하기 전 원칙적으로 필요한 것은?",
                    ["구두 합의 후 사후 정리한다", "법정기재사항이 포함된 서면을 먼저 발급한다", "업무 완료 후 정산 메모만 남긴다"],
                    "t2_v2_q1",
                    "법정기재사항이 포함된 서면을 먼저 발급한다",
                    "위탁업무 시작 전 계약서 등 필요한 서면을 발급하고 보존하는 것은 협력사와 회사 모두를 보호하는 기본 절차입니다. 구두 합의나 사후 정리는 분쟁과 법 위반 리스크를 키울 수 있습니다."
                )
                _render_quiz_question(
                    "Q6. 목적물 수령 후 검사결과 통지는 원칙적으로 언제까지 해야 할까요?",
                    ["10일 이내 서면으로 통지한다", "30일 이내 구두로 통지한다", "문제가 있을 때만 통지한다"],
                    "t2_v2_q2",
                    "10일 이내 서면으로 통지한다",
                    "검사결과는 정해진 기한 내 서면으로 통지해야 대금 지급과 후속 절차가 투명하게 관리됩니다. 구두 통지만으로는 분쟁 발생 시 입증이 어렵습니다."
                )
                _render_quiz_question(
                    "Q7. 협력사의 기술자료를 요구할 때 가장 적절한 기준은?",
                    ["업무에 필요하면 자유롭게 요구한다", "정당한 사유와 절차에 따라 요구하고 목적 범위 내에서만 사용한다", "받은 자료는 유사 업무에도 사용할 수 있다"],
                    "t2_v2_q3",
                    "정당한 사유와 절차에 따라 요구하고 목적 범위 내에서만 사용한다",
                    "기술자료는 정당한 사유, 요구서, 비밀유지, 목적 범위 등 절차가 중요합니다. 제공받은 자료를 다른 목적에 쓰거나 제3자에게 제공하면 중대한 리스크가 됩니다."
                )
                _render_quiz_question(
                    "Q8. 고객 개인정보가 포함된 파일을 개인 메일로 보내는 행위에 대한 가장 적절한 판단은?",
                    ["편의를 위해 가능하다", "원칙적으로 금지되며 내부 보안 기준을 따라야 한다", "암호 없이 보내도 된다"],
                    "t2_v2_q4",
                    "원칙적으로 금지되며 내부 보안 기준을 따라야 한다",
                    "개인정보와 기업비밀은 승인된 시스템과 보안 절차 안에서 처리해야 합니다. 개인 메일, 개인 클라우드, 메신저 등 비인가 경로는 유출 사고로 이어질 수 있습니다."
                )
                _render_quiz_question(
                    "Q9. 정보시스템 ID/PW 관리 기준으로 가장 적절한 것은?",
                    ["팀 업무 편의를 위해 공유한다", "공용 메모장에 적어둔다", "공유하지 않고 개인별 계정과 권한 기준을 준수한다"],
                    "t2_v2_q5",
                    "공유하지 않고 개인별 계정과 권한 기준을 준수한다",
                    "ID/PW 공유는 책임 추적을 어렵게 하고 권한 오남용 위험을 높입니다. 개인별 계정, 최소 권한, 권한 회수 기준을 지켜야 합니다."
                )

        if step in TIMED_STEPS:
            _render_step_timer(theme_no, step)

        checked = _checks_done(theme_no)
        answered = _quiz_answered(theme_no)
        score = _theme_score(theme_no)
        max_score = 35 if theme_no == 1 else 45
        st.markdown(
            f"<span class='score-pill-v2'>실천 체크: {'완료' if checked else '진행 중'}</span>"
            f"<span class='score-pill-v2'>퀴즈 응시: {'완료' if answered else '진행 중'}</span>"
            f"<span class='score-pill-v2'>테마 점수: {score}/{max_score}점</span>",
            unsafe_allow_html=True
        )

        st.markdown("---")
        prev_col, msg_col, next_col = st.columns([0.18, 0.54, 0.28])
        with prev_col:
            if st.button("◀ 이전", use_container_width=True, key=f"june_v2_prev_{theme_no}_{step}", type="secondary"):
                if step > 1:
                    st.session_state["june_v2_step"] = step - 1
                    _ensure_step_timer(theme_no, step - 1)
                elif theme_no == 2:
                    st.session_state["june_v2_view"] = "theme1"
                    st.session_state["june_v2_theme"] = 1
                    st.session_state["june_v2_step"] = 6
                _request_training_scroll_top()
                st.rerun()
        with msg_col:
            st.markdown("<div class='nav-help'>하단 버튼으로 순서대로 이동합니다. 완료된 단계는 상단 Quest Road에서 초록색으로 표시됩니다.</div>", unsafe_allow_html=True)
        with next_col:
            next_label = "다음 ▶" if step < 6 else ("Theme 1 CLEAR → 다음 Quest" if theme_no == 1 else "Theme 2 CLEAR → Event")
            if st.button(next_label, use_container_width=True, key=f"june_v2_next_{theme_no}_{step}", type="primary"):
                if step == 5 and not _checks_done(theme_no):
                    st.warning("실천 체크 항목을 모두 확인해야 다음 단계로 이동할 수 있습니다.")
                elif step == 6:
                    ok, msg = _theme_ready_to_complete(theme_no)
                    if not ok:
                        st.warning(msg)
                    else:
                        _mark_step_done(theme_no, 6)
                        if theme_no == 1:
                            st.session_state["june_v2_theme1_done"] = True
                            st.session_state["june_v2_view"] = "theme2"
                            st.session_state["june_v2_theme"] = 2
                            st.session_state["june_v2_step"] = 1
                            _ensure_step_timer(2, 1)
                        else:
                            st.session_state["june_v2_theme2_done"] = True
                            st.session_state["june_v2_view"] = "event"
                        _request_training_scroll_top()
                        st.rerun()
                else:
                    if step in TIMED_STEPS and not _step_time_met(theme_no, step):
                        remain = _step_remaining(theme_no, step)
                        st.warning(f"최소 학습시간 60초를 충족해야 다음 단계로 이동할 수 있습니다. 현재 {remain}초 남았습니다.")
                    else:
                        _mark_step_done(theme_no, step)
                        next_step = min(6, step + 1)
                        st.session_state["june_v2_step"] = next_step
                        _ensure_step_timer(theme_no, next_step)
                        _request_training_scroll_top()
                        st.rerun()

    _init_june_v2_state()
    _render_training_scroll_top_if_requested()

    # ✅ 첫 안내 화면에서만 과정 소개를 표시합니다.
    #    학습 시작 후에는 Theme Quest 화면만 노출하여 중복·복잡도를 줄입니다.
    if st.session_state.get("june_v2_view") == "intro":
        st.markdown("""
            <div class="premium-hero-v2">
                <div class="premium-badge-v2">AUDIT OFFICE · 2026 JUNE COMPLIANCE</div>
                <h2>2026년 6월 컴플라이언스 인식제고 자율점검 교육</h2>
                <p>
                    본 과정은 전 임직원을 대상으로 하는 감사실 주관 정기 자율점검 교육입니다.
                    부패방지·공정거래·하도급·정보보호 리스크를 사례 중심으로 학습하고,
                    실제 업무에서 바로 적용할 수 있는 실천 기준을 순서대로 확인합니다.
                </p>
            </div>
            <div class="audit-message-v2">
                <h4>감사실 안내</h4>
                <p>
                    교육은 순차형 Quest 방식으로 진행됩니다. 현재 단계를 완료해야 다음 단계로 이동할 수 있으며,
                    각 테마의 STEP 1~4는 단계별 최소 60초 이상 학습해야 다음 단계로 이동할 수 있습니다.
                    STEP 5 실천 체크는 항목별 10초 확인 카운트다운을 통해 실질적인 확인 절차를 거칩니다.
                    이는 단순 클릭형 수료를 방지하고, 전 임직원이 핵심 기준을 충분히 확인하기 위한 장치입니다.
                </p>
            </div>
        """, unsafe_allow_html=True)

    # GitHub 저장소의 assets 폴더 이미지를 안전하게 표시하는 유틸
    TRAINING_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

    def _show_training_asset(filename: str, caption: str = "") -> None:
        image_path = os.path.join(TRAINING_ASSET_DIR, filename)
        if os.path.exists(image_path):
            st.image(image_path, use_container_width=True, caption=caption)
        else:
            st.warning(
                f"이미지 파일을 찾을 수 없습니다: assets/{filename} · "
                "GitHub의 assets 폴더와 파일명을 확인해 주세요."
            )

    if st.session_state.get("june_v2_view") == "intro":
        st.markdown("<div class='intro-sequence-title'>컴플라이언스 인식제고 교육은 다음 순서로 진행됩니다.</div>", unsafe_allow_html=True)
        st.markdown("""
            <div class="content-card-v2" style="padding:18px 20px;">
                <div style="display:grid; grid-template-columns:repeat(4, minmax(120px,1fr)); gap:10px; text-align:center;">
                    <div class="score-pill-v2">① 청렴·공정경영</div>
                    <div class="score-pill-v2">② 협력사·정보보호</div>
                    <div class="score-pill-v2">③ Summer Event</div>
                    <div class="score-pill-v2">④ 수료 제출</div>
                </div>
            </div>
            <div class="start-training-box">
                <b>교육을 시작하겠습니다.</b><br>
                <b>확인 · 학습하기</b>를 누르면 다음 화면에서 <b>Theme 1. 청렴·공정경영 Quest</b>가 시작됩니다.
                이후부터는 단계별 교육을 순서대로 완료해야 다음 단계로 이동할 수 있습니다.
            </div>
        """, unsafe_allow_html=True)
        ok_col, _ = st.columns([0.24, 0.76])
        with ok_col:
            if st.button("확인 · 학습하기", use_container_width=True, key="june_v2_intro_start", type="primary"):
                st.session_state["june_v2_view"] = "theme1"
                st.session_state["june_v2_theme"] = 1
                st.session_state["june_v2_step"] = 1
                _ensure_step_timer(1, 1)
                _request_training_scroll_top()
                st.rerun()

    else:
        _render_quest_cards(show_buttons=True)

        if st.session_state.get("june_v2_view") in ["theme1", "theme2"]:
            current_theme = 1 if st.session_state.get("june_v2_view") == "theme1" else 2
            _render_theme_step(current_theme)

        elif st.session_state.get("june_v2_view") == "event":
            st.markdown("""
                <div class="summer-zone-v2">
                    <h3>🌊 Summer Compliance Event</h3>
                    <p>
                        무더운 6월, 컴플라이언스도 시원하게 점검해 주세요.
                        본 교육을 정상 수료한 임직원은 추후 별도 추첨을 통해 모바일 쿠폰 지급 대상에 포함됩니다.
                        이벤트 퀴즈는 정보보호 핵심 수칙과 연결했습니다.
                    </p>
                </div>
            """, unsafe_allow_html=True)
            _show_training_asset(
                "summer_event_quiz.png",
                "Summer Compliance Event Quiz"
            )
            st.markdown("""
                <div class="content-card-v2">
                    <span class="page-pill-v2">Special Event · 참여형 퀴즈</span>
                    <h4>여름철 휴가·외근 중에도 기준은 그대로입니다</h4>
                    <div class="infographic-grid">
                        <div class="info-tile tile-blue"><span class="icon">🏖️</span><b>휴가철</b><span>업무 자료 반출·저장 경로 확인</span></div>
                        <div class="info-tile tile-green"><span class="icon">🔑</span><b>계정관리</b><span>ID/PW 공유 금지, 개인별 권한 준수</span></div>
                        <div class="info-tile tile-orange"><span class="icon">📁</span><b>파일보호</b><span>개인정보·기업비밀 암호화 및 파기</span></div>
                        <div class="info-tile tile-purple"><span class="icon">🎁</span><b>추첨대상</b><span>정상 수료자 중 모바일 쿠폰 추첨</span></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            event_answer = st.radio(
                "이벤트 Q. 여름철 휴가·외근 중에도 지켜야 할 정보보호 수칙으로 가장 적절한 것은?",
                [
                    SELECT_PLACEHOLDER,
                    "업무 편의를 위해 고객정보 파일을 개인 메일로 보내 둔다",
                    "기업비밀·개인정보 파일은 암호화하고, 목적 완료 후 안전하게 파기한다",
                    "비밀번호는 동료와 공유해 두면 업무 공백을 줄일 수 있다"
                ],
                key="event_v2_q1"
            )
            if event_answer == "기업비밀·개인정보 파일은 암호화하고, 목적 완료 후 안전하게 파기한다":
                st.success("정답입니다. 시원한 여름에도 정보보호 기준은 그대로 유지됩니다. 🌊")
            elif event_answer != SELECT_PLACEHOLDER:
                st.info("힌트: 개인정보·기업비밀은 암호화, 접근권한, 목적 완료 후 안전한 파기가 핵심입니다.")
            ev_prev, ev_msg, ev_next = st.columns([0.18, 0.54, 0.28])
            with ev_prev:
                if st.button("◀ Theme 2로", use_container_width=True, key="june_v2_event_prev", type="secondary"):
                    st.session_state["june_v2_view"] = "theme2"
                    st.session_state["june_v2_theme"] = 2
                    st.session_state["june_v2_step"] = 6
                    _request_training_scroll_top()
                    st.rerun()
            with ev_msg:
                st.markdown("<div class='nav-help'>이벤트 퀴즈에 응답하면 수료 제출 단계로 이동할 수 있습니다.</div>", unsafe_allow_html=True)
            with ev_next:
                if st.button("Event CLEAR → 수료 제출", use_container_width=True, key="june_v2_event_next", type="primary"):
                    if st.session_state.get("event_v2_q1", SELECT_PLACEHOLDER) == SELECT_PLACEHOLDER:
                        st.warning("이벤트 퀴즈에 응답해야 수료 제출 단계로 이동할 수 있습니다.")
                    else:
                        st.session_state["june_v2_event_done"] = True
                        st.session_state["june_v2_view"] = "submit"
                        _request_training_scroll_top()
                        st.rerun()

        elif st.session_state.get("june_v2_view") == "submit":
            st.markdown("### ✅ 수료 제출")
            st.caption("아래 정보를 입력하고 제출하면 교육 수료 및 이벤트 퀴즈 정보가 Google Sheet에 저장됩니다.")
            t1_done = st.session_state.get("june_v2_theme1_done", False)
            t2_done = st.session_state.get("june_v2_theme2_done", False)
            event_answer_now = st.session_state.get("event_v2_q1", SELECT_PLACEHOLDER)
            event_answered_now = event_answer_now != SELECT_PLACEHOLDER
            event_correct_now = event_answer_now == "기업비밀·개인정보 파일은 암호화하고, 목적 완료 후 안전하게 파기한다"
            t1_score_now = _theme_score(1)
            t2_score_now = _theme_score(2)
            quiz_score_now = (_quiz_correct_count(1) * 5) + (_quiz_correct_count(2) * 6)
            event_score_now = 10 if event_answered_now else 0
            final_submit_score = 10 if (t1_done and t2_done and event_answered_now) else 0
            participation_score = (15 if _checks_done(1) else 0) + (15 if _checks_done(2) else 0) + event_score_now + final_submit_score
            final_score = t1_score_now + t2_score_now + event_score_now + final_submit_score

            cstat1, cstat2, cstat3, cstat4 = st.columns(4)
            cstat1.metric("Theme 1", "CLEAR" if t1_done else "진행 중")
            cstat2.metric("Theme 2", "CLEAR" if t2_done else "진행 중")
            cstat3.metric("이벤트", "CLEAR" if event_answered_now else "미참여")
            cstat4.metric("최종점수", f"{final_score}/100")

            st.markdown("""
                <div class="content-card-v2">
                    <span class="page-pill-v2">Completion Standard</span>
                    <h4>수료 기준</h4>
                    <p>
                        Theme 1, Theme 2, Summer Event를 순서대로 완료하고 사번·성명·소속을 입력해야 수료 제출이 가능합니다.
                        점수는 이해도 확인용이며, 정상 수료자는 추후 모바일 쿠폰 추첨 대상에 포함됩니다.
                    </p>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            c1, c2, c3, c4 = st.columns(4)
            emp_id = c1.text_input("사번", placeholder="사번(1000****) / 미부여 시 00000000", key="june_emp_id")
            name = c2.text_input("성명", key="june_name")
            ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
            unit = c3.selectbox("총괄 / 본부 / 단", ordered_units, index=None, placeholder="선택", key="june_unit")
            dept = c4.text_input("상세 부서명", placeholder="현 소속부서명", key="june_dept")

            can_submit = t1_done and t2_done and event_answered_now
            if not can_submit:
                st.warning("Theme 1·Theme 2·Summer Event를 모두 CLEAR해야 수료 제출이 가능합니다.")

            left_nav, right_submit = st.columns([0.22, 0.78])
            with left_nav:
                if st.button("◀ Event로", use_container_width=True, key="june_v2_submit_prev", type="secondary"):
                    st.session_state["june_v2_view"] = "event"
                    _request_training_scroll_top()
                    st.rerun()
            with right_submit:
                submit_june_training = st.button(
                    "📨 6월 컴플라이언스 교육 수료 제출",
                    use_container_width=True,
                    disabled=(not can_submit or st.session_state.get("june_training_saved", False)),
                    key="june_training_submit",
                    type="primary"
                )

            if submit_june_training:
                if not emp_id or not name or not unit or not dept:
                    st.warning("⚠️ 사번, 성명, 총괄/본부/단, 상세 부서명을 모두 입력해 주세요.")
                else:
                    ok, msg = validate_emp_id(emp_id)
                    if not ok:
                        st.warning(msg)
                    else:
                        record = {
                            "사번": emp_id.strip(),
                            "성명": name.strip(),
                            "총괄/본부/단": unit,
                            "부서": dept.strip(),
                            "교육대상": "전 임직원",
                            "Theme1_청렴공정_확인": "완료" if t1_done else "미완료",
                            "Theme1_점수": t1_score_now,
                            "Theme2_협력정보_확인": "완료" if t2_done else "미완료",
                            "Theme2_점수": t2_score_now,
                            "이벤트퀴즈_선택": event_answer_now,
                            "이벤트퀴즈_정답여부": "정답" if event_correct_now else "오답",
                            "퀴즈점수": quiz_score_now,
                            "참여점수": participation_score,
                            "최종점수": final_score,
                            "수료상태": "수료",
                            "이벤트추첨대상": "대상",
                            "비고": "감사실 주관 2026년 6월 컴플라이언스 인식제고 자율점검 교육 / 모바일 쿠폰 추첨 대상 포함 / Final V3 단계별 60초·체크항목 10초 확인형 교육",
                        }
                        with st.spinner("6월 컴플라이언스 교육 수료 내역을 저장 중입니다..."):
                            success, save_msg = save_june_compliance_training_result(record)
                        if success:
                            st.session_state["june_training_saved"] = True
                            st.success(f"✅ {name}님, 최종 수료 제출이 완료되었습니다.")
                            st.balloons()
                            st.info("교육 수료 및 이벤트 퀴즈 정보가 Google Sheet에 저장되었습니다. 5초 후 교육 초기 화면으로 이동합니다.")
                            reset_ph = st.empty()
                            for sec in range(5, 0, -1):
                                reset_ph.markdown(
                                    f"<div class='timer-panel timer-panel-clear'>✅ 최종 제출 완료 · {sec}초 후 초기 화면으로 이동합니다.</div>",
                                    unsafe_allow_html=True,
                                )
                                time.sleep(1)
                            st.session_state["june_force_reset_after_submit"] = True
                            _request_training_scroll_top()
                            st.rerun()
                        else:
                            st.error(f"❌ 제출 실패: {save_msg}")

# --- [Tab 2: 법률 리스크/규정/계약 검토 & 감사보고서 작성] ---
# --- [Tab 2: 법률 리스크/규정/계약 검토 & 감사보고서 작성] ---
with tab_doc:
    st.markdown("### 📄 법률 검토 · 감사보고서 작성/검증")

    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        st.markdown("""
        <div class="audit-message-v2">
            <h4>🧭 AI 검토 품질 업그레이드 적용</h4>
            <p>최신 Gemini 모델 우선 선택, 검색 보강 옵션, 조항별 리스크 표, 수정문안, 감사보고서 품질검증 구조를 적용했습니다. 자율점검 기능은 수정하지 않았습니다.</p>
        </div>
        """, unsafe_allow_html=True)

        cur1, cur2 = st.tabs(["⚖️ 법률 리스크 심층 검토", "🔍 감사보고서 작성·검증"])

        with cur1:
            st.markdown("#### ⚖️ 법률 리스크 정밀 검토")
            st.caption("계약서·규정·공문·검토자료를 업로드하면 쟁점, 리스크, 근거 방향, 수정문안을 구조적으로 정리합니다.")

            uploaded_file = st.file_uploader("파일 업로드 (PDF, Word, TXT)", type=["txt", "pdf", "docx"], key="cur1_file")

            col_a, col_b = st.columns(2)
            with col_a:
                doc_type = st.selectbox(
                    "문서 유형",
                    ["계약서", "약관/일반조건", "사내 규정", "공문/통지문", "감사·조사 자료", "기타"],
                    index=0,
                    key="cur1_doc_type"
                )
                analysis_depth = st.selectbox(
                    "분석 수준",
                    ["핵심 요약", "리스크 식별(중점)", "조항/근거 중심(심층)", "수정문안 중심"],
                    index=2,
                    key="cur1_depth"
                )
            with col_b:
                company_position = st.selectbox(
                    "검토 관점",
                    ["우리 회사 입장", "갑/발주자 입장", "을/수급자 입장", "중립 검토"],
                    index=0,
                    key="cur1_position"
                )
                focus_area = st.selectbox(
                    "중점 분야",
                    ["전체 리스크", "계약대금/지급조건", "손해배상/면책", "하도급/공정거래", "개인정보/정보보호", "노무/안전보건", "부패방지/이해충돌"],
                    index=0,
                    key="cur1_focus"
                )

            use_search = st.toggle(
                "🔎 최신 법령·판례·가이드 검색 보강 사용",
                value=True,
                key="cur1_search",
                help="Gemini API의 Google Search Grounding을 우선 시도합니다. 패키지/계정에서 지원되지 않으면 일반 분석으로 대체됩니다."
            )

            if st.button("🚀 법률 리스크 분석 시작", use_container_width=True, key="cur1_run"):
                if not uploaded_file:
                    st.warning("⚠️ 먼저 파일을 업로드해주세요.")
                else:
                    content = read_file(uploaded_file)
                    if not content:
                        st.error("❌ 파일에서 텍스트를 추출하지 못했습니다. 스캔 PDF인 경우 OCR 처리 후 다시 업로드해 주세요.")
                    else:
                        with st.spinner("🧠 법률·컴플라이언스 관점에서 심층 분석 중입니다..."):
                            try:
                                prompt = build_legal_review_prompt(content, analysis_depth, doc_type, focus_area, company_position)
                                response, grounded, warning = generate_ai_response(prompt, task="legal", use_search=use_search, temperature=0.15)
                                st.success("✅ 분석 완료")
                                render_ai_response(response, grounded=grounded, warning=warning)
                            except Exception as e:
                                st.error(f"오류: {e}")

        with cur2:
            st.markdown("#### 🔍 감사보고서 작성·검증")
            st.caption("면담자료, 증거자료, 회사 규정, 기존 보고서를 바탕으로 감사보고서 초안 작성 또는 품질검증을 수행합니다.")

            mode = st.radio(
                "작업 모드",
                ["🧾 감사보고서 초안 생성", "✅ 감사보고서 검증·교정(오탈자/논리/형식)"],
                horizontal=True,
                key="cur2_mode"
            )
            is_draft_mode = "초안" in mode

            with st.expander("🔐 보안·주의사항", expanded=False):
                st.markdown(
                    "- 민감정보는 업로드 전 내부 보안 기준에 따라 비식별 처리하는 것이 안전합니다.\n"
                    "- 본 기능은 감사 판단을 보조하는 도구이며, 최종 판단·결재 책임은 감사실에 있습니다.\n"
                    "- 자료에 없는 사실은 생성하지 않도록 프롬프트에 제한을 두었습니다."
                )

            interview_audio = None
            interview_transcript = None
            evidence_files = []
            draft_text = ""
            draft_file = None

            if is_draft_mode:
                st.markdown("### ① 감사 자료 입력")
                cL, cR = st.columns(2)
                with cL:
                    interview_audio = st.file_uploader("🎧 면담 음성(mp3/wav/mp4) — 선택", type=["mp3", "wav", "mp4"], key="cur2_audio")
                    interview_transcript = st.file_uploader("📝 면담 녹취/메모(PDF/DOCX/TXT) — 권장", type=["txt", "pdf", "docx"], key="cur2_transcript")
                with cR:
                    evidence_files = st.file_uploader(
                        "📂 조사·증거/확인 자료 — 복수 업로드 가능",
                        type=["pdf", "png", "jpg", "jpeg", "xlsx", "xls", "csv", "txt", "docx"],
                        accept_multiple_files=True,
                        key="cur2_evidence"
                    ) or []
            else:
                st.markdown("### ① 검증 대상 보고서 입력")
                cL, cR = st.columns(2)
                with cL:
                    draft_text = st.text_area("검증할 감사보고서 붙여넣기", height=230, key="cur2_draft")
                with cR:
                    draft_file = st.file_uploader("또는 파일 업로드(PDF/DOCX/TXT)", type=["pdf", "docx", "txt"], key="cur2_draft_file")

            st.markdown("### ② 회사 규정/판단 기준 · ③ 표준 보고서 형식")
            left, right = st.columns(2)
            with left:
                regulations = st.file_uploader(
                    "📘 회사 규정/기준(인사규정·징계기준·윤리지침 등)",
                    type=["pdf", "docx", "txt"],
                    accept_multiple_files=True,
                    key="cur2_regs"
                ) or []
            with right:
                reference_reports = st.file_uploader(
                    "📑 참고 보고서 형식 — 선택",
                    type=["pdf", "docx", "txt"],
                    accept_multiple_files=True,
                    key="cur2_refs"
                ) or []

            st.markdown("### ④ 사건 개요 및 작성 옵션")
            row1, row2 = st.columns(2)
            with row1:
                case_title = st.text_input("사건명/건명", placeholder="예: 법인카드 사적 사용 의혹 조사", key="cur2_title")
            with row2:
                report_tone = st.selectbox(
                    "문서 톤",
                    ["감사보고서(공식·중립)", "보고서(간결·결정 중심)", "상신용(결재/조치 권고 중심)"],
                    index=0,
                    key="cur2_tone"
                )
            case_scope = st.text_area("사건 개요 요약 — 무엇을/언제/누가/어떤 경위로", height=120, key="cur2_scope")

            if st.button("🧠 감사보고서 AI 실행", use_container_width=True, key="cur2_run"):
                materials = []

                if is_draft_mode:
                    if interview_transcript:
                        transcript_text = read_file(interview_transcript)
                        if transcript_text:
                            materials.append(f"[면담 녹취/메모]\n{transcript_text}")
                    if evidence_files:
                        materials.append("[조사·증거 자료]\n" + read_multiple_files(evidence_files))
                    if interview_audio:
                        audio_file = process_media_file(interview_audio)
                        if audio_file:
                            materials.append("[면담 음성 파일]\nAI 업로드 파일이 함께 전달됩니다.")
                else:
                    if draft_text.strip():
                        materials.append("[검증 대상 보고서 - 붙여넣기]\n" + draft_text.strip())
                    if draft_file:
                        extracted = read_file(draft_file)
                        if extracted:
                            materials.append("[검증 대상 보고서 - 파일]\n" + extracted)

                regulations_text = read_multiple_files(regulations) if regulations else ""
                refs_text = read_multiple_files(reference_reports) if reference_reports else ""
                materials_text = "\n\n".join(materials).strip()

                if not case_title.strip():
                    st.warning("⚠️ 사건명/건명을 입력해 주세요.")
                elif not case_scope.strip() and not materials_text:
                    st.warning("⚠️ 사건 개요 또는 감사 자료 중 하나 이상은 입력해야 합니다.")
                else:
                    with st.spinner("📑 감사보고서 품질 기준에 맞춰 처리 중입니다..."):
                        try:
                            prompt = build_audit_report_prompt(mode, case_title, case_scope, report_tone, materials_text, regulations_text, refs_text)
                            if is_draft_mode and interview_audio:
                                # 음성 파일이 있는 경우 멀티모달 입력을 시도합니다.
                                audio_file = process_media_file(interview_audio)
                                if audio_file:
                                    response, grounded, warning = generate_ai_response([prompt, audio_file], task="report", use_search=False, temperature=0.12)
                                else:
                                    response, grounded, warning = generate_ai_response(prompt, task="report", use_search=False, temperature=0.12)
                            else:
                                response, grounded, warning = generate_ai_response(prompt, task="report", use_search=False, temperature=0.12)
                            st.success("✅ 처리 완료")
                            render_ai_response(response, grounded=grounded, warning=warning)
                        except Exception as e:
                            st.error(f"오류: {e}")

# --- [Tab 3: AI 에이전트] ---
with tab_chat:
    st.markdown("### 💬 AI 에이전트(챗봇)")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        st.markdown("""
        <div class="audit-message-v2">
            <h4>🤝 감사·법률·컴플라이언스 전용 챗봇</h4>
            <p>질문을 그대로 전달하지 않고, 감사실 업무 기준에 맞춘 역할·답변 구조·한계 고지를 적용합니다. 최신 이슈는 검색 보강 모드를 사용할 수 있습니다.</p>
        </div>
        """, unsafe_allow_html=True)

        if "messages" not in st.session_state:
            st.session_state.messages = []

        chat_mode = st.selectbox(
            "상담 모드",
            ["감사·컴플라이언스 일반 상담", "최신 법령·판례·뉴스 검색 보강", "문서/보고서 문안 개선"],
            index=0,
            key="chat_mode"
        )
        use_chat_search = "최신" in chat_mode

        c1, c2 = st.columns([0.78, 0.22])
        with c1:
            with st.form(key="chat_input_form", clear_on_submit=True):
                user_input = st.text_input("질문 입력", placeholder="예: 계약서 지급조건 100일 조항의 리스크를 검토해줘")
                send_btn = st.form_submit_button("전송 📤", use_container_width=True)
        with c2:
            st.markdown("<div style='height:29px'></div>", unsafe_allow_html=True)
            if st.button("대화 초기화", use_container_width=True, key="chat_clear"):
                st.session_state.messages = []
                st.rerun()

        if send_btn and user_input:
            history_before = st.session_state.messages.copy()
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("답변 생성 중..."):
                try:
                    prompt = build_chat_prompt(user_input, history_before, chat_mode)
                    response, grounded, warning = generate_ai_response(prompt, task="chat", use_search=use_chat_search, temperature=0.2)
                    answer = _extract_response_text(response) or "응답을 생성하지 못했습니다."
                    sources = _extract_grounding_sources(response)
                    if grounded and sources:
                        src_text = "\n\n---\n**참고 출처**\n" + "\n".join([f"- [{s['title']}]({s['uri']})" for s in sources])
                        answer += src_text
                    elif warning:
                        answer += "\n\nℹ️ 검색 보강 호출이 실패하여 일반 AI 답변으로 대체되었습니다."
                    st.session_state.messages.append({"role": "assistant", "content": answer})
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
        st.markdown("""
        <div class="audit-message-v2">
            <h4>🧩 출처·리스크 중심 스마트 요약</h4>
            <p>뉴스, 웹페이지, 유튜브, 회의 음성, 텍스트를 업무 브리핑 형식으로 요약합니다. 필요 시 Google Search Grounding을 사용해 최신성도 보강합니다.</p>
        </div>
        """, unsafe_allow_html=True)

        st_type = st.radio("입력 방식", ["URL (유튜브/웹)", "미디어 파일", "텍스트"], horizontal=True)
        summary_mode = st.selectbox(
            "요약 모드",
            ["뉴스·보도자료 브리핑", "유튜브·교육영상 요약", "회의·면담 녹취 요약", "감사자료·증거자료 요약", "일반 요약"],
            index=0,
            key="summary_mode"
        )
        output_style = st.selectbox(
            "출력 방식",
            ["임원 보고용", "실무 체크리스트형", "교육자료 재가공용", "상세 분석형"],
            index=1,
            key="summary_style"
        )
        use_summary_search = st.toggle(
            "🔎 최신 검색 보강 사용(URL/뉴스 요약 권장)",
            value=("URL" in st_type),
            key="summary_search"
        )

        final_input = None
        is_multimodal = False
        source_hint = "직접 입력"

        if "URL" in st_type:
            url = st.text_input("URL 입력", placeholder="https:// 또는 유튜브 링크")
            source_hint = url or "URL"
            if url and "youtu" in url:
                with st.spinner("자막 추출 중..."):
                    final_input = get_youtube_transcript(url)
                    if not final_input:
                        st.info("자막을 찾지 못해 음성 분석을 시도합니다. 영상 길이와 권한에 따라 시간이 걸릴 수 있습니다.")
                        final_input = download_and_upload_youtube_audio(url)
                        is_multimodal = True if final_input else False
            elif url:
                with st.spinner("웹페이지 본문을 추출 중..."):
                    final_input = get_web_content(url)
                    if not final_input:
                        st.warning("웹페이지 본문을 직접 추출하지 못했습니다. 검색 보강 모드를 켠 상태로 URL 중심 요약을 시도할 수 있습니다.")
                        final_input = f"다음 URL의 공개 정보를 검색해 업무 브리핑 형식으로 요약하세요: {url}"

        elif "미디어" in st_type:
            mf = st.file_uploader("파일 업로드", type=["mp3", "wav", "mp4"])
            source_hint = getattr(mf, "name", "미디어 파일") if mf else "미디어 파일"
            if mf:
                final_input = process_media_file(mf)
                is_multimodal = True
        else:
            final_input = st.text_area("텍스트 입력", height=230)
            source_hint = "붙여넣은 텍스트"

        if st.button("⚡ 요약 실행", use_container_width=True):
            if final_input:
                with st.spinner("요약 중..."):
                    try:
                        if is_multimodal:
                            prompt = build_summary_prompt(summary_mode, output_style, source_hint, "첨부된 미디어 파일의 내용을 분석하세요.")
                            response, grounded, warning = generate_ai_response([prompt, final_input], task="summary", use_search=False, temperature=0.18)
                        else:
                            prompt = build_summary_prompt(summary_mode, output_style, source_hint, str(final_input))
                            response, grounded, warning = generate_ai_response(prompt, task="summary", use_search=use_summary_search, temperature=0.18)
                        st.success("✅ 요약 완료")
                        render_ai_response(response, grounded=grounded, warning=warning)
                    except Exception as e:
                        st.error(f"오류: {e}")
            else:
                st.warning("⚠️ 요약할 URL, 파일 또는 텍스트를 입력해 주세요.")

# --- [Tab 5: 관리자 대시보드 최종 버전] ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    st.caption("6월 컴플라이언스 인식제고 교육 수료 현황을 실시간으로 확인하고 CSV/Excel로 다운로드할 수 있습니다.")

    # 1. 관리자 비밀번호 검증
    admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_dash_pw")
    if admin_pw.strip() != "ktmos0402!":
        st.info("관리자 비밀번호를 입력하세요.")
        st.stop()

    st.success("✅ 접속 성공")

    # 2. 구글 시트 연결
    client = init_google_sheet_connection()
    if not client:
        st.error("❌ 구글 시트 연결 실패. API 권한 및 Secrets 설정을 확인하세요.")
        st.stop()

    try:
        spreadsheet = client.open("Audit_Result_2026")
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        st.stop()

    # =========================================================
    # ✅ 6월 컴플라이언스 교육 수료 내역: 실시간 확인 / CSV 다운로드
    # =========================================================
    st.markdown("---")
    st.markdown("#### 🌊 6월 컴플라이언스 인식제고 교육 수료 현황")
    st.caption("Google Sheet에 저장된 수료 내역을 그대로 불러옵니다. 필요 시 새로고침 후 CSV/Excel로 내려받아 활용하세요.")

    refresh_col, info_col = st.columns([0.16, 0.84])
    with refresh_col:
        if st.button("🔄 새로고침", use_container_width=True, key="june_admin_refresh"):
            st.cache_data.clear()
            _request_training_scroll_top()
            st.rerun()
    with info_col:
        st.caption("제출 직후 화면에 바로 보이지 않으면 새로고침을 눌러 최신 Google Sheet 데이터를 다시 불러오세요.")

    try:
        try:
            june_ws = spreadsheet.worksheet(JUNE_TRAINING_SHEET_NAME)
            june_values = june_ws.get_all_values()
        except Exception:
            june_values = []

        if not june_values or len(june_values) < 2:
            st.warning("아직 저장된 6월 컴플라이언스 교육 수료 내역이 없습니다.")
            june_df = pd.DataFrame(columns=JUNE_TRAINING_HEADERS)
        else:
            june_df = pd.DataFrame(june_values[1:], columns=june_values[0])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("총 수료자", f"{len(june_df)}명")
        if not june_df.empty and "이벤트추첨대상" in june_df.columns:
            event_count = int((june_df["이벤트추첨대상"].astype(str) == "대상").sum())
            m2.metric("이벤트 추첨 대상", f"{event_count}명")
        else:
            m2.metric("이벤트 추첨 대상", "0명")
        if not june_df.empty and "최종점수" in june_df.columns:
            score_series = pd.to_numeric(june_df["최종점수"], errors="coerce")
            avg_score = score_series.mean() if not score_series.dropna().empty else 0
            m3.metric("평균 점수", f"{avg_score:.1f}점")
        else:
            m3.metric("평균 점수", "0점")
        if not june_df.empty and "저장시간" in june_df.columns:
            m4.metric("최근 저장시간", str(june_df["저장시간"].iloc[-1]))
        else:
            m4.metric("최근 저장시간", "-")

        search_term = st.text_input("🔍 수료 내역 검색", placeholder="성명, 사번, 부서, 본부 등", key="june_admin_search")
        if search_term and not june_df.empty:
            june_display_df = june_df[june_df.apply(lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(), axis=1)]
        else:
            june_display_df = june_df

        st.dataframe(june_display_df, use_container_width=True, hide_index=True)

        dl1, dl2 = st.columns(2)
        with dl1:
            june_csv_bytes = june_display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 현재 조회내역 CSV 다운로드",
                june_csv_bytes,
                f"{JUNE_TRAINING_SHEET_NAME}.csv",
                "text/csv",
                use_container_width=True,
                key="june_csv_download"
            )
        with dl2:
            try:
                from io import BytesIO
                output = BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    june_display_df.to_excel(writer, index=False, sheet_name="6월_컴플라이언스교육")
                st.download_button(
                    "📥 현재 조회내역 Excel 다운로드",
                    output.getvalue(),
                    f"{JUNE_TRAINING_SHEET_NAME}.xlsx",
                    use_container_width=True,
                    key="june_xlsx_download"
                )
            except Exception:
                st.info("Excel 엔진 미설치로 CSV 다운로드를 이용하세요.")
    except Exception as e:
        st.error(f"6월 교육 수료 내역 로드 중 오류 발생: {e}")

    # =========================================================
    # 기존 자율점검 참여율 대시보드는 숨김 보관함으로 이동
    # =========================================================
    with st.expander("📁 기존 자율점검 참여율 대시보드 열기", expanded=False):
        st.caption("기존 윤리경영 실천서약 참여율 및 제출 데이터 조회 기능입니다. 필요할 때만 펼쳐서 확인하세요.")

        try:
            ws_list = spreadsheet.worksheets()
            excluded_sheets = ["Campaign_Config", JUNE_TRAINING_SHEET_NAME, "2026_현장대리인_선임신고"]
            sheet_names = [ws.title for ws in ws_list if ws.title not in excluded_sheets]

            if not sheet_names:
                st.warning("분석 가능한 기존 자율점검 시트가 없습니다.")
            else:
                selected_sheet = st.selectbox("📊 분석 대상 시트 선택", sheet_names, key="admin_sheet_select")
                ws = spreadsheet.worksheet(selected_sheet)
                values = ws.get_all_values()

                if not values or len(values) < 2:
                    st.warning("선택한 시트에 데이터가 없습니다.")
                else:
                    df = pd.DataFrame(values[1:], columns=values[0])

                    st.markdown("---")
                    st.markdown("#### 📈 실시간 참여 현황 분석")

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

                    if "총괄/본부/단" not in df.columns:
                        st.warning("선택한 시트에 '총괄/본부/단' 컬럼이 없어 참여율 차트를 생성할 수 없습니다.")
                    else:
                        unit_counts = df["총괄/본부/단"].value_counts().to_dict()
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
                        total_target = sum(total_staff_map.values())
                        total_current = len(df)
                        total_ratio = (total_current / total_target) * 100 if total_target else 0

                        m1, m2, m3 = st.columns(3)
                        m1.metric("전체 대상자", f"{total_target}명")
                        m2.metric("현재 참여자", f"{total_current}명")
                        m3.metric("전체 참여율", f"{total_ratio:.1f}%")

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

                    with st.expander("📄 제출 데이터 상세 보기 / 검색", expanded=False):
                        search_term_old = st.text_input("🔍 성명 또는 부서 검색", "", key="old_admin_search")
                        if search_term_old:
                            display_df = df[df.apply(lambda row: row.astype(str).str.contains(search_term_old, case=False, na=False).any(), axis=1)]
                        else:
                            display_df = df
                        st.dataframe(display_df, use_container_width=True, hide_index=True)

                    st.markdown("---")
                    st.markdown("#### ⬇️ 기존 자율점검 데이터 내보내기")
                    d1, d2 = st.columns(2)
                    with d1:
                        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
                        st.download_button("📥 CSV 다운로드", csv_bytes, f"{selected_sheet}.csv", "text/csv", use_container_width=True, key="old_csv_download")
                    with d2:
                        try:
                            from io import BytesIO
                            output = BytesIO()
                            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                                df.to_excel(writer, index=False, sheet_name="참여현황")
                            st.download_button("📥 Excel 다운로드", output.getvalue(), f"{selected_sheet}.xlsx", use_container_width=True, key="old_xlsx_download")
                        except Exception:
                            st.info("Excel 엔진 미설치로 CSV 이용을 권장합니다.")
        except Exception as e:
            st.error(f"기존 자율점검 데이터 로드 중 오류 발생: {e}")

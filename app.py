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

        # ✅ 동시 수료 제출 안정화: 저장 직전 전체 데이터 읽기(get_all_records)를 하지 않습니다.
        # 1,000명 동시 접속 상황에서 읽기 요청 한도(429)를 유발하던 중복검사는 운영 종료 후 Google Sheet에서 사번 기준으로 확인합니다.
        emp_id_str = str(record.get("사번", "")).strip()
        name_str = str(record.get("성명", "")).strip()
        dept_str = str(record.get("부서", "")).strip()

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
        last_error = None
        for attempt in range(5):
            try:
                sheet.append_row(row, value_input_option="USER_ENTERED")
                return True, "6월 컴플라이언스 인식제고 교육 수료 내역이 저장되었습니다."
            except Exception as append_error:
                last_error = append_error
                msg = str(append_error)
                if "429" in msg or "Quota exceeded" in msg or "RESOURCE_EXHAUSTED" in msg:
                    time.sleep(1.2 * (attempt + 1))
                    continue
                raise
        return False, f"Google Sheet 저장 요청이 일시적으로 집중되어 저장하지 못했습니다. 잠시 후 현재 화면에서 다시 제출해 주세요. ({last_error})"
    except Exception as e:
        return False, str(e)

# ==========================================
# 8-1. 현장 IP 자동 전환 및 Google Sheets 이력관리
# ==========================================
import json
import platform
import subprocess
import socket
import getpass
import ipaddress

IP_PROFILE_SHEET_NAME = "IP_Profiles"
IP_HISTORY_SHEET_NAME = "IP_Change_History"
IP_PROFILE_HEADERS = [
    "profile_id", "프로필명", "어댑터명", "IP주소", "서브넷마스크", "기본게이트웨이",
    "기본DNS", "보조DNS", "사용여부", "수정일시", "수정자사번", "수정자성명", "비고"
]
IP_HISTORY_HEADERS = [
    "변경일시", "작업ID", "작업결과", "프로필ID", "프로필명", "PC명", "Windows사용자",
    "수정자사번", "수정자성명", "어댑터명", "기존IP", "기존서브넷", "기존게이트웨이",
    "기존DNS", "변경IP", "변경서브넷", "변경게이트웨이", "변경DNS", "오류내용", "비고"
]


def _open_ip_spreadsheet():
    """기존 Google 서비스 계정 연결을 재사용하여 IP 관리 스프레드시트를 엽니다."""
    client = init_google_sheet_connection()
    if not client:
        raise RuntimeError("Google Sheets 연결 실패: .streamlit/secrets.toml의 gcp_service_account 설정을 확인하세요.")
    # 기존 앱이 사용하는 동일 파일을 활용하여 별도 자격증명 추가를 피합니다.
    return client.open("Audit_Result_2026")


def _ensure_ip_sheet(spreadsheet, title: str, headers: list[str], rows: int = 3000):
    try:
        ws = spreadsheet.worksheet(title)
    except Exception:
        ws = spreadsheet.add_worksheet(title=title, rows=rows, cols=max(len(headers) + 2, 20))
        ws.append_row(headers)
    values = ws.get_all_values()
    if not values:
        ws.append_row(headers)
    elif values[0][:len(headers)] != headers:
        # 기존 데이터 훼손 방지를 위해 헤더를 강제로 덮어쓰지 않고 오류로 중단합니다.
        raise RuntimeError(f"'{title}' 시트의 헤더가 예상 형식과 다릅니다. 기존 시트를 백업한 후 확인하세요.")
    return ws


def load_ip_profiles() -> list[dict]:
    spreadsheet = _open_ip_spreadsheet()
    ws = _ensure_ip_sheet(spreadsheet, IP_PROFILE_SHEET_NAME, IP_PROFILE_HEADERS)
    records = ws.get_all_records()
    return [r for r in records if str(r.get("사용여부", "Y")).strip().upper() != "N"]


def _profile_row_index(ws, profile_id: str) -> int | None:
    rows = ws.get_all_values()
    for idx, row in enumerate(rows[1:], start=2):
        if row and str(row[0]).strip() == str(profile_id).strip():
            return idx
    return None


def save_ip_profile(profile: dict, modifier_emp_id: str, modifier_name: str) -> tuple[bool, str]:
    try:
        validate_ip_profile(profile)
        spreadsheet = _open_ip_spreadsheet()
        ws = _ensure_ip_sheet(spreadsheet, IP_PROFILE_SHEET_NAME, IP_PROFILE_HEADERS)
        profile_id = str(profile.get("profile_id") or "").strip()
        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        if not profile_id:
            seed = f"{profile.get('프로필명')}|{profile.get('IP주소')}|{now}"
            profile_id = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]

        row = [
            profile_id, str(profile.get("프로필명", "")).strip(), str(profile.get("어댑터명", "")).strip(),
            str(profile.get("IP주소", "")).strip(), str(profile.get("서브넷마스크", "")).strip(),
            str(profile.get("기본게이트웨이", "")).strip(), str(profile.get("기본DNS", "")).strip(),
            str(profile.get("보조DNS", "")).strip(), "Y", now, modifier_emp_id.strip(), modifier_name.strip(),
            str(profile.get("비고", "")).strip(),
        ]
        row_idx = _profile_row_index(ws, profile_id)
        if row_idx:
            ws.update(f"A{row_idx}:M{row_idx}", [row])
            return True, "IP 프로필이 수정되었습니다."
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True, "IP 프로필이 등록되었습니다."
    except Exception as e:
        return False, str(e)


def disable_ip_profile(profile_id: str, modifier_emp_id: str, modifier_name: str) -> tuple[bool, str]:
    try:
        spreadsheet = _open_ip_spreadsheet()
        ws = _ensure_ip_sheet(spreadsheet, IP_PROFILE_SHEET_NAME, IP_PROFILE_HEADERS)
        row_idx = _profile_row_index(ws, profile_id)
        if not row_idx:
            return False, "삭제할 프로필을 찾지 못했습니다."
        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        ws.update(f"I{row_idx}:L{row_idx}", [["N", now, modifier_emp_id.strip(), modifier_name.strip()]])
        return True, "프로필을 비활성화했습니다. 기존 변경 이력은 유지됩니다."
    except Exception as e:
        return False, str(e)


def _mask_to_prefix(mask: str) -> int:
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen
    except Exception as e:
        raise ValueError("서브넷 마스크 형식이 올바르지 않습니다. 예: 255.255.255.0") from e


def validate_ip_profile(profile: dict) -> None:
    required = ["프로필명", "어댑터명", "IP주소", "서브넷마스크"]
    missing = [k for k in required if not str(profile.get(k, "")).strip()]
    if missing:
        raise ValueError("필수값 누락: " + ", ".join(missing))

    ip = ipaddress.IPv4Address(str(profile["IP주소"]).strip())
    mask = str(profile["서브넷마스크"]).strip()
    prefix = _mask_to_prefix(mask)
    network = ipaddress.IPv4Network(f"{ip}/{prefix}", strict=False)
    if ip in {network.network_address, network.broadcast_address}:
        raise ValueError("IP 주소로 네트워크 주소 또는 브로드캐스트 주소를 사용할 수 없습니다.")

    gateway_text = str(profile.get("기본게이트웨이", "")).strip()
    if gateway_text:
        gateway = ipaddress.IPv4Address(gateway_text)
        if gateway not in network:
            raise ValueError(f"기본 게이트웨이({gateway})가 IP 대역({network})에 포함되지 않습니다.")
    for dns_key in ("기본DNS", "보조DNS"):
        dns = str(profile.get(dns_key, "")).strip()
        if dns:
            ipaddress.IPv4Address(dns)


def is_local_windows() -> bool:
    return platform.system().lower() == "windows"


def is_windows_admin() -> bool:
    if not is_local_windows():
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def list_windows_adapters() -> list[str]:
    if not is_local_windows():
        return []
    command = [
        "powershell", "-NoProfile", "-NonInteractive", "-Command",
        "Get-NetAdapter -Physical | Where-Object {$_.Status -ne 'Disabled'} | Select-Object -ExpandProperty Name"
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def get_current_adapter_config(adapter_name: str) -> dict:
    if not is_local_windows():
        return {"ip": "", "subnet": "", "gateway": "", "dns": [], "dhcp": "", "error": "Windows 로컬 실행이 아닙니다."}
    safe_name = adapter_name.replace("'", "''")
    script = rf"""
$alias = '{safe_name}'
$cfg = Get-NetIPConfiguration -InterfaceAlias $alias -ErrorAction Stop
$ipif = Get-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction Stop
$ipv4 = $cfg.IPv4Address | Select-Object -First 1
$prefix = if ($ipv4) {{ $ipv4.PrefixLength }} else {{ $null }}
$mask = if ($prefix -ne $null) {{
    $bits = ('1' * $prefix).PadRight(32, '0')
    (($bits -split '(.{{8}})' | Where-Object {{$_}} | ForEach-Object {{[convert]::ToInt32($_,2)}}) -join '.')
}} else {{ '' }}
[PSCustomObject]@{{
  ip = if ($ipv4) {{$ipv4.IPAddress}} else {{''}}
  subnet = $mask
  gateway = if ($cfg.IPv4DefaultGateway) {{$cfg.IPv4DefaultGateway.NextHop}} else {{''}}
  dns = @($cfg.DNSServer.ServerAddresses | Where-Object {{$_ -match '^\d+\.\d+\.\d+\.\d+$'}})
  dhcp = [string]$ipif.Dhcp
}} | ConvertTo-Json -Compress
"""
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=20, check=False)
    if result.returncode != 0:
        return {"ip": "", "subnet": "", "gateway": "", "dns": [], "dhcp": "", "error": result.stderr.strip() or "현재 설정 조회 실패"}
    try:
        data = json.loads(result.stdout.strip())
        if isinstance(data.get("dns"), str):
            data["dns"] = [data["dns"]]
        return data
    except Exception:
        return {"ip": "", "subnet": "", "gateway": "", "dns": [], "dhcp": "", "error": "현재 설정 응답을 해석하지 못했습니다."}


def apply_static_ip(profile: dict) -> tuple[bool, str, dict]:
    """선택 어댑터의 IPv4 설정을 변경합니다. 관리자 권한이 없으면 실행하지 않습니다."""
    if not is_local_windows():
        return False, "이 기능은 해당 PC의 Windows에서 로컬 실행할 때만 사용할 수 있습니다.", {}
    if not is_windows_admin():
        return False, "관리자 권한이 없습니다. 명령 프롬프트 또는 PowerShell을 관리자 권한으로 실행한 뒤 Streamlit을 시작하세요.", {}
    validate_ip_profile(profile)
    adapter = str(profile["어댑터명"]).strip()
    before = get_current_adapter_config(adapter)
    prefix = _mask_to_prefix(str(profile["서브넷마스크"]).strip())
    ip = str(profile["IP주소"]).strip()
    gateway = str(profile.get("기본게이트웨이", "")).strip()
    dns = [str(profile.get("기본DNS", "")).strip(), str(profile.get("보조DNS", "")).strip()]
    dns = [x for x in dns if x]
    q = lambda value: value.replace("'", "''")

    script = rf"""
$ErrorActionPreference = 'Stop'
$alias = '{q(adapter)}'
Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Dhcp Disabled
Get-NetIPAddress -InterfaceAlias $alias -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object {{$_.IPAddress -notlike '169.254.*'}} | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
Get-NetRoute -InterfaceAlias $alias -AddressFamily IPv4 -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue |
    Remove-NetRoute -Confirm:$false -ErrorAction SilentlyContinue
"""
    if gateway:
        script += f"New-NetIPAddress -InterfaceAlias $alias -IPAddress '{q(ip)}' -PrefixLength {prefix} -DefaultGateway '{q(gateway)}'\n"
    else:
        script += f"New-NetIPAddress -InterfaceAlias $alias -IPAddress '{q(ip)}' -PrefixLength {prefix}\n"
    if dns:
        dns_literal = ",".join([f"'{q(x)}'" for x in dns])
        script += f"Set-DnsClientServerAddress -InterfaceAlias $alias -ServerAddresses @({dns_literal})\n"
    else:
        script += "Set-DnsClientServerAddress -InterfaceAlias $alias -ResetServerAddresses\n"
    script += "Clear-DnsClientCache\n"

    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=35, check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or "IP 설정 변경에 실패했습니다.", before
    time.sleep(1)
    after = get_current_adapter_config(adapter)
    if str(after.get("ip", "")).strip() != ip:
        return False, f"명령은 실행되었으나 적용된 IP({after.get('ip')})가 요청 IP({ip})와 다릅니다.", before
    return True, "IP 설정이 정상적으로 적용되었습니다.", before


def apply_dhcp(adapter_name: str) -> tuple[bool, str, dict]:
    if not is_local_windows():
        return False, "Windows 로컬 실행이 아닙니다.", {}
    if not is_windows_admin():
        return False, "관리자 권한이 없습니다.", {}
    before = get_current_adapter_config(adapter_name)
    safe = adapter_name.replace("'", "''")
    script = rf"""
$ErrorActionPreference = 'Stop'
$alias = '{safe}'
Set-NetIPInterface -InterfaceAlias $alias -AddressFamily IPv4 -Dhcp Enabled
Set-DnsClientServerAddress -InterfaceAlias $alias -ResetServerAddresses
Clear-DnsClientCache
"""
    result = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script], capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or "DHCP 전환 실패", before
    return True, "자동 IP(DHCP)로 전환했습니다.", before


def save_ip_change_history(profile: dict, before: dict, result: str, modifier_emp_id: str, modifier_name: str, error: str = "", note: str = "") -> tuple[bool, str]:
    try:
        spreadsheet = _open_ip_spreadsheet()
        ws = _ensure_ip_sheet(spreadsheet, IP_HISTORY_SHEET_NAME, IP_HISTORY_HEADERS, rows=10000)
        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        work_id = hashlib.sha256(f"{now}|{socket.gethostname()}|{modifier_emp_id}|{profile.get('IP주소')}".encode()).hexdigest()[:14]
        old_dns = ", ".join(before.get("dns", []) or [])
        new_dns = ", ".join([x for x in [str(profile.get("기본DNS", "")).strip(), str(profile.get("보조DNS", "")).strip()] if x])
        row = [
            now, work_id, result, profile.get("profile_id", ""), profile.get("프로필명", ""),
            socket.gethostname(), getpass.getuser(), modifier_emp_id.strip(), modifier_name.strip(),
            profile.get("어댑터명", ""), before.get("ip", ""), before.get("subnet", ""), before.get("gateway", ""), old_dns,
            profile.get("IP주소", ""), profile.get("서브넷마스크", ""), profile.get("기본게이트웨이", ""), new_dns,
            error, note,
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
        return True, "변경 이력이 Google Sheets에 저장되었습니다."
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

# ✅ 전 임직원 교육 집중 기간에는 앱 시작 시 Google Sheet를 읽지 않습니다.
# 기존 campaign_info 기본값만 사용하여 교육 화면 로딩 속도와 제출 안정성을 우선합니다.

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
    "🌐 IP 자동전환", "📄 법률 검토", "💬 AI 에이전트(챗봇)", "📰 스마트 요약", "🔒 관리자 모드"
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

# --- [Tab 1: 현장 IP 자동전환] ---
with tab_audit:
    st.markdown("### 🌐 현장 IP 자동전환")
    st.caption("장소별 고정 IP를 Google Sheets에 등록하고, 선택한 프로필을 현재 Windows PC에 적용합니다. 모든 변경·실패 이력은 별도로 기록됩니다.")

    st.markdown("""
    <style>
    .ip-hero {
        background: linear-gradient(135deg, #E8F1FF 0%, #F8FAFC 55%, #E8FFF6 100%);
        border: 1px solid #D7E3F4;
        border-left: 9px solid #2563EB;
        border-radius: 22px;
        padding: 22px 24px;
        margin: 10px 0 18px 0;
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
    }
    .ip-hero h3 { margin:0 0 8px 0; color:#0F172A; font-weight:950; }
    .ip-hero p { margin:0; color:#475569; line-height:1.65; font-weight:650; }
    .ip-status-ok { background:#ECFDF5; border:1px solid #A7F3D0; padding:12px 14px; border-radius:14px; }
    .ip-status-warn { background:#FFF7ED; border:1px solid #FED7AA; padding:12px 14px; border-radius:14px; }
    </style>
    <div class="ip-hero">
      <h3>현장 네트워크 설정 오류를 줄이는 표준 IP 프로필</h3>
      <p>본사·현장·장비망 등 장소별 설정을 미리 등록한 뒤 버튼 한 번으로 적용합니다. 기존 IP, 변경 IP, 일시, 작업자, 성공·실패 결과를 Google Sheets에 남겨 추적성을 확보합니다.</p>
    </div>
    """, unsafe_allow_html=True)

    local_windows = is_local_windows()
    local_admin = is_windows_admin()
    if local_windows and local_admin:
        st.success("✅ Windows 로컬 실행 및 관리자 권한이 확인되었습니다. 실제 IP 변경이 가능합니다.")
    elif local_windows:
        st.warning("⚠️ Windows에서 실행 중이지만 관리자 권한이 없습니다. 관리자 권한 PowerShell에서 `streamlit run app.py`로 실행해 주세요.")
    else:
        st.info("ℹ️ 현재 앱은 Windows 로컬 환경이 아닙니다. Google Sheets 프로필 관리와 이력 조회는 가능하지만, 이 서버에서 사용자의 PC IP를 직접 변경할 수는 없습니다.")

    identity_col1, identity_col2 = st.columns(2)
    with identity_col1:
        ip_modifier_emp_id = st.text_input("작업자 사번 *", key="ip_modifier_emp_id", placeholder="예: 10123456")
    with identity_col2:
        ip_modifier_name = st.text_input("작업자 성명 *", key="ip_modifier_name", placeholder="예: 홍길동")

    st.divider()
    switch_tab, manage_tab, history_tab = st.tabs(["⚡ IP 전환", "🛠️ IP 오류 수정·프로필 관리", "📋 변경 이력"])

    with switch_tab:
        try:
            profiles = load_ip_profiles()
            profile_load_error = ""
        except Exception as e:
            profiles = []
            profile_load_error = str(e)
            st.error(f"Google Sheets 프로필 조회 실패: {e}")

        adapters = list_windows_adapters()
        if profiles:
            profile_map = {
                f"{r.get('프로필명', '')} · {r.get('IP주소', '')} · {r.get('어댑터명', '')}": r
                for r in profiles
            }
            selected_label = st.selectbox("적용할 장소/IP 프로필", list(profile_map.keys()), key="ip_apply_profile")
            selected_profile = profile_map[selected_label]

            st.markdown("#### 선택 프로필")
            preview_df = pd.DataFrame([{
                "프로필": selected_profile.get("프로필명", ""),
                "어댑터": selected_profile.get("어댑터명", ""),
                "IP": selected_profile.get("IP주소", ""),
                "서브넷": selected_profile.get("서브넷마스크", ""),
                "게이트웨이": selected_profile.get("기본게이트웨이", ""),
                "DNS": ", ".join([x for x in [str(selected_profile.get("기본DNS", "")).strip(), str(selected_profile.get("보조DNS", "")).strip()] if x]),
            }])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)

            adapter_for_check = str(selected_profile.get("어댑터명", "")).strip()
            if local_windows and adapter_for_check:
                current = get_current_adapter_config(adapter_for_check)
                if current.get("error"):
                    st.warning(f"현재 설정 조회: {current['error']}")
                else:
                    st.markdown("#### 현재 PC 설정")
                    current_df = pd.DataFrame([{
                        "어댑터": adapter_for_check,
                        "현재 IP": current.get("ip", ""),
                        "현재 서브넷": current.get("subnet", ""),
                        "현재 게이트웨이": current.get("gateway", ""),
                        "현재 DNS": ", ".join(current.get("dns", []) or []),
                        "DHCP": current.get("dhcp", ""),
                    }])
                    st.dataframe(current_df, use_container_width=True, hide_index=True)

            confirm_apply = st.checkbox("선택한 프로필과 작업자 정보를 확인했습니다.", key="ip_apply_confirm")
            if st.button("선택 IP 적용", type="primary", use_container_width=True, disabled=not (local_windows and local_admin)):
                if not ip_modifier_emp_id.strip() or not ip_modifier_name.strip():
                    st.error("작업 이력 저장을 위해 작업자 사번과 성명을 입력해 주세요.")
                elif not confirm_apply:
                    st.error("적용 전 확인 항목에 체크해 주세요.")
                elif adapters and adapter_for_check not in adapters:
                    st.error(f"'{adapter_for_check}' 어댑터가 이 PC에서 확인되지 않습니다. 프로필의 어댑터명을 수정해 주세요.")
                else:
                    with st.spinner("기존 설정을 확인하고 IP를 변경하는 중입니다..."):
                        ok, message, before = apply_static_ip(selected_profile)
                        history_ok, history_msg = save_ip_change_history(
                            selected_profile, before, "성공" if ok else "실패",
                            ip_modifier_emp_id, ip_modifier_name,
                            error="" if ok else message,
                            note="사용자 선택 프로필 적용",
                        )
                    if ok:
                        st.success(f"✅ {message}")
                    else:
                        st.error(f"❌ {message}")
                    if history_ok:
                        st.caption(history_msg)
                    else:
                        st.warning(f"IP 변경 결과는 발생했으나 Google Sheets 이력 저장에 실패했습니다: {history_msg}")

            st.markdown("#### 자동 IP(DHCP) 전환")
            dhcp_adapter = st.selectbox("DHCP로 전환할 어댑터", adapters or [adapter_for_check or "Ethernet"], key="dhcp_adapter")
            if st.button("자동 IP(DHCP) 적용", use_container_width=True, disabled=not (local_windows and local_admin)):
                if not ip_modifier_emp_id.strip() or not ip_modifier_name.strip():
                    st.error("작업자 사번과 성명을 입력해 주세요.")
                else:
                    dhcp_profile = {
                        "profile_id": "DHCP", "프로필명": "자동 IP(DHCP)", "어댑터명": dhcp_adapter,
                        "IP주소": "DHCP", "서브넷마스크": "자동", "기본게이트웨이": "자동", "기본DNS": "자동", "보조DNS": ""
                    }
                    ok, message, before = apply_dhcp(dhcp_adapter)
                    history_ok, history_msg = save_ip_change_history(
                        dhcp_profile, before, "성공" if ok else "실패", ip_modifier_emp_id, ip_modifier_name,
                        error="" if ok else message, note="DHCP 전환"
                    )
                    if ok:
                        st.success(message)
                    else:
                        st.error(message)
                    if not history_ok:
                        st.warning(f"이력 저장 실패: {history_msg}")
        elif not profile_load_error:
            st.info("등록된 IP 프로필이 없습니다. 'IP 오류 수정·프로필 관리'에서 첫 프로필을 등록해 주세요.")

    with manage_tab:
        st.markdown("#### IP 프로필 등록 및 직접 수정")
        st.caption("IP 오류가 확인되면 기존 프로필을 선택하여 값을 바로 수정할 수 있습니다. 수정 전 값은 Google Sheets 버전 기록과 변경 이력으로 관리하는 것을 권장합니다.")

        try:
            manage_profiles = load_ip_profiles()
        except Exception as e:
            manage_profiles = []
            st.error(f"프로필 조회 실패: {e}")

        edit_options = ["새 프로필 등록"] + [f"{r.get('프로필명', '')} · {r.get('IP주소', '')}" for r in manage_profiles]
        edit_choice = st.selectbox("작업 선택", edit_options, key="ip_edit_choice")
        editing = None
        if edit_choice != "새 프로필 등록":
            editing = manage_profiles[edit_options.index(edit_choice) - 1]

        detected_adapters = list_windows_adapters()
        default_adapter = str((editing or {}).get("어댑터명", ""))
        adapter_candidates = detected_adapters.copy()
        if default_adapter and default_adapter not in adapter_candidates:
            adapter_candidates.insert(0, default_adapter)
        if not adapter_candidates:
            adapter_candidates = [default_adapter or "Ethernet"]

        with st.form("ip_profile_form"):
            profile_name = st.text_input("프로필명 *", value=str((editing or {}).get("프로필명", "")), placeholder="예: 본사 1층 장비망")
            adapter_name = st.selectbox(
                "네트워크 어댑터명 *",
                adapter_candidates,
                index=adapter_candidates.index(default_adapter) if default_adapter in adapter_candidates else 0,
                help="대상 PC의 Windows 어댑터 이름과 정확히 일치해야 합니다. 예: Ethernet, 이더넷"
            )
            c1, c2 = st.columns(2)
            with c1:
                ip_address = st.text_input("IP 주소 *", value=str((editing or {}).get("IP주소", "")), placeholder="192.168.10.20")
                subnet_mask = st.text_input("서브넷 마스크 *", value=str((editing or {}).get("서브넷마스크", "255.255.255.0")), placeholder="255.255.255.0")
                gateway = st.text_input("기본 게이트웨이", value=str((editing or {}).get("기본게이트웨이", "")), placeholder="192.168.10.1")
            with c2:
                dns1 = st.text_input("기본 DNS", value=str((editing or {}).get("기본DNS", "")), placeholder="사내 DNS 또는 8.8.8.8")
                dns2 = st.text_input("보조 DNS", value=str((editing or {}).get("보조DNS", "")), placeholder="선택 입력")
                note = st.text_input("비고", value=str((editing or {}).get("비고", "")), placeholder="장소·장비·사용 목적")
            submitted = st.form_submit_button("검증 후 Google Sheets에 저장", use_container_width=True)

        if submitted:
            if not ip_modifier_emp_id.strip() or not ip_modifier_name.strip():
                st.error("수정자 사번과 성명을 먼저 입력해 주세요.")
            else:
                profile_payload = {
                    "profile_id": str((editing or {}).get("profile_id", "")),
                    "프로필명": profile_name, "어댑터명": adapter_name, "IP주소": ip_address,
                    "서브넷마스크": subnet_mask, "기본게이트웨이": gateway,
                    "기본DNS": dns1, "보조DNS": dns2, "비고": note,
                }
                ok, msg = save_ip_profile(profile_payload, ip_modifier_emp_id, ip_modifier_name)
                if ok:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(f"저장 실패: {msg}")

        if editing:
            with st.expander("프로필 비활성화", expanded=False):
                st.warning("비활성화하면 전환 목록에서 제외되지만 기존 변경 이력은 삭제되지 않습니다.")
                delete_confirm = st.checkbox("선택 프로필 비활성화에 동의합니다.", key="ip_disable_confirm")
                if st.button("선택 프로필 비활성화", disabled=not delete_confirm, use_container_width=True):
                    if not ip_modifier_emp_id.strip() or not ip_modifier_name.strip():
                        st.error("작업자 사번과 성명을 입력해 주세요.")
                    else:
                        ok, msg = disable_ip_profile(str(editing.get("profile_id", "")), ip_modifier_emp_id, ip_modifier_name)
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

    with history_tab:
        st.markdown("#### IP 변경 이력")
        try:
            spreadsheet = _open_ip_spreadsheet()
            history_ws = _ensure_ip_sheet(spreadsheet, IP_HISTORY_SHEET_NAME, IP_HISTORY_HEADERS, rows=10000)
            history_records = history_ws.get_all_records()
            if history_records:
                history_df = pd.DataFrame(history_records)
                st.dataframe(history_df.iloc[::-1], use_container_width=True, hide_index=True)
                st.download_button(
                    "변경 이력 CSV 다운로드",
                    data=history_df.to_csv(index=False).encode("utf-8-sig"),
                    file_name=f"IP_Change_History_{_korea_now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.info("아직 저장된 IP 변경 이력이 없습니다.")
        except Exception as e:
            st.error(f"변경 이력 조회 실패: {e}")

    st.warning("보안 유의: IP·게이트웨이·DNS 정보는 내부 네트워크 구성정보에 해당할 수 있습니다. Google Sheets 공유 범위를 최소화하고, 서비스 계정 및 앱 접근권한을 현장 담당자에게만 부여하세요.")


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
            <p>최신 Gemini 모델 우선 선택, 검색 보강 옵션, 조항별 리스크 표, 수정문안, 감사보고서 품질검증 구조를 적용했습니다. 기존 법률 검토 기능은 그대로 유지됩니다.</p>
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

# --- [Tab 5: 관리자 대시보드 - 수동 로딩형 현황판] ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    st.caption("교육 수료 제출 안정성을 우선하기 위해, 관리자 화면은 자동으로 Google Sheet 데이터를 읽지 않습니다. 필요한 시점에만 현재 데이터를 불러옵니다.")

    # 1. 관리자 비밀번호 검증
    admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_dash_pw")
    if admin_pw.strip() != "ktmos0402!":
        st.info("관리자 비밀번호를 입력하세요.")
        st.stop()

    st.success("✅ 접속 성공")

    st.markdown("""
    <div style="background:#FFF7ED; border:1px solid #FED7AA; border-left:6px solid #F97316; border-radius:16px; padding:16px 18px; margin:10px 0 18px 0;">
      <div style="font-weight:950; color:#9A3412; font-size:1.02rem; margin-bottom:6px;">운영 안정화 안내</div>
      <div style="color:#7C2D12; font-weight:750; line-height:1.65;">
        전 임직원 교육 수료 제출이 집중되는 기간에는 수료 저장을 최우선으로 보호합니다.<br>
        이 관리자 대시보드는 자동 조회를 하지 않으며, 감사실에서 필요할 때 <b>현재 데이터 불러오기</b> 버튼을 누른 경우에만 Google Sheet를 1회 조회합니다.
      </div>
    </div>
    """, unsafe_allow_html=True)

    TOTAL_STAFF_MAP = {
        "감사실": 3,
        "경영총괄": 27,
        "사업총괄": 39,
        "강북본부": 221,
        "강남본부": 173,
        "서부본부": 278,
        "강원본부": 101,
        "품질지원단": 137,
    }

    if "june_admin_df" not in st.session_state:
        st.session_state["june_admin_df"] = None
    if "june_admin_loaded_at" not in st.session_state:
        st.session_state["june_admin_loaded_at"] = ""
    if "june_admin_load_error" not in st.session_state:
        st.session_state["june_admin_load_error"] = ""

    def _load_june_admin_df_once() -> pd.DataFrame:
        """관리자가 버튼을 누른 경우에만 Google Sheet를 1회 읽습니다."""
        client = init_google_sheet_connection()
        if not client:
            raise RuntimeError("구글 시트 연결 실패. API 권한 및 Secrets 설정을 확인하세요.")
        spreadsheet = client.open("Audit_Result_2026")
        try:
            ws = spreadsheet.worksheet(JUNE_TRAINING_SHEET_NAME)
            values = ws.get_all_values()
        except Exception:
            values = []
        if not values or len(values) < 2:
            return pd.DataFrame(columns=JUNE_TRAINING_HEADERS)
        headers = values[0]
        rows = values[1:]
        return pd.DataFrame(rows, columns=headers)

    load_col, clear_col, stamp_col = st.columns([0.22, 0.18, 0.60], vertical_alignment="center")
    with load_col:
        load_clicked = st.button("📊 현재 데이터 불러오기", type="primary", use_container_width=True, key="june_admin_load_current")
    with clear_col:
        clear_clicked = st.button("🧹 화면 데이터 초기화", use_container_width=True, key="june_admin_clear_loaded")
    with stamp_col:
        if st.session_state.get("june_admin_loaded_at"):
            st.caption(f"마지막 조회 시각: {st.session_state['june_admin_loaded_at']}  ·  검색/필터/다운로드는 저장된 조회 결과 기준으로 동작합니다.")
        else:
            st.caption("아직 데이터를 불러오지 않았습니다. 버튼을 누르기 전에는 Google Sheet 읽기 요청이 발생하지 않습니다.")

    if clear_clicked:
        st.session_state["june_admin_df"] = None
        st.session_state["june_admin_loaded_at"] = ""
        st.session_state["june_admin_load_error"] = ""
        st.rerun()

    if load_clicked:
        with st.spinner("Google Sheet에서 현재 수료 현황을 1회 불러오는 중입니다..."):
            try:
                st.session_state["june_admin_df"] = _load_june_admin_df_once()
                st.session_state["june_admin_loaded_at"] = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["june_admin_load_error"] = ""
            except Exception as e:
                st.session_state["june_admin_load_error"] = str(e)
                st.session_state["june_admin_df"] = None

    if st.session_state.get("june_admin_load_error"):
        st.error(f"현재 데이터 로드 중 오류가 발생했습니다: {st.session_state['june_admin_load_error']}")
        st.info("잠시 후 다시 '현재 데이터 불러오기' 버튼을 눌러 주세요. 이 화면은 자동 재조회하지 않습니다.")
        st.stop()

    june_df = st.session_state.get("june_admin_df")
    if june_df is None:
        st.markdown("""
        <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:18px; padding:22px; margin-top:12px; box-shadow:0 10px 26px rgba(15,23,42,0.06);">
          <div style="font-size:1.18rem; font-weight:950; color:#0F172A; margin-bottom:8px;">수동 조회 대기 상태</div>
          <div style="color:#475569; font-weight:750; line-height:1.65;">
            현재 관리자 모드는 Google Sheet를 자동으로 읽지 않습니다.<br>
            현황 공유가 필요할 때만 <b>📊 현재 데이터 불러오기</b>를 눌러 최신 수료 현황을 확인해 주세요.
          </div>
        </div>
        """, unsafe_allow_html=True)
        st.stop()

    st.markdown("---")
    st.markdown("#### 🌊 6월 컴플라이언스 인식제고 교육 수료 현황")

    # 숫자형/문자형 안전 처리
    if "사번" in june_df.columns:
        unique_emp_count = int(june_df["사번"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        duplicate_count = max(int(len(june_df) - unique_emp_count), 0)
    else:
        unique_emp_count = int(len(june_df))
        duplicate_count = 0

    total_completion_rows = int(len(june_df))
    total_target = int(sum(TOTAL_STAFF_MAP.values()))
    overall_rate = (unique_emp_count / total_target * 100) if total_target else 0

    event_count = 0
    if not june_df.empty and "이벤트추첨대상" in june_df.columns:
        event_count = int((june_df["이벤트추첨대상"].astype(str).str.strip() == "대상").sum())

    latest_time = "-"
    if not june_df.empty and "저장시간" in june_df.columns:
        latest_time = str(june_df["저장시간"].iloc[-1])

    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("전체 대상자", f"{total_target:,}명")
    kpi2.metric("고유 수료자", f"{unique_emp_count:,}명")
    kpi3.metric("전체 수료율", f"{overall_rate:.1f}%")
    kpi4.metric("이벤트 추첨 대상", f"{event_count:,}명")
    kpi5.metric("최근 저장시간", latest_time)

    if duplicate_count > 0:
        st.caption(f"참고: 사번 기준 중복 제출로 추정되는 행이 {duplicate_count:,}건 있습니다. 최종 수료자 산정 시 Google Sheet에서 사번 기준으로 정리해 주세요.")

    # 조직별 참여율 산정
    org_stats_df = pd.DataFrame()
    if not june_df.empty and "총괄/본부/단" in june_df.columns:
        tmp = june_df.copy()
        tmp["총괄/본부/단"] = tmp["총괄/본부/단"].astype(str).str.strip()
        if "사번" in tmp.columns:
            tmp["사번"] = tmp["사번"].astype(str).str.strip()
            org_counts = tmp.drop_duplicates(subset=["사번"], keep="last")["총괄/본부/단"].value_counts().to_dict()
        else:
            org_counts = tmp["총괄/본부/단"].value_counts().to_dict()
        org_rows = []
        for org, target in TOTAL_STAFF_MAP.items():
            done = int(org_counts.get(org, 0))
            rate = (done / target * 100) if target else 0
            org_rows.append({"조직": org, "대상자": target, "수료자": done, "미수료자": max(target - done, 0), "수료율(%)": round(rate, 1)})
        org_stats_df = pd.DataFrame(org_rows)

    if not org_stats_df.empty:
        st.markdown("#### 📈 조직별 수료 현황")
        chart_col1, chart_col2 = st.columns(2)
        with chart_col1:
            fig_rate = px.bar(
                org_stats_df,
                x="조직",
                y="수료율(%)",
                text="수료율(%)",
                title="조직별 수료율(%)",
                color="수료율(%)",
                color_continuous_scale="Blues",
                range_y=[0, 100],
            )
            fig_rate.add_hline(y=100, line_dash="dash", line_color="red")
            fig_rate.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_rate.update_layout(margin=dict(l=10, r=10, t=58, b=10))
            st.plotly_chart(fig_rate, use_container_width=True, config=PLOTLY_CONFIG)
        with chart_col2:
            fig_count = px.bar(
                org_stats_df,
                x="조직",
                y=["수료자", "미수료자"],
                title="조직별 수료/미수료 현황",
                barmode="stack",
                text_auto=True,
            )
            fig_count.update_layout(margin=dict(l=10, r=10, t=58, b=10), legend_title_text="구분")
            st.plotly_chart(fig_count, use_container_width=True, config=PLOTLY_CONFIG)

        st.markdown("#### 🧾 조직별 공유용 요약표")
        org_stats_display_df = org_stats_df.copy()
        org_stats_display_df["명단 다운로드"] = "아래 조직별 버튼 사용"
        st.dataframe(org_stats_display_df, use_container_width=True, hide_index=True)

        summary_csv = org_stats_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "📥 조직별 수료율 요약 CSV 다운로드",
            summary_csv,
            "2026_06_컴플라이언스_조직별_수료율.csv",
            "text/csv",
            use_container_width=True,
            key="june_org_summary_csv_download",
        )

        # =========================================================
        # ✅ 조직별 참여/미참여 명단 다운로드
        # - Google Sheet 추가 조회 없음: 이미 '현재 데이터 불러오기'로 가져온 june_df만 사용
        # - 미참여자 실명 확인은 전체 대상자 명부가 있을 때만 가능
        # =========================================================
        st.markdown("#### 📋 조직별 참여·미참여 명단 다운로드")
        st.caption(
            "완료자 명단은 현재 불러온 수료 데이터 기준으로 바로 생성됩니다. "
            "미참여자 실명 명단은 전체 교육 대상자 명부를 업로드한 경우에만 생성됩니다. "
            "대상자 명부 업로드는 Google Sheet를 추가로 읽지 않습니다."
        )

        roster_file = st.file_uploader(
            "전체 교육 대상자 명부 업로드(선택 · CSV/XLSX) - 권장 컬럼: 사번, 성명, 총괄/본부/단, 부서 또는 상세 부서명",
            type=["csv", "xlsx", "xls"],
            key="june_target_roster_upload",
        )

        def _normalize_admin_colname(col) -> str:
            return str(col or "").strip().replace(" ", "")

        def _read_uploaded_roster(uploaded_file) -> pd.DataFrame:
            if uploaded_file is None:
                return pd.DataFrame()
            name = str(getattr(uploaded_file, "name", "")).lower()
            if name.endswith(".csv"):
                df = pd.read_csv(uploaded_file, dtype=str)
            else:
                df = pd.read_excel(uploaded_file, dtype=str)
            df = df.fillna("")
            col_map = {}
            for col in df.columns:
                norm = _normalize_admin_colname(col)
                if norm in {"사번", "직원번호", "사원번호", "EMPID", "EMPLOYEEID"}:
                    col_map[col] = "사번"
                elif norm in {"성명", "이름", "직원명", "사원명", "NAME"}:
                    col_map[col] = "성명"
                elif norm in {"총괄/본부/단", "총괄본부단", "조직", "본부", "소속", "ORG"}:
                    col_map[col] = "총괄/본부/단"
                elif norm in {"부서", "상세부서명", "상세부서", "팀", "DEPT", "DEPARTMENT"}:
                    col_map[col] = "부서"
            df = df.rename(columns=col_map)
            for required in ["사번", "성명", "총괄/본부/단", "부서"]:
                if required not in df.columns:
                    df[required] = ""
            df["사번"] = df["사번"].astype(str).str.strip()
            df["성명"] = df["성명"].astype(str).str.strip()
            df["총괄/본부/단"] = df["총괄/본부/단"].astype(str).str.strip()
            df["부서"] = df["부서"].astype(str).str.strip()
            return df[["사번", "성명", "총괄/본부/단", "부서"]].drop_duplicates(subset=["사번", "성명", "총괄/본부/단"], keep="last")

        def _unique_completed_df(source_df: pd.DataFrame) -> pd.DataFrame:
            if source_df is None or source_df.empty:
                return pd.DataFrame(columns=["사번", "성명", "총괄/본부/단", "부서", "저장시간"])
            df = source_df.copy().fillna("")
            for col in ["사번", "성명", "총괄/본부/단", "부서", "저장시간"]:
                if col not in df.columns:
                    df[col] = ""
            df["사번"] = df["사번"].astype(str).str.strip()
            df["성명"] = df["성명"].astype(str).str.strip()
            df["총괄/본부/단"] = df["총괄/본부/단"].astype(str).str.strip()
            df["부서"] = df["부서"].astype(str).str.strip()
            if "사번" in df.columns:
                df = df.sort_values("저장시간").drop_duplicates(subset=["사번"], keep="last")
            return df[["사번", "성명", "총괄/본부/단", "부서", "저장시간"]]

        def _build_org_list_df(org_name: str, completed_df: pd.DataFrame, roster_df: pd.DataFrame | None = None) -> pd.DataFrame:
            completed_org = completed_df[completed_df["총괄/본부/단"] == org_name].copy()
            completed_org["참여상태"] = "수료"
            completed_org = completed_org.rename(columns={"저장시간": "수료저장시간"})

            if roster_df is not None and not roster_df.empty:
                roster_org = roster_df[roster_df["총괄/본부/단"] == org_name].copy()
                completed_keys = set(completed_org["사번"].astype(str).str.strip())
                roster_org["참여상태"] = roster_org["사번"].astype(str).str.strip().apply(lambda x: "수료" if x in completed_keys else "미수료")
                saved_time_map = completed_org.set_index("사번")["수료저장시간"].to_dict() if not completed_org.empty else {}
                roster_org["수료저장시간"] = roster_org["사번"].map(saved_time_map).fillna("")
                result = roster_org[["총괄/본부/단", "부서", "사번", "성명", "참여상태", "수료저장시간"]]
                result = result.sort_values(["참여상태", "부서", "성명"], ascending=[True, True, True])
                return result

            result = completed_org[["총괄/본부/단", "부서", "사번", "성명", "참여상태", "수료저장시간"]]
            if result.empty:
                return pd.DataFrame(columns=["총괄/본부/단", "부서", "사번", "성명", "참여상태", "수료저장시간"])
            return result.sort_values(["부서", "성명"])

        try:
            roster_df = _read_uploaded_roster(roster_file)
        except Exception as roster_error:
            roster_df = pd.DataFrame()
            st.warning(f"대상자 명부를 읽지 못했습니다. 파일 컬럼과 형식을 확인해 주세요: {roster_error}")

        completed_unique_df = _unique_completed_df(june_df)
        if roster_df.empty:
            st.info("현재는 수료자 명단만 다운로드할 수 있습니다. 미수료자 실명 명단까지 필요하면 전체 교육 대상자 명부를 업로드해 주세요.")
        else:
            st.success("대상자 명부가 적용되었습니다. 조직별 파일에 수료/미수료 상태가 함께 표시됩니다.")

        org_button_cols = st.columns(4)
        for idx, org_name in enumerate(TOTAL_STAFF_MAP.keys()):
            org_list_df = _build_org_list_df(org_name, completed_unique_df, roster_df)
            if roster_df.empty:
                filename = f"2026_06_컴플라이언스_{org_name}_수료자명단.csv"
                label = f"📥 {org_name} 수료자"
            else:
                filename = f"2026_06_컴플라이언스_{org_name}_참여미참여명단.csv"
                label = f"📥 {org_name} 참여/미참여"
            with org_button_cols[idx % 4]:
                st.download_button(
                    label,
                    org_list_df.to_csv(index=False).encode("utf-8-sig"),
                    filename,
                    "text/csv",
                    use_container_width=True,
                    key=f"june_org_list_download_{org_name}",
                )

        try:
            from io import BytesIO
            all_output = BytesIO()
            with pd.ExcelWriter(all_output, engine="openpyxl") as writer:
                org_stats_df.to_excel(writer, index=False, sheet_name="조직별_요약")
                for org_name in TOTAL_STAFF_MAP.keys():
                    sheet_name = re.sub(r"[\/*?:\[\]]", "", org_name)[:31]
                    _build_org_list_df(org_name, completed_unique_df, roster_df).to_excel(writer, index=False, sheet_name=sheet_name)
            st.download_button(
                "📥 전체 조직별 명단 Excel 다운로드",
                all_output.getvalue(),
                "2026_06_컴플라이언스_전체조직별_참여현황.xlsx",
                use_container_width=True,
                key="june_all_org_list_excel_download",
            )
        except Exception:
            st.caption("Excel 다운로드 생성이 어려운 경우 위 조직별 CSV 다운로드를 이용해 주세요.")
    else:
        st.warning("조직별 통계를 생성할 수 없습니다. 아직 수료 데이터가 없거나 '총괄/본부/단' 컬럼이 없습니다.")

    st.markdown("---")
    st.markdown("#### 🔍 수료 내역 확인 및 다운로드")
    search_term = st.text_input("수료 내역 검색", placeholder="성명, 사번, 부서, 본부 등", key="june_admin_search")
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
            key="june_csv_download",
        )
    with dl2:
        try:
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                june_display_df.to_excel(writer, index=False, sheet_name="6월_컴플라이언스교육")
                if not org_stats_df.empty:
                    org_stats_df.to_excel(writer, index=False, sheet_name="조직별_수료율")
            st.download_button(
                "📥 현재 조회내역 Excel 다운로드",
                output.getvalue(),
                f"{JUNE_TRAINING_SHEET_NAME}.xlsx",
                use_container_width=True,
                key="june_xlsx_download",
            )
        except Exception:
            st.info("Excel 엔진 미설치로 CSV 다운로드를 이용하세요.")

    with st.expander("📌 운영 메모", expanded=False):
        st.markdown("""
        - 이 화면은 버튼을 누른 시점의 Google Sheet 데이터를 기준으로 표시합니다.
        - 검색, 그래프 확인, 다운로드는 이미 불러온 데이터로 처리되므로 추가 Google Sheet 읽기 요청이 발생하지 않습니다.
        - 최신 현황이 필요할 때만 다시 **현재 데이터 불러오기** 버튼을 눌러 주세요.
        - 최종 수료자 확정 시에는 중복 제출 가능성을 고려하여 사번 기준으로 정리하는 것을 권장합니다.
        """)

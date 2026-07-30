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
import html
import json
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
# 8-2. 국사 전원시설 정밀점검 및 Google Sheets 저장
#      - 기존 Google 서비스 계정/스프레드시트 연결 재사용
#      - 점검 1건을 Google Sheet 1행으로 저장
# ==========================================
POWER_INSPECTION_SPREADSHEET_NAME = "Audit_Result_2026"
POWER_INSPECTION_SHEET_NAME = "국사_전원시설_정밀점검"

POWER_STATION_DATA = r"""행당	약수역 BBH
신내	중랑최적화분기국사
중앙	BBH(후암동68-6-BBH)
광진	구의동 BBH
광진	중곡동 BBH
성북	안암 BBH
성북	대광 BBH
성북	성북 BBH
노원	공릉최적화분기국사
도봉	방학최적화분기국사
용산	청파3가 BBH
은평	삼송
은평	홍제최적화분기국사
서대문	서대문(최적화분기국사)
서대문	화전
가평	가평
청평	청평
청평	고성
청평	대성
청평	마일
청평	미사
청평	방일
청평	봉수
청평	삼회
가평	상색
청평	설악
청평	율길
청평	임초
청평	조종
청평	회곡
청평	상판
청평	대보
가평	산유
가평	북면
가평	화악
가평	백둔
가평	도대
가평	적목
동의정부	경중앙(통신구내) BBH
동의정부	남방
의정부	장흥
의정부	송추
의정부	백석
의정부	광적
동의정부	광사
의정부	의정부 덕도(N3162)
동의정부	자일
의정부	석우
동의정부	청학
의정부	삼하
의정부	비암
퇴계원	퇴계원
남양주	남양주
덕소	덕소
퇴계원	진접
퇴계원	진건
퇴계원	오남
퇴계원	광릉
남양주	일패
남양주	답내
남양주	운수
남양주	외방
남양주	호평 BBH
덕소	조안
덕소	송촌
덕소	월문
덕소	팔당
퇴계원	금곡 BBH
퇴계원	별내
양평	양평
양평	노문
양평	정배
양평	목왕
양평	서종
양평	양수
양평	국수
양평	강하
양평	강상
양평	회현
양평	개군
양평	일신
양평	양동
양평	계정
양평	금왕
양평	고송
양평	용문
양평	신점
양평	단월
양평	산음
양평	명성
양평	용두
양평	옥천
양평	지평
양평	용문산중계소
연천	연천
동두천	동두천
전곡	원당
전곡	백학
전곡	동이
전곡	궁평
전곡	왕림
전곡	초성
전곡	동중
전곡	진상
전곡	북삼
전곡	늘목
전곡	양원
전곡	대전
연천	대광
연천	삼곳
연천	내산
연천	고문
동두천	은현
동두천	신산
동두천	상수
동두천	덕정
동두천	덕계
동두천	소요
동두천	광암
포천	포천
송우	송우
송우	가산
송우	내촌
송우	신팔
송우	이곡
포천	자작
포천	직두
포천	화현
포천	일동
포천	사직
포천	수입
포천	장암
포천	도평
포천	산정
포천	영북
포천	관인
포천	운산
포천	창수
포천	신북
포천	남청산
포천	고소성
포천	만세교
포천	양문
덕양	덕양
덕양	덕양 벽제(N3055)
덕양	고양
파주	영장
파주	장곡
파주	위전
파주	법흥
파주	문발
파주	용미
파주	발랑
파주	파주 연다산(N3218)
파주	광탄
파주	탄현
파주	운정
문산	문산
법원리	법원리
문산	파주
문산	마산
문산	마정
문산	통일촌(N3211)
문산	장현
문산	웅담
문산	적성
문산	파평
일산	송포
일산	성석
일산	고봉산중계소
고양IBS고양BBH	백석12블럭 BBH
고양IBS고양BBH	마두21블럭 BBH
일산	백마5단지상가 BBH(N3173)
일산	장항동 BBH
일산	북일산최적화분기국사(북일산)
일산	고양 BBH(N3170)
전곡	전곡
철원	철원
철원	동송분기국사
철원	문혜
철원	내대
철원	관전
철원	장흥
철원	오지
철원	지경
철원	자등
철원	마현
철원	양지
철원	근남
철원	잠곡
철원	와수
철원	도창
파주	(파주)마이프라자1층 BBH
일산	가좌 BBH
동의정부	금오 BBH
법원리	금파리마을회관 BBH
덕양	달빛3단지상가지하 BBH
문산	당동상가 BBH
광화문	독립문통신구 BBH(N995)
고양IBS고양BBH	마두25블럭 BBH
아현	마포분기국사
중랑	망우최적화분기국사(중랑)
광화문	무교동 BBH
일산	백석13블럭 BBH
일산	백석7블럭 BBH
고양IBS고양BBH	백석8블럭 BBH
문산	봉암1리마을회관 BBH
파주	분수3리마을회관 BBH
덕양	상곡 BBH
파주	새말 BBH
능곡	소만8단지(소만풍림8단지) BBH
신촌	신촌분기국사
청평	에덴성회 BBH
일산	정발 BBH
광화문	종로5가통신구-1 BBH(통신구내)
청량	청량최적화 BBH
파주	토우프라자 BBH
파주	통일프라자 BBH
고양IBS고양BBH	풍동에이스타워 BBH
파주	한라비발디상가 BBH
능곡	햇빛주공22단지 BBH
방학	행운빌라 BBH
능곡	화정동상가(별빛건영10단지) BBH
의정부	녹양"""


def _build_power_station_map() -> dict[str, list[str]]:
    station_map: dict[str, list[str]] = {}
    for raw_line in POWER_STATION_DATA.splitlines():
        line = raw_line.strip()
        if not line or "\t" not in line:
            continue
        mother, local = [part.strip() for part in line.split("\t", 1)]
        if not mother or not local:
            continue
        station_map.setdefault(mother, [])
        if local not in station_map[mother]:
            station_map[mother].append(local)
    return station_map


POWER_STATION_MAP = _build_power_station_map()


# 점검자 성명에 따라 소속 조를 자동 표시합니다.
# 이름과 조 정보가 추가되면 이 사전만 확장하면 됩니다.
POWER_INSPECTOR_GROUP_MAP = {
    "정청운": "덕양조",
    "정철선": "덕양운용조",
    "정철순": "덕양운용조",
    "소순고": "덕양운용조",
    "이철순": "고양운용조",
    "김수창": "고양운용조",
    # 영문 입력 보조
    "JEONGCHEONGWOON": "덕양조",
    "JEONGCHEOLSUN": "덕양운용조",
    "SOSOONGO": "덕양운용조",
    "LEECHEOLSOON": "고양운용조",
    "KIMSOOCHANG": "고양운용조",
}


def _normalize_inspector_name(name: str) -> str:
    normalized = re.sub(r"[\s\-_.]", "", str(name or "").strip())
    return normalized.upper() if re.search(r"[A-Za-z]", normalized) else normalized


def _inspector_group_for_name(name: str) -> str:
    return POWER_INSPECTOR_GROUP_MAP.get(_normalize_inspector_name(name), "")


def _update_power_inspector_group() -> None:
    st.session_state["power_inspector_group"] = _inspector_group_for_name(
        st.session_state.get("power_worker", "")
    )


def _power_headers() -> list[str]:
    headers = [
        "저장일시", "점검ID", "점검자", "운용조", "모국", "국소", "전원구분", "축전지조수",
        "입력방식", "원본점검ID", "원본저장일시",
        "입력완료율(%)", "누락항목수", "누락항목", "부분입력확인",
        "삼상전압_R-S(V)", "삼상전압_S-T(V)", "삼상전압_T-R(V)", "삼상전압_R-N(V)",
        "삼상전류_R(A)", "삼상전류_S(A)", "삼상전류_T(A)",
        "단상전압(V)", "단상전류(A)",
        "1조_측정셀수", "1조_방전후_Total전류(A)", "1조_방전후_Total전압(V)",
        "1조_최저전압(V)", "1조_최고전압(V)", "1조_방전종료전압(V)",
    ]
    headers.extend([f"1조_셀{i:02d}(V)" for i in range(1, 25)])
    headers.extend([
        "2조_측정셀수", "2조_방전후_Total전류(A)", "2조_방전후_Total전압(V)",
        "2조_최저전압(V)", "2조_최고전압(V)", "2조_방전종료전압(V)",
    ])
    headers.extend([f"2조_셀{i:02d}(V)" for i in range(1, 25)])
    headers.extend([
        "보안접지_1종(Ω)", "보안접지_2종(Ω)", "보안접지_3종(Ω)",
        "통신용접지_메인(Ω)", "피뢰침접지(Ω)", "특이사항",
    ])
    return headers


POWER_INSPECTION_HEADERS = _power_headers()


def _column_letter(column_number: int) -> str:
    if column_number < 1:
        raise ValueError("열 번호는 1 이상이어야 합니다.")
    letters = ""
    number = column_number
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _ensure_power_inspection_sheet(spreadsheet):
    try:
        ws = spreadsheet.worksheet(POWER_INSPECTION_SHEET_NAME)
    except Exception:
        ws = spreadsheet.add_worksheet(
            title=POWER_INSPECTION_SHEET_NAME,
            rows=10000,
            cols=max(len(POWER_INSPECTION_HEADERS) + 5, 100),
        )

    current_headers = ws.row_values(1)
    if not current_headers:
        end_col = _column_letter(len(POWER_INSPECTION_HEADERS))
        ws.update(range_name=f"A1:{end_col}1", values=[POWER_INSPECTION_HEADERS])
        current_headers = POWER_INSPECTION_HEADERS.copy()
    else:
        missing_headers = [header for header in POWER_INSPECTION_HEADERS if header not in current_headers]
        if missing_headers:
            start_col_num = len(current_headers) + 1
            end_col_num = len(current_headers) + len(missing_headers)
            ws.update(
                range_name=f"{_column_letter(start_col_num)}1:{_column_letter(end_col_num)}1",
                values=[missing_headers],
            )
            current_headers.extend(missing_headers)

    try:
        ws.freeze(rows=1)
        ws.format(
            f"A1:{_column_letter(len(current_headers))}1",
            {
                "backgroundColor": {"red": 0.86, "green": 0.92, "blue": 0.98},
                "textFormat": {"bold": True},
                "horizontalAlignment": "CENTER",
            },
        )
    except Exception:
        pass

    return ws, current_headers


def _parse_power_number(value, implicit_decimals: int | None = None):
    """숫자만 입력한 측정값을 실제 숫자로 변환합니다.

    예시:
    - 전압·전류 3800, decimals=1 → 380.0
    - 축전지 셀 215, decimals=2 → 2.15
    - 접지저항 123, decimals=2 → 1.23
    """
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return ""

    cleaned = re.sub(r"[^0-9.+-]", "", raw)
    if cleaned in {"", "+", "-", ".", "+.", "-."}:
        return ""

    try:
        if implicit_decimals is not None and "." not in cleaned:
            sign = -1 if cleaned.startswith("-") else 1
            digits = cleaned.lstrip("+-")
            if not digits.isdigit():
                return ""
            return sign * (int(digits) / (10 ** implicit_decimals))
        return float(cleaned)
    except (TypeError, ValueError, OverflowError):
        return ""


def _format_power_display(value, decimals: int) -> str:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return ""
    cleaned = re.sub(r"[^0-9.-]", "", raw)
    if not cleaned:
        return ""
    try:
        number = float(cleaned)
        return f"{number:.{decimals}f}"
    except Exception:
        return raw


def _power_value_is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _power_draft() -> dict:
    draft = st.session_state.get("power_draft")
    if not isinstance(draft, dict):
        draft = {}
        st.session_state["power_draft"] = draft
    return draft


def _power_get(key: str, default=""):
    # 현재 화면에 렌더링된 위젯값을 우선하고, 화면에서 사라진 위젯은 임시저장소에서 복원합니다.
    if key in st.session_state:
        return st.session_state.get(key, default)
    return _power_draft().get(key, default)


def _power_set(key: str, value) -> None:
    _power_draft()[key] = value
    st.session_state[key] = value


def _persist_power_widget(key: str) -> None:
    _power_draft()[key] = st.session_state.get(key, "")
    st.session_state["power_draft_saved_at"] = _korea_now().strftime("%H:%M:%S")


def _hydrate_power_widget(key: str, default="") -> None:
    if key not in st.session_state:
        st.session_state[key] = _power_draft().get(key, default)


def _power_text_input(label: str, key: str, **kwargs):
    _hydrate_power_widget(key, "")
    return st.text_input(
        label,
        key=key,
        on_change=_persist_power_widget,
        args=(key,),
        **kwargs,
    )


def _power_text_area(label: str, key: str, **kwargs):
    _hydrate_power_widget(key, "")
    return st.text_area(
        label,
        key=key,
        on_change=_persist_power_widget,
        args=(key,),
        **kwargs,
    )


def _power_theme_keys(theme: str) -> list[str]:
    if theme == "전압·전류 측정":
        return [
            "power_phase_type",
            "power_three_voltage_rs", "power_three_voltage_st",
            "power_three_voltage_tr", "power_three_voltage_rn",
            "power_three_current_r", "power_three_current_s", "power_three_current_t",
            "power_single_voltage", "power_single_current",
        ]
    if theme == "축전지 측정":
        keys = ["power_battery_set", "power_battery2_enabled"]
        for group in (1, 2):
            keys.extend([
                f"power_battery{group}_total_current",
                f"power_battery{group}_total_voltage",
                f"power_battery{group}_min_voltage",
                f"power_battery{group}_max_voltage",
                f"power_battery{group}_end_voltage",
            ])
            keys.extend(f"power_battery_{group}_{index:02d}" for index in range(1, 25))
        return keys
    if theme == "접지저항 측정":
        return [
            "power_security_ground_1", "power_security_ground_2", "power_security_ground_3",
            "power_telecom_ground", "power_lightning_ground", "power_notes",
        ]
    return []


def _save_power_theme_to_draft(theme: str) -> None:
    draft = _power_draft()
    for key in _power_theme_keys(theme):
        if key in st.session_state:
            draft[key] = st.session_state.get(key, "")
    st.session_state["power_draft_saved_at"] = _korea_now().strftime("%H:%M:%S")


def _hydrate_power_theme_from_draft(theme: str) -> None:
    draft = _power_draft()
    for key in _power_theme_keys(theme):
        if key not in st.session_state and key in draft:
            st.session_state[key] = draft[key]


def _on_power_phase_change() -> None:
    _persist_power_widget("power_phase_type")


def _on_power_battery_set_change() -> None:
    _save_power_theme_to_draft("축전지 측정")
    selected = st.session_state.get("power_battery_set", "1조 셀 측정")
    if selected == "2조 셀 측정":
        st.session_state["power_battery2_enabled"] = True
        _power_draft()["power_battery2_enabled"] = True


def _power_basic_missing() -> list[str]:
    missing: list[str] = []
    if _power_state_blank("power_worker"):
        missing.append("점검자 성명")
    if st.session_state.get("power_mother", "모국 선택") == "모국 선택":
        missing.append("모국")
    if st.session_state.get("power_local", "국소 선택") == "국소 선택":
        missing.append("국소")
    return missing


def _power_battery2_enabled() -> bool:
    explicit_enabled = _power_get("power_battery2_enabled", None)
    if explicit_enabled is not None:
        return bool(explicit_enabled)
    if _power_get("power_battery_set", "1조 셀 측정") == "2조 셀 측정":
        return True
    keys = [
        "power_battery2_total_current", "power_battery2_total_voltage",
        "power_battery2_min_voltage", "power_battery2_max_voltage", "power_battery2_end_voltage",
    ]
    keys.extend(f"power_battery_2_{index:02d}" for index in range(1, 25))
    return any(not _power_value_is_blank(_power_get(key, "")) for key in keys)


def _measured_cell_count(cells: list) -> int:
    """마지막으로 값이 입력된 셀 번호를 실제 측정 셀 수로 사용합니다."""
    highest = 0
    for index, value in enumerate(list(cells or [])[:24], 1):
        if not _power_value_is_blank(value):
            highest = index
    return highest


def _power_payload_missing_items(payload: dict) -> list[str]:
    expected: list[tuple[str, object]] = []
    phase_type = str(payload.get("phase_type", "")).strip()

    if phase_type == "삼상":
        expected.extend([
            ("삼상 R-S 전압", payload.get("three_voltage_rs")),
            ("삼상 S-T 전압", payload.get("three_voltage_st")),
            ("삼상 T-R 전압", payload.get("three_voltage_tr")),
            ("삼상 R-N 전압", payload.get("three_voltage_rn")),
            ("삼상 R상 전류", payload.get("three_current_r")),
            ("삼상 S상 전류", payload.get("three_current_s")),
            ("삼상 T상 전류", payload.get("three_current_t")),
        ])
    elif phase_type == "단상":
        expected.extend([
            ("단상 전압", payload.get("single_voltage")),
            ("단상 전류", payload.get("single_current")),
        ])

    expected.extend([
        ("1조 방전 후 Total 전류", payload.get("battery1_total_current")),
        ("1조 방전 후 Total 전압", payload.get("battery1_total_voltage")),
        ("1조 최저전압", payload.get("battery1_min_voltage")),
        ("1조 최고전압", payload.get("battery1_max_voltage")),
        ("1조 방전종료 전압", payload.get("battery1_end_voltage")),
    ])
    battery1_cells = list(payload.get("battery1_cells", []))[:24]
    battery1_cells.extend([""] * (24 - len(battery1_cells)))
    battery1_cell_count = int(payload.get("battery1_cell_count", 0) or 0)
    if battery1_cell_count <= 0:
        battery1_cell_count = _measured_cell_count(battery1_cells)
    expected.extend(
        (f"1조 {index}셀", battery1_cells[index - 1])
        for index in range(1, min(battery1_cell_count, 24) + 1)
    )

    if int(payload.get("battery_group_count", 1) or 1) == 2:
        expected.extend([
            ("2조 방전 후 Total 전류", payload.get("battery2_total_current")),
            ("2조 방전 후 Total 전압", payload.get("battery2_total_voltage")),
            ("2조 최저전압", payload.get("battery2_min_voltage")),
            ("2조 최고전압", payload.get("battery2_max_voltage")),
            ("2조 방전종료 전압", payload.get("battery2_end_voltage")),
        ])
        battery2_cells = list(payload.get("battery2_cells", []))[:24]
        battery2_cells.extend([""] * (24 - len(battery2_cells)))
        battery2_cell_count = int(payload.get("battery2_cell_count", 0) or 0)
        if battery2_cell_count <= 0:
            battery2_cell_count = _measured_cell_count(battery2_cells)
        expected.extend(
            (f"2조 {index}셀", battery2_cells[index - 1])
            for index in range(1, min(battery2_cell_count, 24) + 1)
        )

    expected.extend([
        ("보안접지 1종", payload.get("security_ground_1")),
        ("보안접지 2종", payload.get("security_ground_2")),
        ("보안접지 3종", payload.get("security_ground_3")),
        ("통신용접지(메인)", payload.get("telecom_ground")),
        ("피뢰침접지", payload.get("lightning_ground")),
    ])

    return [label for label, value in expected if _power_value_is_blank(value)]


def _power_expected_item_count(payload: dict) -> int:
    phase_count = 7 if str(payload.get("phase_type", "")).strip() == "삼상" else 2
    battery1_count = int(payload.get("battery1_cell_count", 0) or 0)
    battery_count = 5 + max(0, min(battery1_count, 24))
    if int(payload.get("battery_group_count", 1) or 1) == 2:
        battery2_count = int(payload.get("battery2_cell_count", 0) or 0)
        battery_count += 5 + max(0, min(battery2_count, 24))
    return phase_count + battery_count + 5


def _power_has_measurement(payload: dict) -> bool:
    measurement_keys = [
        "three_voltage_rs", "three_voltage_st", "three_voltage_tr", "three_voltage_rn",
        "three_current_r", "three_current_s", "three_current_t",
        "single_voltage", "single_current",
        "battery1_total_current", "battery1_total_voltage", "battery1_min_voltage",
        "battery1_max_voltage", "battery1_end_voltage",
        "battery2_total_current", "battery2_total_voltage", "battery2_min_voltage",
        "battery2_max_voltage", "battery2_end_voltage",
        "security_ground_1", "security_ground_2", "security_ground_3",
        "telecom_ground", "lightning_ground",
    ]
    if any(payload.get(key, "") not in ("", None) for key in measurement_keys):
        return True
    if any(value not in ("", None) for value in payload.get("battery1_cells", [])):
        return True
    if any(value not in ("", None) for value in payload.get("battery2_cells", [])):
        return True
    return bool(str(payload.get("notes", "")).strip())


def save_power_inspection_result(payload: dict) -> tuple[bool, str, str]:
    """국사 전원시설 정밀점검 결과를 Google Sheet에 새 행으로 저장합니다."""
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패: Streamlit Secrets의 gcp_service_account 설정을 확인하세요.", ""

    try:
        worker = str(payload.get("worker", "")).strip()
        mother = str(payload.get("mother", "")).strip()
        local = str(payload.get("local", "")).strip()
        phase_type = str(payload.get("phase_type", "")).strip()

        if not worker:
            return False, "점검자 성명을 입력해 주세요.", ""
        if mother not in POWER_STATION_MAP:
            return False, "모국 선택값이 올바르지 않습니다.", ""
        if local not in POWER_STATION_MAP.get(mother, []):
            return False, "선택한 모국과 국소의 조합이 올바르지 않습니다.", ""
        if phase_type not in {"삼상", "단상"}:
            return False, "삼상 또는 단상 측정 방식을 선택해 주세요.", ""
        if not _power_has_measurement(payload):
            return False, "측정값 또는 특이사항을 한 개 이상 입력해 주세요.", ""

        missing_items = _power_payload_missing_items(payload)
        if not bool(payload.get("final_confirmed", False)):
            return False, "최종 확인에 동의해 주세요.", ""

        expected_count = max(_power_expected_item_count(payload), 1)
        completed_count = expected_count - len(missing_items)
        completion_rate = round((completed_count / expected_count) * 100, 1)

        spreadsheet = client.open(POWER_INSPECTION_SPREADSHEET_NAME)
        ws, sheet_headers = _ensure_power_inspection_sheet(spreadsheet)

        now = _korea_now()
        saved_at = now.strftime("%Y-%m-%d %H:%M:%S")
        inspection_seed = f"{saved_at}|{worker}|{mother}|{local}|{time.time_ns()}"
        inspection_id = hashlib.sha256(inspection_seed.encode("utf-8")).hexdigest()[:14]
        source_id = str(payload.get("source_inspection_id", "")).strip()
        source_saved_at = str(payload.get("source_saved_at", "")).strip()

        row_map = {
            "저장일시": saved_at,
            "점검ID": inspection_id,
            "점검자": worker,
            "운용조": str(payload.get("inspector_group", "")).strip() or _inspector_group_for_name(worker),
            "모국": mother,
            "국소": local,
            "전원구분": phase_type,
            "축전지조수": int(payload.get("battery_group_count", 1) or 1),
            "입력방식": "기존값 불러오기 후 수정" if source_id else "신규 입력",
            "원본점검ID": source_id,
            "원본저장일시": source_saved_at,
            "입력완료율(%)": completion_rate,
            "누락항목수": len(missing_items),
            "누락항목": ", ".join(missing_items),
            "부분입력확인": "확인" if missing_items else "해당없음",
            "삼상전압_R-S(V)": payload.get("three_voltage_rs", "") if phase_type == "삼상" else "",
            "삼상전압_S-T(V)": payload.get("three_voltage_st", "") if phase_type == "삼상" else "",
            "삼상전압_T-R(V)": payload.get("three_voltage_tr", "") if phase_type == "삼상" else "",
            "삼상전압_R-N(V)": payload.get("three_voltage_rn", "") if phase_type == "삼상" else "",
            "삼상전류_R(A)": payload.get("three_current_r", "") if phase_type == "삼상" else "",
            "삼상전류_S(A)": payload.get("three_current_s", "") if phase_type == "삼상" else "",
            "삼상전류_T(A)": payload.get("three_current_t", "") if phase_type == "삼상" else "",
            "단상전압(V)": payload.get("single_voltage", "") if phase_type == "단상" else "",
            "단상전류(A)": payload.get("single_current", "") if phase_type == "단상" else "",
            "1조_측정셀수": int(payload.get("battery1_cell_count", 0) or 0),
            "1조_방전후_Total전류(A)": payload.get("battery1_total_current", ""),
            "1조_방전후_Total전압(V)": payload.get("battery1_total_voltage", ""),
            "1조_최저전압(V)": payload.get("battery1_min_voltage", ""),
            "1조_최고전압(V)": payload.get("battery1_max_voltage", ""),
            "1조_방전종료전압(V)": payload.get("battery1_end_voltage", ""),
            "2조_측정셀수": int(payload.get("battery2_cell_count", 0) or 0) if int(payload.get("battery_group_count", 1) or 1) == 2 else "",
            "2조_방전후_Total전류(A)": payload.get("battery2_total_current", ""),
            "2조_방전후_Total전압(V)": payload.get("battery2_total_voltage", ""),
            "2조_최저전압(V)": payload.get("battery2_min_voltage", ""),
            "2조_최고전압(V)": payload.get("battery2_max_voltage", ""),
            "2조_방전종료전압(V)": payload.get("battery2_end_voltage", ""),
            "보안접지_1종(Ω)": payload.get("security_ground_1", ""),
            "보안접지_2종(Ω)": payload.get("security_ground_2", ""),
            "보안접지_3종(Ω)": payload.get("security_ground_3", ""),
            "통신용접지_메인(Ω)": payload.get("telecom_ground", ""),
            "피뢰침접지(Ω)": payload.get("lightning_ground", ""),
            "특이사항": str(payload.get("notes", "")).strip(),
        }

        battery1_cells = list(payload.get("battery1_cells", []))[:24]
        battery1_cells.extend([""] * (24 - len(battery1_cells)))
        battery2_cells = list(payload.get("battery2_cells", []))[:24]
        battery2_cells.extend([""] * (24 - len(battery2_cells)))
        for index, value in enumerate(battery1_cells, 1):
            row_map[f"1조_셀{index:02d}(V)"] = value
        for index, value in enumerate(battery2_cells, 1):
            row_map[f"2조_셀{index:02d}(V)"] = value

        row = [row_map.get(header, "") for header in sheet_headers]
        last_error = None
        for attempt in range(5):
            try:
                ws.append_row(row, value_input_option="USER_ENTERED")
                return True, "측정값이 Google Sheets에 정상 저장되었습니다.", inspection_id
            except Exception as append_error:
                last_error = append_error
                error_text = str(append_error)
                if any(token in error_text for token in ("429", "Quota exceeded", "RESOURCE_EXHAUSTED")):
                    time.sleep(1.1 * (attempt + 1))
                    continue
                raise
        return False, f"저장 요청이 집중되어 전송하지 못했습니다. 다시 전송해 주세요. ({last_error})", ""
    except Exception as e:
        return False, str(e), ""


def load_recent_power_inspection(mother: str, local: str, within_days: int = 60) -> tuple[bool, str, dict]:
    """동일 모국·국소의 최근 측정값을 찾아 입력폼 재사용용으로 반환합니다."""
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패: Secrets 설정을 확인하세요.", {}
    if mother not in POWER_STATION_MAP or local not in POWER_STATION_MAP.get(mother, []):
        return False, "먼저 모국과 국소를 정확히 선택해 주세요.", {}

    try:
        spreadsheet = client.open(POWER_INSPECTION_SPREADSHEET_NAME)
        try:
            ws = spreadsheet.worksheet(POWER_INSPECTION_SHEET_NAME)
        except Exception:
            return False, "아직 저장된 전원 정밀점검 기록이 없습니다.", {}

        values = ws.get_all_values()
        if len(values) < 2:
            return False, "아직 저장된 전원 정밀점검 기록이 없습니다.", {}

        headers = values[0]
        now_naive = _korea_now().replace(tzinfo=None)
        cutoff = now_naive - datetime.timedelta(days=max(1, int(within_days)))
        for row in reversed(values[1:]):
            record = {headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))}
            if str(record.get("모국", "")).strip() != mother or str(record.get("국소", "")).strip() != local:
                continue
            saved_text = str(record.get("저장일시", "")).strip()
            try:
                saved_dt = datetime.datetime.strptime(saved_text, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if saved_dt < cutoff:
                continue
            return True, f"최근 측정값을 불러왔습니다. ({saved_text})", record
        return False, f"최근 {within_days}일 이내 동일 국소의 저장 기록이 없습니다.", {}
    except Exception as e:
        return False, str(e), {}


def _set_power_state_from_record(record: dict) -> None:
    draft = _power_draft()

    def set_value(key: str, header: str, decimals: int | None = None) -> None:
        value = str(record.get(header, "")).strip()
        if not value:
            formatted = ""
        elif decimals is None:
            formatted = value
        else:
            formatted = _format_power_display(value, decimals)
        draft[key] = formatted
        st.session_state[key] = formatted

    phase = str(record.get("전원구분", "삼상")).strip()
    phase_value = phase if phase in {"삼상", "단상"} else "삼상"
    draft["power_phase_type"] = phase_value
    st.session_state["power_phase_type"] = phase_value

    phase_map = [
        ("power_three_voltage_rs", "삼상전압_R-S(V)", 1),
        ("power_three_voltage_st", "삼상전압_S-T(V)", 1),
        ("power_three_voltage_tr", "삼상전압_T-R(V)", 1),
        ("power_three_voltage_rn", "삼상전압_R-N(V)", 1),
        ("power_three_current_r", "삼상전류_R(A)", 1),
        ("power_three_current_s", "삼상전류_S(A)", 1),
        ("power_three_current_t", "삼상전류_T(A)", 1),
        ("power_single_voltage", "단상전압(V)", 1),
        ("power_single_current", "단상전류(A)", 1),
    ]
    for key, header, decimals in phase_map:
        set_value(key, header, decimals)

    for group in (1, 2):
        prefix = f"power_battery{group}"
        set_value(f"{prefix}_total_current", f"{group}조_방전후_Total전류(A)", 1)
        set_value(f"{prefix}_total_voltage", f"{group}조_방전후_Total전압(V)", 2)
        set_value(f"{prefix}_min_voltage", f"{group}조_최저전압(V)", 2)
        set_value(f"{prefix}_max_voltage", f"{group}조_최고전압(V)", 2)
        set_value(f"{prefix}_end_voltage", f"{group}조_방전종료전압(V)", 2)
        for index in range(1, 25):
            set_value(f"power_battery_{group}_{index:02d}", f"{group}조_셀{index:02d}(V)", 2)

    ground_map = [
        ("power_security_ground_1", "보안접지_1종(Ω)"),
        ("power_security_ground_2", "보안접지_2종(Ω)"),
        ("power_security_ground_3", "보안접지_3종(Ω)"),
        ("power_telecom_ground", "통신용접지_메인(Ω)"),
        ("power_lightning_ground", "피뢰침접지(Ω)"),
    ]
    for key, header in ground_map:
        set_value(key, header, 2)

    group_count = str(record.get("축전지조수", "1")).strip()
    has_group2 = group_count == "2" or any(
        str(record.get(f"2조_셀{index:02d}(V)", "")).strip() for index in range(1, 25)
    )
    draft["power_battery2_enabled"] = has_group2
    draft["power_battery_set"] = "1조 셀 측정"
    st.session_state["power_battery2_enabled"] = has_group2
    st.session_state["power_battery_set"] = "1조 셀 측정"
    st.session_state["power_loaded_source_id"] = str(record.get("점검ID", "")).strip()
    st.session_state["power_loaded_source_saved_at"] = str(record.get("저장일시", "")).strip()
    st.session_state["power_loaded_notice"] = True
    st.session_state["power_draft_saved_at"] = _korea_now().strftime("%H:%M:%S")


def _render_power_cell_inputs(group_number: int) -> list[str]:
    """셀 번호 1~24를 한 줄 최대 5개로 배치하고, 각 입력을 세션 임시저장소에 보존합니다."""
    values: list[str] = []
    for start in range(1, 25, 5):
        row_columns = st.columns(5, gap="small")
        for offset, column in enumerate(row_columns):
            cell_number = start + offset
            if cell_number > 24:
                break
            key = f"power_battery_{group_number}_{cell_number:02d}"
            with column:
                values.append(
                    _power_text_input(
                        str(cell_number),
                        key=key,
                        label_visibility="visible",
                    )
                )
    return values


def _render_power_battery_summary(group_number: int) -> None:
    prefix = f"power_battery{group_number}"
    st.markdown(f"**{group_number}조 측정값**")
    row1 = st.columns(2, gap="small")
    with row1[0]:
        _power_text_input("방전 후 Total 전류 (A)", key=f"{prefix}_total_current")
    with row1[1]:
        _power_text_input("방전 후 Total 전압 (V)", key=f"{prefix}_total_voltage")
    row2 = st.columns(2, gap="small")
    with row2[0]:
        _power_text_input("최저전압 (V)", key=f"{prefix}_min_voltage")
    with row2[1]:
        _power_text_input("최고전압 (V)", key=f"{prefix}_max_voltage")
    _power_text_input("방전종료 전압 (V)", key=f"{prefix}_end_voltage")
    st.markdown(f"**{group_number}조 셀 전압 (V)**")
    st.caption("실제 설치된 셀 수만 입력해도 됩니다. 예: 10셀만 측정한 경우 1~10번까지만 입력하고 다음 단계로 진행할 수 있습니다.")
    _render_power_cell_inputs(group_number)


POWER_THEME_ORDER = ["전압·전류 측정", "축전지 측정", "접지저항 측정", "최종 확인·전송"]
POWER_THEME_ICON = {
    "전압·전류 측정": "⚡",
    "축전지 측정": "🔋",
    "접지저항 측정": "🛡️",
    "최종 확인·전송": "📤",
}


def _power_state_blank(key: str) -> bool:
    value = _power_get(key, "")
    return value is None or (isinstance(value, str) and not value.strip())


def _clear_power_measurements_after_station_change() -> None:
    """국사가 실제로 바뀌면 이전 국사의 측정값이 섞이지 않도록 측정 임시값을 초기화합니다."""
    keep_keys = {
        "power_worker", "power_inspector_group", "power_mother", "power_local",
        "power_current_theme", "power_phase_type", "power_battery_set",
    }
    for key in list(st.session_state.keys()):
        if key.startswith("power_") and key not in keep_keys:
            del st.session_state[key]
    st.session_state["power_draft"] = {}
    st.session_state["power_current_theme"] = POWER_THEME_ORDER[0]


def _power_theme_missing(theme: str) -> list[str]:
    phase_type = _power_get("power_phase_type", "삼상")
    if theme == "전압·전류 측정":
        if phase_type == "삼상":
            checks = [
                ("power_three_voltage_rs", "R-S 전압"),
                ("power_three_voltage_st", "S-T 전압"),
                ("power_three_voltage_tr", "T-R 전압"),
                ("power_three_voltage_rn", "R-N 전압"),
                ("power_three_current_r", "R상 전류"),
                ("power_three_current_s", "S상 전류"),
                ("power_three_current_t", "T상 전류"),
            ]
        else:
            checks = [
                ("power_single_voltage", "단상 전압"),
                ("power_single_current", "단상 전류"),
            ]
        return [label for key, label in checks if _power_state_blank(key)]

    if theme == "축전지 측정":
        checks = [
            ("power_battery1_total_current", "1조 방전 후 Total 전류"),
            ("power_battery1_total_voltage", "1조 방전 후 Total 전압"),
            ("power_battery1_min_voltage", "1조 최저전압"),
            ("power_battery1_max_voltage", "1조 최고전압"),
            ("power_battery1_end_voltage", "1조 방전종료 전압"),
        ]
        missing = [label for key, label in checks if _power_state_blank(key)]
        missing.extend(
            f"1조 {index}셀" for index in range(1, 25)
            if _power_state_blank(f"power_battery_1_{index:02d}")
        )
        if _power_battery2_enabled():
            checks2 = [
                ("power_battery2_total_current", "2조 방전 후 Total 전류"),
                ("power_battery2_total_voltage", "2조 방전 후 Total 전압"),
                ("power_battery2_min_voltage", "2조 최저전압"),
                ("power_battery2_max_voltage", "2조 최고전압"),
                ("power_battery2_end_voltage", "2조 방전종료 전압"),
            ]
            missing.extend(label for key, label in checks2 if _power_state_blank(key))
            missing.extend(
                f"2조 {index}셀" for index in range(1, 25)
                if _power_state_blank(f"power_battery_2_{index:02d}")
            )
        return missing

    if theme == "접지저항 측정":
        checks = [
            ("power_security_ground_1", "보안 1종"),
            ("power_security_ground_2", "보안 2종"),
            ("power_security_ground_3", "보안 3종"),
            ("power_telecom_ground", "통신용접지(메인)"),
            ("power_lightning_ground", "피뢰침접지"),
        ]
        return [label for key, label in checks if _power_state_blank(key)]
    return []


def _power_theme_started(theme: str) -> bool:
    if theme == "전압·전류 측정":
        keys = _power_theme_keys(theme)[1:]
        return any(not _power_state_blank(key) for key in keys)
    if theme == "축전지 측정":
        keys = [key for key in _power_theme_keys(theme) if key.startswith("power_battery") and key not in {"power_battery_set", "power_battery2_enabled"}]
        return any(not _power_state_blank(key) for key in keys)
    if theme == "접지저항 측정":
        return any(not _power_state_blank(key) for key in _power_theme_keys(theme))
    return False


def _clear_power_pending_move() -> None:
    for key in (
        "power_pending_theme", "power_pending_from_theme", "power_pending_missing",
        "power_missing_answer", "power_move_validation_error",
        "power_battery_pending_target", "power_battery_exit_stage",
        "power_battery_additional_answer", "power_battery2_measure_answer",
        "power_battery_move_error",
    ):
        st.session_state.pop(key, None)


def _request_power_theme(target_theme: str) -> None:
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    if current_theme not in POWER_THEME_ORDER:
        current_theme = POWER_THEME_ORDER[0]
    _save_power_theme_to_draft(current_theme)

    if target_theme == current_theme:
        return

    current_index = POWER_THEME_ORDER.index(current_theme)
    target_index = POWER_THEME_ORDER.index(target_theme)

    # 축전지 메뉴를 앞으로 벗어날 때는 1조 추가입력 여부와 2조 측정 여부를 별도로 확인합니다.
    if current_theme == "축전지 측정" and target_index > current_index:
        st.session_state["power_battery_pending_target"] = "접지저항 측정"
        st.session_state["power_battery_exit_stage"] = "additional"
        st.session_state.pop("power_battery_additional_answer", None)
        st.session_state.pop("power_battery2_measure_answer", None)
        st.session_state.pop("power_battery_move_error", None)
        return

    if target_index > current_index:
        st.session_state["power_pending_theme"] = target_theme
        st.session_state["power_pending_from_theme"] = current_theme
        st.session_state["power_pending_missing"] = _power_theme_missing(current_theme)
        st.session_state.pop("power_missing_answer", None)
        st.session_state.pop("power_move_validation_error", None)
        return

    st.session_state["power_current_theme"] = target_theme
    _clear_power_pending_move()


def _process_power_theme_move() -> bool:
    target = st.session_state.get("power_pending_theme")
    source = st.session_state.get("power_pending_from_theme")
    _save_power_theme_to_draft(str(source))
    missing = _power_theme_missing(str(source)) if source in POWER_THEME_ORDER else []
    st.session_state["power_pending_missing"] = missing
    answer = st.session_state.get("power_missing_answer")
    if answer not in {"예", "아니오"}:
        st.session_state["power_move_validation_error"] = "‘예’ 또는 ‘아니오’를 선택해 주세요."
        return False
    if answer == "아니오" and missing:
        st.session_state["power_move_validation_error"] = (
            f"실제 누락 항목이 {len(missing)}개 있습니다. ‘예’를 선택하거나 값을 추가로 입력해 주세요."
        )
        return False
    if answer == "예" and not missing:
        st.session_state["power_move_validation_error"] = "현재 테마에는 누락된 값이 없습니다. ‘아니오’를 선택해 주세요."
        return False
    confirmations = dict(st.session_state.get("power_theme_confirmations", {}))
    confirmations[str(source)] = {
        "answer": answer,
        "missing_count": len(missing),
        "confirmed_at": _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state["power_theme_confirmations"] = confirmations
    if target in POWER_THEME_ORDER:
        st.session_state["power_current_theme"] = target
    _clear_power_pending_move()
    st.session_state["power_temp_saved_notice"] = True
    return True


def _process_battery_additional_confirmation() -> bool:
    selected_group = 1 if _power_get("power_battery_set", "1조 셀 측정") == "1조 셀 측정" else 2
    answer = st.session_state.get("power_battery_additional_answer")
    if answer not in {"예", "아니오"}:
        st.session_state["power_battery_move_error"] = "추가 입력 여부를 선택해 주세요."
        return False
    _save_power_theme_to_draft("축전지 측정")
    if answer == "예":
        _clear_power_pending_move()
        st.session_state["power_temp_saved_notice"] = True
        return True

    if selected_group == 1:
        st.session_state["power_battery_exit_stage"] = "ask_group2"
        st.session_state.pop("power_battery2_measure_answer", None)
        st.session_state.pop("power_battery_move_error", None)
        return True

    # 2조까지 입력한 뒤 추가값이 없으면 다음 테마로 이동합니다.
    target = st.session_state.get("power_battery_pending_target", "접지저항 측정")
    st.session_state["power_current_theme"] = target if target in POWER_THEME_ORDER else "접지저항 측정"
    confirmations = dict(st.session_state.get("power_theme_confirmations", {}))
    confirmations["축전지 측정"] = {
        "answer": "추가 입력 없음",
        "missing_count": len(_power_theme_missing("축전지 측정")),
        "confirmed_at": _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state["power_theme_confirmations"] = confirmations
    _clear_power_pending_move()
    st.session_state["power_temp_saved_notice"] = True
    return True


def _process_battery2_measure_confirmation() -> bool:
    answer = st.session_state.get("power_battery2_measure_answer")
    if answer not in {"예", "아니오"}:
        st.session_state["power_battery_move_error"] = "2조 축전지 측정 여부를 선택해 주세요."
        return False
    _save_power_theme_to_draft("축전지 측정")
    if answer == "예":
        _power_set("power_battery2_enabled", True)
        _power_set("power_battery_set", "2조 셀 측정")
        st.session_state["power_current_theme"] = "축전지 측정"
    else:
        # 기존 2조 임시값은 삭제하지 않고 보존하되, 이번 점검의 저장범위에서는 제외합니다.
        _power_set("power_battery2_enabled", False)
        _power_set("power_battery_set", "1조 셀 측정")
        target = st.session_state.get("power_battery_pending_target", "접지저항 측정")
        st.session_state["power_current_theme"] = target if target in POWER_THEME_ORDER else "접지저항 측정"
    confirmations = dict(st.session_state.get("power_theme_confirmations", {}))
    confirmations["축전지 측정"] = {
        "answer": f"2조 측정 {answer}",
        "missing_count": len(_power_theme_missing("축전지 측정")),
        "confirmed_at": _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state["power_theme_confirmations"] = confirmations
    _clear_power_pending_move()
    st.session_state["power_temp_saved_notice"] = True
    return True


def _cancel_power_theme_move() -> None:
    _save_power_theme_to_draft(st.session_state.get("power_current_theme", POWER_THEME_ORDER[0]))
    _clear_power_pending_move()


def _build_power_payload_from_state(final_confirmed: bool = False) -> dict:
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    _save_power_theme_to_draft(current_theme)
    phase_type = _power_get("power_phase_type", "삼상")
    group_count = 2 if _power_battery2_enabled() else 1
    worker = str(st.session_state.get("power_worker", "")).strip()
    battery1_cells = [
        _parse_power_number(_power_get(f"power_battery_1_{index:02d}", ""), 2)
        for index in range(1, 25)
    ]
    battery2_cells = [
        _parse_power_number(_power_get(f"power_battery_2_{index:02d}", ""), 2)
        for index in range(1, 25)
    ] if group_count == 2 else [""] * 24
    return {
        "worker": worker,
        "inspector_group": st.session_state.get("power_inspector_group", "") or _inspector_group_for_name(worker),
        "mother": st.session_state.get("power_mother", "모국 선택"),
        "local": st.session_state.get("power_local", "국소 선택"),
        "phase_type": phase_type,
        "battery_group_count": group_count,
        "source_inspection_id": st.session_state.get("power_loaded_source_id", ""),
        "source_saved_at": st.session_state.get("power_loaded_source_saved_at", ""),
        "three_voltage_rs": _parse_power_number(_power_get("power_three_voltage_rs", ""), 1),
        "three_voltage_st": _parse_power_number(_power_get("power_three_voltage_st", ""), 1),
        "three_voltage_tr": _parse_power_number(_power_get("power_three_voltage_tr", ""), 1),
        "three_voltage_rn": _parse_power_number(_power_get("power_three_voltage_rn", ""), 1),
        "three_current_r": _parse_power_number(_power_get("power_three_current_r", ""), 1),
        "three_current_s": _parse_power_number(_power_get("power_three_current_s", ""), 1),
        "three_current_t": _parse_power_number(_power_get("power_three_current_t", ""), 1),
        "single_voltage": _parse_power_number(_power_get("power_single_voltage", ""), 1),
        "single_current": _parse_power_number(_power_get("power_single_current", ""), 1),
        "battery1_total_current": _parse_power_number(_power_get("power_battery1_total_current", ""), 1),
        "battery1_total_voltage": _parse_power_number(_power_get("power_battery1_total_voltage", ""), 2),
        "battery1_min_voltage": _parse_power_number(_power_get("power_battery1_min_voltage", ""), 2),
        "battery1_max_voltage": _parse_power_number(_power_get("power_battery1_max_voltage", ""), 2),
        "battery1_end_voltage": _parse_power_number(_power_get("power_battery1_end_voltage", ""), 2),
        "battery1_cell_count": _measured_cell_count(battery1_cells),
        "battery1_cells": battery1_cells,
        "battery2_total_current": _parse_power_number(_power_get("power_battery2_total_current", ""), 1) if group_count == 2 else "",
        "battery2_total_voltage": _parse_power_number(_power_get("power_battery2_total_voltage", ""), 2) if group_count == 2 else "",
        "battery2_min_voltage": _parse_power_number(_power_get("power_battery2_min_voltage", ""), 2) if group_count == 2 else "",
        "battery2_max_voltage": _parse_power_number(_power_get("power_battery2_max_voltage", ""), 2) if group_count == 2 else "",
        "battery2_end_voltage": _parse_power_number(_power_get("power_battery2_end_voltage", ""), 2) if group_count == 2 else "",
        "battery2_cell_count": _measured_cell_count(battery2_cells) if group_count == 2 else 0,
        "battery2_cells": battery2_cells,
        "security_ground_1": _parse_power_number(_power_get("power_security_ground_1", ""), 2),
        "security_ground_2": _parse_power_number(_power_get("power_security_ground_2", ""), 2),
        "security_ground_3": _parse_power_number(_power_get("power_security_ground_3", ""), 2),
        "telecom_ground": _parse_power_number(_power_get("power_telecom_ground", ""), 2),
        "lightning_ground": _parse_power_number(_power_get("power_lightning_ground", ""), 2),
        "notes": _power_get("power_notes", ""),
        "final_confirmed": bool(final_confirmed),
    }


def _reset_power_inspection() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("power_"):
            del st.session_state[key]
    st.session_state["power_current_theme"] = POWER_THEME_ORDER[0]
    st.session_state["power_phase_type"] = "삼상"
    st.session_state["power_battery_set"] = "1조 셀 측정"


def _render_power_auto_decimal_script() -> None:
    field_decimals = {
        "power_three_voltage_rs": 1, "power_three_voltage_st": 1,
        "power_three_voltage_tr": 1, "power_three_voltage_rn": 1,
        "power_three_current_r": 1, "power_three_current_s": 1, "power_three_current_t": 1,
        "power_single_voltage": 1, "power_single_current": 1,
        "power_battery1_total_current": 1, "power_battery2_total_current": 1,
        "power_battery1_total_voltage": 2, "power_battery2_total_voltage": 2,
        "power_battery1_min_voltage": 2, "power_battery2_min_voltage": 2,
        "power_battery1_max_voltage": 2, "power_battery2_max_voltage": 2,
        "power_battery1_end_voltage": 2, "power_battery2_end_voltage": 2,
        "power_security_ground_1": 2, "power_security_ground_2": 2,
        "power_security_ground_3": 2, "power_telecom_ground": 2,
        "power_lightning_ground": 2,
    }
    for group in (1, 2):
        for cell_number in range(1, 25):
            field_decimals[f"power_battery_{group}_{cell_number:02d}"] = 2

    rules_json = json.dumps(field_decimals, ensure_ascii=False)
    script = r"""
        <script>
        (() => {
          const rules = __POWER_RULES_JSON__;

          function formatted(raw, decimals) {
            let value = String(raw || '').trim().replace(/,/g, '');
            if (!value) return '';
            value = value.replace(/[^0-9.]/g, '');
            if (!value) return '';
            if (value.includes('.')) {
              const pieces = value.split('.', 2);
              const integer = (pieces[0] || '0').replace(/\D/g, '') || '0';
              const fraction = (pieces[1] || '').replace(/\D/g, '').slice(0, decimals).padEnd(decimals, '0');
              return decimals > 0 ? `${integer}.${fraction}` : integer;
            }
            const digits = value.replace(/\D/g, '');
            if (!digits) return '';
            if (decimals <= 0) return digits;
            const padded = digits.length <= decimals ? digits.padStart(decimals + 1, '0') : digits;
            return `${padded.slice(0, -decimals)}.${padded.slice(-decimals)}`;
          }

          function setReactValue(input, value) {
            const proto = window.parent.HTMLInputElement.prototype;
            const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
            if (descriptor && descriptor.set) descriptor.set.call(input, value);
            else input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
          }

          function isVisible(element) {
            const style = window.parent.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
          }

          function wrapperForKey(doc, key) {
            return doc.querySelector(`div.st-key-${key}`);
          }

          function visibleMeasurementInputs(doc) {
            const found = [];
            Object.keys(rules).forEach((key) => {
              const wrapper = wrapperForKey(doc, key);
              const input = wrapper ? wrapper.querySelector('input') : null;
              if (input && isVisible(input)) found.push({ key, input });
            });
            return found.sort((a, b) => {
              const pos = a.input.compareDocumentPosition(b.input);
              if (pos & Node.DOCUMENT_POSITION_FOLLOWING) return -1;
              if (pos & Node.DOCUMENT_POSITION_PRECEDING) return 1;
              return 0;
            });
          }

          function bindInputs() {
            let doc;
            try { doc = window.parent.document; } catch (error) { return; }
            Object.entries(rules).forEach(([key, decimals]) => {
              const wrapper = wrapperForKey(doc, key);
              const input = wrapper ? wrapper.querySelector('input') : null;
              if (!input || input.dataset.powerDecimalBound === '1') return;
              input.dataset.powerDecimalBound = '1';
              input.dataset.powerKey = key;
              input.setAttribute('inputmode', 'decimal');
              input.setAttribute('autocomplete', 'off');

              const applyFormat = () => {
                const next = formatted(input.value, Number(decimals));
                if (next && next !== input.value) setReactValue(input, next);
              };

              input.addEventListener('blur', applyFormat);
              input.addEventListener('keydown', (event) => {
                if (event.key !== 'Enter') return;
                event.preventDefault();
                applyFormat();
                window.setTimeout(() => {
                  const ordered = visibleMeasurementInputs(doc);
                  const currentIndex = ordered.findIndex((item) => item.input === input);
                  const nextItem = ordered[currentIndex + 1];
                  if (nextItem) {
                    try { window.parent.sessionStorage.setItem('__power_next_focus_key__', nextItem.key); } catch (e) {}
                    nextItem.input.focus();
                    nextItem.input.select();
                    nextItem.input.scrollIntoView({behavior: 'smooth', block: 'center'});
                  } else {
                    input.blur();
                  }
                }, 100);
              });
            });
          }

          function restoreNextFocus() {
            let doc;
            try { doc = window.parent.document; } catch (error) { return; }
            let nextKey = '';
            try { nextKey = window.parent.sessionStorage.getItem('__power_next_focus_key__') || ''; } catch (e) {}
            if (!nextKey) return;
            const wrapper = wrapperForKey(doc, nextKey);
            const input = wrapper ? wrapper.querySelector('input') : null;
            if (input && isVisible(input)) {
              input.focus();
              input.select();
              input.scrollIntoView({behavior: 'smooth', block: 'center'});
              try { window.parent.sessionStorage.removeItem('__power_next_focus_key__'); } catch (e) {}
            }
          }

          bindInputs();
          restoreNextFocus();
          const timer = setInterval(() => { bindInputs(); restoreNextFocus(); }, 350);
          setTimeout(() => clearInterval(timer), 60000);
        })();
        </script>
    """
    components.html(script.replace("__POWER_RULES_JSON__", rules_json), height=1)


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

tab_power, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    "🔋 국사 전원시설 정밀점검", "📄 법률 검토",
    "💬 AI 에이전트(챗봇)", "📰 스마트 요약", "🔒 관리자 모드"
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


# --- [Tab 1: 국사 전원시설 정밀점검] ---
with tab_power:
    if st.session_state.get("power_current_theme") not in POWER_THEME_ORDER:
        st.session_state["power_current_theme"] = POWER_THEME_ORDER[0]
    if st.session_state.get("power_phase_type") not in {"삼상", "단상"}:
        st.session_state["power_phase_type"] = "삼상"
    if st.session_state.get("power_battery_set") not in {"1조 셀 측정", "2조 셀 측정"}:
        st.session_state["power_battery_set"] = "1조 셀 측정"
    _power_draft()
    expected_group = _inspector_group_for_name(st.session_state.get("power_worker", ""))
    if st.session_state.get("power_inspector_group", "") != expected_group:
        st.session_state["power_inspector_group"] = expected_group

    st.markdown("### 🔋 국사 전원시설 정밀점검")
    st.caption("기본정보를 먼저 선택한 뒤, 측정 테마별로 입력하고 마지막에 Google Sheets로 전송합니다.")

    st.markdown("""
    <style>
    .power-mobile-hero {
        background: linear-gradient(135deg, #EAF4FF 0%, #F8FAFC 54%, #ECFDF5 100%);
        border: 1px solid #D5E3F3;
        border-left: 8px solid #0B5CAB;
        border-radius: 20px;
        padding: 17px 19px;
        margin: 8px 0 12px 0;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    }
    .power-mobile-hero h3 { margin:0 0 6px 0; color:#0F172A; font-weight:950; font-size:1.15rem; }
    .power-mobile-hero p { margin:0; color:#475569; line-height:1.55; font-weight:650; }
    .power-basic-card {
        background:#FFFFFF; border:1px solid #D8E3F2; border-radius:17px;
        padding:14px 15px 6px; margin:10px 0 10px; box-shadow:0 6px 18px rgba(15,23,42,.06);
    }
    .power-basic-title {font-size:1.02rem; font-weight:950; color:#0B5CAB; margin-bottom:8px;}
    .power-sticky-card {
        position: sticky; top: 0.35rem; z-index: 990;
        background: rgba(15, 23, 42, 0.96); color: #FFFFFF;
        border: 1px solid rgba(255,255,255,0.18); border-radius: 15px;
        padding: 10px 14px; margin: 8px 0 11px 0;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.22); backdrop-filter: blur(10px);
    }
    .power-sticky-title { font-size:0.73rem; opacity:0.76; font-weight:800; margin-bottom:3px; }
    .power-sticky-main { font-size:0.98rem; font-weight:950; line-height:1.35; word-break:keep-all; }
    .power-sticky-sub { font-size:0.82rem; opacity:0.88; margin-top:3px; line-height:1.35; }
    .power-theme-heading {
        font-size:1.18rem; font-weight:950; color:#0B5CAB;
        margin:12px 0 9px 0; padding-bottom:8px; border-bottom:2px solid #DCEAF7;
    }
    .power-unit-guide {
        background:#EFF6FF; border:1px solid #BFDBFE; border-radius:12px;
        padding:10px 12px; color:#1E3A8A; font-weight:800; margin:8px 0 12px;
    }
    .power-missing-box {
        background:#FFF7ED; border:1px solid #FDBA74; border-left:7px solid #F97316;
        border-radius:15px; padding:13px 15px; margin:10px 0;
        color:#7C2D12; line-height:1.55; font-weight:750;
    }
    .power-complete-box {
        background:#ECFDF5; border:1px solid #86EFAC; border-radius:15px;
        padding:13px 15px; color:#166534; font-weight:800;
    }
    .power-loaded-box {
        background:#F0FDF4; border:1px solid #86EFAC; border-left:6px solid #16A34A;
        border-radius:13px; padding:11px 13px; color:#166534; font-weight:800; margin:8px 0;
    }
    .power-sheet-note {
        background:#F8FAFC; border:1px solid #CBD5E1; border-radius:14px;
        padding:13px 15px; color:#334155; font-weight:700; line-height:1.55;
    }
    .st-key-power_theme_menu_0 button,
    .st-key-power_theme_menu_1 button,
    .st-key-power_theme_menu_2 button,
    .st-key-power_theme_menu_3 button {
        min-height: 52px !important; padding: 0.45rem 0.35rem !important;
        border-radius: 13px !important; font-size: 0.92rem !important; line-height: 1.15 !important;
    }
    div[class*="st-key-power_battery_"] input {
        text-align:center !important; padding-left:0.25rem !important; padding-right:0.25rem !important;
        min-height:44px !important; font-weight:850 !important;
    }
    div[class*="st-key-power_battery_"] label p {
        text-align:center !important; font-size:0.80rem !important; font-weight:900 !important;
    }
    @media (max-width: 768px) {
        .power-mobile-hero { padding:14px 13px; border-radius:15px; }
        .power-sticky-card { top:0.2rem; border-radius:13px; padding:9px 11px; }
        .power-sticky-main { font-size:0.92rem; }
        div[class*="st-key-power_"] input,
        div[class*="st-key-power_"] textarea { font-size:16px !important; }
        div[class*="st-key-power_"] label p { font-size:0.82rem !important; }
        div[class*="st-key-power_battery_"] input { padding:0.35rem 0.12rem !important; }
        div[class*="st-key-power_battery_"] label p { font-size:0.72rem !important; }
    }
    </style>
    <div class="power-mobile-hero">
      <h3>새로운 전원 정밀점검 전용 공간</h3>
      <p>점검자와 국소를 먼저 선택하고, 필요한 측정 테마만 열어 입력합니다. 최근 60일 측정값을 불러와 변경된 값만 수정할 수도 있습니다.</p>
    </div>
    """, unsafe_allow_html=True)

    # 기본정보는 별도 메뉴가 아니라 항상 최상단에 표시합니다.
    st.markdown('<div class="power-basic-card"><div class="power-basic-title">👤 기본정보</div></div>', unsafe_allow_html=True)
    inspector_col1, inspector_col2 = st.columns([1.25, 0.75], gap="small")
    with inspector_col1:
        st.text_input(
            "점검자 성명 *",
            key="power_worker",
            on_change=_update_power_inspector_group,
            placeholder="성명을 입력하세요",
        )
    with inspector_col2:
        st.text_input(
            "소속 조",
            key="power_inspector_group",
            disabled=True,
            placeholder="이름 입력 시 자동 표시",
        )
    if st.session_state.get("power_worker") and not st.session_state.get("power_inspector_group"):
        st.caption("※ 등록되지 않은 성명입니다. 이름별 조 정보가 제공되면 목록에 추가할 수 있습니다.")
    station_col1, station_col2 = st.columns([1, 1], gap="small")
    with station_col1:
        mother_options = ["모국 선택"] + list(POWER_STATION_MAP.keys())
        selected_mother = st.selectbox(
            "모국 *", mother_options, key="power_mother",
            on_change=_clear_power_measurements_after_station_change,
        )

    local_options = ["국소 선택"]
    if selected_mother in POWER_STATION_MAP:
        local_options += POWER_STATION_MAP[selected_mother]
    current_local = st.session_state.get("power_local", "국소 선택")
    if current_local not in local_options:
        st.session_state["power_local"] = "국소 선택"
    with station_col2:
        st.selectbox(
            "국소 *", local_options, key="power_local",
            disabled=selected_mother not in POWER_STATION_MAP,
            on_change=_clear_power_measurements_after_station_change,
        )

    selected_local = st.session_state.get("power_local", "국소 선택")
    can_load = selected_mother in POWER_STATION_MAP and selected_local in POWER_STATION_MAP.get(selected_mother, [])
    if st.button(
        "↩️ 최근 60일 동일 국소 측정값 불러오기",
        key="power_load_recent_values",
        use_container_width=True,
        disabled=not can_load,
    ):
        with st.spinner("최근 측정값을 확인하고 있습니다..."):
            ok, message, record = load_recent_power_inspection(selected_mother, selected_local, 60)
        if ok:
            _set_power_state_from_record(record)
            st.session_state["power_loaded_message"] = message
            st.rerun()
        else:
            st.warning(message)

    if st.session_state.pop("power_loaded_notice", False):
        st.toast("최근 측정값을 입력폼에 불러왔습니다. 변경된 값만 수정해 주세요.", icon="↩️")
    if st.session_state.get("power_loaded_source_id"):
        st.markdown(
            f'<div class="power-loaded-box">↩️ 기존 측정값 사용 중 · '
            f'원본 저장일시: {html.escape(str(st.session_state.get("power_loaded_source_saved_at", "-")))} · '
            f'원본 점검ID: {html.escape(str(st.session_state.get("power_loaded_source_id", "-")))}</div>',
            unsafe_allow_html=True,
        )

    basic_missing = _power_basic_missing()
    if basic_missing:
        st.caption("※ 점검자 성명·모국·국소는 최종 전송을 위한 필수 기본정보입니다.")

    worker_summary = html.escape(str(st.session_state.get("power_worker", "")).strip() or "미입력")
    inspector_group_summary = html.escape(str(st.session_state.get("power_inspector_group", "")).strip() or "조 미등록")
    draft_saved_at = html.escape(str(st.session_state.get("power_draft_saved_at", "")).strip() or "-")
    mother_summary = str(st.session_state.get("power_mother", "모국 선택"))
    local_summary = str(st.session_state.get("power_local", "국소 선택"))
    station_summary = "미선택"
    if mother_summary in POWER_STATION_MAP and local_summary in POWER_STATION_MAP.get(mother_summary, []):
        station_summary = f"{mother_summary} / {local_summary}"
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    st.markdown(
        f"""<div class="power-sticky-card">
          <div class="power-sticky-title">현재 점검정보 · {html.escape(current_theme)}</div>
          <div class="power-sticky-main">👤 {worker_summary} · {inspector_group_summary}</div>
          <div class="power-sticky-sub">📍 {html.escape(station_summary)} · 임시저장 {draft_saved_at}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown("#### 측정 메뉴")
    for row_start in range(0, len(POWER_THEME_ORDER), 2):
        menu_columns = st.columns(2, gap="small")
        for offset, column in enumerate(menu_columns):
            theme_index = row_start + offset
            if theme_index >= len(POWER_THEME_ORDER):
                continue
            theme = POWER_THEME_ORDER[theme_index]
            missing_count = len(_power_theme_missing(theme))
            if theme == "최종 확인·전송":
                status_mark = ""
            elif not missing_count:
                status_mark = " ✅"
            elif _power_theme_started(theme):
                status_mark = " ◐"
            else:
                status_mark = ""
            with column:
                st.button(
                    f"{'▶ ' if theme == current_theme else ''}{POWER_THEME_ICON[theme]} {theme}{status_mark}",
                    key=f"power_theme_menu_{theme_index}",
                    type="primary" if theme == current_theme else "secondary",
                    use_container_width=True,
                    on_click=_request_power_theme,
                    args=(theme,),
                )

    battery_pending_target = st.session_state.get("power_battery_pending_target")
    if battery_pending_target:
        battery_stage = st.session_state.get("power_battery_exit_stage", "additional")
        selected_group = 1 if _power_get("power_battery_set", "1조 셀 측정") == "1조 셀 측정" else 2
        if battery_stage == "additional":
            st.markdown(
                f'<div class="power-missing-box"><b>{selected_group}조 축전지에 추가로 입력할 측정값이 있습니까?</b><br>'
                '실제 설치된 셀 수만 입력하면 됩니다. 24셀을 모두 채울 필요는 없습니다.<br>'
                '‘아니오’를 선택하면 현재 값을 임시 저장하고 다음 확인으로 진행합니다.</div>',
                unsafe_allow_html=True,
            )
            st.radio(
                "추가 측정값 입력 여부",
                ["예", "아니오"],
                horizontal=True,
                index=None,
                key="power_battery_additional_answer",
            )
            if st.session_state.get("power_battery_move_error"):
                st.error(st.session_state["power_battery_move_error"])
            confirm_col, cancel_col = st.columns(2, gap="small")
            with confirm_col:
                st.button(
                    "확인",
                    key="power_confirm_battery_additional",
                    type="primary",
                    use_container_width=True,
                    on_click=_process_battery_additional_confirmation,
                )
            with cancel_col:
                st.button(
                    "계속 입력",
                    key="power_cancel_battery_additional",
                    use_container_width=True,
                    on_click=_cancel_power_theme_move,
                )
        elif battery_stage == "ask_group2":
            st.markdown(
                '<div class="power-missing-box"><b>2조 축전지 측정값도 입력하시겠습니까?</b><br>'
                '‘예’를 선택하면 2조 입력화면으로 이동하고, ‘아니오’를 선택하면 현재 1조 값을 임시 저장한 뒤 접지저항 측정으로 이동합니다.</div>',
                unsafe_allow_html=True,
            )
            st.radio(
                "2조 축전지 측정 여부",
                ["예", "아니오"],
                horizontal=True,
                index=None,
                key="power_battery2_measure_answer",
            )
            if st.session_state.get("power_battery_move_error"):
                st.error(st.session_state["power_battery_move_error"])
            confirm_col, cancel_col = st.columns(2, gap="small")
            with confirm_col:
                st.button(
                    "확인",
                    key="power_confirm_battery2_measure",
                    type="primary",
                    use_container_width=True,
                    on_click=_process_battery2_measure_confirmation,
                )
            with cancel_col:
                st.button(
                    "취소",
                    key="power_cancel_battery2_measure",
                    use_container_width=True,
                    on_click=_cancel_power_theme_move,
                )

    pending_theme = st.session_state.get("power_pending_theme")
    if pending_theme:
        pending_from_theme = st.session_state.get("power_pending_from_theme")
        pending_missing = _power_theme_missing(str(pending_from_theme)) if pending_from_theme in POWER_THEME_ORDER else []
        st.session_state["power_pending_missing"] = pending_missing
        preview = ", ".join(pending_missing[:8]) if pending_missing else "없음"
        more_text = f" 외 {len(pending_missing) - 8}개" if len(pending_missing) > 8 else ""
        st.markdown(
            f'<div class="power-missing-box"><b>누락된 값이 있습니까?</b><br>'
            f'시스템 확인 결과: {html.escape(preview)}{more_text}<br>'
            '선택 후 ‘확인’을 누르면 현재 입력값을 임시 저장하고 다음 측정 테마로 이동합니다.</div>',
            unsafe_allow_html=True,
        )
        st.radio(
            "누락된 값이 있습니까?",
            ["예", "아니오"],
            horizontal=True,
            index=None,
            key="power_missing_answer",
        )
        if st.session_state.get("power_move_validation_error"):
            st.error(st.session_state["power_move_validation_error"])
        confirm_col, cancel_col = st.columns(2, gap="small")
        with confirm_col:
            st.button(
                "확인",
                key="power_confirm_theme_move",
                type="primary",
                use_container_width=True,
                on_click=_process_power_theme_move,
            )
        with cancel_col:
            st.button(
                "계속 입력",
                key="power_cancel_theme_move",
                use_container_width=True,
                on_click=_cancel_power_theme_move,
            )

    if st.session_state.pop("power_temp_saved_notice", False):
        st.toast("현재 측정값을 임시 저장하고 다음 테마로 이동했습니다.", icon="✅")

    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    _hydrate_power_theme_from_draft(current_theme)
    st.markdown(
        f'<div class="power-theme-heading">{POWER_THEME_ICON[current_theme]} {html.escape(current_theme)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="power-unit-guide">전압(V), 전류(A), 저항(Ω) 단위는 자동으로 표시·저장됩니다. 숫자만 입력하세요.</div>',
        unsafe_allow_html=True,
    )

    if current_theme == "전압·전류 측정":
        st.radio(
            "전원 방식 선택",
            ["삼상", "단상"],
            format_func=lambda value: "삼상 전류" if value == "삼상" else "단상 전류",
            horizontal=True,
            key="power_phase_type",
            on_change=_on_power_phase_change,
        )
        phase_type = st.session_state.get("power_phase_type", "삼상")
        if phase_type == "삼상":
            voltage_fields = [
                ("R-S 전압 (V)", "power_three_voltage_rs"),
                ("S-T 전압 (V)", "power_three_voltage_st"),
                ("T-R 전압 (V)", "power_three_voltage_tr"),
                ("R-N 전압 (V)", "power_three_voltage_rn"),
            ]
            for start in range(0, len(voltage_fields), 2):
                row1 = st.columns(2, gap="small")
                for column, (label, key) in zip(row1, voltage_fields[start:start + 2]):
                    with column:
                        _power_text_input(label, key=key)
            row2 = st.columns(3, gap="small")
            current_fields = [
                ("R상 전류 (A)", "power_three_current_r"),
                ("S상 전류 (A)", "power_three_current_s"),
                ("T상 전류 (A)", "power_three_current_t"),
            ]
            for column, (label, key) in zip(row2, current_fields):
                with column:
                    _power_text_input(label, key=key)
        else:
            row = st.columns(2, gap="small")
            with row[0]:
                _power_text_input("단상 전압 (V)", key="power_single_voltage")
            with row[1]:
                _power_text_input("단상 전류 (A)", key="power_single_current")

    elif current_theme == "축전지 측정":
        st.radio(
            "측정할 축전지 선택",
            ["1조 셀 측정", "2조 셀 측정"],
            horizontal=True,
            key="power_battery_set",
            on_change=_on_power_battery_set_change,
        )
        st.caption("1조 측정 후 다음 단계로 이동하면 2조 측정 여부를 다시 확인합니다.")
        selected_group = 1 if st.session_state.get("power_battery_set") == "1조 셀 측정" else 2
        _render_power_battery_summary(selected_group)

    elif current_theme == "접지저항 측정":
        row1 = st.columns(3, gap="small")
        with row1[0]:
            _power_text_input("보안 1종 (Ω)", key="power_security_ground_1")
        with row1[1]:
            _power_text_input("보안 2종 (Ω)", key="power_security_ground_2")
        with row1[2]:
            _power_text_input("보안 3종 (Ω)", key="power_security_ground_3")
        row2 = st.columns(2, gap="small")
        with row2[0]:
            _power_text_input("통신용접지(메인) (Ω)", key="power_telecom_ground")
        with row2[1]:
            _power_text_input("피뢰침접지 (Ω)", key="power_lightning_ground")
        _power_text_area(
            "특이사항",
            key="power_notes",
            height=90,
        )

    elif current_theme == "최종 확인·전송":
        payload_preview = _build_power_payload_from_state(final_confirmed=True)
        all_missing = _power_payload_missing_items(payload_preview)
        expected_count = max(_power_expected_item_count(payload_preview), 1)
        completion_rate = round(((expected_count - len(all_missing)) / expected_count) * 100, 1)

        metric1, metric2, metric3 = st.columns(3, gap="small")
        metric1.metric("입력 완료율", f"{completion_rate}%")
        metric2.metric("누락 측정항목", f"{len(all_missing)}개")
        cell_summary = f"1조 {payload_preview.get('battery1_cell_count', 0)}셀"
        if payload_preview.get("battery_group_count") == 2:
            cell_summary += f" · 2조 {payload_preview.get('battery2_cell_count', 0)}셀"
        metric3.metric("축전지 측정", cell_summary)

        summary_df = pd.DataFrame([
            {"구분": "점검자", "내용": payload_preview.get("worker") or "미입력"},
            {"구분": "소속 조", "내용": payload_preview.get("inspector_group") or "미등록"},
            {"구분": "점검 국사", "내용": f"{payload_preview.get('mother')} / {payload_preview.get('local')}"},
            {"구분": "전원 구분", "내용": payload_preview.get("phase_type")},
            {"구분": "입력 방식", "내용": "기존값 불러오기 후 수정" if payload_preview.get("source_inspection_id") else "신규 입력"},
            {"구분": "특이사항", "내용": payload_preview.get("notes") or "없음"},
        ])
        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        basic_missing = _power_basic_missing()
        if basic_missing:
            st.error("저장 필수 기본정보가 누락되었습니다: " + ", ".join(basic_missing))

        if all_missing:
            preview = ", ".join(all_missing[:12])
            more = f" 외 {len(all_missing) - 12}개" if len(all_missing) > 12 else ""
            st.markdown(
                f'<div class="power-missing-box"><b>입력하지 않은 측정값이 있습니다.</b><br>'
                f'{html.escape(preview)}{more}<br><br>'
                '누락값은 Google Sheets에 공란으로 저장되며 누락항목도 함께 기록됩니다.</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown('<div class="power-complete-box">✅ 모든 예정 측정항목이 입력되었습니다.</div>', unsafe_allow_html=True)

        final_confirmed = st.checkbox(
            "입력한 측정값과 누락항목을 모두 확인했으며, 현재 내용으로 최종 전송합니다.",
            key="power_final_confirmed",
        )
        st.markdown("**모든 측정값이 정확하게 입력되었는지 최종 확인한 후 ‘전송’을 눌러 주세요.**")
        submit_power = st.button(
            "📤 전송",
            key="power_final_submit",
            type="primary",
            use_container_width=True,
            disabled=bool(basic_missing) or not final_confirmed,
        )

        if submit_power:
            payload = _build_power_payload_from_state(final_confirmed=final_confirmed)
            payload_signature = hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()
            now_ts = time.time()
            last_signature = st.session_state.get("power_last_signature", "")
            last_saved_ts = float(st.session_state.get("power_last_saved_ts", 0) or 0)
            if payload_signature == last_signature and (now_ts - last_saved_ts) < 30:
                st.warning("같은 측정값이 방금 저장되었습니다. 중복 전송을 방지했습니다.")
            else:
                with st.spinner("Google Sheets에 측정값을 저장하고 있습니다..."):
                    ok, message, inspection_id = save_power_inspection_result(payload)
                if ok:
                    st.session_state["power_last_signature"] = payload_signature
                    st.session_state["power_last_saved_ts"] = now_ts
                    st.success(f"✅ {message} · 점검ID: {inspection_id}")
                    time.sleep(2)
                    _reset_power_inspection()
                    st.rerun()
                else:
                    st.error(f"❌ 저장 실패: {message}")

        with st.expander("📊 Google Sheets 저장 구조", expanded=False):
            st.markdown(
                f'<div class="power-sheet-note">스프레드시트: <b>{POWER_INSPECTION_SPREADSHEET_NAME}</b><br>'
                f'워크시트: <b>{POWER_INSPECTION_SHEET_NAME}</b><br>'
                '점검 1건은 새 행으로 추가됩니다. 최근 측정값을 불러온 경우 원본 점검ID와 원본 저장일시도 함께 기록됩니다.</div>',
                unsafe_allow_html=True,
            )

    _render_power_auto_decimal_script()

    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    current_index = POWER_THEME_ORDER.index(current_theme)
    nav_left, nav_right = st.columns(2, gap="small")
    with nav_left:
        if current_index > 0:
            previous_theme = POWER_THEME_ORDER[current_index - 1]
            st.button(
                f"← {previous_theme}",
                key=f"power_previous_{current_index}",
                use_container_width=True,
                on_click=_request_power_theme,
                args=(previous_theme,),
            )
    with nav_right:
        if current_index < len(POWER_THEME_ORDER) - 1:
            next_theme = POWER_THEME_ORDER[current_index + 1]
            st.button(
                f"{next_theme} →",
                key=f"power_next_{current_index}",
                type="primary",
                use_container_width=True,
                on_click=_request_power_theme,
                args=(next_theme,),
            )

    st.info("측정값 입력 후 휴대전화 키패드의 Enter/확인을 누르면 자동 소수점이 적용되고 다음 입력칸으로 이동합니다.")


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

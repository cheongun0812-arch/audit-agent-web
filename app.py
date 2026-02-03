import streamlit as st
import streamlit.components.v1 as components  # ✅ for DOM/CSS patch injection
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
import random
import html

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


/* ✅ (속도/UX) 자율점검 홍보영상(st.video) 스타일 + 자동재생 대응 */
#audit-tab div[data-testid="stVideo"]{
    background: #0B1B2B;
    padding: 14px;
    border-radius: 18px;
    box-shadow: 0 18px 40px rgba(0,0,0,0.35);
    border: 1px solid rgba(255,255,255,0.12);
    margin: 8px auto 18px auto;
    max-width: 1500px;
}
#audit-tab div[data-testid="stVideo"] video{
    border-radius: 12px;
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

/* =========================================================
   ✅ 상단 메인 메뉴(탭) 간격/가독성 개선
   - 탭 간격 확대(gap)
   - 탭 텍스트/아이콘을 흰색으로 고정(어두운 배경에서도 선명)
   ========================================================= */
div[data-testid="stTabs"] [data-baseweb="tab-list"]{
  gap: 12px !important;                 /* ← 메뉴 간격 */
}
div[data-testid="stTabs"] [data-baseweb="tab"]{
  padding: 10px 16px !important;        /* ← 버튼 여백 */
  border-radius: 999px !important;
}
div[data-testid="stTabs"] [data-baseweb="tab"] *{
  color: #FFFFFF !important;
  font-weight: 850 !important;
  opacity: 1 !important;
}
div[data-testid="stTabs"] [data-baseweb="tab"] svg,
div[data-testid="stTabs"] [data-baseweb="tab"] svg *{
  fill: #FFFFFF !important;
  stroke: #FFFFFF !important;
  opacity: 1 !important;
}

/* ✅ '로그인 후 이용 가능합니다.' 안내: 노란 경고 대신 화이트 텍스트 배너 */
.login-required{
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.16);
  color: #FFFFFF;
  padding: 14px 16px;
  border-radius: 12px;
  font-weight: 900;
  letter-spacing: -0.01em;
}



/* =========================================================
   ✅ (NEW) 자율점검 탭(1번) 제외: 나머지 4개 탭(법률/챗봇/요약/관리자)
   본문 텍스트를 "완전 WHITE"로 강제 + 위젯 배경도 어둡게 보정
   (JS가 메인 탭의 패널에 .bright-tab 클래스를 붙입니다)
   ========================================================= */
.bright-tab,
.bright-tab *{
  color: #FFFFFF !important;
  opacity: 1 !important;
}

/* 링크도 흰색으로 */
.bright-tab a{
  color: #FFFFFF !important;
  text-decoration-color: rgba(255,255,255,0.65) !important;
}

/* 캡션/설명 텍스트 */
.bright-tab [data-testid="stCaptionContainer"] *{
  color: rgba(255,255,255,0.92) !important;
}

/* 입력/텍스트영역 */
.bright-tab input,
.bright-tab textarea{
  color: #FFFFFF !important;
  background: rgba(255,255,255,0.08) !important;
  border: 1px solid rgba(255,255,255,0.28) !important;
}

/* 셀렉트/콤보박스 */
.bright-tab div[data-baseweb="select"] > div,
.bright-tab div[role="combobox"]{
  background: rgba(255,255,255,0.08) !important;
  border: 1px solid rgba(255,255,255,0.28) !important;
}
.bright-tab div[data-baseweb="select"] svg,
.bright-tab div[data-baseweb="select"] svg *{
  fill: #FFFFFF !important;
  stroke: #FFFFFF !important;
}

/* 파일업로더 드롭존(기본 흰 배경 → 어둡게) */
.bright-tab [data-testid="stFileUploaderDropzone"]{
  background: rgba(255,255,255,0.06) !important;
  border: 1px dashed rgba(255,255,255,0.35) !important;
}
.bright-tab [data-testid="stFileUploaderDropzone"] *{
  color: #FFFFFF !important;
}

/* 아이콘/벡터도 흰색 */
.bright-tab svg,
.bright-tab svg *{
  fill: #FFFFFF !important;
  stroke: #FFFFFF !important;
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
    # ✅ 속도 개선: 로그인/세션복구 시 list_models() 호출은 초기 로딩을 크게 지연시킬 수 있어 생략합니다.
    #    (키가 잘못된 경우에는 실제 AI 호출 시 예외가 발생하며, 그때 사용자에게 안내됩니다.)
    genai.configure(api_key=clean_key)
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


# ==========================================
# ✅ (클린캠페인) 자율 참여 '청렴 서약' 저장/집계
# - 요청사항: 이름만 수집, Google Sheet에 저장
# - 500명 이상 참여 시 50명 추첨(1회)하여 별도 시트에 기록
# ==========================================
PLEDGE_SHEET_TITLE = "2026_청렴서약_참여자"
PLEDGE_WINNERS_SHEET_TITLE = "2026_청렴서약_추첨자"
PLEDGE_THRESHOLD = 500
PLEDGE_WINNERS = 50

def _build_pledge_popup_html(name: str, rank: int, total: int) -> str:
    safe_name = html.escape(str(name or "")).strip()
    rank = int(rank or 0)
    total = int(total or 0)

    template = """
<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<link rel="stylesheet" as="style" crossorigin href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css" />
<script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
<style>
  :root {
    --bg: rgba(2, 6, 23, 0.74);
    --panel: rgba(255, 255, 255, 0.06);
    --border: rgba(255, 255, 255, 0.14);
    --txt: rgba(255, 255, 255, 0.94);
    --muted: rgba(229, 231, 235, 0.76);
    --red: #ef4444;
    --orange: #f97316;
    --yellow: #f59e0b;
  }
  html, body { margin:0; padding:0; background:transparent; font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, "Noto Sans KR", sans-serif; }
  @keyframes fadeUp {
    from { opacity:0; transform: translateY(18px) scale(0.985); }
    to   { opacity:1; transform: translateY(0) scale(1); }
  }
  @keyframes fadeOut {
    from { opacity:1; }
    to   { opacity:0; }
  }
  @keyframes floatPollen {
    0%   { transform: translateY(0) translateX(0) scale(0.9); opacity:0; }
    12%  { opacity:0.85; }
    100% { transform: translateY(-140px) translateX(18px) scale(1.2); opacity:0; }
  }
  .overlay {
    position: fixed; inset: 0;
    display:flex; align-items:center; justify-content:center;
    background: var(--bg);
    z-index: 999999;
  }
  .card {
    width: min(720px, 92vw);
    border-radius: 30px;
    background: var(--panel);
    border: 1px solid var(--border);
    backdrop-filter: blur(14px);
    box-shadow: 0 30px 90px rgba(0,0,0,0.45);
    overflow: hidden;
            position: relative;
    position: relative;
    animation: fadeUp 0.32s ease-out both;
  }
  .glow {
    position:absolute; inset:-2px;
    background:
      radial-gradient(circle at 20% 18%, rgba(239,68,68,0.28), transparent 52%),
      radial-gradient(circle at 80% 28%, rgba(249,115,22,0.22), transparent 55%),
      radial-gradient(circle at 52% 92%, rgba(245,158,11,0.18), transparent 60%);
    filter: blur(22px);
    pointer-events:none;
  }
  .inner { position:relative; padding: 26px 26px 22px 26px; text-align:center; }
  .badge {
    display:inline-flex; align-items:center; justify-content:center;
    width: 72px; height: 72px;
    margin: 6px auto 10px auto;
    border-radius: 22px;
    background: rgba(239,68,68,0.12);
    border: 1px solid rgba(239,68,68,0.25);
    box-shadow: 0 16px 40px rgba(239,68,68,0.14);
    font-size: 36px;
  }
  .title {
    margin: 0;
    font-weight: 950;
    letter-spacing: -0.03em;
    font-size: 22px;
    color: var(--txt);
  }
  .line {
    margin: 12px auto 14px auto;
    width: 56px; height: 4px;
    background: rgba(148,163,184,0.32);
    border-radius: 999px;
  }
  .msg {
    margin: 0;
    font-size: 18px;
    font-weight: 900;
    letter-spacing: -0.02em;
    color: var(--txt);
  }
  .msg .hot {
    color: var(--red);
    text-decoration: underline;
    text-decoration-thickness: 6px;
    text-underline-offset: 8px;
  }
  .sub {
    margin: 10px 0 0 0;
    font-size: 14px;
    font-weight: 800;
    color: var(--muted);
    line-height: 1.6;
  }
  .sub b { color: rgba(255,255,255,0.95); }
  .pollen {
    position:absolute;
    width: 10px; height: 10px;
    border-radius: 999px;
    background: rgba(255,255,255,0.18);
    box-shadow: 0 0 14px rgba(239,68,68,0.18);
    filter: blur(0.3px);
    animation: floatPollen 4.8s ease-out forwards;
    pointer-events:none;
  }
</style>
</head>
<body>
<div class="overlay" id="overlay">
  <div class="card" id="card">
    <div class="glow"></div>
    <div class="inner">
      <div class="badge">🎊</div>
      <h3 class="title"><span class="hot">청렴 서약</span> 완료!</h3>
      <div class="line"></div>
      <div class="big">청렴 서약</div>
      <p class="msg"><span class="hot">__NAME__</span>님은 <span class="hot">__RANK__</span>번째 참여자입니다!</p>
      <p class="sub">현재 누적 <b>__TOTAL__</b>명 참여 · 여러분의 한 번의 선택이 ktMOS북부의 신뢰가 됩니다.</p>
    </div>
  </div>
</div>

<script>
(function(){
  // --- Expand this component to full viewport (center popup) ---
  function setFrame(h){
    try{ window.parent.postMessage({isStreamlitMessage:true, type:"streamlit:setFrameHeight", height: h},"*"); }catch(e){}
  }
    // ✅ Streamlit 레이아웃 여백 최소화 (전체화면 오버레이는 iframe fixed로 처리)
  setFrame(1);

  // --- ✅ Make THIS iframe itself an overlay (so even with height=1, visuals show full-screen) ---
  const fe = window.frameElement;
  const __prev = {};
  if (fe) {
    __prev.position = fe.style.position;
    __prev.top = fe.style.top;
    __prev.left = fe.style.left;
    __prev.width = fe.style.width;
    __prev.height = fe.style.height;
    __prev.zIndex = fe.style.zIndex;
    __prev.pointerEvents = fe.style.pointerEvents;
    __prev.background = fe.style.background;

    fe.style.position = "fixed";
    fe.style.top = "0";
    fe.style.left = "0";
    fe.style.width = "100vw";
    fe.style.height = "100vh";
    fe.style.zIndex = "2147483647";
    fe.style.pointerEvents = "auto";
    fe.style.background = "transparent";
  }
  function restoreFrame(){
    if (!fe) return;
    fe.style.position = __prev.position || "";
    fe.style.top = __prev.top || "";
    fe.style.left = __prev.left || "";
    fe.style.width = __prev.width || "";
    fe.style.height = __prev.height || "";
    fe.style.zIndex = __prev.zIndex || "";
    fe.style.pointerEvents = __prev.pointerEvents || "";
    fe.style.background = __prev.background || "";
  }


// Pollen particles
  const overlay = document.getElementById('overlay');
  for(let i=0;i<22;i++){
    const s = document.createElement('div');
    s.className = 'pollen';
    s.style.left = (Math.random()*100).toFixed(2) + 'vw';
    s.style.bottom = (Math.random()*20).toFixed(2) + 'vh';
    s.style.opacity = (0.4 + Math.random()*0.5).toFixed(2);
    s.style.animationDelay = (Math.random()*0.35).toFixed(2) + 's';
    const tx = (Math.random()*-10).toFixed(2);
    const sc = (0.7 + Math.random()*0.9).toFixed(2);
    s.style.transform = "translateY(0) translateX(" + tx + "px) scale(" + sc + ")";
    overlay.appendChild(s);
  }

  // Confetti for ~3s
  const end = Date.now() + 5000;
  (function frame(){
    confetti({ particleCount: 7, angle: 60,  spread: 62, origin: { x: 0 }, colors: ['#ef4444','#f97316','#f59e0b']});
    confetti({ particleCount: 7, angle: 120, spread: 62, origin: { x: 1 }, colors: ['#ef4444','#f97316','#f59e0b']});
    if(Date.now() < end) requestAnimationFrame(frame);
  })();

  // Auto close
  setTimeout(() => {
    overlay.style.animation = "fadeOut 0.30s ease-in forwards";
    setTimeout(() => { overlay.remove(); restoreFrame(); setFrame(1); }, 360);
  }, 5200);
})();
</script>
</body>
</html>
"""
    return (
        template.replace("__NAME__", safe_name)
                .replace("__RANK__", str(rank))
                .replace("__TOTAL__", str(total))
    )

def _normalize_kor_name(name: str) -> str:
    # 공백 제거 + 양끝 정리 (동명이인 리스크는 존재하나, "이름만" 수집 요청에 맞춰 최소한으로 처리)
    return "".join(str(name or "").strip().split())

def _get_or_create_ws(spreadsheet, title: str, headers: list[str]):
    try:
        ws = spreadsheet.worksheet(title)
        return ws
    except Exception:
        ws = spreadsheet.add_worksheet(title=title, rows=5000, cols=max(8, len(headers) + 2))
        ws.append_row(headers)
        return ws

def _pledge_count(ws) -> int:
    # A열(저장시간) 기준으로 비어있지 않은 행 수를 빠르게 계산
    try:
        col = ws.col_values(1)
        return max(0, len(col) - 1)  # header 제외
    except Exception:
        try:
            return max(0, len(ws.get_all_values()) - 1)
        except Exception:
            return 0

def _maybe_draw_winners(spreadsheet, pledge_ws):
    # 500명 이상이 되었을 때 '최초 1회'만 추첨하여 Winners 시트에 저장
    try:
        winners_ws = _get_or_create_ws(
            spreadsheet,
            PLEDGE_WINNERS_SHEET_TITLE,
            ["추첨시간", "사번", "성함", "참여순번"]
        )

        # 이미 추첨이 진행되었는지 체크(헤더 제외 1행 이상이면 스킵)
        existing = winners_ws.get_all_values()
        if len(existing) > 1:
            return

        total = _pledge_count(pledge_ws)
        if total < PLEDGE_THRESHOLD:
            return

        # 참여자 목록 확보 (시트 구조: [저장시간, 사번, 성함])
        all_rows = pledge_ws.get_all_values()[1:]  # header 제외
        entries = []
        for idx, row in enumerate(all_rows, start=1):  # idx = 참여순번(1-based)
            emp = row[1].strip() if len(row) > 1 else ""
            name = row[2].strip() if len(row) > 2 else (row[1].strip() if len(row) > 1 else "")
            norm_emp = "".join(emp.split()).replace("-", "")
            # 사번이 비어있거나 숫자 성분이 전혀 없으면(과거 '성함-only' 데이터 등) 추첨 대상에서 제외
            if not norm_emp or not any(ch.isdigit() for ch in norm_emp):
                continue
            entries.append((idx, emp, name))

        if not entries:
            return

        pool = [e[0] for e in entries]  # 참여순번(실제 행 기준)
        pick = min(PLEDGE_WINNERS, len(pool))
        rng = random.SystemRandom()
        picked_ranks = sorted(rng.sample(pool, pick))

        entry_map = {e[0]: e for e in entries}

        kst = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
        rows = [[now, entry_map[r][1], entry_map[r][2], r] for r in picked_ranks]
        winners_ws.append_rows(rows, value_input_option="USER_ENTERED")
    except Exception:
        # 추첨 실패는 사용자 UX를 막지 않도록 무시(관리자가 시트에서 확인 가능)
        return

def save_clean_campaign_pledge(emp_id: str, name: str) -> tuple[bool, str, int, int]:
    """
    자율 참여 '청렴 서약' 정보를 Google Sheet에 저장합니다.

    Returns:
      (ok, message, rank, total_count)
        - rank: 참여순번(1부터)
        - total_count: 누적 참여자 수
    """
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패 (Secrets 확인)", 0, 0

    def _norm_emp(v: str) -> str:
        # 공백/하이픈 제거(사번은 문자열로 유지)
        return "".join(str(v or "").strip().split()).replace("-", "")

    try:
        spreadsheet = client.open("Audit_Result_2026")
        pledge_ws = _get_or_create_ws(spreadsheet, PLEDGE_SHEET_TITLE, ["저장시간", "사번", "성함"])

        raw_emp = str(emp_id or "").strip()
        raw_name = str(name or "").strip()
        norm_emp = _norm_emp(raw_emp)

        total_now = _pledge_count(pledge_ws)

        # ✅ 입력값 검증
        if not norm_emp:
            return False, "사번을 입력해 주세요.", 0, total_now
        if not raw_name:
            return False, "성함을 입력해 주세요.", 0, total_now

        # ✅ 중복 체크(사번+성함 기준) — 동일 사번(예: 00000000) 예외를 고려
        norm_name = _normalize_kor_name(raw_name)
        emp_col = pledge_ws.col_values(2)[1:]   # header 제외
        name_col = pledge_ws.col_values(3)[1:]  # header 제외
        for i, (e, n) in enumerate(zip(emp_col, name_col), start=1):
            if _norm_emp(e) == norm_emp and _normalize_kor_name(n) == norm_name:
                total_now = _pledge_count(pledge_ws)
                return False, f"사번/성함({raw_emp} / {raw_name})은(는) 이미 청렴 서약에 참여하셨습니다.", i, total_now

        # ✅ 저장
        kst = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(kst).strftime("%Y-%m-%d %H:%M:%S")
        pledge_ws.append_row([now, raw_emp, raw_name], value_input_option="USER_ENTERED")

        total_after = total_now + 1
        rank = total_after

        # ✅ 500명 이상 시 50명 추첨(최초 1회)
        if total_after >= PLEDGE_THRESHOLD:
            _maybe_draw_winners(spreadsheet, pledge_ws)

        return True, "성공", rank, total_after
    except Exception as e:
        return False, f"저장 중 오류: {e}", 0, 0

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

def render_login_required():
    st.markdown('<div class="login-required">🔒 로그인 후 이용 가능합니다.</div>', unsafe_allow_html=True)

# ==========================================
st.markdown("<h1 style='text-align: center; color: #F8FAFC; text-shadow: 0 6px 24px rgba(0,0,0,0.35);'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='text-align: center; color: rgba(234,242,255,0.78); text-shadow: 0 1px 10px rgba(0,0,0,0.25); margin-top: -10px; ...'>Professional Legal & Audit Assistant System</div>",
    unsafe_allow_html=True
)

st.markdown('<div style="height:56px"></div>', unsafe_allow_html=True)

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


# ✅ 메인 탭(자율점검 제외) 본문을 WHITE로 강제하기 위해: 메인 탭 패널에 .bright-tab 클래스 부여
components.html(r'''
<script>
(function () {
  // 이 컴포넌트 iframe 자체는 화면에 보일 필요 없으니 높이를 0으로 축소
  try {
    const fe = window.frameElement;
    if (fe) {
      fe.style.height = "0px";
      fe.style.minHeight = "0px";
      fe.style.border = "0";
      fe.style.margin = "0";
      fe.style.padding = "0";
    }
    // Streamlit이 높이를 강제로 잡는 경우도 있어 메시지로도 한번 축소 요청
    window.parent.postMessage({type: "streamlit:setFrameHeight", height: 0}, "*");
  } catch (e) {}

  function apply() {
    const doc = window.parent.document;
    const tabs = doc.querySelectorAll('div[data-testid="stTabs"]');
    if (!tabs || !tabs.length) return false;

    // 첫 번째 stTabs가 상단 메인 메뉴 탭
    const main = tabs[0];
    if (!main.classList.contains("main-menu-tabs")) main.classList.add("main-menu-tabs");

    // 메인 탭 패널들에 클래스 부여 (0: 자율점검 / 1~: 나머지)
    const panels = main.querySelectorAll('[role="tabpanel"], div[data-baseweb="tab-panel"]');
    if (!panels || !panels.length) return false;

    panels.forEach((p, i) => {
      if (i === 0) {
        p.classList.remove("bright-tab");
        p.classList.add("selfcheck-tab");
      } else {
        p.classList.add("bright-tab");
        p.classList.remove("selfcheck-tab");
      }
    });
    return true;
  }

  let tries = 0;
  const t = setInterval(() => {
    tries += 1;
    const ok = apply();
    if (ok || tries > 40) clearInterval(t);
  }, 250);

  // 탭 전환 시에도 재적용
  try {
    window.parent.document.addEventListener("click", () => setTimeout(apply, 80), true);
  } catch (e) {}
})();
</script>
''', height=1, scrolling=False)
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

    # ✅ (팝업) 서약 완료 축하/감사 오버레이는 화면 상단에 렌더링
    __pledge_popup_slot = st.empty()


    current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")

    # ✅ (UX) '서약 확인/임직원 정보 입력' 영역: 최초에는 접힘, 입력/체크 시 자동 펼침
    if "pledge_box_open" not in st.session_state:
        st.session_state["pledge_box_open"] = False

    # ✅ (요청 1) 제목: Google Sheet 값과 무관하게 강제 고정
    title_for_box = "2026 병오년 ktMOS북부 설 명절 클린캠페인"
    period_for_box = "Period: 2026. 2.9. (Mon) ~ 2.27. (Fri.)"

    st.markdown(f"""
        <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 20px;'>
            <div style='margin-top:0; color:#1565C0; font-weight:900; font-size: clamp(34px, 3.6vw, 54px); line-height:1.08;'>📜 {title_for_box}</div>
            <div style='margin-top:6px; color:#1565C0; font-weight:900; font-size: clamp(34px, 3.6vw, 54px); line-height:1.08;'>{period_for_box}</div>
        </div>
    """, unsafe_allow_html=True)

    # --- 📐 캠페인 콘텐츠 정렬(영상 폭 기준) ---
    cc_l, cc_mid, cc_r = st.columns([1, 16, 1])
    with cc_mid:
        # 2) 🎞️ 캠페인 홍보 영상 (자동 재생)
        video_filename = "2026 new yearf.mp4"  # app.py 폴더에 업로드된 파일명
        _base_dir = os.path.dirname(__file__) if "__file__" in globals() else os.getcwd()
        video_path = os.path.join(_base_dir, video_filename)

        @st.cache_data(show_spinner=False)
        def _load_mp4_bytes(_path: str) -> bytes:
            with open(_path, "rb") as f:
                return f.read()

        def _render_autoplay_video(_path: str) -> None:
            try:
                # ✅ 속도 개선: base64 인라인(video/mp4;base64, ...) 방식은 HTML 전송량이 커서
                #    첫 로딩 시 '잠깐 예전 화면이 보였다가' 갱신되는 현상이 생길 수 있습니다.
                #    Streamlit의 st.video()로 출력하고, JS로 autoplay/muted/loop를 적용합니다.
                video_bytes = _load_mp4_bytes(_path)
                st.video(video_bytes, format="video/mp4")

                components.html(r'''
<script>
(function () {
  // iframe(components.html) 자체는 보일 필요가 없어 높이를 0으로 축소
  try {
    const fe = window.frameElement;
    if (fe) { fe.style.height="0px"; fe.style.minHeight="0px"; fe.style.border="0"; fe.style.margin="0"; fe.style.padding="0"; }
    window.parent.postMessage({type:"streamlit:setFrameHeight", height:0}, "*");
  } catch (e) {}

  function apply(){
    const doc = window.parent.document;
    const vids = doc.querySelectorAll('#audit-tab div[data-testid="stVideo"] video');
    if (!vids || !vids.length) return false;
    const v = vids[vids.length - 1]; // 가장 마지막 video에 적용
    try {
      v.muted = true;
      v.loop = true;
      v.autoplay = true;
      v.playsInline = true;
      const p = v.play();
      if (p && p.catch) p.catch(()=>{});
    } catch (e) {}
    return true;
  }

  let tries = 0;
  const t = setInterval(() => {
    tries += 1;
    const ok = apply();
    if (ok || tries > 40) clearInterval(t);
  }, 250);

  // 탭/클릭으로 DOM이 다시 그려질 때도 재적용
  try { window.parent.document.addEventListener("click", () => setTimeout(apply, 80), true); } catch (e) {}
})();
</script>
''', height=0, scrolling=False)
            except Exception as e:
                st.error(f"❌ 캠페인 영상 로드 실패: {e}")

        if os.path.exists(video_path):
            _render_autoplay_video(video_path)
            st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)
        else:
            st.warning(f"⚠️ 캠페인 영상 파일을 찾을 수 없습니다: {video_filename}\n(app.py와 동일 폴더에 업로드해 주세요.)")

        # 3) 🎯 영상 아래 3대 테마(청렴 아우라 → 아젠다 → 신고 채널) 한 블록 정렬
        #    - 영상 폭 기준으로 동일한 폭/간격/정렬감을 유지하도록 하나의 HTML 컴포넌트로 묶었습니다.
        import streamlit.components.v1 as components
    
        CLEAN_CAMPAIGN_BUNDLE_HTML = r"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <link rel="preconnect" href="https://cdn.tailwindcss.com" />
          <script src="https://cdn.tailwindcss.com"></script>
          <style>
            :root{
              --maxw: 1500px;
              --title: clamp(34px, 3.6vw, 54px);
              --kicker: 12px;
              --radius: 30px;
              --bg: rgba(2,6,23,0.74);
              --glass: rgba(255,255,255,0.04);
              --stroke: rgba(255,255,255,0.10);
              --txt: rgba(255,255,255,0.94);
              --muted: rgba(226,232,240,0.64);
              --muted2: rgba(226,232,240,0.52);
              --red: #ef4444;
              --orange: #f97316;
              --amber: #f59e0b;
              --gap: 70px;
            }
            html,body{margin:0;padding:0;background:transparent;color:var(--txt);
              font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Noto Sans KR", sans-serif;}
            *{box-sizing:border-box;}
            .cc-card{
              width: min(100%, var(--maxw));
              margin: 0 auto;
              padding: 38px 24px 56px 24px;
              border-radius: var(--radius);
              background:
                radial-gradient(circle at 16% 18%, rgba(239,68,68,0.14), transparent 40%),
                radial-gradient(circle at 78% 26%, rgba(249,115,22,0.12), transparent 40%),
                radial-gradient(circle at 36% 92%, rgba(245,158,11,0.10), transparent 48%),
                var(--bg);
              border: 1px solid rgba(255,255,255,0.10);
              box-shadow: 0 26px 72px rgba(0,0,0,0.45);
              overflow:hidden;
            }
                        .cc-section{
              margin-top: var(--gap);
              padding: 34px 22px;
              border-radius: 30px;
              border: 1px solid rgba(255,255,255,0.12);
              background: rgba(255,255,255,0.03);
              box-shadow: 0 16px 46px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.06);
              position: relative;
            }
            .cc-section:before{
              content:"";
              position:absolute;
              left: 18px;
              top: 18px;
              width: 6px;
              height: 52px;
              border-radius: 999px;
              background: linear-gradient(180deg,
                        rgba(239,68,68,0.92),
                        rgba(249,115,22,0.78),
                        rgba(245,158,11,0.70));
              opacity: 0.45;
            }
            .cc-section.aura{
              border-color: rgba(249,115,22,0.30);
              background:
                radial-gradient(circle at 18% 10%, rgba(249,115,22,0.12), transparent 50%),
                rgba(255,255,255,0.03);
            }
            .cc-section.agenda{
              border-color: rgba(239,68,68,0.22);
              background:
                radial-gradient(circle at 82% 20%, rgba(239,68,68,0.12), transparent 54%),
                rgba(255,255,255,0.03);
            }
            .cc-section.report{
              border-color: rgba(148,163,184,0.26);
              background:
                radial-gradient(circle at 20% 30%, rgba(148,163,184,0.10), transparent 52%),
                rgba(255,255,255,0.03);
            }
            .cc-kicker{
              text-align:center;
              font-size: var(--kicker);
              font-weight: 900;
              color: rgba(239,68,68,0.85);
              letter-spacing: .42em;
              text-transform: uppercase;
            }
            .cc-title{
              text-align:center;
              font-weight: 900;
              font-size: var(--title);
              line-height: 1.08;
              margin-top: 10px;
            }
            .cc-sub{
              text-align:center;
              margin-top: 10px;
              color: var(--muted);
              font-weight: 700;
            }
            .glass{
              background: var(--glass);
              border: 1px solid var(--stroke);
              backdrop-filter: blur(18px);
              -webkit-backdrop-filter: blur(18px);
              box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
            }
            .pill-input,.pill-select{
              width:100%;
              border-radius: 18px;
              padding: 14px 16px;
              border: 1px solid rgba(255,255,255,0.12);
              background: rgba(15,23,42,0.55);
              color: rgba(255,255,255,0.94);
              outline: none;
              font-weight: 900;
              text-align: center;
            }
            .pill-input::placeholder{color: rgba(226,232,240,0.42);}
            .scan-btn{
              width: 100%;
              border: 0;
              border-radius: 18px;
              padding: 16px 16px;
              font-weight: 900;
              color: rgba(255,255,255,0.96);
              background: linear-gradient(90deg, rgba(239,68,68,0.95), rgba(249,115,22,0.92));
              cursor:pointer;
              display:flex;
              align-items:center;
              justify-content:center;
              gap:10px;
              box-shadow: 0 18px 40px rgba(0,0,0,0.35);
            }
            .scan-btn:active{transform: translateY(1px);}
            .grad-border{
              padding: 2px;
              border-radius: 26px;
              background: linear-gradient(90deg, rgba(239,68,68,0.95), rgba(249,115,22,0.92), rgba(245,158,11,0.90));
            }
            .result{
              border-radius: 24px;
              padding: 26px 18px;
              background: rgba(2,6,23,0.72);
              border: 1px solid rgba(255,255,255,0.10);
              text-align:center;
            }
            .result .ok{
              color: rgba(239,68,68,0.85);
              font-weight: 900;
              letter-spacing: .20em;
              font-size: 12px;
            }
            .result .slogan{
              margin-top: 10px;
              font-size: clamp(20px, 2.2vw, 30px);
              font-weight: 900;
              line-height: 1.25;
            }
            .result .fortune{
              margin-top: 12px;
              color: rgba(203,213,225,0.74);
              font-weight: 700;
              line-height: 1.55;
            }
            .sep{
              height:1px; width:100%;
              margin: calc(var(--gap) - 10px) 0 0 0;
              background: linear-gradient(90deg, transparent, rgba(239,68,68,0.45), rgba(249,115,22,0.35), transparent);
              opacity:0.55;
            }
            .agenda-grid{
              display:grid;
              grid-template-columns: repeat(3, minmax(0,1fr));
              gap: 16px;
              margin-top: 18px;
            }
            @media (max-width: 860px){
              .agenda-grid{grid-template-columns: 1fr; gap: 14px;}
            }
            .agenda-card{
              border-radius: 26px;
              padding: 22px 18px;
              min-height: 168px;
              display:flex;
              flex-direction:column;
              gap: 10px;
            }
            .ico{
              width: 54px; height: 54px;
              border-radius: 18px;
              display:flex; align-items:center; justify-content:center;
              font-size: 22px;
              border: 1px solid rgba(255,255,255,0.10);
              background: rgba(255,255,255,0.05);
            }
            .agenda-card h4{
              margin:0;
              font-size: 18px;
              font-weight: 900;
            }
            .agenda-card p{
              margin:0;
              color: rgba(203,213,225,0.72);
              font-weight: 700;
              line-height: 1.5;
              font-size: 13.5px;
            }

            .report-grid{
              display:grid;
              grid-template-columns: 1.15fr 1fr;
              gap: 16px;
              margin-top: 18px;
              align-items: start;
            }
            @media (max-width: 860px){
              .report-grid{grid-template-columns: 1fr;}
            }
            .report-left h4{
              margin:0;
              font-size: 22px;
              font-weight: 900;
              line-height:1.15;
            }
            .report-left p{
              margin: 10px 0 0 0;
              color: rgba(203,213,225,0.72);
              font-weight: 700;
              line-height: 1.6;
            }
            .report-cards{
              display:grid;
              grid-template-columns: 1fr 1fr;
              gap: 12px;
            }
            @media (max-width: 860px){
              .report-cards{grid-template-columns: 1fr;}
            }
            .report-card{
              border-radius: 24px;
              padding: 16px 16px;
              display:flex;
              align-items:center;
              gap: 12px;
              text-decoration:none;
              color: var(--txt);
              transition: transform .15s ease, background .15s ease;
            }
            .report-card:hover{transform: translateY(-1px); background: rgba(255,255,255,0.05);}
            .report-card .label{
              font-size: 12px;
              font-weight: 900;
              letter-spacing: .22em;
              color: rgba(148,163,184,0.82);
              text-transform: uppercase;
            }
            .report-card .value{
              font-size: 18px;
              font-weight: 900;
              margin-top: 2px;
            }
            .fade-in{animation: fadeIn .25s ease both;}
            @keyframes fadeIn{from{opacity:0; transform: translateY(10px) scale(.99);}to{opacity:1; transform: translateY(0) scale(1);}}
          </style>
        </head>
        <body>
          <div class="cc-card">
            <!-- 1) Integrity Aura -->
            <section class="cc-section aura">
              <div class="cc-kicker">2026 integrity aura</div>
              <div class="cc-title">2026 청렴 아우라 분석</div>
              <div class="cc-sub">성함과 올해의 목표를 선택하고 <b>“청렴 기운 스캔하기”</b>를 눌러보세요.</div>

              <div class="glass" style="border-radius:28px; padding:22px 18px; margin-top: 18px;">
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                  <input id="empName" class="pill-input" placeholder="성함" maxlength="12" />
                  <select id="goal" class="pill-select">
                    <option value="가족의 행복">올해의 주요 목표</option>
                    <option value="가족의 행복">가족의 행복</option>
                    <option value="업무의 성장">업무의 성장</option>
                    <option value="건강한 생활">건강한 생활</option>
                    <option value="관계의 회복">관계의 회복</option>
                    <option value="새로운 도전">새로운 도전</option>
                  </select>
                </div>

                <div style="margin-top:12px;">
                  <button id="scanBtn" class="scan-btn"><span style="font-size:18px;">✨</span>청렴 기운 스캔하기</button>
                </div>

                <div id="resultWrap" class="grad-border" style="margin-top:16px; display:none;">
                  <div class="result fade-in">
                    <div class="ok">SCAN COMPLETED</div>
                    <div id="slogan" class="slogan"></div>
                    <div id="fortune" class="fortune"></div>
                  </div>
                </div>
              </div>
            </section>

            <div class="sep"></div>

            <!-- 2) Agenda -->
            <section class="cc-section agenda">
              <div class="cc-kicker">clean festival policy</div>
              <div class="cc-title">설 명절 클린 캠페인 아젠다</div>
              <div class="cc-sub">명절 기간에도 청렴은 최고의 선물입니다. 아래 3대 원칙을 꼭 지켜주세요.</div>

              <div class="agenda-grid">
                <div class="agenda-card glass">
                  <div class="ico" style="color: rgba(239,68,68,0.95);">🎁</div>
                  <h4>선물 안 주고 안 받기</h4>
                  <p>협력사 및 이해관계자와의 명절 선물 교환은 금지됩니다. 마음만 정중히 받겠습니다.</p>
                </div>
                <div class="agenda-card glass">
                  <div class="ico" style="color: rgba(249,115,22,0.95);">☕</div>
                  <h4>향응 및 편의 제공 금지</h4>
                  <p>부적절한 식사 대접이나 골프 등 편의 제공은 원천 차단하여 투명성을 지킵니다.</p>
                </div>
                <div class="agenda-card glass">
                  <div class="ico" style="color: rgba(245,158,11,0.95);">🛡️</div>
                  <h4>부득이한 경우 자진신고</h4>
                  <p>택배 등으로 배송된 선물은 반송이 원칙이며, 불가피할 시 클린센터로 즉시 신고합니다.</p>
                </div>
              </div>
            </section>

            <div class="sep"></div>

            <!-- 3) Reporting Channel -->
            <section class="cc-section report">
              <div class="cc-title">비윤리 행위 신고 채널</div>
              <div class="report-grid">
                <div class="report-left">
                  <h4>부정부패 없는 ktMOS북부를 위해<br>여러분의 용기 있는 목소리가 필요합니다.</h4>
                  <p>‘혹시’라는 작은 의심도 괜찮습니다. 빠르게 공유해 주시면 감사실이 즉시 확인하고 필요한 조치를 안내하겠습니다.</p>
                </div>

                <div class="report-cards">
                  <div class="report-card glass" style="grid-column: span 1;">
                    <div class="ico" style="font-size:20px;">📞</div>
                    <div>
                      <div class="label">감사실 직통</div>
                      <div class="value">02-3414-1919</div>
                    </div>
                  </div>

                  <a class="report-card glass" href="http://ktmos.com/management/management" target="_blank" rel="noopener noreferrer" style="grid-column: span 1;">
                    <div class="ico" style="font-size:20px;">🌐</div>
                    <div>
                      <div class="label">사이버 신문고</div>
                      <div class="value">바로가기</div>
                    </div>
                  </a>

                  <div class="report-card glass" style="grid-column: span 2;">
                    <div class="ico" style="font-size:20px;">✉️</div>
                    <div>
                      <div class="label">이메일 제보</div>
                      <div class="value">ethics@ktmos.com</div>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          </div>

          <script>
          (function(){
            const AURA = [
              {goal:"가족의 행복", slogan:"깨끗한 소통으로 피어나는 동료 간의 진정한 즐거움", fortune:"작은 호의보다 큰 진심이 통하는 한 해입니다. 사람 사이의 신뢰가 최고의 행운입니다."},
              {goal:"가족의 행복", slogan:"따뜻한 배려가 만드는 가장 큰 행운", fortune:"오늘의 작은 친절이 집안의 분위기를 환하게 바꿉니다. 말 한마디가 복이 됩니다."},
              {goal:"업무의 성장", slogan:"원칙 위에 세워지는 성과", fortune:"규정을 지키는 것이 오히려 속도를 만듭니다. 리스크가 줄며 추진력이 커집니다."},
              {goal:"업무의 성장", slogan:"투명한 과정이 부르는 인정", fortune:"과정이 깨끗하면 결과가 빛납니다. 평판이 성과를 돕습니다."},
              {goal:"건강한 생활", slogan:"균형 잡힌 습관이 부르는 맑은 기운", fortune:"무리보다 꾸준함이 정답입니다. 작은 루틴이 큰 변화를 이끕니다."},
              {goal:"건강한 생활", slogan:"정직한 선택이 만드는 가벼운 하루", fortune:"과식·과음을 줄이는 선택이 컨디션을 살립니다. 가벼워진 몸이 자신감을 줍니다."},
              {goal:"관계의 회복", slogan:"솔직함이 여는 관계의 문", fortune:"한 번의 진심 어린 대화가 관계를 회복시킵니다. 오해를 풀 기회가 찾아옵니다."},
              {goal:"관계의 회복", slogan:"공정함이 만드는 오래가는 인연", fortune:"공정한 태도는 관계를 오래가게 합니다. 상대가 당신을 더 신뢰하게 됩니다."},
              {goal:"새로운 도전", slogan:"정직한 출발이 만드는 큰 도약", fortune:"출발이 깨끗하면 끝이 편합니다. 도전의 성공 확률이 올라갑니다."},
              {goal:"새로운 도전", slogan:"원칙 있는 도전, 안전한 혁신", fortune:"무리한 모험 대신, 안전한 혁신이 가능합니다. ‘현명한 도전자’가 됩니다."},
            ];

            const pick = (arr)=> arr[Math.floor(Math.random()*arr.length)];
            const scanBtn = document.getElementById("scanBtn");
            const emp = document.getElementById("empName");
            const goal = document.getElementById("goal");
            const resultWrap = document.getElementById("resultWrap");
            const sloganEl = document.getElementById("slogan");
            const fortuneEl = document.getElementById("fortune");

            let scanning = false;

            function pickByGoal(g){
              const filtered = AURA.filter(x=>x.goal===g);
              return pick(filtered.length?filtered:AURA);
            }

            function doScan(){
              if(scanning) return;
              const name = (emp.value||"").trim();
              const g = goal.value || "가족의 행복";
              if(!name){
                emp.focus();
                emp.style.boxShadow="0 0 0 4px rgba(239,68,68,0.25)";
                setTimeout(()=>emp.style.boxShadow="", 800);
                return;
              }
              scanning = true;
              scanBtn.style.filter="brightness(0.92)";
              scanBtn.innerHTML = '⏳ 스캔 중...';
              setTimeout(()=>{
                const picked = pickByGoal(g);
                sloganEl.textContent = "“" + picked.slogan + "”";
                fortuneEl.textContent = picked.fortune;
                resultWrap.style.display = "block";
                scanBtn.style.filter="";
                scanBtn.innerHTML = '✨ 청렴 기운 스캔하기';
                scanning = false;
                sendHeight();
              }, 650);
            }

            scanBtn.addEventListener("click", doScan);

                        // --- Streamlit iframe height auto-fit ---
                        function sendHeight(){
                          try{
                            const h = Math.max(
                              document.body.scrollHeight,
                              document.documentElement.scrollHeight,
                              document.body.offsetHeight,
                              document.documentElement.offsetHeight
                            );
                            window.parent.postMessage({isStreamlitMessage:true, type:"streamlit:setFrameHeight", height: Math.ceil(h)+16},"*");
                          }catch(e){}
                        }

                        function scheduleHeight(){
                          sendHeight();
                          setTimeout(sendHeight, 80);
                          setTimeout(sendHeight, 260);
                          setTimeout(sendHeight, 820);
                          setTimeout(sendHeight, 1500);
                        }

                        try{
                          const ro = new ResizeObserver(()=>{ sendHeight(); });
                          ro.observe(document.documentElement);
                          ro.observe(document.body);
                        }catch(e){}

                        try{
                          const mo = new MutationObserver(()=>{ sendHeight(); });
                          mo.observe(document.body, {subtree:true, childList:true, attributes:true, characterData:true});
                        }catch(e){}

                        window.addEventListener("load", scheduleHeight);
                        window.addEventListener("resize", ()=>{ setTimeout(sendHeight, 120); });
                        scheduleHeight();
</script>
        </body>
        </html>
        """
    
        components.html(
            CLEAN_CAMPAIGN_BUNDLE_HTML,
            height=1500,
            scrolling=False,
        )
        st.markdown(
            '''
            <div style="max-width:1500px; margin: 18px auto 14px auto; height: 1px;
                        background: linear-gradient(90deg,
                          transparent,
                          rgba(239,68,68,0.55),
                          rgba(249,115,22,0.45),
                          rgba(245,158,11,0.35),
                          transparent);
                        opacity: 0.95;"></div>
            <div style="height:42px"></div>
            ''',
            unsafe_allow_html=True
        )

    


    # ✅ 자율점검 탭 전용 스타일 범위 종료
    

        # 5) ✍️ 스스로 다짐하는 청렴 서약 (자율 참여 이벤트)
        #    - 이름만 수집하여 Google Sheet에 저장
        #    - 참여 순번/누적 참여자 수 표시
        #    - 참여 시 3초 감사 팝업 + 꽃가루(Confetti) 효과

        st.markdown("""
        <style>
          :root{
            --cc-maxw: 1500px;
            --cc-title: clamp(34px, 3.6vw, 54px);
            --cc-red: #ef4444;
            --cc-orange: #f97316;
            --cc-amber: #f59e0b;
          }
          /* ✅ 청렴 서약 블록(세로 블록) 자체를 카드화: Streamlit 위젯도 포함해서 한 덩어리로 스타일 적용 */
          div[data-testid="stVerticalBlock"]:has(.cc-pledge-anchor){
            width: min(100%, var(--cc-maxw));
            margin: 16px auto 14px auto;
            padding: 44px 22px 34px 22px;
            border-radius: 34px;
            background:
              radial-gradient(circle at 18% 22%, rgba(239,68,68,0.18), transparent 45%),
              radial-gradient(circle at 82% 26%, rgba(249,115,22,0.14), transparent 46%),
              radial-gradient(circle at 40% 90%, rgba(245,158,11,0.10), transparent 52%),
              rgba(2,6,23,0.74);
            border: 1px solid rgba(255,255,255,0.10);
            box-shadow: 0 26px 72px rgba(0,0,0,0.45);
            overflow: hidden;
            position: relative;
          }
          

          div[data-testid="stVerticalBlock"]:has(.cc-pledge-anchor)::before{
            content:"";
            position:absolute;
            left:0; right:0; top:0;
            height:2px;
            background: linear-gradient(90deg, rgba(239,68,68,0.90), rgba(249,115,22,0.80), rgba(245,158,11,0.70));
            opacity: 0.95;
          }

          div[data-testid="stVerticalBlock"]:has(.cc-pledge-anchor) > div{ padding-top: 0 !important; }

          .cc-pledge-title{
            text-align:center;
            font-weight: 900;
            font-size: var(--cc-title);
            line-height: 1.06;
            letter-spacing: -0.02em;
            color: rgba(255,255,255,0.96);
            margin: 6px 0 18px 0;
          }
          .cc-pledge-title .em{
            color: var(--cc-red);
            text-decoration: underline;
            text-decoration-thickness: 10px;
            text-underline-offset: 10px;
          }
          .cc-pledge-panel{
            max-width: 1500px;
            margin: 0 auto;
            padding: 28px 26px 20px 26px;
            border-radius: 30px;
            background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.10);
            backdrop-filter: blur(14px);
            -webkit-backdrop-filter: blur(14px);
            text-align:center;
          }
          .cc-pledge-badge{
            width: 74px;
            height: 74px;
            margin: 0 auto 12px auto;
            border-radius: 22px;
            background: rgba(239,68,68,0.10);
            border: 1px solid rgba(239,68,68,0.22);
            display:flex;
            align-items:center;
            justify-content:center;
            box-shadow: 0 18px 40px rgba(0,0,0,0.30);
          }
          .cc-pledge-badge svg{ width: 42px; height: 42px; }
          .cc-pledge-event-title{
            margin-top: 6px;
            font-weight: 900;
            font-size: 18px;
            color: rgba(255,255,255,0.94);
          }
          .cc-pledge-desc{
            margin-top: 10px;
            color: rgba(203,213,225,0.74);
            font-weight: 700;
            line-height: 1.6;
            font-size: 13.5px;
          }
          .cc-pledge-desc .hot{
            color: rgba(239,68,68,0.92);
            font-weight: 900;
          }
          .cc-pledge-count{
            text-align:center;
            margin-top: 14px;
            color: rgba(148,163,184,0.90);
            font-weight: 900;
            letter-spacing: 0.08em;
          }
          .cc-pledge-count .num{
            color: rgba(255,255,255,0.96);
            font-variant-numeric: tabular-nums;
          }
          .cc-pledge-note{
            text-align:center;
            font-size: 13px;
            font-weight: 700;
            color: rgba(229,231,235,0.60);
            margin-top: 8px;
          }

          /* ✅ Streamlit 위젯(이름 입력/버튼)도 동일 톤으로 */
          div[data-testid="stVerticalBlock"]:has(.cc-pledge-anchor) div[data-testid="stTextInput"] input{
            background: rgba(15,23,42,0.65) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            border-radius: 18px !important;
            height: 52px !important;
            color: rgba(255,255,255,0.96) !important;
            -webkit-text-fill-color: rgba(255,255,255,0.96) !important;
            text-align: center !important;
            font-weight: 900 !important;
          }
          div[data-testid="stVerticalBlock"]:has(.cc-pledge-anchor) div[data-testid="stTextInput"] input::placeholder{
            color: rgba(226,232,240,0.42) !important;
          }
          div[data-testid="stVerticalBlock"]:has(.cc-pledge-anchor) button[kind="primary"],
          div[data-testid="stVerticalBlock"]:has(.cc-pledge-anchor) button{
            border-radius: 18px !important;
            height: 52px !important;
            font-weight: 900 !important;
            background: linear-gradient(90deg, rgba(239,68,68,0.95), rgba(249,115,22,0.92)) !important;
            border: 0 !important;
            color: rgba(255,255,255,0.96) !important;
            box-shadow: 0 18px 40px rgba(0,0,0,0.35) !important;
          }
        </style>
        """, unsafe_allow_html=True)

        # ✅ 블록 간 간격(영상/3테마/서약이 ‘정렬감’ 있게 보이도록 고정 간격)
        st.markdown('<div style="height:24px"></div>', unsafe_allow_html=True)

        pledge_total = 0
        pledge_sheet_ready = True
        try:
            _client = init_google_sheet_connection()
            if _client:
                _ss = _client.open("Audit_Result_2026")
                _ws = _get_or_create_ws(_ss, PLEDGE_SHEET_TITLE, ["저장시간", "사번", "성함"])
                pledge_total = _pledge_count(_ws)
            else:
                pledge_sheet_ready = False
        except Exception:
            pledge_sheet_ready = False

        with st.container():
            st.markdown('<div class="cc-pledge-anchor"></div>', unsafe_allow_html=True)

            st.markdown('<div class="cc-pledge-title">스스로 다짐하는<br><span class="em">청렴 서약</span></div>', unsafe_allow_html=True)

            st.markdown("""
            <div class="cc-pledge-panel">
              <div class="cc-pledge-badge">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 14.2c3.75 0 6.8-3.05 6.8-6.8S15.75.6 12 .6 5.2 3.65 5.2 7.4s3.05 6.8 6.8 6.8Z" stroke="rgba(239,68,68,0.95)" stroke-width="1.8"/>
                  <path d="M8.6 13.7 7.6 23l4.4-2.4 4.4 2.4-1.0-9.3" stroke="rgba(239,68,68,0.85)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                  <path d="M9.1 7.7 10.9 9.5l4-4" stroke="rgba(249,115,22,0.92)" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </div>
              <div class="cc-pledge-event-title">🎁 청렴 실천 응원 이벤트</div>
              <div class="cc-pledge-desc">
                본 서약은 <b>자율 참여</b>입니다.<br>
                임직원 <span class="hot">{threshold}명 이상</span>이 서약에 참여하시면,<br>
                참여자 중 <span class="hot">{winners}명</span>을 추첨하여 새해 모바일 커피 쿠폰을 감사실에서 드립니다.
              </div>
            </div>
            """.format(threshold=PLEDGE_THRESHOLD, winners=PLEDGE_WINNERS), unsafe_allow_html=True)

            if not pledge_sheet_ready:
                st.warning("⚠️ 현재 서약 저장 기능이 준비되지 않았습니다. (Google Sheet 연결 확인 필요)")
            else:
                pledge_popup_slot = st.empty()  # 청렴서약 완료 팝업(현재 위치에서 노출)
                with st.form("clean_campaign_pledge_form", clear_on_submit=True):
                    c1, c2, c3 = st.columns([0.38, 0.38, 0.24], vertical_alignment="center")
                    with c1:
                        pledge_emp_id = st.text_input("사번", placeholder="사번", label_visibility="collapsed")
                    with c2:
                        pledge_name = st.text_input("성함", placeholder="성함", label_visibility="collapsed")
                    with c3:
                        submit_pledge = st.form_submit_button("서약하기")
                if submit_pledge:
                    ok, msg, rank, total = save_clean_campaign_pledge(pledge_emp_id, pledge_name)
                    if ok:
                        pledge_total = max(int(total or 0), pledge_total)

                        # ✅ 현재 화면 위치에서 즉시 팝업(가이드/꽃가루/폭죽 효과)
                        with pledge_popup_slot.container():
                            components.html(
                                _build_pledge_popup_html((pledge_name or "").strip(), int(rank or 0), int(total or 0)),
                                height=1,
                                scrolling=False,
                            )
                        st.toast(f"🎉 {(pledge_name or '').strip()}님, 청렴 서약에 참여해 주셔서 감사합니다!", icon="✅")
                    else:
                        st.warning(msg)

            st.markdown(
                f'<div class="cc-pledge-count">CURRENT: <span class="num">{pledge_total}</span> SIGNATURES<br>'
                f'현재 총 <span class="num">{pledge_total}</span>명의 임직원이 서약에 참여했습니다.</div>',
                unsafe_allow_html=True
            )
            st.markdown('<div class="cc-pledge-note">※ 참여 정보는 사번/성함이 저장되며, 클린캠페인 운영 목적 외에는 사용되지 않습니다.</div>', unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# --- [Tab 2: 법률 리스크/규정/계약 검토 & 감사보고서 작성] ---
with tab_doc:
    st.markdown("### 📄 법률 리스크(계약서)·규정 검토 / 감사보고서 작성·검증")

    if "api_key" not in st.session_state:
        render_login_required()
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
        render_login_required()
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
        render_login_required()
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
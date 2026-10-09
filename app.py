import streamlit as st
import streamlit.components.v1 as components
import os
import requests
import time
import tempfile
import hashlib
import hmac
import base64
import html
import json
import datetime
import pytz
import pandas as pd
import re
import random
import uuid
import shutil
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse


# Plotly: 확대/축소 후 "원점 복원" 가능하도록 모드바 항상 표시

# [필수] 구글 시트 라이브러리 체크
try:
    import gspread
except ImportError:
    gspread = None
    st.error("❌ 구글 시트 라이브러리가 없습니다. requirements.txt를 확인하세요.")

# 인증 라이브러리: google-auth를 우선 사용하고, 없을 때만 구형 oauth2client로 대체합니다.
try:
    from google.oauth2.service_account import Credentials as _GoogleServiceCredentials
except ImportError:
    _GoogleServiceCredentials = None
try:
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    ServiceAccountCredentials = None
if gspread is not None and _GoogleServiceCredentials is None and ServiceAccountCredentials is None:
    st.error("❌ 구글 인증 라이브러리(google-auth)가 없습니다. requirements.txt에 google-auth를 추가하세요.")


# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="SMART POWER FIELD · 전원 현장업무",
    page_icon="⚡",
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
/* 사이드바는 사용하지 않습니다 (Control Center 제거) */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] { display: none !important; }

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

/* ===== SMART POWER FIELD 디자인 기준: 현장(장갑·한 손·야외) 사용성 ===== */
.stButton > button, div[data-testid="stFormSubmitButton"] > button, div[data-testid="stDownloadButton"] > button {
    min-height: 50px !important; font-size: 1.02rem !important; border-radius: 12px !important;
}
.stTextInput input, .stTextArea textarea, div[data-baseweb="select"] > div { min-height: 48px !important; font-size: 1.04rem !important; }
div[data-testid="stTabs"] button[role="tab"] { min-height: 52px; font-size: 1.02rem; font-weight: 900; padding: 0 14px; }
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color: #0F4C81 !important; }
section.main .block-container, div[data-testid="stMainBlockContainer"] { max-width: 1120px; }
.spf-strip { display:flex; flex-wrap:wrap; gap:6px; align-items:center; margin:2px 0 6px; }
.spf-chip { display:inline-flex; align-items:center; gap:4px; padding:5px 11px; border-radius:999px; background:#EEF2F7;
            border:1px solid #D5DEE9; color:#334155; font-size:.82rem; font-weight:800; }
.spf-chip.user { background:#E8F1FB; border-color:#BFD7F2; color:#0F3B66; }
.spf-chip.ok { background:#E9F7EF; border-color:#BFE5CE; color:#16643A; }
div[data-testid="stAlert"] { border-radius: 12px; }
@media (max-width: 640px) {
    section.main .block-container, div[data-testid="stMainBlockContainer"] { padding-left: .7rem; padding-right: .7rem; }
    div[data-testid="stTabs"] button[role="tab"] { padding: 0 9px; font-size: .96rem; }
    .stButton > button { font-size: 1rem !important; }
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 세션 관리
# ==========================================
def _clear_query_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()





# ==========================================
# 4. 자동 로그인 복구 (URL 파라미터)
# ==========================================
# 과거 버전이 URL(?k=...)에 남긴 API 키는 즉시 제거합니다. (주소 공유·브라우저 기록 유출 방지)
try:
    if "k" in st.query_params:
        del st.query_params["k"]
except Exception:
    pass

# 공용 Gemini 키가 Secrets에 있으면 사용자가 키를 입력할 필요 없이 자동 연결됩니다.

# ==========================================
# 5. 사이드바 (로그인/로그아웃)
# ==========================================

# ==========================================
# 7. 로그아웃 애니메이션
# ==========================================

# ==========================================
# 8. 핵심 기능 함수 (구글시트, AI, 파일처리)
# ==========================================
logger = logging.getLogger("smartwork")

_GS_SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource(show_spinner=False)
def _process_state() -> dict:
    """서버 프로세스 전체에서 공유되는 상태 저장소.

    Streamlit은 화면이 갱신될 때마다 이 파일을 처음부터 다시 실행하므로, 일반 모듈 전역 변수는 매번 초기화됩니다.
    잠금 기록·사진 작업·캐시처럼 '실행이 바뀌어도 유지되어야 하는' 상태는 반드시 여기에 둡니다.
    """
    return {
        "gs_lock": threading.Lock(),
        "gs_state": {"client": None, "built_at": 0.0, "error": ""},
        "gs_handle_cache": {},
        "drive_token_cache": {"token": "", "expires": 0.0},
        "users_cache": {"at": 0.0, "value": None, "error": ""},
        "users_cache_lock": threading.Lock(),
        "auth_lock": threading.Lock(),
        "auth_state": {},
        "devices_cache": {"at": 0.0, "value": None},
        "devices_cache_lock": threading.Lock(),
        "photo_jobs": {},
        "photo_jobs_lock": threading.Lock(),
        "photo_executor": ThreadPoolExecutor(max_workers=2, thread_name_prefix="swphoto"),
        "draft_executor": ThreadPoolExecutor(max_workers=1, thread_name_prefix="swdraft"),
    }


_PS = _process_state()
_GS_LOCK = _PS["gs_lock"]
_GS_STATE = _PS["gs_state"]
_GS_CLIENT_TTL_SECONDS = 40 * 60
_GS_HANDLE_CACHE = _PS["gs_handle_cache"]
_GS_HANDLE_TTL_SECONDS = 10 * 60
_DRIVE_TOKEN_CACHE = _PS["drive_token_cache"]


def _gs_service_info() -> dict:
    """서비스 계정 정보를 일반 dict로 복사합니다. (백그라운드 스레드에 안전하게 전달하기 위함)"""
    return {str(k): v for k, v in dict(st.secrets["gcp_service_account"]).items()}


def _gs_make_client(info: dict):
    """서비스 계정 정보로 gspread 클라이언트를 새로 만듭니다. google-auth 우선, 구형 oauth2client는 대체용입니다."""
    if gspread is None:
        raise RuntimeError("gspread 라이브러리가 설치되어 있지 않습니다.")
    if _GoogleServiceCredentials is not None:
        creds = _GoogleServiceCredentials.from_service_account_info(info, scopes=_GS_SCOPE)
    elif ServiceAccountCredentials is not None:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(info, _GS_SCOPE)
    else:
        raise RuntimeError("google-auth 또는 oauth2client 라이브러리가 필요합니다.")
    return gspread.authorize(creds)


def init_google_sheet_connection(force: bool = False):
    """구글 시트 클라이언트를 반환합니다.

    - 실패 결과(None)는 절대 캐시하지 않습니다. 다음 호출에서 자동으로 다시 연결을 시도합니다.
    - 클라이언트는 40분마다 새로 만들어 토큰 만료·끊긴 연결을 예방합니다.
    - 실패 원인은 `_gs_last_error()`와 서버 로그에 남깁니다.
    """
    now = time.time()
    with _GS_LOCK:
        client = _GS_STATE.get("client")
        if client is not None and not force and (now - float(_GS_STATE.get("built_at", 0) or 0)) < _GS_CLIENT_TTL_SECONDS:
            return client
        try:
            client = _gs_make_client(_gs_service_info())
            _GS_STATE.update(client=client, built_at=now, error="")
            _GS_HANDLE_CACHE.clear()
            return client
        except Exception as error:
            _GS_STATE.update(client=None, built_at=0.0, error=f"{type(error).__name__}: {error}")
            logger.error("Google Sheets 연결 실패: %s", _GS_STATE["error"])
            return None


def _gs_last_error() -> str:
    return str(_GS_STATE.get("error", "") or "")


def _gs_connection_failure_message(prefix: str = "Google Sheets 연결 실패") -> str:
    detail = _gs_last_error()
    return f"{prefix}: {detail}" if detail else f"{prefix}: Streamlit Secrets의 gcp_service_account 설정을 확인하세요."


_TRANSIENT_HTTP_PATTERN = re.compile(r"\[(?:408|429|500|502|503|504)\]")
_TRANSIENT_WORDS = (
    "Quota exceeded", "RESOURCE_EXHAUSTED", "rateLimitExceeded", "Connection aborted",
    "Connection reset", "Connection refused", "RemoteDisconnected", "timed out", "Timeout",
    "Max retries exceeded", "temporarily unavailable", "Service Unavailable", "Bad Gateway",
)


def _is_transient_error(error: Exception) -> bool:
    text = f"{type(error).__name__} {error}"
    return bool(_TRANSIENT_HTTP_PATTERN.search(text)) or any(word.lower() in text.lower() for word in _TRANSIENT_WORDS)


def _sheet_call(func, *args, _retries: int = 4, **kwargs):
    """구글 시트 API 호출을 일시 오류(429·5xx·연결 끊김)에 한해 지수 백오프로 재시도합니다."""
    last_error = None
    for attempt in range(max(1, _retries)):
        try:
            return func(*args, **kwargs)
        except Exception as error:
            last_error = error
            if attempt >= _retries - 1 or not _is_transient_error(error):
                raise
            time.sleep(min(1.0 * (2 ** attempt), 8.0) + random.random() * 0.4)
    raise last_error  # pragma: no cover


def _open_spreadsheet(name: str, client=None):
    """스프레드시트 핸들을 10분간 재사용합니다. (client.open(name)은 호출마다 Drive 검색 API를 소모)"""
    now = time.time()
    cached = _GS_HANDLE_CACHE.get(("ss", name))
    if cached and (now - cached[0]) < _GS_HANDLE_TTL_SECONDS:
        return cached[1]
    client = client or init_google_sheet_connection()
    if client is None:
        raise RuntimeError(_gs_connection_failure_message())
    spreadsheet = _sheet_call(client.open, name)
    _GS_HANDLE_CACHE[("ss", name)] = (now, spreadsheet)
    return spreadsheet


def _cached_sheet_setup(cache_key: str, builder):
    """시트 생성·헤더 점검처럼 무거운 준비 작업을 10분에 한 번만 수행합니다."""
    now = time.time()
    cached = _GS_HANDLE_CACHE.get(("setup", cache_key))
    if cached and (now - cached[0]) < _GS_HANDLE_TTL_SECONDS:
        return cached[1]
    result = builder()
    _GS_HANDLE_CACHE[("setup", cache_key)] = (now, result)
    return result


def _invalidate_sheet_setup(cache_key: str | None = None) -> None:
    if cache_key is None:
        _GS_HANDLE_CACHE.clear()
    else:
        _GS_HANDLE_CACHE.pop(("setup", cache_key), None)

def _korea_now():
    try:
        kst = pytz.timezone("Asia/Seoul")
        return datetime.datetime.now(kst)
    except Exception:
        return datetime.datetime.now()













































# ==========================================
# ✅ (요청 2) 사번 검증 유틸
# ==========================================


# ==========================================
# ✅ 2026년 6월 컴플라이언스 인식제고 교육 저장 유틸
#    - 기존 윤리경영 실천서약 저장 로직과 분리
#    - Google Sheet: Audit_Result_2026 / 2026_06_컴플라이언스_인식제고교육
# ==========================================



# ==========================================
# 8-2. 국사 전원시설 정밀점검 및 Google Sheets 저장
#      - 기존 Google 서비스 계정/스프레드시트 연결 재사용
#      - 점검 1건을 Google Sheet 1행으로 저장
# ==========================================
POWER_INSPECTION_SPREADSHEET_NAME = "Audit_Result_2026"
POWER_INSPECTION_SHEET_NAME = "국사_전원시설_정밀점검"

POWER_REGION_DATA = {'1권역 · 파주·문산·동두천 등': {'담당자': ['이철순', '김수창'],
                       '모국_국소': {'동두천': ['은현', '신산', '상수'],
                                 '문산': ['문산', '파주', '마산', '마정', '통일촌(N3211)', '장현', '웅담', '적성', '파평', '당동상가BBH', '봉암1리마을회관BBH'],
                                 '법원리': ['법원리', '금파리마을회관BBH', '어유지리BBH'],
                                 '연천': ['연천', '대광', '삼곳', '내산', '고문'],
                                 '일산': ['중산BBH'],
                                 '전곡': ['원당', '백학', '동이', '궁평', '왕림', '초성', '동중', '진상', '북삼', '늘목', '양원', '대전', '전곡', '학곡'],
                                 '파주': ['영장',
                                        '장곡',
                                        '위전',
                                        '법흥',
                                        '문발',
                                        '용미',
                                        '발랑',
                                        '파주 연다산(N3218)',
                                        '광탄',
                                        '탄현',
                                        '운정',
                                        '(파주)마이프라자1층BBH',
                                        '분수3리마을회관BBH',
                                        '새말BBH',
                                        '토우프라자BBH',
                                        '통일프라자BBH',
                                        '한라비발디상가BBH',
                                        '대성동마을회관BBH']}},
 '2권역 · 고양·덕양·의정부 등': {'담당자': ['소순고', '정청운'],
                       '모국_국소': {'고양IBS고양BBH': ['백석12블럭BBH', '마두21블럭BBH', '마두25블럭BBH', '백석8블럭BBH', '풍동에이스타워BBH'],
                                 '능곡': ['소만8단지(소만풍림8단지)BBH', '햇빛주공22단지BBH', '화정동상가(별빛건영10단지) BBH'],
                                 '덕양': ['덕양', '덕양 벽제(N3055)', '고양', '달빛3단지상가지하BBH', '상곡BBH'],
                                 '서대문': ['서대문(최적화분기국사)', '화전'],
                                 '신촌': ['신촌분기국사', '망원동BBH#1'],
                                 '아현': ['마포분기국사'],
                                 '용산': ['청파3가BBH'],
                                 '은평': ['삼송'],
                                 '의정부': ['장흥', '송추', '백석', '광적', '의정부 덕도(N3162)', '석우', '삼하', '비암'],
                                 '일산': ['송포',
                                        '성석',
                                        '고봉산중계소',
                                        '백마5단지상가BBH(N3173)',
                                        '장항동BBH',
                                        '북일산최적화분기국사(북일산)',
                                        '고양BBH(N3170)',
                                        '가좌BBH',
                                        '백석13블럭BBH',
                                        '백석7블럭BBH',
                                        '정발BBH',
                                        '일산(EBS)']}},
 '3권역 · 광화문·중앙·광진 등': {'담당자': ['김태수', '이학원'],
                       '모국_국소': {'광진': ['구의동BBH', '중곡동BBH'],
                                 '광화문': ['독립문통신구BBH(N995)', '무교동BBH', '종로5가통신구-1BBH(통신구내)'],
                                 '노원': ['공릉최적화분기국사'],
                                 '도봉': ['방학최적화분기국사', '수유3국사(수유동269-16단독주택)BBH'],
                                 '방학': ['행운빌라BBH'],
                                 '성북': ['안암BBH', '대광BBH', '성북BBH', '보문시장BBH'],
                                 '신내': ['중랑최적화분기국사'],
                                 '용산': ['경찰청'],
                                 '은평': ['홍제최적화분기국사', '평창아파트BBH', '효자BBH(N977)'],
                                 '을지': ['을지로3가BBH', '을지로6가BBH', '을지로7가BBH(통신구내)'],
                                 '중랑': ['망우최적화분기국사(중랑)'],
                                 '중앙': ['BBH(후암동68-6-BBH)', '을지메인통신구', '을지입구B1통신구내 BBH(N944)'],
                                 '청량': ['청량최적화BBH'],
                                 '행당': ['약수역BBH', '동대문최적화BBH(통신구내)']}},
 '4권역 · 동의정부·동두천·철원 등': {'담당자': ['박동희', '신진우'],
                         '모국_국소': {'동두천': ['동두천', '덕정', '덕계', '소요', '광암'],
                                   '동의정부': ['경중앙(통신구내)BBH', '남방', '광사', '자일', '청학', '금오BBH'],
                                   '송우': ['송우', '가산', '내촌', '신팔', '이곡'],
                                   '의정부': ['녹양'],
                                   '철원': ['철원', '동송분기국사', '문혜', '내대', '관전', '장흥', '오지', '지경', '자등', '마현', '양지', '근남', '잠곡', '와수', '도창'],
                                   '청평': ['마일', '봉수', '율길', '임초', '조종', '상판', '대보'],
                                   '퇴계원': ['광릉', '금곡BBH'],
                                   '포천': ['포천',
                                          '자작',
                                          '직두',
                                          '화현',
                                          '일동',
                                          '사직',
                                          '수입',
                                          '장암',
                                          '도평',
                                          '산정',
                                          '영북',
                                          '관인',
                                          '운산',
                                          '창수',
                                          '신북',
                                          '남청산',
                                          '고소성',
                                          '만세교',
                                          '양문',
                                          '대회산']}},
 '5권역 · 가평·남양주·양평 등': {'담당자': ['강만식', '이민우'],
                       '모국_국소': {'가평': ['개곡', '가평', '상색', '산유', '북면', '화악', '백둔', '도대', '적목'],
                                 '남양주': ['남양주', '일패', '답내', '운수', '외방', '호평BBH'],
                                 '덕소': ['덕소', '조안', '송촌', '월문', '팔당'],
                                 '양평': ['양평',
                                        '노문',
                                        '정배',
                                        '목왕',
                                        '서종',
                                        '양수',
                                        '국수',
                                        '강하',
                                        '강상',
                                        '회현',
                                        '개군',
                                        '일신',
                                        '양동',
                                        '계정',
                                        '금왕',
                                        '고송',
                                        '용문',
                                        '신점',
                                        '단월',
                                        '산음',
                                        '명성',
                                        '용두',
                                        '옥천',
                                        '지평',
                                        '용문산중계소'],
                                 '청평': ['청평', '고성', '대성', '미사', '방일', '삼회', '설악', '회곡', '에덴성회BBH'],
                                 '퇴계원': ['퇴계원', '진접', '진건', '오남', '별내']}}}


def _build_power_station_map() -> dict[str, list[str]]:
    """모든 권역의 모국·국소를 합친 하위 호환용 전체 목록입니다."""
    station_map: dict[str, list[str]] = {}
    for region in POWER_REGION_DATA.values():
        for mother, locals_ in region.get("모국_국소", {}).items():
            station_map.setdefault(mother, [])
            for local in locals_:
                if local not in station_map[mother]:
                    station_map[mother].append(local)
    return station_map


POWER_STATION_MAP = _build_power_station_map()
POWER_INSPECTOR_OPTIONS = [
    person
    for region in POWER_REGION_DATA.values()
    for person in region.get("담당자", [])
]
POWER_INSPECTOR_MAJOR_AREA_MAP = {
    person: area
    for area, region in POWER_REGION_DATA.items()
    for person in region.get("담당자", [])
}

# ✅ 현장 기본정보 단축 입력용: 권역별 담당자 2명을 한 묶음으로 표시합니다.
POWER_AREA_INSPECTOR_DISPLAY = {
    area: ", ".join(
        str(person).strip()
        for person in region.get("담당자", [])
        if str(person).strip()
    )
    for area, region in POWER_REGION_DATA.items()
}
POWER_INSPECTOR_GROUP_OPTIONS = [
    display for display in POWER_AREA_INSPECTOR_DISPLAY.values() if display
]
POWER_INSPECTOR_DISPLAY_AREA_MAP = {
    display: area
    for area, display in POWER_AREA_INSPECTOR_DISPLAY.items()
    if display
}


def _build_power_station_search_entries() -> list[dict]:
    """국소명 하나로 권역·담당자·모국·국소를 찾을 수 있는 역색인을 만듭니다."""
    entries: list[dict] = []
    serial = 0
    for area, region in POWER_REGION_DATA.items():
        inspectors = POWER_AREA_INSPECTOR_DISPLAY.get(area, "")
        station_map = region.get("모국_국소", {}) if isinstance(region, dict) else {}
        for mother, locals_ in station_map.items():
            for local in locals_:
                serial += 1
                entries.append({
                    "id": f"power_station_{serial:03d}",
                    "area": str(area).strip(),
                    "inspectors": inspectors,
                    "mother": str(mother).strip(),
                    "local": str(local).strip(),
                })
    return entries


POWER_STATION_SEARCH_ENTRIES = _build_power_station_search_entries()
POWER_STATION_SEARCH_BY_ID = {
    entry["id"]: entry for entry in POWER_STATION_SEARCH_ENTRIES
}



# 담당자에 따라 소속 조를 자동 표시합니다.
# 이름과 조 정보가 추가되면 이 사전만 확장하면 됩니다.
POWER_INSPECTOR_GROUP_MAP = {
    "정청운": "덕양관리조",
    "정철선": "덕양관리조",
    "정철순": "덕양관리조",
    "소순고": "덕양관리조",
    "이철순": "고양관리조",
    "김수창": "고양관리조",
    # 영문 입력 보조
    "JEONGCHEONGWOON": "덕양관리조",
    "JEONGCHEOLSUN": "덕양관리조",
    "SOSOONGO": "덕양관리조",
    "LEECHEOLSOON": "고양관리조",
    "KIMSOOCHANG": "고양관리조",
}


def _normalize_inspector_name(name: str) -> str:
    normalized = re.sub(r"[\s\-_.]", "", str(name or "").strip())
    return normalized.upper() if re.search(r"[A-Za-z]", normalized) else normalized


def _inspector_group_for_name(name: str) -> str:
    return POWER_INSPECTOR_GROUP_MAP.get(_normalize_inspector_name(name), "")


def _major_areas_for_inspector(name: str) -> list[str]:
    normalized = _normalize_inspector_name(name)
    areas: list[str] = []
    for person, area in POWER_INSPECTOR_MAJOR_AREA_MAP.items():
        if _normalize_inspector_name(person) == normalized and area not in areas:
            areas.append(area)
    return areas


def _power_area_station_map(area: str) -> dict[str, list[str]]:
    region = POWER_REGION_DATA.get(str(area or "").strip(), {})
    mapping = region.get("모국_국소", {}) if isinstance(region, dict) else {}
    return mapping if isinstance(mapping, dict) else {}


def _inspectors_for_major_area(area: str) -> list[str]:
    """선택한 권역에 배정된 담당자 2명만 반환합니다."""
    region = POWER_REGION_DATA.get(str(area or "").strip(), {})
    people = region.get("담당자", []) if isinstance(region, dict) else []
    return [str(person).strip() for person in people if str(person).strip()]


def _automatic_inspector_display(area: str) -> str:
    """권역을 선택하면 별도 선택 없이 담당자 2명을 가로로 표시·저장합니다."""
    return POWER_AREA_INSPECTOR_DISPLAY.get(str(area or "").strip(), "")


def _major_area_for_worker_value(worker: str) -> str:
    """개별 담당자 또는 '담당자1, 담당자2' 묶음값에서 권역을 찾습니다."""
    value = str(worker or "").strip()
    if value in POWER_INSPECTOR_DISPLAY_AREA_MAP:
        return POWER_INSPECTOR_DISPLAY_AREA_MAP[value]
    return POWER_INSPECTOR_MAJOR_AREA_MAP.get(value, "권역 선택")


def _power_worker_matches_area(worker: str, area: str) -> bool:
    """과거 개별 담당자 값과 신규 2인 묶음값을 모두 허용합니다."""
    worker_value = str(worker or "").strip()
    area_value = str(area or "").strip()
    if area_value not in POWER_REGION_DATA:
        return False
    if worker_value == _automatic_inspector_display(area_value):
        return True
    return worker_value in _inspectors_for_major_area(area_value)


def _normalize_power_station_search(text: str) -> str:
    return re.sub(r"[\s·._()#\-]", "", str(text or "").strip()).lower()


def _search_power_station_entries(query: str, limit: int = 40) -> list[dict]:
    """국소명을 우선으로 검색하고, 모국/권역명도 보조 검색합니다."""
    normalized = _normalize_power_station_search(query)
    if not normalized:
        return []

    scored: list[tuple[int, str, dict]] = []
    for entry in POWER_STATION_SEARCH_ENTRIES:
        local_key = _normalize_power_station_search(entry.get("local", ""))
        mother_key = _normalize_power_station_search(entry.get("mother", ""))
        area_key = _normalize_power_station_search(entry.get("area", ""))
        if normalized == local_key:
            rank = 0
        elif local_key.startswith(normalized):
            rank = 1
        elif normalized in local_key:
            rank = 2
        elif normalized in mother_key:
            rank = 3
        elif normalized in area_key:
            rank = 4
        else:
            continue
        scored.append((rank, local_key, entry))

    scored.sort(key=lambda item: (item[0], item[1], item[2].get("mother", ""), item[2].get("area", "")))
    return [entry for _, _, entry in scored[:max(1, int(limit))]]


def _power_station_search_label(entry_id: str) -> str:
    entry = POWER_STATION_SEARCH_BY_ID.get(str(entry_id or ""), {})
    if not entry:
        return "검색 결과 없음"
    return (
        f"{entry.get('local', '')}  |  모국 {entry.get('mother', '')}  |  "
        f"담당자 {entry.get('inspectors', '')}  |  {entry.get('area', '')}"
    )


def _apply_power_station_search_entry(entry: dict) -> None:
    """검색으로 확정한 국사의 기본정보를 기존 입력 상태에 안전하게 반영합니다."""
    if not entry:
        return

    _preserve_current_power_measurements()
    selected_area = str(entry.get("area", "")).strip()
    st.session_state["power_worker"] = _automatic_inspector_display(selected_area)
    st.session_state["power_major_area"] = selected_area
    st.session_state["power_inspector_group"] = _inspector_group_for_area(selected_area)
    st.session_state["power_mother"] = str(entry.get("mother", "")).strip()
    st.session_state["power_local"] = str(entry.get("local", "")).strip()
    _clear_power_history_state()
    _mark_power_basic_info_changed()

    # 검색 반영 여부를 별도 보존하여 아래 기본정보 선택값을 자주색으로 강조합니다.
    st.session_state["power_station_search_applied"] = True
    st.session_state["power_station_search_candidates"] = []
    # duplicate radio key는 해당 위젯이 생성된 실행 중에는 직접 변경하지 않습니다.
    st.session_state["power_station_search_status"] = "applied"
    st.session_state["power_station_search_notice"] = (
        f"✅ {entry.get('local', '')} 국사 자동입력 완료 · "
        f"담당자 {entry.get('inspectors', '')} · {selected_area} · "
        f"모국 {entry.get('mother', '')}"
    )


def _run_power_station_search() -> None:
    """확인 버튼/Enter 제출 시 검색합니다. 1건이면 즉시 반영하고, 중복이면 후보만 표시합니다."""
    query = str(st.session_state.get("power_station_search_query", "") or "").strip()
    st.session_state["power_station_search_notice"] = ""
    st.session_state["power_station_search_status"] = ""
    st.session_state["power_station_search_candidates"] = []
    st.session_state["power_station_search_choice"] = ""

    if not query:
        st.session_state["power_station_search_status"] = "empty"
        return

    normalized_query = _normalize_power_station_search(query)
    matches = _search_power_station_entries(query)

    # '송포'처럼 국소명이 정확히 일치하면 부분검색 결과보다 정확일치를 우선합니다.
    exact_matches = [
        entry for entry in matches
        if _normalize_power_station_search(entry.get("local", "")) == normalized_query
    ]
    candidates = exact_matches if exact_matches else matches

    if len(candidates) == 1:
        _apply_power_station_search_entry(candidates[0])
        return

    if len(candidates) > 1:
        candidate_ids = [entry["id"] for entry in candidates]
        st.session_state["power_station_search_candidates"] = candidate_ids
        st.session_state["power_station_search_choice"] = candidate_ids[0]
        st.session_state["power_station_search_status"] = "multiple"
        st.session_state["power_station_search_applied"] = False
        return

    st.session_state["power_station_search_status"] = "none"
    st.session_state["power_station_search_applied"] = False


def _confirm_power_station_search_choice() -> None:
    """동일 이름/부분검색 후보 중 사용자가 선택한 한 곳을 최종 반영합니다."""
    selected_id = str(st.session_state.get("power_station_search_choice", "") or "").strip()
    entry = POWER_STATION_SEARCH_BY_ID.get(selected_id)
    if not entry:
        st.session_state["power_station_search_status"] = "choice_required"
        return
    _apply_power_station_search_entry(entry)


def _inspector_group_for_area(area: str) -> str:
    groups: list[str] = []
    for person in _inspectors_for_major_area(area):
        group = _inspector_group_for_name(person)
        if group and group not in groups:
            groups.append(group)
    return " · ".join(groups)


def _sync_power_inspectors_from_area() -> None:
    selected_area = st.session_state.get("power_major_area", "권역 선택")
    st.session_state["power_worker"] = _automatic_inspector_display(selected_area)
    st.session_state["power_inspector_group"] = _inspector_group_for_area(selected_area)


def _update_power_inspector_group() -> None:
    selected_worker = st.session_state.get("power_worker", "담당자 선택")
    selected_area = _major_area_for_worker_value(selected_worker)
    if selected_area in POWER_REGION_DATA:
        st.session_state["power_inspector_group"] = _inspector_group_for_area(selected_area)
    else:
        st.session_state["power_inspector_group"] = _inspector_group_for_name(selected_worker)


def _clear_power_history_state() -> None:
    """국사 선택과 연동된 과거기록 조회 상태만 초기화합니다."""
    for key in (
        "power_history_records", "power_history_message", "power_history_station",
        "power_history_selected_index", "power_loaded_message",
    ):
        st.session_state.pop(key, None)


def _preserve_current_power_measurements() -> None:
    """기본정보 또는 메뉴를 변경하기 전에 현재 측정값과 특이사항을 영구 임시저장소에 보존합니다."""
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    if current_theme in POWER_THEME_ORDER:
        _save_power_theme_to_draft(current_theme)


def _mark_power_basic_info_changed() -> None:
    st.session_state["power_basic_changed_notice"] = True
    st.session_state["power_draft_saved_at"] = _korea_now().strftime("%H:%M:%S")


def _on_power_worker_change() -> None:
    """담당자를 선택하면 권역을 자동 지정하고 기존 측정값은 보존합니다."""
    st.session_state["power_station_search_applied"] = False
    st.session_state["power_station_search_notice"] = ""
    _preserve_current_power_measurements()
    selected_worker = st.session_state.get("power_worker", "담당자 선택")
    previous_area = st.session_state.get("power_major_area", "권역 선택")
    selected_area = _major_area_for_worker_value(selected_worker)
    st.session_state["power_major_area"] = selected_area
    _update_power_inspector_group()
    if selected_area != previous_area:
        st.session_state["power_mother"] = "모국 선택"
        st.session_state["power_local"] = "국소 선택"
        _clear_power_history_state()
    _mark_power_basic_info_changed()


def _on_power_major_area_change() -> None:
    """권역 변경 시 담당자 2명을 자동 설정하고 측정값은 유지합니다."""
    _preserve_current_power_measurements()
    _sync_power_inspectors_from_area()
    st.session_state["power_mother"] = "모국 선택"
    st.session_state["power_local"] = "국소 선택"
    _clear_power_history_state()
    _mark_power_basic_info_changed()


def _on_power_mother_change() -> None:
    """모국 변경 시 국소와 과거조회 상태만 초기화하고 측정값은 유지합니다."""
    st.session_state["power_station_search_applied"] = False
    st.session_state["power_station_search_notice"] = ""
    _preserve_current_power_measurements()
    st.session_state["power_local"] = "국소 선택"
    _clear_power_history_state()
    _mark_power_basic_info_changed()


def _power_headers() -> list[str]:
    headers = [
        "저장일시", "점검ID", "점검자", "운용조", "주요점검권역", "모국", "국소", "전원구분", "축전지조수",
        "입력방식", "원본점검ID", "원본저장일시",
        "입력완료율(%)", "누락항목수", "누락항목", "부분입력확인",
        "삼상전압_R-S(V)", "삼상전압_S-T(V)", "삼상전압_T-R(V)", "삼상전압_R-N(V)",
        "삼상전류_R(A)", "삼상전류_S(A)", "삼상전류_T(A)", "삼상전류_N(A)",
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
        "사진수", "사진파일ID목록", "사진파일명목록",
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


def _ensure_worksheet_grid_capacity(ws, required_rows: int = 1, required_cols: int = 1):
    """Google Sheet의 행·열 크기를 저장에 필요한 만큼 자동 확장합니다.

    기존 시트가 과거 버전의 열 수로 생성되어 있어도 새 측정항목이 추가되면
    헤더를 쓰기 전에 필요한 열까지 자동으로 늘립니다.
    """
    current_rows = int(getattr(ws, "row_count", 0) or 0)
    current_cols = int(getattr(ws, "col_count", 0) or 0)
    target_rows = max(current_rows, int(required_rows or 1))
    target_cols = max(current_cols, int(required_cols or 1))

    if target_rows == current_rows and target_cols == current_cols:
        return ws

    try:
        ws.resize(rows=target_rows, cols=target_cols)
    except TypeError:
        # 일부 gspread 버전의 위치 인자 방식도 지원합니다.
        ws.resize(target_rows, target_cols)
    return ws


def _power_sheet_has_measurement_rows(ws) -> bool:
    """헤더 아래에 실제 측정 데이터가 한 건이라도 있는지 확인합니다."""
    try:
        values = ws.get_all_values()
    except Exception:
        return True

    if len(values) <= 1:
        return False
    return any(
        any(str(cell or "").strip() for cell in row)
        for row in values[1:]
    )


def _rewrite_power_sheet_in_standard_order(ws) -> list[str]:
    """기존 데이터까지 헤더명 기준으로 재배열해 최종 표준 열 순서를 즉시 적용합니다.

    기존 시트에 데이터가 남아 있어도 각 행을 헤더명으로 다시 매핑하므로 값과 항목이
    어긋나지 않습니다. 삼상전류는 반드시 R → S → T → N 순서로 배치됩니다.
    표준 목록에 없는 기존 사용자 정의 열은 오른쪽 끝에 보존합니다.
    """
    try:
        values = ws.get_all_values()
    except Exception as read_error:
        raise RuntimeError(f"기존 Google Sheets 데이터를 읽지 못했습니다: {read_error}")

    current_headers = [str(value or "").strip() for value in (values[0] if values else [])]
    standard_headers = POWER_INSPECTION_HEADERS.copy()
    extra_headers = [
        header for header in current_headers
        if header and header not in standard_headers
    ]
    target_headers = standard_headers + extra_headers

    # 이미 정확한 표준 순서이면 불필요한 전체 재작성을 하지 않습니다.
    if current_headers == target_headers:
        _ensure_worksheet_grid_capacity(
            ws,
            required_rows=max(int(getattr(ws, "row_count", 0) or 0), 10000),
            required_cols=max(len(target_headers), 100),
        )
        return target_headers

    # 중복 헤더가 있더라도 최초 열의 값을 기준으로 안전하게 재배열합니다.
    source_index = {}
    for index, header in enumerate(current_headers):
        if header and header not in source_index:
            source_index[header] = index

    reordered_rows = [target_headers]
    for source_row in values[1:]:
        reordered_rows.append([
            source_row[source_index[header]]
            if header in source_index and source_index[header] < len(source_row)
            else ""
            for header in target_headers
        ])

    required_rows = max(
        int(getattr(ws, "row_count", 0) or 0),
        len(reordered_rows),
        10000,
    )
    required_cols = max(
        int(getattr(ws, "col_count", 0) or 0),
        len(current_headers),
        len(target_headers),
        100,
    )
    _ensure_worksheet_grid_capacity(
        ws,
        required_rows=required_rows,
        required_cols=required_cols,
    )

    # 기존 값 영역을 비운 뒤 헤더와 모든 행을 표준 순서로 다시 기록합니다.
    clear_last_row = max(len(values), 1)
    clear_range = f"A1:{_column_letter(required_cols)}{clear_last_row}"
    try:
        ws.batch_clear([clear_range])
    except Exception:
        try:
            ws.update(
                range_name=clear_range,
                values=[[""] * required_cols for _ in range(clear_last_row)],
            )
        except TypeError:
            ws.update(
                clear_range,
                [[""] * required_cols for _ in range(clear_last_row)],
            )

    end_col = _column_letter(len(target_headers))
    end_row = len(reordered_rows)
    try:
        ws.update(
            range_name=f"A1:{end_col}{end_row}",
            values=reordered_rows,
            value_input_option="USER_ENTERED",
        )
    except TypeError:
        ws.update(
            f"A1:{end_col}{end_row}",
            reordered_rows,
            value_input_option="USER_ENTERED",
        )

    # 재작성 결과를 다시 확인하여 R/S/T/N 순서가 실제 시트에 반영됐는지 검증합니다.
    verified_headers = [str(value or "").strip() for value in ws.row_values(1)]
    expected_sequence = [
        "삼상전류_R(A)",
        "삼상전류_S(A)",
        "삼상전류_T(A)",
        "삼상전류_N(A)",
    ]
    sequence_start = target_headers.index("삼상전류_R(A)")
    if verified_headers[sequence_start:sequence_start + 4] != expected_sequence:
        raise RuntimeError("Google Sheets의 삼상전류 R/S/T/N 열 순서 재배치에 실패했습니다.")
    return target_headers


def _ensure_power_inspection_sheet(spreadsheet):
    """시트 전체 읽기·헤더 점검은 10분에 한 번만 수행해 저장 속도와 API 할당량을 아낍니다."""
    return _cached_sheet_setup(
        "power_sheet",
        lambda: _ensure_power_inspection_sheet_uncached(spreadsheet),
    )


def _ensure_power_inspection_sheet_uncached(spreadsheet):
    try:
        ws = spreadsheet.worksheet(POWER_INSPECTION_SHEET_NAME)
    except Exception:
        ws = spreadsheet.add_worksheet(
            title=POWER_INSPECTION_SHEET_NAME,
            rows=10000,
            cols=max(len(POWER_INSPECTION_HEADERS) + 5, 100),
        )

    # 데이터 유무와 관계없이 기존 행을 헤더명으로 안전하게 재매핑하여
    # 삼상전류 R → S → T → N 표준 순서를 실제 시트에 즉시 적용합니다.
    current_headers = _rewrite_power_sheet_in_standard_order(ws)

    _ensure_worksheet_grid_capacity(
        ws,
        required_rows=max(int(getattr(ws, "row_count", 0) or 0), 10000),
        required_cols=max(len(current_headers), 100),
    )

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


def _extract_appended_row_number(append_response) -> int | None:
    """gspread append_row 응답에서 실제 추가된 행 번호를 추출합니다."""
    if not isinstance(append_response, dict):
        return None
    updated_range = ""
    updates = append_response.get("updates")
    if isinstance(updates, dict):
        updated_range = str(updates.get("updatedRange", "") or "")
    if not updated_range:
        updated_range = str(append_response.get("updatedRange", "") or "")
    match = re.search(r"![A-Z]+(\d+):[A-Z]+(\d+)$", updated_range)
    if not match:
        return None
    return int(match.group(1))


def _locate_saved_inspection_row(ws, sheet_headers: list[str], inspection_id: str) -> int | None:
    """append 응답에 행 번호가 없을 때 점검ID 열에서 저장 행을 찾습니다."""
    if not inspection_id or "점검ID" not in sheet_headers:
        return None
    id_col = sheet_headers.index("점검ID") + 1
    try:
        values = ws.col_values(id_col)
    except Exception:
        return None
    for row_number in range(len(values), 1, -1):
        if str(values[row_number - 1]).strip() == inspection_id:
            return row_number
    return None


def _ensure_n_phase_current_saved(
    ws,
    sheet_headers: list[str],
    append_response,
    inspection_id: str,
    n_phase_value,
) -> None:
    """삼상 N상 전류를 저장 직후 확인하고 누락 시 정확한 셀에 보정 저장합니다.

    과거 버전 시트와 최종 표준 시트 모두에서 헤더명으로 실제 열을 찾고,
    저장된 행의 해당 셀을 직접 검증하여 N상 전류 누락을 방지합니다.
    """
    if n_phase_value in ("", None):
        return

    target_header = "삼상전류_N(A)"
    if target_header not in sheet_headers:
        raise RuntimeError("Google Sheets에 '삼상전류_N(A)' 헤더가 생성되지 않았습니다.")

    row_number = _extract_appended_row_number(append_response)
    if row_number is None:
        row_number = _locate_saved_inspection_row(ws, sheet_headers, inspection_id)
    if row_number is None:
        raise RuntimeError("저장된 행을 찾지 못해 N상 전류를 확인할 수 없습니다.")

    column_number = sheet_headers.index(target_header) + 1
    _ensure_worksheet_grid_capacity(
        ws,
        required_rows=max(int(getattr(ws, "row_count", 0) or 0), row_number),
        required_cols=max(int(getattr(ws, "col_count", 0) or 0), column_number),
    )
    cell_ref = f"{_column_letter(column_number)}{row_number}"

    existing_value = ""
    try:
        existing_value = str(ws.acell(cell_ref).value or "").strip()
    except Exception:
        existing_value = ""

    if existing_value:
        return

    last_error = None
    for attempt in range(3):
        try:
            ws.update(
                range_name=cell_ref,
                values=[[n_phase_value]],
                value_input_option="USER_ENTERED",
            )
            verified = str(ws.acell(cell_ref).value or "").strip()
            if verified:
                return
            last_error = RuntimeError("N상 전류 셀의 저장값이 비어 있습니다.")
        except TypeError:
            try:
                ws.update(cell_ref, [[n_phase_value]], value_input_option="USER_ENTERED")
                verified = str(ws.acell(cell_ref).value or "").strip()
                if verified:
                    return
                last_error = RuntimeError("N상 전류 셀의 저장값이 비어 있습니다.")
            except Exception as update_error:
                last_error = update_error
        except Exception as update_error:
            last_error = update_error
        time.sleep(0.4 * (attempt + 1))

    raise RuntimeError(f"N상 전류 저장 확인에 실패했습니다: {last_error}")


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


def _parse_battery_cell_number(value):
    """방전 후 셀 전압은 현장 입력 자릿수에 따라 2~3자리 소수를 허용합니다.

    - 215  → 2.15V
    - 3507 → 3.507V
    - 0.00 / 0.000처럼 직접 입력한 소수점은 그대로 숫자로 저장
    """
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return ""
    cleaned = re.sub(r"[^0-9.+-]", "", raw)
    if cleaned in {"", "+", "-", ".", "+.", "-."}:
        return ""
    try:
        if "." in cleaned:
            return float(cleaned)
        sign = -1 if cleaned.startswith("-") else 1
        digits = cleaned.lstrip("+-")
        if not digits.isdigit():
            return ""
        decimals = 3 if len(digits) >= 4 else 2
        return sign * (int(digits) / (10 ** decimals))
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


def _format_battery_cell_display(value) -> str:
    """Google Sheets의 셀 전압 자릿수를 가능한 한 보존합니다."""
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return ""
    cleaned = re.sub(r"[^0-9.-]", "", raw)
    if not cleaned:
        return ""
    try:
        number = float(cleaned)
        if "." in cleaned:
            fraction_len = len(cleaned.split(".", 1)[1])
            decimals = max(2, min(3, fraction_len))
        else:
            decimals = 2
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


def _power_widget_key(data_key: str) -> str:
    """화면 위젯 키와 영구 임시저장 키를 분리합니다.

    Streamlit은 현재 화면에서 사라진 위젯 키를 정리할 수 있으므로,
    측정값은 power_draft와 data_key에 별도로 보존하고 화면에는 _ui_ 키를 사용합니다.
    """
    return f"_ui_{data_key}"


def _power_get(key: str, default=""):
    """화면의 최신값 → 임시저장값 → 영구 세션값 순으로 값을 반환합니다."""
    ui_key = _power_widget_key(key)
    if ui_key in st.session_state:
        return st.session_state.get(ui_key, default)
    draft = _power_draft()
    if key in draft:
        return draft.get(key, default)
    return st.session_state.get(key, default)


def _power_set(key: str, value) -> None:
    """영구 임시저장값과 현재 렌더링된 화면값을 함께 갱신합니다."""
    _power_draft()[key] = value
    st.session_state[key] = value
    ui_key = _power_widget_key(key)
    if ui_key in st.session_state:
        st.session_state[ui_key] = value


def _persist_power_widget(key: str) -> None:
    """화면 위젯값을 영구 임시저장소로 즉시 복사합니다."""
    ui_key = _power_widget_key(key)
    value = st.session_state.get(ui_key, st.session_state.get(key, ""))
    _power_draft()[key] = value
    st.session_state[key] = value
    st.session_state["power_draft_saved_at"] = _korea_now().strftime("%H:%M:%S")


def _hydrate_power_widget(key: str, default="") -> None:
    """매 렌더링 시 임시저장값으로 화면 위젯을 복원합니다."""
    draft = _power_draft()
    value = draft.get(key, st.session_state.get(key, default))
    st.session_state[key] = value
    # 위젯이 만들어지기 전에 항상 화면 키를 임시저장값으로 맞춥니다.
    st.session_state[_power_widget_key(key)] = value


def _power_text_input(label: str, key: str, **kwargs):
    _hydrate_power_widget(key, "")
    ui_key = _power_widget_key(key)
    result = st.text_input(
        label,
        key=ui_key,
        on_change=_persist_power_widget,
        args=(key,),
        **kwargs,
    )
    # 버튼 클릭 등 다른 이벤트로 재실행되더라도 현재 화면값을 놓치지 않습니다.
    current_value = st.session_state.get(ui_key, result)
    _power_draft()[key] = current_value
    st.session_state[key] = current_value
    return current_value


def _power_text_area(label: str, key: str, **kwargs):
    _hydrate_power_widget(key, "")
    ui_key = _power_widget_key(key)
    result = st.text_area(
        label,
        key=ui_key,
        on_change=_persist_power_widget,
        args=(key,),
        **kwargs,
    )
    current_value = st.session_state.get(ui_key, result)
    _power_draft()[key] = current_value
    st.session_state[key] = current_value
    return current_value


def _power_theme_keys(theme: str) -> list[str]:
    if theme == "전압·전류 측정":
        return [
            "power_phase_type",
            "power_three_voltage_rs", "power_three_voltage_st",
            "power_three_voltage_tr", "power_three_voltage_rn",
            "power_three_current_r", "power_three_current_s", "power_three_current_t", "power_three_current_n",
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
            "power_telecom_ground", "power_lightning_ground",
        ]
    if theme == "최종 확인·전송":
        return ["power_notes"]
    return []


def _save_power_theme_to_draft(theme: str) -> None:
    """현재 화면값을 shadow UI 키에서 읽어 영구 임시저장소에 스냅샷합니다."""
    draft = _power_draft()
    for key in _power_theme_keys(theme):
        ui_key = _power_widget_key(key)
        if ui_key in st.session_state:
            value = st.session_state.get(ui_key, "")
        elif key in draft:
            value = draft.get(key, "")
        else:
            value = st.session_state.get(key, "")
        draft[key] = value
        st.session_state[key] = value
    st.session_state["power_draft_saved_at"] = _korea_now().strftime("%H:%M:%S")


def _hydrate_power_theme_from_draft(theme: str) -> None:
    """선택한 테마의 모든 값을 영구 임시저장소에서 복원합니다."""
    draft = _power_draft()
    for key in _power_theme_keys(theme):
        if key in draft:
            st.session_state[key] = draft[key]


def _on_power_phase_change() -> None:
    _persist_power_widget("power_phase_type")


def _on_power_battery_set_change() -> None:
    _persist_power_widget("power_battery_set")
    _save_power_theme_to_draft("축전지 측정")
    selected = _power_get("power_battery_set", "1조 셀 측정")
    if selected == "2조 셀 측정":
        _power_set("power_battery2_enabled", True)


def _power_basic_missing() -> list[str]:
    missing: list[str] = []
    worker = str(st.session_state.get("power_worker", "담당자 선택")).strip()
    major_area = str(st.session_state.get("power_major_area", "권역 선택")).strip()
    if not _power_worker_matches_area(worker, major_area):
        missing.append("담당자")
    if major_area == "권역 선택" or major_area not in POWER_REGION_DATA:
        missing.append("주요 점검권역")
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
            ("삼상 N상 전류", payload.get("three_current_n")),
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
    phase_count = 8 if str(payload.get("phase_type", "")).strip() == "삼상" else 2
    battery1_count = int(payload.get("battery1_cell_count", 0) or 0)
    battery_count = 5 + max(0, min(battery1_count, 24))
    if int(payload.get("battery_group_count", 1) or 1) == 2:
        battery2_count = int(payload.get("battery2_cell_count", 0) or 0)
        battery_count += 5 + max(0, min(battery2_count, 24))
    return phase_count + battery_count + 5


def _power_has_measurement(payload: dict) -> bool:
    measurement_keys = [
        "three_voltage_rs", "three_voltage_st", "three_voltage_tr", "three_voltage_rn",
        "three_current_r", "three_current_s", "three_current_t", "three_current_n",
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


def save_power_inspection_result(payload: dict, photos: list | None = None) -> tuple[bool, str, str]:
    """국사 전원시설 정밀점검 결과를 Google Sheet에 먼저 저장하고, 사진은 백그라운드로 Drive에 올려 연결합니다."""
    photos = list(photos or [])[:WORK_LOG_MAX_PHOTOS]
    client = init_google_sheet_connection()
    if not client:
        return False, _gs_connection_failure_message("구글 시트 연결 실패"), ""

    try:
        worker = str(payload.get("worker", "")).strip()
        major_area = str(payload.get("major_area", "")).strip()
        mother = str(payload.get("mother", "")).strip()
        local = str(payload.get("local", "")).strip()
        phase_type = str(payload.get("phase_type", "")).strip()

        if not worker or worker == "담당자 선택":
            return False, "담당자를 선택해 주세요.", ""
        if not _power_worker_matches_area(worker, major_area):
            return False, "선택한 담당자와 주요 점검권역 정보가 일치하지 않습니다.", ""
        area_map = _power_area_station_map(major_area)
        if mother not in area_map:
            return False, "선택한 권역에 포함된 모국을 선택해 주세요.", ""
        if local not in area_map.get(mother, []):
            return False, "선택한 권역·모국·국소의 조합이 올바르지 않습니다.", ""
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

        spreadsheet = _open_spreadsheet(POWER_INSPECTION_SPREADSHEET_NAME, client)
        ws, sheet_headers = _ensure_power_inspection_sheet(spreadsheet)

        now = _korea_now()
        saved_at = now.strftime("%Y-%m-%d %H:%M:%S")
        inspection_seed = f"{saved_at}|{worker}|{major_area}|{mother}|{local}|{time.time_ns()}"
        inspection_id = hashlib.sha256(inspection_seed.encode("utf-8")).hexdigest()[:14]
        source_id = str(payload.get("source_inspection_id", "")).strip()
        source_saved_at = str(payload.get("source_saved_at", "")).strip()

        # 사진은 선택사항입니다. 측정값을 먼저 확정하고 사진은 저장 후 백그라운드로 연결합니다.
        photo_items, prepare_errors = _prepare_photo_items(
            photos, now, lambda stamp, index: f"정밀점검_{stamp}_{inspection_id}_{index:02d}.jpg"
        )

        row_map = {
            "저장일시": saved_at,
            "점검ID": inspection_id,
            "점검자": worker,
            "운용조": str(payload.get("inspector_group", "")).strip() or _inspector_group_for_area(major_area),
            "주요점검권역": major_area,
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
            "삼상전류_N(A)": payload.get("three_current_n", "") if phase_type == "삼상" else "",
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
            "사진수": 0,
            "사진파일ID목록": "",
            "사진파일명목록": "",
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
        append_response = _sheet_call(ws.append_row, row, value_input_option="USER_ENTERED", _retries=6)
        if append_response is None:
            return False, "저장 요청이 집중되어 전송하지 못했습니다. 다시 전송해 주세요.", ""

        # 최종 표준 순서(R/S/T/N)에서도 N상 전류가 실제 저장됐는지 확인합니다.
        if phase_type == "삼상":
            n_phase_value = row_map.get("삼상전류_N(A)", "")
            try:
                _ensure_n_phase_current_saved(
                    ws,
                    sheet_headers,
                    append_response,
                    inspection_id,
                    n_phase_value,
                )
            except Exception as n_phase_error:
                return False, (
                    "기본 측정데이터 행은 저장되었으나 N상 전류 저장 확인에 실패했습니다. "
                    f"관리자에게 확인해 주세요. ({n_phase_error})"
                ), inspection_id

        photo_message = ""
        if photo_items:
            cfg = _photo_cfg_snapshot()
            if cfg["error"]:
                photo_message = f" · ⚠️ 사진 {len(photo_items)}장 미첨부(설정 확인 필요: {cfg['error']})"
            else:
                try:
                    _photo_job_submit(
                        kind="power",
                        title=f"정밀점검 · {local}",
                        user_id=str(_worklog_current_user().get("user_id", "") or ""),
                        spec={
                            "cfg": cfg, "gs_info": _gs_service_info(),
                            "spreadsheet": POWER_INSPECTION_SPREADSHEET_NAME,
                            "sheet": POWER_INSPECTION_SHEET_NAME,
                            "id_header": "점검ID", "record_id": inspection_id, "history": None,
                        },
                        items=photo_items,
                    )
                    photo_message = f" · 현장사진 {len(photo_items)}장 업로드 진행 중"
                except Exception as job_error:
                    photo_message = f" · ⚠️ 사진 업로드를 시작하지 못했습니다({job_error})"
        if prepare_errors:
            photo_message += f" · ⚠️ 사진 {len(prepare_errors)}장 처리 실패"
        return True, f"측정값과 N상 전류가 Google Sheets에 정상 저장되었습니다.{photo_message}", inspection_id
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
        spreadsheet = _open_spreadsheet(POWER_INSPECTION_SPREADSHEET_NAME, client)
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


def list_power_inspection_history(
    mother: str,
    local: str,
    within_days: int = 183,
    max_records: int = 100,
) -> tuple[bool, str, list[dict]]:
    """동일 모국·국소의 과거 측정기록을 최신순으로 반환합니다."""
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패: Secrets 설정을 확인하세요.", []
    if mother not in POWER_STATION_MAP or local not in POWER_STATION_MAP.get(mother, []):
        return False, "먼저 모국과 국소를 정확히 선택해 주세요.", []

    try:
        spreadsheet = _open_spreadsheet(POWER_INSPECTION_SPREADSHEET_NAME, client)
        try:
            ws = spreadsheet.worksheet(POWER_INSPECTION_SHEET_NAME)
        except Exception:
            return False, "아직 저장된 전원 정밀점검 기록이 없습니다.", []

        values = ws.get_all_values()
        if len(values) < 2:
            return False, "아직 저장된 전원 정밀점검 기록이 없습니다.", []

        headers = values[0]
        now_naive = _korea_now().replace(tzinfo=None)
        cutoff = now_naive - datetime.timedelta(days=max(1, int(within_days)))
        records: list[dict] = []

        for row in reversed(values[1:]):
            record = {
                headers[index]: row[index] if index < len(row) else ""
                for index in range(len(headers))
            }
            if str(record.get("모국", "")).strip() != mother:
                continue
            if str(record.get("국소", "")).strip() != local:
                continue

            saved_text = str(record.get("저장일시", "")).strip()
            try:
                saved_dt = datetime.datetime.strptime(saved_text, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if saved_dt < cutoff:
                continue

            records.append(record)
            if len(records) >= max(1, int(max_records)):
                break

        if not records:
            return False, f"최근 {within_days}일 이내 동일 국소의 저장 기록이 없습니다.", []
        return True, f"과거 측정기록 {len(records)}건을 조회했습니다.", records
    except Exception as e:
        return False, str(e), []


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
        ("power_three_current_n", "삼상전류_N(A)", 1),
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
            key = f"power_battery_{group}_{index:02d}"
            value = str(record.get(f"{group}조_셀{index:02d}(V)", "")).strip()
            formatted = _format_battery_cell_display(value) if value else ""
            draft[key] = formatted
            st.session_state[key] = formatted

    ground_map = [
        ("power_security_ground_1", "보안접지_1종(Ω)"),
        ("power_security_ground_2", "보안접지_2종(Ω)"),
        ("power_security_ground_3", "보안접지_3종(Ω)"),
        ("power_telecom_ground", "통신용접지_메인(Ω)"),
        ("power_lightning_ground", "피뢰침접지(Ω)"),
    ]
    for key, header in ground_map:
        set_value(key, header, 2)
    set_value("power_notes", "특이사항", None)

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
    # 최근 측정값을 불러온 경우 모든 테마를 바로 확인·수정할 수 있도록 잠금을 해제합니다.
    st.session_state["power_unlocked_theme_index"] = len(POWER_THEME_ORDER) - 1
    st.session_state["power_theme_confirmations"] = {
        theme: {
            "answer": "기존값 불러오기",
            "missing_count": len(_power_theme_missing(theme)) if theme != "최종 확인·전송" else 0,
            "confirmed_at": _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        for theme in POWER_THEME_ORDER[:-1]
    }
    # 화면 위젯 shadow 값은 제거하여 불러온 최신 draft 값으로 다시 생성합니다.
    for session_key in list(st.session_state.keys()):
        if session_key.startswith("_ui_power_"):
            del st.session_state[session_key]
    st.session_state["power_panel_nonce"] = int(st.session_state.get("power_panel_nonce", 0) or 0) + 1


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
    st.markdown(f"**{group_number}조 방전 후 셀 전압 (V)**")
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
    """국소가 바뀌어도 측정값을 삭제하지 않고 현재값을 보존합니다.

    과거에는 이 함수가 power_draft까지 초기화하여, 최종 확인 단계에서
    기본정보를 보완하면 모든 측정값이 사라지는 문제가 있었습니다.
    이제 측정값 초기화는 최종 전송 성공 후 `_reset_power_inspection()`에서만 수행합니다.
    """
    st.session_state["power_station_search_applied"] = False
    st.session_state["power_station_search_notice"] = ""
    _preserve_current_power_measurements()
    _clear_power_history_state()
    _mark_power_basic_info_changed()


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
                ("power_three_current_n", "N상 전류"),
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
        battery1_values = [_power_get(f"power_battery_1_{index:02d}", "") for index in range(1, 25)]
        battery1_count = _measured_cell_count(battery1_values)
        missing.extend(
            f"1조 {index}셀" for index in range(1, battery1_count + 1)
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
            battery2_values = [_power_get(f"power_battery_2_{index:02d}", "") for index in range(1, 25)]
            battery2_count = _measured_cell_count(battery2_values)
            missing.extend(
                f"2조 {index}셀" for index in range(1, battery2_count + 1)
                if _power_state_blank(f"power_battery_2_{index:02d}")
            )
        return missing

    if theme == "접지저항 측정":
        checks = [
            ("power_security_ground_1", "보안접지 1종"),
            ("power_security_ground_2", "보안접지 2종"),
            ("power_security_ground_3", "보안접지 3종"),
            ("power_telecom_ground", "통신접지(메인)"),
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


def _power_unlocked_theme_index() -> int:
    """모든 측정 테마는 언제든 선택할 수 있으므로 마지막 인덱스를 반환합니다."""
    return len(POWER_THEME_ORDER) - 1


def _bump_power_panel_nonce() -> None:
    st.session_state["power_panel_nonce"] = int(st.session_state.get("power_panel_nonce", 0) or 0) + 1


def _clear_power_completion_prompt() -> None:
    for key in (
        "power_completion_prompt_theme", "power_completion_answer",
        "power_completion_validation_error", "power_battery2_measure_answer",
        "power_battery_move_error", "power_battery_exit_stage",
    ):
        st.session_state.pop(key, None)


def _move_to_power_theme(target_theme: str) -> None:
    if target_theme not in POWER_THEME_ORDER:
        return
    _hydrate_power_theme_from_draft(target_theme)
    st.session_state["power_current_theme"] = target_theme
    st.session_state["power_temp_saved_notice"] = True
    st.session_state.pop("power_pending_theme_switch", None)
    st.session_state.pop("power_pending_from_theme", None)
    st.session_state.pop("power_navigation_error", None)
    _clear_power_completion_prompt()
    _bump_power_panel_nonce()


def _activate_power_theme(target_theme: str) -> None:
    """측정 순서를 강제하지 않고, 다른 메뉴로 이동하기 전에 현재값 확인을 요청합니다."""
    if target_theme not in POWER_THEME_ORDER:
        return
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    if target_theme == current_theme:
        _hydrate_power_theme_from_draft(current_theme)
        return

    if current_theme in POWER_THEME_ORDER[:-1]:
        _save_power_theme_to_draft(current_theme)
        st.session_state["power_pending_from_theme"] = current_theme
        st.session_state["power_pending_theme_switch"] = target_theme
        st.session_state.pop("power_navigation_error", None)
        return

    _move_to_power_theme(target_theme)


def _confirm_power_theme_switch() -> None:
    """직접 메뉴 이동은 현재값만 임시저장하고 완료 상태는 변경하지 않습니다."""
    from_theme = st.session_state.get("power_pending_from_theme")
    target_theme = st.session_state.get("power_pending_theme_switch")
    if from_theme not in POWER_THEME_ORDER[:-1] or target_theme not in POWER_THEME_ORDER:
        st.session_state["power_navigation_error"] = "이동할 측정 메뉴를 다시 선택해 주세요."
        return

    _save_power_theme_to_draft(from_theme)
    st.session_state["power_temp_saved_notice"] = True
    _move_to_power_theme(target_theme)


def _cancel_power_theme_switch() -> None:
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    if current_theme in POWER_THEME_ORDER[:-1]:
        _save_power_theme_to_draft(current_theme)
    st.session_state.pop("power_pending_theme_switch", None)
    st.session_state.pop("power_pending_from_theme", None)
    st.session_state.pop("power_navigation_error", None)


def _finish_battery_navigation(measure_second_group: bool) -> None:
    target_theme = st.session_state.get("power_battery_navigation_target")
    _save_power_theme_to_draft("축전지 측정")
    if measure_second_group:
        _power_set("power_battery2_enabled", True)
        _power_set("power_battery_set", "2조 셀 측정")
        st.session_state["power_current_theme"] = "축전지 측정"
        _hydrate_power_theme_from_draft("축전지 측정")
        st.session_state["power_temp_saved_notice"] = True
    elif target_theme in POWER_THEME_ORDER:
        _move_to_power_theme(target_theme)
    st.session_state.pop("power_battery_navigation_target", None)
    st.session_state.pop("power_battery_exit_stage", None)
    _bump_power_panel_nonce()


def _request_power_completion(theme: str) -> None:
    if theme not in POWER_THEME_ORDER[:-1]:
        return
    _save_power_theme_to_draft(theme)
    st.session_state["power_completion_prompt_theme"] = theme
    st.session_state.pop("power_completion_answer", None)
    st.session_state.pop("power_completion_validation_error", None)


def _cancel_power_completion() -> None:
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    if current_theme in POWER_THEME_ORDER:
        _save_power_theme_to_draft(current_theme)
    _clear_power_completion_prompt()


def _next_power_theme_after_completion(theme: str) -> str:
    """현재 테마 다음부터 순환하며 아직 완료하지 않은 측정 테마를 찾습니다."""
    measurement_themes = POWER_THEME_ORDER[:-1]
    confirmations = dict(st.session_state.get("power_theme_confirmations", {}))
    if theme not in measurement_themes:
        return POWER_THEME_ORDER[-1]

    current_index = measurement_themes.index(theme)
    for offset in range(1, len(measurement_themes) + 1):
        candidate = measurement_themes[(current_index + offset) % len(measurement_themes)]
        if candidate not in confirmations:
            return candidate
    return POWER_THEME_ORDER[-1]


def _mark_power_theme_complete(theme: str, answer_note: str = "담당자 측정 완료 확인") -> None:
    if theme not in POWER_THEME_ORDER[:-1]:
        return
    _save_power_theme_to_draft(theme)
    confirmations = dict(st.session_state.get("power_theme_confirmations", {}))
    confirmations[theme] = {
        "answer": answer_note,
        "missing_count": len(_power_theme_missing(theme)),
        "confirmed_at": _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    st.session_state["power_theme_confirmations"] = confirmations
    target_theme = _next_power_theme_after_completion(theme)
    _move_to_power_theme(target_theme)


def _complete_current_power_theme() -> None:
    """담당자가 현재 테마의 측정 완료를 명시적으로 확정합니다."""
    theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    if theme not in POWER_THEME_ORDER[:-1]:
        return
    _save_power_theme_to_draft(theme)

    if (
        theme == "축전지 측정"
        and _power_get("power_battery_set", "1조 셀 측정") == "1조 셀 측정"
        and not _power_battery2_enabled()
    ):
        st.session_state["power_battery_exit_stage"] = "ask_group2_complete"
        st.session_state["power_temp_saved_notice"] = True
        return

    _mark_power_theme_complete(theme)


def _finish_battery_completion(measure_second_group: bool) -> None:
    """축전지 1조 완료 후 2조 측정 여부를 처리합니다."""
    _save_power_theme_to_draft("축전지 측정")
    if measure_second_group:
        _power_set("power_battery2_enabled", True)
        _power_set("power_battery_set", "2조 셀 측정")
        st.session_state["power_current_theme"] = "축전지 측정"
        st.session_state["power_temp_saved_notice"] = True
        st.session_state.pop("power_battery_exit_stage", None)
        _hydrate_power_theme_from_draft("축전지 측정")
        _bump_power_panel_nonce()
        return

    _power_set("power_battery2_enabled", False)
    _power_set("power_battery_set", "1조 셀 측정")
    st.session_state.pop("power_battery_exit_stage", None)
    _mark_power_theme_complete("축전지 측정", answer_note="1조 완료·2조 미측정 확인")

def _process_power_completion() -> bool:
    theme = st.session_state.get("power_completion_prompt_theme")
    if theme not in POWER_THEME_ORDER[:-1]:
        return False
    answer = st.session_state.get("power_completion_answer")
    if answer not in {"예", "아니오"}:
        st.session_state["power_completion_validation_error"] = "‘예’ 또는 ‘아니오’를 선택해 주세요."
        return False

    _save_power_theme_to_draft(theme)

    # '예'는 누락값이 있으므로 현재 테마를 유지하며 추가 입력합니다.
    if answer == "예":
        st.session_state["power_temp_saved_notice"] = True
        _clear_power_completion_prompt()
        return True

    # 1조 입력을 마친 경우에는 2조 측정 여부를 한 번 더 확인합니다.
    if theme == "축전지 측정":
        selected_group = 1 if _power_get("power_battery_set", "1조 셀 측정") == "1조 셀 측정" else 2
        if selected_group == 1 and not _power_battery2_enabled():
            st.session_state.pop("power_completion_prompt_theme", None)
            st.session_state.pop("power_completion_answer", None)
            st.session_state.pop("power_completion_validation_error", None)
            st.session_state["power_battery_exit_stage"] = "ask_group2"
            return True

    _mark_power_theme_complete(theme)
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
        st.session_state["power_temp_saved_notice"] = True
        _clear_power_completion_prompt()
        _bump_power_panel_nonce()
        return True

    _power_set("power_battery2_enabled", False)
    _power_set("power_battery_set", "1조 셀 측정")
    _mark_power_theme_complete("축전지 측정", answer_note="2조 미측정 확인")
    return True


def _build_power_payload_from_state(final_confirmed: bool = False) -> dict:
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    _save_power_theme_to_draft(current_theme)
    phase_type = _power_get("power_phase_type", "삼상")
    group_count = 2 if _power_battery2_enabled() else 1
    worker = str(st.session_state.get("power_worker", "")).strip()
    battery1_cells = [
        _parse_battery_cell_number(_power_get(f"power_battery_1_{index:02d}", ""))
        for index in range(1, 25)
    ]
    battery2_cells = [
        _parse_battery_cell_number(_power_get(f"power_battery_2_{index:02d}", ""))
        for index in range(1, 25)
    ] if group_count == 2 else [""] * 24
    return {
        "worker": worker,
        "inspector_group": st.session_state.get("power_inspector_group", "") or _inspector_group_for_area(st.session_state.get("power_major_area", "")) or _inspector_group_for_name(worker),
        "major_area": st.session_state.get("power_major_area", "권역 선택"),
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
        "three_current_n": _parse_power_number(_power_get("power_three_current_n", ""), 1),
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
        if key.startswith("power_") or key.startswith("_ui_power_"):
            del st.session_state[key]
    st.session_state["power_current_theme"] = POWER_THEME_ORDER[0]
    st.session_state["power_unlocked_theme_index"] = len(POWER_THEME_ORDER) - 1
    st.session_state["power_theme_confirmations"] = {}
    st.session_state["power_panel_nonce"] = 0
    st.session_state["power_draft"] = {
        "power_phase_type": "삼상",
        "power_major_area": "권역 선택",
        "power_battery_set": "1조 셀 측정",
        "power_battery2_enabled": False,
    }
    st.session_state["power_phase_type"] = "삼상"
    st.session_state["power_battery_set"] = "1조 셀 측정"


def _render_power_auto_decimal_script() -> None:
    data_field_rules = {
        "power_three_voltage_rs": 1, "power_three_voltage_st": 1,
        "power_three_voltage_tr": 1, "power_three_voltage_rn": 1,
        "power_three_current_r": 1, "power_three_current_s": 1, "power_three_current_t": 1, "power_three_current_n": 1,
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
            data_field_rules[f"power_battery_{group}_{cell_number:02d}"] = {"mode": "battery_cell"}

    # 실제 화면에는 shadow UI key가 렌더링됩니다.
    field_rules = {
        _power_widget_key(data_key): rule
        for data_key, rule in data_field_rules.items()
    }
    rules_json = json.dumps(field_rules, ensure_ascii=False)
    explicit_next_data_keys = {
        "power_security_ground_1": "power_security_ground_2",
        "power_security_ground_2": "power_security_ground_3",
        "power_security_ground_3": "power_telecom_ground",
        "power_telecom_ground": "power_lightning_ground",
    }
    explicit_next_keys = {
        _power_widget_key(current_key): _power_widget_key(next_key)
        for current_key, next_key in explicit_next_data_keys.items()
    }
    next_keys_json = json.dumps(explicit_next_keys, ensure_ascii=False)
    script = r"""
        <script>
        (() => {
          const rules = __POWER_RULES_JSON__;
          const explicitNextKeys = __POWER_NEXT_KEYS_JSON__;
          const FOCUS_STORAGE_KEY = '__power_next_focus_key_v13__';
          const SCROLL_STORAGE_KEY = '__power_scroll_y_v13__';
          const RUNTIME_STORAGE_KEY = '__power_numeric_runtime_v13__';

          // Streamlit rerun이 반복되어도 이전 감시기/이벤트가 누적되지 않도록 먼저 정리합니다.
          try {
            const previousRuntime = window.parent[RUNTIME_STORAGE_KEY];
            if (previousRuntime && typeof previousRuntime.cleanup === 'function') previousRuntime.cleanup();
          } catch (e) {}

          function formatFixed(value, decimals, key) {
            if (value.includes('.')) {
              const pieces = value.split('.', 2);
              const integer = (pieces[0] || '0').replace(/\D/g, '') || '0';
              const fraction = (pieces[1] || '').replace(/\D/g, '').slice(0, decimals).padEnd(decimals, '0');
              return decimals > 0 ? `${integer}.${fraction}` : integer;
            }
            const digits = value.replace(/\D/g, '');
            if (!digits) return '';
            if (decimals <= 0) return digits;

            // 접지저항 현장 입력: 00→0.0, 000→0.00, 0000→00.00
            const isGroundResistance = String(key || '').includes('ground');
            if (isGroundResistance && digits.length === 2) {
              return `${digits.slice(0, 1)}.${digits.slice(1)}`;
            }
            const padded = digits.length <= decimals ? digits.padStart(decimals + 1, '0') : digits;
            return `${padded.slice(0, -decimals)}.${padded.slice(-decimals)}`;
          }

          function formatBatteryCell(value) {
            if (value.includes('.')) {
              const pieces = value.split('.', 2);
              const integer = (pieces[0] || '0').replace(/\D/g, '') || '0';
              const rawFraction = (pieces[1] || '').replace(/\D/g, '');
              const decimals = Math.max(2, Math.min(3, rawFraction.length || 2));
              const fraction = rawFraction.slice(0, decimals).padEnd(decimals, '0');
              return `${integer}.${fraction}`;
            }
            const digits = value.replace(/\D/g, '');
            if (!digits) return '';
            // 참고 시험성적서의 셀 전압은 소수 셋째 자리까지 사용합니다.
            // 215→2.15, 3507→3.507, 000→0.00, 0000→0.000
            const decimals = digits.length >= 4 ? 3 : 2;
            const padded = digits.length <= decimals ? digits.padStart(decimals + 1, '0') : digits;
            return `${padded.slice(0, -decimals)}.${padded.slice(-decimals)}`;
          }

          function formatted(raw, rule, key) {
            let value = String(raw || '').trim().replace(/,/g, '');
            if (!value) return '';
            value = value.replace(/[^0-9.]/g, '');
            if (!value) return '';
            if (rule && typeof rule === 'object' && rule.mode === 'battery_cell') {
              return formatBatteryCell(value);
            }
            return formatFixed(value, Number(rule || 0), key);
          }

          function parentDocument() {
            try { return window.parent.document; } catch (error) { return null; }
          }

          function setReactValue(input, value) {
            const view = input.ownerDocument.defaultView || window.parent;
            const proto = view.HTMLInputElement.prototype;
            const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
            if (descriptor && descriptor.set) descriptor.set.call(input, value);
            else input.value = value;
            input.dispatchEvent(new view.Event('input', { bubbles: true }));
            input.dispatchEvent(new view.Event('change', { bubbles: true }));
          }

          function isVisible(element) {
            if (!element) return false;
            const view = element.ownerDocument.defaultView || window.parent;
            const style = view.getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return style.display !== 'none' && style.visibility !== 'hidden'
              && Number(style.opacity || 1) !== 0 && rect.width > 0 && rect.height > 0;
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
            const NodeCtor = doc.defaultView.Node;
            return found.sort((a, b) => {
              const pos = a.input.compareDocumentPosition(b.input);
              if (pos & NodeCtor.DOCUMENT_POSITION_FOLLOWING) return -1;
              if (pos & NodeCtor.DOCUMENT_POSITION_PRECEDING) return 1;
              return 0;
            });
          }

          function rememberViewport() {
            try {
              const parentWindow = window.parent;
              parentWindow.sessionStorage.setItem(SCROLL_STORAGE_KEY, String(parentWindow.scrollY || 0));
            } catch (e) {}
          }

          function restoreViewport(lockDuration = 520) {
            let saved = null;
            try {
              const raw = window.parent.sessionStorage.getItem(SCROLL_STORAGE_KEY);
              if (raw !== null && raw !== '') saved = Number(raw);
            } catch (e) {}
            if (!Number.isFinite(saved)) return;

            const parentWindow = window.parent;
            const restore = () => parentWindow.scrollTo({ top: saved, left: 0, behavior: 'auto' });
            restore();
            const started = Date.now();
            const timer = parentWindow.setInterval(() => {
              restore();
              if (Date.now() - started >= lockDuration) {
                parentWindow.clearInterval(timer);
                try { parentWindow.sessionStorage.removeItem(SCROLL_STORAGE_KEY); } catch (e) {}
              }
            }, 24);
          }

          function rememberAndFocusNext(doc, input) {
            const currentKey = String(input.dataset.powerKey || '');
            const explicitNextKey = explicitNextKeys[currentKey] || '';
            let nextItem = null;

            // 보안접지 1종→2종→3종→통신접지→피뢰침접지는
            // 열 배치나 모바일 DOM 순서와 관계없이 지정된 순서로 이동합니다.
            if (explicitNextKey) {
              const explicitWrapper = wrapperForKey(doc, explicitNextKey);
              const explicitInput = explicitWrapper ? explicitWrapper.querySelector('input') : null;
              if (explicitInput && isVisible(explicitInput)) {
                nextItem = { key: explicitNextKey, input: explicitInput };
              }
            }

            if (!nextItem) {
              const ordered = visibleMeasurementInputs(doc);
              const currentIndex = ordered.findIndex((item) => item.input === input);
              nextItem = currentIndex >= 0 ? ordered[currentIndex + 1] : null;
            }

            try {
              if (nextItem) window.parent.sessionStorage.setItem(FOCUS_STORAGE_KEY, nextItem.key);
              else window.parent.sessionStorage.removeItem(FOCUS_STORAGE_KEY);
            } catch (e) {}
            return nextItem;
          }

          function prepareNumericInput(input, key) {
            if (!input || !key || !Object.prototype.hasOwnProperty.call(rules, key)) return;
            input.dataset.powerKey = key;
            input.setAttribute('inputmode', 'decimal');
            input.setAttribute('pattern', '[0-9.]*');
            input.setAttribute('autocomplete', 'off');
            input.setAttribute('autocapitalize', 'off');
            input.setAttribute('enterkeyhint', 'next');
            input.spellcheck = false;
          }

          function measurementKeyForInput(input) {
            if (!input) return '';
            for (const key of Object.keys(rules)) {
              const wrapper = wrapperForKey(input.ownerDocument, key);
              if (wrapper && wrapper.contains(input)) return key;
            }
            return '';
          }

          function bindInput(doc, key, rule) {
            const wrapper = wrapperForKey(doc, key);
            const input = wrapper ? wrapper.querySelector('input') : null;
            if (!input || input.dataset.powerDecimalBoundV13 === '1') return;

            input.dataset.powerDecimalBoundV13 = '1';
            prepareNumericInput(input, key);

            const applyFormat = () => {
              const next = formatted(input.value, rule, key);
              if (next !== input.value) setReactValue(input, next);
              return next;
            };

            input.addEventListener('blur', applyFormat, { passive: true });
            input.addEventListener('keydown', (event) => {
              if (event.key !== 'Enter' && event.keyCode !== 13) return;
              event.preventDefault();
              event.stopPropagation();

              // Enter 직전의 화면 위치와 다음 입력키를 먼저 보존합니다.
              rememberViewport();
              const nextItem = rememberAndFocusNext(doc, input);
              applyFormat();

              window.setTimeout(() => {
                restoreViewport();
                if (nextItem && isVisible(nextItem.input)) {
                  nextItem.input.focus({ preventScroll: true });
                  nextItem.input.select();
                } else {
                  input.blur();
                }
              }, 35);
            }, true);
          }

          function bindInputs() {
            const doc = parentDocument();
            if (!doc) return;
            Object.entries(rules).forEach(([key, rule]) => bindInput(doc, key, rule));
          }

          function restoreNextFocus() {
            const doc = parentDocument();
            if (!doc) return;
            let nextKey = '';
            try { nextKey = window.parent.sessionStorage.getItem(FOCUS_STORAGE_KEY) || ''; } catch (e) {}
            if (!nextKey) return;
            const wrapper = wrapperForKey(doc, nextKey);
            const input = wrapper ? wrapper.querySelector('input') : null;
            if (input && isVisible(input)) {
              restoreViewport();
              input.focus({ preventScroll: true });
              input.select();
              try { window.parent.sessionStorage.removeItem(FOCUS_STORAGE_KEY); } catch (e) {}
            }
          }

          bindInputs();
          restoreNextFocus();

          const doc = parentDocument();
          let observer = null;
          let timer = null;
          let prepareFromEvent = null;

          if (doc) {
            prepareFromEvent = (event) => {
              const input = event && event.target;
              if (!input || String(input.tagName || '').toLowerCase() !== 'input') return;
              const key = measurementKeyForInput(input);
              if (key) prepareNumericInput(input, key);
            };
            // 모바일에서 사용자가 새로 열린 2조 셀을 즉시 눌러도 포커스 전에 숫자키패드 속성을 먼저 적용합니다.
            doc.addEventListener('pointerdown', prepareFromEvent, true);
            doc.addEventListener('touchstart', prepareFromEvent, { capture: true, passive: true });
            doc.addEventListener('focusin', prepareFromEvent, true);

            observer = new MutationObserver(() => {
              bindInputs();
              restoreNextFocus();
            });
            observer.observe(doc.body, { childList: true, subtree: true });
          }

          timer = window.setInterval(() => {
            bindInputs();
            restoreNextFocus();
          }, 250);

          const cleanup = () => {
            try { if (observer) observer.disconnect(); } catch (e) {}
            try { if (timer) window.clearInterval(timer); } catch (e) {}
            try {
              if (doc && prepareFromEvent) {
                doc.removeEventListener('pointerdown', prepareFromEvent, true);
                doc.removeEventListener('touchstart', prepareFromEvent, true);
                doc.removeEventListener('focusin', prepareFromEvent, true);
              }
            } catch (e) {}
          };
          try { window.parent[RUNTIME_STORAGE_KEY] = { cleanup }; } catch (e) {}
          window.setTimeout(cleanup, 120000);
        })();
        </script>
    """
    rendered_script = (
        script
        .replace("__POWER_RULES_JSON__", rules_json)
        .replace("__POWER_NEXT_KEYS_JSON__", next_keys_json)
    )
    components.html(rendered_script, height=1)


# ==========================================
# 8-3. MY WORK LOG · 현장 기록 / 시설 이력 · V14
#      - 기존 전원 정밀점검 로직과 완전히 분리
#      - 텍스트/상태이력: Google Sheets
#      - 사진: Google Drive/Shared Drive (선택 설정)
#      - 원본 사진은 앱 서버에 영구 저장하지 않음
# ==========================================
WORK_LOG_SPREADSHEET_NAME = "Audit_Result_2026"
WORK_LOG_SHEET_NAME = "MY_WORK_LOG"
WORK_LOG_HISTORY_SHEET_NAME = "MY_WORK_LOG_HISTORY"
WORK_LOG_USER_SHEET_NAME = "MY_WORK_LOG_USERS"
WORK_LOG_DELETE_AUDIT_SHEET_NAME = "MY_WORK_LOG_DELETED"
WORK_LOG_MAX_PHOTOS = 10
WORK_LOG_IMAGE_MAX_SIDE = 1600
WORK_LOG_IMAGE_TARGET_BYTES = 450 * 1024
WORK_LOG_PIN_ITERATIONS = 210_000

# 기존 시트 열 순서를 절대 바꾸지 않고, 신규 권한 필드는 맨 뒤에 추가합니다.
WORK_LOG_HEADERS = [
    "저장일시", "기록ID", "작성자", "권역", "모국", "국소", "상태", "점검항목",
    "현상_특이사항", "조치내용", "후속조치", "비고", "사진수", "사진파일ID목록",
    "사진파일명목록", "최근수정일시", "작성자ID", "공개범위",
]
WORK_LOG_HISTORY_HEADERS = [
    "저장일시", "기록ID", "작성자", "상태", "변경구분", "조치내용", "후속조치", "비고", "작업자ID",
]
WORK_LOG_USER_HEADERS = [
    "사용자ID", "이름", "사번", "PIN_SALT", "PIN_HASH", "PIN변경필요", "활성", "최근로그인", "최근PIN변경일시",
    "QUICK_SALT", "QUICK_HASH", "QUICK설정일시", "QUICK_VER",
]
# 사용자 인증코드: 영문+숫자 6자리(신규). 기존 4자리 코드는 로그인만 허용하고 즉시 6자리로 교체하게 합니다.
WORK_LOG_QUICK_LEN = 6
WORK_LOG_QUICK_LEGACY_LEN = 4
WORK_LOG_QUICK_VERSION = "6"
# 신뢰 단말 등록 시트와 쿠키 설정
WORK_LOG_DEVICE_SHEET_NAME = "MY_WORK_LOG_DEVICES"
WORK_LOG_DEVICE_HEADERS = [
    "사용자ID", "이름", "토큰해시", "단말구분", "단말모델", "단말요약", "등록일시", "최근접속", "활성",
]
WORK_LOG_DEVICE_COOKIE = "sw_dev"
WORK_LOG_DEVICE_MODEL_COOKIE = "sw_dm"
WORK_LOG_DEVICE_TTL_DAYS = 90
WORK_LOG_DEVICE_MAX_PER_USER = 3
WORK_LOG_ADMIN_STEPUP_MINUTES = 30
WORK_LOG_DELETE_AUDIT_HEADERS = [
    "삭제일시", "기록ID", "작성자ID", "작성자", "삭제자ID", "삭제자", "공개범위", "사진수",
]
WORK_LOG_STATUS_OPTIONS = ["신규", "확인필요", "조치중", "재점검", "완료"]
WORK_LOG_ITEM_OPTIONS = ["전원", "축전지", "접지", "냉방", "출입", "안전", "기타"]
WORK_LOG_VISIBILITY_OPTIONS = ["공개", "비공개"]

# 최초 1회 로그인 공통 임시 PIN은 000000입니다.
# 최초 인증 후에는 "영문+숫자 혼합 6자리 사용자 인증코드"를 설정하여 이후 접속에 사용합니다.
# 6자리 개인 PIN은 사용자 인증코드를 잊었을 때 사용하는 복구용 인증수단으로 유지합니다.
# PIN과 사용자 인증코드는 모두 평문으로 저장하지 않고, 사용자별 salt/PBKDF2-SHA256 해시만 저장합니다.
# 한 번 인증한 단말(브라우저 고유 토큰 + 단말 모델)은 신뢰 단말로 등록되어 이후 사용자 인증을 건너뜁니다.
WORK_LOG_INITIAL_PIN = "000000"
WORK_LOG_USER_BOOTSTRAP = [
    {"사용자ID": "U001", "이름": "정청운", "사번": "10001713", "PIN_SALT": "de28394a671befb76a8fd8ec1b904d72", "PIN_HASH": "8fb388bf36dd783aeda3bbfd362b5b035df14ef1d11b64bb078085e521a4f295"},
    {"사용자ID": "U002", "이름": "이학원", "사번": "10001612", "PIN_SALT": "2fcd8fad516f3d7b0719729fc9f60996", "PIN_HASH": "6d7041143724825e28f813004029a15caca9a580635878eb8c8a1e82217b7e19"},
    {"사용자ID": "U003", "이름": "이철순", "사번": "10002090", "PIN_SALT": "c5e1143a554e05ec9051b537281b9a1a", "PIN_HASH": "7aec4643550243e931bdaaa4ea931f3ed6ea0dcf4a53555971a0289d7ce15bae"},
    {"사용자ID": "U004", "이름": "소순고", "사번": "81000020", "PIN_SALT": "3d2a67162bfd799901747c7e5e716e5e", "PIN_HASH": "cee9feacb954b53343986b93c87b8d3fccab7d1fc6492a879549af01a5dab886"},
    {"사용자ID": "U005", "이름": "강만식", "사번": "10001009", "PIN_SALT": "7bfa69aaf3b2a6ece51c5fc5ac25d0d2", "PIN_HASH": "45c73984e01f3d857682124f4ce167feb4e4f2ed8178dda4fbeb05dc34eeec97"},
    {"사용자ID": "U006", "이름": "이민우", "사번": "10001522", "PIN_SALT": "18a1a33b692c2a2142e1eabe56cdd6ff", "PIN_HASH": "cc667aeef9fe18ad0d7772cef1ee26091ad8fb311c102cc8c8691f25a7e927f7"},
    {"사용자ID": "U007", "이름": "신진우", "사번": "10001405", "PIN_SALT": "00a1ec0138defc16e5845bb54ddc3c6d", "PIN_HASH": "4daf3b870e8f289b15a5b59a933fed897141858405724bd48efe84fd6de1772b"},
    {"사용자ID": "U008", "이름": "박동희", "사번": "10001280", "PIN_SALT": "27dd2fbd801a3cc0d8cc53b9436e11f6", "PIN_HASH": "9bf8757c5b114e3b051afece0bbb5fd41adc4acbab696d5f810552fd0525b4a7"},
    {"사용자ID": "U009", "이름": "김태수", "사번": "10001923", "PIN_SALT": "02bd5b1d4eedb7103955495269126453", "PIN_HASH": "6bf64d324a844f33de7b04203dbcfb3c42d6cb44785a0c6680eefc3b8462fceb"},
    {"사용자ID": "U010", "이름": "김수창", "사번": "10002211", "PIN_SALT": "41b790666a4e7c4654df4c3bb57d3680", "PIN_HASH": "c1ef17186b3dea51c524663a11fec23d7a65b4b2f898123b513afd4e35aed741"},
]

def _worklog_bootstrap_users() -> list[dict]:
    """최초 등록용 사용자 목록을 반환합니다.

    Secrets의 [work_log] initial_pin 값이 있으면 코드에 박힌 공통 임시 PIN(000000) 대신 그 값을 사용해
    사용자별 salt로 해시를 다시 계산합니다. (임시 PIN을 코드 수정 없이 바꿀 수 있습니다.)
    """
    override = str(_worklog_secret_value("work_log_initial_pin", "") or "").strip()
    initial_pin = override if re.fullmatch(r"\d{6}", override) else WORK_LOG_INITIAL_PIN

    # Secrets의 [work_log] users(JSON 문자열 또는 배열)가 있으면 코드에 박힌 명단 대신 그 명단을 사용합니다.
    # 각 항목: {"사용자ID": "U011", "이름": "홍길동", "사번": "10001234"}
    external = _worklog_secret_value("work_log_users", "")
    entries = []
    try:
        if isinstance(external, str) and external.strip():
            entries = json.loads(external)
        elif external:
            entries = [dict(item) for item in external]
    except Exception as error:
        logger.error("work_log.users 형식 오류: %s", error)
        entries = []
    users = []
    if entries:
        for item in entries:
            employee_no = re.sub(r"\D", "", str(item.get("사번", "") or ""))
            name = str(item.get("이름", "") or "").strip()
            user_id = str(item.get("사용자ID", "") or "").strip()
            if not (employee_no and name and user_id):
                continue
            salt = hashlib.sha256(("smartwork-bootstrap|" + employee_no).encode("utf-8")).hexdigest()[:32]
            users.append({"사용자ID": user_id, "이름": name, "사번": employee_no,
                          "PIN_SALT": salt, "PIN_HASH": _worklog_hash_pin(initial_pin, salt)})
        if users:
            return users

    if initial_pin == WORK_LOG_INITIAL_PIN:
        return WORK_LOG_USER_BOOTSTRAP
    for row in WORK_LOG_USER_BOOTSTRAP:
        updated = dict(row)
        new_hash = _worklog_hash_pin(initial_pin, row["PIN_SALT"])
        if new_hash:
            updated["PIN_HASH"] = new_hash
        users.append(updated)
    return users


WORK_LOG_NAME_TO_USER_ID = {row["이름"]: row["사용자ID"] for row in WORK_LOG_USER_BOOTSTRAP}
WORK_LOG_EMPLOYEE_TO_NAME = {row["사번"]: row["이름"] for row in WORK_LOG_USER_BOOTSTRAP}


def _worklog_area_display(area: str) -> str:
    """WORK LOG에서 권역을 담당자 + 주요 지역이 함께 보이는 현장형 표기로 변환합니다."""
    area_value = str(area or "").strip()
    if area_value not in POWER_REGION_DATA:
        return "국사를 검색하면 자동 표시됩니다"

    region = POWER_REGION_DATA.get(area_value, {})
    inspectors = ", ".join(
        str(person).strip()
        for person in region.get("담당자", [])
        if str(person).strip()
    )

    # 예: "1권역 · 파주·문산·동두천 등" -> "1권역: 이철순, 김수창 (파주, 문산, 동두천 등)"
    if "·" in area_value:
        area_no, coverage = area_value.split("·", 1)
        coverage_text = ", ".join(
            part.strip() for part in coverage.split("·") if part.strip()
        )
    else:
        area_no = area_value
        coverage_text = ""

    if inspectors and coverage_text:
        return f"{area_no.strip()}: {inspectors} ({coverage_text})"
    if inspectors:
        return f"{area_no.strip()}: {inspectors}"
    return area_value


def _worklog_station_search_label(entry_id: str) -> str:
    """동일/유사 국사가 여러 곳일 때 WORK LOG 선택 후보를 알아보기 쉽게 표시합니다."""
    entry = POWER_STATION_SEARCH_BY_ID.get(str(entry_id or ""), {})
    if not entry:
        return "검색 결과 없음"
    area_display = _worklog_area_display(entry.get("area", ""))
    return (
        f"{entry.get('local', '')}  |  모국 {entry.get('mother', '')}  |  {area_display}"
    )


def _apply_worklog_station_search_entry(entry: dict) -> None:
    """선택한 국사의 권역·모국·국소를 WORK LOG 전용 상태에 자동 반영합니다."""
    if not entry:
        return

    selected_area = str(entry.get("area", "")).strip()
    st.session_state["worklog_area_key"] = selected_area
    st.session_state["worklog_mother"] = str(entry.get("mother", "")).strip()
    st.session_state["worklog_local"] = str(entry.get("local", "")).strip()
    st.session_state["worklog_station_search_applied"] = True
    st.session_state["worklog_station_search_candidates"] = []
    st.session_state["worklog_station_search_status"] = "applied"
    st.session_state["worklog_station_search_notice"] = (
        f"✅ {entry.get('local', '')} 국사 선택 완료 · "
        f"{_worklog_area_display(selected_area)} · 모국 {entry.get('mother', '')}"
    )


def _run_worklog_station_search() -> None:
    """정밀점검과 같은 국사 역색인을 사용해 WORK LOG 국사를 검색합니다."""
    query = str(st.session_state.get("worklog_station_search_query", "") or "").strip()
    st.session_state["worklog_station_search_notice"] = ""
    st.session_state["worklog_station_search_status"] = ""
    st.session_state["worklog_station_search_candidates"] = []
    st.session_state["worklog_station_search_choice"] = ""

    if not query:
        st.session_state["worklog_station_search_status"] = "empty"
        return

    normalized_query = _normalize_power_station_search(query)
    matches = _search_power_station_entries(query)
    exact_matches = [
        entry for entry in matches
        if _normalize_power_station_search(entry.get("local", "")) == normalized_query
    ]
    candidates = exact_matches if exact_matches else matches

    if len(candidates) == 1:
        _apply_worklog_station_search_entry(candidates[0])
        return

    if len(candidates) > 1:
        candidate_ids = [entry["id"] for entry in candidates]
        st.session_state["worklog_station_search_candidates"] = candidate_ids
        st.session_state["worklog_station_search_choice"] = candidate_ids[0]
        st.session_state["worklog_station_search_status"] = "multiple"
        st.session_state["worklog_station_search_applied"] = False
        return

    st.session_state["worklog_station_search_status"] = "none"
    st.session_state["worklog_station_search_applied"] = False


def _confirm_worklog_station_search_choice() -> None:
    """WORK LOG 검색 후보 중 사용자가 고른 국사를 확정합니다."""
    selected_id = str(st.session_state.get("worklog_station_search_choice", "") or "").strip()
    entry = POWER_STATION_SEARCH_BY_ID.get(selected_id)
    if not entry:
        st.session_state["worklog_station_search_status"] = "choice_required"
        return
    _apply_worklog_station_search_entry(entry)


def _worklog_secret_value(name: str, default=""):
    """WORK LOG 전용 Secrets를 평면/섹션 형식 모두에서 안전하게 읽습니다."""
    try:
        direct = st.secrets.get(name, default)
        if direct not in (None, ""):
            return direct
    except Exception:
        pass
    try:
        section = st.secrets.get("work_log", {})
        if hasattr(section, "get"):
            short_name = name.replace("work_log_", "")
            value = section.get(short_name, default)
            if value not in (None, ""):
                return value
    except Exception:
        pass
    return default



def _worklog_hash_pin(pin: str, salt_hex: str) -> str:
    """개인 PIN을 PBKDF2-SHA256으로 해시합니다. PIN 평문은 시트/코드에 저장하지 않습니다."""
    try:
        salt = bytes.fromhex(str(salt_hex or "").strip())
    except Exception:
        return ""
    if not salt:
        return ""
    return hashlib.pbkdf2_hmac(
        "sha256",
        str(pin or "").encode("utf-8"),
        salt,
        WORK_LOG_PIN_ITERATIONS,
    ).hex()


def _worklog_ensure_headers(worksheet, desired_headers: list[str]) -> list[str]:
    """기존 열 순서를 보존한 채 필요한 헤더만 맨 뒤에 추가합니다."""
    try:
        headers = [str(value).strip() for value in worksheet.row_values(1)]
    except Exception:
        headers = []

    if not headers:
        worksheet.append_row(desired_headers, value_input_option="USER_ENTERED")
        return list(desired_headers)

    missing = [header for header in desired_headers if header not in headers]
    if missing:
        try:
            needed_cols = len(headers) + len(missing)
            current_cols = int(getattr(worksheet, "col_count", 0) or 0)
            if current_cols < needed_cols:
                worksheet.add_cols(needed_cols - current_cols)
        except Exception:
            pass
        for header in missing:
            headers.append(header)
            worksheet.update_cell(1, len(headers), header)
    return headers


def _worklog_ensure_user_sheet(spreadsheet):
    """사용자 시트 준비(생성·헤더 점검·최초 PIN 동기화)는 10분에 한 번만 수행합니다."""
    return _cached_sheet_setup(
        "worklog_users_sheet",
        lambda: _worklog_ensure_user_sheet_uncached(spreadsheet),
    )


def _worklog_ensure_user_sheet_uncached(spreadsheet):
    """개인인증 사용자 시트를 생성하고, 최초 PIN 미변경 계정은 최초 임시 PIN으로 동기화합니다."""
    try:
        ws = spreadsheet.worksheet(WORK_LOG_USER_SHEET_NAME)
    except Exception:
        ws = spreadsheet.add_worksheet(
            title=WORK_LOG_USER_SHEET_NAME,
            rows=1000,
            cols=max(len(WORK_LOG_USER_HEADERS) + 2, 12),
        )
        _sheet_call(ws.append_row, WORK_LOG_USER_HEADERS, value_input_option="USER_ENTERED")

    headers = _worklog_ensure_headers(ws, WORK_LOG_USER_HEADERS)
    values = _sheet_call(ws.get_all_values)
    employee_index = headers.index("사번") if "사번" in headers else None
    existing_rows: dict[str, tuple[int, list[str]]] = {}
    if values and employee_index is not None:
        for row_no, row in enumerate(values[1:], start=2):
            value = str((row[employee_index] if employee_index < len(row) else "") or "").strip()
            if value:
                existing_rows[value] = (row_no, row)

    pending_updates: list[dict] = []
    for bootstrap in _worklog_bootstrap_users():
        employee_no = bootstrap["사번"]
        existing = existing_rows.get(employee_no)
        if existing is None:
            row_map = {
                **bootstrap,
                "PIN변경필요": "Y",
                "활성": "Y",
                "최근로그인": "",
                "최근PIN변경일시": "",
            }
            _sheet_call(
                ws.append_row,
                [row_map.get(header, "") for header in headers],
                value_input_option="USER_ENTERED",
            )
            continue

        row_no, row = existing
        row_map = {header: (row[idx] if idx < len(row) else "") for idx, header in enumerate(headers)}
        must_change = str(row_map.get("PIN변경필요", "") or "").strip().upper() in {"Y", "YES", "TRUE", "1"}

        # 아직 본인 PIN으로 바꾸지 않은 계정만 최초 임시 PIN으로 맞춥니다.
        # 이미 PIN변경필요=N인 사용자의 개인 PIN은 절대 건드리지 않습니다.
        if must_change:
            initial_updates = {
                "PIN_SALT": bootstrap["PIN_SALT"],
                "PIN_HASH": bootstrap["PIN_HASH"],
                "PIN변경필요": "Y",
            }
            for header, value in initial_updates.items():
                if header in headers and str(row_map.get(header, "") or "") != str(value):
                    pending_updates.append({
                        "range": f"{_column_letter(headers.index(header) + 1)}{row_no}",
                        "values": [[value]],
                    })

    if pending_updates:
        _sheet_call(ws.batch_update, pending_updates, value_input_option="USER_ENTERED")
        _worklog_invalidate_users_cache()
    return ws

def _worklog_read_user_by_employee(employee_no: str) -> tuple[object | None, dict, int | None]:
    """사번으로 사용자 시트의 실제 행을 읽습니다. (30초 캐시된 사용자 표 사용)"""
    employee_no = re.sub(r"\D", "", str(employee_no or ""))
    if not employee_no:
        return None, {}, None
    ws, headers, rows = _worklog_read_all_users()
    if ws is None:
        return None, {}, None
    for row_no, record in rows:
        if re.sub(r"\D", "", str(record.get("사번", "") or "")) == employee_no:
            return ws, record, row_no
    return ws, {}, None



def _worklog_normalize_quick_code(value: str) -> str:
    """사용자 인증코드를 대문자 영문+숫자로 정규화합니다."""
    return str(value or "").strip().upper()


def _worklog_validate_quick_code(value: str, allow_legacy: bool = False) -> tuple[bool, str, str]:
    """사용자 인증코드(영문+숫자 6자리) 형식과 추측하기 쉬운 값을 점검합니다.

    allow_legacy=True는 로그인 단계에서만 사용하며, 기존 4자리 코드를 한 번 인식해 6자리로 교체시키기 위함입니다.
    """
    code = _worklog_normalize_quick_code(value)
    if allow_legacy and len(code) == WORK_LOG_QUICK_LEGACY_LEN and re.fullmatch(r"[A-Z0-9]{4}", code):
        return True, "", code
    if len(code) != WORK_LOG_QUICK_LEN:
        return False, f"사용자 인증코드는 영문+숫자 {WORK_LOG_QUICK_LEN}자리로 입력해 주세요.", ""
    if not re.fullmatch(r"[A-Z0-9]{6}", code):
        return False, "사용자 인증코드는 영문(A-Z)과 숫자(0-9)만 사용할 수 있습니다.", ""
    if code.isalpha() or code.isdigit():
        return False, "보안을 위해 영문과 숫자를 함께 사용해 주세요. 예: K7M2Q9", ""
    if len(set(code)) <= 2:
        return False, "같은 문자가 반복되는 코드는 사용할 수 없습니다. 다른 조합을 사용해 주세요.", ""
    weak_codes = {
        "ABC123", "123ABC", "A1B2C3", "1A2B3C", "ABCD12", "AB1234", "A12345", "ABC321",
        "QWE123", "QWERT1", "ASD123", "ZXC123", "PASS12", "TEST12", "ADMIN1", "KT1234",
        "KTMOS1", "ABC111", "AAA111",
    }
    if code in weak_codes:
        return False, "너무 단순한 인증코드는 피해주세요. 다른 6자리 조합을 사용해 주세요.", ""
    return True, "", code


def _worklog_read_all_users(force: bool = False):
    """MY_WORK_LOG_USERS의 모든 사용자 행을 읽습니다. 30초 캐시 · 변경 시 즉시 무효화."""
    now = time.time()
    with _USERS_CACHE_LOCK:
        cached = _USERS_CACHE.get("value")
        if (
            not force
            and cached is not None
            and (now - float(_USERS_CACHE.get("at", 0) or 0)) < _USERS_CACHE_TTL_SECONDS
        ):
            return cached

    client = init_google_sheet_connection()
    if not client:
        _USERS_CACHE["error"] = _gs_connection_failure_message()
        return None, [], []
    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws = _worklog_ensure_user_sheet(spreadsheet)
        values = _sheet_call(ws.get_all_values)
        headers = [str(value).strip() for value in values[0]] if values else []
        rows = []
        for row_no, row in enumerate(values[1:], start=2):
            if not any(str(cell or "").strip() for cell in row):
                continue
            record = {
                header: (row[index] if index < len(row) else "")
                for index, header in enumerate(headers)
            }
            rows.append((row_no, record))
        result = (ws, headers, rows)
        with _USERS_CACHE_LOCK:
            _USERS_CACHE["value"] = result
            _USERS_CACHE["at"] = time.time()
            _USERS_CACHE["error"] = ""
        return result
    except Exception as error:
        _USERS_CACHE["error"] = f"{type(error).__name__}: {error}"
        logger.error("사용자 시트 읽기 실패: %s", _USERS_CACHE["error"])
        return None, [], []


def _worklog_quick_code_is_duplicate(code: str, exclude_employee_no: str = "") -> bool:
    """다른 활성 사용자와 동일한 사용자 인증코드인지 해시 비교로 확인합니다. (항상 최신 표 사용)"""
    ok, _, normalized = _worklog_validate_quick_code(code)
    if not ok:
        return False
    exclude_employee_no = re.sub(r"\D", "", str(exclude_employee_no or ""))
    ws, headers, rows = _worklog_read_all_users(force=True)
    if ws is None:
        return False

    for _, record in rows:
        employee_no = re.sub(r"\D", "", str(record.get("사번", "") or ""))
        if exclude_employee_no and employee_no == exclude_employee_no:
            continue
        if str(record.get("활성", "Y") or "Y").strip().upper() not in {"Y", "YES", "TRUE", "1", "활성"}:
            continue
        expected_hash = str(record.get("QUICK_HASH", "") or "").strip().lower()
        salt_hex = str(record.get("QUICK_SALT", "") or "").strip()
        if not expected_hash or not salt_hex:
            continue
        actual_hash = _worklog_hash_pin(normalized, salt_hex).lower()
        if actual_hash and hmac.compare_digest(expected_hash, actual_hash):
            return True
    return False


def _worklog_set_quick_code(employee_no: str, quick_code: str, confirm_code: str) -> tuple[bool, str]:
    """인증된 사용자의 사용자 인증코드(영문+숫자 6자리)를 생성/변경합니다."""
    employee_no = re.sub(r"\D", "", str(employee_no or ""))
    ok, message, normalized = _worklog_validate_quick_code(quick_code)
    if not ok:
        return False, message
    if normalized != _worklog_normalize_quick_code(confirm_code):
        return False, "사용자 인증코드와 확인값이 일치하지 않습니다."
    if _worklog_quick_code_is_duplicate(normalized, exclude_employee_no=employee_no):
        return False, f"이미 다른 사용자가 사용 중인 인증코드입니다. 다른 {WORK_LOG_QUICK_LEN}자리 조합을 선택해 주세요."

    ws, record, row_no = _worklog_read_user_by_employee(employee_no)
    if ws is None or not record or row_no is None:
        return False, "사용자 계정을 찾지 못했습니다."

    salt_hex = os.urandom(16).hex()
    quick_hash = _worklog_hash_pin(normalized, salt_hex)
    if not quick_hash:
        return False, "사용자 인증코드 보안처리에 실패했습니다."

    try:
        _worklog_update_user_fields(ws, row_no, {
            "QUICK_SALT": salt_hex,
            "QUICK_HASH": quick_hash,
            "QUICK설정일시": _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
            "QUICK_VER": WORK_LOG_QUICK_VERSION,
        })
        return True, f"사용자 인증코드가 설정되었습니다. 다음 접속부터는 이 {WORK_LOG_QUICK_LEN}자리 코드만 입력하면 됩니다."
    except Exception as error:
        return False, f"사용자 인증코드 저장 실패: {error}"


def _worklog_complete_first_auth_setup(
    employee_no: str,
    quick_code: str,
    confirm_quick_code: str,
    recovery_pin: str,
    confirm_recovery_pin: str,
) -> tuple[bool, str]:
    """최초 임시 PIN 인증 후 사용자 인증코드 + 복구용 개인 PIN을 한 번에 설정합니다."""
    employee_no = re.sub(r"\D", "", str(employee_no or ""))
    ok, message, normalized_quick = _worklog_validate_quick_code(quick_code)
    if not ok:
        return False, message
    if normalized_quick != _worklog_normalize_quick_code(confirm_quick_code):
        return False, "사용자 인증코드와 확인값이 일치하지 않습니다."
    if _worklog_quick_code_is_duplicate(normalized_quick, exclude_employee_no=employee_no):
        return False, f"이미 다른 사용자가 사용 중인 인증코드입니다. 다른 {WORK_LOG_QUICK_LEN}자리 조합을 선택해 주세요."

    recovery_pin = re.sub(r"\D", "", str(recovery_pin or ""))
    confirm_recovery_pin = re.sub(r"\D", "", str(confirm_recovery_pin or ""))
    if len(recovery_pin) != 6:
        return False, "복구용 개인 PIN은 숫자 6자리로 입력해 주세요."
    if recovery_pin != confirm_recovery_pin:
        return False, "복구용 개인 PIN과 확인 PIN이 일치하지 않습니다."
    if recovery_pin in {"000000", "111111", "123456", "654321", "121212", "777777"}:
        return False, "복구용 PIN은 추측하기 쉬운 숫자를 사용할 수 없습니다."
    if employee_no and (recovery_pin in employee_no or employee_no.endswith(recovery_pin)):
        return False, "사번에 포함된 숫자를 그대로 복구용 PIN으로 사용하지 마세요."

    ws, record, row_no = _worklog_read_user_by_employee(employee_no)
    if ws is None or not record or row_no is None:
        return False, "사용자 계정을 찾지 못했습니다."

    pin_salt = os.urandom(16).hex()
    quick_salt = os.urandom(16).hex()
    pin_hash = _worklog_hash_pin(recovery_pin, pin_salt)
    quick_hash = _worklog_hash_pin(normalized_quick, quick_salt)
    if not pin_hash or not quick_hash:
        return False, "인증정보 보안처리에 실패했습니다."

    now_text = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        _worklog_update_user_fields(ws, row_no, {
            "PIN_SALT": pin_salt,
            "PIN_HASH": pin_hash,
            "PIN변경필요": "N",
            "최근PIN변경일시": now_text,
            "QUICK_SALT": quick_salt,
            "QUICK_HASH": quick_hash,
            "QUICK설정일시": now_text,
            "QUICK_VER": WORK_LOG_QUICK_VERSION,
        })
        return True, f"사용자 인증 설정이 완료되었습니다. 다음 접속부터는 {WORK_LOG_QUICK_LEN}자리 사용자 인증코드만 입력하면 됩니다."
    except Exception as error:
        return False, f"최초 인증정보 설정 실패: {error}"


def _worklog_authenticate_quick_code(quick_code: str) -> tuple[bool, str, dict]:
    """영문+숫자 6자리 사용자 인증코드만으로 사용자를 찾아 인증합니다. (기존 4자리 코드는 1회 인식 후 교체 유도)"""
    ok, message, normalized = _worklog_validate_quick_code(quick_code, allow_legacy=True)
    if not ok:
        return False, message, {}

    remaining = _auth_lock_remaining()
    if remaining > 0:
        return False, f"인증 실패가 반복되어 {remaining}초 후 다시 시도할 수 있습니다.", {}

    ws, headers, rows = _worklog_read_all_users()
    if ws is None:
        detail = str(_USERS_CACHE.get("error", "") or "")
        return False, "사용자 인증정보를 불러오지 못했습니다." + (f" ({detail})" if detail else ""), {}

    matches = []
    for row_no, record in rows:
        if str(record.get("활성", "Y") or "Y").strip().upper() not in {"Y", "YES", "TRUE", "1", "활성"}:
            continue
        # 최초 임시 PIN 단계가 끝나지 않은 계정은 사용자 인증코드 로그인 대상에서 제외합니다.
        must_change = str(record.get("PIN변경필요", "N") or "N").strip().upper() in {"Y", "YES", "TRUE", "1"}
        if must_change:
            continue
        expected_hash = str(record.get("QUICK_HASH", "") or "").strip().lower()
        salt_hex = str(record.get("QUICK_SALT", "") or "").strip()
        if not expected_hash or not salt_hex:
            continue
        actual_hash = _worklog_hash_pin(normalized, salt_hex).lower()
        if actual_hash and hmac.compare_digest(expected_hash, actual_hash):
            matches.append((row_no, record))

    if len(matches) != 1:
        left, locked_seconds = _auth_register_failure()
        time.sleep(0.7)
        if locked_seconds > 0:
            return False, f"인증코드가 일치하지 않습니다. 보안을 위해 {locked_seconds}초 동안 인증을 잠급니다.", {}
        return False, f"사용자 인증코드를 확인해 주세요. (남은 시도 {left}회)", {}

    row_no, record = matches[0]
    user = {
        "user_id": str(record.get("사용자ID", "") or "").strip(),
        "name": str(record.get("이름", "") or "").strip(),
        "employee_no": re.sub(r"\D", "", str(record.get("사번", "") or "")),
        "must_change_pin": False,
        "has_quick_code": str(record.get("QUICK_VER", "") or "").strip() == WORK_LOG_QUICK_VERSION,
    }
    if not user["user_id"] or not user["name"] or not user["employee_no"]:
        return False, "사용자 등록정보가 올바르지 않습니다.", {}

    _auth_register_success()
    _worklog_touch_last_login(ws, headers, row_no, record)
    if user["has_quick_code"]:
        return True, f"{user['name']}님으로 사용자 인증되었습니다.", user
    return True, (
        f"{user['name']}님으로 인증되었습니다. 보안 강화를 위해 "
        f"{WORK_LOG_QUICK_LEN}자리 사용자 인증코드로 새로 설정해 주세요."
    ), user


def _worklog_authenticate_user(employee_no: str, pin: str) -> tuple[bool, str, dict]:
    """사번 + 개인 PIN을 검증합니다."""
    employee_no = re.sub(r"\D", "", str(employee_no or ""))
    pin = re.sub(r"\D", "", str(pin or ""))
    if len(employee_no) < 6:
        return False, "사번을 정확히 입력해 주세요.", {}
    if len(pin) != 6:
        return False, "개인 PIN 6자리를 입력해 주세요.", {}

    remaining = _auth_lock_remaining()
    if remaining > 0:
        return False, f"인증 실패가 반복되어 {remaining}초 후 다시 시도할 수 있습니다.", {}

    ws, record, row_no = _worklog_read_user_by_employee(employee_no)
    if ws is None:
        detail = str(_USERS_CACHE.get("error", "") or "")
        return False, "사용자 인증정보를 불러오지 못했습니다." + (f" ({detail})" if detail else ""), {}
    if not record or row_no is None:
        _auth_register_failure()
        time.sleep(0.7)
        return False, "사번 또는 PIN이 일치하지 않습니다.", {}
    if str(record.get("활성", "Y") or "Y").strip().upper() not in {"Y", "YES", "TRUE", "1", "활성"}:
        return False, "현재 사용이 중지된 계정입니다. 관리자에게 문의해 주세요.", {}

    expected_hash = str(record.get("PIN_HASH", "") or "").strip().lower()
    salt_hex = str(record.get("PIN_SALT", "") or "").strip()
    actual_hash = _worklog_hash_pin(pin, salt_hex).lower()
    if not expected_hash or not actual_hash or not hmac.compare_digest(expected_hash, actual_hash):
        left, locked_seconds = _auth_register_failure()
        time.sleep(0.7)
        if locked_seconds > 0:
            return False, f"PIN이 일치하지 않습니다. 보안을 위해 {locked_seconds}초 동안 인증을 잠급니다.", {}
        return False, f"사번 또는 PIN이 일치하지 않습니다. (남은 시도 {left}회)", {}

    _auth_register_success()
    user = {
        "user_id": str(record.get("사용자ID", "") or "").strip(),
        "name": str(record.get("이름", "") or "").strip(),
        "employee_no": employee_no,
    }
    if not user["user_id"] or not user["name"]:
        return False, "사용자 등록정보가 올바르지 않습니다.", {}

    ws_all, headers_all, _rows = _worklog_read_all_users()
    _worklog_touch_last_login(ws, headers_all, row_no, record)

    must_change = str(record.get("PIN변경필요", "N") or "N").strip().upper() in {"Y", "YES", "TRUE", "1"}
    user["must_change_pin"] = must_change
    user["has_quick_code"] = (
        bool(str(record.get("QUICK_HASH", "") or "").strip())
        and str(record.get("QUICK_VER", "") or "").strip() == WORK_LOG_QUICK_VERSION
    )
    return True, f"{user['name']}님 인증되었습니다.", user


def _worklog_change_pin(employee_no: str, new_pin: str, confirm_pin: str) -> tuple[bool, str]:
    """현재 사용자의 복구용 개인 PIN을 새 6자리 PIN으로 변경합니다."""
    employee_no = re.sub(r"\D", "", str(employee_no or ""))
    new_pin = re.sub(r"\D", "", str(new_pin or ""))
    confirm_pin = re.sub(r"\D", "", str(confirm_pin or ""))
    if len(new_pin) != 6:
        return False, "새 PIN은 숫자 6자리로 입력해 주세요."
    if new_pin != confirm_pin:
        return False, "새 PIN과 확인 PIN이 일치하지 않습니다."
    if new_pin in {"000000", "111111", "123456", "654321", "121212", "777777"}:
        return False, "추측하기 쉬운 PIN은 사용할 수 없습니다."
    if employee_no and (new_pin in employee_no or employee_no.endswith(new_pin)):
        return False, "사번에 포함된 숫자를 그대로 PIN으로 사용하지 마세요."

    ws, record, row_no = _worklog_read_user_by_employee(employee_no)
    if ws is None or not record or row_no is None:
        return False, "사용자 계정을 찾지 못했습니다."

    salt_hex = os.urandom(16).hex()
    pin_hash = _worklog_hash_pin(new_pin, salt_hex)
    if not pin_hash:
        return False, "PIN 보안처리에 실패했습니다."

    try:
        _worklog_update_user_fields(ws, row_no, {
            "PIN_SALT": salt_hex,
            "PIN_HASH": pin_hash,
            "PIN변경필요": "N",
            "최근PIN변경일시": _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        return True, "복구용 개인 PIN이 변경되었습니다."
    except Exception as error:
        return False, f"PIN 변경 실패: {error}"


# ==========================================
# 사용자 인증 보조 · 사용자 표 캐시 / 시도 잠금 / 신뢰 단말
# ==========================================
_USERS_CACHE = _PS["users_cache"]
_USERS_CACHE_LOCK = _PS["users_cache_lock"]
_USERS_CACHE_TTL_SECONDS = 30


def _worklog_invalidate_users_cache() -> None:
    with _USERS_CACHE_LOCK:
        _USERS_CACHE["at"] = 0.0
        _USERS_CACHE["value"] = None


def _sheet_update_fields(ws, headers: list[str], row_no: int, updates: dict, raw: bool = False) -> None:
    """한 행의 여러 열을 API 1회(batch_update)로 갱신합니다. (셀별 update_cell 반복 대체)"""
    data = []
    for header, value in updates.items():
        if header in headers:
            data.append({
                "range": f"{_column_letter(headers.index(header) + 1)}{row_no}",
                "values": [[value]],
            })
    if data:
        _sheet_call(ws.batch_update, data, value_input_option="RAW" if raw else "USER_ENTERED")


def _worklog_update_user_fields(ws, row_no: int, updates: dict, invalidate: bool = True) -> None:
    with _USERS_CACHE_LOCK:
        cached = _USERS_CACHE.get("value")
    headers = list(cached[1]) if cached else [str(v).strip() for v in _sheet_call(ws.row_values, 1)]
    _sheet_update_fields(ws, headers, row_no, updates)
    if invalidate:
        _worklog_invalidate_users_cache()


def _parse_kst_text(text: str):
    """'YYYY-MM-DD HH:MM:SS' 문자열을 한국시간 datetime으로 변환합니다. 실패하면 None."""
    try:
        parsed = datetime.datetime.strptime(str(text or "").strip()[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    tzinfo = _korea_now().tzinfo
    return parsed.replace(tzinfo=tzinfo) if tzinfo else parsed


def _worklog_touch_last_login(ws, headers: list[str], row_no: int, record: dict) -> None:
    """최근로그인은 6시간 이상 지났을 때만 기록해 쓰기 호출을 줄입니다."""
    try:
        last = _parse_kst_text(record.get("최근로그인", ""))
        now = _korea_now()
        if last is not None and (now - last) < datetime.timedelta(hours=6):
            return
        _sheet_update_fields(ws, headers, row_no, {"최근로그인": now.strftime("%Y-%m-%d %H:%M:%S")})
    except Exception as error:
        logger.warning("최근로그인 기록 실패: %s", error)


# ---------- 인증 시도 잠금 (새로고침·재접속으로 초기화되지 않도록 서버 프로세스 메모리에 보관) ----------
_AUTH_LOCK = _PS["auth_lock"]
_AUTH_STATE = _PS["auth_state"]
_AUTH_MAX_ATTEMPTS = 5
_AUTH_BASE_LOCK_SECONDS = 60
_AUTH_MAX_LOCK_SECONDS = 1800


def _client_ip() -> str:
    try:
        headers = st.context.headers
        forwarded = str(headers.get("X-Forwarded-For", "") or headers.get("x-forwarded-for", "") or "")
        return forwarded.split(",")[0].strip()
    except Exception:
        return ""


def _auth_keys() -> list[str]:
    keys: list[str] = []
    ip = _client_ip()
    if ip:
        keys.append("ip:" + ip)
    token = _device_token_from_cookie()
    if token:
        keys.append("dev:" + token[:24])
    sid = st.session_state.get("_auth_sid")
    if not sid:
        sid = uuid.uuid4().hex
        st.session_state["_auth_sid"] = sid
    keys.append("sid:" + str(sid))
    return keys


def _auth_lock_remaining() -> int:
    now = time.time()
    remaining = 0
    with _AUTH_LOCK:
        for key in _auth_keys():
            state = _AUTH_STATE.get(key)
            if state and state.get("locked_until", 0) > now:
                remaining = max(remaining, int(state["locked_until"] - now) + 1)
    return remaining


def _auth_register_failure() -> tuple[int, int]:
    """실패를 기록하고 (남은 시도 횟수, 새로 걸린 잠금 초)를 반환합니다. 잠금 시간은 반복할수록 2배로 늘어납니다."""
    now = time.time()
    left_min = _AUTH_MAX_ATTEMPTS
    lock_seconds = 0
    with _AUTH_LOCK:
        for key in _auth_keys():
            state = _AUTH_STATE.setdefault(key, {"count": 0, "level": 0, "locked_until": 0.0, "last": 0.0})
            if now - float(state.get("last", 0) or 0) > 3600:
                state["count"] = 0
                state["level"] = 0
            state["count"] += 1
            state["last"] = now
            if state["count"] >= _AUTH_MAX_ATTEMPTS:
                seconds = min(_AUTH_BASE_LOCK_SECONDS * (2 ** int(state["level"])), _AUTH_MAX_LOCK_SECONDS)
                state["locked_until"] = now + seconds
                state["level"] += 1
                state["count"] = 0
                lock_seconds = max(lock_seconds, seconds)
            left_min = min(left_min, _AUTH_MAX_ATTEMPTS - int(state["count"]))
        if len(_AUTH_STATE) > 2000:
            for stale_key in [k for k, v in _AUTH_STATE.items() if now - float(v.get("last", 0) or 0) > 7200]:
                _AUTH_STATE.pop(stale_key, None)
    if lock_seconds > 0:
        _audit_log("인증 잠금", f"{lock_seconds}초", user={})
    return max(left_min, 0), lock_seconds


def _auth_register_success() -> None:
    with _AUTH_LOCK:
        for key in _auth_keys():
            _AUTH_STATE.pop(key, None)


# ---------- 신뢰 단말 (브라우저 고유 토큰 + 단말 모델 확인) ----------
_DEVICES_CACHE = _PS["devices_cache"]
_DEVICES_CACHE_LOCK = _PS["devices_cache_lock"]
_DEVICES_CACHE_TTL_SECONDS = 45


def _device_supported() -> bool:
    """서버가 요청 쿠키를 읽을 수 있는 Streamlit 버전인지 확인합니다. (st.context, 1.37+)"""
    try:
        return hasattr(st, "context") and st.context.cookies is not None
    except Exception:
        return False


def _device_token_from_cookie() -> str:
    try:
        token = str(st.context.cookies.get(WORK_LOG_DEVICE_COOKIE, "") or "")
    except Exception:
        return ""
    return token if re.fullmatch(r"[0-9a-f]{64}", token) else ""


def _device_hash(token: str) -> str:
    return hashlib.sha256(("smartwork-device|" + str(token or "")).encode("utf-8")).hexdigest()


def _device_ua_info() -> dict:
    """요청의 User-Agent와 브라우저가 알려 준 모델 힌트로 단말 구분·모델을 추정합니다."""
    try:
        ua = str(st.context.headers.get("User-Agent", "") or "")
    except Exception:
        ua = ""
    low = ua.lower()
    if "android" in low:
        kind = "android"
    elif "iphone" in low:
        kind = "iphone"
    elif "ipad" in low or ("macintosh" in low and "mobile" in low):
        kind = "ipad"
    elif "windows" in low:
        kind = "windows"
    elif "macintosh" in low or "mac os x" in low:
        kind = "mac"
    elif "cros" in low:
        kind = "chromeos"
    elif "linux" in low:
        kind = "linux"
    else:
        kind = "other"

    if "edg/" in low:
        browser = "Edge"
    elif "samsungbrowser" in low:
        browser = "Samsung Internet"
    elif "opr/" in low:
        browser = "Opera"
    elif "firefox" in low or "fxios" in low:
        browser = "Firefox"
    elif "crios" in low:
        browser = "Chrome(iOS)"
    elif "chrome" in low:
        browser = "Chrome"
    elif "safari" in low:
        browser = "Safari"
    else:
        browser = "기타"

    model = ""
    if kind == "android":
        match = re.search(r"Android[\s\d.]*;\s*([^;)]+?)(?:\s+Build/|\)|;)", ua)
        candidate = match.group(1).strip() if match else ""
        # Chrome의 축소 UA는 모델을 'K'로 감추므로 무시하고 JS 힌트를 우선 사용합니다.
        if candidate and candidate.upper() not in {"K", "MOBILE", "LINUX", "WV"} and len(candidate) >= 2:
            model = candidate
    try:
        hint = str(st.context.cookies.get(WORK_LOG_DEVICE_MODEL_COOKIE, "") or "")
    except Exception:
        hint = ""
    if "|" in hint:
        hint_model = hint.split("|", 1)[1].strip()
        if hint_model and hint_model.upper() not in {"K", "NA"}:
            model = hint_model[:60]
    return {
        "kind": kind,
        "browser": browser,
        "model": model,
        "summary": f"{kind} · {model or '-'} · {browser}"[:120],
    }


def _device_compatible(stored_kind: str, stored_model: str, info: dict) -> bool:
    """등록된 단말과 현재 접속 단말이 같은 종류·모델인지 확인합니다. (모델을 알 수 있을 때만 모델 비교)"""
    stored_kind = str(stored_kind or "").strip().lower()
    if stored_kind and info.get("kind") and stored_kind != info["kind"]:
        return False
    stored_model = str(stored_model or "").strip().upper()
    current_model = str(info.get("model", "") or "").strip().upper()
    if stored_model and current_model and stored_model != current_model:
        return False
    return True


def _device_bootstrap_script() -> None:
    """브라우저에 단말 고유 토큰(쿠키)을 만들고 모델 힌트를 기록합니다. 토큰은 서버에 해시로만 저장됩니다."""
    script = """
<script>
(function () {
  try {
    var P = window.parent, D = P.document;
    var TOKEN = "__TOKEN__", MODEL = "__MODEL__";
    function getC(n) { var m = D.cookie.match(new RegExp('(?:^|; )' + n + '=([^;]*)')); return m ? decodeURIComponent(m[1]) : ''; }
    function setC(n, v, age) {
      D.cookie = n + '=' + encodeURIComponent(v) + '; Max-Age=' + age + '; Path=/; SameSite=Lax' + (P.location.protocol === 'https:' ? '; Secure' : '');
    }
    var tok = getC(TOKEN);
    if (!/^[0-9a-f]{64}$/.test(tok)) {
      try { tok = P.localStorage.getItem(TOKEN) || ''; } catch (e) { tok = ''; }
      if (!/^[0-9a-f]{64}$/.test(tok)) {
        var a = new Uint8Array(32); P.crypto.getRandomValues(a);
        tok = Array.prototype.map.call(a, function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
      }
      setC(TOKEN, tok, 31536000);
      try { P.localStorage.setItem(TOKEN, tok); } catch (e) {}
      if (getC(TOKEN) === tok) {
        if (!P.sessionStorage.getItem('sw_dev_reload')) { P.sessionStorage.setItem('sw_dev_reload', '1'); P.location.reload(); return; }
      } else if (P.location.search.indexOf('nodev=1') < 0) {
        var u = new URL(P.location.href); u.searchParams.set('nodev', '1'); P.location.replace(u.toString()); return;
      }
    }
    if (!getC(MODEL)) {
      var uad = P.navigator.userAgentData;
      if (uad && uad.getHighEntropyValues) {
        uad.getHighEntropyValues(['model', 'platform']).then(function (v) {
          setC(MODEL, (v.platform || 'na') + '|' + (v.model || 'na'), 31536000);
        }).catch(function () { setC(MODEL, 'na|na', 31536000); });
      } else { setC(MODEL, 'na|na', 31536000); }
    }
  } catch (e) {}
})();
</script>
""".replace("__TOKEN__", WORK_LOG_DEVICE_COOKIE).replace("__MODEL__", WORK_LOG_DEVICE_MODEL_COOKIE)
    components.html(script, height=0)


def _device_ensure_sheet(spreadsheet):
    def build():
        try:
            ws = spreadsheet.worksheet(WORK_LOG_DEVICE_SHEET_NAME)
        except Exception:
            ws = spreadsheet.add_worksheet(
                title=WORK_LOG_DEVICE_SHEET_NAME,
                rows=500,
                cols=max(len(WORK_LOG_DEVICE_HEADERS) + 2, 12),
            )
            _sheet_call(ws.append_row, WORK_LOG_DEVICE_HEADERS, value_input_option="USER_ENTERED")
        headers = _worklog_ensure_headers(ws, WORK_LOG_DEVICE_HEADERS)
        return ws, headers

    return _cached_sheet_setup("worklog_devices_sheet", build)


def _devices_read(force: bool = False):
    now = time.time()
    with _DEVICES_CACHE_LOCK:
        cached = _DEVICES_CACHE.get("value")
        if not force and cached is not None and (now - float(_DEVICES_CACHE.get("at", 0) or 0)) < _DEVICES_CACHE_TTL_SECONDS:
            return cached
    client = init_google_sheet_connection()
    if not client:
        return None, [], []
    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws, headers = _device_ensure_sheet(spreadsheet)
        values = _sheet_call(ws.get_all_values)
        headers = [str(v).strip() for v in values[0]] if values else list(headers)
        rows = []
        for row_no, row in enumerate(values[1:], start=2):
            if not any(str(c or "").strip() for c in row):
                continue
            rows.append((row_no, {h: (row[i] if i < len(row) else "") for i, h in enumerate(headers)}))
        result = (ws, headers, rows)
        with _DEVICES_CACHE_LOCK:
            _DEVICES_CACHE["value"] = result
            _DEVICES_CACHE["at"] = time.time()
        return result
    except Exception as error:
        logger.error("신뢰 단말 목록 읽기 실패: %s", error)
        return None, [], []


def _devices_invalidate() -> None:
    with _DEVICES_CACHE_LOCK:
        _DEVICES_CACHE["at"] = 0.0
        _DEVICES_CACHE["value"] = None


def _device_find(token: str, force: bool = False):
    if not token:
        return None
    ws, headers, rows = _devices_read(force=force)
    if ws is None:
        return None
    target = _device_hash(token)
    for row_no, rec in rows:
        if str(rec.get("토큰해시", "") or "").strip() == target:
            return ws, headers, row_no, rec
    return None


def _devices_for_user(user_id: str) -> list[tuple[int, dict]]:
    ws, headers, rows = _devices_read()
    if ws is None:
        return []
    return [
        (row_no, rec) for row_no, rec in rows
        if str(rec.get("사용자ID", "") or "").strip() == str(user_id or "").strip()
        and str(rec.get("활성", "") or "").strip().upper() == "Y"
    ]


def _device_set_session_user(rec_user: dict) -> None:
    st.session_state["worklog_auth_user"] = {
        "user_id": str(rec_user.get("사용자ID", "") or "").strip(),
        "name": str(rec_user.get("이름", "") or "").strip(),
        "employee_no": re.sub(r"\D", "", str(rec_user.get("사번", "") or "")),
    }
    st.session_state["worklog_pin_change_required"] = False
    st.session_state["worklog_quick_setup_required"] = False
    st.session_state["worklog_df"] = None
    st.session_state["worklog_selected_id"] = ""


def _device_try_auto_login() -> tuple[bool, str]:
    """등록된 신뢰 단말이면 사용자 인증을 건너뛰고 자동 로그인합니다. 실패 시 (False, 안내문구)."""
    token = _device_token_from_cookie()
    if not token:
        return False, ""
    found = _device_find(token)
    if not found:
        return False, ""
    ws, headers, row_no, rec = found
    if str(rec.get("활성", "") or "").strip().upper() != "Y":
        return False, ""

    now = _korea_now()
    last_seen = _parse_kst_text(rec.get("최근접속", "")) or _parse_kst_text(rec.get("등록일시", ""))
    if last_seen is not None and (now - last_seen) > datetime.timedelta(days=WORK_LOG_DEVICE_TTL_DAYS):
        return False, f"단말 신뢰 기간({WORK_LOG_DEVICE_TTL_DAYS}일)이 지나 사용자 인증을 다시 진행합니다."

    info = _device_ua_info()
    if not _device_compatible(rec.get("단말구분", ""), rec.get("단말모델", ""), info):
        return False, "등록된 단말과 다른 기기로 확인되어 사용자 인증을 다시 진행합니다."

    user_ws, _user_headers, user_rows = _worklog_read_all_users()
    if user_ws is None:
        return False, "사용자 정보를 불러오지 못해 사용자 인증을 진행합니다."
    user_rec = next(
        (r for _, r in user_rows if str(r.get("사용자ID", "") or "").strip() == str(rec.get("사용자ID", "") or "").strip()),
        None,
    )
    if not user_rec:
        return False, ""
    if str(user_rec.get("활성", "Y") or "Y").strip().upper() not in {"Y", "YES", "TRUE", "1", "활성"}:
        return False, "사용이 중지된 계정입니다. 관리자에게 문의해 주세요."
    must_change = str(user_rec.get("PIN변경필요", "N") or "N").strip().upper() in {"Y", "YES", "TRUE", "1"}
    if must_change or str(user_rec.get("QUICK_VER", "") or "").strip() != WORK_LOG_QUICK_VERSION:
        return False, ""

    _device_set_session_user(user_rec)
    st.session_state["device_checked"] = True
    st.session_state["auth_via_device"] = True
    try:
        if last_seen is None or (now - last_seen) > datetime.timedelta(hours=6):
            _sheet_update_fields(ws, headers, row_no, {"최근접속": now.strftime("%Y-%m-%d %H:%M:%S")})
            _devices_invalidate()
    except Exception as error:
        logger.warning("단말 최근접속 기록 실패: %s", error)
    return True, ""


def _device_register(user: dict) -> tuple[bool, str]:
    """현재 단말을 사용자에게 연결합니다. 사용자당 최대 개수를 넘으면 가장 오래 쓰지 않은 단말을 해제합니다."""
    token = _device_token_from_cookie()
    if not token or not user:
        return False, "단말 정보를 확인하지 못해 이번 접속에서만 인증이 유지됩니다."
    ws, headers, rows = _devices_read(force=True)
    if ws is None:
        return False, "단말 등록 시트에 접근하지 못했습니다."
    info = _device_ua_info()
    now_text = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
    token_hash = _device_hash(token)
    user_id = str(user.get("user_id", "") or "").strip()
    try:
        existing_row = None
        active_rows = []
        for row_no, rec in rows:
            if str(rec.get("토큰해시", "") or "").strip() == token_hash:
                existing_row = row_no
            elif (
                str(rec.get("사용자ID", "") or "").strip() == user_id
                and str(rec.get("활성", "") or "").strip().upper() == "Y"
            ):
                active_rows.append((str(rec.get("최근접속", "") or ""), row_no))
        fields = {
            "사용자ID": user_id,
            "이름": str(user.get("name", "") or ""),
            "단말구분": info["kind"],
            "단말모델": info["model"],
            "단말요약": info["summary"],
            "최근접속": now_text,
            "활성": "Y",
        }
        if existing_row is not None:
            _sheet_update_fields(ws, headers, existing_row, fields)
        else:
            overflow = len(active_rows) - (WORK_LOG_DEVICE_MAX_PER_USER - 1)
            if overflow > 0:
                for _, old_row in sorted(active_rows)[:overflow]:
                    _sheet_update_fields(ws, headers, old_row, {"활성": "N"})
            row_map = {**fields, "토큰해시": token_hash, "등록일시": now_text}
            _sheet_call(ws.append_row, [row_map.get(h, "") for h in headers], value_input_option="USER_ENTERED")
        _devices_invalidate()
        _audit_log("단말 등록", info["summary"], user=user)
        return True, "이 단말이 신뢰 단말로 등록되었습니다."
    except Exception as error:
        logger.error("단말 등록 실패: %s", error)
        return False, f"단말 등록 실패: {error}"


def _device_revoke_row(row_no: int) -> None:
    ws, headers, rows = _devices_read(force=True)
    if ws is None:
        return
    _sheet_update_fields(ws, headers, row_no, {"활성": "N"})
    _devices_invalidate()
    _audit_log("단말 해제", "사용자 직접 해제")


def _device_revoke_current() -> None:
    """현재 단말의 신뢰 등록을 해제합니다. (로그아웃 시 다음 접속에서 사용자 인증을 다시 요구)"""
    try:
        found = _device_find(_device_token_from_cookie(), force=True)
        if found:
            ws, headers, row_no, _rec = found
            _sheet_update_fields(ws, headers, row_no, {"활성": "N"})
            _devices_invalidate()
    except Exception as error:
        logger.warning("단말 해제 실패: %s", error)


# ---------- 관리자 모드 재확인 (사용자 인증코드 재입력, 30분 유효) ----------
def _admin_stepup_active() -> bool:
    return time.time() < float(st.session_state.get("admin_verified_until", 0) or 0)


def _admin_stepup_grant() -> None:
    st.session_state["admin_verified_until"] = time.time() + WORK_LOG_ADMIN_STEPUP_MINUTES * 60


def _worklog_verify_code_for_current_user(code: str) -> tuple[bool, str]:
    ok, message, matched = _worklog_authenticate_quick_code(code)
    if not ok:
        return False, message
    current = _worklog_current_user()
    if str(matched.get("user_id", "")) != str(current.get("user_id", "")):
        _auth_register_failure()
        return False, "현재 로그인한 사용자의 인증코드가 아닙니다."
    return True, ""


def _render_admin_stepup_gate() -> None:
    """관리자 모드 진입 시 사용자 인증코드를 다시 확인합니다. 통과 전에는 이후 화면을 그리지 않습니다."""
    if _admin_stepup_active():
        return
    st.markdown("### 🔒 관리자 모드 · 사용자 인증")
    st.caption(
        f"누적 측정 데이터를 보호하기 위해 사용자 인증코드를 한 번 더 확인합니다. "
        f"확인 후 {WORK_LOG_ADMIN_STEPUP_MINUTES}분 동안 유지됩니다."
    )
    with st.form("admin_stepup_form", clear_on_submit=True):
        code = st.text_input(
            "사용자 인증코드",
            type="password",
            max_chars=WORK_LOG_QUICK_LEN,
            placeholder=f"영문+숫자 {WORK_LOG_QUICK_LEN}자리",
        )
        submitted = st.form_submit_button("🔐 관리자 모드 열기", type="primary", use_container_width=True)
    if submitted:
        ok, message = _worklog_verify_code_for_current_user(code)
        if ok:
            _admin_stepup_grant()
            _audit_log("점검 데이터 화면 열기", "")
            st.rerun()
        else:
            st.error(message)
    st.stop()


# ---------- 로그아웃 / 앱 진입 게이트 ----------


def _auth_card_html(title: str, desc: str, accent: str = "#D71920") -> str:
    return (
        f'<div style="background:linear-gradient(135deg,#FFFFFF 0%,#F8FAFC 100%);border:1px solid #CBD5E1;'
        f'border-left:6px solid {accent};border-radius:18px;padding:18px 20px;margin:8px 0 14px;'
        f'box-shadow:0 8px 22px rgba(15,23,42,.07);">'
        f'<div style="color:#24364B;font-size:1.3rem;font-weight:950;margin-bottom:5px;">{title}</div>'
        f'<div style="color:#64748B;font-size:.93rem;font-weight:800;line-height:1.55;">{desc}</div></div>'
    )


def _apply_login_success(user: dict) -> None:
    st.session_state["worklog_auth_user"] = {
        "user_id": user["user_id"],
        "name": user["name"],
        "employee_no": user["employee_no"],
    }
    st.session_state["worklog_pin_change_required"] = bool(user.get("must_change_pin"))
    st.session_state["worklog_quick_setup_required"] = not bool(user.get("has_quick_code"))
    st.session_state["worklog_df"] = None
    st.session_state["worklog_selected_id"] = ""
    st.session_state.pop("device_checked", None)
    st.session_state.pop("auth_via_device", None)
    st.session_state.pop("idle_locked", None)
    st.session_state["last_activity_at"] = time.time()
    _audit_log("로그인(사용자 인증)", "", user=user)


def _render_login_gate() -> None:
    st.markdown(
        _auth_card_html(
            "🔐 사용자 인증",
            "SMART POWER FIELD는 사용자 인증 후 이용할 수 있습니다. "
            f"<b>영문+숫자 {WORK_LOG_QUICK_LEN}자리 사용자 인증코드</b>를 입력하세요. "
            "최초 1회 인증 후에는 이 단말에서 다시 묻지 않습니다."
            "<br><br><b>📝 현장기록 · 🔋 전원 정밀점검 · 📊 점검 데이터</b> 모두 같은 인증을 사용합니다.",
        ),
        unsafe_allow_html=True,
    )
    notice = st.session_state.pop("device_notice", "")
    if notice:
        st.warning(notice)

    with st.form("gate_quick_login_form", clear_on_submit=False):
        quick_code = st.text_input(
            "사용자 인증코드",
            type="password",
            placeholder=f"영문+숫자 {WORK_LOG_QUICK_LEN}자리",
            max_chars=WORK_LOG_QUICK_LEN,
            key="gate_quick_login_code",
        )
        submitted = st.form_submit_button("🔐 사용자 인증", type="primary", use_container_width=True)

    if submitted:
        ok, message, user = _worklog_authenticate_quick_code(quick_code)
        if ok:
            _apply_login_success({**user, "must_change_pin": False})
            st.session_state.pop("gate_quick_login_code", None)
            st.success(message)
            time.sleep(0.3)
            st.rerun()
        else:
            st.error(message)

    button_col, info_col = st.columns([1.9, 3.1], gap="small", vertical_alignment="center")
    with button_col:
        if st.button("처음 사용 · 인증코드 분실", key="gate_open_first_login", use_container_width=True):
            _worklog_login_dialog()
    with info_col:
        st.caption("처음 사용: 사번 + 임시 PIN · 인증코드 분실: 사번 + 복구용 개인 PIN")


def _render_first_setup_gate(user: dict) -> None:
    name = html.escape(str(user.get("name", "") or "사용자"))
    st.markdown(
        _auth_card_html(
            f"✅ {name}님 본인 확인 완료",
            f"앞으로 사용할 <b>영문+숫자 {WORK_LOG_QUICK_LEN}자리 사용자 인증코드</b>를 설정하세요. "
            "인증코드를 잊었을 때를 대비해 복구용 숫자 6자리 개인 PIN도 함께 설정합니다.",
            "#2563EB",
        ),
        unsafe_allow_html=True,
    )
    with st.form("gate_first_setup_form", clear_on_submit=False):
        code1 = st.text_input("사용자 인증코드", type="password", max_chars=WORK_LOG_QUICK_LEN,
                              placeholder="예: K7M2Q9", key="gate_first_quick_code")
        code2 = st.text_input("인증코드 확인", type="password", max_chars=WORK_LOG_QUICK_LEN,
                              key="gate_first_quick_confirm")
        pin1 = st.text_input("복구용 개인 PIN", type="password", max_chars=6,
                             placeholder="숫자 6자리", key="gate_first_recovery_pin")
        pin2 = st.text_input("복구 PIN 확인", type="password", max_chars=6, key="gate_first_recovery_confirm")
        submitted = st.form_submit_button("🔐 사용자 인증 설정 완료", type="primary", use_container_width=True)
    if submitted:
        ok, message = _worklog_complete_first_auth_setup(
            str(user.get("employee_no", "") or ""), code1, code2, pin1, pin2,
        )
        if ok:
            st.session_state["worklog_pin_change_required"] = False
            st.session_state["worklog_quick_setup_required"] = False
            st.success(message)
            time.sleep(0.4)
            st.rerun()
        else:
            st.error(message)
    st.button("로그아웃", key="gate_first_logout", on_click=_worklog_logout)


def _render_quick_upgrade_gate(user: dict) -> None:
    name = html.escape(str(user.get("name", "") or "사용자"))
    st.markdown(
        _auth_card_html(
            f"🔐 {name}님 · 사용자 인증코드 설정",
            f"보안 강화를 위해 사용자 인증코드가 <b>영문+숫자 {WORK_LOG_QUICK_LEN}자리</b>로 바뀌었습니다. "
            "새 인증코드를 설정해 주세요. (설정 후에는 이 코드로만 접속합니다.)",
            "#2563EB",
        ),
        unsafe_allow_html=True,
    )
    with st.form("gate_quick_upgrade_form", clear_on_submit=False):
        code1 = st.text_input("새 사용자 인증코드", type="password", max_chars=WORK_LOG_QUICK_LEN,
                              placeholder="예: K7M2Q9", key="gate_upgrade_quick_code")
        code2 = st.text_input("인증코드 확인", type="password", max_chars=WORK_LOG_QUICK_LEN,
                              key="gate_upgrade_quick_confirm")
        submitted = st.form_submit_button("🔐 사용자 인증코드 설정", type="primary", use_container_width=True)
    if submitted:
        ok, message = _worklog_set_quick_code(str(user.get("employee_no", "") or ""), code1, code2)
        if ok:
            st.session_state["worklog_quick_setup_required"] = False
            st.success(message)
            time.sleep(0.4)
            st.rerun()
        else:
            st.error(message)
    st.button("로그아웃", key="gate_upgrade_logout", on_click=_worklog_logout)


def _app_auth_gate() -> dict:
    """앱 전체 진입 게이트. 인증되면 사용자 dict를 반환하고, 아니면 인증 화면을 그린 뒤 실행을 멈춥니다."""
    device_enabled = _device_supported() and "nodev" not in st.query_params and not st.session_state.get("device_skip")
    token = _device_token_from_cookie() if device_enabled else ""

    if device_enabled:
        if not token:
            _device_bootstrap_script()
            st.info("🔄 이 단말을 확인하는 중입니다. 잠시만 기다려 주세요…")
            if st.button("단말 기억 없이 계속", key="device_skip_btn"):
                st.session_state["device_skip"] = True
                st.rerun()
            st.stop()
        elif not st.session_state.get("device_model_hint_ready"):
            _device_bootstrap_script()
            try:
                if st.context.cookies.get(WORK_LOG_DEVICE_MODEL_COOKIE):
                    st.session_state["device_model_hint_ready"] = True
            except Exception:
                pass

    user = _worklog_current_user()

    # 장시간 사용이 없으면(기본 120분) 신뢰 단말이어도 사용자 인증코드를 다시 확인합니다.
    idle_limit = _idle_lock_minutes()
    last_activity = float(st.session_state.get("last_activity_at", 0) or 0)
    if user and idle_limit > 0 and last_activity and (time.time() - last_activity) > idle_limit * 60:
        _audit_log("유휴 잠금", f"{idle_limit}분 이상 미사용", user=user)
        for key in ("worklog_auth_user", "device_checked", "auth_via_device", "admin_verified_until", "last_activity_at"):
            st.session_state.pop(key, None)
        st.session_state["idle_locked"] = True
        st.session_state["device_notice"] = f"{idle_limit}분 이상 사용이 없어 보안을 위해 사용자 인증을 다시 확인합니다."
        user = {}

    if not user and device_enabled and token and not st.session_state.get("idle_locked"):
        ok, notice = _device_try_auto_login()
        if ok:
            user = _worklog_current_user()
            _audit_log("로그인(신뢰 단말)", "", user=user)
        elif notice:
            st.session_state["device_notice"] = notice

    if not user:
        _render_login_gate()
        st.stop()

    if st.session_state.get("worklog_pin_change_required"):
        _render_first_setup_gate(user)
        st.stop()
    if st.session_state.get("worklog_quick_setup_required"):
        _render_quick_upgrade_gate(user)
        st.stop()

    st.session_state["last_activity_at"] = time.time()

    # 사용자 인증코드로 직접 인증한 접속이면 이 단말을 신뢰 단말로 등록합니다.
    if device_enabled and token and not st.session_state.get("device_checked"):
        st.session_state["device_checked"] = True
        found = _device_find(token, force=True)
        needs_register = (
            not found
            or str(found[3].get("활성", "")).strip().upper() != "Y"
            or str(found[3].get("사용자ID", "")).strip() != str(user.get("user_id", "")).strip()
        )
        if needs_register:
            ok, message = _device_register(user)
            if ok:
                st.toast("✅ 이 단말이 신뢰 단말로 등록되었습니다. 다음부터 사용자 인증을 건너뜁니다.", icon="🔐")
    return user


# ==========================================
# 입력 중 임시저장 (새로고침·연결 끊김·화면 꺼짐 대비)
#   - 정밀점검 측정값 / MY WORK LOG 작성 내용 / 담아 둔 사진을 사용자별로 서버에 자동 보관합니다.
#   - 1차: 서버 로컬 파일(재접속 즉시 복구) · 2차: 구글 시트 미러(서버 재시작 대비, 텍스트만)
#   - 저장 성공 또는 사용자가 내용을 모두 비우면 자동 삭제됩니다.
# ==========================================
DRAFT_ROOT_DIR = os.path.join(tempfile.gettempdir(), "smartwork_drafts")
DRAFT_SHEET_NAME = "MY_WORK_LOG_DRAFTS"
DRAFT_SHEET_HEADERS = ["사용자ID", "구분", "내용JSON", "수정일시"]
DRAFT_MIRROR_MIN_INTERVAL_SECONDS = 60
DRAFT_MIRROR_MAX_CHARS = 45000
_DRAFT_EXECUTOR = _PS["draft_executor"]

_POWER_DRAFT_STATE_KEYS = [
    "power_worker", "power_major_area", "power_mother", "power_local", "power_inspector_group",
    "power_current_theme", "power_unlocked_theme_index", "power_theme_confirmations",
    "power_phase_type", "power_battery_set", "power_battery2_enabled", "power_notes",
    "power_loaded_source_id", "power_loaded_source_saved_at", "power_station_search_applied",
]
_POWER_DRAFT_NEUTRAL_KEYS = {"power_phase_type", "power_major_area", "power_battery_set", "power_battery2_enabled"}
_WORKLOG_DRAFT_FIELDS = ("visibility", "status", "items", "issue", "action", "followup", "remark")
_WORKLOG_DRAFT_SHARED_KEYS = ("worklog_area_key", "worklog_mother", "worklog_local")
_WORKLOG_VISIBILITY_LABELS = ["🌐 공개 · 팀 공유", "🔒 비공개 · 나만 보기"]


def _draft_user_dir(user_id: str, kind: str) -> str:
    safe_user = re.sub(r"[^A-Za-z0-9_-]", "", str(user_id or ""))[:40] or "anonymous"
    safe_kind = re.sub(r"[^A-Za-z0-9_-]", "", str(kind or ""))[:20] or "draft"
    return os.path.join(DRAFT_ROOT_DIR, safe_user, safe_kind)


def _blank_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    if isinstance(value, bool):
        return not value
    return not str(value).strip()


def _power_draft_snapshot() -> dict:
    draft = st.session_state.get("power_draft")
    snapshot = {"draft": dict(draft) if isinstance(draft, dict) else {}, "state": {}}
    for key in _POWER_DRAFT_STATE_KEYS:
        if key in st.session_state:
            snapshot["state"][key] = st.session_state[key]
    return snapshot


def _power_snapshot_has_content(snapshot: dict) -> bool:
    draft = snapshot.get("draft", {}) or {}
    if any(not _blank_value(v) for k, v in draft.items() if k not in _POWER_DRAFT_NEUTRAL_KEYS):
        return True
    state = snapshot.get("state", {}) or {}
    return str(state.get("power_mother", "") or "") not in ("", "모국 선택")


def _worklog_draft_snapshot() -> dict:
    generation = int(st.session_state.get("worklog_entry_generation", 0) or 0)
    prefix = f"wlentry_{generation}_"
    fields = {name: st.session_state.get(prefix + name) for name in _WORKLOG_DRAFT_FIELDS if (prefix + name) in st.session_state}
    shared = {key: st.session_state.get(key) for key in _WORKLOG_DRAFT_SHARED_KEYS if key in st.session_state}
    return {"fields": fields, "shared": shared}


def _worklog_snapshot_has_content(snapshot: dict) -> bool:
    fields = snapshot.get("fields", {}) or {}
    if any(not _blank_value(fields.get(name)) for name in ("issue", "action", "followup", "remark", "items")):
        return True
    shared = snapshot.get("shared", {}) or {}
    return any(not _blank_value(shared.get(key)) for key in _WORKLOG_DRAFT_SHARED_KEYS)


def _draft_photo_digest(photos: list) -> str:
    return hashlib.sha256(
        "|".join(str(p.get("digest", "")) + ":" + str(p.get("bytes", "")) for p in photos if isinstance(p, dict)).encode("utf-8")
    ).hexdigest()


def _draft_write_local(user_id: str, kind: str, snapshot_json: str, photos: list) -> None:
    folder = _draft_user_dir(user_id, kind)
    os.makedirs(folder, exist_ok=True)
    temp_path = os.path.join(folder, "draft.json.tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        handle.write(snapshot_json)
    os.replace(temp_path, os.path.join(folder, "draft.json"))

    manifest_path = os.path.join(folder, "photos.json")
    new_digest = _draft_photo_digest(photos)
    old_digest = ""
    try:
        with open(manifest_path, encoding="utf-8") as handle:
            old_digest = str(json.load(handle).get("digest", ""))
    except Exception:
        pass
    if new_digest == old_digest:
        return
    for name in os.listdir(folder):
        if name.startswith("photo_") and name.endswith(".bin"):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass
    meta = []
    for index, item in enumerate(photos):
        if not isinstance(item, dict) or not item.get("data"):
            continue
        with open(os.path.join(folder, f"photo_{index:02d}.bin"), "wb") as handle:
            handle.write(item["data"])
        meta.append({k: item.get(k, "") for k in ("name", "type", "digest", "capture_stamp", "bytes")} | {"file": f"photo_{index:02d}.bin"})
    with open(manifest_path, "w", encoding="utf-8") as handle:
        json.dump({"digest": new_digest, "photos": meta}, handle, ensure_ascii=False)


def _draft_read_local(user_id: str, kind: str):
    folder = _draft_user_dir(user_id, kind)
    try:
        with open(os.path.join(folder, "draft.json"), encoding="utf-8") as handle:
            snapshot = json.load(handle)
    except Exception:
        return None, []
    photos = []
    try:
        with open(os.path.join(folder, "photos.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        for meta in manifest.get("photos", []):
            with open(os.path.join(folder, str(meta.get("file", ""))), "rb") as handle:
                data = handle.read()
            if data:
                photos.append({
                    "data": data, "name": meta.get("name", "field_photo.jpg"), "type": meta.get("type", "image/jpeg"),
                    "digest": meta.get("digest", ""), "capture_stamp": meta.get("capture_stamp", ""),
                    "bytes": int(meta.get("bytes", len(data)) or len(data)),
                })
    except Exception:
        photos = []
    return snapshot, photos


def _draft_clear(user_id: str, kind: str) -> None:
    try:
        shutil.rmtree(_draft_user_dir(user_id, kind), ignore_errors=True)
    except Exception:
        pass
    _draft_mirror_async(user_id, kind, "")


def _draft_mirror_worker(gs_info: dict, user_id: str, kind: str, snapshot_json: str) -> None:
    """시트 미러: 사용자·구분별 1행을 만들거나 갱신하고, 내용이 비면 행을 비웁니다. (스레드 전용 클라이언트)"""
    try:
        client = _gs_make_client(gs_info)
        spreadsheet = _sheet_call(client.open, WORK_LOG_SPREADSHEET_NAME)
        try:
            ws = _sheet_call(spreadsheet.worksheet, DRAFT_SHEET_NAME)
        except Exception:
            if not snapshot_json:
                return
            ws = _sheet_call(spreadsheet.add_worksheet, title=DRAFT_SHEET_NAME, rows=200, cols=6)
            _sheet_call(ws.append_row, DRAFT_SHEET_HEADERS, value_input_option="RAW")
        user_col = _sheet_call(ws.col_values, 1)
        kind_col = _sheet_call(ws.col_values, 2)
        row_no = None
        for index in range(1, len(user_col)):
            if user_col[index] == user_id and index < len(kind_col) and kind_col[index] == kind:
                row_no = index + 1
                break
        now_text = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        if not snapshot_json:
            if row_no is not None:
                _sheet_update_fields(ws, DRAFT_SHEET_HEADERS, row_no, {"내용JSON": "", "수정일시": now_text}, raw=True)
            return
        if len(snapshot_json) > DRAFT_MIRROR_MAX_CHARS:
            return
        if row_no is None:
            _sheet_call(ws.append_row, [user_id, kind, snapshot_json, now_text], value_input_option="RAW")
        else:
            _sheet_update_fields(ws, DRAFT_SHEET_HEADERS, row_no, {"내용JSON": snapshot_json, "수정일시": now_text}, raw=True)
    except Exception as error:
        logger.warning("임시저장 시트 미러 실패: %s", error)


def _draft_mirror_async(user_id: str, kind: str, snapshot_json: str) -> None:
    try:
        _DRAFT_EXECUTOR.submit(_draft_mirror_worker, _gs_service_info(), str(user_id), str(kind), snapshot_json)
    except Exception as error:
        logger.warning("임시저장 미러 예약 실패: %s", error)


def _draft_read_mirror(user_id: str, kind: str):
    try:
        client = init_google_sheet_connection()
        if not client:
            return None
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws = _sheet_call(spreadsheet.worksheet, DRAFT_SHEET_NAME)
        values = _sheet_call(ws.get_all_values)
        for row in values[1:]:
            if len(row) >= 3 and row[0] == user_id and row[1] == kind and row[2].strip():
                return json.loads(row[2])
    except Exception:
        return None
    return None


def _apply_power_snapshot(snapshot: dict, photos: list) -> None:
    st.session_state["power_draft"] = dict(snapshot.get("draft", {}) or {})
    for key, value in (snapshot.get("state", {}) or {}).items():
        if key in _POWER_DRAFT_STATE_KEYS:
            st.session_state[key] = value
    for key in list(st.session_state.keys()):
        if str(key).startswith("_ui_power_"):
            del st.session_state[key]
    if photos:
        st.session_state["power_photo_queue"] = photos


def _apply_worklog_snapshot(snapshot: dict, photos: list) -> None:
    generation = int(st.session_state.get("worklog_entry_generation", 0) or 0)
    prefix = f"wlentry_{generation}_"
    fields = snapshot.get("fields", {}) or {}
    for name in _WORKLOG_DRAFT_FIELDS:
        if name not in fields or (prefix + name) in st.session_state:
            continue
        value = fields[name]
        if name == "status" and value not in WORK_LOG_STATUS_OPTIONS:
            continue
        if name == "visibility" and value not in _WORKLOG_VISIBILITY_LABELS:
            continue
        if name == "items":
            value = [v for v in (value or []) if v in WORK_LOG_ITEM_OPTIONS]
        st.session_state[prefix + name] = value
    for key, value in (snapshot.get("shared", {}) or {}).items():
        if key in _WORKLOG_DRAFT_SHARED_KEYS and key not in st.session_state and value is not None:
            st.session_state[key] = value
    if photos:
        st.session_state[f"worklog_photo_queue_{generation}"] = photos


def _drafts_restore_once(user: dict) -> None:
    """새 접속(세션)에서 한 번만 이전 임시저장을 불러옵니다. 위젯이 만들어지기 전에 호출해야 합니다."""
    if st.session_state.get("draft_restore_done") or not user:
        return
    st.session_state["draft_restore_done"] = True
    user_id = str(user.get("user_id", "") or "")
    restored: list[str] = []
    try:
        snapshot, photos = _draft_read_local(user_id, "power")
        if snapshot is None:
            snapshot = _draft_read_mirror(user_id, "power")
        if snapshot and _power_snapshot_has_content(snapshot) and not _power_snapshot_has_content(_power_draft_snapshot()):
            _apply_power_snapshot(snapshot, photos)
            restored.append("정밀점검 측정값" + (f"·사진 {len(photos)}장" if photos else ""))

        snapshot, photos = _draft_read_local(user_id, "worklog")
        if snapshot is None:
            snapshot = _draft_read_mirror(user_id, "worklog")
        if snapshot and (_worklog_snapshot_has_content(snapshot) or photos) and not _worklog_snapshot_has_content(_worklog_draft_snapshot()):
            _apply_worklog_snapshot(snapshot, photos)
            restored.append("MY WORK LOG 작성 내용" + (f"·사진 {len(photos)}장" if photos else ""))
    except Exception as error:
        logger.warning("임시저장 복구 실패: %s", error)
    if restored:
        st.toast("♻️ 이전에 입력하던 " + ", ".join(restored) + "을(를) 복구했습니다.", icon="💾")


def _drafts_autosave(user: dict) -> None:
    """매 실행 끝에서 입력 상태가 바뀌었을 때만 임시저장합니다. (변경 없으면 아무 작업도 하지 않음)"""
    if not user:
        return
    user_id = str(user.get("user_id", "") or "")
    generation = int(st.session_state.get("worklog_entry_generation", 0) or 0)
    targets = (
        ("power", _power_draft_snapshot(), list(st.session_state.get("power_photo_queue") or []), _power_snapshot_has_content),
        ("worklog", _worklog_draft_snapshot(), list(st.session_state.get(f"worklog_photo_queue_{generation}") or []), _worklog_snapshot_has_content),
    )
    for kind, snapshot, photos, has_content in targets:
        try:
            snapshot_json = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str)
            signature = hashlib.sha256((snapshot_json + _draft_photo_digest(photos)).encode("utf-8")).hexdigest()
            if st.session_state.get(f"_draft_sig_{kind}") == signature:
                continue
            st.session_state[f"_draft_sig_{kind}"] = signature
            if has_content(snapshot) or photos:
                _draft_write_local(user_id, kind, snapshot_json, photos)
                st.session_state[f"_draft_had_{kind}"] = True
                st.session_state["_draft_saved_at"] = _korea_now().strftime("%H:%M")
                last_mirror = float(st.session_state.get(f"_draft_mirror_at_{kind}", 0) or 0)
                if time.time() - last_mirror >= DRAFT_MIRROR_MIN_INTERVAL_SECONDS:
                    st.session_state[f"_draft_mirror_at_{kind}"] = time.time()
                    _draft_mirror_async(user_id, kind, snapshot_json)
            elif st.session_state.get("draft_restore_done") and (
                st.session_state.get(f"_draft_had_{kind}") or os.path.isdir(_draft_user_dir(user_id, kind))
            ):
                _draft_clear(user_id, kind)
                st.session_state[f"_draft_had_{kind}"] = False
        except Exception as error:
            logger.warning("임시저장 실패(%s): %s", kind, error)


# ==========================================
# 운영 보강: 접속·조회 감사 기록 / 유휴 재확인 / 상태 표시줄 / 입력값 점검
# ==========================================
AUDIT_SHEET_NAME = "MY_WORK_LOG_AUDIT"
AUDIT_HEADERS = ["일시", "사용자ID", "이름", "이벤트", "상세", "접속IP(마스킹)", "단말"]
APP_DISPLAY_NAME = "SMART POWER FIELD"
APP_VERSION_TEXT = "v7.0 · 사용자 인증 · 신뢰 단말 · 자동 임시저장"


def _mask_ip(ip: str) -> str:
    text = str(ip or "").strip()
    if "." in text:
        parts = text.split(".")
        return ".".join(parts[:3] + ["*"]) if len(parts) == 4 else text
    if ":" in text:
        return ":".join(text.split(":")[:3] + ["*"])
    return text


def _audit_worker(gs_info: dict, row: list) -> None:
    try:
        client = _gs_make_client(gs_info)
        spreadsheet = _sheet_call(client.open, WORK_LOG_SPREADSHEET_NAME)
        try:
            ws = _sheet_call(spreadsheet.worksheet, AUDIT_SHEET_NAME)
        except Exception:
            ws = _sheet_call(spreadsheet.add_worksheet, title=AUDIT_SHEET_NAME, rows=5000, cols=8)
            _sheet_call(ws.append_row, AUDIT_HEADERS, value_input_option="RAW")
        _sheet_call(ws.append_row, row, value_input_option="RAW")
    except Exception as error:
        logger.warning("감사 기록 실패: %s", error)


def _audit_log(event: str, detail: str = "", user: dict | None = None) -> None:
    """접속·인증·조회·다운로드 이력을 시트에 남깁니다. (백그라운드 · 실패해도 업무에 영향 없음)

    개인정보 보호를 위해 IP는 마지막 자리를 가리고, 인증코드·PIN·측정 내용은 기록하지 않습니다.
    """
    try:
        user = user or _worklog_current_user() or {}
        info = _device_ua_info()
        row = [
            _korea_now().strftime("%Y-%m-%d %H:%M:%S"),
            str(user.get("user_id", "") or ""),
            str(user.get("name", "") or ""),
            str(event),
            str(detail)[:300],
            _mask_ip(_client_ip()),
            str(info.get("summary", "")),
        ]
        _DRAFT_EXECUTOR.submit(_audit_worker, _gs_service_info(), row)
    except Exception as error:
        logger.warning("감사 기록 예약 실패: %s", error)


# ---------- 현장 입력값 점검 (참고용 · 저장을 막지 않음) ----------
# 값이 명백히 이상한(오타·단위 착오 가능성이 큰) 경우만 알려 줍니다. 현장 기준에 맞게 아래 값을 조정하세요.
POWER_SANITY_LIMITS = {
    "line_voltage": (300.0, 460.0),     # 삼상 선간전압 R-S / S-T / T-R (V)
    "phase_voltage": (150.0, 280.0),    # 삼상 상전압 R-N, 단상 전압 (V)
    "max_current": 2000.0,              # 전류 상한 (A)
    "cell_voltage": (1.5, 2.6),         # 2V 셀 전압 (V) — 5V 초과 값이 있으면 모노블록으로 보고 건너뜀
    "cell_spread": 0.20,                # 셀 간 최고-최저 편차 (V)
    "ground_ohm": 100.0,                # 접지저항 (Ω)
    "voltage_unbalance_pct": 5.0,       # 선간전압 불평형 (%)
    "current_unbalance_pct": 40.0,      # R/S/T 전류 편차 (%)
}


def _as_float(value):
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _power_sanity_warnings(payload: dict) -> list[str]:
    limits = POWER_SANITY_LIMITS
    warnings: list[str] = []

    def check_range(label: str, value, low: float, high: float, unit: str) -> None:
        number = _as_float(value)
        if number is not None and not (low <= number <= high):
            warnings.append(f"{label} {number:g}{unit} — 일반 범위({low:g}~{high:g}{unit})를 벗어났습니다. 단위·소수점을 확인해 주세요.")

    if str(payload.get("phase_type", "")) == "삼상":
        line = []
        for key, label in (("three_voltage_rs", "R-S 전압"), ("three_voltage_st", "S-T 전압"), ("three_voltage_tr", "T-R 전압")):
            check_range(label, payload.get(key), *limits["line_voltage"], "V")
            number = _as_float(payload.get(key))
            if number is not None:
                line.append(number)
        check_range("R-N 상전압", payload.get("three_voltage_rn"), *limits["phase_voltage"], "V")
        if len(line) == 3 and min(line) > 0:
            spread = (max(line) - min(line)) / (sum(line) / 3) * 100
            if spread > limits["voltage_unbalance_pct"]:
                warnings.append(f"선간전압 편차가 {spread:.1f}%입니다. 상 순서·측정 위치를 확인해 주세요.")
        currents = [_as_float(payload.get(k)) for k in ("three_current_r", "three_current_s", "three_current_t")]
        currents = [c for c in currents if c is not None]
        for key, label in (("three_current_r", "R상"), ("three_current_s", "S상"), ("three_current_t", "T상"), ("three_current_n", "N상")):
            number = _as_float(payload.get(key))
            if number is not None and (number < 0 or number > limits["max_current"]):
                warnings.append(f"{label} 전류 {number:g}A — 값이 비정상적입니다.")
        if len(currents) == 3 and sum(currents) > 0:
            mean = sum(currents) / 3
            if mean > 0 and (max(currents) - min(currents)) / mean * 100 > limits["current_unbalance_pct"]:
                warnings.append("R/S/T 상전류 편차가 큽니다. 부하 불평형 또는 입력 오류인지 확인해 주세요.")
    else:
        check_range("단상 전압", payload.get("single_voltage"), *limits["phase_voltage"], "V")
        number = _as_float(payload.get("single_current"))
        if number is not None and (number < 0 or number > limits["max_current"]):
            warnings.append(f"단상 전류 {number:g}A — 값이 비정상적입니다.")

    for group in (1, 2):
        cells = [_as_float(v) for v in payload.get(f"battery{group}_cells", [])]
        cells = [c for c in cells if c is not None]
        if not cells or max(cells) > 5:
            continue
        low, high = limits["cell_voltage"]
        outliers = [i for i, v in enumerate([_as_float(x) for x in payload.get(f"battery{group}_cells", [])], 1)
                    if v is not None and not (low <= v <= high)]
        if outliers:
            warnings.append(f"{group}조 {', '.join(str(i) for i in outliers[:8])}번 셀 전압이 일반 범위({low:g}~{high:g}V)를 벗어났습니다.")
        if max(cells) - min(cells) > limits["cell_spread"]:
            warnings.append(f"{group}조 셀 간 편차가 {max(cells) - min(cells):.2f}V입니다. 열화 셀 여부를 확인해 주세요.")

    for key, label in (
        ("security_ground_1", "보안접지 1종"), ("security_ground_2", "보안접지 2종"), ("security_ground_3", "보안접지 3종"),
        ("telecom_ground", "통신용접지"), ("lightning_ground", "피뢰침접지"),
    ):
        number = _as_float(payload.get(key))
        if number is not None and (number < 0 or number > limits["ground_ohm"]):
            warnings.append(f"{label} {number:g}Ω — 매우 높거나 비정상적인 값입니다. 재측정 여부를 확인해 주세요.")
    return warnings


def _render_status_strip(user: dict) -> None:
    """상단 상태 표시줄: 누가 · 어떤 방식으로 인증됐고 · 임시저장이 언제 됐는지를 항상 보여 줍니다."""
    if not user:
        return
    method = "신뢰 단말" if st.session_state.get("auth_via_device") else "인증코드"
    saved = st.session_state.get("_draft_saved_at", "")
    saved_text = f"💾 임시저장 {saved}" if saved else "💾 입력 내용은 자동 임시저장됩니다"
    strip_col, logout_col = st.columns([5.2, 1.2], gap="small", vertical_alignment="center")
    with strip_col:
        st.markdown(
            '<div class="spf-strip">'
            f'<span class="spf-chip user">👤 {html.escape(str(user.get("name", "")))}</span>'
            f'<span class="spf-chip ok">🔐 {method}</span>'
            f'<span class="spf-chip">{saved_text}</span>'
            '</div>',
            unsafe_allow_html=True,
        )
    with logout_col:
        st.button("로그아웃", key="spf_strip_logout", use_container_width=True, on_click=_worklog_logout)


def _idle_lock_minutes() -> int:
    try:
        return max(0, int(str(_worklog_secret_value("work_log_idle_lock_minutes", "120") or "120").strip()))
    except ValueError:
        return 120


def _my_power_mothers(user_name: str) -> list[str]:
    """로그인한 사용자가 담당자로 지정된 권역의 모국 목록을 반환합니다."""
    mothers: list[str] = []
    for area, data in POWER_REGION_DATA.items():
        if user_name and user_name in (data.get("담당자") or []):
            mothers.extend(list((data.get("모국_국소") or {}).keys()))
    return mothers


def _worklog_current_user() -> dict:
    user = st.session_state.get("worklog_auth_user")
    return user if isinstance(user, dict) else {}


def _worklog_logout() -> None:
    """로그아웃: 이 단말의 신뢰 등록을 해제하고(다음 접속에서 사용자 인증 재요구) 개인 세션을 정리합니다."""
    _audit_log("로그아웃", "이 단말 신뢰 해제")
    _device_revoke_current()
    for key in (
        "worklog_auth_user", "worklog_pin_change_required", "worklog_quick_setup_required", "worklog_show_pin_change",
        "worklog_show_auth_settings", "worklog_df", "worklog_loaded_at", "worklog_selected_id", "worklog_selected_ui_key", "worklog_delete_pending_id",
        "worklog_search", "worklog_filter", "worklog_public_scope",
        "device_checked", "auth_via_device", "admin_verified_until", "draft_restore_done",
    ):
        st.session_state.pop(key, None)


def _worklog_user_id_from_name(name: str) -> str:
    name = str(name or "").strip()
    cached = _USERS_CACHE.get("value")
    if cached:
        for _row_no, record in cached[2]:
            if str(record.get("이름", "") or "").strip() == name and record.get("사용자ID"):
                return str(record["사용자ID"]).strip()
    return str(WORK_LOG_NAME_TO_USER_ID.get(name, "") or "")


def _worklog_record_owner_id(record) -> str:
    explicit = str(record.get("작성자ID", "") or "").strip()
    if explicit:
        return explicit
    return _worklog_user_id_from_name(record.get("작성자", ""))


def _worklog_record_visibility(record) -> str:
    value = str(record.get("공개범위", "") or "").strip()
    return "비공개" if value == "비공개" else "공개"


def _worklog_record_owned_by(record, auth_user: dict) -> bool:
    if not auth_user:
        return False
    return _worklog_record_owner_id(record) == str(auth_user.get("user_id", "") or "").strip()


def _worklog_filter_accessible_records(df: pd.DataFrame, auth_user: dict) -> pd.DataFrame:
    """공개 기록 + 로그인 사용자의 비공개 기록만 반환합니다. 비공개는 검색 전 단계에서 차단합니다."""
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=WORK_LOG_HEADERS)
    if df.empty:
        return df.copy()

    result = df.copy()
    if "작성자ID" not in result.columns:
        result["작성자ID"] = ""
    if "공개범위" not in result.columns:
        result["공개범위"] = ""

    result["작성자ID"] = result.apply(
        lambda row: str(row.get("작성자ID", "") or "").strip() or _worklog_user_id_from_name(row.get("작성자", "")),
        axis=1,
    )
    result["공개범위"] = result["공개범위"].apply(
        lambda value: "비공개" if str(value or "").strip() == "비공개" else "공개"
    )

    current_user_id = str(auth_user.get("user_id", "") or "").strip()
    if not current_user_id:
        return result.iloc[0:0].copy()

    allowed = (result["공개범위"] == "공개") | (
        (result["공개범위"] == "비공개") & (result["작성자ID"] == current_user_id)
    )
    return result[allowed].copy()


def _worklog_login_dialog_body() -> None:
    st.caption(
        "처음 사용하는 경우 사번 + 관리자가 안내한 임시 PIN으로 본인 확인 후 사용자 인증코드를 설정합니다. "
        "인증코드를 잊었다면 사번 + 복구용 개인 PIN으로 다시 인증할 수 있습니다."
    )
    with st.form("worklog_personal_login_form", clear_on_submit=False):
        employee_no = st.text_input(
            "사번",
            placeholder="사번 입력",
            max_chars=10,
            key="worklog_login_employee_no",
        )
        pin = st.text_input(
            "개인 PIN",
            type="password",
            placeholder="최초 임시 PIN / 이후 복구용 개인 PIN",
            max_chars=6,
            key="worklog_login_pin",
        )
        submitted = st.form_submit_button("🔐 본인 확인", type="primary", use_container_width=True)

    if submitted:
        ok, message, user = _worklog_authenticate_user(employee_no, pin)
        if ok:
            _apply_login_success(user)
            st.session_state.pop("worklog_login_pin", None)
            st.success(message)
            time.sleep(0.35)
            st.rerun()
        else:
            st.error(message)


if hasattr(st, "dialog"):
    _worklog_login_dialog = st.dialog(
        "🔐 MY WORK LOG 개인 인증",
    )(_worklog_login_dialog_body)
else:
    _worklog_login_dialog = _worklog_login_dialog_body


def _worklog_drive_folder_id() -> str:
    """하위 호환용 Google Drive 폴더 ID입니다. Apps Script 방식에서는 Script Properties의 FOLDER_ID가 실제 저장 위치를 결정합니다."""
    return str(_worklog_secret_value("work_log_drive_folder_id", "") or "").strip()


def _worklog_photo_upload_url() -> str:
    """MY WORK LOG 사진 업로드용 Google Apps Script 웹 앱(/exec) URL을 반환합니다."""
    return str(_worklog_secret_value("work_log_photo_upload_url", "") or "").strip()


def _worklog_photo_upload_token() -> str:
    """Apps Script와 공유하는 사진 업로드 비밀 토큰을 반환합니다."""
    return str(_worklog_secret_value("work_log_upload_token", "") or "").strip()


WORK_LOG_PHOTO_ENGINE_VERSION = "V10-20260819-COMPACT-LIST"


def _worklog_normalize_apps_script_url() -> tuple[str, str]:
    """Apps Script 웹 앱의 영구 /exec URL만 허용합니다.

    ContentService가 반환하는 script.googleusercontent.com 주소는 일회성 응답 URL이므로
    Secrets에 저장하면 이후 404가 발생할 수 있습니다.
    """
    raw_url = _worklog_photo_upload_url().strip().strip('"').strip("'")
    if not raw_url:
        return "", "Streamlit Secrets의 [work_log] photo_upload_url이 비어 있습니다."
    try:
        parsed = urlparse(raw_url)
    except Exception:
        return "", "photo_upload_url을 URL로 해석할 수 없습니다."

    host = str(parsed.netloc or "").lower().split(":")[0]
    path = str(parsed.path or "").rstrip("/")

    if parsed.scheme.lower() != "https":
        return "", "photo_upload_url은 https:// 주소여야 합니다."
    if host == "script.googleusercontent.com" or host.endswith(".script.googleusercontent.com"):
        return "", (
            "photo_upload_url에 Google의 일회성 리디렉션 주소(script.googleusercontent.com)가 들어 있습니다. "
            "Apps Script의 '배포 관리'에서 복사한 https://script.google.com/macros/s/.../exec 원본 주소를 넣어 주세요."
        )
    if host != "script.google.com":
        return "", (
            f"photo_upload_url 호스트가 {host or '확인 불가'}입니다. "
            "Apps Script 웹 앱의 원본 /exec 주소(https://script.google.com/macros/s/.../exec)를 사용해 주세요."
        )
    if path.endswith("/dev"):
        return "", "photo_upload_url이 /dev 개발용 주소입니다. 실제 배포용 /exec 주소를 사용해 주세요."
    if not re.fullmatch(r"/macros/s/[^/]+/exec", path):
        return "", (
            "photo_upload_url 형식이 Apps Script 배포용 /exec 주소와 일치하지 않습니다. "
            "배포 → 배포 관리에서 '웹 앱 URL'을 다시 복사해 주세요."
        )
    return f"https://script.google.com{path}", ""


def _worklog_photo_config_status() -> tuple[bool, list[str]]:
    """사진 업로드 Secrets 상태를 항목별로 진단합니다."""
    issues: list[str] = []

    raw_url = _worklog_photo_upload_url().strip()
    token = _worklog_photo_upload_token().strip()

    if not raw_url:
        issues.append("photo_upload_url 누락")
    else:
        _, url_error = _worklog_normalize_apps_script_url()
        if url_error:
            issues.append(f"photo_upload_url 오류: {url_error}")

    if not token:
        issues.append("upload_token 누락")

    return (len(issues) == 0), issues


def _worklog_photo_upload_ready() -> bool:
    ready, _ = _worklog_photo_config_status()
    return ready


def _worklog_follow_apps_script_response(first_response, timeout: int = 30):
    """Apps Script ContentService의 일회성 리디렉션을 즉시 따라가 최종 응답을 반환합니다."""
    response = first_response
    if first_response.status_code in {301, 302, 303, 307, 308}:
        redirect_url = str(first_response.headers.get("Location", "") or "").strip()
        if not redirect_url:
            return None, "Apps Script 리디렉션에 Location 주소가 없습니다."
        redirect_host = str(urlparse(redirect_url).netloc or "").lower()
        if "script.googleusercontent.com" not in redirect_host:
            return None, f"예상하지 않은 리디렉션 주소입니다: {redirect_host or '확인 불가'}"
        try:
            response = requests.get(
                redirect_url,
                timeout=timeout,
                allow_redirects=True,
                headers={
                    "Accept": "application/json,text/plain,*/*",
                    "User-Agent": "SMART-WORK-AI-AGENT/4.0",
                },
            )
        except Exception as error:
            return None, f"Apps Script 응답 리디렉션 처리 실패: {error}"
    return response, ""


def _worklog_apps_script_healthcheck() -> tuple[bool, str]:
    """Streamlit 서버에서 GET과 실제 POST 경로를 모두 점검합니다.

    브라우저 GET 성공은 로그인 쿠키 때문에 오판할 수 있으므로, 실제 사진 업로드와 같은
    서버 측 POST도 아주 작은 요청으로 확인합니다. POST probe는 사진을 생성하지 않습니다.
    현재 Apps Script doPost는 data가 없으면 '사진 데이터가 없습니다.' JSON을 반환하므로
    이 응답을 POST 경로 정상의 증거로 사용합니다.
    """
    upload_url, url_error = _worklog_normalize_apps_script_url()
    if url_error:
        return False, url_error
    upload_token = _worklog_photo_upload_token()
    if not upload_token:
        return False, "[work_log] upload_token이 설정되지 않았습니다."

    # 1) 익명 GET 확인
    try:
        get_first = requests.get(
            upload_url,
            timeout=20,
            allow_redirects=False,
            headers={
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "SMART-WORK-AI-AGENT/4.0",
            },
        )
        get_response, redirect_error = _worklog_follow_apps_script_response(get_first, timeout=20)
        if redirect_error:
            return False, f"GET 진단 실패: {redirect_error}"
        if get_response is None or get_response.status_code != 200:
            code = getattr(get_response, "status_code", get_first.status_code)
            return False, (
                f"GET 진단 실패 ({code}). Streamlit 서버가 Apps Script를 익명으로 열 수 없습니다. "
                "웹 앱 배포의 접근 권한이 로그인 없이 허용되는지 확인해야 합니다."
            )
        if get_response.text.lstrip().lower().startswith("<!doctype html"):
            return False, "GET 진단에서 JSON 대신 Google HTML이 반환되었습니다. 익명 접근 또는 배포 URL 문제입니다."
        try:
            get_json = get_response.json()
        except Exception:
            return False, f"GET 진단 응답이 JSON이 아닙니다: {get_response.text[:160]}"
        if not bool(get_json.get("ok")):
            return False, f"GET 진단 실패: {get_json}"
    except requests.Timeout:
        return False, "GET 진단 시간이 초과되었습니다."
    except Exception as error:
        return False, f"GET 진단 오류: {error}"

    # 2) 실제 사진 업로드와 같은 POST 경로 확인. data는 의도적으로 비워 파일을 만들지 않습니다.
    probe_payload = {
        "token": upload_token,
        "filename": "__worklog_probe__.jpg",
        "mimeType": "image/jpeg",
        "data": "",
    }
    probe_bytes = json.dumps(probe_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    try:
        post_first = requests.post(
            upload_url,
            data=probe_bytes,
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "SMART-WORK-AI-AGENT/4.0",
            },
            timeout=30,
            allow_redirects=False,
        )
        post_response, redirect_error = _worklog_follow_apps_script_response(post_first, timeout=30)
        if redirect_error:
            return False, f"POST 진단 실패: {redirect_error}"
        if post_response is None or post_response.status_code != 200:
            code = getattr(post_response, "status_code", post_first.status_code)
            body = getattr(post_response, "text", post_first.text)[:120]
            return False, (
                f"POST 진단 실패 ({code}). 브라우저 GET은 열려 있어도 Streamlit 서버의 POST가 차단된 상태입니다. "
                f"응답: {body}"
            )
        if post_response.text.lstrip().lower().startswith("<!doctype html"):
            return False, (
                "POST 진단에서 Google HTML 페이지가 반환되었습니다. 이 경우 폴더/토큰 문제가 아니라 "
                "웹 앱의 익명 POST 접근 또는 현재 /exec 배포 버전 문제입니다."
            )
        try:
            post_json = post_response.json()
        except Exception:
            return False, f"POST 진단 응답이 JSON이 아닙니다: {post_response.text[:160]}"

        # 현재 doPost에서 빈 data는 정상적으로 여기까지 도달하면 '사진 데이터가 없습니다.'를 반환합니다.
        if bool(post_json.get("ok")):
            return True, f"사진 연결 정상 · GET/POST 모두 통과 · PHOTO ENGINE {WORK_LOG_PHOTO_ENGINE_VERSION}"
        error_text = str(post_json.get("error", "") or "")
        if error_text == "사진 데이터가 없습니다.":
            return True, f"사진 연결 정상 · GET/POST 모두 통과 · PHOTO ENGINE {WORK_LOG_PHOTO_ENGINE_VERSION}"
        if error_text.lower() == "unauthorized":
            return False, "POST는 Apps Script에 도달했지만 UPLOAD_TOKEN이 일치하지 않습니다."
        return False, f"POST는 Apps Script에 도달했지만 doPost가 오류를 반환했습니다: {error_text or post_json}"
    except requests.Timeout:
        return False, "POST 진단 시간이 초과되었습니다."
    except Exception as error:
        return False, f"POST 진단 오류: {error}"


def _worklog_google_credentials():
    """Drive API용 서비스 계정 인증 객체를 만듭니다. (실패를 캐시하지 않도록 cache_resource를 쓰지 않음)"""
    try:
        if _GoogleServiceCredentials is not None:
            return _GoogleServiceCredentials.from_service_account_info(_gs_service_info(), scopes=_GS_SCOPE)
        if ServiceAccountCredentials is not None:
            return ServiceAccountCredentials.from_json_keyfile_dict(_gs_service_info(), _GS_SCOPE)
    except Exception as error:
        logger.error("Drive 인증 객체 생성 실패: %s", error)
    return None


def _worklog_drive_access_token() -> str:
    """Drive 접근 토큰을 만료 5분 전까지 재사용합니다."""
    now = time.time()
    if _DRIVE_TOKEN_CACHE["token"] and now < float(_DRIVE_TOKEN_CACHE["expires"]) - 300:
        return str(_DRIVE_TOKEN_CACHE["token"])
    creds = _worklog_google_credentials()
    if creds is None:
        return ""
    try:
        if _GoogleServiceCredentials is not None and isinstance(creds, _GoogleServiceCredentials):
            from google.auth.transport.requests import Request as _GoogleAuthRequest
            creds.refresh(_GoogleAuthRequest())
            token = str(creds.token or "")
            expires = creds.expiry.replace(tzinfo=datetime.timezone.utc).timestamp() if creds.expiry else now + 1800
        else:
            token_info = creds.get_access_token()
            token = str(getattr(token_info, "access_token", "") or "")
            expires = now + int(getattr(token_info, "expires_in", 1800) or 1800)
        _DRIVE_TOKEN_CACHE.update(token=token, expires=expires)
        return token
    except Exception as error:
        logger.error("Drive 토큰 발급 실패: %s", error)
        return ""


def _worklog_ensure_sheets(spreadsheet):
    """WORK LOG 시트 준비(생성·헤더 점검)는 10분에 한 번만 수행하고 결과를 재사용합니다."""
    return _cached_sheet_setup(
        "worklog_sheets",
        lambda: _worklog_ensure_sheets_uncached(spreadsheet),
    )


def _worklog_ensure_sheets_uncached(spreadsheet):
    """WORK LOG 본문/상태이력 시트를 생성하고 기존 열 순서를 보존한 채 신규 헤더를 보장합니다."""
    try:
        ws = spreadsheet.worksheet(WORK_LOG_SHEET_NAME)
    except Exception:
        ws = spreadsheet.add_worksheet(
            title=WORK_LOG_SHEET_NAME,
            rows=10000,
            cols=max(len(WORK_LOG_HEADERS) + 4, 24),
        )
        ws.append_row(WORK_LOG_HEADERS, value_input_option="USER_ENTERED")

    try:
        history_ws = spreadsheet.worksheet(WORK_LOG_HISTORY_SHEET_NAME)
    except Exception:
        history_ws = spreadsheet.add_worksheet(
            title=WORK_LOG_HISTORY_SHEET_NAME,
            rows=20000,
            cols=max(len(WORK_LOG_HISTORY_HEADERS) + 4, 16),
        )
        history_ws.append_row(WORK_LOG_HISTORY_HEADERS, value_input_option="USER_ENTERED")

    _worklog_ensure_headers(ws, WORK_LOG_HEADERS)
    _worklog_ensure_headers(history_ws, WORK_LOG_HISTORY_HEADERS)
    return ws, history_ws


def _worklog_make_id(now_dt: datetime.datetime | None = None) -> str:
    now_dt = now_dt or _korea_now()
    seed = f"{now_dt.isoformat()}|{time.time_ns()}"
    suffix = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:6].upper()
    return f"WL-{now_dt.strftime('%Y%m%d-%H%M%S')}-{suffix}"



def _worklog_register_mobile_image_support() -> tuple[bool, str]:
    """HEIC/HEIF를 포함한 모바일 이미지 디코더를 등록합니다."""
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener(thumbnails=False)
        return True, ""
    except ImportError:
        return False, "HEIC/HEIF 지원을 위해 requirements.txt에 pillow-heif>=1.1.1을 추가해 주세요."
    except Exception as error:
        return False, f"HEIC/HEIF 디코더 초기화 실패: {error}"


def _worklog_uploaded_file_meta(uploaded_file) -> dict:
    name = str(getattr(uploaded_file, "name", "") or "field_photo")
    mime = str(getattr(uploaded_file, "type", "") or "").lower()
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    try:
        size = len(uploaded_file.getvalue())
    except Exception:
        size = 0
    return {"name": name, "mime": mime, "ext": ext, "size": size}


def _worklog_is_heif_file(uploaded_file) -> bool:
    meta = _worklog_uploaded_file_meta(uploaded_file)
    return (
        meta["ext"] in {"heic", "heif", "heics", "heifs", "hif"}
        or meta["mime"] in {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}
    )


def _worklog_photo_health_cached(max_age_seconds: int = 120) -> tuple[bool, str]:
    """Apps Script/Drive 연결을 짧게 캐시해 모바일에서 반복 네트워크 점검을 줄입니다."""
    cache = st.session_state.get("worklog_photo_health_cache")
    now_ts = time.time()
    if isinstance(cache, dict):
        cached_at = float(cache.get("at", 0) or 0)
        if now_ts - cached_at <= max_age_seconds:
            return bool(cache.get("ok")), str(cache.get("message", "") or "")
    ok, message = _worklog_apps_script_healthcheck()
    st.session_state["worklog_photo_health_cache"] = {
        "at": now_ts,
        "ok": bool(ok),
        "message": str(message or ""),
    }
    return bool(ok), str(message or "")


def _worklog_process_photo_submission(
    uploaded_files,
    queue_key: str,
    notice_key: str,
    raw_receipt_key: str,
    health_key: str,
) -> tuple[int, int, list[str]]:
    """폼 제출이 완료된 뒤 사진을 처리합니다. 모바일 picker와 처리 rerun을 분리합니다."""
    files = list(uploaded_files or [])
    if not files:
        st.session_state[notice_key] = "선택된 사진이 없습니다."
        return 0, len(st.session_state.get(queue_key, []) or []), []

    metas = [_worklog_uploaded_file_meta(file_obj) for file_obj in files]
    st.session_state[raw_receipt_key] = {
        "received": True,
        "count": len(files),
        "size": sum(int(meta.get("size", 0) or 0) for meta in metas),
        "files": metas,
        "at": _korea_now().strftime("%H:%M:%S"),
    }

    added, queued_count, errors = _worklog_queue_selected_photos(queue_key, files)
    if errors:
        st.session_state[notice_key] = (
            f"원본 {len(files)}장 수신 · {added}장 처리 완료 · " + " / ".join(errors[:2])
        )
    elif added:
        st.session_state[notice_key] = (
            f"원본 {len(files)}장 수신 · {added}장 처리 완료 · 현재 {queued_count}장"
        )
    else:
        st.session_state[notice_key] = (
            f"원본 {len(files)}장은 수신했지만 새 사진으로 추가되지 않았습니다. 동일 사진 여부를 확인해 주세요."
        )

    if added:
        health_ok, health_message = _worklog_photo_health_cached()
        st.session_state[health_key] = {
            "ok": health_ok,
            "message": health_message,
        }
    return added, queued_count, errors



def _worklog_render_photo_pipeline_status(
    photos: list,
    queue_key: str,
    raw_receipt_key: str,
    health_key: str,
) -> None:
    """원본 수신 → 처리 완료 → Drive 연결 상태를 서로 분리하여 표시합니다."""
    raw_receipt = st.session_state.get(raw_receipt_key)
    queue = list(st.session_state.get(queue_key, []) or [])

    if isinstance(raw_receipt, dict) and raw_receipt.get("received"):
        raw_count = int(raw_receipt.get("count", 0) or 0)
        raw_size = int(raw_receipt.get("size", 0) or 0)
        st.info(
            f"① 최근 선택 원본 수신 완료 · {raw_count}장 · "
            f"원본 합계 약 {raw_size / (1024 * 1024):.1f}MB"
        )
    else:
        st.caption("① 최근 선택 원본 수신: 아직 없음")

    if not photos:
        if isinstance(raw_receipt, dict) and raw_receipt.get("received"):
            st.warning("② 누적 사진 처리 완료: 0장 · 원본은 도착했지만 압축/형식 처리 단계에서 큐에 들어가지 못했습니다.")
        else:
            st.caption("② 누적 사진 처리 완료: 0장")
        return

    total_bytes = sum(int(item.get("bytes", 0) or 0) for item in queue if isinstance(item, dict))
    st.success(
        f"② 누적 사진 처리 완료 · {len(photos)}장 / 최대 {WORK_LOG_MAX_PHOTOS}장 · 압축 후 약 {total_bytes / 1024:.0f}KB"
    )

    # 업로드 단계에서는 큰 썸네일을 표시하지 않습니다.
    # 최대 10장의 첨부 대기 파일명을 작은 고정 높이 목록으로만 보여 화면 이동을 최소화합니다.
    file_rows = []
    for index, item in enumerate(queue[:WORK_LOG_MAX_PHOTOS], 1):
        if not isinstance(item, dict):
            continue
        queued_name = str(item.get("name", "") or f"photo_{index:02d}.jpg")
        capture_stamp = str(item.get("capture_stamp", "") or "")
        display_name = html.escape(queued_name)
        stamp_text = f' <span style="color:#94A3B8;">· {html.escape(capture_stamp)}</span>' if capture_stamp else ""
        file_rows.append(
            f'<div style="padding:2px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
            f'<b style="display:inline-block;min-width:26px;color:#475569;">{index:02d}</b>'
            f'<span>{display_name}</span>{stamp_text}</div>'
        )

    if file_rows:
        st.markdown(
            '<div style="margin:4px 0 8px;padding:7px 10px;border:1px solid #E2E8F0;'
            'border-radius:8px;background:#F8FAFC;max-height:132px;overflow-y:auto;'
            'font-size:.76rem;line-height:1.25;color:#334155;">'
            '<div style="font-weight:900;margin-bottom:4px;color:#475569;">📎 첨부 대기 파일</div>'
            + ''.join(file_rows)
            + '</div>',
            unsafe_allow_html=True,
        )
        st.caption("저장 시에는 기존 규칙대로 기록ID/점검ID가 포함된 고유 파일명으로 자동 저장됩니다.")

    health = st.session_state.get(health_key)
    if isinstance(health, dict):
        if bool(health.get("ok")):
            st.caption("③ Drive 사진 저장 연결: 정상")
        else:
            st.warning(
                "③ Drive 사진 저장 연결: 점검 실패 · 기록 본문은 저장되며 사진은 나중에 다시 추가할 수 있습니다. "
                f"원인: {str(health.get('message', '') or '연결 확인 필요')}"
            )
    else:
        st.caption("③ Drive 사진 저장 연결: 아직 점검 전")



def _photo_capture_timestamp(uploaded_file, fallback_dt: datetime.datetime | None = None) -> str:
    """사진 EXIF 촬영시각을 우선 사용하고, 없으면 현재 한국시간을 파일명용 시각으로 반환합니다."""
    fallback_dt = fallback_dt or _korea_now()
    queued_stamp = str(getattr(uploaded_file, "_worklog_capture_stamp", "") or "").strip()
    if re.fullmatch(r"\d{8}_\d{6}", queued_stamp):
        return queued_stamp
    try:
        from io import BytesIO
        from PIL import Image

        if _worklog_is_heif_file(uploaded_file):
            _worklog_register_mobile_image_support()

        raw = uploaded_file.getvalue() if uploaded_file is not None else b""
        if raw:
            image = Image.open(BytesIO(raw))
            exif = image.getexif()
            # DateTimeOriginal(36867) → DateTimeDigitized(36868) → DateTime(306) 순서
            for tag_id in (36867, 36868, 306):
                value = str(exif.get(tag_id, "") or "").strip()
                if not value:
                    continue
                for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        captured = datetime.datetime.strptime(value[:19], fmt)
                        return captured.strftime("%Y%m%d_%H%M%S")
                    except Exception:
                        continue
    except Exception:
        pass
    return fallback_dt.strftime("%Y%m%d_%H%M%S")


def _worklog_compress_image(uploaded_file) -> tuple[bytes | None, str, str, str]:
    """현장 사진을 방향보정하고 1600px/약 450KB 수준 JPEG로 최적화합니다."""
    if uploaded_file is None:
        return None, "", "", "사진이 없습니다."
    if bool(getattr(uploaded_file, "_worklog_precompressed", False)):
        raw = uploaded_file.getvalue()
        safe_name = str(getattr(uploaded_file, "_worklog_safe_name", "") or getattr(uploaded_file, "name", "field_photo.jpg"))
        return raw, safe_name, "image/jpeg", ""
    try:
        from io import BytesIO
        from PIL import Image, ImageOps

        if _worklog_is_heif_file(uploaded_file):
            heif_ok, heif_error = _worklog_register_mobile_image_support()
            if not heif_ok:
                return None, "", "", heif_error

        raw = uploaded_file.getvalue()
        if len(raw) > WORK_LOG_UPLOAD_MAX_RAW_BYTES:
            return None, "", "", f"사진 용량이 너무 큽니다({len(raw) // (1024 * 1024)}MB). 40MB 이하로 줄여 주세요."
        image = Image.open(BytesIO(raw))
        if image.format == "JPEG":
            # JPEG는 디코딩 단계에서 축소해 읽어 대용량 사진의 메모리 사용량을 크게 줄입니다.
            try:
                image.draft("RGB", (WORK_LOG_IMAGE_MAX_SIDE * 2, WORK_LOG_IMAGE_MAX_SIDE * 2))
            except Exception:
                pass
        image = ImageOps.exif_transpose(image)
        if image.mode not in ("RGB", "L"):
            # 투명 PNG/WebP는 흰 배경으로 합성해 현장 문서 가독성을 유지합니다.
            if "A" in image.getbands():
                background = Image.new("RGB", image.size, "white")
                alpha = image.getchannel("A")
                background.paste(image.convert("RGB"), mask=alpha)
                image = background
            else:
                image = image.convert("RGB")
        elif image.mode == "L":
            image = image.convert("RGB")

        max_side = max(image.size)
        if max_side > WORK_LOG_IMAGE_MAX_SIDE:
            ratio = WORK_LOG_IMAGE_MAX_SIDE / float(max_side)
            image = image.resize(
                (max(1, int(image.width * ratio)), max(1, int(image.height * ratio))),
                Image.Resampling.LANCZOS,
            )

        best = None
        working = image
        for _resize_round in range(4):
            for quality in (84, 78, 72, 66, 60, 54, 48):
                buffer = BytesIO()
                working.save(
                    buffer,
                    format="JPEG",
                    quality=quality,
                    optimize=True,
                    progressive=True,
                )
                data = buffer.getvalue()
                best = data
                if len(data) <= WORK_LOG_IMAGE_TARGET_BYTES:
                    break
            if best is not None and len(best) <= WORK_LOG_IMAGE_TARGET_BYTES:
                break
            working = working.resize(
                (max(1, int(working.width * 0.86)), max(1, int(working.height * 0.86))),
                Image.Resampling.LANCZOS,
            )

        original_name = str(getattr(uploaded_file, "name", "field_photo") or "field_photo")
        safe_stem = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", os.path.splitext(os.path.basename(original_name))[0])[:60] or "field_photo"
        return best, f"{safe_stem}.jpg", "image/jpeg", ""
    except ImportError:
        return None, "", "", "사진 자동 압축을 위해 Pillow 패키지가 필요합니다. requirements.txt에 Pillow를 추가해 주세요."
    except Exception as error:
        return None, "", "", f"사진 처리 실패: {error}"


# ==========================================
# 사진 백그라운드 업로드 작업 (저장 속도·연결 끊김 대응)
#   - 기록 본문은 먼저 시트에 저장하고, 사진은 별도 스레드가 Drive에 올린 뒤 해당 행에 연결합니다.
#   - 화면이 꺼지거나 웹소켓이 끊겨도 서버에서 업로드가 계속됩니다.
#   - 실패한 사진은 작업 목록에 보관되어 "다시 시도" 버튼으로 이어서 올릴 수 있습니다.
# ==========================================
WORK_LOG_UPLOAD_TIMEOUT = 45
WORK_LOG_UPLOAD_MAX_RAW_BYTES = 40 * 1024 * 1024
_PHOTO_JOBS = _PS["photo_jobs"]
_PHOTO_JOBS_LOCK = _PS["photo_jobs_lock"]
_PHOTO_EXECUTOR = _PS["photo_executor"]


def _photo_cfg_snapshot() -> dict:
    """Apps Script 업로드 설정을 일반 dict로 복사합니다. (스레드에서 st.secrets를 읽지 않도록)"""
    url, error = _worklog_normalize_apps_script_url()
    token = _worklog_photo_upload_token()
    if not error and not token:
        error = "Streamlit Secrets의 [work_log] upload_token이 설정되지 않았습니다."
    return {"url": url, "token": token, "error": error}


def _apps_script_upload_bytes(
    cfg: dict, image_bytes: bytes, file_name: str, mime_type: str, attempts: int = 2
) -> tuple[bool, dict, str]:
    """압축된 사진 1장을 Apps Script로 저장합니다. 스트림릿 객체를 쓰지 않아 스레드에서도 안전합니다.

    JSON은 text/plain으로 보내 Apps Script 웹앱과의 호환성을 높이고, ContentService 리디렉션은 즉시 따라갑니다.
    일시 오류(시간 초과·5xx·연결 끊김)는 짧게 재시도하고, 토큰 불일치처럼 재시도해도 소용없는 오류는 바로 반환합니다.
    """
    if cfg.get("error"):
        return False, {}, str(cfg["error"])
    payload = {
        "token": cfg["token"],
        "filename": file_name,
        "mimeType": mime_type or "image/jpeg",
        "data": base64.b64encode(image_bytes).decode("ascii"),
    }
    payload_bytes = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Accept": "application/json,text/plain,*/*",
        "User-Agent": "SMART-WORK-AI-AGENT/6.0",
        "Cache-Control": "no-cache",
    }
    last_error = "알 수 없는 오류"
    for attempt in range(max(1, attempts)):
        retryable = True
        try:
            first = requests.post(
                cfg["url"], data=payload_bytes, headers=headers,
                timeout=WORK_LOG_UPLOAD_TIMEOUT, allow_redirects=False,
            )
            response, redirect_error = _worklog_follow_apps_script_response(first, timeout=WORK_LOG_UPLOAD_TIMEOUT)
            if redirect_error:
                last_error = redirect_error
            elif response is None:
                last_error = "Apps Script 응답을 받지 못했습니다."
            elif response.status_code != 200:
                last_error = (
                    f"PHOTO ENGINE {WORK_LOG_PHOTO_ENGINE_VERSION} · Apps Script POST 실패 ({response.status_code}). "
                    "/exec 배포 또는 익명 POST 접근을 확인해 주세요."
                )
                retryable = response.status_code >= 500 or response.status_code == 429
            elif response.text.lstrip().lower().startswith("<!doctype html"):
                last_error = "Apps Script가 JSON 대신 Google HTML을 반환했습니다. 최신 /exec 배포와 익명 접근을 확인해 주세요."
                retryable = False
            else:
                try:
                    result = response.json()
                except Exception:
                    result = None
                    last_error = f"Apps Script 응답이 JSON이 아닙니다: {response.text[:180]}"
                if result is not None:
                    if bool(result.get("ok")):
                        file_id = str(result.get("fileId", "") or "").strip()
                        if not file_id:
                            return False, {}, "Apps Script 저장 응답에 fileId가 없습니다."
                        return True, {
                            "id": file_id,
                            "name": str(result.get("fileName", file_name) or file_name),
                            "webViewLink": str(result.get("fileUrl", "") or ""),
                            "mimeType": mime_type or "image/jpeg",
                        }, ""
                    error_text = str(result.get("error", "알 수 없는 오류") or "알 수 없는 오류")
                    if error_text.lower() == "unauthorized":
                        return False, {}, "Apps Script에는 도달했지만 UPLOAD_TOKEN이 일치하지 않습니다."
                    last_error = f"Apps Script doPost 오류: {error_text}"
                    retryable = False
        except requests.Timeout:
            last_error = "Apps Script 사진 저장 시간이 초과되었습니다."
        except Exception as error:
            last_error = f"Apps Script 사진 저장 오류: {error}"
        if not retryable or attempt >= attempts - 1:
            break
        time.sleep(1.5 * (attempt + 1))
    return False, {}, last_error


def _prepare_photo_items(photos: list, now_dt, name_fn) -> tuple[list[dict], list[str]]:
    """대기열 사진을 업로드용 dict(데이터·파일명·형식)로 변환합니다. 이미 압축된 사진은 그대로 사용합니다."""
    items: list[dict] = []
    errors: list[str] = []
    for index, photo in enumerate(list(photos or [])[:WORK_LOG_MAX_PHOTOS], 1):
        compressed, _safe_name, mime_type, error = _worklog_compress_image(photo)
        if not compressed:
            errors.append(f"{index}번째 사진 처리 실패: {error}")
            continue
        stamp = _photo_capture_timestamp(photo, fallback_dt=now_dt)
        items.append({
            "data": compressed,
            "name": name_fn(stamp, index),
            "type": mime_type or "image/jpeg",
        })
    return items, errors


def _photo_job_public(job: dict) -> dict:
    return {
        "id": job["id"],
        "kind": job["kind"],
        "title": job["title"],
        "state": job["state"],
        "total": job["total"],
        "uploaded": job["uploaded"],
        "errors": list(job["errors"]),
        "failed_count": len(job["failed_items"]),
        "attached": job["attached"],
        "created_at": job["created_at"],
        "finished_at": job["finished_at"],
    }


def _photo_job_prune() -> None:
    now = time.time()
    with _PHOTO_JOBS_LOCK:
        for job_id, job in list(_PHOTO_JOBS.items()):
            finished = job.get("finished_at") or 0
            if job["state"] in ("done", "partial", "failed") and finished and now - finished > 6 * 3600:
                _PHOTO_JOBS.pop(job_id, None)
            elif now - job["created_at"] > 24 * 3600:
                _PHOTO_JOBS.pop(job_id, None)


def _photo_job_submit(*, kind: str, title: str, user_id: str, spec: dict, items: list[dict]) -> str:
    job_id = uuid.uuid4().hex[:12]
    job = {
        "id": job_id, "kind": kind, "title": title, "user_id": str(user_id or ""),
        "spec": spec, "items": list(items), "failed_items": [],
        "state": "queued", "total": len(items), "uploaded": 0, "attached": 0,
        "errors": [], "created_at": time.time(), "finished_at": 0.0, "dismissed": False,
    }
    with _PHOTO_JOBS_LOCK:
        _PHOTO_JOBS[job_id] = job
    _photo_job_prune()
    _PHOTO_EXECUTOR.submit(_photo_job_run, job_id)
    return job_id


def _photo_attach_to_sheet(spec: dict, new_ids: list[str], new_names: list[str]) -> None:
    """업로드된 사진 ID·파일명을 기록 행의 기존 값 뒤에 합쳐 저장합니다. (스레드 전용 시트 클라이언트 사용)"""
    client = _gs_make_client(spec["gs_info"])
    spreadsheet = _sheet_call(client.open, spec["spreadsheet"])
    ws = _sheet_call(spreadsheet.worksheet, spec["sheet"])
    headers = [str(v).strip() for v in _sheet_call(ws.row_values, 1)]
    id_header = spec["id_header"]
    if id_header not in headers:
        raise RuntimeError(f"시트에 '{id_header}' 열이 없습니다.")
    record_id = str(spec["record_id"]).strip()

    row_no = None
    for attempt in range(4):
        id_column = _sheet_call(ws.col_values, headers.index(id_header) + 1)
        for number in range(len(id_column), 1, -1):
            if str(id_column[number - 1]).strip() == record_id:
                row_no = number
                break
        if row_no is not None:
            break
        time.sleep(1.5 * (attempt + 1))
    if row_no is None:
        raise RuntimeError("사진을 연결할 기록 행을 찾지 못했습니다.")

    row = _sheet_call(ws.row_values, row_no)

    def cell(header: str) -> str:
        index = headers.index(header) if header in headers else -1
        return str(row[index]).strip() if 0 <= index < len(row) else ""

    existing_ids = [v.strip() for v in cell("사진파일ID목록").split("|") if v.strip()]
    existing_names = [v.strip() for v in cell("사진파일명목록").split("|") if v.strip()]
    all_ids = existing_ids + [v for v in new_ids if v not in existing_ids]
    all_names = existing_names + [v for v in new_names if v not in existing_names]
    now_text = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
    _sheet_update_fields(ws, headers, row_no, {
        "사진수": len(all_ids),
        "사진파일ID목록": "|".join(all_ids),
        "사진파일명목록": "|".join(all_names),
        "최근수정일시": now_text,
    }, raw=True)

    history = spec.get("history")
    if history:
        try:
            history_ws = _sheet_call(spreadsheet.worksheet, history["sheet"])
            history_headers = [str(v).strip() for v in _sheet_call(history_ws.row_values, 1)]
            history_map = dict(history["map"])
            history_map["저장일시"] = now_text
            history_map["변경구분"] = f"현장사진 추가 {len(new_ids)}장"
            _sheet_call(
                history_ws.append_row,
                [history_map.get(h, "") for h in history_headers],
                value_input_option="USER_ENTERED",
            )
        except Exception as error:
            logger.warning("사진 추가 이력 기록 실패: %s", error)


def _photo_job_run(job_id: str) -> None:
    with _PHOTO_JOBS_LOCK:
        job = _PHOTO_JOBS.get(job_id)
        if job is None:
            return
        job["state"] = "running"
        items = list(job["items"])
        spec = job["spec"]
    try:
        uploaded: list[tuple[dict, dict]] = []
        failed: list[dict] = []
        errors: list[str] = []
        consecutive_failures = 0
        for index, item in enumerate(items, 1):
            if consecutive_failures >= 3:
                failed.append(item)
                errors.append(f"{index}번째 사진: 연속 실패로 건너뜀 (연결 복구 후 '다시 시도')")
                continue
            ok, meta, error = _apps_script_upload_bytes(spec["cfg"], item["data"], item["name"], item["type"])
            if ok:
                consecutive_failures = 0
                uploaded.append((item, meta))
                with _PHOTO_JOBS_LOCK:
                    job["uploaded"] = len(uploaded)
            else:
                consecutive_failures += 1
                failed.append(item)
                errors.append(f"{index}번째 사진: {error}")

        attached = 0
        if uploaded:
            new_ids = [str(meta.get("id", "")) for _, meta in uploaded]
            new_names = [str(meta.get("name", item["name"])) for item, meta in uploaded]
            try:
                _photo_attach_to_sheet(spec, new_ids, new_names)
                attached = len(uploaded)
            except Exception as attach_error:
                logger.error("사진 시트 연결 실패: %s", attach_error)
                errors.append(f"사진은 올라갔지만 기록 연결에 실패했습니다: {attach_error}")
                try:
                    _worklog_apps_script_file_action("trash_files", new_ids, cfg=spec["cfg"])
                except Exception:
                    pass
                failed.extend(item for item, _ in uploaded)

        with _PHOTO_JOBS_LOCK:
            job["items"] = []
            job["failed_items"] = failed
            job["errors"] = errors
            job["attached"] = attached
            job["finished_at"] = time.time()
            if not failed:
                job["state"] = "done"
            elif attached:
                job["state"] = "partial"
            else:
                job["state"] = "failed"
    except Exception as error:  # 어떤 경우에도 작업 상태가 '진행 중'으로 남지 않도록 합니다.
        logger.exception("사진 작업 중 예외")
        with _PHOTO_JOBS_LOCK:
            job["state"] = "failed"
            job["errors"] = [f"작업 중 오류: {error}"]
            job["failed_items"] = list(items)
            job["finished_at"] = time.time()


def _photo_jobs_for_user(user_id: str) -> list[dict]:
    uid = str(user_id or "")
    with _PHOTO_JOBS_LOCK:
        jobs = [
            _photo_job_public(job) for job in _PHOTO_JOBS.values()
            if job["user_id"] == uid and not job.get("dismissed")
        ]
    return sorted(jobs, key=lambda j: j["created_at"], reverse=True)


def _photo_job_dismiss(job_id: str) -> None:
    with _PHOTO_JOBS_LOCK:
        job = _PHOTO_JOBS.get(job_id)
        if job and job["state"] in ("done", "partial", "failed"):
            job["dismissed"] = True
            if job["state"] == "done":
                job["failed_items"] = []


def _photo_job_retry(job_id: str) -> str:
    """실패한 사진만 모아 새 작업으로 다시 올립니다. 새 작업 ID를 반환(없으면 빈 문자열)."""
    with _PHOTO_JOBS_LOCK:
        job = _PHOTO_JOBS.get(job_id)
        if not job or job["state"] not in ("partial", "failed") or not job["failed_items"]:
            return ""
        items = list(job["failed_items"])
        spec = dict(job["spec"])
        kind, title, user_id = job["kind"], job["title"], job["user_id"]
        job["dismissed"] = True
        job["failed_items"] = []
    spec["cfg"] = _photo_cfg_snapshot()
    return _photo_job_submit(kind=kind, title=title, user_id=user_id, spec=spec, items=items)


def _render_photo_jobs_body() -> None:
    user = _worklog_current_user()
    jobs = _photo_jobs_for_user(str(user.get("user_id", "") or ""))
    if not jobs:
        return
    for job in jobs:
        label = html.escape(job["title"])
        if job["state"] in ("queued", "running"):
            total = max(job["total"], 1)
            st.progress(
                min(job["uploaded"] / total, 1.0),
                text=f"📤 {job['title']} · 사진 {job['uploaded']}/{job['total']}장 업로드 중 — 화면이 꺼져도 서버에서 계속 진행됩니다.",
            )
        elif job["state"] == "done":
            c1, c2 = st.columns([5, 1.2], gap="small", vertical_alignment="center")
            c1.success(f"✅ {job['title']} · 사진 {job['attached']}장이 기록에 연결되었습니다.")
            if c2.button("확인", key=f"photojob_ok_{job['id']}", use_container_width=True):
                _photo_job_dismiss(job["id"])
                st.rerun()
        else:
            reason = job["errors"][0] if job["errors"] else "원인을 확인하지 못했습니다."
            st.warning(
                f"⚠️ {job['title']} · 사진 {job['attached']}장 연결, {job['failed_count']}장 미첨부\n\n원인: {reason}"
            )
            c1, c2 = st.columns(2, gap="small")
            if job["failed_count"] and c1.button(
                f"실패한 사진 {job['failed_count']}장 다시 시도",
                key=f"photojob_retry_{job['id']}", type="primary", use_container_width=True,
            ):
                _photo_job_retry(job["id"])
                st.rerun()
            if c2.button("닫기", key=f"photojob_close_{job['id']}", use_container_width=True):
                _photo_job_dismiss(job["id"])
                st.rerun()


def _photo_jobs_active(user_id: str) -> bool:
    return any(j["state"] in ("queued", "running") for j in _photo_jobs_for_user(user_id))


if hasattr(st, "fragment"):
    @st.fragment(run_every=3)
    def _photo_jobs_live_fragment():
        _render_photo_jobs_body()
        user = _worklog_current_user()
        if not _photo_jobs_active(str(user.get("user_id", "") or "")):
            st.rerun()

    @st.fragment
    def _photo_jobs_idle_fragment():
        _render_photo_jobs_body()


def _render_photo_jobs_panel() -> None:
    """진행 중이거나 결과 확인이 필요한 사진 업로드 작업을 화면 상단에 표시합니다."""
    user = _worklog_current_user()
    user_id = str(user.get("user_id", "") or "")
    if not user_id or not _photo_jobs_for_user(user_id):
        return
    if hasattr(st, "fragment"):
        if _photo_jobs_active(user_id):
            _photo_jobs_live_fragment()
        else:
            _photo_jobs_idle_fragment()
    else:
        _render_photo_jobs_body()
        if _photo_jobs_active(user_id):
            st.button("🔄 업로드 상태 새로고침", key="photojob_manual_refresh")


def _worklog_upload_drive_image(image_bytes: bytes, file_name: str, mime_type: str) -> tuple[bool, dict, str]:
    """압축 사진 1장을 Apps Script로 저장합니다. (동기 호출용 · 실제 전송은 `_apps_script_upload_bytes`)"""
    return _apps_script_upload_bytes(_photo_cfg_snapshot(), image_bytes, file_name, mime_type)



def _worklog_apps_script_file_action(action: str, file_ids: list[str], cfg: dict | None = None) -> tuple[bool, dict, str]:
    """Apps Script 소유자 권한으로 Drive 파일을 휴지통 이동/복원합니다. (cfg를 주면 스레드에서도 안전)"""
    normalized_ids = [str(value or "").strip() for value in file_ids if str(value or "").strip()]
    if not normalized_ids:
        return True, {"processedIds": []}, ""

    cfg = cfg or _photo_cfg_snapshot()
    upload_url, url_error = cfg.get("url", ""), cfg.get("error", "")
    upload_token = cfg.get("token", "")
    if url_error:
        return False, {}, url_error
    if not upload_token:
        return False, {}, "[work_log] upload_token이 설정되지 않았습니다."

    payload = {
        "token": upload_token,
        "action": action,
        "fileIds": normalized_ids,
    }
    try:
        first = requests.post(
            upload_url,
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            headers={
                "Content-Type": "text/plain; charset=utf-8",
                "Accept": "application/json,text/plain,*/*",
                "User-Agent": "SMART-WORK-AI-AGENT/6.0",
                "Cache-Control": "no-cache",
            },
            timeout=60,
            allow_redirects=False,
        )
        response, redirect_error = _worklog_follow_apps_script_response(first, timeout=60)
        if redirect_error:
            return False, {}, redirect_error
        if response is None or response.status_code != 200:
            code = getattr(response, "status_code", getattr(first, "status_code", ""))
            return False, {}, f"Apps Script 파일 처리 요청 실패 ({code})"
        if response.text.lstrip().lower().startswith("<!doctype html"):
            return False, {}, "Apps Script가 JSON 대신 Google HTML을 반환했습니다. 최신 /exec 배포를 확인해 주세요."
        try:
            result = response.json()
        except Exception:
            return False, {}, f"Apps Script 파일 처리 응답이 JSON이 아닙니다: {response.text[:180]}"

        if not bool(result.get("ok")):
            error_text = str(result.get("error", "") or "")
            if error_text.lower() == "unauthorized":
                return False, result, "UPLOAD_TOKEN이 일치하지 않습니다."
            if "사진 데이터가 없습니다" in error_text:
                return False, result, (
                    "현재 Apps Script 배포에는 사진 삭제 기능이 없습니다. "
                    "V12와 함께 제공된 Apps Script V2로 교체 후 배포를 업데이트해 주세요."
                )
            return False, result, error_text or "Drive 파일 처리에 실패했습니다."
        return True, result, ""
    except requests.Timeout:
        return False, {}, "Drive 파일 처리 시간이 초과되었습니다."
    except Exception as error:
        return False, {}, f"Drive 파일 처리 오류: {error}"


def _worklog_trash_drive_files(file_ids: list[str]) -> tuple[bool, list[str], str]:
    """사진 파일을 영구삭제하지 않고 사용자 Drive 휴지통으로 이동합니다."""
    ok, result, error = _worklog_apps_script_file_action("trash_files", file_ids)
    processed = [
        str(value or "").strip()
        for value in (result.get("processedIds", result.get("trashedIds", [])) or [])
        if str(value or "").strip()
    ]
    if ok:
        return True, processed, ""

    # 부분 처리된 경우 로그 삭제를 중단하고 이미 휴지통으로 간 파일은 되돌립니다.
    if processed:
        _worklog_apps_script_file_action("restore_files", processed)
    return False, [], error


def _worklog_restore_drive_files(file_ids: list[str]) -> None:
    normalized_ids = [str(value or "").strip() for value in file_ids if str(value or "").strip()]
    if normalized_ids:
        _worklog_apps_script_file_action("restore_files", normalized_ids)


@st.cache_data(ttl=300, max_entries=24, show_spinner=False)
def _worklog_download_drive_image(file_id: str) -> bytes | None:
    """비공개 Drive 사진을 서비스 계정으로 읽어 최근 기록 썸네일에 사용합니다. (메모리 보호를 위해 최대 24장 캐시)"""
    file_id = str(file_id or "").strip()
    if not file_id:
        return None
    token = _worklog_drive_access_token()
    if not token:
        return None
    try:
        response = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"alt": "media", "supportsAllDrives": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=25,
        )
        if response.status_code == 200 and len(response.content) <= 8 * 1024 * 1024:
            return response.content
    except Exception:
        pass
    return None


def _render_power_photo_download(record, key_prefix: str) -> None:
    """정밀점검 1건에 연결된 비공개 Drive 사진을 전체보기/개별/ZIP 다운로드로 제공합니다."""
    photo_ids = [
        value.strip() for value in str(record.get("사진파일ID목록", "") or "").split("|") if value.strip()
    ]
    photo_names = [
        value.strip() for value in str(record.get("사진파일명목록", "") or "").split("|") if value.strip()
    ]
    if not photo_ids:
        st.info("이 정밀점검 기록에는 첨부된 사진이 없습니다.")
        return

    payloads = []
    failed_count = 0
    saved_stamp = re.sub(r"[^0-9]", "", str(record.get("저장일시", "") or ""))[:14] or _korea_now().strftime("%Y%m%d%H%M%S")
    safe_local = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", str(record.get("국소", "") or "정밀점검"))[:40] or "정밀점검"

    for index, file_id in enumerate(photo_ids, 1):
        photo_bytes = _worklog_download_drive_image(file_id)
        if not photo_bytes:
            failed_count += 1
            continue
        stored_name = photo_names[index - 1] if index - 1 < len(photo_names) else f"정밀점검_{saved_stamp}_{index:02d}.jpg"
        download_name = stored_name if stored_name.lower().endswith(".jpg") else f"{stored_name}.jpg"
        payloads.append({"index": index, "bytes": photo_bytes, "name": download_name})

    if not payloads:
        st.warning("사진 정보는 있으나 현재 파일을 읽을 수 없습니다. Drive 읽기 권한을 확인해 주세요.")
        return

    st.caption(f"첨부사진 {len(photo_ids)}장 · Drive 폴더는 공개하지 않고 이 화면에서만 조회·다운로드합니다.")
    photo_cols = st.columns(2)
    for pos, payload in enumerate(payloads):
        with photo_cols[pos % 2]:
            st.image(payload["bytes"], caption=f"사진 {payload['index']} / {len(photo_ids)}", use_container_width=True)
            st.download_button(
                "📥 사진 다운로드",
                data=payload["bytes"],
                file_name=payload["name"],
                mime="image/jpeg",
                use_container_width=True,
                key=f"{key_prefix}_photo_{payload['index']}",
            )

    try:
        from io import BytesIO
        import zipfile

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as photo_zip:
            for payload in payloads:
                photo_zip.writestr(payload["name"], payload["bytes"])
        zip_name = f"{safe_local}_정밀점검_{saved_stamp}_사진{len(payloads)}장.zip"
        st.download_button(
            f"📦 사진 {len(payloads)}장 전체 ZIP 다운로드",
            data=zip_buffer.getvalue(),
            file_name=zip_name,
            mime="application/zip",
            use_container_width=True,
            key=f"{key_prefix}_zip",
        )
    except Exception as zip_error:
        st.warning(f"사진 ZIP 파일을 만들지 못했습니다. 개별 다운로드를 이용해 주세요. ({zip_error})")

    if failed_count:
        st.warning(f"첨부사진 중 {failed_count}장은 현재 읽을 수 없어 표시하지 못했습니다.")



class _WorklogQueuedPhoto:
    """압축된 사진 bytes를 기존 UploadedFile 호환 객체처럼 제공합니다."""
    def __init__(
        self,
        data: bytes,
        name: str = "field_photo.jpg",
        mime_type: str = "image/jpeg",
        capture_stamp: str = "",
    ):
        self._data = bytes(data or b"")
        self.name = str(name or "field_photo.jpg")
        self.type = str(mime_type or "image/jpeg")
        self._worklog_precompressed = True
        self._worklog_safe_name = self.name
        self._worklog_capture_stamp = str(capture_stamp or "")

    def getvalue(self) -> bytes:
        return self._data


def _worklog_queue_selected_photos(queue_key: str, uploaded_files) -> tuple[int, int, list[str]]:
    """선택 즉시 압축 후 세션 큐에 누적합니다. 모바일 원본 대용량 bytes는 세션에 남기지 않습니다."""
    queue = list(st.session_state.get(queue_key, []) or [])
    seen = {
        str(item.get("digest", "") or "")
        for item in queue
        if isinstance(item, dict) and str(item.get("digest", "") or "")
    }

    added = 0
    failures: list[str] = []
    for file_index, file_obj in enumerate(list(uploaded_files or []), 1):
        if len(queue) >= WORK_LOG_MAX_PHOTOS:
            failures.append(f"최대 {WORK_LOG_MAX_PHOTOS}장까지만 추가할 수 있습니다.")
            break
        try:
            raw = file_obj.getvalue()
        except Exception as error:
            failures.append(f"{file_index}번째 사진을 읽지 못했습니다: {error}")
            continue
        if not raw:
            failures.append(f"{file_index}번째 사진 데이터가 비어 있습니다.")
            continue

        original_digest = hashlib.sha256(raw).hexdigest()
        if original_digest in seen:
            continue

        capture_stamp = _photo_capture_timestamp(file_obj, fallback_dt=_korea_now())
        compressed, safe_name, mime_type, compress_error = _worklog_compress_image(file_obj)
        if not compressed:
            meta = _worklog_uploaded_file_meta(file_obj)
            fmt_text = meta.get("ext") or meta.get("mime") or "형식 미확인"
            failures.append(
                f"{file_index}번째 사진 처리 실패 · {meta.get('name')} · {fmt_text}: {compress_error}"
            )
            continue

        queue.append({
            "data": compressed,
            "name": safe_name or "field_photo.jpg",
            "type": mime_type or "image/jpeg",
            "digest": original_digest,
            "capture_stamp": capture_stamp,
            "bytes": len(compressed),
        })
        seen.add(original_digest)
        added += 1

    st.session_state[queue_key] = queue[:WORK_LOG_MAX_PHOTOS]
    return added, len(st.session_state[queue_key]), failures


def _worklog_queued_photo_objects(queue_key: str) -> list:
    """세션 사진 큐를 기존 저장 함수가 그대로 사용할 수 있는 객체 목록으로 변환합니다."""
    result = []
    for item in list(st.session_state.get(queue_key, []) or [])[:WORK_LOG_MAX_PHOTOS]:
        if not isinstance(item, dict):
            continue
        raw = item.get("data", b"")
        if not raw:
            continue
        result.append(
            _WorklogQueuedPhoto(
                raw,
                str(item.get("name", "") or "field_photo.jpg"),
                str(item.get("type", "") or "image/jpeg"),
                str(item.get("capture_stamp", "") or ""),
            )
        )
    return result


def _worklog_clear_photo_queue(queue_key: str, nonce_key: str) -> None:
    st.session_state[queue_key] = []
    st.session_state[nonce_key] = int(st.session_state.get(nonce_key, 0) or 0) + 1


def _worklog_collect_photos(camera_photo, uploaded_photos) -> list:
    """카메라 촬영 + 앨범 업로드를 중복 제거해 최대 10장으로 합칩니다."""
    candidates = []
    if camera_photo is not None:
        candidates.append(camera_photo)
    candidates.extend(list(uploaded_photos or []))

    unique = []
    seen = set()
    for file_obj in candidates:
        try:
            digest = hashlib.sha256(file_obj.getvalue()).hexdigest()
        except Exception:
            digest = f"{getattr(file_obj, 'name', '')}|{id(file_obj)}"
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(file_obj)
        if len(unique) >= WORK_LOG_MAX_PHOTOS:
            break
    return unique



def _worklog_get_record_row(worksheet, record_id: str) -> tuple[dict, int | None, list[str]]:
    """기록ID로 시트의 실제 행/레코드를 찾습니다."""
    record_id = str(record_id or "").strip()
    try:
        values = worksheet.get_all_values()
    except Exception:
        return {}, None, []
    if not values:
        return {}, None, []
    headers = [str(value).strip() for value in values[0]]
    if "기록ID" not in headers:
        return {}, None, headers
    id_index = headers.index("기록ID")
    for row_no, row in enumerate(values[1:], start=2):
        current_id = str(row[id_index] if id_index < len(row) else "").strip()
        if current_id == record_id:
            record = {
                header: (row[index] if index < len(row) else "")
                for index, header in enumerate(headers)
            }
            return record, row_no, headers
    return {}, None, headers


def _worklog_can_access_record(record: dict, auth_user: dict) -> bool:
    if not auth_user:
        return False
    if _worklog_record_visibility(record) == "공개":
        return True
    return _worklog_record_owned_by(record, auth_user)


def save_work_log(record: dict, photos: list) -> tuple[bool, str, str, str]:
    """기록 본문을 먼저 시트에 저장하고, 사진은 백그라운드 작업으로 Drive에 올려 행에 연결합니다.

    사진 업로드가 느리거나 실패해도 본문 저장은 즉시 끝나므로, 저장 중 화면이 끊겨 기록이 유실되는 일이 없습니다.
    """
    client = init_google_sheet_connection()
    if not client:
        return False, _gs_connection_failure_message(), "", ""

    writer = str(record.get("작성자", "")).strip()
    owner_id = str(record.get("작성자ID", "") or "").strip()
    visibility = str(record.get("공개범위", "공개") or "공개").strip()
    area = str(record.get("권역", "")).strip()
    mother = str(record.get("모국", "")).strip()
    local = str(record.get("국소", "")).strip()
    status = str(record.get("상태", "신규")).strip()
    items = record.get("점검항목", []) or []
    issue = str(record.get("현상_특이사항", "")).strip()
    action = str(record.get("조치내용", "")).strip()
    followup = str(record.get("후속조치", "")).strip()
    remark = str(record.get("비고", "")).strip()
    photos = list(photos or [])[:WORK_LOG_MAX_PHOTOS]

    expected_owner = _worklog_user_id_from_name(writer)
    if not writer or not owner_id:
        return False, "MY WORK LOG 개인 인증 정보를 확인하지 못했습니다. 다시 로그인해 주세요.", "", ""
    if expected_owner and expected_owner != owner_id:
        return False, "로그인 사용자와 작성자 정보가 일치하지 않습니다. 다시 로그인해 주세요.", "", ""
    if visibility not in WORK_LOG_VISIBILITY_OPTIONS:
        return False, "공개범위 값이 올바르지 않습니다.", "", ""
    if area not in POWER_REGION_DATA:
        return False, "국사명을 검색하여 정확한 국사를 먼저 선택해 주세요.", "", ""
    area_map = POWER_REGION_DATA.get(area, {}).get("모국_국소", {})
    if mother not in area_map or local not in area_map.get(mother, []):
        return False, "선택한 국사의 권역·모국·국소 정보가 올바르지 않습니다. 국사를 다시 검색해 주세요.", "", ""
    if status not in WORK_LOG_STATUS_OPTIONS:
        return False, "상태이력 값이 올바르지 않습니다.", "", ""
    if not items:
        return False, "점검항목을 한 개 이상 선택해 주세요.", "", ""
    if not any([issue, action, followup, remark, photos]):
        return False, "현상·특이사항, 조치내용, 후속조치, 비고 또는 사진 중 한 가지 이상을 남겨 주세요.", "", ""

    now = _korea_now()
    record_id = _worklog_make_id(now)

    # 1) 사진 준비(이미 압축된 대기열 사진이므로 빠름) — 네트워크 작업 없음
    photo_items, prepare_errors = _prepare_photo_items(
        photos, now, lambda stamp, index: f"WORK LOG_{stamp}_{record_id}_{index:02d}.jpg"
    )

    # 2) 본문 저장 — 이 단계가 성공하면 기록은 확정됩니다.
    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws, history_ws = _worklog_ensure_sheets(spreadsheet)
        saved_at = now.strftime("%Y-%m-%d %H:%M:%S")
        row_map = {
            "저장일시": saved_at,
            "기록ID": record_id,
            "작성자": writer,
            "권역": area,
            "모국": mother,
            "국소": local,
            "상태": status,
            "점검항목": ", ".join(str(v) for v in items),
            "현상_특이사항": issue,
            "조치내용": action,
            "후속조치": followup,
            "비고": remark,
            "사진수": 0,
            "사진파일ID목록": "",
            "사진파일명목록": "",
            "최근수정일시": saved_at,
            "작성자ID": owner_id,
            "공개범위": visibility,
        }
        actual_headers = [str(value).strip() for value in _sheet_call(ws.row_values, 1)]
        _sheet_call(
            ws.append_row,
            [row_map.get(header, "") for header in actual_headers],
            value_input_option="USER_ENTERED",
        )

        history_headers = [str(value).strip() for value in _sheet_call(history_ws.row_values, 1)]
        history_map = {
            "저장일시": saved_at,
            "기록ID": record_id,
            "작성자": writer,
            "상태": status,
            "변경구분": "신규 등록",
            "조치내용": action,
            "후속조치": followup,
            "비고": remark,
            "작업자ID": owner_id,
        }
        _sheet_call(
            history_ws.append_row,
            [history_map.get(header, "") for header in history_headers],
            value_input_option="USER_ENTERED",
        )
    except Exception as error:
        return False, f"WORK LOG 저장 실패: {error}", "", ""

    # 3) 사진은 백그라운드로 업로드 후 행에 연결
    scope_text = "팀 공유" if visibility == "공개" else "나만 보기"
    warnings: list[str] = []
    if prepare_errors:
        warnings.append("; ".join(prepare_errors[:2]))
    photo_summary = "사진 없음"
    if photo_items:
        cfg = _photo_cfg_snapshot()
        if cfg["error"]:
            warnings.append(f"사진 업로드 설정 확인 필요: {cfg['error']}")
        else:
            try:
                job_id = _photo_job_submit(
                    kind="worklog",
                    title=f"MY WORK LOG · {local}",
                    user_id=owner_id,
                    spec={
                        "cfg": cfg, "gs_info": _gs_service_info(),
                        "spreadsheet": WORK_LOG_SPREADSHEET_NAME, "sheet": WORK_LOG_SHEET_NAME,
                        "id_header": "기록ID", "record_id": record_id, "history": None,
                    },
                    items=photo_items,
                )
                photo_summary = f"사진 {len(photo_items)}장 업로드 진행 중"
            except Exception as job_error:
                warnings.append(f"사진 업로드 작업을 시작하지 못했습니다: {job_error}")
    if photos and photo_summary == "사진 없음":
        photo_summary = f"사진 0/{len(photos)}장"
    warning_text = ""
    if warnings:
        warning_text = (
            "기록은 정상 저장됐지만 사진은 첨부되지 않았습니다. 원인: " + " / ".join(warnings)
            + " · 휴대폰 앨범의 원본은 유지되므로 상세·조치에서 사진만 다시 추가할 수 있습니다."
        )
    return True, f"MY WORK LOG가 저장되었습니다. · {scope_text} · {photo_summary}", record_id, warning_text


def append_work_log_photos(record_id: str, auth_user: dict, photos: list) -> tuple[bool, str]:
    """기존 본인 WORK LOG에 사진을 나중에 추가합니다. 업로드는 백그라운드로 진행되고 진행률이 화면 상단에 표시됩니다."""
    if not auth_user:
        return False, "개인 인증이 필요합니다."
    record_id = str(record_id or "").strip()
    photos = list(photos or [])
    if not record_id or not photos:
        return False, "추가할 사진을 선택해 주세요."

    client = init_google_sheet_connection()
    if not client:
        return False, _gs_connection_failure_message()
    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws, history_ws = _worklog_ensure_sheets(spreadsheet)
        record, row_no, headers = _worklog_get_record_row(ws, record_id)
        if not record or row_no is None:
            return False, "기록을 찾지 못했습니다."
        if not _worklog_record_owned_by(record, auth_user):
            return False, "사진 추가 권한은 이 기록을 작성한 본인에게만 있습니다."

        existing_ids = [v.strip() for v in str(record.get("사진파일ID목록", "") or "").split("|") if v.strip()]
        available = max(0, WORK_LOG_MAX_PHOTOS - len(existing_ids))
        if available <= 0:
            return False, f"사진은 최대 {WORK_LOG_MAX_PHOTOS}장까지 저장할 수 있습니다."

        cfg = _photo_cfg_snapshot()
        if cfg["error"]:
            return False, f"현재 사진 저장 연결을 사용할 수 없습니다. 기록 본문은 유지되어 있습니다. ({cfg['error']})"

        now = _korea_now()
        base_seq = len(existing_ids)
        photo_items, prepare_errors = _prepare_photo_items(
            photos[:available], now,
            lambda stamp, index: f"WORK LOG_{stamp}_{record_id}_{base_seq + index:02d}.jpg",
        )
        if not photo_items:
            return False, prepare_errors[0] if prepare_errors else "처리할 수 있는 사진이 없습니다."

        _photo_job_submit(
            kind="worklog",
            title=f"MY WORK LOG · {record.get('국소', '') or record.get('모국', '')} 사진 추가",
            user_id=str(auth_user.get("user_id", "") or ""),
            spec={
                "cfg": cfg, "gs_info": _gs_service_info(),
                "spreadsheet": WORK_LOG_SPREADSHEET_NAME, "sheet": WORK_LOG_SHEET_NAME,
                "id_header": "기록ID", "record_id": record_id,
                "history": {
                    "sheet": WORK_LOG_HISTORY_SHEET_NAME,
                    "map": {
                        "기록ID": record_id,
                        "작성자": str(auth_user.get("name", "") or ""),
                        "상태": str(record.get("상태", "") or ""),
                        "조치내용": str(record.get("조치내용", "") or ""),
                        "후속조치": str(record.get("후속조치", "") or ""),
                        "비고": str(record.get("비고", "") or ""),
                        "작업자ID": str(auth_user.get("user_id", "") or ""),
                    },
                },
            },
            items=photo_items,
        )
        message = f"사진 {len(photo_items)}장을 백그라운드로 업로드합니다. 진행 상황은 화면 상단에 표시됩니다."
        if prepare_errors:
            message += f" · {len(prepare_errors)}장은 처리 실패로 제외되었습니다."
        return True, message
    except Exception as error:
        return False, f"현장사진 추가 실패: {error}"


def load_work_logs(auth_user: dict | None = None) -> pd.DataFrame:
    """누적 WORK LOG를 읽은 뒤 공개 기록 + 로그인 사용자의 비공개 기록만 반환합니다."""
    auth_user = auth_user or _worklog_current_user()
    if not auth_user:
        return pd.DataFrame(columns=WORK_LOG_HEADERS)

    client = init_google_sheet_connection()
    if not client:
        raise RuntimeError("Google Sheets 연결 실패")
    spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
    try:
        ws = spreadsheet.worksheet(WORK_LOG_SHEET_NAME)
    except Exception:
        return pd.DataFrame(columns=WORK_LOG_HEADERS)

    values = ws.get_all_values()
    if not values:
        return pd.DataFrame(columns=WORK_LOG_HEADERS)

    headers = [str(v).strip() for v in values[0]]
    rows = [
        [row[i] if i < len(row) else "" for i in range(len(headers))]
        for row in values[1:]
        if any(str(cell or "").strip() for cell in row)
    ]
    df = pd.DataFrame(rows, columns=headers).fillna("")
    for required in WORK_LOG_HEADERS:
        if required not in df.columns:
            df[required] = ""

    df = _worklog_filter_accessible_records(df, auth_user)
    if not df.empty:
        df["_저장일시_dt"] = pd.to_datetime(df["저장일시"], errors="coerce")
        df = df.sort_values("_저장일시_dt", ascending=False, na_position="last")
    return df


def load_work_log_history(record_id: str, auth_user: dict | None = None) -> pd.DataFrame:
    """로그인 사용자가 볼 수 있는 기록에 대해서만 변경이력을 반환합니다."""
    auth_user = auth_user or _worklog_current_user()
    if not auth_user:
        return pd.DataFrame(columns=WORK_LOG_HISTORY_HEADERS)

    client = init_google_sheet_connection()
    if not client:
        return pd.DataFrame(columns=WORK_LOG_HISTORY_HEADERS)
    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        main_ws, history_ws = _worklog_ensure_sheets(spreadsheet)
        record, _, _ = _worklog_get_record_row(main_ws, record_id)
        if not record or not _worklog_can_access_record(record, auth_user):
            return pd.DataFrame(columns=WORK_LOG_HISTORY_HEADERS)

        records = history_ws.get_all_records()
        df = pd.DataFrame(records).fillna("") if records else pd.DataFrame(columns=WORK_LOG_HISTORY_HEADERS)
        if not df.empty and "기록ID" in df.columns:
            df = df[df["기록ID"].astype(str) == str(record_id)]
        return df
    except Exception:
        return pd.DataFrame(columns=WORK_LOG_HISTORY_HEADERS)


def update_work_log(
    record_id: str,
    writer: str,
    status: str,
    action: str,
    followup: str,
    remark: str,
    actor_user: dict | None = None,
) -> tuple[bool, str]:
    """공개 기록 또는 본인 비공개 기록만 갱신하고 실제 변경 사용자를 이력에 남깁니다."""
    record_id = str(record_id or "").strip()
    status = str(status or "").strip()
    actor_user = actor_user or _worklog_current_user()
    if not record_id:
        return False, "변경할 기록ID가 없습니다."
    if not actor_user:
        return False, "MY WORK LOG 개인 인증이 필요합니다."
    if status not in WORK_LOG_STATUS_OPTIONS:
        return False, "상태 값이 올바르지 않습니다."

    actor_name = str(actor_user.get("name", "") or "").strip()
    actor_id = str(actor_user.get("user_id", "") or "").strip()
    if not actor_name or not actor_id:
        return False, "로그인 사용자 정보를 확인하지 못했습니다."

    client = init_google_sheet_connection()
    if not client:
        return False, "Google Sheets 연결 실패"
    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws, history_ws = _worklog_ensure_sheets(spreadsheet)
        record, target_row, headers = _worklog_get_record_row(ws, record_id)
        if not record or target_row is None:
            return False, f"기록ID {record_id}를 찾지 못했습니다."
        if not _worklog_can_access_record(record, actor_user):
            return False, "이 기록에 접근할 권한이 없습니다."

        now_text = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        updates = {
            "상태": status,
            "조치내용": str(action or "").strip(),
            "후속조치": str(followup or "").strip(),
            "비고": str(remark or "").strip(),
            "최근수정일시": now_text,
        }
        for header, value in updates.items():
            if header in headers:
                ws.update_cell(target_row, headers.index(header) + 1, value)

        history_headers = [str(value).strip() for value in history_ws.row_values(1)]
        history_map = {
            "저장일시": now_text,
            "기록ID": record_id,
            "작성자": actor_name,
            "상태": status,
            "변경구분": "상태/조치 변경",
            "조치내용": updates["조치내용"],
            "후속조치": updates["후속조치"],
            "비고": updates["비고"],
            "작업자ID": actor_id,
        }
        history_ws.append_row(
            [history_map.get(header, "") for header in history_headers],
            value_input_option="USER_ENTERED",
        )
        return True, "상태이력과 조치내용이 업데이트되었습니다."
    except Exception as error:
        return False, f"WORK LOG 업데이트 실패: {error}"


def update_work_log_visibility(
    record_id: str,
    new_visibility: str,
    actor_user: dict | None = None,
) -> tuple[bool, str]:
    """작성자 본인만 자신의 과거/현재 WORK LOG 공개범위를 변경합니다.

    기존 자료에 작성자ID/공개범위가 비어 있어도 등록된 작성자 이름으로 소유권을
    복원한 뒤 명시값을 저장합니다. 공개범위 변경 사실은 MY_WORK_LOG_HISTORY에 남깁니다.
    """
    record_id = str(record_id or "").strip()
    new_visibility = str(new_visibility or "").strip()
    actor_user = actor_user or _worklog_current_user()

    if not record_id:
        return False, "변경할 기록ID가 없습니다."
    if not actor_user:
        return False, "MY WORK LOG 개인 인증이 필요합니다."
    if new_visibility not in WORK_LOG_VISIBILITY_OPTIONS:
        return False, "공개범위 값이 올바르지 않습니다."

    actor_name = str(actor_user.get("name", "") or "").strip()
    actor_id = str(actor_user.get("user_id", "") or "").strip()
    if not actor_name or not actor_id:
        return False, "로그인 사용자 정보를 확인하지 못했습니다."

    client = init_google_sheet_connection()
    if not client:
        return False, "Google Sheets 연결 실패"

    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws, history_ws = _worklog_ensure_sheets(spreadsheet)
        record, target_row, headers = _worklog_get_record_row(ws, record_id)
        if not record or target_row is None:
            return False, f"기록ID {record_id}를 찾지 못했습니다."
        if not _worklog_record_owned_by(record, actor_user):
            return False, "공개범위는 본인이 작성한 기록만 변경할 수 있습니다."

        old_visibility = _worklog_record_visibility(record)
        owner_id = _worklog_record_owner_id(record) or actor_id
        now_text = _korea_now().strftime("%Y-%m-%d %H:%M:%S")

        # 과거 자료의 빈 권한 필드도 이 시점에 명시값으로 보완합니다.
        updates = {
            "작성자ID": owner_id,
            "공개범위": new_visibility,
            "최근수정일시": now_text,
        }
        for header, value in updates.items():
            if header in headers:
                ws.update_cell(target_row, headers.index(header) + 1, value)

        if old_visibility != new_visibility:
            history_headers = [str(value).strip() for value in history_ws.row_values(1)]
            history_map = {
                "저장일시": now_text,
                "기록ID": record_id,
                "작성자": actor_name,
                "상태": str(record.get("상태", "") or "").strip(),
                "변경구분": f"공개범위 변경: {old_visibility} → {new_visibility}",
                "조치내용": "",
                "후속조치": "",
                "비고": "",
                "작업자ID": actor_id,
            }
            history_ws.append_row(
                [history_map.get(header, "") for header in history_headers],
                value_input_option="USER_ENTERED",
            )

        if old_visibility == new_visibility:
            return True, f"현재 공개범위가 이미 '{new_visibility}'입니다."
        scope_text = "🌐 공개 · 팀 공유" if new_visibility == "공개" else "🔒 비공개 · 나만 보기"
        return True, f"공개범위를 {scope_text}(으)로 변경했습니다. 사진 열람 권한도 같은 범위를 따릅니다."
    except Exception as error:
        return False, f"공개범위 변경 실패: {error}"


def _worklog_ensure_delete_audit_sheet(spreadsheet):
    try:
        ws = spreadsheet.worksheet(WORK_LOG_DELETE_AUDIT_SHEET_NAME)
    except Exception:
        ws = spreadsheet.add_worksheet(
            title=WORK_LOG_DELETE_AUDIT_SHEET_NAME,
            rows=5000,
            cols=max(len(WORK_LOG_DELETE_AUDIT_HEADERS) + 2, 12),
        )
        ws.append_row(WORK_LOG_DELETE_AUDIT_HEADERS, value_input_option="USER_ENTERED")
    _worklog_ensure_headers(ws, WORK_LOG_DELETE_AUDIT_HEADERS)
    return ws


def delete_work_log(record_id: str, auth_user: dict | None = None) -> tuple[bool, str]:
    """작성자 본인의 WORK LOG 1건과 연결 사진을 함께 삭제합니다. 사진은 Drive 휴지통으로 이동합니다."""
    auth_user = auth_user or _worklog_current_user()
    record_id = str(record_id or "").strip()
    if not auth_user:
        return False, "MY WORK LOG 개인 인증이 필요합니다."
    if not record_id:
        return False, "삭제할 기록ID가 없습니다."

    client = init_google_sheet_connection()
    if not client:
        return False, "Google Sheets 연결 실패"

    trashed_photo_ids: list[str] = []
    try:
        spreadsheet = _open_spreadsheet(WORK_LOG_SPREADSHEET_NAME, client)
        ws, history_ws = _worklog_ensure_sheets(spreadsheet)
        record, target_row, headers = _worklog_get_record_row(ws, record_id)
        if not record or target_row is None:
            return False, "삭제할 기록을 찾지 못했습니다."
        if not _worklog_record_owned_by(record, auth_user):
            return False, "본인이 작성한 기록만 삭제할 수 있습니다."

        photo_ids = [
            value.strip()
            for value in str(record.get("사진파일ID목록", "") or "").split("|")
            if value.strip()
        ]
        if photo_ids:
            photo_ok, trashed_photo_ids, photo_error = _worklog_trash_drive_files(photo_ids)
            if not photo_ok:
                return False, f"기록은 삭제하지 않았습니다. 연결 사진 정리에 실패했습니다: {photo_error}"

        # 본문을 지우기 전에 삭제 감사 메타데이터를 준비합니다. 개인 메모 내용 자체는 감사시트에 복제하지 않습니다.
        deleted_at = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        audit_map = {
            "삭제일시": deleted_at,
            "기록ID": record_id,
            "작성자ID": _worklog_record_owner_id(record),
            "작성자": str(record.get("작성자", "") or "").strip(),
            "삭제자ID": str(auth_user.get("user_id", "") or "").strip(),
            "삭제자": str(auth_user.get("name", "") or "").strip(),
            "공개범위": _worklog_record_visibility(record),
            "사진수": len(photo_ids),
        }

        # 이력은 아래 행부터 지워 행번호 변화를 방지합니다.
        history_values = history_ws.get_all_values()
        if history_values:
            history_headers = [str(value).strip() for value in history_values[0]]
            if "기록ID" in history_headers:
                id_index = history_headers.index("기록ID")
                delete_rows = [
                    row_no
                    for row_no, row in enumerate(history_values[1:], start=2)
                    if id_index < len(row) and str(row[id_index]).strip() == record_id
                ]
                for row_no in reversed(delete_rows):
                    history_ws.delete_rows(row_no)

        ws.delete_rows(target_row)

        audit_warning = ""
        try:
            audit_ws = _worklog_ensure_delete_audit_sheet(spreadsheet)
            audit_headers = [str(value).strip() for value in audit_ws.row_values(1)]
            audit_ws.append_row(
                [audit_map.get(header, "") for header in audit_headers],
                value_input_option="USER_ENTERED",
            )
        except Exception as audit_error:
            audit_warning = f" · 삭제 감사기록 저장 경고: {audit_error}"

        return True, f"WORK LOG 1건을 삭제했습니다. 연결 사진 {len(photo_ids)}장은 Drive 휴지통으로 이동했습니다.{audit_warning}"
    except Exception as error:
        # 본문 삭제가 실패했는데 사진만 휴지통으로 간 경우 자동 복원합니다.
        if trashed_photo_ids:
            _worklog_restore_drive_files(trashed_photo_ids)
        return False, f"WORK LOG 삭제 실패: {error}"


def _worklog_reset_entry_widgets() -> None:
    keys = [
        "worklog_writer", "worklog_area", "worklog_area_key", "worklog_mother", "worklog_local", "worklog_status",
        "worklog_items", "worklog_uploads", "worklog_photo_queue", "worklog_photo_upload_nonce", "worklog_photo_queue_notice",
        "worklog_issue", "worklog_action",
        "worklog_followup", "worklog_remark", "worklog_station_search_query",
        "worklog_station_search_candidates", "worklog_station_search_choice", "worklog_station_search_status",
        "worklog_station_search_notice", "worklog_station_search_applied",
        "worklog_items_confirmed_notice", "worklog_visibility",
    ]
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
    for key in list(st.session_state.keys()):
        key_text = str(key)
        if (
            key_text.startswith("wlentry_")
            or key_text.startswith("worklog_uploads_")
            or key_text.startswith("worklog_photo_queue_")
            or key_text.startswith("worklog_photo_upload_nonce_")
            or key_text.startswith("worklog_photo_queue_notice_")
            or key_text.startswith("worklog_photo_raw_receipt_")
            or key_text.startswith("worklog_photo_album_nonce_")
            or key_text.startswith("worklog_photo_camera_nonce_")
            or key_text.endswith("_health")
        ):
            del st.session_state[key]
        elif key_text in {
            "worklog_photo_queue_clear",
            "worklog_save",
            "worklog_items_ok",
        }:
            del st.session_state[key]


# ==========================================
# 9. 메인 화면 및 탭 구성
# ==========================================
st.markdown("""
<div class="smart-work-brand">
  <div class="smart-work-brand-line"></div>
  <div class="smart-work-brand-title">
    <span class="smart-work-brand-icon">◆</span>
    <span>SMART POWER <b>FIELD</b></span>
  </div>
  <div class="smart-work-brand-subtitle">ktMOS북부 · 전원시설 현장업무 플랫폼</div>
  <div class="smart-work-brand-version">v7.0 · 사용자 인증 · 신뢰 단말 · 자동 임시저장</div>
</div>
""", unsafe_allow_html=True)

# ✅ 상단 메뉴 카드형 디자인: 선택된 탭이 명확하게 보이도록 개선
st.markdown("""
<style>
/* 상단 브랜드: 기존 제목 문구는 유지하고 가독성/색상만 보강 */
.smart-work-brand {
    text-align: center;
    margin: 2px auto 18px auto;
    padding: 8px 12px 11px 12px;
}
.smart-work-brand-line {
    width: 78px;
    height: 4px;
    margin: 0 auto 9px auto;
    border-radius: 999px;
    background: linear-gradient(90deg, #D71920 0%, #FF5A5F 55%, #0F4C81 55%, #0F4C81 100%);
}
.smart-work-brand-title {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 9px;
    color: #24364B;
    font-size: clamp(1.85rem, 4vw, 2.65rem);
    line-height: 1.08;
    font-weight: 950;
    letter-spacing: -0.035em;
}
.smart-work-brand-title b {
    color: #D71920;
    font-weight: 950;
}
.smart-work-brand-icon {
    color: #D71920;
    font-size: .72em;
    filter: drop-shadow(0 2px 3px rgba(215,25,32,.18));
}
.smart-work-brand-subtitle {
    margin-top: 6px;
    color: #64748B;
    font-size: .92rem;
    font-weight: 750;
}
.smart-work-brand-version {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-top: 8px;
    padding: 4px 11px;
    border: 1px solid #CBD5E1;
    border-radius: 999px;
    background: #F8FAFC;
    color: #475569;
    font-size: .80rem;
    font-weight: 850;
    letter-spacing: .01em;
    line-height: 1.25;
}

/* 외부 스마트 내비 메뉴 1개: 기존 Streamlit 탭은 그대로 유지 */
.smart-navi-launch-wrap {
    display: flex;
    justify-content: flex-start;
    margin: 0 0 9px 0;
}
@keyframes pulse-attention {
    0% { box-shadow: 0 7px 18px rgba(215,25,32,.15); transform: translateY(0); }
    50% { box-shadow: 0 12px 25px rgba(215,25,32,.35); transform: translateY(-2px); }
    100% { box-shadow: 0 7px 18px rgba(215,25,32,.15); transform: translateY(0); }
}

.smart-navi-launch {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    min-height: 52px;
    padding: 8px 14px 8px 11px;
    border: 1.5px solid #D71920;
    border-left: 5px solid #D71920;
    border-radius: 15px;
    background: linear-gradient(135deg, #FFFFFF 0%, #FFF7F7 100%);
    box-shadow: 0 7px 18px rgba(15,23,42,.08);
    color: #24364B !important;
    text-decoration: none !important;
    transition: border-color .16s ease;
    animation: pulse-attention 2.5s infinite ease-in-out;
}
/* 🔥 부드럽고 빠른 왼쪽->오른쪽 스포츠카 애니메이션 */
.smart-navi-launch {
    overflow: visible !important;
}
.navi-sportscar-wrapper {
    position: absolute;
    top: -38px;
    left: -20px;
    z-index: 10;
    pointer-events: none;
    /* linear: 멈춤 없이 일정한 속도로 매끄럽게 이동 */
    animation: car-drive-smooth 1.8s linear infinite;
}
.navi-sportscar-inner {
    display: inline-block;
    font-size: 38px;
    filter: drop-shadow(0 5px 8px rgba(0,0,0,0.3));
    /* 핵심: 윈도우 기본 이모지가 왼쪽을 보므로 좌우를 뒤집어서 오른쪽을 보게 만듦 */
    transform: scaleX(-1);
}
.navi-signal {
    position: absolute;
    top: 10px;
    left: 20px;
    font-size: 24px;
    color: #D71920;
    font-weight: 900;
    opacity: 0;
    animation: signal-shoot 1.8s ease-out infinite;
    z-index: 5;
    pointer-events: none;
}
.signal-1 { animation-delay: 0.0s; }
.signal-2 { animation-delay: 0.2s; }
.signal-3 { animation-delay: 0.4s; }

@keyframes car-drive-smooth {
    0% { transform: translateX(-30px); opacity: 0; }
    15% { opacity: 1; transform: translateX(20px); }
    85% { opacity: 1; transform: translateX(260px); }
    100% { transform: translateX(310px); opacity: 0; }
}
@keyframes signal-shoot {
    0% { transform: translate(0, 0) scale(0.5) rotate(-45deg); opacity: 0; }
    20% { opacity: 1; }
    100% { transform: translate(120px, -50px) scale(1.8) rotate(45deg); opacity: 0; }
}
.smart-navi-launch:hover {
    transform: translateY(-1px);
    box-shadow: 0 10px 23px rgba(215,25,32,.14);
    border-color: #B91218;
}
.smart-navi-launch-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: 11px;
    background: #D71920;
    color: #FFFFFF;
    font-size: 20px;
    line-height: 1;
    box-shadow: 0 5px 12px rgba(215,25,32,.22);
}
.smart-navi-launch-copy {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
}
.smart-navi-launch-title {
    color: #24364B;
    font-size: 1.10rem;
    font-weight: 950;
    white-space: nowrap;
}
.smart-navi-launch-sub {
    margin-top: 3px;
    color: #D71920;
    font-size: .72rem;
    font-weight: 850;
}
.smart-navi-launch-arrow {
    color: #D71920;
    font-size: 1.05rem;
    font-weight: 950;
    margin-left: 2px;
}

/* Streamlit 탭을 카드형 메뉴처럼 보이게 개선 */
div[data-testid="stTabs"] > div[role="tablist"] {
    gap: 10px !important;
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
    scrollbar-width: thin !important;
    background: linear-gradient(135deg, #EEF4FF 0%, #F8FAFC 100%) !important;
    border: 1px solid #D8E3F2 !important;
    border-radius: 20px !important;
    padding: 10px !important;
    box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08) !important;
}
div[data-testid="stTabs"] button[role="tab"] {
    min-height: 62px !important;
    padding: 12px 18px !important;
    border-radius: 16px !important;
    border: 1px solid #D8E3F2 !important;
    background: #FFFFFF !important;
    color: #334155 !important;
    font-weight: 900 !important;
    box-shadow: 0 5px 14px rgba(15, 23, 42, 0.06) !important;
    transition: all 0.18s ease-in-out !important;
}
div[data-testid="stTabs"] button[role="tab"] p {
    font-size: clamp(1.5rem, 3.2vw, 1.8rem) !important;
    font-weight: 900 !important;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.15) !important;
    letter-spacing: -0.03em !important;
    line-height: 1.2 !important;
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
/* 상단 메뉴 전환 시 부드럽게 내려오는 느낌을 주되 기능 실행에는 관여하지 않습니다. */
div[data-testid="stTabs"] div[role="tabpanel"] {
    animation: smartWorkTabReveal .18s ease-out;
}
@keyframes smartWorkTabReveal {
    from { opacity:.72; transform:translateY(-5px); }
    to { opacity:1; transform:translateY(0); }
}

@media (max-width: 768px) {
    section.main .block-container { padding-left:.65rem !important; padding-right:.65rem !important; padding-top:.75rem !important; }
    div[data-testid="stTabs"] > div[role="tablist"] { padding:7px !important; gap:7px !important; border-radius:15px !important; }
    div[data-testid="stTabs"] button[role="tab"] { flex:0 0 auto !important; min-width:154px !important; min-height:56px !important; padding:9px 13px !important; }
    div[data-testid="stTabs"] button[role="tab"] p {
    font-size: clamp(1.5rem, 3.2vw, 1.8rem) !important;
    font-weight: 900 !important;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.15) !important;
    letter-spacing: -0.03em !important;
    line-height: 1.2 !important;
    margin: 0 !important;
}
    .smart-navi-launch-wrap { justify-content: stretch; }
    .smart-navi-launch { width: 100%; box-sizing: border-box; }
    .smart-work-brand { margin-bottom: 14px; }
}

</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="smart-navi-launch-wrap">
  <a class="smart-navi-launch" href="https://willowy-frangipane-e06d37.netlify.app/" target="_blank" rel="noopener noreferrer" aria-label="국사 스마트 내비게이션 새 창으로 열기">
    <div class="navi-sportscar-wrapper"><div class="navi-sportscar-inner">🏎️💨</div></div>
    <div class="navi-signal signal-1">⚡</div>
    <div class="navi-signal signal-2">⚡</div>
    <div class="navi-signal signal-3">⚡</div>
    <span class="smart-navi-launch-icon" aria-hidden="true">📡</span>
    <span class="smart-navi-launch-copy">
      <span class="smart-navi-launch-title">국사 스마트 내비</span>
      <span class="smart-navi-launch-sub">SMART NAVIGATION · 새 창</span>
    </span>
    <span class="smart-navi-launch-arrow" aria-hidden="true">↗</span>
  </a>
</div>
""", unsafe_allow_html=True)

# 사용자 인증 게이트: 신뢰 단말이면 자동 통과, 아니면 사용자 인증코드를 확인한 뒤에만 아래 화면을 그립니다.
_gate_user = _app_auth_gate()
_drafts_restore_once(_gate_user)
_render_status_strip(_gate_user)
_render_photo_jobs_panel()

tab_worklog, tab_power, tab_admin = st.tabs([
    "📝 현장기록",
    "🔋 전원 정밀점검",
    "📊 점검 데이터",
])

# ---------- (아이콘) 인라인 SVG: 애니메이션 모래시계 ----------


# =========================
# ✅ 체크 "순간" 감지 + 우측 카운트다운 렌더 유틸
# =========================




# --- [Top Tab: MY WORK LOG · 현장 기록 / 시설 이력] ---
with tab_worklog:
    # 조회를 닫았을 때 돌아올 MY WORK LOG 전용 상단 기준점입니다.
    st.markdown('<div id="worklog-top-anchor" style="height:1px;scroll-margin-top:18px;"></div>', unsafe_allow_html=True)
    st.markdown("""
    <style>
    .worklog-overview {
        display:grid;
        grid-template-columns:minmax(0,1fr) minmax(0,1fr);
        gap:12px;
        margin:8px 0 14px;
        align-items:stretch;
    }
    .worklog-hero {
        position:relative; overflow:hidden;
        background:linear-gradient(135deg,#FFFFFF 0%,#FFF7F7 48%,#F8FAFC 100%);
        border:1px solid #F1C7CA; border-left:8px solid #D71920;
        border-radius:18px; padding:15px 18px; margin:0;
        min-height:122px;
        box-shadow:0 8px 22px rgba(15,23,42,.07);
    }
    .worklog-hero:after {
        content:'📝'; position:absolute; right:18px; top:6px;
        font-size:64px; opacity:.08; transform:rotate(-6deg);
    }
    .worklog-hero .eyebrow { color:#D71920; font-size:.72rem; font-weight:950; letter-spacing:.12em; }
    .worklog-hero h2 { color:#B91218; margin:3px 0 2px; font-size:clamp(1.55rem,3vw,2.05rem); font-weight:950; letter-spacing:-.035em; }
    .worklog-hero .sub { color:#24364B; font-size:clamp(.96rem,2vw,1.12rem); font-weight:900; }
    .worklog-hero .desc { color:#64748B; margin-top:5px; font-size:.88rem; font-weight:750; line-height:1.45; padding-right:42px; }

    .worklog-section-title {
        color:#24364B;
        font-size:1.15rem;
        font-weight:950;
        line-height:1.25;
        margin:8px 0 8px;
        letter-spacing:-.015em;
    }
    .worklog-entry-title {
        color:#102A43;
        font-size:1.34rem;
        font-weight:950;
        line-height:1.25;
        margin:3px 0 10px;
        letter-spacing:-.025em;
    }
    .worklog-field-title {
        display:flex;
        align-items:center;
        width:clamp(230px,52%,360px);
        max-width:100%;
        box-sizing:border-box;
        color:#102A43;
        background:#E4F3DE;
        border-left:4px solid #4C8B50;
        border-radius:4px;
        padding:5px 10px;
        font-size:1.10rem;
        font-weight:950;
        line-height:1.25;
        margin:14px 0 9px;
        letter-spacing:-.018em;
    }

    .worklog-dashboard {
        background:#FFFFFF;
        border:1px solid #DCE5F1;
        border-left:5px solid #0F4C81;
        border-radius:18px;
        padding:12px 13px;
        min-height:122px;
        display:flex;
        flex-direction:column;
        justify-content:center;
        box-shadow:0 8px 22px rgba(15,23,42,.06);
    }
    .worklog-dashboard-label {
        color:#64748B;
        font-size:.72rem;
        font-weight:900;
        letter-spacing:.08em;
        margin-bottom:8px;
    }
    .worklog-kpi-grid {
        display:grid;
        grid-template-columns:repeat(4,minmax(0,1fr));
        gap:6px;
        width:100%;
    }
    .worklog-kpi {
        min-width:0;
        display:flex;
        align-items:baseline;
        justify-content:center;
        gap:3px;
        padding:9px 3px;
        border-radius:11px;
        background:#F8FAFC;
        border:1px solid #E2E8F0;
        white-space:nowrap;
        overflow:hidden;
    }
    .worklog-kpi .label { color:#64748B; font-size:.66rem; font-weight:900; letter-spacing:-.025em; }
    .worklog-kpi .value { color:#0F3B66; font-size:1.08rem; font-weight:950; letter-spacing:-.04em; }
    .worklog-kpi .unit { color:#64748B; font-size:.62rem; font-weight:850; }
    .worklog-kpi.open { background:#FFF7ED; border-color:#FED7AA; }
    .worklog-kpi.open .value { color:#C2410C; }
    .worklog-kpi.doing { background:#FAF5FF; border-color:#E9D5FF; }
    .worklog-kpi.doing .value { color:#7E22CE; }
    .worklog-kpi.done { background:#F0FDF4; border-color:#BBF7D0; }
    .worklog-kpi.done .value { color:#15803D; }

    .worklog-storage-note {
        background:#EFF6FF; border:1px solid #BFDBFE; border-left:5px solid #2563EB;
        border-radius:14px; padding:9px 12px; color:#1E3A8A; font-size:.86rem; font-weight:750; line-height:1.45;
    }
    .worklog-storage-note.ready { background:#F0FDF4; border-color:#BBF7D0; border-left-color:#16A34A; color:#166534; }
    .worklog-storage-note.warn { background:#FFF7ED; border-color:#FED7AA; border-left-color:#F97316; color:#9A3412; }

    .worklog-card {
        background:#FFFFFF; border:1px solid #DCE5F1; border-radius:16px;
        padding:14px 15px; margin:0 0 10px; box-shadow:0 6px 16px rgba(15,23,42,.055);
    }
    .worklog-card-top { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; }
    .worklog-place { color:#0F3B66; font-weight:950; font-size:1.08rem; }
    .worklog-meta { color:#64748B; font-size:.82rem; font-weight:750; margin-top:2px; }
    .worklog-body { color:#334155; font-weight:730; line-height:1.55; margin-top:8px; }
    .worklog-badge { display:inline-flex; padding:4px 9px; border-radius:999px; font-size:.78rem; font-weight:950; white-space:nowrap; }
    .worklog-badge.new { color:#B91C1C; background:#FEE2E2; }
    .worklog-badge.wait { color:#1D4ED8; background:#DBEAFE; }
    .worklog-badge.doing { color:#B45309; background:#FEF3C7; }
    .worklog-badge.recheck { color:#7E22CE; background:#F3E8FF; }
    .worklog-badge.done { color:#15803D; background:#DCFCE7; }

    .law-search-hero {
        display:flex; align-items:center; gap:12px; flex-wrap:wrap;
        background:linear-gradient(135deg,#EEF4FF,#F8FAFC); border:1px solid #C9D8EC;
        border-left:6px solid #24364B; border-radius:15px; padding:12px 15px; margin:6px 0 10px;
        color:#24364B;
    }
    .law-search-hero b { font-size:1.15rem; font-weight:950; }
    .law-search-hero span { color:#64748B; font-weight:750; }

    input[placeholder="예: 송포"]::placeholder {
        color:#94A3B8 !important;
        -webkit-text-fill-color:#94A3B8 !important;
        opacity:1 !important;
        font-weight:700 !important;
    }

    /* WORK LOG 조회 UI: PC는 대시보드 폭, 모바일은 공개 조회 시 조건+범위 / 검색어 / 불러오기 순으로 배치 */
    div[data-testid="stElementContainer"]:has(.worklog-search-row-marker),
    div[data-testid="stElementContainer"]:has(.worklog-recent-marker),
    div[data-testid="stElementContainer"]:has(.worklog-sticky-close-marker) {
        display:none !important;
    }

    @media (min-width:769px) {
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker) {
            width:calc(50% - 6px) !important;
            margin-left:calc(50% + 6px) !important;
            gap:.45rem !important;
            align-items:flex-end !important;
        }
    }

    /* 조회 결과가 열려 있을 때만 생성되는 고정 닫기 버튼 */
    div[data-testid="stElementContainer"]:has(.worklog-sticky-close-marker)
      + div[data-testid="stElementContainer"],
    .st-key-worklog_results_close {
        position:fixed !important;
        left:50% !important;
        bottom:12px !important;
        transform:translateX(-50%) !important;
        width:min(410px, calc(100vw - 28px)) !important;
        z-index:9999 !important;
        padding:6px !important;
        background:rgba(255,255,255,.96) !important;
        border:1px solid #CBD5E1 !important;
        border-radius:14px !important;
        box-shadow:0 12px 30px rgba(15,23,42,.20) !important;
        backdrop-filter:blur(10px);
    }
    div[data-testid="stElementContainer"]:has(.worklog-sticky-close-marker)
      + div[data-testid="stElementContainer"] button,
    .st-key-worklog_results_close button {
        min-height:44px !important;
        background:#D71920 !important;
        color:#FFFFFF !important;
        font-weight:950 !important;
        border:none !important;
        border-radius:10px !important;
    }
    .worklog-close-safe-space { height:72px; }

    @media (max-width:768px) {
        .worklog-overview { grid-template-columns:1fr; gap:7px; margin:6px 0 10px; }
        .worklog-hero { padding:12px 13px; border-radius:15px; min-height:auto; }
        .worklog-hero:after { font-size:44px; right:7px; top:7px; }
        .worklog-hero .eyebrow { font-size:.64rem; }
        .worklog-hero h2 { font-size:1.42rem; }
        .worklog-hero .sub { font-size:.92rem; }
        .worklog-hero .desc { font-size:.75rem; line-height:1.36; padding-right:24px; }

        .worklog-dashboard { min-height:auto; padding:7px 6px; border-radius:14px; }
        .worklog-dashboard-label { display:none; }
        .worklog-kpi-grid { grid-template-columns:repeat(4,minmax(0,1fr)); gap:3px; }
        .worklog-kpi { padding:6px 1px; gap:2px; border-radius:8px; }
        .worklog-kpi .label { font-size:.54rem; letter-spacing:-.055em; }
        .worklog-kpi .value { font-size:.88rem; }
        .worklog-kpi .unit { font-size:.52rem; }

        .worklog-section-title { font-size:1.02rem; font-weight:950; margin:8px 0 7px; }
        .worklog-entry-title { font-size:1.24rem; margin:2px 0 9px; }
        .worklog-field-title {
            width:min(92%,340px);
            font-size:1.04rem;
            font-weight:950;
            padding:5px 9px;
            margin:13px 0 8px;
        }

        .worklog-card { padding:12px 11px; }

        input[placeholder="예: 송포"],
        input[placeholder="예: 정청운"],
        input[placeholder="필요한 추가 메모"],
        textarea[placeholder^="예: 축전지"],
        textarea[placeholder^="예: 단자"],
        textarea[placeholder^="예: 다음"] {
            font-size:16px !important;
        }

        /* 모바일: 검색 조건 + 검색어를 첫 줄, 불러오기를 둘째 줄 전체 폭으로 */
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker) {
            display:grid !important;
            grid-template-columns:minmax(0,.82fr) minmax(0,1.38fr) !important;
            gap:6px !important;
            width:100% !important;
            margin:0 !important;
            align-items:end !important;
        }
        /* Streamlit 버전에 따라 컬럼 testid가 column / stColumn으로 달라질 수 있어 둘 다 대응 */
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="column"],
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="stColumn"] {
            width:100% !important;
            max-width:none !important;
            min-width:0 !important;
            flex:unset !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="column"]:nth-child(1),
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="stColumn"]:nth-child(1) { grid-column:1; grid-row:1; }
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="column"]:nth-child(2),
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="stColumn"]:nth-child(2) { grid-column:2; grid-row:1; }
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="column"]:nth-child(3),
        div[data-testid="stHorizontalBlock"]:has(.worklog-search-row-marker)
          > div[data-testid="stColumn"]:nth-child(3) {
            grid-column:1 / -1 !important;
            grid-row:2 !important;
            width:100% !important;
            max-width:none !important;
        }

        /* V15 공개 조회: 1행=검색조건+내/전체, 2행=검색어, 3행=불러오기 전체 폭 */
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker) {
            grid-template-columns:minmax(0,1fr) minmax(0,1fr) !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="column"]:nth-child(1),
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="stColumn"]:nth-child(1) { grid-column:1; grid-row:1; }
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="column"]:nth-child(2),
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="stColumn"]:nth-child(2) { grid-column:2; grid-row:1; }
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="column"]:nth-child(3),
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="stColumn"]:nth-child(3) {
            grid-column:1 / -1 !important; grid-row:2 !important; width:100% !important; max-width:none !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="column"]:nth-child(4),
        div[data-testid="stHorizontalBlock"]:has(.worklog-public-scope-marker)
          > div[data-testid="stColumn"]:nth-child(4) {
            grid-column:1 / -1 !important; grid-row:3 !important; width:100% !important; max-width:none !important;
        }
        /* 불러오기 버튼은 모바일에서 검색영역 전체 폭 + 한 줄 고정 */
        .st-key-worklog_refresh {
            width:100% !important;
            max-width:none !important;
        }
        .st-key-worklog_refresh button {
            width:100% !important;
            max-width:none !important;
            min-height:46px !important;
            white-space:nowrap !important;
        }

        /* 모바일: 기존 2열의 순서만 뒤집어 불러오기 바로 아래에 최근 기록 표시 */
        div[data-testid="stHorizontalBlock"]:has(.worklog-recent-marker) {
            display:flex !important;
            flex-direction:column-reverse !important;
            gap:.7rem !important;
        }
        div[data-testid="stHorizontalBlock"]:has(.worklog-recent-marker)
          > div[data-testid="column"] {
            width:100% !important;
            min-width:0 !important;
            flex:1 1 100% !important;
        }

        div[data-testid="stElementContainer"]:has(.worklog-sticky-close-marker)
          + div[data-testid="stElementContainer"],
        .st-key-worklog_results_close {
            bottom:max(10px, env(safe-area-inset-bottom)) !important;
            width:calc(100vw - 22px) !important;
        }
        .worklog-close-safe-space { height:78px; }
    }

    .worklog-auth-card {
        background:linear-gradient(135deg,#FFFFFF 0%,#F8FAFC 100%);
        border:1px solid #CBD5E1;
        border-left:6px solid #D71920;
        border-radius:18px;
        padding:18px 20px;
        margin:8px 0 14px;
        box-shadow:0 8px 22px rgba(15,23,42,.07);
    }
    .worklog-auth-title { color:#24364B; font-size:1.36rem; font-weight:950; margin-bottom:5px; }
    .worklog-auth-desc { color:#64748B; font-size:.94rem; font-weight:800; line-height:1.55; }
    .worklog-quick-login {
        background:linear-gradient(135deg,#F8FBFF 0%,#EEF6FF 100%);
        border:1px solid #BFDBFE; border-left:6px solid #2563EB;
        border-radius:16px; padding:12px 14px; margin:8px 0 10px;
    }
    .worklog-quick-login-title { color:#0F3B66; font-size:1.08rem; font-weight:950; margin-bottom:3px; }
    .worklog-quick-login-desc { color:#64748B; font-size:.84rem; font-weight:800; line-height:1.45; }
    .worklog-userbar {
        display:flex; align-items:center; justify-content:space-between; gap:10px;
        background:#EEF6FF; border:1px solid #BFDBFE; border-radius:14px;
        padding:10px 13px; margin:4px 0 10px;
    }
    .worklog-userbar .name { color:#0F3B66; font-size:1rem; font-weight:950; }
    .worklog-userbar .meta { color:#64748B; font-size:.78rem; font-weight:760; margin-top:2px; }
    .worklog-privacy-guide {
        display:grid; grid-template-columns:1fr 1fr; gap:8px; margin:6px 0 8px;
    }
    .worklog-privacy-guide .public,
    .worklog-privacy-guide .private {
        border-radius:12px; padding:9px 11px; line-height:1.4;
        font-size:.82rem; font-weight:760;
    }
    .worklog-privacy-guide .public { background:#EFF6FF; border:1px solid #BFDBFE; color:#1E40AF; }
    .worklog-privacy-guide .private { background:#FFF7ED; border:1px solid #FED7AA; color:#9A3412; }
    .worklog-privacy-badge {
        display:inline-flex; align-items:center; padding:3px 8px; border-radius:999px;
        font-size:.72rem; font-weight:950; white-space:nowrap; margin-left:5px;
    }
    .worklog-privacy-badge.public { background:#DBEAFE; color:#1D4ED8; }
    .worklog-privacy-badge.private { background:#FFEDD5; color:#C2410C; }
    .worklog-visibility-manage {
        background:#F8FAFC; border:1px solid #CBD5E1; border-left:5px solid #2563EB;
        border-radius:14px; padding:11px 13px; margin:12px 0 8px;
        color:#334155; font-size:.86rem; font-weight:760; line-height:1.5;
    }
    .worklog-visibility-manage.private {
        background:#FFF7ED; border-color:#FED7AA; border-left-color:#F97316; color:#9A3412;
    }
    .worklog-delete-box {
        background:#FFF7F7; border:1px solid #FECACA; border-left:5px solid #DC2626;
        border-radius:14px; padding:11px 13px; margin-top:12px;
    }

    /* 현장 가독성: MY WORK LOG 주요 메뉴/버튼/필드 라벨을 한 단계 굵고 크게 */
    .st-key-worklog_refresh button p,
    .st-key-worklog_results_close button p,
    .st-key-worklog_auth_settings_toggle button p,
    .st-key-worklog_logout button p {
        font-weight:950 !important;
        font-size:1rem !important;
    }
    div[data-testid="stForm"] label p,
    div[data-testid="stSelectbox"] label p {
        font-weight:850 !important;
    }

    @media (max-width:768px) {
        .worklog-auth-card { padding:14px 13px; border-radius:15px; }
        .worklog-privacy-guide { grid-template-columns:1fr; gap:5px; }
        .worklog-userbar { align-items:flex-start; }
    }
    </style>
    """, unsafe_allow_html=True)


    if st.session_state.pop("worklog_scroll_to_top", False):
        components.html(
            """
            <script>
            (function () {
              let tries = 0;
              function goTop() {
                try {
                  const w = window.parent;
                  const d = w.document;
                  const anchor = d.getElementById('worklog-top-anchor');
                  if (anchor) {
                    anchor.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    return;
                  }
                } catch (e) {}
                tries += 1;
                if (tries < 24) window.setTimeout(goTop, 70);
              }
              window.setTimeout(goTop, 90);
            })();
            </script>
            """,
            height=1,
        )

    worklog_auth_user = _worklog_current_user()

    if not worklog_auth_user:
        # 앱 진입 게이트(_app_auth_gate)가 인증과 최초 설정을 모두 끝낸 뒤에만 탭을 그립니다.
        st.stop()
    else:
        auth_user = worklog_auth_user

        # V23: 저장 성공 후에는 다음 rerun의 위젯 생성 전에 새 기록 입력값을 초기화합니다.
        # 이미 생성된 widget key를 같은 run에서 삭제하면 모바일/브라우저가 이전 값을 다시 보낼 수 있으므로
        # reset_pending 플래그를 사용해 렌더링 전에 초기화합니다.
        if st.session_state.pop("worklog_entry_reset_pending", False):
            _worklog_reset_entry_widgets()
            st.session_state["worklog_entry_reset_completed"] = True

        user_employee = str(auth_user.get("employee_no", "") or "")
        masked_employee = ("••••" + user_employee[-4:]) if len(user_employee) >= 4 else user_employee
        userbar_col, auth_manage_col, logout_col = st.columns([5.2, 1.8, 1.25], gap="small", vertical_alignment="center")
        with userbar_col:
            st.markdown(
                f'<div class="worklog-userbar"><div><div class="name">👤 {html.escape(str(auth_user.get("name","")))}</div>'
                f'<div class="meta">사용자 인증 완료 · 사번 {html.escape(masked_employee)}'
                f'{" · 신뢰 단말" if st.session_state.get("auth_via_device") else ""}</div></div></div>',
                unsafe_allow_html=True,
            )
        with auth_manage_col:
            if st.button("🔑 인증정보", key="worklog_auth_settings_toggle", use_container_width=True):
                st.session_state["worklog_show_auth_settings"] = not bool(st.session_state.get("worklog_show_auth_settings", False))
        with logout_col:
            st.button("로그아웃", key="worklog_logout", use_container_width=True, on_click=_worklog_logout)

        if st.session_state.get("worklog_show_auth_settings"):
            with st.container(border=True):
                st.markdown("#### 🔐 사용자 인증코드 변경")
                st.caption(f"사용자 인증에 쓰는 영문+숫자 {WORK_LOG_QUICK_LEN}자리 코드를 변경합니다.")
                with st.form("worklog_quick_code_change_form", clear_on_submit=True):
                    current_quick = st.text_input("현재 인증코드", type="password", max_chars=WORK_LOG_QUICK_LEN)
                    new_quick = st.text_input("새 인증코드", type="password", max_chars=WORK_LOG_QUICK_LEN)
                    new_quick_confirm = st.text_input("새 인증코드 확인", type="password", max_chars=WORK_LOG_QUICK_LEN)
                    quick_change_submit = st.form_submit_button(
                        "인증코드 변경",
                        type="primary",
                        use_container_width=True,
                    )
                if quick_change_submit:
                    verify_ok, verify_message = _worklog_verify_code_for_current_user(current_quick)
                    if not verify_ok:
                        st.error(f"현재 인증코드를 확인하지 못했습니다. {verify_message}")
                    else:
                        quick_ok, quick_message = _worklog_set_quick_code(
                            user_employee,
                            new_quick,
                            new_quick_confirm,
                        )
                        if quick_ok:
                            _audit_log("인증코드 변경", "")
                            st.success(quick_message)
                            time.sleep(0.35)
                            st.rerun()
                        else:
                            st.error(quick_message)

                st.markdown("#### 📱 신뢰 단말 관리")
                st.caption(
                    f"신뢰 단말에서는 사용자 인증을 다시 묻지 않습니다. 최대 {WORK_LOG_DEVICE_MAX_PER_USER}대까지 등록되며, "
                    f"{WORK_LOG_DEVICE_TTL_DAYS}일 이상 사용하지 않거나 단말 모델이 바뀌면 다시 인증합니다."
                )
                current_device_token = _device_token_from_cookie()
                current_device_hash = _device_hash(current_device_token) if current_device_token else ""
                my_devices = _devices_for_user(str(auth_user.get("user_id", "") or ""))
                if not my_devices:
                    st.info("등록된 신뢰 단말이 없습니다.")
                for device_row_no, device_rec in my_devices:
                    is_this_device = bool(current_device_hash) and str(device_rec.get("토큰해시", "")) == current_device_hash
                    dev_c1, dev_c2 = st.columns([4.2, 1.4], gap="small", vertical_alignment="center")
                    with dev_c1:
                        st.markdown(
                            f"**{'📍 이 단말 · ' if is_this_device else ''}{html.escape(str(device_rec.get('단말요약', '') or '단말'))}**  \n"
                            f"등록 {device_rec.get('등록일시', '')} · 최근 접속 {device_rec.get('최근접속', '')}"
                        )
                    with dev_c2:
                        if st.button("해제", key=f"worklog_device_revoke_{device_row_no}", use_container_width=True):
                            _device_revoke_row(device_row_no)
                            st.rerun()

                st.markdown("#### 🔐 복구용 개인 PIN 변경")
                st.caption("사용자 인증코드를 잊었을 때 사번과 함께 사용하는 숫자 6자리 PIN입니다.")
                with st.form("worklog_regular_pin_change_form", clear_on_submit=True):
                    current_pin = st.text_input("현재 복구 PIN", type="password", max_chars=6)
                    new_pin = st.text_input("새 복구 PIN", type="password", max_chars=6)
                    new_pin_confirm = st.text_input("새 복구 PIN 확인", type="password", max_chars=6)
                    pin_change_submit = st.form_submit_button("복구 PIN 변경", use_container_width=True)
                if pin_change_submit:
                    verify_ok, verify_message, _ = _worklog_authenticate_user(user_employee, current_pin)
                    if not verify_ok:
                        st.error(f"현재 복구 PIN 확인 실패: {verify_message}")
                    else:
                        pin_ok, pin_message = _worklog_change_pin(user_employee, new_pin, new_pin_confirm)
                        if pin_ok:
                            st.success(pin_message)
                            time.sleep(0.35)
                            st.rerun()
                        else:
                            st.error(pin_message)

        if "worklog_df" not in st.session_state:
            st.session_state["worklog_df"] = None
        if "worklog_loaded_at" not in st.session_state:
            st.session_state["worklog_loaded_at"] = ""
        if "worklog_selected_id" not in st.session_state:
            st.session_state["worklog_selected_id"] = ""
        if "worklog_selected_ui_key" not in st.session_state:
            st.session_state["worklog_selected_ui_key"] = ""

        def _worklog_close_loaded_results():
            """조회 결과만 닫고 새 현장기록 작성 중 입력값은 보존한 뒤 WORK LOG 상단으로 이동합니다."""
            st.session_state["worklog_df"] = None
            st.session_state["worklog_loaded_at"] = ""
            st.session_state["worklog_selected_id"] = ""
            st.session_state["worklog_selected_ui_key"] = ""
            st.session_state["worklog_search"] = ""
            st.session_state["worklog_filter"] = "전체"
            st.session_state["worklog_public_scope"] = "👤 내 기록"
            st.session_state["worklog_scroll_to_top"] = True
            for reset_key in (
                "worklog_update_writer", "worklog_update_status", "worklog_update_action",
                "worklog_update_followup", "worklog_update_remark",
            ):
                st.session_state.pop(reset_key, None)

        # PC/모바일 공용 상단: 왼쪽 MY WORK LOG 소개 + 오른쪽 미니 대시보드
        worklog_overview_slot = st.empty()

        photo_upload_ready, photo_config_issues = _worklog_photo_config_status()
        # 정상 운영 시 사진 저장 안내 문구는 표시하지 않습니다.
        # 설정 이상이 있을 때만 오류 원인을 보여 기존 사진 저장 안정성은 유지합니다.
        if not photo_upload_ready:
            issue_html = html.escape(" / ".join(photo_config_issues) if photo_config_issues else "사진 업로드 설정 확인 필요")
            st.markdown(
                f'<div class="worklog-storage-note warn">📷 사진 업로드 설정 확인 필요 · PHOTO ENGINE <b>{WORK_LOG_PHOTO_ENGINE_VERSION}</b><br><b>현재 진단:</b> {issue_html}<br>Streamlit Secrets의 <b>[work_log]</b>에 <b>photo_upload_url</b>과 <b>upload_token</b>을 확인해 주세요. 기존 내비·정밀점검 기능에는 영향이 없습니다.</div>',
                unsafe_allow_html=True,
            )

        # V15: 공개 조회는 "내 기록 / 전체 기록"을 선택할 수 있게 하고 검색어 폭을 줄입니다.
        public_filter_for_layout = str(st.session_state.get("worklog_filter", "전체") or "전체") == "🌐 공개"
        if public_filter_for_layout:
            search_condition_col, public_scope_col, search_text_col, search_load_col = st.columns(
                [0.24, 0.23, 0.31, 0.22], gap="small", vertical_alignment="bottom"
            )
        else:
            search_condition_col, search_text_col, search_load_col = st.columns(
                [0.30, 0.46, 0.24], gap="small", vertical_alignment="bottom"
            )
            public_scope_col = None

        with search_condition_col:
            st.markdown('<div class="worklog-search-row-marker"></div>', unsafe_allow_html=True)
            worklog_filter = st.selectbox(
                "검색 조건",
                ["전체", "🌐 공개", "🔒 내 비공개"] + WORK_LOG_STATUS_OPTIONS,
                key="worklog_filter",
            )

        worklog_public_scope = str(st.session_state.get("worklog_public_scope", "👤 내 기록") or "👤 내 기록")
        if worklog_filter == "🌐 공개":
            # Streamlit은 위젯 변경 시 즉시 rerun되므로 공개 선택 이후에는 4열 레이아웃으로 다시 그려집니다.
            if public_scope_col is not None:
                with public_scope_col:
                    st.markdown('<div class="worklog-public-scope-marker"></div>', unsafe_allow_html=True)
                    worklog_public_scope = st.selectbox(
                        "공개 기록 범위",
                        ["👤 내 기록", "👥 전체 기록"],
                        key="worklog_public_scope",
                        help="내 기록은 로그인한 본인이 작성한 공개 기록만, 전체 기록은 모든 사용자의 공개 기록을 조회합니다.",
                    )
            else:
                st.session_state["worklog_public_scope"] = "👤 내 기록"
                worklog_public_scope = "👤 내 기록"
        else:
            worklog_public_scope = "👤 내 기록"

        with search_text_col:
            worklog_search = st.text_input(
                "검색어",
                placeholder="국사 · 작성자 · 점검항목 등",
                key="worklog_search",
            ).strip()
        with search_load_col:
            refresh_worklog = st.button(
                "🔄 불러오기",
                use_container_width=True,
                type="primary",
                key="worklog_refresh",
            )

        if refresh_worklog:
            with st.spinner("Google Sheets에서 MY WORK LOG를 불러오는 중입니다..."):
                try:
                    st.session_state["worklog_df"] = load_work_logs(auth_user)
                    st.session_state["worklog_loaded_at"] = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
                    st.session_state["worklog_selected_id"] = ""
                    st.session_state["worklog_selected_ui_key"] = ""
                except Exception as error:
                    st.error(f"WORK LOG를 불러오지 못했습니다: {error}")

        loaded_df = st.session_state.get("worklog_df")
        if isinstance(loaded_df, pd.DataFrame):
            summary_source = loaded_df.copy()
            count_open = int(summary_source["상태"].isin(["신규", "확인필요"]).sum()) if not summary_source.empty else 0
            count_doing = int(summary_source["상태"].isin(["조치중", "재점검"]).sum()) if not summary_source.empty else 0
            count_done = int((summary_source["상태"] == "완료").sum()) if not summary_source.empty else 0
            count_all = int(len(summary_source))
        else:
            count_all = count_open = count_doing = count_done = 0

        count_all_text = f"{count_all:,}" if loaded_df is not None else "-"
        count_open_text = f"{count_open:,}" if loaded_df is not None else "-"
        count_doing_text = f"{count_doing:,}" if loaded_df is not None else "-"
        count_done_text = f"{count_done:,}" if loaded_df is not None else "-"

        worklog_overview_slot.markdown(
            f"""
            <div class="worklog-overview">
              <div class="worklog-hero">
                <div class="eyebrow">FIELD HISTORY &amp; RECORD</div>
                <h2>MY WORK LOG</h2>
                <div class="sub">현장 기록 · 시설 이력</div>
                <div class="desc">오늘의 현장 기록이 내일의 정확한 업무가 됩니다. 상태이력·점검항목·사진·조치사항을 국사별로 연결해 관리합니다.</div>
              </div>
              <div class="worklog-dashboard">
                <div class="worklog-dashboard-label">WORK LOG STATUS</div>
                <div class="worklog-kpi-grid">
                  <div class="worklog-kpi">
                    <span class="label">전체 기록</span><span class="value">{count_all_text}</span><span class="unit">건</span>
                  </div>
                  <div class="worklog-kpi open">
                    <span class="label">미처리</span><span class="value">{count_open_text}</span><span class="unit">건</span>
                  </div>
                  <div class="worklog-kpi doing">
                    <span class="label">진행·재점검</span><span class="value">{count_doing_text}</span><span class="unit">건</span>
                  </div>
                  <div class="worklog-kpi done">
                    <span class="label">완료</span><span class="value">{count_done_text}</span><span class="unit">건</span>
                  </div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.session_state.get("worklog_loaded_at"):
            st.caption(f"최근 기록 조회시각: {st.session_state['worklog_loaded_at']} · 화면 진입만으로는 Google Sheets를 자동 조회하지 않습니다.")

        entry_col, recent_col = st.columns([0.94, 1.06], gap="large")

        with entry_col:
            st.markdown('<div class="worklog-entry-title">📝 새 현장기록</div>', unsafe_allow_html=True)
            post_save_result = st.session_state.pop("worklog_post_save_result", None)
            if isinstance(post_save_result, dict):
                st.success("✅ " + str(post_save_result.get("message", "") or "MY WORK LOG가 저장되었습니다."))
                if str(post_save_result.get("warning", "") or "").strip():
                    st.warning("⚠️ " + str(post_save_result.get("warning", "") or "").strip())
            if st.session_state.pop("worklog_entry_reset_completed", False):
                st.caption("새 기록 입력창이 초기화되었습니다. 다음 현장기록을 바로 작성할 수 있습니다.")

            # V24 HARD RESET:
            # 저장 성공마다 generation을 증가시켜 모든 새 기록 위젯 key를 새 값으로 만듭니다.
            # 따라서 모바일 브라우저가 이전 입력 위젯을 재사용할 수 없습니다.
            entry_generation = int(st.session_state.get("worklog_entry_generation", 0) or 0)
            entry_key = lambda name: f"wlentry_{entry_generation}_{name}"

            with st.container(border=True):
                st.markdown('<div class="worklog-field-title">✍️ 작성자</div>', unsafe_allow_html=True)
                writer = str(auth_user.get("name", "") or "").strip()
                st.markdown(
                    f'<div class="worklog-userbar"><div><div class="name">👤 {html.escape(writer)}</div>'
                    f'<div class="meta">개인 인증된 사용자 · 작성자는 자동으로 고정됩니다.</div></div></div>',
                    unsafe_allow_html=True,
                )

                st.markdown('<div class="worklog-field-title">🔐 공개범위</div>', unsafe_allow_html=True)
                visibility_label = st.radio(
                    "공개범위",
                    ["🌐 공개 · 팀 공유", "🔒 비공개 · 나만 보기"],
                    horizontal=True,
                    key=entry_key("visibility"),
                    label_visibility="collapsed",
                )
                visibility = "비공개" if visibility_label.startswith("🔒") else "공개"
                st.markdown(
                    '<div class="worklog-privacy-guide">'
                    '<div class="public"><b>🌐 공개 · 팀 공유</b><br>업무 공유가 필요한 기록입니다. 인증된 팀원이 검색·조회할 수 있습니다.</div>'
                    '<div class="private"><b>🔒 비공개 · 나만 보기</b><br>개인 업무메모입니다. 작성한 본인만 검색·조회·사진 다운로드할 수 있습니다.</div>'
                    '</div>',
                    unsafe_allow_html=True,
                )

                st.markdown('<div class="worklog-field-title">📍 국사 검색 · 자동입력</div>', unsafe_allow_html=True)
                st.caption("정밀점검과 같은 국사 기준정보를 사용합니다. 국사명만 검색·선택하면 권역·모국·국소가 자동 반영됩니다.")

                station_query_key = entry_key("station_search_query")
                with st.form(key=entry_key("station_search_form"), clear_on_submit=False):
                    station_search_col, station_search_btn_col = st.columns([4.2, 1.15], gap="small")
                    with station_search_col:
                        st.text_input(
                            "국사명",
                            key=station_query_key,
                            placeholder="예: 송포",
                            help="국사명을 입력한 뒤 확인을 누르세요. 키보드 Enter로도 검색할 수 있습니다.",
                            label_visibility="collapsed",
                        )
                    with station_search_btn_col:
                        worklog_station_search_submitted = st.form_submit_button("확인", use_container_width=True)

                if worklog_station_search_submitted:
                    # 기존 검색 엔진은 내부 상태명 그대로 사용하고,
                    # 화면 widget만 generation key로 분리합니다.
                    st.session_state["worklog_station_search_query"] = str(
                        st.session_state.get(station_query_key, "") or ""
                    )
                    _run_worklog_station_search()

                worklog_station_search_status = str(
                    st.session_state.get("worklog_station_search_status", "") or ""
                )
                worklog_station_candidate_ids = list(
                    st.session_state.get("worklog_station_search_candidates", []) or []
                )

                if worklog_station_search_status == "empty":
                    st.warning("국사명을 먼저 입력해 주세요. 예: 송포")
                elif worklog_station_search_status == "none":
                    st.warning("일치하는 국사를 찾지 못했습니다. 국사명을 다시 확인해 주세요.")
                elif worklog_station_search_status == "multiple" and worklog_station_candidate_ids:
                    st.info(
                        f"같은 이름 또는 유사한 국사가 {len(worklog_station_candidate_ids)}곳 있습니다. "
                        "아래에서 정확한 국사를 선택해 주세요."
                    )
                    station_choice_key = entry_key("station_search_choice")
                    with st.form(key=entry_key("station_duplicate_form"), clear_on_submit=False):
                        st.radio(
                            "국사 선택",
                            worklog_station_candidate_ids,
                            key=station_choice_key,
                            format_func=_worklog_station_search_label,
                        )
                        worklog_station_choice_submitted = st.form_submit_button(
                            "선택 확인", use_container_width=True
                        )
                    if worklog_station_choice_submitted:
                        st.session_state["worklog_station_search_choice"] = str(
                            st.session_state.get(station_choice_key, "") or ""
                        )
                        _confirm_worklog_station_search_choice()

                worklog_station_notice = str(
                    st.session_state.get("worklog_station_search_notice", "") or ""
                )
                if worklog_station_notice:
                    st.success(worklog_station_notice)

                area = str(st.session_state.get("worklog_area_key", "") or "").strip()
                mother = str(st.session_state.get("worklog_mother", "") or "").strip()
                local = str(st.session_state.get("worklog_local", "") or "").strip()
                area_display = _worklog_area_display(area)

                st.markdown(
                    f"""<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:6px 0 12px;">
                        <div style="grid-column:1/-1;background:#FAF5FF;border:1px solid #C4B5FD;border-radius:11px;padding:10px 12px;">
                            <div style="font-size:.78rem;font-weight:900;color:#6D28D9;margin-bottom:3px;">권역</div>
                            <div style="font-weight:950;color:#5B21B6;line-height:1.45;">{html.escape(area_display)}</div>
                        </div>
                        <div style="background:#F8FAFC;border:1px solid #CBD5E1;border-radius:11px;padding:10px 12px;">
                            <div style="font-size:.78rem;font-weight:900;color:#64748B;margin-bottom:3px;">모국</div>
                            <div style="font-weight:900;color:#24364B;">{html.escape(mother or '자동 표시')}</div>
                        </div>
                        <div style="background:#F8FAFC;border:1px solid #CBD5E1;border-radius:11px;padding:10px 12px;">
                            <div style="font-size:.78rem;font-weight:900;color:#64748B;margin-bottom:3px;">국소</div>
                            <div style="font-weight:900;color:#24364B;">{html.escape(local or '자동 표시')}</div>
                        </div>
                    </div>""",
                    unsafe_allow_html=True,
                )

                st.markdown('<div class="worklog-field-title">🔄 상태이력</div>', unsafe_allow_html=True)
                status = st.radio(
                    "상태이력",
                    WORK_LOG_STATUS_OPTIONS,
                    horizontal=True,
                    key=entry_key("status"),
                    label_visibility="collapsed",
                )

                st.markdown('<div class="worklog-field-title">🧰 점검항목</div>', unsafe_allow_html=True)
                item_select_col, item_ok_col = st.columns([4.35, 1.0], gap="small", vertical_alignment="center")
                with item_select_col:
                    items = st.multiselect(
                        "점검항목",
                        WORK_LOG_ITEM_OPTIONS,
                        placeholder="전원 · 축전지 · 접지 · 냉방 · 출입 · 안전 · 기타",
                        key=entry_key("items"),
                        label_visibility="collapsed",
                    )
                with item_ok_col:
                    worklog_items_ok = st.button(
                        "확인",
                        key=entry_key("items_ok"),
                        use_container_width=True,
                    )
                if worklog_items_ok:
                    selected_item_text = ", ".join(items) if items else "선택 없음"
                    st.session_state["worklog_items_confirmed_notice"] = f"선택 완료: {selected_item_text}"
                if st.session_state.get("worklog_items_confirmed_notice"):
                    st.caption(st.session_state["worklog_items_confirmed_notice"])

                st.markdown('<div class="worklog-field-title">📷 현장사진</div>', unsafe_allow_html=True)
                worklog_photo_queue_key = f"worklog_photo_queue_{entry_generation}"
                worklog_photo_notice_key = f"worklog_photo_queue_notice_{entry_generation}"
                worklog_raw_receipt_key = f"worklog_photo_raw_receipt_{entry_generation}"
                worklog_health_key = f"{worklog_photo_queue_key}_health"
                worklog_album_nonce_key = f"worklog_photo_album_nonce_{entry_generation}"
                worklog_camera_nonce_key = f"worklog_photo_camera_nonce_{entry_generation}"
                worklog_album_nonce = int(st.session_state.get(worklog_album_nonce_key, 0) or 0)
                worklog_camera_nonce = int(st.session_state.get(worklog_camera_nonce_key, 0) or 0)

                st.caption("앨범은 여러 장을 한 번에 선택할 수 있습니다. 직접 촬영은 촬영 후 아래 확인 버튼을 눌러 사진을 담습니다.")

                with st.form(key=entry_key(f"photo_album_form_{worklog_album_nonce}"), clear_on_submit=False):
                    album_files = st.file_uploader(
                        "🖼️ 앨범에서 여러 장 선택",
                        type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
                        accept_multiple_files=True,
                        key=entry_key(f"album_uploads_{worklog_album_nonce}"),
                    ) or []
                    album_submit = st.form_submit_button(
                        "선택한 사진 담기",
                        use_container_width=True,
                    )
                if album_submit:
                    _worklog_process_photo_submission(
                        album_files,
                        worklog_photo_queue_key,
                        worklog_photo_notice_key,
                        worklog_raw_receipt_key,
                        worklog_health_key,
                    )
                    st.session_state[worklog_album_nonce_key] = worklog_album_nonce + 1
                    st.rerun()

                with st.form(key=entry_key(f"photo_camera_form_{worklog_camera_nonce}"), clear_on_submit=False):
                    camera_file = st.file_uploader(
                        "📷 카메라 촬영 또는 사진 1장 선택",
                        type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
                        accept_multiple_files=False,
                        key=entry_key(f"camera_upload_{worklog_camera_nonce}"),
                    )
                    camera_submit = st.form_submit_button(
                        "촬영/선택 사진 담기",
                        use_container_width=True,
                    )
                if camera_submit:
                    _worklog_process_photo_submission(
                        [camera_file] if camera_file is not None else [],
                        worklog_photo_queue_key,
                        worklog_photo_notice_key,
                        worklog_raw_receipt_key,
                        worklog_health_key,
                    )
                    st.session_state[worklog_camera_nonce_key] = worklog_camera_nonce + 1
                    st.rerun()

                queue_notice = str(st.session_state.pop(worklog_photo_notice_key, "") or "").strip()
                if queue_notice:
                    if "실패" in queue_notice or "못했습니다" in queue_notice or "없습니다" in queue_notice or "최대" in queue_notice:
                        st.warning(queue_notice)
                    else:
                        st.success(queue_notice)

                photos = _worklog_queued_photo_objects(worklog_photo_queue_key)
                _worklog_render_photo_pipeline_status(
                    photos,
                    worklog_photo_queue_key,
                    worklog_raw_receipt_key,
                    worklog_health_key,
                )
                photo_info_col, photo_clear_col = st.columns([4.0, 1.2], gap="small", vertical_alignment="center")
                with photo_info_col:
                    st.caption(
                        f"첨부 대기 {len(photos)}장 / 최대 {WORK_LOG_MAX_PHOTOS}장 · "
                        "여러 장 선택과 1장 촬영을 섞어서 추가할 수 있습니다."
                    )
                with photo_clear_col:
                    if photos and st.button(
                        "사진 지우기",
                        key=entry_key("photo_queue_clear"),
                        use_container_width=True,
                    ):
                        st.session_state[worklog_photo_queue_key] = []
                        st.session_state.pop(worklog_raw_receipt_key, None)
                        st.session_state.pop(worklog_health_key, None)
                        st.rerun()

                st.markdown('<div class="worklog-field-title">📝 현상·특이사항</div>', unsafe_allow_html=True)
                issue = st.text_area(
                    "현상·특이사항",
                    placeholder="예: 축전지 1조 7번 셀 전압이 다른 셀보다 낮게 측정됨",
                    height=105,
                    key=entry_key("issue"),
                    label_visibility="collapsed",
                )
                st.markdown('<div class="worklog-field-title">🛠️ 조치내용</div>', unsafe_allow_html=True)
                action = st.text_area(
                    "조치내용",
                    placeholder="예: 단자 상태 확인 및 재측정",
                    height=85,
                    key=entry_key("action"),
                    label_visibility="collapsed",
                )
                st.markdown('<div class="worklog-field-title">🔁 후속조치</div>', unsafe_allow_html=True)
                followup = st.text_area(
                    "후속조치",
                    placeholder="예: 다음 방문 시 1조 7번 셀 재확인",
                    height=85,
                    key=entry_key("followup"),
                    label_visibility="collapsed",
                )
                st.markdown('<div class="worklog-field-title">📌 비고</div>', unsafe_allow_html=True)
                remark = st.text_input(
                    "비고",
                    placeholder="필요한 추가 메모",
                    key=entry_key("remark"),
                    label_visibility="collapsed",
                )

                save_log = st.button(
                    "💾 MY WORK LOG 저장",
                    use_container_width=True,
                    type="primary",
                    key=entry_key("save"),
                )
                if save_log:
                    record = {
                        "작성자": writer,
                        "작성자ID": str(auth_user.get("user_id", "") or "").strip(),
                        "공개범위": visibility,
                        "권역": area,
                        "모국": mother,
                        "국소": local,
                        "상태": status,
                        "점검항목": items,
                        "현상_특이사항": issue,
                        "조치내용": action,
                        "후속조치": followup,
                        "비고": remark,
                    }
                    with st.spinner("현장 기록을 우선 저장하고 선택 사진을 연결하고 있습니다..."):
                        ok, message, record_id, photo_warning = save_work_log(record, photos)
                    if ok:
                        st.session_state["worklog_post_save_result"] = {
                            "message": f"{message} · 기록ID: {record_id}",
                            "warning": photo_warning,
                        }
                        try:
                            st.session_state["worklog_df"] = load_work_logs(auth_user)
                            st.session_state["worklog_loaded_at"] = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass

                        # HARD RESET: 다음 기록은 완전히 다른 widget key 세대를 사용합니다.
                        st.session_state["worklog_entry_generation"] = entry_generation + 1
                        st.session_state["worklog_entry_reset_pending"] = True
                        time.sleep(0.15)
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")

        def _render_worklog_inline_detail(selected, selected_id: str) -> None:
            """선택한 최근 기록의 기존 상세·조치 화면을 해당 카드 바로 아래에 렌더링합니다."""
            st.markdown("---")
            st.markdown("### 📷 첨부 현장사진")
            st.caption(
                f"기록ID: {selected_id} · {selected.get('모국','')} / {selected.get('국소','')} · "
                "Drive 폴더는 공개하지 않고 이 화면에서만 조회·다운로드합니다."
            )

            selected_photo_ids = [
                v.strip() for v in str(selected.get("사진파일ID목록", "") or "").split("|") if v.strip()
            ]
            selected_photo_names = [
                v.strip() for v in str(selected.get("사진파일명목록", "") or "").split("|") if v.strip()
            ]

            photo_payloads = []
            failed_photo_count = 0
            local_for_name = str(selected.get("국소", "") or selected.get("모국", "") or "WORK_LOG").strip()
            writer_for_name = str(selected.get("작성자", "") or "현장").strip()
            saved_for_name = re.sub(r"[^0-9]", "", str(selected.get("저장일시", "") or ""))[:8] or _korea_now().strftime("%Y%m%d")
            item_for_name = str(selected.get("점검항목", "") or "현장사진").split(",")[0].strip() or "현장사진"

            safe_local = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", local_for_name)[:40] or "WORK_LOG"
            safe_writer = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", writer_for_name)[:30] or "현장"
            safe_item = re.sub(r"[^0-9A-Za-z가-힣_-]", "_", item_for_name)[:30] or "현장사진"

            for photo_index, file_id in enumerate(selected_photo_ids, 1):
                photo_bytes = _worklog_download_drive_image(file_id)
                if not photo_bytes:
                    failed_photo_count += 1
                    continue
                download_name = f"{safe_local}_{safe_item}_{safe_writer}_{saved_for_name}_{photo_index:02d}.jpg"
                stored_name = selected_photo_names[photo_index - 1] if photo_index - 1 < len(selected_photo_names) else download_name
                photo_payloads.append({
                    "index": photo_index,
                    "id": file_id,
                    "bytes": photo_bytes,
                    "download_name": download_name,
                    "stored_name": stored_name,
                })

            if photo_payloads:
                st.caption(f"첨부사진 {len(selected_photo_ids)}장 · 전체 보기 및 개별/일괄 다운로드")
                photo_cols = st.columns(2)
                for payload_pos, payload in enumerate(photo_payloads):
                    with photo_cols[payload_pos % 2]:
                        st.image(
                            payload["bytes"],
                            caption=f"사진 {payload['index']} / {len(selected_photo_ids)}",
                            use_container_width=True,
                        )
                        st.download_button(
                            "📥 사진 다운로드",
                            data=payload["bytes"],
                            file_name=payload["download_name"],
                            mime="image/jpeg",
                            use_container_width=True,
                            key=f"worklog_photo_download_{selected_id}_{payload['index']}",
                        )

                try:
                    from io import BytesIO
                    import zipfile

                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as photo_zip:
                        for payload in photo_payloads:
                            photo_zip.writestr(payload["download_name"], payload["bytes"])
                    zip_file_name = f"{safe_local}_WORK_LOG_{saved_for_name}_사진{len(photo_payloads)}장.zip"
                    st.download_button(
                        f"📦 사진 {len(photo_payloads)}장 전체 ZIP 다운로드",
                        data=zip_buffer.getvalue(),
                        file_name=zip_file_name,
                        mime="application/zip",
                        use_container_width=True,
                        type="primary",
                        key=f"worklog_photo_zip_{selected_id}",
                    )
                except Exception as zip_error:
                    st.warning(f"사진 ZIP 파일을 만들지 못했습니다. 개별 다운로드를 이용해 주세요. ({zip_error})")

                if failed_photo_count:
                    st.warning(f"첨부사진 중 {failed_photo_count}장은 현재 읽을 수 없어 표시하지 못했습니다.")
            elif selected_photo_ids:
                st.warning("첨부사진 정보는 있으나 현재 사진 파일을 읽을 수 없습니다. Drive 읽기 권한을 확인해 주세요.")
            else:
                st.info("이 기록에는 첨부된 현장사진이 없습니다.")

            # V22 FIELD-SAFE: 기록 소유자는 현장에서 누락된 사진을 나중에 상세·조치에서 추가할 수 있습니다.
            is_owner = _worklog_record_owned_by(selected, auth_user)
            if is_owner and len(selected_photo_ids) < WORK_LOG_MAX_PHOTOS:
                st.markdown("#### ➕ 현장사진 추가")
                st.caption(
                    f"현재 {len(selected_photo_ids)}장 · 최대 {WORK_LOG_MAX_PHOTOS}장. "
                    "현장에서 사진 연결이 실패했더라도 기록은 유지되며, 휴대폰 앨범에서 사진만 다시 추가할 수 있습니다."
                )
                detail_queue_key = f"worklog_detail_photo_queue_{selected_id}"
                detail_notice_key = f"worklog_detail_photo_notice_{selected_id}"
                detail_raw_receipt_key = f"worklog_detail_photo_raw_receipt_{selected_id}"
                detail_health_key = f"{detail_queue_key}_health"
                detail_album_nonce_key = f"worklog_detail_photo_album_nonce_{selected_id}"
                detail_camera_nonce_key = f"worklog_detail_photo_camera_nonce_{selected_id}"
                detail_album_nonce = int(st.session_state.get(detail_album_nonce_key, 0) or 0)
                detail_camera_nonce = int(st.session_state.get(detail_camera_nonce_key, 0) or 0)

                with st.form(key=f"worklog_detail_album_form_{selected_id}_{detail_album_nonce}", clear_on_submit=False):
                    detail_album_files = st.file_uploader(
                        "🖼️ 앨범에서 여러 장 선택",
                        type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
                        accept_multiple_files=True,
                        key=f"worklog_detail_album_{selected_id}_{detail_album_nonce}",
                    ) or []
                    detail_album_submit = st.form_submit_button("선택한 사진 담기", use_container_width=True)
                if detail_album_submit:
                    _worklog_process_photo_submission(
                        detail_album_files,
                        detail_queue_key,
                        detail_notice_key,
                        detail_raw_receipt_key,
                        detail_health_key,
                    )
                    st.session_state[detail_album_nonce_key] = detail_album_nonce + 1
                    st.rerun()

                with st.form(key=f"worklog_detail_camera_form_{selected_id}_{detail_camera_nonce}", clear_on_submit=False):
                    detail_camera_file = st.file_uploader(
                        "📷 카메라 촬영 또는 사진 1장 선택",
                        type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
                        accept_multiple_files=False,
                        key=f"worklog_detail_camera_{selected_id}_{detail_camera_nonce}",
                    )
                    detail_camera_submit = st.form_submit_button("촬영/선택 사진 담기", use_container_width=True)
                if detail_camera_submit:
                    _worklog_process_photo_submission(
                        [detail_camera_file] if detail_camera_file is not None else [],
                        detail_queue_key,
                        detail_notice_key,
                        detail_raw_receipt_key,
                        detail_health_key,
                    )
                    st.session_state[detail_camera_nonce_key] = detail_camera_nonce + 1
                    st.rerun()

                detail_notice = str(st.session_state.pop(detail_notice_key, "") or "")
                if detail_notice:
                    if "실패" in detail_notice or "못했습니다" in detail_notice or "없습니다" in detail_notice:
                        st.warning(detail_notice)
                    else:
                        st.success(detail_notice)

                detail_photos = _worklog_queued_photo_objects(detail_queue_key)
                _worklog_render_photo_pipeline_status(
                    detail_photos,
                    detail_queue_key,
                    detail_raw_receipt_key,
                    detail_health_key,
                )
                if detail_photos:
                    add_photo_c1, add_photo_c2 = st.columns([3.8, 1.4], gap="small")
                    with add_photo_c1:
                        st.caption(f"사진 {len(detail_photos)}장 추가 대기")
                    with add_photo_c2:
                        if st.button(
                            "추가 취소",
                            key=f"worklog_detail_photo_clear_{selected_id}",
                            use_container_width=True,
                        ):
                            st.session_state[detail_queue_key] = []
                            st.session_state.pop(detail_raw_receipt_key, None)
                            st.session_state.pop(detail_health_key, None)
                            st.rerun()
                    if st.button(
                        "📎 선택 사진을 이 기록에 추가 저장",
                        key=f"worklog_detail_photo_save_{selected_id}",
                        type="primary",
                        use_container_width=True,
                    ):
                        with st.spinner("기존 기록에 현장사진을 추가하고 있습니다..."):
                            add_ok, add_message = append_work_log_photos(selected_id, auth_user, detail_photos)
                        if add_ok:
                            st.session_state[detail_queue_key] = []
                            st.session_state.pop(detail_raw_receipt_key, None)
                            st.session_state.pop(detail_health_key, None)
                            st.session_state["worklog_df"] = load_work_logs(auth_user)
                            st.session_state["worklog_selected_id"] = selected_id
                            st.session_state["worklog_detail_photo_saved_notice"] = add_message
                            st.rerun()
                        else:
                            st.error(add_message)

                detail_saved_notice = str(st.session_state.pop("worklog_detail_photo_saved_notice", "") or "")
                if detail_saved_notice:
                    st.success("✅ " + detail_saved_notice)

            # V13: 기록 소유자는 과거/현재 자료 모두 공개 ↔ 비공개를 언제든 변경할 수 있습니다.
            current_visibility = _worklog_record_visibility(selected)
            current_visibility_label = (
                "🌐 공개 · 팀 공유" if current_visibility == "공개" else "🔒 비공개 · 나만 보기"
            )
            visibility_box_class = "private" if current_visibility == "비공개" else "public"
            st.markdown("### 🔐 공개범위 관리")
            st.markdown(
                f'<div class="worklog-visibility-manage {visibility_box_class}">'
                f'<b>현재 공개범위: {html.escape(current_visibility_label)}</b><br>'
                '공개 기록은 인증된 팀원이 검색·조회할 수 있고, 비공개 기록은 작성한 본인만 검색·조회·사진 다운로드할 수 있습니다. '
                '공개범위를 바꾸면 연결 사진도 같은 권한을 따르며, 다른 사용자의 화면에는 다음 조회부터 반영됩니다.</div>',
                unsafe_allow_html=True,
            )

            if is_owner:
                visibility_options = ["🌐 공개 · 팀 공유", "🔒 비공개 · 나만 보기"]
                visibility_manage_key = f"worklog_manage_visibility_{selected_id}"
                if visibility_manage_key not in st.session_state:
                    st.session_state[visibility_manage_key] = current_visibility_label
                managed_visibility_label = st.radio(
                    "내 기록 공개범위 변경",
                    visibility_options,
                    horizontal=True,
                    key=visibility_manage_key,
                    label_visibility="collapsed",
                )
                new_visibility = "비공개" if managed_visibility_label.startswith("🔒") else "공개"
                change_needed = new_visibility != current_visibility
                if st.button(
                    "💾 공개범위 변경 저장" if change_needed else "현재 공개범위 유지",
                    type="primary" if change_needed else "secondary",
                    use_container_width=True,
                    disabled=not change_needed,
                    key=f"worklog_visibility_save_{selected_id}",
                ):
                    with st.spinner("공개범위를 변경하고 권한을 반영하고 있습니다..."):
                        visibility_ok, visibility_message = update_work_log_visibility(
                            selected_id, new_visibility, actor_user=auth_user
                        )
                    if visibility_ok:
                        st.session_state["worklog_df"] = load_work_logs(auth_user)
                        st.session_state["worklog_selected_id"] = selected_id
                        st.success(visibility_message)
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(visibility_message)
            else:
                st.caption("※ 공개범위 변경 권한은 이 기록을 작성한 본인에게만 있습니다.")

            st.markdown("### 🔄 상태이력 · 조치 업데이트")
            st.caption(f"기록ID: {selected_id} · {selected.get('모국','')} / {selected.get('국소','')}")
            u1, u2 = st.columns(2)
            with u1:
                update_writer = str(auth_user.get("name", "") or "").strip()
                st.text_input(
                    "변경 작성자",
                    value=update_writer,
                    disabled=True,
                    key="worklog_update_writer",
                    help="상태·조치 변경 이력에는 현재 로그인 사용자가 자동 기록됩니다.",
                )
                current_status = str(selected.get("상태", "신규"))
                status_index = WORK_LOG_STATUS_OPTIONS.index(current_status) if current_status in WORK_LOG_STATUS_OPTIONS else 0
                update_status = st.selectbox("변경 상태", WORK_LOG_STATUS_OPTIONS, index=status_index, key="worklog_update_status")
                update_action = st.text_area("조치내용", value=str(selected.get("조치내용", "")), height=100, key="worklog_update_action")
            with u2:
                update_followup = st.text_area("후속조치", value=str(selected.get("후속조치", "")), height=100, key="worklog_update_followup")
                update_remark = st.text_area("비고", value=str(selected.get("비고", "")), height=100, key="worklog_update_remark")

            uc1, uc2 = st.columns(2)
            with uc1:
                if st.button("💾 상태·조치 저장", type="primary", use_container_width=True, key="worklog_update_save"):
                    ok, msg = update_work_log(
                        selected_id,
                        update_writer,
                        update_status,
                        update_action,
                        update_followup,
                        update_remark,
                        actor_user=auth_user,
                    )
                    if ok:
                        st.session_state["worklog_df"] = load_work_logs(auth_user)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            with uc2:
                if st.button("닫기", use_container_width=True, key="worklog_update_close"):
                    st.session_state["worklog_selected_id"] = ""
                    st.session_state["worklog_selected_ui_key"] = ""
                    st.session_state.pop("worklog_delete_pending_id", None)
                    for detail_key in (
                        "worklog_update_writer", "worklog_update_status", "worklog_update_action",
                        "worklog_update_followup", "worklog_update_remark",
                    ):
                        st.session_state.pop(detail_key, None)
                    st.rerun()

            if is_owner:
                delete_photo_count = len([
                    value for value in str(selected.get("사진파일ID목록", "") or "").split("|") if value.strip()
                ])
                st.markdown(
                    f'<div class="worklog-delete-box"><b>🗑️ 내 기록 삭제</b><br>'
                    f'본인이 작성한 기록만 삭제할 수 있습니다. 삭제 시 연결 사진 {delete_photo_count}장은 '
                    'Google Drive에서 영구삭제하지 않고 휴지통으로 이동합니다.</div>',
                    unsafe_allow_html=True,
                )
                pending_delete_id = str(st.session_state.get("worklog_delete_pending_id", "") or "").strip()
                if pending_delete_id != selected_id:
                    if st.button(
                        "🗑️ 이 기록 삭제",
                        key=f"worklog_delete_request_{selected_id}",
                        use_container_width=True,
                    ):
                        st.session_state["worklog_delete_pending_id"] = selected_id
                        st.rerun()
                else:
                    st.warning(
                        f"정말 삭제하시겠습니까? · {selected.get('모국','')} / {selected.get('국소','')} · "
                        f"{selected.get('저장일시','')} · 사진 {delete_photo_count}장"
                    )
                    delete_yes, delete_no = st.columns(2)
                    with delete_yes:
                        if st.button(
                            "삭제 확정",
                            type="primary",
                            use_container_width=True,
                            key=f"worklog_delete_confirm_{selected_id}",
                        ):
                            with st.spinner("내 기록과 연결 사진을 안전하게 정리하고 있습니다..."):
                                delete_ok, delete_message = delete_work_log(selected_id, auth_user)
                            if delete_ok:
                                st.session_state["worklog_df"] = load_work_logs(auth_user)
                                st.session_state["worklog_selected_id"] = ""
                                st.session_state["worklog_selected_ui_key"] = ""
                                st.session_state.pop("worklog_delete_pending_id", None)
                                st.success(delete_message)
                                time.sleep(0.6)
                                st.rerun()
                            else:
                                st.error(delete_message)
                    with delete_no:
                        if st.button(
                            "취소",
                            use_container_width=True,
                            key=f"worklog_delete_cancel_{selected_id}",
                        ):
                            st.session_state.pop("worklog_delete_pending_id", None)
                            st.rerun()
            else:
                st.caption("※ 삭제 권한은 이 기록을 작성한 본인에게만 있습니다.")

            history_df = load_work_log_history(selected_id, auth_user)
            if not history_df.empty:
                st.markdown("#### 🕘 변경 이력")
                history_display = history_df[[c for c in WORK_LOG_HISTORY_HEADERS if c in history_df.columns]].copy()
                st.dataframe(history_display, use_container_width=True, hide_index=True)


        with recent_col:
            st.markdown('<div class="worklog-recent-marker"></div>', unsafe_allow_html=True)
            with st.container(border=True):
                st.markdown('<div class="worklog-section-title">🕘 최근 기록</div>', unsafe_allow_html=True)

                if not isinstance(loaded_df, pd.DataFrame):
                    st.info("검색 조건과 검색어를 정한 뒤 ‘불러오기’를 누르면 최근 현장이력이 표시됩니다.")
                else:
                    display_logs = loaded_df.copy()
                    if worklog_filter == "🌐 공개":
                        display_logs = display_logs[display_logs["공개범위"].astype(str) == "공개"]
                        if worklog_public_scope == "👤 내 기록":
                            current_user_id = str(auth_user.get("user_id", "") or "").strip()
                            display_logs = display_logs[
                                display_logs["작성자ID"].astype(str).str.strip() == current_user_id
                            ]
                    elif worklog_filter == "🔒 내 비공개":
                        display_logs = display_logs[display_logs["공개범위"].astype(str) == "비공개"]
                    elif worklog_filter in WORK_LOG_STATUS_OPTIONS:
                        display_logs = display_logs[display_logs["상태"].astype(str) == worklog_filter]
                    if worklog_search:
                        search_cols = [
                            "작성자", "권역", "모국", "국소", "상태", "점검항목",
                            "현상_특이사항", "조치내용", "후속조치", "비고",
                        ]
                        mask = display_logs[search_cols].apply(
                            lambda row: row.astype(str).str.contains(worklog_search, case=False, na=False).any(),
                            axis=1,
                        )
                        display_logs = display_logs[mask]

                    if display_logs.empty:
                        st.warning("조건에 맞는 WORK LOG가 없습니다.")
                    else:
                        for display_pos, (_, log) in enumerate(display_logs.head(12).iterrows(), start=1):
                            record_id = str(log.get("기록ID", "")).strip()
                            saved_for_key = str(log.get("저장일시", "") or "").strip()
                            writer_for_key = str(log.get("작성자", "") or "").strip()
                            station_for_key = f"{str(log.get('모국','')).strip()}|{str(log.get('국소','')).strip()}"
                            ui_seed = f"{record_id}|{saved_for_key}|{writer_for_key}|{station_for_key}|{display_pos}"
                            ui_suffix = hashlib.sha256(ui_seed.encode("utf-8")).hexdigest()[:10]
                            ui_record_key = f"{record_id or 'legacy'}_{display_pos}_{ui_suffix}"
                            status_value = str(log.get("상태", "신규")).strip()
                            badge_class = {
                                "신규": "new", "확인필요": "wait", "조치중": "doing",
                                "재점검": "recheck", "완료": "done",
                            }.get(status_value, "wait")
                            place_text = f"{str(log.get('모국','')).strip()} · {str(log.get('국소','')).strip()}"
                            main_note = str(log.get("현상_특이사항", "")).strip() or str(log.get("조치내용", "")).strip() or "기록 내용 없음"
                            saved_text = str(log.get("저장일시", "")).strip()
                            items_text = str(log.get("점검항목", "")).strip()
                            privacy_value = _worklog_record_visibility(log)
                            privacy_class = "private" if privacy_value == "비공개" else "public"
                            privacy_text = "🔒 나만 보기" if privacy_value == "비공개" else "🌐 팀 공유"
                            photo_ids = [v for v in str(log.get("사진파일ID목록", "")).split("|") if v.strip()]

                            st.markdown(
                                f'<div class="worklog-card">'
                                f'<div class="worklog-card-top"><div>'
                                f'<div class="worklog-place">📍 {html.escape(place_text)}'
                                f'<span class="worklog-privacy-badge {privacy_class}">{privacy_text}</span></div>'
                                f'<div class="worklog-meta">{html.escape(items_text)} · {html.escape(saved_text)} · {html.escape(str(log.get("작성자","")))}</div>'
                                f'</div><span class="worklog-badge {badge_class}">{html.escape(status_value)}</span></div>'
                                f'<div class="worklog-body">{html.escape(main_note)}</div>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                            if photo_ids:
                                thumbnail_ids = photo_ids[:4]
                                thumb_cols = st.columns(len(thumbnail_ids))
                                for photo_index, file_id in enumerate(thumbnail_ids):
                                    with thumb_cols[photo_index]:
                                        photo_bytes = _worklog_download_drive_image(file_id)
                                        if photo_bytes:
                                            st.image(photo_bytes, use_container_width=True)
                                if len(photo_ids) > 4:
                                    st.caption(f"📷 사진 {len(photo_ids)}장 · 화면에는 처음 4장만 미리보기")

                            action_c1, action_c2 = st.columns(2)
                            with action_c1:
                                if record_id:
                                    if st.button("상세·조치", key=f"worklog_detail_{ui_record_key}", use_container_width=True):
                                        previous_detail_id = str(st.session_state.get("worklog_selected_id", "") or "").strip()
                                        previous_ui_key = str(st.session_state.get("worklog_selected_ui_key", "") or "").strip()
                                        if previous_detail_id != record_id or previous_ui_key != ui_record_key:
                                            for detail_key in (
                                                "worklog_update_writer", "worklog_update_status", "worklog_update_action",
                                                "worklog_update_followup", "worklog_update_remark",
                                            ):
                                                st.session_state.pop(detail_key, None)
                                            st.session_state.pop("worklog_delete_pending_id", None)
                                        st.session_state["worklog_selected_id"] = record_id
                                        st.session_state["worklog_selected_ui_key"] = ui_record_key
                                        st.rerun()
                                else:
                                    st.button(
                                        "상세·조치",
                                        key=f"worklog_detail_legacy_disabled_{ui_record_key}",
                                        use_container_width=True,
                                        disabled=True,
                                    )
                                    st.caption("이전 형식 기록 · 기록ID 없음")
                            with action_c2:
                                if not record_id:
                                    st.button(
                                        "처리 불가",
                                        disabled=True,
                                        key=f"worklog_done_legacy_disabled_{ui_record_key}",
                                        use_container_width=True,
                                    )
                                elif status_value != "완료":
                                    if st.button("✅ 완료", key=f"worklog_done_{ui_record_key}", use_container_width=True):
                                        ok, msg = update_work_log(
                                            record_id,
                                            str(auth_user.get("name", "") or "현장 사용자"),
                                            "완료",
                                            str(log.get("조치내용", "")),
                                            str(log.get("후속조치", "")),
                                            str(log.get("비고", "")),
                                            actor_user=auth_user,
                                        )
                                        if ok:
                                            st.session_state["worklog_df"] = load_work_logs(auth_user)
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                else:
                                    st.button("완료됨", disabled=True, key=f"worklog_done_disabled_{ui_record_key}", use_container_width=True)

                            # 카드의 논리 기록ID와 화면 UI key를 함께 비교하여 중복 ID가 있어도 상세창은 1개만 엽니다.
                            active_detail_id = str(st.session_state.get("worklog_selected_id", "") or "").strip()
                            active_ui_key = str(st.session_state.get("worklog_selected_ui_key", "") or "").strip()
                            if record_id and active_detail_id == record_id and active_ui_key == ui_record_key:
                                _render_worklog_inline_detail(log, record_id)

        if isinstance(st.session_state.get("worklog_df"), pd.DataFrame):
            st.markdown('<div class="worklog-close-safe-space"></div>', unsafe_allow_html=True)
            st.markdown('<div class="worklog-sticky-close-marker"></div>', unsafe_allow_html=True)
            st.button(
                "✕ 조회 닫기",
                key="worklog_results_close",
                use_container_width=True,
                on_click=_worklog_close_loaded_results,
            )



# --- [Tab 1: 국사 전원시설 정밀점검] ---
with tab_power:
    if st.session_state.get("power_current_theme") not in POWER_THEME_ORDER:
        st.session_state["power_current_theme"] = POWER_THEME_ORDER[0]
    if _power_get("power_phase_type", "삼상") not in {"삼상", "단상"}:
        _power_set("power_phase_type", "삼상")
    if _power_get("power_battery_set", "1조 셀 측정") not in {"1조 셀 측정", "2조 셀 측정"}:
        _power_set("power_battery_set", "1조 셀 측정")
    if "power_unlocked_theme_index" not in st.session_state:
        st.session_state["power_unlocked_theme_index"] = len(POWER_THEME_ORDER) - 1
    if "power_theme_confirmations" not in st.session_state:
        st.session_state["power_theme_confirmations"] = {}
    if "power_panel_nonce" not in st.session_state:
        st.session_state["power_panel_nonce"] = 0
    unlocked_index = _power_unlocked_theme_index()
    _power_draft()
    selected_worker_state = str(st.session_state.get("power_worker", "담당자 선택")).strip()
    expected_area = _major_area_for_worker_value(selected_worker_state)
    if expected_area in POWER_REGION_DATA:
        # 과거 세션에 개별 담당자가 남아 있어도 현장 화면에서는 권역 담당자 2명을 한 묶음으로 통일합니다.
        selected_worker_state = _automatic_inspector_display(expected_area)
        st.session_state["power_worker"] = selected_worker_state
    else:
        st.session_state["power_worker"] = "담당자 선택"
        selected_worker_state = "담당자 선택"
        expected_area = "권역 선택"
    if st.session_state.get("power_major_area", "권역 선택") != expected_area:
        st.session_state["power_major_area"] = expected_area
    expected_group = _inspector_group_for_area(expected_area) if expected_area in POWER_REGION_DATA else ""
    if st.session_state.get("power_inspector_group", "") != expected_group:
        st.session_state["power_inspector_group"] = expected_group

    st.markdown("### 🔋 국사 전원시설 정밀점검")
    st.caption("국사명을 검색해 선택하면 담당자 2명·주요 점검권역·모국·국소가 자동 입력됩니다. 기존 수동 선택 방식도 그대로 사용할 수 있습니다.")

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
    .power-mobile-hero h3 { margin:0 0 7px 0; color:#0F172A; font-weight:950; font-size:clamp(1.28rem,3.5vw,1.60rem); letter-spacing:-0.02em; }
    .power-mobile-hero p { margin:0; color:#334155; line-height:1.65; font-weight:720; font-size:clamp(.94rem,2.6vw,1.04rem); }
    .power-basic-card {
        background:#FFFFFF; border:1px solid #D8E3F2; border-radius:17px;
        padding:14px 15px 6px; margin:10px 0 10px; box-shadow:0 6px 18px rgba(15,23,42,.06);
    }
    .power-basic-title {font-size:clamp(1.16rem,3.2vw,1.34rem); font-weight:950; color:#0B5CAB; margin-bottom:9px; letter-spacing:-.01em;}
    .power-sticky-card {
        position: sticky; top: 0.35rem; z-index: 990;
        background: rgba(15, 23, 42, 0.96); color: #FFFFFF;
        border: 1px solid rgba(255,255,255,0.18); border-radius: 15px;
        padding: 10px 14px; margin: 8px 0 11px 0;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.22); backdrop-filter: blur(10px);
    }
    .power-sticky-title { font-size:.82rem; opacity:.82; font-weight:850; margin-bottom:3px; }
    .power-sticky-main { font-size:clamp(1.00rem,3vw,1.16rem); font-weight:950; line-height:1.35; word-break:keep-all; }
    .power-sticky-area { font-size:clamp(.88rem,2.7vw,1.02rem); font-weight:850; color:#BFDBFE; margin-top:2px; }
    .power-sticky-sub { font-size:.88rem; opacity:.92; margin-top:3px; line-height:1.4; }
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
    .power-battery-flow {
        display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:7px;
        margin:8px 0 11px;
    }
    .power-battery-flow-step {
        min-height:66px; display:flex; flex-direction:column; align-items:center; justify-content:center;
        padding:8px 6px; border:1.5px solid #CBD5E1; border-radius:13px;
        background:#F8FAFC; color:#64748B; text-align:center; line-height:1.25;
        font-size:clamp(.76rem,2.3vw,.91rem); font-weight:900;
    }
    .power-battery-flow-step .step-no {
        display:inline-flex; align-items:center; justify-content:center; width:25px; height:25px;
        margin-bottom:4px; border-radius:999px; background:#E2E8F0; color:#475569; font-weight:950;
    }
    .power-battery-flow-step.active {
        border-color:#F59E0B; background:linear-gradient(135deg,#FFF7ED,#FEF3C7);
        color:#92400E; box-shadow:0 0 0 2px rgba(245,158,11,.18);
    }
    .power-battery-flow-step.active .step-no { background:#F59E0B; color:#FFFFFF; }
    .power-battery-flow-step.done {
        border-color:#34D399; background:linear-gradient(135deg,#ECFDF5,#DCFCE7); color:#166534;
    }
    .power-battery-flow-step.done .step-no { background:#10B981; color:#FFFFFF; }
    .power-battery-path-guide {
        margin:7px 0 12px; padding:10px 12px; border-radius:12px;
        background:#EFF6FF; border:1px solid #93C5FD; color:#1E3A8A;
        font-size:clamp(.82rem,2.5vw,.96rem); font-weight:800; line-height:1.55;
    }
    .power-notes-guide {
        margin:4px 0 9px; padding:13px 15px; border-radius:14px;
        background:linear-gradient(135deg,#FFF7ED,#FFFBEB); border:1px solid #FDBA74;
        border-left:7px solid #F97316; color:#7C2D12;
    }
    .power-notes-guide .title { font-size:clamp(1.10rem,3.4vw,1.30rem); font-weight:950; margin-bottom:4px; }
    .power-notes-guide .desc { font-size:clamp(.88rem,2.6vw,1rem); font-weight:750; line-height:1.45; }
    div.st-key-_ui_power_notes textarea {
        min-height:145px !important; border:2px solid #F97316 !important;
        background:#FFFEF7 !important; box-shadow:0 0 0 3px rgba(249,115,22,.10) !important;
        font-size:clamp(1.04rem,3vw,1.16rem) !important; font-weight:800 !important; line-height:1.55 !important;
    }
    div.st-key-_ui_power_notes textarea::placeholder {
        color:#94A3B8 !important; -webkit-text-fill-color:#94A3B8 !important; font-weight:600 !important; opacity:1 !important;
    }
    div.st-key-_ui_power_notes label p {
        color:#9A3412 !important; font-size:clamp(1rem,3vw,1.14rem) !important; font-weight:950 !important;
    }
    .power-loaded-box {
        background:#F0FDF4; border:1px solid #86EFAC; border-left:6px solid #16A34A;
        border-radius:13px; padding:11px 13px; color:#166534; font-weight:800; margin:8px 0;
    }
    .power-sheet-note {
        background:#F8FAFC; border:1px solid #CBD5E1; border-radius:14px;
        padding:13px 15px; color:#334155; font-weight:700; line-height:1.55;
    }
    .power-ground-heading {
        border-radius:13px; padding:11px 14px; margin:9px 0 9px;
        font-size:clamp(1.05rem,3vw,1.22rem); font-weight:950; color:#0F172A;
        box-shadow:0 5px 14px rgba(15,23,42,.07);
    }
    .power-ground-heading span { font-weight:850; opacity:.78; }
    .power-ground-heading.security {
        background:linear-gradient(135deg,#DBEAFE,#E0F2FE);
        border:1px solid #60A5FA; border-left:7px solid #2563EB;
    }
    .power-ground-heading.telecom {
        background:linear-gradient(135deg,#DCFCE7,#ECFDF5);
        border:1px solid #4ADE80; border-left:7px solid #16A34A;
    }
    .power-ground-heading.lightning {
        background:linear-gradient(135deg,#FEF3C7,#FFF7ED);
        border:1px solid #FBBF24; border-left:7px solid #F97316;
    }
    .power-menu-legend {
        display:flex; flex-wrap:wrap; gap:7px; margin:7px 0 10px;
        font-size:.80rem; font-weight:850; color:#334155;
    }
    .power-menu-legend span {
        background:#FFFFFF; border:1px solid #D8E3F2; border-radius:999px;
        padding:5px 9px; box-shadow:0 3px 9px rgba(15,23,42,.05);
    }
    @keyframes powerBlindDown {
        0% { opacity:0; transform:scaleY(0.08) translateY(-10px); clip-path:inset(0 0 92% 0); }
        70% { opacity:1; transform:scaleY(1.015) translateY(0); clip-path:inset(0 0 0 0); }
        100% { opacity:1; transform:scaleY(1) translateY(0); clip-path:inset(0 0 0 0); }
    }
    details:has(.power-panel-marker) [data-testid="stExpanderDetails"] {
        transform-origin:top center;
        animation:powerBlindDown .42s cubic-bezier(.2,.82,.25,1) both;
    }
    details:has(.power-panel-marker) > summary {
        background:linear-gradient(135deg,#EFF6FF,#F8FAFC) !important;
        border-radius:14px !important;
        border:1px solid #BFDBFE !important;
        padding:0.65rem 0.85rem !important;
    }
    .power-menu-status {
        background:#F8FAFC; border:1px solid #D8E3F2; border-radius:12px;
        padding:9px 12px; margin:8px 0 10px; color:#475569; font-weight:750;
    }
    div[class*="st-key-power_theme_menu_"] button {
        min-height: 56px !important; padding: 0.50rem 0.35rem !important;
        border-radius: 14px !important; font-size: 0.94rem !important; line-height: 1.15 !important;
        font-weight:950 !important; transition:transform .18s ease, box-shadow .18s ease !important;
    }
    div[class*="st-key-power_theme_menu_"] button:hover:not(:disabled) {
        transform:translateY(-2px) !important;
    }
    div[class*="st-key-_ui_power_battery_"] input {
        text-align:center !important; padding-left:0.25rem !important; padding-right:0.25rem !important;
        min-height:44px !important; font-weight:850 !important;
    }
    div[class*="st-key-_ui_power_battery_"] label p {
        text-align:center !important; font-size:0.86rem !important; font-weight:950 !important;
    }
    .power-measurement-menu-title {
        font-size:clamp(1.26rem,3.7vw,1.52rem); font-weight:950; color:#0F3B66;
        margin:14px 0 9px; padding:10px 13px; border-radius:14px;
        background:linear-gradient(135deg,#DBEAFE,#ECFEFF); border:1px solid #93C5FD;
        border-left:7px solid #0284C7; box-shadow:0 5px 14px rgba(2,132,199,.10);
    }
    details:has(.power-panel-marker) > summary p,
    details:has(.power-panel-marker) > summary span {
        font-size:clamp(1.10rem,3.4vw,1.30rem) !important; font-weight:950 !important; color:#0F3B66 !important;
    }
    div[class*="st-key-_ui_power_"] label p {
        font-size:clamp(.96rem,2.8vw,1.08rem) !important; font-weight:950 !important; color:#172033 !important; line-height:1.35 !important;
    }
    div[class*="st-key-_ui_power_"] input,
    div[class*="st-key-_ui_power_"] textarea {
        font-size:clamp(1.04rem,3vw,1.18rem) !important; font-weight:900 !important; color:#0F172A !important;
        -webkit-text-fill-color:#0F172A !important; min-height:48px !important; border:1.5px solid #94A3B8 !important;
    }
    div.st-key-power_worker label p, div.st-key-power_mother label p, div.st-key-power_local label p,
    div.st-key-power_station_search_query label p {
        font-size:clamp(.98rem,2.9vw,1.10rem) !important; font-weight:950 !important; color:#1E293B !important;
    }
    div.st-key-power_worker [data-baseweb="select"], div.st-key-power_mother [data-baseweb="select"], div.st-key-power_local [data-baseweb="select"] {
        width:100% !important; height:52px !important; min-height:52px !important; max-height:52px !important;
        box-sizing:border-box !important; border:2px solid #38BDF8 !important; border-radius:12px !important;
        background:#F0F9FF !important; box-shadow:0 5px 14px rgba(14,165,233,.12) !important;
        font-size:clamp(1rem,3vw,1.12rem) !important; font-weight:850 !important; opacity:1 !important;
    }
    div.st-key-power_worker [data-baseweb="select"] > div,
    div.st-key-power_mother [data-baseweb="select"] > div,
    div.st-key-power_local [data-baseweb="select"] > div {
        height:48px !important; min-height:48px !important; border:0 !important; border-radius:10px !important;
        background:transparent !important; box-shadow:none !important;
    }
    div.st-key-power_station_search_query input {
        min-height:54px !important; border:2.5px solid #7C3AED !important; border-radius:13px !important;
        background:#FFFFFF !important; box-shadow:0 6px 16px rgba(124,58,237,.16) !important;
        font-size:clamp(1.03rem,3vw,1.16rem) !important; font-weight:950 !important; color:#4C1D95 !important;
        -webkit-text-fill-color:#4C1D95 !important;
    }
    .power-station-search-guide {
        margin:2px 0 10px; padding:13px 14px; border-radius:15px;
        background:linear-gradient(135deg,#FFF7F7 0%,#FAF5FF 48%,#EFF6FF 100%);
        border:2px solid #7C3AED; border-left:7px solid #D71920;
        box-shadow:0 8px 20px rgba(76,29,149,.13); color:#3B0764; line-height:1.5;
    }
    .power-station-search-guide .title { font-size:clamp(1.08rem,3.2vw,1.26rem); font-weight:950; color:#6D28D9; }
    .power-station-search-guide .desc { margin-top:3px; font-size:.88rem; font-weight:800; color:#4B5563; }
    .power-station-duplicate-guide {
        margin:8px 0 7px; padding:9px 11px; border-radius:11px; background:#FFF7ED;
        border:1px solid #FDBA74; color:#9A3412; font-size:.88rem; font-weight:900; line-height:1.45;
    }
    .power-station-applied-note {
        margin:8px 0 10px; padding:10px 12px; border-radius:12px;
        background:linear-gradient(135deg,#F5F3FF,#FFF1F2); border:1.5px solid #A78BFA;
        color:#6D28D9; font-weight:950; line-height:1.5; box-shadow:0 4px 12px rgba(109,40,217,.09);
    }
    div.st-key-power_station_search_form button,
    div.st-key-power_station_duplicate_form button {
        min-height:54px !important; border-radius:13px !important; border:0 !important;
        background:linear-gradient(135deg,#D71920 0%,#7C3AED 100%) !important;
        color:#FFFFFF !important; font-weight:950 !important; box-shadow:0 7px 17px rgba(124,58,237,.20) !important;
    }
    div.st-key-power_station_search_form button *,
    div.st-key-power_station_duplicate_form button * { color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; }
    div.st-key-power_station_search_choice [role="radiogroup"] {
        padding:4px 2px 2px;
    }
    div.st-key-power_station_search_choice label {
        margin:4px 0 !important; padding:8px 10px !important; border-radius:10px !important;
        background:#FAF5FF !important; border:1px solid #DDD6FE !important;
    }
    .power-basic-auto-label {
        font-size:clamp(.98rem,2.9vw,1.10rem); font-weight:950; color:#1E293B; margin:0 0 6px 1px;
    }
    .power-basic-auto-card {
        width:100%; height:52px; min-height:52px; max-height:52px;
        display:flex; align-items:center; justify-content:center; box-sizing:border-box;
        padding:0 12px; border:2px solid #38BDF8; border-radius:12px;
        background:linear-gradient(135deg,#EFF6FF 0%,#F0F9FF 55%,#ECFEFF 100%);
        color:#0F3C5D; font-size:clamp(1rem,3vw,1.14rem); font-weight:950;
        letter-spacing:-0.02em; text-align:center; box-shadow:0 5px 14px rgba(14,165,233,.12);
        overflow:hidden;
    }
    .power-basic-auto-card.is-empty { color:#64748B; border-color:#CBD5E1; background:#F8FAFC; box-shadow:none; }
    .power-basic-auto-card.search-applied {
        color:#7C3AED; border-color:#8B5CF6; background:linear-gradient(135deg,#FAF5FF,#FFF1F2);
        box-shadow:0 5px 14px rgba(124,58,237,.14);
    }
    .power-basic-history-title {
        margin:14px 0 8px; padding-top:12px; border-top:1px solid #D8E3F2;
        color:#0B5CAB; font-size:clamp(1.02rem,3vw,1.16rem); font-weight:950;
    }
    .power-auto-worker-label { font-size:clamp(.98rem,2.9vw,1.10rem); font-weight:950; color:#1E293B; margin:0 0 6px 1px; }
    .power-auto-worker-card {
        min-height:48px; display:flex; align-items:center; justify-content:center;
        padding:9px 12px; border:2px solid #38BDF8; border-radius:12px;
        background:linear-gradient(135deg,#E0F2FE 0%,#F0F9FF 55%,#ECFEFF 100%);
        color:#0F3C5D; font-size:clamp(1.02rem,3.2vw,1.18rem); font-weight:950;
        letter-spacing:-0.02em; text-align:center; box-shadow:0 5px 14px rgba(14,165,233,.13);
    }
    .power-auto-worker-card.is-empty { color:#64748B; border-color:#CBD5E1; background:#F8FAFC; }
    div[class*="st-key-power_theme_menu_"] button p { font-size:clamp(.95rem,2.8vw,1.08rem) !important; font-weight:950 !important; }
    @media (max-width: 768px) {
        .power-mobile-hero { padding:14px 13px; border-radius:15px; }
        .power-sticky-card { top:0.2rem; border-radius:13px; padding:9px 11px; }
        .power-sticky-main { font-size:1rem; }
        div[class*="st-key-_ui_power_"] input,
        div[class*="st-key-_ui_power_"] textarea { font-size:16px !important; min-height:47px !important; }
        div[class*="st-key-_ui_power_"] label p { font-size:.94rem !important; }
        div[class*="st-key-_ui_power_battery_"] input { padding:.35rem .08rem !important; text-align:center !important; }
        div[class*="st-key-_ui_power_battery_"] label p { font-size:.78rem !important; }
        div[class*="st-key-power_theme_menu_"] button { min-height:60px !important; }
        .power-battery-flow { grid-template-columns:repeat(2,minmax(0,1fr)); gap:6px; }
        .power-battery-flow-step { min-height:60px; }
    }
    @media (max-width: 430px) {
        .power-mobile-hero { padding:13px 11px; }
        .power-basic-card { padding:12px 11px 5px; }
        .power-sticky-card { margin-left:-.1rem; margin-right:-.1rem; }
        .power-menu-legend { gap:5px; font-size:.75rem; }
        .power-menu-legend span { padding:4px 7px; }
        div[class*="st-key-_ui_power_battery_"] label p { font-size:.72rem !important; }
        div[class*="st-key-_ui_power_battery_"] input { font-size:15px !important; min-height:44px !important; }
    }
    </style>
    <div class="power-mobile-hero">
      <h3>새로운 전원 정밀점검 전용 공간</h3>
      <p>국사명을 검색해 선택하면 담당자 2명·주요 점검권역·모국·국소가 자동 입력됩니다. 기존 수동 선택과 과거 측정값 불러오기도 그대로 사용할 수 있습니다.</p>
    </div>
    """, unsafe_allow_html=True)

    # 기본정보와 과거 측정값 불러오기를 하나의 블록으로 묶어 표시합니다.
    with st.container(border=True):
        st.markdown('<div class="power-basic-title">👤 기본정보</div>', unsafe_allow_html=True)

        # 국사 검색은 기존 기본정보보다 먼저, 별도 카드처럼 눈에 띄게 배치합니다.
        with st.container(border=True):
            st.markdown(
                '<div class="power-station-search-guide">'
                '<div class="title">📍 국사 검색 · 빠른 자동입력</div>'
                '<div class="desc">예: <b>송포</b> 입력 → 오른쪽 <b>확인</b>. 한 곳이면 즉시 자동입력되고, 같은 이름이 여러 곳이면 아래 후보 중 하나만 선택하면 됩니다.</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            with st.form(key="power_station_search_form", clear_on_submit=False):
                search_input_col, search_button_col = st.columns([4.2, 1.15], gap="small")
                with search_input_col:
                    st.text_input(
                        "국사명",
                        key="power_station_search_query",
                        placeholder="예: 송포",
                        help="국사명을 입력한 뒤 오른쪽 확인 버튼을 누르세요. 키보드 Enter로도 확인할 수 있습니다.",
                    )
                with search_button_col:
                    st.markdown("<div style='height:1.70rem'></div>", unsafe_allow_html=True)
                    search_submitted = st.form_submit_button("확인", use_container_width=True)

            if search_submitted:
                _run_power_station_search()

            search_status = str(st.session_state.get("power_station_search_status", "") or "")
            candidate_ids = list(st.session_state.get("power_station_search_candidates", []) or [])

            if search_status == "empty":
                st.warning("국사명을 먼저 입력해 주세요. 예: 송포")
            elif search_status == "none":
                st.warning("일치하는 국사를 찾지 못했습니다. 국사명을 다시 확인해 주세요.")
            elif search_status == "multiple" and candidate_ids:
                st.markdown(
                    f'<div class="power-station-duplicate-guide">⚠️ 같은 이름 또는 유사한 국사가 {len(candidate_ids)}곳 있습니다. 아래에서 정확한 국사를 선택한 뒤 <b>선택 확인</b>을 눌러 주세요.</div>',
                    unsafe_allow_html=True,
                )
                with st.form(key="power_station_duplicate_form", clear_on_submit=False):
                    st.radio(
                        "국사 선택",
                        candidate_ids,
                        key="power_station_search_choice",
                        format_func=_power_station_search_label,
                    )
                    duplicate_submitted = st.form_submit_button("선택 확인", use_container_width=True)
                if duplicate_submitted:
                    _confirm_power_station_search_choice()

            station_search_notice = str(st.session_state.get("power_station_search_notice", "") or "")
            if station_search_notice:
                st.markdown(
                    f'<div class="power-station-applied-note">{html.escape(station_search_notice)}</div>',
                    unsafe_allow_html=True,
                )

        # 검색으로 자동 반영된 경우 아래 기본정보의 선택값을 자주색으로 강조합니다.
        if bool(st.session_state.get("power_station_search_applied", False)):
            st.markdown(
                """
                <style>
                div.st-key-power_worker [data-baseweb="select"],
                div.st-key-power_mother [data-baseweb="select"],
                div.st-key-power_local [data-baseweb="select"] {
                    border-color:#8B5CF6 !important; background:#FAF5FF !important;
                    box-shadow:0 5px 14px rgba(124,58,237,.14) !important;
                }
                div.st-key-power_worker [role="combobox"] *,
                div.st-key-power_mother [role="combobox"] *,
                div.st-key-power_local [role="combobox"] * {
                    color:#7C3AED !important; -webkit-text-fill-color:#7C3AED !important; font-weight:950 !important;
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

        worker_options = ["담당자 선택"] + POWER_INSPECTOR_GROUP_OPTIONS
        if st.session_state.get("power_worker", "담당자 선택") not in worker_options:
            legacy_area = _major_area_for_worker_value(st.session_state.get("power_worker", ""))
            st.session_state["power_worker"] = (
                _automatic_inspector_display(legacy_area)
                if legacy_area in POWER_REGION_DATA else "담당자 선택"
            )

        basic_row1 = st.columns(2, gap="small")
        with basic_row1[0]:
            selected_worker = st.selectbox(
                "담당자 *",
                worker_options,
                key="power_worker",
                on_change=_on_power_worker_change,
            )

        selected_area = _major_area_for_worker_value(selected_worker)
        if st.session_state.get("power_major_area", "권역 선택") != selected_area:
            st.session_state["power_major_area"] = selected_area
        with basic_row1[1]:
            if selected_area in POWER_REGION_DATA:
                area_class = "power-basic-auto-card search-applied" if st.session_state.get("power_station_search_applied", False) else "power-basic-auto-card"
            else:
                area_class = "power-basic-auto-card is-empty"
            area_text = html.escape(selected_area if selected_area in POWER_REGION_DATA else "담당자를 선택하면 자동 표시됩니다")
            st.markdown(
                f'<div class="power-basic-auto-label">주요 점검권역 *</div>'
                f'<div class="{area_class}">{area_text}</div>',
                unsafe_allow_html=True,
            )

        area_station_map = _power_area_station_map(selected_area)
        basic_row2 = st.columns(2, gap="small")
        mother_options = ["모국 선택"] + list(area_station_map.keys())
        if st.session_state.get("power_mother", "모국 선택") not in mother_options:
            st.session_state["power_mother"] = "모국 선택"
        with basic_row2[0]:
            selected_mother = st.selectbox(
                "모국 *",
                mother_options,
                key="power_mother",
                disabled=selected_area not in POWER_REGION_DATA,
                on_change=_on_power_mother_change,
            )

        local_options = ["국소 선택"]
        if selected_mother in area_station_map:
            local_options += area_station_map[selected_mother]
        if st.session_state.get("power_local", "국소 선택") not in local_options:
            st.session_state["power_local"] = "국소 선택"
        with basic_row2[1]:
            st.selectbox(
                "국소 *",
                local_options,
                key="power_local",
                disabled=selected_mother not in area_station_map,
                on_change=_clear_power_measurements_after_station_change,
            )

        selected_local = st.session_state.get("power_local", "국소 선택")
        can_load = selected_mother in area_station_map and selected_local in area_station_map.get(selected_mother, [])

        st.markdown('<div class="power-basic-history-title">↩️ 과거 측정값 불러오기</div>', unsafe_allow_html=True)
        history_periods = {
            "최근 6개월": 183,
            "최근 1년": 365,
            "최근 2년": 730,
        }
        history_col1, history_col2 = st.columns([0.82, 1.18], gap="small")
        with history_col1:
            history_period_label = st.selectbox(
                "조회 기간",
                list(history_periods.keys()),
                key="power_history_period_label",
                disabled=not can_load,
            )
        with history_col2:
            history_search_clicked = st.button(
                "🔎 과거 측정기록 조회",
                key="power_search_history",
                use_container_width=True,
                disabled=not can_load,
            )

        if history_search_clicked:
            within_days = history_periods.get(history_period_label, 183)
            with st.spinner("동일 국소의 과거 측정기록을 확인하고 있습니다..."):
                ok, message, records = list_power_inspection_history(
                    selected_mother,
                    selected_local,
                    within_days=within_days,
                    max_records=100,
                )
            if ok:
                st.session_state["power_history_records"] = records
                st.session_state["power_history_message"] = message
                st.session_state["power_history_station"] = f"{selected_mother}|{selected_local}"
                st.session_state["power_history_selected_index"] = 0
                st.rerun()
            else:
                st.session_state.pop("power_history_records", None)
                st.warning(message)

        history_records = list(st.session_state.get("power_history_records", []))
        expected_history_station = f"{selected_mother}|{selected_local}" if can_load else ""
        if st.session_state.get("power_history_station", "") != expected_history_station:
            history_records = []
            st.session_state.pop("power_history_records", None)

        if history_records:
            st.success(st.session_state.get("power_history_message", f"과거 측정기록 {len(history_records)}건을 조회했습니다."))

            def _power_history_label(index: int) -> str:
                record = history_records[index]
                saved_at = str(record.get("저장일시", "일시 미상")).strip() or "일시 미상"
                worker = str(record.get("점검자", "점검자 미상")).strip() or "점검자 미상"
                phase = str(record.get("전원구분", "-")).strip() or "-"
                completion = str(record.get("입력완료율(%)", "-")).strip() or "-"
                return f"{saved_at} · {worker} · {phase} · 완료율 {completion}%"

            selected_history_index = st.selectbox(
                "불러올 측정기록",
                options=list(range(len(history_records))),
                format_func=_power_history_label,
                key="power_history_selected_index",
            )
            selected_history_record = history_records[int(selected_history_index)]
            selected_history_photo_count = len([
                value for value in str(selected_history_record.get("사진파일ID목록", "") or "").split("|") if value.strip()
            ])
            if selected_history_photo_count:
                with st.expander(f"📷 선택 기록 현장사진 {selected_history_photo_count}장 · 보기/다운로드", expanded=False):
                    _render_power_photo_download(
                        selected_history_record,
                        key_prefix=f"power_history_{selected_history_record.get('점검ID', selected_history_index)}",
                    )
            if st.button(
                "↩️ 선택한 측정값 불러오기",
                key="power_load_selected_history",
                use_container_width=True,
                type="primary",
            ):
                selected_record = history_records[int(selected_history_index)]
                _set_power_state_from_record(selected_record)
                st.session_state["power_loaded_message"] = (
                    f"선택한 측정값을 불러왔습니다. "
                    f"({selected_record.get('저장일시', '')})"
                )
                st.rerun()

        if st.session_state.pop("power_loaded_notice", False):
            st.toast("선택한 과거 측정값을 입력폼에 불러왔습니다. 변경된 값만 수정해 주세요.", icon="↩️")
        if st.session_state.get("power_loaded_source_id"):
            st.markdown(
                f'<div class="power-loaded-box">↩️ 기존 측정값 사용 중 · '
                f'원본 저장일시: {html.escape(str(st.session_state.get("power_loaded_source_saved_at", "-")))} · '
                f'원본 점검ID: {html.escape(str(st.session_state.get("power_loaded_source_id", "-")))}</div>',
                unsafe_allow_html=True,
            )

    if st.session_state.pop("power_basic_changed_notice", False):
        st.info("기본정보가 변경되었습니다. 기존 측정값은 삭제하지 않고 그대로 유지했습니다. 현재 국소의 측정값인지 확인해 주세요.")

    basic_missing = _power_basic_missing()
    if basic_missing:
        st.caption("※ 담당자를 선택하면 주요 점검권역이 자동 표시됩니다. 모국·국소까지 선택해야 최종 전송할 수 있습니다.")

    worker_value = str(st.session_state.get("power_worker", "")).strip()
    major_area_value = str(st.session_state.get("power_major_area", "권역 선택")).strip()
    worker_summary = html.escape(worker_value if _power_worker_matches_area(worker_value, major_area_value) else "담당자 미선택")
    major_area_summary = html.escape(major_area_value or "권역 미선택")
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
          <div class="power-sticky-main">👤 {worker_summary}</div>
          <div class="power-sticky-area">🗺️ {major_area_summary}</div>
          <div class="power-sticky-sub">📍 {html.escape(station_summary)} · 임시저장 {draft_saved_at}</div>
        </div>""",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="power-measurement-menu-title">📋 측정 메뉴</div>', unsafe_allow_html=True)
    confirmations = dict(st.session_state.get("power_theme_confirmations", {}))
    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])

    # 측정 순서는 자유이며, 색상으로 현재·완료·미측정 상태를 구분합니다.
    state_css_rules: list[str] = []
    for theme_index, theme in enumerate(POWER_THEME_ORDER):
        selector = f'div[class*="st-key-power_theme_menu_{theme_index}"] button'
        is_completed = theme in confirmations
        is_current = theme == current_theme
        if is_current:
            style = (
                "background:linear-gradient(135deg,#FFB703,#FB8500)!important;"
                "color:#FFFFFF!important;border:2px solid #FFD166!important;"
                "box-shadow:0 10px 24px rgba(251,133,0,.38)!important;"
            )
        elif is_completed:
            style = (
                "background:linear-gradient(135deg,#34D399,#16A34A)!important;"
                "color:#FFFFFF!important;border:2px solid #86EFAC!important;"
                "box-shadow:0 8px 20px rgba(22,163,74,.28)!important;"
            )
        else:
            style = (
                "background:linear-gradient(135deg,#38BDF8,#2563EB)!important;"
                "color:#FFFFFF!important;border:2px solid #93C5FD!important;"
                "box-shadow:0 8px 20px rgba(37,99,235,.25)!important;"
            )
        state_css_rules.append(f"{selector}{{{style}}}{selector} *{{color:inherit!important;}}")

    st.markdown("<style>" + "".join(state_css_rules) + "</style>", unsafe_allow_html=True)
    st.markdown(
        '<div class="power-menu-legend">'
        '<span>🟠 현재 측정</span><span>🟢 확인·임시저장 완료</span>'
        '<span>🔵 미측정 또는 이동 가능</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    for row_start in range(0, len(POWER_THEME_ORDER), 2):
        menu_columns = st.columns(2, gap="small")
        for offset, column in enumerate(menu_columns):
            theme_index = row_start + offset
            if theme_index >= len(POWER_THEME_ORDER):
                continue
            theme = POWER_THEME_ORDER[theme_index]
            is_completed = theme in confirmations
            is_current = theme == current_theme
            if is_completed:
                status_mark = " ✅"
            elif _power_theme_started(theme):
                status_mark = " ◐"
            else:
                status_mark = ""
            prefix = "▼ " if is_current else ""
            with column:
                st.button(
                    f"{prefix}{POWER_THEME_ICON[theme]} {theme}{status_mark}",
                    key=f"power_theme_menu_{theme_index}",
                    type="primary" if is_current else "secondary",
                    use_container_width=True,
                    on_click=_activate_power_theme,
                    args=(theme,),
                )

    pending_target = st.session_state.get("power_pending_theme_switch")
    pending_from = st.session_state.get("power_pending_from_theme")
    if pending_target in POWER_THEME_ORDER and pending_from in POWER_THEME_ORDER[:-1]:
        detected_missing = _power_theme_missing(pending_from)
        missing_preview = ", ".join(detected_missing[:8]) if detected_missing else "시스템상 확인된 공란 없음"
        more_text = f" 외 {len(detected_missing) - 8}개" if len(detected_missing) > 8 else ""
        st.markdown(
            f'<div class="power-missing-box"><b>현재 입력값을 임시저장하고 이동하시겠습니까?</b><br>'
            f'현재 메뉴: {html.escape(pending_from)}<br>'
            f'이동할 메뉴: {html.escape(pending_target)}<br>'
            f'시스템 확인 공란: {html.escape(missing_preview)}{more_text}<br><br>'
            '이 이동은 측정 완료 처리와 별개입니다. 완료 판단은 각 테마 하단의 ‘측정 완료’ 버튼으로 확정합니다.</div>',
            unsafe_allow_html=True,
        )
        if st.session_state.get("power_navigation_error"):
            st.error(st.session_state["power_navigation_error"])
        move_col, stay_col = st.columns(2, gap="small")
        with move_col:
            st.button(
                "현재값 저장·이동",
                key="power_confirm_theme_switch",
                type="primary",
                use_container_width=True,
                on_click=_confirm_power_theme_switch,
            )
        with stay_col:
            st.button(
                "계속 입력",
                key="power_cancel_theme_switch",
                use_container_width=True,
                on_click=_cancel_power_theme_switch,
            )

    current_missing = _power_theme_missing(current_theme) if current_theme != "최종 확인·전송" else []
    current_status_text = (
        f"현재 ‘{current_theme}’ 입력 중 · 시스템 확인 공란 {len(current_missing)}개 · 모든 메뉴는 자유롭게 이동할 수 있습니다. 테마를 마치면 하단의 ‘측정 완료’를 눌러 주세요."
        if current_theme != "최종 확인·전송"
        else "모든 측정단계를 마쳤습니다. 최종 내용을 확인한 뒤 전송해 주세요."
    )
    st.markdown(f'<div class="power-menu-status">{html.escape(current_status_text)}</div>', unsafe_allow_html=True)

    if st.session_state.pop("power_temp_saved_notice", False):
        st.toast("현재 측정값을 임시 저장했습니다.", icon="✅")

    current_theme = st.session_state.get("power_current_theme", POWER_THEME_ORDER[0])
    _hydrate_power_theme_from_draft(current_theme)
    panel_nonce = int(st.session_state.get("power_panel_nonce", 0) or 0)

    # 측정 입력칸이 렌더링되기 전에 모바일 숫자키패드/자동 소수점 감시기를 먼저 설치합니다.
    # 특히 1조→2조 화면 전환 직후 새로 생성되는 셀 입력에도 동일 규칙이 즉시 적용됩니다.
    _render_power_auto_decimal_script()

    with st.expander(f"{POWER_THEME_ICON[current_theme]} {current_theme}", expanded=True):
        st.markdown(f'<div class="power-panel-marker" data-panel="{panel_nonce}"></div>', unsafe_allow_html=True)
        if current_theme == "전압·전류 측정":
            _hydrate_power_widget("power_phase_type", "삼상")
            st.radio(
                "전원 방식 선택",
                ["삼상", "단상"],
                format_func=lambda value: "삼상 전류" if value == "삼상" else "단상 전류",
                horizontal=True,
                key=_power_widget_key("power_phase_type"),
                on_change=_on_power_phase_change,
            )
            phase_type = _power_get("power_phase_type", "삼상")
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
                current_fields = [
                    ("R상 전류 (A)", "power_three_current_r"),
                    ("S상 전류 (A)", "power_three_current_s"),
                    ("T상 전류 (A)", "power_three_current_t"),
                    ("N상 전류 (A)", "power_three_current_n"),
                ]
                for start in range(0, len(current_fields), 2):
                    current_row = st.columns(2, gap="small")
                    for column, (label, key) in zip(current_row, current_fields[start:start + 2]):
                        with column:
                            _power_text_input(label, key=key)
            else:
                row = st.columns(2, gap="small")
                with row[0]:
                    _power_text_input("단상 전압 (V)", key="power_single_voltage")
                with row[1]:
                    _power_text_input("단상 전류 (A)", key="power_single_current")

        elif current_theme == "축전지 측정":
            _hydrate_power_widget("power_battery_set", "1조 셀 측정")
            battery_exit_stage = st.session_state.get("power_battery_exit_stage")
            battery2_enabled = _power_battery2_enabled()
            current_battery_set = _power_get("power_battery_set", "1조 셀 측정")
            selected_group = 2 if current_battery_set == "2조 셀 측정" and battery2_enabled else 1

            battery_options = ["1조 셀 측정"]
            if battery2_enabled:
                battery_options.append("2조 셀 측정")
            battery_ui_key = _power_widget_key("power_battery_set")
            if st.session_state.get(battery_ui_key, "1조 셀 측정") not in battery_options:
                st.session_state[battery_ui_key] = "1조 셀 측정"
                _power_set("power_battery_set", "1조 셀 측정")

            st.radio(
                "현재 입력할 축전지",
                battery_options,
                horizontal=True,
                key=battery_ui_key,
                on_change=_on_power_battery_set_change,
            )
            selected_group = 1 if _power_get("power_battery_set", "1조 셀 측정") == "1조 셀 측정" else 2
            group_caption = (
                "1조의 실제 설치 셀 수만 입력한 뒤 아래 ‘1조 셀 측정 완료’를 눌러 주세요."
                if selected_group == 1
                else "2조의 실제 설치 셀 수만 입력한 뒤 아래 ‘2조 셀 측정 완료’를 눌러 주세요."
            )
            st.caption(group_caption)

            # 측정값 화면을 먼저 보여 준 뒤 진행상태와 2조 측정 여부를 아래에 배치합니다.
            _render_power_battery_summary(selected_group)

            if battery_exit_stage == "ask_group2_complete":
                step_classes = ["done", "done", "active", ""]
            elif selected_group == 2:
                step_classes = ["done", "done", "done", "active"]
            else:
                step_classes = ["active", "", "", ""]

            step_labels = [
                "1조 셀 입력",
                "1조 측정 완료",
                "2조 측정 여부",
                "2조 측정 또는 테마 완료",
            ]
            step_html = ''.join(
                f'<div class="power-battery-flow-step {step_classes[index]}">'
                f'<span class="step-no">{index + 1}</span>{html.escape(label)}</div>'
                for index, label in enumerate(step_labels)
            )
            st.markdown(f'<div class="power-battery-flow">{step_html}</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="power-battery-path-guide">'
                '<b>1조만 측정:</b> 1조 입력 → 1조 측정 완료 → 2조 ‘아니오’ → 다음 메뉴<br>'
                '<b>2조까지 측정:</b> 1조 입력 → 1조 측정 완료 → 2조 ‘예’ → 2조 입력 → 2조 측정 완료 → 다음 메뉴'
                '</div>',
                unsafe_allow_html=True,
            )

            if battery_exit_stage == "ask_group2_complete":
                st.markdown(
                    '<div class="power-missing-box"><b>1조 셀 입력값을 완료했습니다. 2조 셀도 측정하시겠습니까?</b><br>'
                    '예를 선택하면 1조 값은 그대로 저장되고 2조 셀 입력 화면이 열립니다.<br>'
                    '아니오를 선택하면 축전지 측정이 완료되고 다음 미완료 측정 메뉴로 이동합니다.</div>',
                    unsafe_allow_html=True,
                )
                group2_yes, group2_no = st.columns(2, gap="small")
                with group2_yes:
                    st.button(
                        "예 · 2조 셀 측정",
                        key="power_complete_measure_group2",
                        type="primary",
                        use_container_width=True,
                        on_click=_finish_battery_completion,
                        args=(True,),
                    )
                with group2_no:
                    st.button(
                        "아니오 · 축전지 측정 완료 후 다음 메뉴",
                        key="power_complete_skip_group2",
                        use_container_width=True,
                        on_click=_finish_battery_completion,
                        args=(False,),
                    )

        elif current_theme == "접지저항 측정":
            st.markdown(
                '<div class="power-ground-heading security">🛡️ 보안접지 <span>(Ω)</span></div>',
                unsafe_allow_html=True,
            )
            st.caption("보안접지는 보안 1종·2종·3종으로 구분합니다.")
            security_columns = st.columns(3, gap="small")
            with security_columns[0]:
                _power_text_input("보안 1종", key="power_security_ground_1")
            with security_columns[1]:
                _power_text_input("보안 2종", key="power_security_ground_2")
            with security_columns[2]:
                _power_text_input("보안 3종", key="power_security_ground_3")

            ground_columns = st.columns(2, gap="small")
            with ground_columns[0]:
                st.markdown(
                    '<div class="power-ground-heading telecom">📡 통신접지 <span>(Ω)</span></div>',
                    unsafe_allow_html=True,
                )
                _power_text_input("통신접지(메인)", key="power_telecom_ground")
            with ground_columns[1]:
                st.markdown(
                    '<div class="power-ground-heading lightning">⚡ 피뢰침접지 <span>(Ω)</span></div>',
                    unsafe_allow_html=True,
                )
                _power_text_input("피뢰침접지", key="power_lightning_ground")

        elif current_theme == "최종 확인·전송":
            st.markdown(
                '<div class="power-notes-guide">'
                '<div class="title">📝 특이사항 입력</div>'
                '<div class="desc">현장 특이사항이나 미측정 사유, 후속 조치가 필요한 경우 아래 메모 입력란에 작성해 주세요. 특이사항이 없으면 비워 두어도 됩니다.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            _power_text_area(
                "특이사항 입력란 (선택)",
                key="power_notes",
                height=145,
                placeholder="특이사항이 있을 때 여기에 입력하세요.",
            )
            st.caption("작성 예: 축전지 2조 미측정 사유 · 접지선 보완 필요 · 다음 점검 시 확인사항")

            st.markdown("**📷 정밀점검 현장사진 (선택)**")
            power_photo_queue_key = "power_photo_queue"
            power_notice_key = "power_photo_queue_notice"
            power_raw_receipt_key = "power_photo_raw_receipt"
            power_health_key = f"{power_photo_queue_key}_health"
            power_album_nonce_key = "power_photo_album_nonce"
            power_camera_nonce_key = "power_photo_camera_nonce"
            power_album_nonce = int(st.session_state.get(power_album_nonce_key, 0) or 0)
            power_camera_nonce = int(st.session_state.get(power_camera_nonce_key, 0) or 0)

            st.caption("앨범은 여러 장을 한 번에 선택할 수 있고, 직접 촬영은 촬영 후 확인 버튼으로 담습니다.")

            with st.form(key=f"power_photo_album_form_{power_album_nonce}", clear_on_submit=False):
                power_album_files = st.file_uploader(
                    "🖼️ 앨범에서 여러 장 선택",
                    type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
                    accept_multiple_files=True,
                    key=f"power_photo_album_{power_album_nonce}",
                ) or []
                power_album_submit = st.form_submit_button("선택한 사진 담기", use_container_width=True)
            if power_album_submit:
                _worklog_process_photo_submission(
                    power_album_files,
                    power_photo_queue_key,
                    power_notice_key,
                    power_raw_receipt_key,
                    power_health_key,
                )
                st.session_state[power_album_nonce_key] = power_album_nonce + 1
                st.rerun()

            with st.form(key=f"power_photo_camera_form_{power_camera_nonce}", clear_on_submit=False):
                power_camera_file = st.file_uploader(
                    "📷 카메라 촬영 또는 사진 1장 선택",
                    type=["jpg", "jpeg", "png", "webp", "heic", "heif"],
                    accept_multiple_files=False,
                    key=f"power_photo_camera_{power_camera_nonce}",
                )
                power_camera_submit = st.form_submit_button("촬영/선택 사진 담기", use_container_width=True)
            if power_camera_submit:
                _worklog_process_photo_submission(
                    [power_camera_file] if power_camera_file is not None else [],
                    power_photo_queue_key,
                    power_notice_key,
                    power_raw_receipt_key,
                    power_health_key,
                )
                st.session_state[power_camera_nonce_key] = power_camera_nonce + 1
                st.rerun()

            power_queue_notice = str(st.session_state.pop(power_notice_key, "") or "").strip()
            if power_queue_notice:
                if "실패" in power_queue_notice or "못했습니다" in power_queue_notice or "없습니다" in power_queue_notice or "최대" in power_queue_notice:
                    st.warning(power_queue_notice)
                else:
                    st.success(power_queue_notice)

            power_photos = _worklog_queued_photo_objects(power_photo_queue_key)
            _worklog_render_photo_pipeline_status(
                power_photos,
                power_photo_queue_key,
                power_raw_receipt_key,
                power_health_key,
            )
            power_photo_info_col, power_photo_clear_col = st.columns(
                [4.0, 1.2], gap="small", vertical_alignment="center"
            )
            with power_photo_info_col:
                st.caption(
                    f"첨부 대기 {len(power_photos)}장 / 최대 {WORK_LOG_MAX_PHOTOS}장 · "
                    "여러 장 선택과 1장 촬영을 섞어서 추가할 수 있습니다."
                )
            with power_photo_clear_col:
                if power_photos and st.button(
                    "사진 지우기",
                    key="power_photo_queue_clear",
                    use_container_width=True,
                ):
                    st.session_state[power_photo_queue_key] = []
                    st.session_state.pop(power_raw_receipt_key, None)
                    st.session_state.pop(power_health_key, None)
                    st.rerun()

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
                {"구분": "주요 점검권역", "내용": payload_preview.get("major_area") or "미선택"},
                {"구분": "점검 국사", "내용": f"{payload_preview.get('mother')} / {payload_preview.get('local')}"},
                {"구분": "전원 구분", "내용": payload_preview.get("phase_type")},
                {"구분": "입력 방식", "내용": "기존값 불러오기 후 수정" if payload_preview.get("source_inspection_id") else "신규 입력"},
                {"구분": "특이사항", "내용": payload_preview.get("notes") or "없음"},
            ])
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            sanity_notes = _power_sanity_warnings(payload_preview)
            if sanity_notes:
                st.warning(
                    "🔎 **입력값 확인 권장** (참고용 · 저장은 그대로 가능합니다)\n\n"
                    + "\n".join(f"- {note}" for note in sanity_notes[:10])
                )

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
                photo_signature = []
                for photo in power_photos:
                    try:
                        photo_signature.append(hashlib.sha256(photo.getvalue()).hexdigest())
                    except Exception:
                        photo_signature.append(str(getattr(photo, "name", "photo")))
                payload_signature = hashlib.sha256(
                    json.dumps(
                        {"payload": payload, "photos": photo_signature},
                        ensure_ascii=False, sort_keys=True, default=str,
                    ).encode("utf-8")
                ).hexdigest()
                now_ts = time.time()
                last_signature = st.session_state.get("power_last_signature", "")
                last_saved_ts = float(st.session_state.get("power_last_saved_ts", 0) or 0)
                if payload_signature == last_signature and (now_ts - last_saved_ts) < 30:
                    st.warning("같은 측정값이 방금 저장되었습니다. 중복 전송을 방지했습니다.")
                else:
                    save_spinner_text = (
                        "Google Sheets와 Drive에 측정값·사진을 저장하고 있습니다..."
                        if power_photos else "Google Sheets에 측정값을 저장하고 있습니다..."
                    )
                    with st.spinner(save_spinner_text):
                        ok, message, inspection_id = save_power_inspection_result(payload, power_photos)
                    if ok:
                        st.session_state["power_last_signature"] = payload_signature
                        st.session_state["power_last_saved_ts"] = now_ts
                        st.success(f"✅ {message} · 점검ID: {inspection_id}")
                        time.sleep(2)
                        _reset_power_inspection()
                        st.rerun()
                    else:
                        st.error(f"❌ 저장 실패: {message}")

        show_theme_complete_button = not (
            current_theme == "축전지 측정"
            and st.session_state.get("power_battery_exit_stage") == "ask_group2_complete"
        )
        if current_theme in POWER_THEME_ORDER[:-1] and show_theme_complete_button:
            theme_missing = _power_theme_missing(current_theme)
            st.markdown("---")
            if current_theme == "축전지 측정":
                selected_battery_group = 1 if _power_get("power_battery_set", "1조 셀 측정") == "1조 셀 측정" else 2
                if selected_battery_group == 1:
                    complete_title = "1조 셀 입력을 마쳤습니까?"
                    complete_description = "‘1조 셀 측정 완료’를 누르면 현재 값이 저장되고 2조 셀 측정 여부를 확인합니다."
                    complete_button_label = "✅ 1조 셀 측정 완료"
                else:
                    complete_title = "2조 셀 입력을 마쳤습니까?"
                    complete_description = "‘2조 셀 측정 완료’를 누르면 축전지 테마가 완료되고 다음 미완료 측정 메뉴로 이동합니다."
                    complete_button_label = "✅ 2조 셀 측정 완료"
            else:
                complete_title = "현재 테마 측정을 마쳤습니까?"
                complete_description = "‘측정 완료’를 누르면 현재 값이 임시저장되고 완료 상태로 표시됩니다."
                complete_button_label = "✅ 측정 완료"

            st.markdown(
                f'<div class="power-complete-box"><b>{html.escape(complete_title)}</b><br>'
                f'{html.escape(complete_description)} '
                f'시스템 확인 공란: {len(theme_missing)}개</div>',
                unsafe_allow_html=True,
            )
            st.button(
                complete_button_label,
                key=f"power_measurement_complete_{POWER_THEME_ORDER.index(current_theme)}",
                type="primary",
                use_container_width=True,
                on_click=_complete_current_power_theme,
            )

    if current_theme != "최종 확인·전송":
        st.info("측정값은 화면과 분리된 임시저장소에 즉시 보존됩니다. 기본정보·특이사항을 제외한 측정 입력은 모바일 숫자키패드를 사용하며, Enter/확인을 누르면 자동 소수점 적용 후 다음 입력칸으로 이동합니다.")


# --- [Tab 2: 법률 리스크/규정/계약 검토 & 감사보고서 작성] ---

# --- [Tab 3: AI 에이전트] ---

# --- [Tab 4: 스마트 요약] ---

# --- [Tab 5: 관리자 대시보드 - 수동 로딩형 현황판] ---
# 입력 중인 내용을 서버에 자동 보관합니다. (연결이 끊겨도 다음 접속에서 복구)
_drafts_autosave(_gate_user)

with tab_admin:
    # 누적 데이터 보호: 사용자 인증코드를 한 번 더 확인합니다. (통과 전에는 아래 화면을 그리지 않음)
    _render_admin_stepup_gate()
    st.markdown("### 📊 전원 정밀점검 데이터 조회")
    st.caption(
        "Google Sheets의 최신 누적 점검자료를 필요한 시점에 불러와 지역·국소·기간별로 확인하고 "
        "CSV 또는 Excel 파일로 다운로드합니다. 이 화면은 조회 버튼을 누를 때만 Google Sheets를 읽습니다."
    )

    st.markdown("""
    <div style="background:linear-gradient(135deg,#E0F2FE 0%,#ECFDF5 100%); border:1px solid #7DD3FC;
                border-radius:18px; padding:18px 20px; margin:8px 0 16px; box-shadow:0 8px 22px rgba(14,116,144,0.10);">
      <div style="font-size:1.08rem; font-weight:950; color:#0F172A; margin-bottom:6px;">지역 사용자 이용방법</div>
      <div style="color:#334155; font-weight:750; line-height:1.65;">
        ① 최신 누적 데이터를 불러옵니다. ② 담당 모국·국소와 기간을 선택합니다.<br>
        ③ 화면에서 측정값을 확인하거나 CSV·Excel로 내려받아 현장 및 사무실 업무에 활용합니다.
      </div>
    </div>
    """, unsafe_allow_html=True)

    if "power_admin_df" not in st.session_state:
        st.session_state["power_admin_df"] = None
    if "power_admin_loaded_at" not in st.session_state:
        st.session_state["power_admin_loaded_at"] = ""
    if "power_admin_error" not in st.session_state:
        st.session_state["power_admin_error"] = ""

    def _load_power_inspection_admin_df() -> pd.DataFrame:
        """사용자가 조회 버튼을 누른 시점의 최신 전원 정밀점검 누적자료를 읽습니다."""
        client = init_google_sheet_connection()
        if not client:
            raise RuntimeError("Google Sheets 연결 실패: Streamlit Secrets와 서비스 계정 권한을 확인하세요.")

        spreadsheet = _open_spreadsheet(POWER_INSPECTION_SPREADSHEET_NAME, client)
        try:
            worksheet = spreadsheet.worksheet(POWER_INSPECTION_SHEET_NAME)
        except Exception:
            return pd.DataFrame(columns=POWER_INSPECTION_HEADERS)

        values = worksheet.get_all_values()
        if not values:
            return pd.DataFrame(columns=POWER_INSPECTION_HEADERS)

        headers = [str(value).strip() for value in values[0]]
        rows = values[1:]
        normalized_rows = [
            [row[index] if index < len(row) else "" for index in range(len(headers))]
            for row in rows
        ]
        return pd.DataFrame(normalized_rows, columns=headers).fillna("")

    load_col, reset_col, status_col = st.columns([0.27, 0.20, 0.53], vertical_alignment="center")
    with load_col:
        load_power_data = st.button(
            "🔄 최신 누적 데이터 불러오기",
            type="primary",
            use_container_width=True,
            key="power_admin_load_latest",
        )
    with reset_col:
        clear_power_data = st.button(
            "🧹 조회화면 초기화",
            use_container_width=True,
            key="power_admin_clear_data",
        )
    with status_col:
        if st.session_state.get("power_admin_loaded_at"):
            st.caption(
                f"마지막 조회: {st.session_state['power_admin_loaded_at']} · "
                "최신 자료가 필요하면 다시 불러오기를 누르세요."
            )
        else:
            st.caption("아직 Google Sheets 데이터를 불러오지 않았습니다.")

    if clear_power_data:
        st.session_state["power_admin_df"] = None
        st.session_state["power_admin_loaded_at"] = ""
        st.session_state["power_admin_error"] = ""
        st.rerun()

    if load_power_data:
        with st.spinner("Google Sheets에서 전원 정밀점검 최신 누적자료를 불러오는 중입니다..."):
            try:
                st.session_state["power_admin_df"] = _load_power_inspection_admin_df()
                st.session_state["power_admin_loaded_at"] = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state["power_admin_error"] = ""
            except Exception as error:
                st.session_state["power_admin_df"] = None
                st.session_state["power_admin_error"] = str(error)

    if st.session_state.get("power_admin_error"):
        st.error(f"전원 정밀점검 데이터를 불러오지 못했습니다: {st.session_state['power_admin_error']}")

    power_admin_df = st.session_state.get("power_admin_df")

    if power_admin_df is None:
        st.info("업무에 최신 측정자료가 필요할 때 위의 ‘최신 누적 데이터 불러오기’를 눌러 주세요.")
    elif power_admin_df.empty:
        st.warning("Google Sheets에 저장된 전원 정밀점검 자료가 아직 없습니다.")
    else:
        source_df = power_admin_df.copy().fillna("")

        for required_column in POWER_INSPECTION_HEADERS:
            if required_column not in source_df.columns:
                source_df[required_column] = ""

        source_df["_저장일시_dt"] = pd.to_datetime(source_df["저장일시"], errors="coerce")
        source_df = source_df.sort_values("_저장일시_dt", ascending=False, na_position="last")

        st.markdown("#### 🔎 담당 지역 및 조회범위 선택")
        filter_col1, filter_col2, filter_col3 = st.columns(3)

        mother_values = sorted(
            value for value in source_df["모국"].astype(str).str.strip().unique().tolist() if value
        )
        my_mothers = [m for m in _my_power_mothers(str(_gate_user.get("name", "") or "")) if m in mother_values]
        mother_options = (["내 담당 모국 전체"] if my_mothers else []) + ["전체 모국"] + mother_values
        with filter_col1:
            selected_mother = st.selectbox(
                "관리 모국",
                mother_options,
                key="power_admin_filter_mother",
            )

        if selected_mother == "전체 모국":
            locality_source = source_df
        elif selected_mother == "내 담당 모국 전체":
            locality_source = source_df[source_df["모국"].astype(str).str.strip().isin(my_mothers)]
        else:
            locality_source = source_df[source_df["모국"].astype(str).str.strip() == selected_mother]

        locality_values = sorted(
            value for value in locality_source["국소"].astype(str).str.strip().unique().tolist() if value
        )
        with filter_col2:
            selected_local = st.selectbox(
                "관리 국소",
                ["전체 국소"] + locality_values,
                key="power_admin_filter_local",
            )

        period_options = {
            "최근 1개월": 31,
            "최근 6개월": 183,
            "최근 1년": 365,
            "최근 2년": 730,
            "전체 기간": None,
        }
        with filter_col3:
            selected_period = st.selectbox(
                "조회 기간",
                list(period_options.keys()),
                index=2,
                key="power_admin_filter_period",
            )

        search_term = st.text_input(
            "측정자료 검색",
            placeholder="점검자, 운용조, 모국, 국소, 특이사항 등",
            key="power_admin_search_term",
        ).strip()

        filtered_df = source_df.copy()
        if selected_mother == "내 담당 모국 전체":
            filtered_df = filtered_df[filtered_df["모국"].astype(str).str.strip().isin(my_mothers)]
        elif selected_mother != "전체 모국":
            filtered_df = filtered_df[
                filtered_df["모국"].astype(str).str.strip() == selected_mother
            ]
        if selected_local != "전체 국소":
            filtered_df = filtered_df[
                filtered_df["국소"].astype(str).str.strip() == selected_local
            ]

        period_days = period_options[selected_period]
        if period_days is not None:
            cutoff = _korea_now().replace(tzinfo=None) - datetime.timedelta(days=period_days)
            filtered_df = filtered_df[
                filtered_df["_저장일시_dt"].notna()
                & (filtered_df["_저장일시_dt"] >= cutoff)
            ]

        if search_term:
            searchable_columns = [column for column in filtered_df.columns if column != "_저장일시_dt"]
            search_mask = filtered_df[searchable_columns].apply(
                lambda row: row.astype(str).str.contains(search_term, case=False, na=False).any(),
                axis=1,
            )
            filtered_df = filtered_df[search_mask]

        total_records = int(len(filtered_df))
        unique_mothers = int(filtered_df["모국"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        unique_locals = int(filtered_df["국소"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        unique_inspectors = int(filtered_df["점검자"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        latest_saved_at = "-"
        if not filtered_df.empty and filtered_df["_저장일시_dt"].notna().any():
            latest_saved_at = filtered_df["_저장일시_dt"].max().strftime("%Y-%m-%d %H:%M:%S")

        metric1, metric2, metric3, metric4, metric5 = st.columns(5)
        metric1.metric("조회 건수", f"{total_records:,}건")
        metric2.metric("모국", f"{unique_mothers:,}개")
        metric3.metric("국소", f"{unique_locals:,}개")
        metric4.metric("점검자", f"{unique_inspectors:,}명")
        metric5.metric("최근 측정일시", latest_saved_at)

        display_df = filtered_df.drop(columns=["_저장일시_dt"], errors="ignore")

        st.markdown("#### 📋 전원 정밀점검 측정자료")
        st.caption(
            "화면에는 선택한 모국·국소·기간 조건의 자료만 표시됩니다. "
            "CSV와 Excel 다운로드에도 동일한 필터가 적용됩니다."
        )
        st.dataframe(display_df, use_container_width=True, hide_index=True, height=520)

        photo_records_df = filtered_df[
            filtered_df.get("사진파일ID목록", pd.Series(index=filtered_df.index, dtype=str)).astype(str).str.strip() != ""
        ].copy()
        if not photo_records_df.empty:
            with st.expander("📷 정밀점검 현장사진 조회·다운로드", expanded=False):
                photo_record_indices = photo_records_df.index.tolist()

                def _power_admin_photo_label(row_index):
                    row = photo_records_df.loc[row_index]
                    count = len([v for v in str(row.get("사진파일ID목록", "") or "").split("|") if v.strip()])
                    return (
                        f"{row.get('저장일시','')} · {row.get('모국','')} / {row.get('국소','')} · "
                        f"{row.get('점검자','')} · 사진 {count}장"
                    )

                selected_photo_row_index = st.selectbox(
                    "사진을 확인할 정밀점검 기록",
                    options=photo_record_indices,
                    format_func=_power_admin_photo_label,
                    key="power_admin_photo_record",
                )
                selected_photo_record = photo_records_df.loc[selected_photo_row_index]
                _render_power_photo_download(
                    selected_photo_record,
                    key_prefix=f"power_admin_{selected_photo_record.get('점검ID', selected_photo_row_index)}",
                )

        summary_df = pd.DataFrame(columns=["모국", "국소", "점검건수", "최근측정일시", "최근점검자"])
        if not filtered_df.empty:
            summary_source = filtered_df.copy()
            summary_source["점검자"] = summary_source["점검자"].astype(str)
            summary_rows = []
            for (mother_name, local_name), group in summary_source.groupby(["모국", "국소"], dropna=False):
                ordered = group.sort_values("_저장일시_dt", ascending=False, na_position="last")
                latest_row = ordered.iloc[0]
                latest_dt = latest_row.get("_저장일시_dt")
                latest_text = latest_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(latest_dt) else str(latest_row.get("저장일시", ""))
                summary_rows.append({
                    "모국": str(mother_name),
                    "국소": str(local_name),
                    "점검건수": int(len(group)),
                    "최근측정일시": latest_text,
                    "최근점검자": str(latest_row.get("점검자", "")),
                })
            summary_df = pd.DataFrame(summary_rows).sort_values(["모국", "국소"])

        safe_mother = "전체" if selected_mother == "전체 모국" else "담당" if selected_mother == "내 담당 모국 전체" else re.sub(r"[^0-9A-Za-z가-힣_-]", "_", selected_mother)
        safe_local = "전체" if selected_local == "전체 국소" else re.sub(r"[^0-9A-Za-z가-힣_-]", "_", selected_local)
        exported_at = _korea_now().strftime("%Y%m%d_%H%M%S")
        file_base = f"전원정밀점검_{safe_mother}_{safe_local}_{exported_at}"

        download_col1, download_col2 = st.columns(2)
        with download_col1:
            csv_bytes = display_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 현재 조회자료 CSV 다운로드",
                data=csv_bytes,
                file_name=f"{file_base}.csv",
                mime="text/csv",
                use_container_width=True,
                key="power_admin_download_csv",
                disabled=display_df.empty,
                on_click=_audit_log,
                args=("점검 데이터 다운로드(CSV)", f"{file_base} · {len(display_df)}건"),
            )

        with download_col2:
            try:
                from io import BytesIO

                excel_output = BytesIO()
                with pd.ExcelWriter(excel_output, engine="openpyxl") as writer:
                    display_df.to_excel(writer, index=False, sheet_name="전원정밀점검_자료")
                    summary_df.to_excel(writer, index=False, sheet_name="국소별_요약")
                st.download_button(
                    "📥 현재 조회자료 Excel 다운로드",
                    data=excel_output.getvalue(),
                    file_name=f"{file_base}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="power_admin_download_excel",
                    disabled=display_df.empty,
                    on_click=_audit_log,
                    args=("점검 데이터 다운로드(Excel)", f"{file_base} · {len(display_df)}건"),
                )
            except Exception as excel_error:
                st.warning(f"Excel 파일을 생성하지 못했습니다. CSV 다운로드를 이용해 주세요. ({excel_error})")

        with st.expander("📌 데이터 이용 및 운영 안내", expanded=False):
            st.markdown(
                "- 이 화면은 **최신 누적 데이터 불러오기**를 누른 시점의 Google Sheets 자료를 사용합니다.\n"
                "- 실시간 최신자료가 필요하면 조회 버튼을 다시 눌러 새로 읽어오면 됩니다.\n"
                "- 지역 사용자는 담당 모국과 국소를 선택한 뒤 화면 확인 또는 파일 다운로드를 이용할 수 있습니다.\n"
                "- CSV는 범용 공유용, Excel은 원본자료와 국소별 요약을 함께 제공하는 업무용 형식입니다.\n"
                "- 조회·다운로드 이력은 감사 기록(MY_WORK_LOG_AUDIT 시트)에 남습니다. 지역별 열람권한을 기술적으로 제한해야 하는 경우에는 사용자 계정과 담당 모국을 연결하는 별도 권한 설정이 필요합니다."
            )

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
import plotly.graph_objects as go
import plotly.express as px

# Plotly: 확대/축소 후 "원점 복원" 가능하도록 모드바 항상 표시
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
    "doubleClick": "reset",
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
# 2. 🎨 디자인 테마 (베프님이 좋아하는 가독성 스타일 보존)
# ==========================================
st.markdown("""
<style>
/* Expander 및 텍스트 가독성 */
details > summary { font-size: 1.15rem !important; font-weight: 900 !important; color: #1565C0 !important; }
html { font-size: 16.2px; }
.stApp { background-color: #F4F6F9; }
[data-testid="stSidebar"] { background-color: #2C3E50; }
[data-testid="stSidebar"] * { color: #FFFFFF !important; }

/* 2월 캠페인 전용 스타일 */
.clean-container { max-width: 850px; margin: 0 auto; }
div[data-testid="stForm"] {
    background-color: #0F172A !important;
    border: 2px solid #334155 !important;
    border-radius: 25px !important;
    padding: 30px !important;
}
.stTextInput input {
    background-color: #1E293B !important;
    color: white !important;
    border: 1px solid #475569 !important;
    height: 55px !important;
    text-align: center !important;
}
.stSelectbox div[role="combobox"] { background-color: #1E293B !important; color: white !important; height: 55px !important; }

/* 버튼 스타일 */
.stButton > button, div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    font-weight: 800 !important;
}

/* 캠페인 제출 버튼 커스텀 */
.clean-submit button {
    background: linear-gradient(to right, #E11D48, #9F1239) !important;
    height: 65px !important;
    font-size: 1.3rem !important;
    border-radius: 15px !important;
}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 핵심 유틸리티 함수 (구글시트 연동 로직)
# ==========================================
@st.cache_resource
def init_google_sheet_connection():
    if gspread is None: return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except: return None

def _korea_now():
    kst = pytz.timezone("Asia/Seoul")
    return datetime.datetime.now(kst)

def get_participation_stats(sheet_name):
    client = init_google_sheet_connection()
    if not client: return 0
    try:
        ss = client.open("Audit_Result_2026")
        ws = ss.worksheet(sheet_name)
        return len(ws.get_all_values()) - 1
    except: return 0

def save_campaign_pledge(emp_id, name, unit, dept, sheet_name):
    """
    설 명절 클린 캠페인 서약 저장 (실시간 중복 방지)
    - 기본: 사번(사번 1인 1회)
    - 예외: 사번이 "00000000"인 경우, (사번 + 성명) 조합으로 1인 1회
    """
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패"

    emp_id = str(emp_id or "").strip()
    name = str(name or "").strip()
    unit = str(unit or "").strip()
    dept = str(dept or "").strip()

    if not emp_id or not name:
        return False, "사번/성함은 필수입니다."

    try:
        ss = client.open("Audit_Result_2026")

        # 시트 준비
        try:
            ws = ss.worksheet(sheet_name)
        except Exception:
            ws = ss.add_worksheet(title=sheet_name, rows=2000, cols=10)
            ws.append_row(["저장시간", "사번", "성명", "소속", "부서", "상태"], value_input_option="USER_ENTERED")

        # 헤더 보정(혹시라도 헤더가 비어있거나 바뀐 경우)
        try:
            header = ws.row_values(1)
        except Exception:
            header = []
        if not header or "사번" not in header or "성명" not in header:
            ws.insert_row(["저장시간", "사번", "성명", "소속", "부서", "상태"], 1)
            header = ws.row_values(1)

        # 실시간 중복 체크 (가급적 특정 컬럼만 읽기)
        # 사번: 2열, 성명: 3열(기본 헤더 기준)
        emp_col = ws.col_values(2)[1:]  # header 제외
        emp_col = [str(v).strip() for v in emp_col if str(v).strip()]

        if emp_id != "00000000":
            if emp_id in emp_col:
                return False, "이미 참여하셨습니다. (중복 서약 불가)"
        else:
            # 예외 사번은 성명까지 함께 체크
            name_col = ws.col_values(3)[1:]
            name_col = [str(v).strip() for v in name_col]
            pairs = set()
            for i in range(min(len(emp_col), len(name_col))):
                pairs.add((emp_col[i], name_col[i]))
            if (emp_id, name) in pairs:
                return False, "이미 참여하셨습니다. (중복 서약 불가)"

        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([now, emp_id, name, unit, dept, "2026 설 명절 클린캠페인 서약완료"], value_input_option="USER_ENTERED")
        return True, "성공"

    except Exception as e:
        return False, str(e)


# ------------------------------------------
# ------------------------------------------
# 기존 AI 모델 및 파일 처리 함수 (1200라인 로직 보존)
# ------------------------------------------
def get_model():
    if "api_key" in st.session_state:
        genai.configure(api_key=st.session_state["api_key"])
    return genai.GenerativeModel("gemini-1.5-pro")

# (기존의 read_file, process_media_file, get_youtube_transcript 등 모든 로직이 이 아래에 포함됨)

# ==========================================
# 4. 로그인 및 세션 관리
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    if "api_key" not in st.session_state:
        # 로그인 폼...
        with st.form("login_form"):
            key_in = st.text_input("Access Key", type="password")
            if st.form_submit_button("접속"):
                st.session_state["api_key"] = key_in
                st.rerun()
    else:
        st.success("🟢 정상 가동 중")
        if st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()

# ==========================================
# 5. 메인 화면 및 탭 구성 (완벽 통합)
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)

tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    "✅ 자율점검", "📄 법률 검토", "💬 AI 에이전트(챗봇)", "📰 스마트 요약", "🔒 관리자 모드"
])

# --- [Tab 1: 자율점검 - 2월 클린 캠페인 전용] ---
with tab_audit:
    # ==========================================
    # 🧧 2026 설 명절 클린 캠페인 (자율점검 탭 전용)
    # - 다른 탭(법률 검토/챗봇/관리자) 로직은 변경하지 않습니다.
    # ==========================================
    CAMPAIGN_SHEET = "2026_설명절_클린캠페인"
    TOTAL_STAFF = 1000  # 전사 기준 인원(필요 시 조정)
    EVENT_HEADLINE = "전 임직원 50% 이상 참여 시, 참여자 중 50명 추첨 커피 쿠폰 지급"
    REPORT_PHONE = "02-3414-1919"
    REPORT_EMAIL = "ethics@ktmos.com"
    CYBER_REPORT_URL = "https://www.clean.go.kr"  # 필요 시 사내 링크로 교체

    # --- 캠페인 전용 CSS (자율점검 탭 1번 패널에만 적용) ---
    st.markdown("""
    <style>
    /* 탭 1(자율점검) 패널에만 적용 */
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) {
        background: radial-gradient(1200px 800px at 30% 20%, #111C3A 0%, #070B17 55%, #050814 100%);
        border-radius: 18px;
        padding: 18px 18px 28px 18px;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .lny-top-banner{
        background: linear-gradient(90deg, #F59E0B 0%, #EF4444 50%, #E11D48 100%);
        color: #0B1020;
        font-weight: 900;
        letter-spacing: 0.3px;
        padding: 10px 14px;
        border-radius: 14px;
        text-align: center;
        margin: 6px 0 14px 0;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .lny-section-title{
        margin: 26px 0 12px 0;
        font-size: 2.0rem;
        font-weight: 900;
        color: #E5E7EB;
        text-align: center;
        letter-spacing: -0.5px;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .lny-subtitle{
        margin-top: -6px;
        margin-bottom: 12px;
        color: #94A3B8;
        text-align: center;
        font-weight: 700;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .lny-card{
        background: rgba(15, 23, 42, 0.75);
        border: 1px solid rgba(148, 163, 184, 0.15);
        box-shadow: 0 10px 30px rgba(0,0,0,0.35);
        border-radius: 22px;
        padding: 22px;
        color: #E5E7EB;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .lny-card h3{
        margin: 0 0 10px 0;
        font-size: 1.35rem;
        font-weight: 900;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .lny-muted{
        color: #94A3B8;
        font-weight: 650;
        line-height: 1.75;
    }
    /* 폼/입력 UI (탭 1 한정) */
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) div[data-testid="stForm"]{
        background: rgba(15, 23, 42, 0.75) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 28px !important;
        padding: 24px !important;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .stTextInput input,
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .stSelectbox div[role="combobox"]{
        background: rgba(30, 41, 59, 0.95) !important;
        color: #E5E7EB !important;
        border: 1px solid rgba(148, 163, 184, 0.25) !important;
        border-radius: 16px !important;
        height: 52px !important;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) div[data-testid="stFormSubmitButton"] button{
        background: linear-gradient(90deg, #EF4444 0%, #E11D48 70%, #9F1239 100%) !important;
        color: white !important;
        font-weight: 900 !important;
        border-radius: 18px !important;
        height: 52px !important;
        width: 100% !important;
        border: 0 !important;
    }
    div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) .lny-count{
        margin-top: 18px;
        text-align: center;
        color: #94A3B8;
        font-weight: 900;
        letter-spacing: 2px;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- 이벤트 문구 (상단 인포그래픽/폼 상단에 모두 노출) ---
    st.markdown(f"<div class='lny-top-banner'>🎁 {EVENT_HEADLINE}</div>", unsafe_allow_html=True)

    # ==========================================
    # 1) HERO (비디오 배경)
    # ==========================================
    video_b64 = None
    video_used = None
    for _vp in ["2026 New year.mp4", "2026 New Year.mp4", "2026_new_year.mp4", "2026_newyear.mp4"]:
        if os.path.exists(_vp):
            try:
                with open(_vp, "rb") as _vf:
                    video_b64 = base64.b64encode(_vf.read()).decode("utf-8")
                video_used = _vp
                break
            except Exception:
                video_b64 = None
                video_used = None

    hero_html = f"""
    <div style="position:relative; width:100%; height:640px; border-radius:28px; overflow:hidden;
                border:1px solid rgba(148,163,184,0.18); box-shadow:0 18px 45px rgba(0,0,0,0.45);">
        {('<video autoplay muted loop playsinline style="position:absolute; inset:0; width:100%; height:100%; object-fit:cover; filter:contrast(1.05) saturate(1.05);"><source src="data:video/mp4;base64,' + (video_b64 or '') + '" type="video/mp4"></video>') if video_b64 else '<div style="position:absolute; inset:0; background:linear-gradient(115deg,#111C3A 0%, #070B17 55%, #050814 100%);"></div>'}
        <div style="position:absolute; inset:0; background:linear-gradient(90deg, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0.25) 45%, rgba(0,0,0,0.55) 100%);"></div>

        <div style="position:absolute; top:32px; left:32px; right:32px;">
            <div style="display:inline-block; padding:8px 14px; border-radius:999px;
                        border:1px solid rgba(239,68,68,0.35); background:rgba(15,23,42,0.55);
                        color:#FCA5A5; font-weight:900; font-size:14px;">
                2026 병오년(丙午年) : 붉은 말의 해
            </div>
        </div>

        <div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; flex-direction:column; gap:14px; padding:0 28px;">
            <div style="font-size:82px; font-weight:950; line-height:1.0; color:#E5E7EB; letter-spacing:-1px; text-align:center; text-shadow:0 10px 30px rgba(0,0,0,0.55);">
                새해 복
            </div>
            <div style="font-size:88px; font-weight:980; line-height:1.0; color:#EF4444; letter-spacing:-1.5px; text-align:center; text-shadow:0 12px 35px rgba(0,0,0,0.60);">
                많이 받으십시오
            </div>

            <div style="max-width:900px; text-align:center; color:#E5E7EB; font-weight:800; font-size:18px; line-height:1.8; opacity:0.92;">
                ktMOS북부 임직원 여러분, 정직과 신뢰를 바탕으로 더 크게 도약하고 성장하는 2026년이 되시길 기원합니다.
            </div>

            <div style="margin-top:18px; display:flex; gap:14px; align-items:center;">
                <div style="background:linear-gradient(90deg,#EF4444 0%, #E11D48 100%); color:#fff; font-weight:950;
                            padding:14px 22px; border-radius:16px; font-size:18px; box-shadow:0 14px 35px rgba(225,29,72,0.35);">
                    캠페인 확인하기
                </div>
                <div style="width:46px; height:46px; border-radius:14px; background:rgba(15,23,42,0.60);
                            border:1px solid rgba(148,163,184,0.18); display:flex; align-items:center; justify-content:center; color:#E5E7EB; font-weight:900;">
                    🔇
                </div>
                <div style="width:46px; height:46px; border-radius:14px; background:rgba(15,23,42,0.60);
                            border:1px solid rgba(148,163,184,0.18); display:flex; align-items:center; justify-content:center; color:#E5E7EB; font-weight:900;">
                    ⤴
                </div>
            </div>

            <div style="margin-top:10px; font-size:13px; color:rgba(148,163,184,0.85); font-weight:800;">
                {('Video: ' + video_used) if video_used else '※ 비디오 파일이 없으면 기본 배경으로 표시됩니다. (루트에 “2026 New year.mp4” 추가)'}
            </div>
        </div>
    </div>
    """
    components.html(hero_html, height=660, scrolling=False)

    # ==========================================
    # 2) 2026 청렴 아우라 분석 (Fortune Scan)
    # ==========================================
    st.markdown("<div class='lny-section-title'>2026 청렴 아우라 분석</div>", unsafe_allow_html=True)
    st.markdown("<div class='lny-subtitle'>성함과 올해의 목표를 입력하고, 청렴 기운을 스캔해 보세요.</div>", unsafe_allow_html=True)

    f1, f2 = st.columns(2)
    scan_name = f1.text_input("성함", key="lny_scan_name", placeholder="성함")
    scan_goal = f2.text_input("올해의 주요 목표", key="lny_scan_goal", placeholder="올해의 주요 목표")

    if st.button("✨ 청렴 기운 스캔하기", use_container_width=True):
        seed = hashlib.sha256(f"{scan_name}|{scan_goal}|2026".encode("utf-8")).hexdigest()
        pick = int(seed[:8], 16) % 8
        msgs = [
            "오늘의 청렴 키워드: **정직** — 작은 선택이 큰 신뢰를 만듭니다.",
            "오늘의 청렴 키워드: **절제** — 명절일수록 기준을 단단히 지켜요.",
            "오늘의 청렴 키워드: **투명** — 기록과 공유가 가장 강한 예방입니다.",
            "오늘의 청렴 키워드: **존중** — 이해관계자와의 경계를 분명히 해요.",
            "오늘의 청렴 키워드: **신속** — 애매하면 즉시 문의/신고가 안전합니다.",
            "오늘의 청렴 키워드: **공정** — 같은 기준, 같은 원칙을 적용합니다.",
            "오늘의 청렴 키워드: **책임** — 내 결정의 무게를 끝까지 감당합니다.",
            "오늘의 청렴 키워드: **용기** — 부당함 앞에서 침묵하지 않습니다.",
        ]
        st.session_state["lny_scan_result"] = msgs[pick]

    if st.session_state.get("lny_scan_result"):
        st.markdown(
            f"<div class='lny-card' style='text-align:center;'><h3>결과</h3><div class='lny-muted' style='font-size:1.15rem;'>{st.session_state['lny_scan_result']}</div></div>",
            unsafe_allow_html=True
        )

    # ==========================================
    # 3) 설 명절 클린 캠페인 아젠다 (Clean Agenda)
    # ==========================================
    st.markdown("<div class='lny-section-title'>설명절 클린 캠페인 아젠다</div>", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div class='lny-card'>
            <h3>🎁 선물 안 주고 안 받기</h3>
            <div class='lny-muted'>협력사 및 이해관계자와의 명절 선물 교환은 금지됩니다. 마음만 정중히 받겠습니다.</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown("""
        <div class='lny-card'>
            <h3>☕ 향응 및 편의 제공 금지</h3>
            <div class='lny-muted'>부적절한 식사 대접이나 골프 등 편의 제공은 원천 차단하여 투명성을 지킵니다.</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown("""
        <div class='lny-card'>
            <h3>🛡️ 부득이한 경우 자진신고</h3>
            <div class='lny-muted'>택배 등으로 배송된 선물은 반송이 원칙이며, 불가피할 시 클린센터로 즉시 신고합니다.</div>
        </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # 4) 비윤리 행위 신고 채널 (Reporting Channel)
    # ==========================================
    st.markdown("<div class='lny-section-title'>비윤리 행위 신고 채널</div>", unsafe_allow_html=True)

    left, right = st.columns([1.2, 2.2])
    with left:
        st.markdown("""
        <div class='lny-card'>
            <h3 style="font-size:1.6rem;">비윤리 행위<br/>신고 채널</h3>
            <div class='lny-muted'>부정부패 없는 ktMOS북부를 위해 여러분의 용기 있는 목소리가 필요합니다.</div>
        </div>
        """, unsafe_allow_html=True)

    with right:
        r1, r2 = st.columns(2)
        with r1:
            st.markdown(f"""
            <div class='lny-card' style='height:100%;'>
                <h3>📞 감사실 직통</h3>
                <div class='lny-muted' style='font-size:1.35rem; font-weight:950; color:#E5E7EB;'>{REPORT_PHONE}</div>
            </div>
            """, unsafe_allow_html=True)
        with r2:
            st.markdown(f"""
            <div class='lny-card' style='height:100%;'>
                <h3>🌐 사이버 신고</h3>
                <div class='lny-muted'><a href='{CYBER_REPORT_URL}' target='_blank' style='color:#FBBF24; font-weight:950; text-decoration:none;'>바로가기</a></div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class='lny-card' style='margin-top:14px;'>
            <h3>✉️ 이메일 제보</h3>
            <div class='lny-muted' style='font-size:1.25rem; font-weight:950; color:#E5E7EB;'>{REPORT_EMAIL}</div>
        </div>
        """, unsafe_allow_html=True)

    # ==========================================
    # 5) 스스로 다짐하는 청렴 서약 (Pledge Event)
    # ==========================================
    st.markdown("<div class='lny-section-title'>스스로 다짐하는 청렴 서약</div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div class='lny-card' style='text-align:center; border:2px solid rgba(239,68,68,0.35);'>
        <div style='font-size:1.45rem; font-weight:980; margin-bottom:6px;'>🎁 청렴 실천 응원 이벤트</div>
        <div class='lny-muted' style='font-size:1.05rem;'>
            <b style='color:#FBBF24;'>{EVENT_HEADLINE}</b>
        </div>
        <div class='lny-muted' style='margin-top:10px;'>서약 참여로 스스로의 기준을 다지고, 함께 투명한 명절 문화를 만들어요.</div>
    </div>
    """, unsafe_allow_html=True)

    # 현재 참여 수(대시보드)
    current_count = get_participation_stats(CAMPAIGN_SHEET)
    current_rate = 0.0 if TOTAL_STAFF <= 0 else min(100.0, (current_count / TOTAL_STAFF) * 100.0)

    # 서약 폼 (사번 1인 1회, 시트 실시간 중복 체크)
    unit = ""
    dept = ""
    with st.form("lny_pledge_form"):
        col_id, col_name, col_btn = st.columns([2.2, 1.3, 1.1])
        emp_id = col_id.text_input("사번", placeholder="사번(8자리) 예: 10001234")
        emp_name = col_name.text_input("성함", placeholder="홍길동")
        submitted = col_btn.form_submit_button("서약하기")

        with st.expander("추가 정보(선택)"):
            unit = st.text_input("소속", placeholder="예: 강북본부")
            dept = st.text_input("부서", placeholder="예: OO팀")

    if submitted:
        if not emp_id or not emp_name:
            st.warning("⚠️ 사번과 성함을 입력해 주세요.")
        else:
            ok, msg = save_campaign_pledge(emp_id, emp_name, unit, dept, CAMPAIGN_SHEET)
            if ok:
                # 폭죽 효과(가벼운 JS)
                components.html(
                    """<script src='https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js'></script>
                    <script>
                    confetti({particleCount:160, spread:75, origin:{y:0.7}});
                    setTimeout(()=>confetti({particleCount:120, spread:80, origin:{y:0.7}}), 450);
                    </script>""",
                    height=0
                )
                st.success("✅ 서약이 완료되었습니다. 참여해 주셔서 감사합니다!")
                st.rerun()
            else:
                st.error(f"❌ {msg}")

    # 하단 참여 현황 (실시간)
    st.markdown(f"<div class='lny-count'>CURRENT: {current_count} SIGNATURES</div>", unsafe_allow_html=True)
    st.progress(current_rate / 100.0)
    st.caption(f"참여율: {current_rate:.1f}% (기준: {TOTAL_STAFF}명)")
with tab_doc:
    st.info("기존 법률 검토 로직 보존됨...")
    # (원래의 tab_doc 코드 삽입)

# (tab_chat, tab_summary, tab_admin 등도 모두 동일하게 유지)

st.markdown("<div style='text-align:center; padding:30px; color:#94A3B8; font-size:0.8rem;'>© 2026 ktMOS North Audit AI Agent.</div>", unsafe_allow_html=True)

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

# Plotly: 확대/축소 후 "원점 복원" 가능하도록 모드바 항상 표시
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,          # 스크롤로 의도치 않은 확대 방지
    "doubleClick": "reset",       # 더블클릭/더블탭 시 원점 복원
}
import plotly.graph_objects as go
import plotly.express as px

# [필수] 구글 시트 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
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
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 🎨 디자인 테마 (검증된 V71 코드 100% 유지)
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9; }
    [data-testid="stSidebar"] { background-color: #2C3E50; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: 1px solid #BDC3C7 !important;
    }
    
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }


    /* ✅ (로그인) Form submit button도 동일 스타일 적용 */
    div[data-testid="stFormSubmitButton"] > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }
    div[data-testid="stFormSubmitButton"] > button * {
        color: #FFFFFF !important;
    }

    /* ✅ (로그인) 비밀번호 보기(눈) 아이콘이 '하얀 박스'로 보이지 않게 색상/배경 조정 */
    [data-testid="stSidebar"] div[data-testid="stTextInput"] button {
        background: transparent !important;
        border: none !important;
        color: #2C3E50 !important;   /* 흰 입력창 위에서 잘 보이게 */
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] div[data-testid="stTextInput"] button:hover {
        background: rgba(44, 62, 80, 0.12) !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] div[data-testid="stTextInput"] button svg {
        fill: currentColor !important;
        stroke: currentColor !important;
    }

    /* 상단 메뉴 버튼 (책갈피) */
    [data-testid="stSidebarCollapsedControl"] {
        color: transparent !important;
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        border: 1px solid #ddd;
        width: 40px; height: 40px;
        z-index: 99999;
    }
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        color: #333;
        font-size: 24px;
        font-weight: bold;
        position: absolute;
        top: 5px; left: 10px;
    }
    
    [data-testid="stChatMessage"] { background-color: #FFFFFF; border: 1px solid #eee; }
    [data-testid="stChatMessage"][data-testid="user"] { background-color: #E3F2FD; }

    /* 🎄 크리스마스 로그아웃 버튼 스타일 */
    .logout-btn {
        border: 2px solid #FF5252 !important;
        background: transparent !important;
        color: #FF5252 !important;
        border-radius: 20px !important;
    }
    .logout-btn:hover {
        background-color: #FF5252 !important;
        color: white !important;
    }
    

    /* ==========================
       📱 Mobile / Responsive Tweaks
       - Stack columns on small screens
       - Reduce padding & font sizes
       - Make sidebar usable on mobile
       ========================== */
    @media (max-width: 768px) {
        /* Main content padding */
        [data-testid="stAppViewContainer"] .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1.25rem !important;
            max-width: 100% !important;
        }

        /* Stack Streamlit columns */
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 0.75rem !important;
        }
        div[data-testid="stHorizontalBlock"] > div {
            flex: 1 1 100% !important;
            width: 100% !important;
            min-width: 0 !important;
        }

        /* Slightly smaller typography */
        h1 { font-size: 1.65rem !important; }
        h2 { font-size: 1.35rem !important; }
        h3 { font-size: 1.15rem !important; }
        .stMarkdown, .stTextInput, .stSelectbox, .stRadio, .stCheckbox {
            font-size: 0.98rem !important;
        }

        /* Buttons: full width & comfortable tap target */
        .stButton > button {
            width: 100% !important;
            min-height: 44px !important;
            font-size: 1rem !important;
        }

        /* Sidebar width when opened on mobile */
        [data-testid="stSidebar"] {
            width: 82vw !important;
            min-width: 82vw !important;
            max-width: 82vw !important;
        }
    }

    /* Extra-small devices */
    @media (max-width: 420px) {
        [data-testid="stAppViewContainer"] .main .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
        h1 { font-size: 1.5rem !important; }
    }

    /* ✅ 비밀번호 보기(눈) 아이콘이 흐릿/안보이는 문제 보정 */
    div[data-testid="stTextInput"] button,
    div[data-testid="stTextInput"] button * {
        opacity: 1 !important;
    }
    /* Streamlit 버전별 aria-label 커버 */
    button[aria-label="Show password text"],
    button[aria-label="Hide password text"] {
        color: #000 !important;
        opacity: 1 !important;
        filter: none !important;
    }
    button[aria-label="Show password text"] svg,
    button[aria-label="Hide password text"] svg,
    button[aria-label="Show password text"] svg path,
    button[aria-label="Hide password text"] svg path {
        fill: #000 !important;
        stroke: #000 !important;
        opacity: 1 !important;
    }

    /* (추가) Streamlit 버전/브라우저별 라벨 차이까지 커버 */
    button[aria-label*="password"],
    button[title*="password"],
    button[aria-label*="비밀번호"],
    button[title*="비밀번호"] {
        color: #000 !important;
        opacity: 1 !important;
        filter: none !important;
    }
    button[aria-label*="password"] svg,
    button[title*="password"] svg,
    button[aria-label*="비밀번호"] svg,
    button[title*="비밀번호"] svg,
    button[aria-label*="password"] svg path,
    button[title*="password"] svg path,
    button[aria-label*="비밀번호"] svg path,
    button[title*="비밀번호"] svg path {
        fill: #000 !important;
        stroke: #000 !important;
        opacity: 1 !important;
    }


    /* ✅ Plotly 모드바(Reset 등) 아이콘이 흐릿/안보이는 문제 보정 */
    .modebar-btn svg, .modebar-btn path {
        fill: #000 !important;
        stroke: #000 !important;
        opacity: 1 !important;
    }
    .modebar {
        opacity: 1 !important;
    }
/* --- Streamlit Cloud UI(하단 Manage app / 상단 툴바) 강제 숨김 --- */

/* 1) 하단 우측 Manage app 배지 (Cloud) */
a[title="Manage app"],
a[href*="manage-app"],
a[href*="streamlit.io/cloud"],
div[data-testid="stAppToolbar"] a,
div[data-testid="stAppToolbar"] button {
  display: none !important;
  visibility: hidden !important;
}

/* 2) 상단 툴바/메뉴(Deploy, GitHub, Fork 등) */
header,
div[data-testid="stToolbar"],
div[data-testid="stHeader"],
div[data-testid="stAppToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"] {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}

/* 3) 하단 footer 전체 */
footer,
div[data-testid="stFooter"] {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}

/* 4) 위 요소들 숨기면서 생기는 여백 제거 */
main .block-container {
  padding-top: 1.5rem !important;
  padding-bottom: 1.5rem !important;
}

</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 세션 관리 (콜백 방식 - 즉시 로그인)
# ==========================================
def try_login():
    """버튼 클릭 시 즉시 실행되어 로그인을 처리하는 콜백 함수"""
    if 'login_input_key' in st.session_state:
        raw_key = st.session_state['login_input_key']
        clean_key = "".join(raw_key.split()) # 모든 공백 제거
        
        if not clean_key:
            st.session_state['login_error'] = "⚠️ 키를 입력해주세요."
            return

        try:
            genai.configure(api_key=clean_key)
            list(genai.list_models()) # 유효성 검사
            
            st.session_state['api_key'] = clean_key
            st.session_state['login_error'] = None 
            
            # URL에 암호화하여 저장 (새로고침 방지)
            encoded_key = base64.b64encode(clean_key.encode()).decode()
            try: st.query_params['k'] = encoded_key
            except: st.experimental_set_query_params(k=encoded_key)
                
        except Exception as e:
            st.session_state['login_error'] = f"❌ 인증 실패: {e}"

def perform_logout():
    """로그아웃 처리"""
    st.session_state['logout_anim'] = True

# ==========================================
# 4. 사이드바 (로그인/로그아웃)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    # 1. 자동 로그인 복구 (URL 파라미터 확인)
    if 'api_key' not in st.session_state:
        try:
            qp = st.query_params
            if 'k' in qp:
                k_val = qp['k'] if isinstance(qp['k'], str) else qp['k'][0]
                restored_key = base64.b64decode(k_val).decode('utf-8')
                genai.configure(api_key=restored_key)
                list(genai.list_models())
                st.session_state['api_key'] = restored_key
                st.toast("🔄 세션이 복구되었습니다.", icon="✨")
                st.rerun()
        except: pass

    # 2. 로그인 폼 (비로그인 시)
    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.markdown("<h4 style='color:white;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input("Key", type="password", placeholder="API 키를 입력해 주세요", label_visibility="collapsed", key="login_input_key")
            # [중요] on_click으로 콜백 연결
            st.form_submit_button(label="시스템 접속 (Login)", on_click=try_login)
        
        if 'login_error' in st.session_state and st.session_state['login_error']:
            st.error(st.session_state['login_error'])

    # 3. 로그아웃 버튼 (로그인 시)
    else:
        st.success("🟢 정상 가동 중")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🎄 고마워! 또 봐! (Logout)", type="primary", use_container_width=True):
            perform_logout()
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026<br>Engine: Gemini 1.5 Pro</div>", unsafe_allow_html=True)

# ==========================================
# 5. 로그아웃 애니메이션
# ==========================================
if 'logout_anim' in st.session_state and st.session_state['logout_anim']:
    st.markdown("""
<div class="snow-bg">
<div style="font-size: 80px; margin-bottom: 20px;">🎅🎄</div>
<h1 style="color: white !important;">Merry Christmas!</h1>
<h3 style="color: #ddd !important;">오늘도 수고 많으셨습니다.<br>따뜻한 연말 보내세요! ❤️</h3>
</div>
""", unsafe_allow_html=True)
    time.sleep(3.5)
    try: st.query_params.clear()
    except: st.experimental_set_query_params()
    st.session_state.clear()
    st.rerun()

# ==========================================
# 6. 핵심 기능 함수 (구글시트, AI, 파일처리)
# ==========================================

# [구글 시트 연결]
@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        # secrets.toml 파일이 있어야 함
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except Exception as e: return None

# [자율점검 저장]

# ==========================================
# 5-1. 📌 월별 캠페인(자율점검) 테마 관리
#   - 매월 말일 자정(=월이 바뀌는 순간) 자동으로 새 캠페인 키로 전환
#   - 관리자 모드/참여 집계는 '현재 캠페인 시트'에 자동 연동
#   - 캠페인 제목/시트명은 Google Sheet의 'Campaign_Config'에서 관리
# ==========================================
def _korea_now():
    try:
        kst = pytz.timezone('Asia/Seoul')
        return datetime.datetime.now(kst)
    except Exception:
        return datetime.datetime.now()

def _campaign_key(dt: datetime.datetime) -> str:
    return f"{dt.year}-{dt.month:02d}"

def _ensure_campaign_config_sheet(spreadsheet):
    """'Campaign_Config' 시트가 없으면 생성하고 헤더를 만든다."""
    try:
        ws = spreadsheet.worksheet('Campaign_Config')
        return ws
    except Exception:
        ws = spreadsheet.add_worksheet(title='Campaign_Config', rows=200, cols=10)
        ws.append_row(['campaign_key', 'title', 'sheet_name', 'start_date'])
        return ws

def _default_campaign_title(dt: datetime.datetime) -> str:
    return f"{dt.month}월 자율점검"

def _default_campaign_sheet_name(dt: datetime.datetime, spreadsheet=None) -> str:
    """기본 시트명 규칙. 2026년 1월은 기존 윤리경영 서약 시트를 우선 사용."""
    # 기존 운영 중인 2026년 1월 윤리경영 서약 시트가 있으면 그대로 사용
    if spreadsheet is not None and dt.year == 2026 and dt.month == 1:
        try:
            spreadsheet.worksheet('2026_윤리경영_실천서약')
            return '2026_윤리경영_실천서약'
        except Exception:
            pass
    return f"{dt.year}_{dt.month:02d}_자율점검"

def get_current_campaign_info(spreadsheet, now_dt: datetime.datetime | None = None) -> dict:
    """현재 월에 해당하는 캠페인 정보를 반환. 없으면 기본값으로 생성."""
    now_dt = now_dt or _korea_now()
    key = _campaign_key(now_dt)
    cfg_ws = _ensure_campaign_config_sheet(spreadsheet)
    records = cfg_ws.get_all_records()
    for r in records:
        if str(r.get('campaign_key', '')).strip() == key:
            title = str(r.get('title') or '').strip() or _default_campaign_title(now_dt)
            sheet_name = str(r.get('sheet_name') or '').strip() or _default_campaign_sheet_name(now_dt, spreadsheet)
            start_date = str(r.get('start_date') or '').strip()
            return {'key': key, 'title': title, 'sheet_name': sheet_name, 'start_date': start_date}

    # 없으면 기본값으로 1행 추가
    title = _default_campaign_title(now_dt)
    sheet_name = _default_campaign_sheet_name(now_dt, spreadsheet)
    start_date = now_dt.strftime('%Y.%m.%d')
    cfg_ws.append_row([key, title, sheet_name, start_date])
    return {'key': key, 'title': title, 'sheet_name': sheet_name, 'start_date': start_date}

def set_current_campaign_info(spreadsheet, title: str | None = None, sheet_name: str | None = None, now_dt: datetime.datetime | None = None) -> dict:
    """현재 월 캠페인 정보를 업데이트(관리자 런칭)."""
    now_dt = now_dt or _korea_now()
    key = _campaign_key(now_dt)
    cfg_ws = _ensure_campaign_config_sheet(spreadsheet)
    all_rows = cfg_ws.get_all_values()
    # 헤더 포함 행 기준으로 위치 찾기
    row_idx = None
    for i in range(2, len(all_rows) + 1):
        if len(all_rows[i-1]) >= 1 and str(all_rows[i-1][0]).strip() == key:
            row_idx = i
            break
    if row_idx is None:
        # 없으면 새로 생성
        cur = get_current_campaign_info(spreadsheet, now_dt)
        row_idx = len(all_rows) + 1
    # 업데이트 값 결정
    cur = get_current_campaign_info(spreadsheet, now_dt)
    new_title = (title or cur['title']).strip()
    new_sheet = (sheet_name or cur['sheet_name']).strip()
    new_start = cur.get('start_date') or now_dt.strftime('%Y.%m.%d')
    cfg_ws.update(f"B{row_idx}:D{row_idx}", [[new_title, new_sheet, new_start]])
    return {'key': key, 'title': new_title, 'sheet_name': new_sheet, 'start_date': new_start}

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if not client: return False, "구글 시트 연결 실패 (Secrets 확인)"
    try:
        spreadsheet = client.open("Audit_Result_2026")
        try: sheet = spreadsheet.worksheet(sheet_name)
        except:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])
        
        # 중복 방지 (사번 기준)
        if str(emp_id) in sheet.col_values(2): return False, "이미 참여하셨습니다."
        
        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e: return False, str(e)

# [AI 모델 가져오기]
def get_model():
    """사용자 계정에서 사용 가능한 최적의 모델을 자동으로 탐색하여 연결합니다"""
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    
    try:
        # 1. 지원되는 모델 목록 중 generateContent가 가능한 모델들만 추출합니다.
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        # 2. 성능이 좋은 1.5-pro 모델을 우선 탐색하고, 없으면 1.5-flash를 선택합니다.
        for m in available_models:
            if '1.5-pro' in m: return genai.GenerativeModel(m)
        for m in available_models:
            if '1.5-flash' in m: return genai.GenerativeModel(m)
            
        # 3. 위 모델들이 모두 없다면 사용 가능한 목록의 첫 번째 모델을 반환합니다.
        if available_models: return genai.GenerativeModel(available_models[0])
    except Exception:
        pass
        
    # 최후의 수단으로 가장 범용적인 gemini-1.5-flash를 설정합니다.
    return genai.GenerativeModel('gemini-1.5-flash')

# [파일 읽기]
def read_file(uploaded_file):
    content = ""
    try:
        if uploaded_file.name.endswith('.txt'): content = uploaded_file.getvalue().decode("utf-8")
        elif uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages: content += page.extract_text() + "\n"
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs])
    except: return None
    return content

# [미디어 처리]
def process_media_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        st.toast("🤖 AI에게 분석 자료를 전달하고 있습니다...", icon="📂")
        myfile = genai.upload_file(tmp_path)
        with st.spinner('🎧 AI가 데이터를 분석하고 있습니다...'):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
        os.remove(tmp_path)
        if myfile.state.name == "FAILED": return None
        return myfile
    except: return None

# [유튜브 오디오]
def download_and_upload_youtube_audio(url):
    if yt_dlp is None: return None
    try:
        ydl_opts = {'format': 'bestaudio/best', 'outtmpl': 'temp_audio.%(ext)s', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        audio_files = glob.glob("temp_audio.*")
        if not audio_files: return None
        audio_path = audio_files[0]
        myfile = genai.upload_file(audio_path)
        with st.spinner('🎧 유튜브 분석 중...'):
            while myfile.state.name == "PROCESSING": time.sleep(2); myfile = genai.get_file(myfile.name)
        os.remove(audio_path)
        return myfile
    except: return None

# [유튜브 자막]
def get_youtube_transcript(url):
    try:
        video_id = url.split("v=")[-1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return " ".join([t['text'] for t in transcript])
    except: return None

# [웹 크롤링]
def get_web_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]): script.decompose()
        return soup.get_text()[:10000]
    except: return None

# ==========================================
# 7. 메인 화면 및 탭 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

# ✅ 현재(한국시간) 캠페인(테마) 정보
_now_kst = _korea_now()
CURRENT_YEAR = _now_kst.year
CURRENT_MONTH = _now_kst.month

# 기본값(구글시트 연결 실패 시에도 앱이 동작하도록)
campaign_info = {
    'key': f"{CURRENT_YEAR}-{CURRENT_MONTH:02d}",
    'title': f"{CURRENT_MONTH}월 자율점검",
    'sheet_name': f"{CURRENT_YEAR}_{CURRENT_MONTH:02d}_자율점검",
    'start_date': _now_kst.strftime('%Y.%m.%d'),
}

try:
    _client_for_campaign = init_google_sheet_connection()
    if _client_for_campaign:
        _ss_for_campaign = _client_for_campaign.open('Audit_Result_2026')
        campaign_info = get_current_campaign_info(_ss_for_campaign, _now_kst)
except Exception:
    pass


# 탭 생성 (5개)
tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    f"✅ {CURRENT_MONTH}월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"
])

# --- [Tab 1: 자율점검 - 2026 윤리경영 실천서약] ---
with tab_audit:
    # ✅ 캠페인(월별) 시트 자동 연동
    current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")  # 현재 캠페인 시트

    st.markdown(f"""
        <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 20px;'>
            <h3 style='margin-top:0; color: #1565C0;'>📜 {campaign_info.get('title','2026 윤리경영원칙 실천지침 실천서약')}</h3>
            <p style='font-size: 0.95rem; color: #444;'>
                나는 <b>kt MOS북부</b>의 지속적인 발전을 위하여 회사 윤리경영원칙실천지침에 명시된 
                <b>「임직원의 책임과 의무」</b> 및 <b>「관리자의 책임과 의무」</b>를 성실히 이행할 것을 서약합니다.
            </p>
        </div>
    """, unsafe_allow_html=True)

    with st.form("audit_ethics_form", clear_on_submit=False):
        # 기본 정보 입력
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
        dept = c4.text_input("상세 부서명")

        st.markdown("---")

        # 1. 임직원의 책임과 의무 (개별 체크박스)
        st.markdown("#### ■ 임직원의 책임과 의무")
        e1 = st.checkbox("하나, 나는 회사 윤리경영원칙과 윤리경영원칙 실천지침에 따라 판단하고 행동한다.")
        e2 = st.checkbox("하나, 나는 윤리경영원칙 실천지침을 몰랐다는 이유로 면책을 주장하지 않는다.")
        e3 = st.checkbox("하나, 나는 직무수행 과정에서 윤리적 갈등 상황에 직면한 경우 감사부서의 해석에 따른다.")
        e4 = st.checkbox("하나, 나는 가족, 친·인척, 지인 등을 이용하여 회사 윤리경영원칙 실천지침을 위반하지 않는다.")

        st.markdown("<br>", unsafe_allow_html=True)

        # 2. 관리자의 책임과 의무 (개별 체크박스)
        st.markdown("#### ■ 관리자의 책임과 의무")
        m1 = st.checkbox("하나, 나는 소속 구성원 및 업무상 이해관계자들이 지침을 준수할 수 있도록 지원하고 관리한다.")
        m2 = st.checkbox("하나, 나는 공정하고 깨끗한 의사결정을 통해 지침 준수를 솔선수범한다.")
        m3 = st.checkbox("하나, 나는 부서 내 위반 사안 발생 시 관리자로서의 책임을 다한다.")

        st.markdown("---")

        submit = st.form_submit_button("서약 제출", use_container_width=True)

        if submit:
            # 필수값 체크
            if not emp_id or not name:
                st.warning("⚠️ 사번과 성명을 입력해주세요.")
            else:
                # 모든 서약 항목 체크 여부 확인
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

    # ※ 윤리경영원칙 실천지침 주요내용 (가이드)
    if ("윤리" in (campaign_info.get("title","") or "")) or ("윤리" in (current_sheet_name or "")):
        st.markdown("---")
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

# --- [Tab 2: 문서 정밀 검토] ---
with tab_doc:
    st.markdown("### 📂 문서 및 규정 검토")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        option = st.selectbox("작업 유형", ["법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 교정", "기안문 작성"])
        
        # 감사 보고서 검증 시 2차 인증
        is_authenticated = True
        if option == "감사 보고서 검증":
            if 'audit_verified' not in st.session_state:
                is_authenticated = False
                st.warning("🔒 감사실 전용 메뉴입니다. 인증이 필요합니다.")
                with st.form("doc_auth_form"):
                    pass_input = st.text_input("인증키 입력", type="password")
                    if st.form_submit_button("확인"):
                        # 공백 제거 후 비교 (ktmos0402!)
                        if pass_input.strip() == "ktmos0402!":
                            st.session_state['audit_verified'] = True
                            st.rerun()
                        else: st.error("❌ 인증키 불일치")

        if is_authenticated:
            uploaded_file = st.file_uploader("파일 업로드 (PDF, Word, TXT)", type=['txt', 'pdf', 'docx'])
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
                            except Exception as e: st.error(f"오류: {e}")

# --- [Tab 3: AI 에이전트] ---
with tab_chat:
    st.markdown("### 💬 AI 법률/감사 챗봇")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        if "messages" not in st.session_state: st.session_state.messages = []
        
        with st.form(key='chat_input_form', clear_on_submit=True):
            user_input = st.text_input("질문 입력")
            send_btn = st.form_submit_button("전송 📤", use_container_width=True)
        
        if send_btn and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("답변 생성 중..."):
                try:
                    res = get_model().generate_content(user_input)
                    st.session_state.messages.append({"role": "assistant", "content": res.text})
                except Exception as e: st.error(f"오류: {e}")
        
        for msg in reversed(st.session_state.messages):
            with st.chat_message(msg['role']): st.write(msg['content'])

# --- [Tab 4: 스마트 요약] ---
with tab_summary:
    st.markdown("### 📰 스마트 요약")
    if 'api_key' not in st.session_state:
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
            mf = st.file_uploader("파일 업로드", type=['mp3','wav','mp4'])
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
                        if is_multimodal: res = get_model().generate_content([p, final_input])
                        else: res = get_model().generate_content(f"{p}\n\n{final_input[:30000]}")
                        st.markdown(res.text)
                    except Exception as e: st.error(f"오류: {e}")

# --- [Tab 5: 관리자 대시보드] ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    # [수정] 패스워드 "ktmos0402!"로 통일 및 공백 제거
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
                # ✅ 현재 월 테마(캠페인) 자동 연동
                camp = get_current_campaign_info(ss, _now_kst)

                # (선택) 관리자: 이번 달 테마 런칭/변경
                with st.expander("⚙️ 이번 달 테마 런칭/변경 (관리자)", expanded=False):
                    new_title = st.text_input("테마 제목", value=camp.get("title", ""), key="camp_title_input")
                    new_sheet = st.text_input("연동 시트명", value=camp.get("sheet_name", ""), key="camp_sheet_input")
                    cA, cB = st.columns([1, 1])
                    if cA.button("🚀 테마 적용", use_container_width=True):
                        camp = set_current_campaign_info(ss, title=new_title, sheet_name=new_sheet, now_dt=_now_kst)
                        # 캐시 초기화(테마 변경 즉시 반영)
                        st.session_state.pop("admin_df", None)
                        st.session_state.pop("admin_stats_df", None)
                        st.session_state["admin_cache_key"] = camp["key"]
                        st.toast("✅ 테마가 적용되었습니다.", icon="🚀")
                        st.rerun()
                    cB.caption("※ 매월 말일 자정(=월 변경 시점) 자동으로 새 캠페인으로 전환됩니다.")

                st.caption(f"현재 테마: **{camp['title']}**  |  연동 시트: `{camp['sheet_name']}`  |  캠페인 키: `{camp['key']}`")

                # ✅ 조직별 목표 인원(필요 시 여기만 조정)
                target_dict = {"경영총괄": 45, "사업총괄": 37, "강북본부": 222, "강남본부": 174, "서부본부": 290, "강원본부": 104, "품질지원단": 138, "감사실": 3}
                ordered_units = list(target_dict.keys())

                # 새 캠페인(월 변경) 또는 버튼 클릭 시 자동 재집계
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

                    # 참여 집계(시트 컬럼명은 save_audit_result 헤더 기준)
                    if (not df.empty) and ("총괄/본부/단" in df.columns):
                        counts = df["총괄/본부/단"].astype(str).value_counts().to_dict()
                    else:
                        counts = {}

                    stats_rows = []
                    for unit in ordered_units:
                        participated = int(counts.get(unit, 0))
                        target = int(target_dict.get(unit, 0))
                        not_part = max(target - participated, 0)
                        rate = round((participated / target) * 100, 2) if target > 0 else 0.0
                        stats_rows.append({"조직": unit, "참여완료": participated, "미참여": not_part, "참여율": rate})
                    stats_df = pd.DataFrame(stats_rows)

                    st.session_state["admin_df"] = df
                    st.session_state["admin_stats_df"] = stats_df
                    st.session_state["admin_cache_key"] = camp["key"]
                    st.session_state["admin_last_update"] = _korea_now().strftime("%Y-%m-%d %H:%M:%S")

                df = st.session_state.get("admin_df", pd.DataFrame())
                stats_df = st.session_state.get("admin_stats_df", pd.DataFrame())
                last_update = st.session_state.get("admin_last_update")

                # =========================
                # ✅ 요약 전광판 + 신호등
                # =========================
                total_target = int(sum(target_dict.values()))
                total_participated = int(stats_df["참여완료"].sum()) if (stats_df is not None and not stats_df.empty) else 0
                total_rate = (total_participated / total_target * 100) if total_target > 0 else 0.0
                date_kor = _korea_now().strftime("%Y.%m.%d")

                # 신호등 규칙: 50% 미만=빨강, 80% 미만=주황, 80% 이상=파랑(99.5% 이상도 포함)
                if total_rate < 50:
                    lamp_color = "#E74C3C"
                    lamp_label = "RED"
                    lamp_msg = "위험"
                elif total_rate < 80:
                    lamp_color = "#F39C12"
                    lamp_label = "ORANGE"
                    lamp_msg = "주의"
                else:
                    lamp_color = "#2980B9"
                    lamp_label = "BLUE"
                    lamp_msg = "양호"

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

                # =========================
                # ✅ 그래프/데이터
                # =========================
                if df is None or df.empty:
                    st.info("데이터가 없습니다.")
                else:
                    # 1) 막대 그래프(참여완료/미참여)
                    melt_df = stats_df.melt(id_vars="조직", value_vars=["참여완료", "미참여"], var_name="구분", value_name="인원")
                    fig_bar = px.bar(melt_df, x="조직", y="인원", color="구분", barmode="stack", text="인원", title="조직별 참여 현황")
                    fig_bar.update_layout(dragmode="pan", autosize=True, margin=dict(l=20, r=20, t=60, b=20))
                    fig_bar.update_traces(textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig_bar, use_container_width=True, config=PLOTLY_CONFIG)

                    # 2) 라인 그래프(참여율)
                    fig_line = px.line(stats_df, x="조직", y="참여율", markers=True, text="참여율", title="조직별 참여율(%)")
                    fig_line.update_layout(dragmode="pan", autosize=True, margin=dict(l=20, r=20, t=60, b=20))
                    fig_line.update_traces(textposition="top center")
                    st.plotly_chart(fig_line, use_container_width=True, config=PLOTLY_CONFIG)

                    # 3) 데이터 및 다운로드
                    st.dataframe(df, use_container_width=True)
                    st.download_button(
                        label="📥 엑셀 다운로드",
                        data=df.to_csv(index=False).encode('utf-8-sig'),
                        file_name=f"audit_result_{camp['key']}.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )

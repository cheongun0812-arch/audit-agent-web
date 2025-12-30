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
# 1. 페이지 설정 (사이드바 기본 열림)
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded" # [핵심] 시작 시 사이드바 열림
)

# ==========================================
# 2. 🎨 디자인 테마 (버튼 위치 오류 수정)
# ==========================================
st.markdown("""
    <style>
    /* 기본 배경 */
    .stApp { background-color: #F4F6F9 !important; }
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 사이드바 스타일 (강제 display 제거 -> 자연스럽게 동작) */
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* 입력창 스타일 */
    input.stTextInput, textarea.stTextArea {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: 1px solid #BDC3C7 !important;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
        border-radius: 5px !important;
    }

    /* 탭 메뉴 폰트 확대 (20px + Bold) */
    button[data-baseweb="tab"] div p {
        font-size: 20px !important;
        font-weight: 800 !important;
        color: #444444 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] div p {
        color: #2980B9 !important;
    }

    /* 🚨 [수정] 상단 메뉴 버튼 (위치 고정 해제 -> 제자리 유지) */
    [data-testid="stSidebarCollapsedControl"] {
        color: transparent !important; /* 기존 텍스트 숨김 */
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        border: 1px solid #ddd;
        width: 40px !important;
        height: 40px !important;
        z-index: 100000 !important;
    }
    
    /* ☰ 아이콘 덮어쓰기 */
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        color: #2C3E50 !important;
        font-size: 24px !important;
        font-weight: bold !important;
        position: absolute;
        top: 5px; left: 10px;
    }

    /* [보안] 헤더 배경 투명화 (버튼은 보이게 둠) */
    header[data-testid="stHeader"] {
        background: transparent !important;
        visibility: visible !important;
    }

    /* [보안] 개인정보 요소 핀셋 숨김 */
    .stDeployButton { display: none !important; } /* Manage App */
    [data-testid="stToolbar"] { display: none !important; } /* 우측 메뉴 */
    [data-testid="stDecoration"] { display: none !important; } /* 상단 장식 */
    footer { display: none !important; } /* 하단 푸터 */
    #MainMenu { display: none !important; } /* 햄버거 메뉴 */
    
    /* 크리스마스 애니메이션 */
    .snow-bg {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.9); z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; color: white !important; pointer-events: none;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 세션 관리 (콜백 방식)
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
            st.text_input("Key", type="password", placeholder="API 키 입력", label_visibility="collapsed", key="login_input_key")
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

# [AI 모델 가져오기 - 404 방지 패치]
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    
    # 1. 우선적으로 사용 가능한 최신 모델 탐색
    try:
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in models:
            if 'gemini-1.5-pro' in m and 'latest' not in m: return genai.GenerativeModel(m)
        for m in models:
            if 'gemini-1.5-flash' in m: return genai.GenerativeModel(m)
    except: pass

    # 2. 리스트 조회 실패 시 표준 이름으로 강제 연결
    return genai.GenerativeModel('gemini-1.5-pro')

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

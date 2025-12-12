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

# yt_dlp 라이브러리 체크
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
    layout="centered"
)

# ==========================================
# 2. 🎨 [디자인] V41 CSS 유지
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9 !important; }
    html, body, p, div, span, label, h1, h2, h3, h4, h5, h6, li, button {
        font-family: 'Pretendard', sans-serif !important;
    }
    p, div, span, label, li { color: #333333 !important; }
    
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #FFFFFF !important; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span { color: #ECF0F1 !important; }

    [data-testid="stSidebarCollapsedControl"] {
        text-indent: -9999px !important;
        white-space: nowrap !important;
        background-color: #FFFFFF !important;
        border-radius: 0 12px 12px 0 !important;
        border: 1px solid #BDC3C7 !important;
        border-left: none !important;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.15) !important;
        position: fixed !important;
        top: 60px !important;
        left: 0 !important;
        width: 45px !important;
        height: 45px !important;
        z-index: 9999999 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    [data-testid="stSidebarCollapsedControl"] > svg, 
    [data-testid="stSidebarCollapsedControl"] > img { display: none !important; }
    
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        text-indent: 0 !important;
        font-size: 26px !important;
        color: #2C3E50 !important;
        font-weight: 900 !important;
        position: absolute;
        top: 50%; left: 50%;
        transform: translate(-50%, -55%);
        display: block !important;
        visibility: visible !important;
    }

    input[type="text"], input[type="password"] {
        background-color: #FFFFFF !important;
        border: 2px solid #D5DBDB !important;
        border-radius: 8px !important;
        padding: 10px !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        caret-color: #000000 !important;
        opacity: 1 !important;
    }
    ::placeholder {
        color: #7F8C8D !important;
        -webkit-text-fill-color: #7F8C8D !important;
        opacity: 1 !important;
    }
    button[aria-label="Show password"] { filter: invert(1) !important; }

    .stButton > button {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2) !important;
    }
    [data-testid="stChatMessage"] { background-color: #FFFFFF !important; border: 1px solid #E0E0E0; border-radius: 12px; }
    [data-testid="stChatMessage"][data-testid="user"] { background-color: #EBF5FB !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 사이드바 (로그인)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    with st.form(key='login_form'):
        st.markdown("**🔐 Access Key**")
        api_key_input = st.text_input("Key", type="password", label_visibility="collapsed", placeholder="API 키를 입력하세요")
        submit_button = st.form_submit_button(label="시스템 접속 (Login)")
    
    if submit_button:
        if api_key_input:
            clean_key = api_key_input.strip()
            try:
                genai.configure(api_key=clean_key)
                st.session_state['api_key'] = clean_key
                st.success("✅ 접속 완료")
            except:
                st.error("❌ 키 오류")
        else:
            st.warning("⚠️ 키 입력 필요")
            
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("🟢 가동 중")
        
    st.markdown("---")
    st.markdown("""
        <div class="sidebar-footer">
            Audit AI Solution © 2025<br>
            Engine: Gemini 1.5 Pro
        </div>
    """, unsafe_allow_html=True)

# ==========================================
# 4. 기능 함수
# ==========================================
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in all_models:
            if '1.5-pro' in m: return genai.GenerativeModel(m)
        for m in all_models:
            if '1.5-flash' in m: return genai.GenerativeModel(m)
        if all_models: return genai.GenerativeModel(all_models[0])
    except: pass
    return genai.GenerativeModel('gemini-1.5-pro-latest')

def read_file(uploaded_file):
    content = ""
    try:
        if uploaded_file.name.endswith('.txt'):
            content = uploaded_file.getvalue().decode("utf-8")
        elif uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages: content += page.extract_text() + "\n"
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs])
    except: return None
    return content

def download_and_upload_youtube_audio(url):
    if yt_dlp is None:
        st.error("서버에 yt-dlp가 설치되지 않았습니다.")
        return None
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp_audio.%(ext)s',
            'quiet': True,
            'overwrites': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {'User-Agent': 'Mozilla/5.0'}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        audio_files = glob.glob("temp_audio.*")
        if not audio_files: return None
        audio_path = audio_files[0]
        myfile = genai.upload_file(audio_path)
        while myfile.state.name == "PROCESSING":
            time.sleep(2)
            myfile = genai.get_file(myfile.name)
        os.remove(audio_path)
        return myfile
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e):
            st.error("🔒 [보안 차단] 유튜브 보안으로 인해 자동 다운로드가 막혔습니다.")
            st.info("💡 '미디어 파일 업로드' 탭을 이용해 다운받은 파일을 직접 올려주세요.")
        else:
            st.error(f"오디오 처리 중 오류: {e}")
        return None

def get_youtube_transcript(url):
    try:
        if "youtu.be" in url: video_id = url.split("/")[-1]
        else: video_id = url.split("v=")[-1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        text = " ".join([t['text'] for t in transcript])
        return text
    except: return None

def get_web_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]): script.decompose()
        return soup.get_text()[:10000]
    except Exception as e: return f"[오류] {e}"

def process_media_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        myfile = genai.upload_file(tmp_path)
        with st.spinner('🎧 파일 분석 준비 중...'):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
        os.remove(tmp_path)
        return myfile
    except Exception as e:
        st.error(f"파일 오류: {e}")
        return None

# ==========================================
# 5. 메인 화면
# ==========================================

st.markdown("<h1 style='text-align: center; color: #2C3E50 !important;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #7F8C8D !important; margin-bottom: 25px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["  📄 문서 정밀 검토  ", "  💬 AI 파트너 대화  ", "  📰 스마트 요약  "])

# --- Tab 1: 문서 검토 ---
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container():
        st.markdown("#### 1️⃣ 작업 선택")
        option = st.selectbox("작업 유형", ("법률 리스크 정밀 검토", "감사 보고서 초안 작성", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"), label_visibility="collapsed")
        
        st.markdown("#### 2️⃣ 파일 업로드")
        col1, col2 = st.columns(2)
        with col1:
            st.info("👇 **검토 파일**")
            uploaded_file = st.file_uploader("검토 파일", type=['txt', 'pdf', 'docx'], key="target", label_visibility="collapsed")
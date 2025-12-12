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
# 2. 🎨 [디자인] V40~42 디자인 유지
# ==========================================
st.markdown("""
    <style>
    /* 1. 기본 배경 */
    .stApp { background-color: #F4F6F9 !important; }
    
    /* 2. 폰트 강제 적용 */
    html, body, p, div, span, label, h1, h2, h3, h4, h5, h6, li, button {
        font-family: 'Pretendard', sans-serif !important;
    }

    /* 3. 사이드바 배경 */
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }

    /* 입력창 글씨 색상: 진한 회색 */
    input.stTextInput {
        background-color: #FFFFFF !important;
        color: #333333 !important;
        -webkit-text-fill-color: #333333 !important;
        caret-color: #333333 !important;
    }
    ::placeholder {
        color: #888888 !important;
        -webkit-text-fill-color: #888888 !important;
        opacity: 1 !important;
    }

    /* 버튼 글씨: 흰색 */
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }

    /* 사이드바 하단 정보: 흰색 */
    .sidebar-footer {
        color: #FFFFFF !important;
        text-align: center;
        font-size: 12px;
        opacity: 0.9;
        margin-top: 50px;
    }
    
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p {
        color: #FFFFFF !important;
    }

    /* 상단 메뉴 버튼: 글씨 숨기고 아이콘만 */
    [data-testid="stSidebarCollapsedControl"] {
        color: transparent !important;
        background-color: #FFFFFF !important;
        border-radius: 0 12px 12px 0 !important;
        width: 40px !important;
        height: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        color: #2C3E50 !important;
        font-size: 24px !important;
        font-weight: bold !important;
        position: absolute;
    }
    
    /* 채팅 메시지 박스 */
    [data-testid="stChatMessage"] { background-color: #FFFFFF !important; border-radius: 12px; }
    [data-testid="stChatMessage"] p { color: #333333 !important; }
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
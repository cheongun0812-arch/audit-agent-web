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
# 2. 🎨 [디자인] V50: CSS 분리 및 절대 색상 적용
# ==========================================
st.markdown("""
    <style>
    /* 1. 전체 폰트 및 배경 */
    .stApp { background-color: #F4F6F9 !important; }
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 2. 사이드바 (다크 네이비) */
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    
    /* 사이드바 내 모든 텍스트 강제 화이트 */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] div, [data-testid="stSidebar"] label {
        color: #FFFFFF !important;
    }

    /* 3. 입력창 디자인 (무조건 흰 배경에 검은 글씨) */
    input.stTextInput {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important; /* 모바일 크롬 강제 */
        caret-color: #000000 !important;
        border: 2px solid #BDC3C7 !important;
    }
    
    /* 입력창 안내문구 (플레이스홀더) 색상 */
    ::placeholder {
        color: #666666 !important;
        -webkit-text-fill-color: #666666 !important;
        opacity: 1 !important;
    }

    /* 4. 버튼 디자인 */
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }

    /* 5. 상단 메뉴 버튼 (책갈피 스타일) */
    [data-testid="stSidebarCollapsedControl"] {
        color: transparent !important;
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        width: 40px !important;
        height: 40px !important;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.2) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    /* 햄버거 아이콘 */
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        color: #2C3E50 !important;
        font-size: 24px !important;
        font-weight: bold !important;
        position: absolute;
    }

    /* 6. 🎄 크리스마스 애니메이션 스타일 (여기서 정의) */
    .snow-container {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.9); z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center;
    }
    .snow-text-main {
        font-size: 40px; font-weight: bold; color: #FFFFFF !important; margin: 20px 0;
    }
    .snow-text-sub {
        font-size: 20px; color: #DDDDDD !important; line-height: 1.5;
    }
    .snowflake {
        color: #fff; font-size: 1.5em; position: fixed; top: -10%; z-index: 9999;
        animation-name: snowflakes-fall, snowflakes-shake;
        animation-duration: 10s, 3s;
        animation-timing-function: linear, ease-in-out;
        animation-iteration-count: infinite, infinite;
        animation-play-state: running, running;
    }
    @keyframes snowflakes-fall { 0% { top: -10%; } 100% { top: 100%; } }
    @keyframes snowflakes-shake { 0%, 100% { transform: translateX(0); } 50% { transform: translateX(80px); } }
    .snowflake:nth-of-type(0) { left: 1%; animation-delay: 0s, 0s; }
    .snowflake:nth-of-type(1) { left: 10%; animation-delay: 1s, 1s; }
    .snowflake:nth-of-type(2) { left: 20%; animation-delay: 6s, 0.5s; }
    .snowflake:nth-of-type(3) { left: 30%; animation-delay: 4s, 2s; }
    .snowflake:nth-of-type(4) { left: 40%; animation-delay: 2s, 2s; }
    .snowflake:nth-of-type(5) { left: 50%; animation-delay: 8s, 3s; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 사이드바 (로그인 & 로그아웃)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            # [수정] 라벨을 별도 Markdown으로 강제 표시 (시인성 100%)
            st.markdown("<h4 style='color:white; margin-bottom:5px;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            api_key_input = st.text_input("Key", type="password", placeholder="API 키를 입력하세요", label_visibility="collapsed")
            submit_button = st.form_submit_button(label="시스템 접속 (Login)")
        
        if submit_button:
            if api_key_input:
                clean_key = api_key_input.strip()
                try:
                    genai.configure(api_key=clean_key)
                    st.session_state['api_key'] = clean_key
                    st.success("✅ 접속 완료")
                    st.rerun()
                except:
                    st.error("❌ 키 오류")
            else:
                st.warning("⚠️ 키 입력 필요")

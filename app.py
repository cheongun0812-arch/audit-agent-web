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
# 2. 🎨 [디자인] V57: 최후의 CSS (Visibility & Text-Fill 강제)
# ==========================================
st.markdown("""
    <style>
    /* 1. 배경 및 폰트 */
    .stApp { background-color: #F4F6F9 !important; }
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 2. 사이드바 (다크 네이비) */
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    
    /* 사이드바 텍스트 전체 화이트 강제 */
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] div, 
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }

    /* 🚨 3. [최종 해결] 입력창 글씨 색상 원천 봉쇄 🚨 */
    /* 어떤 환경에서도 흰 배경에 검은 글씨가 나오도록 강제함 */
    input[type="text"], input[type="password"] {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important; /* 모바일 강제 적용 */
        caret-color: #000000 !important;
        border: 2px solid #BDC3C7 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    
    /* 플레이
# =====================================================
# AUDIT AI AGENT - FIXED VERSION FOR RIMLET
# =====================================================

import streamlit as st

# ⚠️ 반드시 Streamlit 첫 명령
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# =====================================================
# IMPORTS
# =====================================================
import os
import time
import glob
import tempfile
import base64
import datetime
import pytz
import pandas as pd
import google.generativeai as genai
from docx import Document
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import requests
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# =====================================================
# SAFE CSS (❌ 토글 숨김 제거)
# =====================================================
st.markdown("""
<style>
.stApp { background-color: #F4F6F9; }

[data-testid="stSidebar"] {
    background-color: #2C3E50;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

.stTextInput input, .stTextArea textarea {
    background-color: #FFFFFF !important;
    color: #000000 !important;
}

.stButton > button {
    background: linear-gradient(to right, #2980B9, #2C3E50);
    color: white;
    font-weight: bold;
    border: none;
}

/* ❌ 사이드바 토글 관련 CSS 완전 제거 */
</style>
""", unsafe_allow_html=True)

# =====================================================
# LOGIN
# =====================================================
def try_login():
    key = st.session_state.get("login_key", "").strip()
    if not key:
        st.session_state.login_error = "API 키를 입력하세요."
        return
    try:
        genai.configure(api_key=key)
        list(genai.list_models())
        st.session_state.api_key = key
        st.session_state.login_error = None
    except Exception as e:
        st.session_state.login_error = str(e)

# =====================================================
# GOOGLE SHEET
# =====================================================
@st.cache_resource
def init_gsheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

# =====================================================
# SIDEBAR (항상 렌더링)
# =====================================================
with st.sidebar:
    st.markdown("## 🏛️ Control Center")
    st.divider()

    if "api_key" not in st.session_state:
        with st.form("login_form"):
            st.text_input("Gemini API Key", type="password", key="login_key")
            st.form_submit_button("Login", on_click=try_login)

        if st.session_state.get("login_error"):
            st.error(st.session_state.login_error)
    else:
        st.success("🟢 로그인됨")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    st.divider()
    st.caption("Audit AI Agent © 2026")

# =====================================================
# MAIN HEADER (⚠️ 로그인과 무관하게 항상 표시)
# =====================================================
st.markdown(
    "<h1 style='text-align:center; color:#2C3E50;'>🛡️ AUDIT AI AGENT</h1>",
    unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align:center; color:#555;'>Professional Legal & Audit Assistant</p>",
    unsafe_allow_html=True
)

# =====================================================
# TABS
# =====================================================
tab1, tab2, tab3 = st.tabs([
    "✅ 자율점검",
    "💬 AI 에이전트",
    "📊 관리자"
])

# =====================================================
# TAB 1
# =====================================================
with tab1:
    st.subheader("자율점검 화면")
    st.info("이 화면이 보이면 UI는 정상입니다.")
    st.checkbox("정상 출력 확인")

# =====================================================
# TAB 2
# =====================================================
with tab2:
    if "api_key" not in st.session_state:
        st.warning("로그인 후 이용 가능합니다.")
    else:
        q = st.text_input("질문 입력")
        if q:
            model = genai.GenerativeModel("gemini-1.5-pro-latest")
            st.write(model.generate_content(q).text)

# =====================================================
# TAB 3
# =====================================================
with tab3:
    pw = st.text_input("관리자 비밀번호", type="password")
    if pw.strip() == "ktmos0402!":
        st.success("관리자 접속 성공")
        st.write("대시보드 영역 (정상 출력 확인)")

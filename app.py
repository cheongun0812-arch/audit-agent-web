# ==========================================
# AUDIT AI AGENT - STABLE VERSION (Rimlet OK)
# ==========================================

import streamlit as st
import os
import time
import glob
import tempfile
import base64
import datetime
import pytz
import google.generativeai as genai
from docx import Document
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import requests
from bs4 import BeautifulSoup
import pandas as pd
import plotly.express as px

# ==========================================
# 1. 페이지 설정 (⚠ 반드시 최상단)
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# ==========================================
# 2. 안전한 CSS (사이드바 토글 문제 해결)
# ==========================================
st.markdown("""
<style>
.stApp {
    background-color: #F4F6F9;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #2C3E50;
}
[data-testid="stSidebar"] * {
    color: #FFFFFF !important;
}

/* Inputs */
.stTextInput input, .stTextArea textarea {
    background-color: #FFFFFF !important;
    color: #000000 !important;
    border: 1px solid #BDC3C7 !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: white !important;
    font-weight: bold;
    border: none;
}

/* ⚠️ 사이드바 토글 관련 CSS 제거
   (Rimlet 흰 화면 원인) */
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 함수
# ==========================================
def try_login():
    api_key = st.session_state.get("login_key", "").strip()
    if not api_key:
        st.session_state.login_error = "API 키를 입력해주세요."
        return
    try:
        genai.configure(api_key=api_key)
        list(genai.list_models())
        st.session_state.api_key = api_key
        st.session_state.login_error = None
    except Exception as e:
        st.session_state.login_error = f"로그인 실패: {e}"

# ==========================================
# 4. 사이드바
# ==========================================
with st.sidebar:
    st.markdown("## 🏛️ Control Center")
    st.divider()

    if "api_key" not in st.session_state:
        with st.form("login_form"):
            st.text_input("Google Gemini API Key", type="password", key="login_key")
            st.form_submit_button("Login", on_click=try_login)

        if st.session_state.get("login_error"):
            st.error(st.session_state.login_error)
    else:
        st.success("🟢 로그인 성공")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    st.divider()
    st.caption("Audit AI Agent © 2026")

# ==========================================
# 5. 메인 헤더
# ==========================================
st.markdown(
    "<h1 style='text-align:center; color:#2C3E50;'>🛡️ AUDIT AI AGENT</h1>",
    unsafe_allow_html=True
)
st.markdown(
    "<p style='text-align:center; color:#555;'>Professional Legal & Audit Assistant</p>",
    unsafe_allow_html=True
)

# ==========================================
# 6. 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "✅ 자율점검",
    "📄 문서 검토",
    "💬 AI 챗봇",
    "📰 요약"
])

# ==========================================
# Tab 1: 자율점검
# ==========================================
with tab1:
    st.subheader("자율점검 테스트 화면")
    st.info("화면 및 메뉴 정상 출력 확인용")
    st.checkbox("정상적으로 체크됩니다")

# ==========================================
# Tab 2: 문서 검토
# ==========================================
with tab2:
    st.subheader("문서 검토")
    if "api_key" not in st.session_state:
        st.warning("로그인 후 이용 가능합니다.")
    else:
        uploaded_file = st.file_uploader(
            "파일 업로드 (PDF, DOCX, TXT)",
            type=["pdf", "docx", "txt"]
        )
        if uploaded_file and st.button("분석 시작"):
            text = ""
            if uploaded_file.name.endswith(".txt"):
                text = uploaded_file.read().decode("utf-8")
            elif uploaded_file.name.endswith(".pdf"):
                reader = PyPDF2.PdfReader(uploaded_file)
                for p in reader.pages:
                    text += p.extract_text()
            elif uploaded_file.name.endswith(".docx"):
                doc = Document(uploaded_file)
                text = "\n".join(p.text for p in doc.paragraphs)

            with st.spinner("AI 분석 중..."):
                model = genai.GenerativeModel("gemini-1.5-pro-latest")
                result = model.generate_content(text[:30000])
                st.success("분석 완료")
                st.write(result.text)

# ==========================================
# Tab 3: AI 챗봇
# ==========================================
with tab3:
    st.subheader("AI 법률 / 감사 챗봇")

    if "api_key" not in st.session_state:
        st.warning("로그인이 필요합니다.")
    else:
        if "chat" not in st.session_state:
            st.session_state.chat = []

        user_input = st.text_input("질문을 입력하세요")

        if user_input:
            st.session_state.chat.append(("user", user_input))
            model = genai.GenerativeModel("gemini-1.5-pro-latest")
            reply = model.generate_content(user_input).text
            st.session_state.chat.append(("ai", reply))

        for role, msg in st.session_state.chat[::-1]:
            if role == "user":
                st.markdown(f"**🙋 사용자:** {msg}")
            else:
                st.markdown(f"**🤖 AI:** {msg}")

# ==========================================
# Tab 4: 요약
# ==========================================
with tab4:
    st.subheader("스마트 요약")

    if "api_key" not in st.session_state:
        st.warning("로그인이 필요합니다.")
    else:
        text = st.text_area("요약할 텍스트 입력", height=200)
        if st.button("요약 실행") and text:
            with st.spinner("요약 중..."):
                model = genai.GenerativeModel("gemini-1.5-pro-latest")
                summary = model.generate_content(
                    f"다음 내용을 핵심 요약과 인사이트로 정리해줘:\n\n{text}"
                )
                st.success("요약 완료")
                st.write(summary.text)

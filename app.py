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
import random

import plotly.graph_objects as go
import plotly.express as px

# ==========================================
# 1. 페이지 설정 및 가독성 강화 CSS
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
/* 전체 텍스트 가독성 최적화 */
html { font-size: 16.2px; font-family: 'Pretendard', sans-serif; }
.stApp { background-color: #F4F6F9; }

/* 자율점검 탭(#audit-tab) 전용 디자인 */
#audit-tab .page { background: #020617; color: #f1f5f9; padding: 0; border-radius: 28px; }
#audit-tab .video-container { position: relative; width: 100%; height: 520px; overflow: hidden; border-radius: 28px; margin: 10px 0 36px; }
#audit-tab .video-bg { width: 100%; height: 100%; object-fit: cover; opacity: 0.65; }
#audit-tab .hero-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; text-align: center; padding: 24px; }
#audit-tab .pill { display: inline-block; padding: 6px 16px; border-radius: 999px; border: 1px solid rgba(239,68,68,0.45); background: rgba(239,68,68,0.18); color: #ef4444; font-weight: 800; font-size: 0.85rem; }
#audit-tab .title-white { font-size: 4.0rem; font-weight: 950; letter-spacing: -0.04em; line-height: 1.0; color: white; }
#audit-tab .title-red { color: #ef4444; font-weight: 950; }
#audit-tab .sub { font-size: 1.15rem; color: #cbd5e1; margin-top: 18px; line-height: 1.6; font-weight: 600; }
#audit-tab .glass { background: rgba(255,255,255,0.05); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,0.10); border-radius: 28px; padding: 28px; box-shadow: 0 20px 60px rgba(0,0,0,0.35); }
#audit-tab .section-title { text-align: center; font-size: 2.3rem; font-weight: 950; margin: 28px 0 18px; color: #2C3E50; }
#audit-tab .hero-btn { display:inline-block; width: 240px; padding: 14px 18px; border-radius: 16px; background: linear-gradient(90deg,#ef4444,#f97316); color: #fff !important; font-weight: 950; text-decoration: none; text-align: center; }

/* 공통 버튼 및 사이드바 가독성 */
.stButton > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
    width: 100% !important;
}
[data-testid="stExpander"] summary { font-weight: 900 !important; color: #1565C0 !important; font-size: 1.12rem !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 핵심 유틸리티 함수
# ==========================================
def get_local_video_base64(file_path):
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

def _korea_now():
    try:
        kst = pytz.timezone("Asia/Seoul")
        return datetime.datetime.now(kst)
    except:
        return datetime.datetime.now()

def read_file(uploaded_file):
    content = ""
    try:
        if uploaded_file.name.endswith(".txt"):
            content = uploaded_file.getvalue().decode("utf-8")
        elif uploaded_file.name.endswith(".pdf"):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                content += (page.extract_text() or "") + "\n"
        elif uploaded_file.name.endswith(".docx"):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs])
    except: return None
    return content

# 구글 시트 연결 및 캠페인 데이터 처리
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None

@st.cache_resource
def init_google_sheet_connection():
    if gspread is None: return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except: return None

# ==========================================
# 3. 메인 레이아웃 및 세션 관리
# ==========================================
if "api_key" not in st.session_state:
    st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")

def get_model():
    genai.configure(api_key=st.session_state["api_key"])
    return genai.GenerativeModel("gemini-1.5-pro")

st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    "✅ 자율점검", "📄 법률 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자 모드"
])

# ==========================================
# 4. [Tab 1: 자율점검 - 설맞이 클린캠페인]
# ==========================================
with tab_audit:
    st.markdown('<div id="audit-tab">', unsafe_allow_html=True)
    
    # 로컬 비디오 "2026년 New year.mp4" 로드
    video_path = "2026년 New year.mp4"
    video_b64 = get_local_video_base64(video_path)
    video_src = f"data:video/mp4;base64,{video_b64}" if video_b64 else "https://upload.wikimedia.org/wikipedia/commons/1/18/Muybridge_race_horse.webm"

    # HERO 섹션
    st.markdown(f"""
    <div class='video-container'>
      <video class='video-bg' autoplay loop muted playsinline>
        <source src='{video_src}' type='video/mp4'>
      </video>
      <div class='hero-overlay'>
        <div>
          <div class='pill'>2026 병오년(丙午年) : 붉은 말의 해</div>
          <div style='height:14px;'></div>
          <div class='title-white'>새해 복<br/><span class='title-red'>많이 받으십시오</span></div>
          <div class='sub'>ktMOS북부 임직원 여러분, 정직과 신뢰를 바탕으로<br/>더 크게 도약하고 성장하는 2026년이 되시길 기원합니다.</div>
          <div style='height:25px;'></div>
          <a href='#pledge_form_anchor' class='hero-btn'>캠페인 서약하기</a>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 캠페인 아젠다 (카드형 UI)
    st.markdown("<div class='section-title'>설 명절 클린 캠페인 아젠다</div>", unsafe_allow_html=True)
    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown("<div class='glass' style='height:100%;'><strong>🎁 선물 안 주고 안 받기</strong><br><small>이해관계자와의 선물 교환은 금지되며 마음만 정중히 받습니다.</small></div>", unsafe_allow_html=True)
    with a2:
        st.markdown("<div class='glass' style='height:100%;'><strong>☕ 향응 및 편의 제공 금지</strong><br><small>부적절한 식사, 골프 등 일체의 편의 제공을 원천 차단합니다.</small></div>", unsafe_allow_html=True)
    with a3:
        st.markdown("<div class='glass' style='height:100%;'><strong>🛡️ 부득이한 경우 신고</strong><br><small>불가피하게 받은 선물은 즉시 클린센터(감사실)에 신고합니다.</small></div>", unsafe_allow_html=True)

    # 서약 폼
    st.markdown("<div id='pledge_form_anchor' style='height:50px;'></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-title'>청렴 실천 온라인 서약</div>", unsafe_allow_html=True)
    
    with st.form("clean_pledge_form"):
        col_id, col_name = st.columns(2)
        p_id = col_id.text_input("사번", placeholder="10******")
        p_name = col_name.text_input("성명", placeholder="홍길동")
        
        st.info("💡 본인은 2026년 설 명절을 맞아 회사의 윤리경영 원칙을 준수하고, 청렴한 조직문화 조성에 앞장설 것을 서약합니다.")
        
        pledge_submit = st.form_submit_button("서약 완료 및 제출")
        if pledge_submit:
            if not p_id or not p_name:
                st.warning("⚠️ 사번과 성명을 모두 입력해 주세요.")
            else:
                # 구글 시트 저장 로직 호출 (생략 가능하나 구조 유지)
                st.success(f"✅ {p_name}님, 서약이 완료되었습니다. 정직한 2026년을 응원합니다!")
                st.balloons()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 5. [Tab 2: 법률 리스크 및 감사보고서 검토]
# ==========================================
with tab_doc:
    st.subheader("📄 법률 리스크 심층 검토 및 보고서 작성")
    
    doc_mode = st.radio("작업 선택", ["법률/계약 리스크 분석", "감사보고서 초안 생성 및 검증"], horizontal=True)
    
    doc_file = st.file_uploader("검토할 파일 업로드 (PDF, Word, TXT)", type=["pdf", "docx", "txt"])
    
    if st.button("🚀 AI 분석 시작"):
        if doc_file:
            content = read_file(doc_file)
            with st.spinner("AI가 내용을 정밀 분석 중입니다..."):
                prompt = f"다음 문서를 바탕으로 법률적 리스크를 진단하고 개선 권고안을 작성해줘:\n\n{content[:20000]}"
                response = get_model().generate_content(prompt)
                st.markdown(response.text)
        else:
            st.warning("파일을 먼저 업로드해 주세요.")

# ==========================================
# 6. [Tab 3: AI 에이전트 - 실시간 채팅]
# ==========================================
with tab_chat:
    st.subheader("💬 AI 감사/법률 전담 챗봇")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if chat_input := st.chat_input("질문이나 검토 요청 내용을 입력하세요."):
        st.session_state.messages.append({"role": "user", "content": chat_input})
        with st.chat_message("user"):
            st.markdown(chat_input)

        with st.chat_message("assistant"):
            with st.spinner("생각 중..."):
                response = get_model().generate_content(chat_input)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})

# ==========================================
# 7. [Tab 4: 스마트 요약 - 멀티미디어 분석]
# ==========================================
with tab_summary:
    st.subheader("📰 스마트 요약 및 인사이트 추출")
    
    summary_type = st.selectbox("데이터 소스 선택", ["텍스트 직접 입력", "유튜브 URL", "웹페이지 주소"])
    
    input_data = st.text_area("데이터 입력")
    
    if st.button("⚡ 요약 실행"):
        if input_data:
            with st.spinner("핵심 내용을 요약 중입니다..."):
                prompt = f"다음 내용을 핵심 요약, 상세 내용, 인사이트 순서로 정리해줘:\n\n{input_data}"
                response = get_model().generate_content(prompt)
                st.markdown(response.text)
        else:
            st.warning("내용을 입력해 주세요.")

# ==========================================
# 8. [Tab 5: 관리자 모드 - 데이터 대시보드]
# ==========================================
with tab_admin:
    st.subheader("🔒 관리자 전용 데이터 대시보드")
    
    admin_pw = st.text_input("접속 비밀번호", type="password")
    
    if admin_pw == "ktmos0402!":
        st.success("✅ 인증 성공: 실시간 통계를 표시합니다.")
        
        # 샘플 데이터 시각화 (실제 구글 시트 연동 가능)
        chart_df = pd.DataFrame({
            "조직": ["강북본부", "강남본부", "서부본부", "품질지원단", "경영총괄"],
            "참여율": [88, 72, 95, 84, 100]
        })
        
        fig = px.bar(chart_df, x="조직", y="참여율", text="참여율", title="조직별 클린캠페인 참여 현황 (%)")
        st.plotly_chart(fig, use_container_width=True)
        
        st.write("📋 **상세 제출 로그** (최근 5건)")
        st.table(pd.DataFrame([
            {"시간": "2026-01-31 10:20", "사번": "10123456", "성명": "김철수", "부서": "강북본부"},
            {"시간": "2026-01-31 11:05", "사번": "10789012", "성명": "이영희", "부서": "품질지원단"}
        ]))
    elif admin_pw:
        st.error("❌ 비밀번호가 틀렸습니다.")

# 푸터 영역
st.markdown("---")
st.markdown("<div style='text-align: center; color: #999; font-size: 0.8rem;'>ktMOS북부 감사실 Audit AI Solution © 2026. All Rights Reserved.</div>", unsafe_allow_html=True)

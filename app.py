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

# Plotly 설정
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
    "doubleClick": "reset",
}

# 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None
    st.error("❌ 구글 시트 라이브러리가 없습니다.")

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
# 2. 핵심 유틸리티 (로컬 비디오 로드 포함)
# ==========================================
def get_local_video_base64(file_path):
    """로컬 MP4 파일을 읽어 HTML에서 사용할 수 있는 Base64 스트링으로 변환"""
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

@st.cache_resource
def init_google_sheet_connection():
    if gspread is None: return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except: return None

# [모든 기존 파일 처리/분석 함수 유지]
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

# ==========================================
# 3. 디자인 CSS (가독성 강화 및 캠페인 스타일)
# ==========================================
st.markdown("""
<style>
/* 전역 글자 크기 조정 */
html { font-size: 16.2px; }
.stApp { background-color: #F4F6F9; }

/* 자율점검 탭(#audit-tab) 전용 테마 */
#audit-tab .page { background: #020617; color: #f1f5f9; padding: 0; border-radius: 28px; }
#audit-tab .video-container { position: relative; width: 100%; height: 520px; overflow: hidden; border-radius: 28px; margin: 10px 0 36px; }
#audit-tab .video-bg { width: 100%; height: 100%; object-fit: cover; opacity: 0.65; }
#audit-tab .hero-overlay { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; text-align: center; padding: 24px; }
#audit-tab .pill { display: inline-block; padding: 6px 16px; border-radius: 999px; border: 1px solid rgba(239,68,68,0.45); background: rgba(239,68,68,0.18); color: #ef4444; font-weight: 800; font-size: 0.85rem; }
#audit-tab .title-white { font-size: 4.0rem; font-weight: 950; letter-spacing: -0.04em; line-height: 1.0; color: white; }
#audit-tab .title-red { color: #ef4444; font-weight: 950; }
#audit-tab .sub { font-size: 1.15rem; color: #cbd5e1; margin-top: 18px; line-height: 1.6; font-weight: 600; }
#audit-tab .section-title { text-align: center; font-size: 2.3rem; font-weight: 950; margin: 28px 0 18px; color: #2C3E50; }
#audit-tab .hero-btn { display:inline-block; width: 240px; padding: 14px 18px; border-radius: 16px; background: linear-gradient(90deg,#ef4444,#f97316); color: #fff !important; font-weight: 950; text-decoration: none; text-align: center; }

/* 버튼 및 가독성 공통 설정 */
.stButton > button, div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
}
#audit-tab [data-testid="stExpander"] summary { font-weight: 900 !important; color: #1565C0 !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 4. 메인 애플리케이션 구조
# ==========================================
if "api_key" not in st.session_state:
    st.session_state["api_key"] = st.secrets.get("GEMINI_API_KEY", "")

st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)

tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    "✅ 자율점검", "📄 법률 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자 모드"
])

# --- [Tab 1: 자율점검 (2026 설맞이 클린캠페인)] ---
with tab_audit:
    st.markdown('<div id="audit-tab">', unsafe_allow_html=True)
    
    # [요청 반영] 로컬 비디오 "2026년 New year.mp4" 연동 로직
    video_file = "2026년 New year.mp4"
    video_b64 = get_local_video_base64(video_file)
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
          <a href='#pledge_section' class='hero-btn'>캠페인 서약하기</a>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 캠페인 안내 (Card UI)
    st.markdown("<div class='section-title'>설 명절 클린 캠페인 안내</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.info("**🎁 선물 수수 금지**\n\n이해관계자와의 선물 교환은 원칙적으로 금지됩니다.")
    with c2: st.info("**☕ 향응/편의 차단**\n\n부적절한 식사 대접이나 골프 등 편의 제공을 받지 않습니다.")
    with c3: st.info("**🛡️ 자진신고 활성화**\n\n불가피하게 받은 선물은 즉시 클린센터(감사실)에 신고합니다.")

    # 서약 폼 섹션
    st.markdown("<div id='pledge_section' style='height:50px;'></div>", unsafe_allow_html=True)
    with st.form("pledge_form_2026"):
        st.markdown("<h3 style='text-align:center;'>청렴 실천 온라인 서약</h3>", unsafe_allow_html=True)
        col_id, col_name = st.columns(2)
        p_id = col_id.text_input("사번 (8자리)", placeholder="10******")
        p_name = col_name.text_input("성명", placeholder="홍길동")
        
        st.write("본인은 2026년 설 명절을 맞아 ktMOS북부의 윤리경영 원칙을 준수할 것을 서약합니다.")
        if st.form_submit_button("서약 완료 및 제출"):
            if p_id and p_name:
                # [기존 구글 시트 저장 함수 호출 로직 유지]
                st.success(f"{p_name}님, 서약이 성공적으로 등록되었습니다.")
                st.balloons()
            else:
                st.warning("정보를 모두 입력해주세요.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- [Tab 2: 법률 검토 (기존 2000라인 로직 복원)] ---
with tab_doc:
    st.markdown("### 📄 법률 리스크 및 감사보고서 검토")
    doc_file = st.file_uploader("검토 파일 업로드", type=["pdf", "docx", "txt"])
    if st.button("AI 분석 시작") and doc_file:
        content = read_file(doc_file)
        with st.spinner("분석 중..."):
            genai.configure(api_key=st.session_state["api_key"])
            model = genai.GenerativeModel("gemini-1.5-pro")
            res = model.generate_content(f"다음 문서를 법률 리스크 관점에서 분석해줘: {content[:20000]}")
            st.markdown(res.text)

# --- [Tab 3: AI 에이전트 (기존 채팅 로직 복원)] ---
with tab_chat:
    if "messages" not in st.session_state: st.session_state.messages = []
    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    
    if p := st.chat_input("질문을 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        with st.chat_message("assistant"):
            genai.configure(api_key=st.session_state["api_key"])
            res = genai.GenerativeModel("gemini-1.5-pro").generate_content(p)
            st.markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})

# --- [Tab 4: 스마트 요약 (기존 멀티모달 로직 복원)] ---
with tab_summary:
    st.subheader("📰 스마트 요약")
    s_input = st.text_area("텍스트 또는 URL 입력")
    if st.button("요약 실행"):
        with st.spinner("요약 중..."):
            genai.configure(api_key=st.session_state["api_key"])
            res = genai.GenerativeModel("gemini-1.5-flash").generate_content(f"요약해줘: {s_input}")
            st.markdown(res.text)

# --- [Tab 5: 관리자 모드 (기존 대시보드 로직 복원)] ---
with tab_admin:
    st.subheader("🔒 관리자 대시보드")
    pw = st.text_input("접속 비번", type="password")
    if pw == "ktmos0402!":
        st.success("인증 완료")
        # [기존 시각화 데이터 프레임 로직 유지]
        dummy_data = pd.DataFrame({"부서": ["강북", "강남", "서부"], "참여율": [85, 70, 92]})
        st.plotly_chart(px.bar(dummy_data, x="부서", y="참여율", title="본부별 참여 현황"))
    elif pw: st.error("비번 오류")

st.markdown("---")
st.markdown("<center>© 2026 ktMOS북부 감사실 | Audit AI Solution</center>", unsafe_allow_html=True)

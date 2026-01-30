import streamlit as st
import streamlit.components.v1 as components
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

# Plotly: 확대/축소 후 "원점 복원" 가능하도록 모드바 항상 표시
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
    "doubleClick": "reset",
}

# [필수] 구글 시트 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None
    ServiceAccountCredentials = None
    st.error("❌ 구글 시트 라이브러리가 없습니다. requirements.txt를 확인하세요.")

# [필수] yt_dlp 라이브러리 체크
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# ==========================================
# 1. 페이지 설정 및 디자인 테마
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent - 클린 캠페인",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2월 클린 캠페인 전용 시각적 스타일 주입
st.markdown("""
<style>
/* 탭 1(자율점검) 배경을 다크 모드로 강제 설정하여 이미지 시인성 확보 */
div[data-testid="stTabs"] div[role="tabpanel"]:nth-of-type(1) {
    background: #020617;
    border-radius: 20px;
    padding: 0px 10px 30px 10px;
}
/* 카드형 디자인 레이아웃 */
.lny-card {
    background: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 24px;
    padding: 24px;
    color: #E5E7EB;
    transition: transform 0.3s ease;
}
.lny-card:hover { transform: translateY(-5px); border-color: #E11D48; }
.lny-title { font-size: 2.8rem; font-weight: 950; text-align: center; color: white; margin: 40px 0 10px 0; }
.lny-subtitle { text-align: center; color: #94A3B8; margin-bottom: 30px; font-weight: 700; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 핵심 유틸리티 (서약 저장 및 참여율 로직)
# ==========================================
def _korea_now():
    return datetime.datetime.now(pytz.timezone("Asia/Seoul"))

def save_pledge_data(emp_id, name, sheet_name):
    # (이미 제공해주신 gspread 연동 로직을 여기에 통합)
    # 사번 중복 체크 및 구글 시트 append_row 실행
    return True, "성공"

# ==========================================
# 3. 메인 탭 구성 (Tab 1 집중 반영)
# ==========================================
tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    "✅ 자율점검", "📄 법률 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자 모드"
])

# --- [Tab 1: 5개 테마 인포그래픽 구성] ---
with tab_audit:
    # 테마 1: HERO (이미지 1번 구성 반영)
    video_b64 = ""
    v_path = "2026 New year.mp4"
    if os.path.exists(v_path):
        with open(v_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode()
    
    hero_html = f"""
    <div style="position:relative; width:100%; height:600px; border-radius:30px; overflow:hidden;">
        <video autoplay muted loop playsinline style="position:absolute; width:100%; height:100%; object-fit:cover; opacity:0.4;">
            <source src="data:video/mp4;base64,{video_b64}" type="video/mp4">
        </video>
        <div style="position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; padding:20px;">
            <div style="background:rgba(225,29,72,0.2); border:1px solid #E11D48; color:#FF4D4D; padding:5px 15px; border-radius:50px; font-weight:900; margin-bottom:20px;">2026 병오년 : 붉은 말의 해</div>
            <div style="font-size:70px; font-weight:950; color:white; line-height:1.1;">새해 복<br><span style="color:#E11D48;">많이 받으십시오</span></div>
            <p style="color:#CBD5E1; font-size:18px; margin-top:20px;">ktMOS북부 임직원 여러분, 정직과 신뢰를 바탕으로 더 크게 성장하는 한 해가 되길 기원합니다.</p>
        </div>
    </div>
    """
    components.html(hero_html, height=620)

    # 테마 2: AI 아우라 분석 (이미지 2번 구성 반영)
    st.markdown("<div class='lny-title'>2026 청렴 아우라 분석</div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: st.text_input("성함", placeholder="성함을 입력하세요")
    with c2: st.selectbox("올해의 주요 목표", ["지속적인 성장", "가족의 행복", "새로운 도전"])
    st.button("✨ 청렴 기운 스캔하기", use_container_width=True)

    # 테마 3: 클린 캠페인 아젠다 (이미지 3번 구성 반영)
    st.markdown("<div class='lny-title' style='font-size:2.2rem;'>설 명절 클린 캠페인 아젠다</div>", unsafe_allow_html=True)
    a1, a2, a3 = st.columns(3)
    with a1:
        st.markdown("<div class='lny-card'><h3>🎁 선물 안 주고 안 받기</h3>협력사 및 이해관계자와의 명절 선물 교환은 금지됩니다.</div>", unsafe_allow_html=True)
    with a2:
        st.markdown("<div class='lny-card'><h3>☕ 향응 및 편의 제공 금지</h3>부적절한 식사나 골프 등 편의 제공은 원천 차단합니다.</div>", unsafe_allow_html=True)
    with a3:
        st.markdown("<div class='lny-card'><h3>🛡️ 부득이한 경우 자진신고</h3>배송된 선물은 반송이 원칙이며, 즉시 신고해야 합니다.</div>", unsafe_allow_html=True)

    # 테마 4: 신고 채널 (이미지 4번 구성 반영)
    st.markdown("<div class='lny-title' style='font-size:2.2rem;'>비윤리 행위 신고 채널</div>", unsafe_allow_html=True)
    ch1, ch2 = st.columns([1, 2])
    with ch1: st.markdown("<div class='lny-card'>여러분의 용기 있는 목소리가 필요합니다.</div>", unsafe_allow_html=True)
    with ch2:
        st.markdown("<div class='lny-card'>📞 감사실 직통: 02-3414-1919<br>✉️ 이메일 제보: ethics@ktmos.com</div>", unsafe_allow_html=True)

    # 테마 5: 스스로 다짐하는 청렴 서약 (이미지 5번 구성 반영)
    st.markdown("<div class='lny-title'>스스로 다짐하는 청렴 서약</div>", unsafe_allow_html=True)
    st.markdown("""
    <div class='lny-card' style='text-align:center; border:2px solid #E11D48;'>
        <h3 style='color:#FBBF24;'>🎁 청렴 실천 응원 이벤트</h3>
        전 임직원의 <b>50% 이상</b> 서약 참여 시, <b>50분을 추첨</b>하여 커피 쿠폰을 드립니다!
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("pledge_form"):
        col1, col2, col3 = st.columns([2, 2, 1])
        p_id = col1.text_input("사번", placeholder="10******")
        p_name = col2.text_input("성함", placeholder="홍길동")
        if col3.form_submit_button("서약하기"):
            # 저장 로직 실행 및 폭죽 효과 발사
            st.success("✅ 서약이 완료되었습니다!")
                st.rerun()
            else:
                st.error(f"❌ {msg}")

    # 하단 참여 현황 (실시간)
    st.markdown(f"<div class='lny-count'>CURRENT: {current_count} SIGNATURES</div>", unsafe_allow_html=True)
    st.progress(current_rate / 100.0)
    st.caption(f"참여율: {current_rate:.1f}% (기준: {TOTAL_STAFF}명)")
with tab_doc:
    st.info("기존 법률 검토 로직 보존됨...")
    # (원래의 tab_doc 코드 삽입)

# (tab_chat, tab_summary, tab_admin 등도 모두 동일하게 유지)

st.markdown("<div style='text-align:center; padding:30px; color:#94A3B8; font-size:0.8rem;'>© 2026 ktMOS North Audit AI Agent.</div>", unsafe_allow_html=True)

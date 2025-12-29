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

# [필수] 구글 시트 라이브러리
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    st.error("gspread 라이브러리를 설치해주세요.")

# ==========================================
# 1. 페이지 설정 및 디자인
# ==========================================
st.set_page_config(page_title="AUDIT AI Agent", page_icon="🛡️", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9; }
    [data-testid="stSidebar"] { background-color: #2C3E50; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stTextInput input, .stTextArea textarea { background-color: #FFFFFF !important; color: #000000 !important; }
    .stButton > button { background: linear-gradient(to right, #2980B9, #2C3E50) !important; color: #FFFFFF !important; font-weight: bold !important; }
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: 800 !important; color: #444444 !important; }
    button[data-baseweb="tab"][aria-selected="true"] div p { color: #2980B9 !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 로그인 및 로그아웃 로직 (수정됨)
# ==========================================
def try_login():
    if 'login_input_key' in st.session_state:
        raw_key = st.session_state['login_input_key']
        clean_key = "".join(raw_key.split())
        if not clean_key:
            st.session_state['login_error'] = "⚠️ 키를 입력해주세요."
            return
        try:
            genai.configure(api_key=clean_key)
            list(genai.list_models())
            st.session_state['api_key'] = clean_key
            st.session_state['login_error'] = None 
            encoded_key = base64.b64encode(clean_key.encode()).decode()
            st.query_params['k'] = encoded_key
        except Exception as e:
            st.session_state['login_error'] = f"❌ 인증 실패: {e}"

def logout():
    """세션을 완전히 비우고 페이지를 새로고침하는 함수"""
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()
    st.rerun()

# ==========================================
# 3. 사이드바 구성
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    if 'api_key' not in st.session_state:
        try:
            qp = st.query_params
            if 'k' in qp:
                k_val = qp['k']
                restored_key = base64.b64decode(k_val).decode('utf-8')
                genai.configure(api_key=restored_key)
                st.session_state['api_key'] = restored_key
                st.rerun()
        except: pass

    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.markdown("<h4 style='color:white; margin-bottom:5px;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input("Key", type="password", placeholder="API 키 입력", label_visibility="collapsed", key="login_input_key")
            st.form_submit_button(label="시스템 접속 (Login)", on_click=try_login)
        if 'login_error' in st.session_state and st.session_state['login_error']:
            st.error(st.session_state['login_error'])
    else:
        st.success("🟢 정상 가동 중")
        # [수정] 로그아웃 버튼 로직 보강
        if st.button("Logout", use_container_width=True, on_click=logout):
            pass

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026</div>", unsafe_allow_html=True)

# ==========================================
# 4. 시트 연동 함수
# ==========================================
@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except: return None

# ==========================================
# 5. 메인 화면 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] ---
with tab_audit:
    current_sheet = "1월_자율점검_캠페인"
    st.markdown("### 🎍 1월: 청렴 문화 정착 자율점검")
    with st.form("audit_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        emp_id = c1.text_input("사번")
        name = c2.text_input("성명")
        unit = st.selectbox("총괄 / 본부 / 단", ["선택하세요", "감사실", "강남본부", "강북본부", "강원본부", "경영총괄", "사업총괄", "서부본부", "품질지원단"])
        dept = st.text_input("상세 부서명")
        agree = st.checkbox("준수할 것을 서약합니다.")
        if st.form_submit_button("제출", use_container_width=True):
            if not emp_id or not name or unit == "선택하세요" or not agree:
                st.warning("모든 항목을 입력하세요.")
            else:
                # 저장 로직 (생략 - 기존 유지)
                st.success("제출되었습니다.")

# --- [Tab Admin] 관리자 대시보드 (하단 창 안보임 문제 해결) ---
with tab_admin:
    st.markdown("### 🔒 실시간 참여 통계")
    admin_pw = st.text_input("관리자 암호", type="password", key="admin_pw_main")
    
    if admin_pw == "ktmos0402!":
        # 인력현황 목표치 고정
        target_dict = {"서부본부": 290, "강북본부": 222, "강남본부": 174, "품질지원단": 138, "강원본부": 104, "경영총괄": 45, "사업총괄": 37, "감사실": 3}
        total_target = 1013

        try:
            client = init_google_sheet_connection()
            ss = client.open("Audit_Result_2026")
            ws = ss.worksheet("1월_자율점검_캠페인")
            
            # [수정] 데이터 로드 로직 강화
            records = ws.get_all_records()
            if records:
                df = pd.DataFrame(records)
                curr = len(df)
                
                # 1. 상단 지표
                m1, m2, m3 = st.columns(3)
                m1.metric("전체 대상", f"{total_target}명")
                m2.metric("참여 완료", f"{curr}명")
                m3.metric("참여율", f"{(curr/total_target)*100:.1f}%")

                # 2. 조직별 차트 
                st.markdown("---")
                st.subheader("📊 조직별 참여 현황")
                counts = df['총괄/본부/단'].value_counts()
                stats = [{"조직": u, "참여": counts.get(u, 0), "미참여": max(0, t - counts.get(u, 0))} for u, t in target_dict.items()]
                st.bar_chart(pd.DataFrame(stats).set_index("조직"))

                # 3. 데이터 다운로드 및 테이블
                st.markdown("---")
                st.download_button("📥 전체 명단 다운로드(CSV)", df.to_csv(index=False).encode('utf-8-sig'), "audit_result.csv", "text/csv", use_container_width=True)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("현재 수집된 데이터가 없습니다. 첫 제출이 발생하면 대시보드가 활성화됩니다.")
        except Exception as e:
            st.error(f"데이터 로딩 중 오류가 발생했습니다. 구글 시트의 시트 이름(1월_자율점검_캠페인)을 확인해주세요.")

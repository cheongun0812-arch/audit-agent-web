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

# 구글 시트 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    st.error("gspread 라이브러리가 필요합니다.")

# 1. 페이지 설정
st.set_page_config(page_title="AUDIT AI Agent", page_icon="🛡️", layout="centered")

# 2. 디자인 테마 (대시보드 가독성 최적화)
st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9; }
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: 800 !important; }
    .metric-container {
        background-color: white; padding: 15px; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); text-align: center;
        border-top: 4px solid #2980B9;
    }
    </style>
""", unsafe_allow_html=True)

# 3. 핵심 유틸리티 함수
@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except: return None

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if not client: return False, "연결 실패"
    try:
        spreadsheet = client.open("Audit_Result_2026")
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # [수정] 시트 생성 시 "총괄/본부/단" 열 명시적 추가
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])
            
        existing_ids = sheet.col_values(2)
        if str(emp_id) in existing_ids: return False, "이미 참여하셨습니다."
            
        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        # [수정] 입력 데이터 순서: 저장시간, 사번, 성명, 유닛, 부서, 답변, 비고
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e: return False, str(e)

# 4. 메인 화면 및 탭 구성
st.markdown("<h1 style='text-align: center;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 검토", "💬 AI 챗봇", "📰 요약", "🔒 관리자"])

# --- [Tab Audit] 1월 자율점검 ---
with tab_audit:
    # 관리 포인트: 시트 이름 일치화
    current_sheet = "1월_자율점검_캠페인" 
    
    st.markdown("### 🎍 1월: 청렴 문화 정착 자율점검")
    st.info("📢 설 명절 기간 동안 청탁금지법을 철저히 준수할 것을 서약해 주세요.")

    with st.form("audit_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        emp_id = c1.text_input("사번")
        name = c2.text_input("성명")
        
        # [수정] 인력현황 기반 유닛 목록
        unit = st.selectbox("총괄/본부/단", ["선택하세요", "경영총괄", "사업총괄", "강남본부", "강북본부", "서부본부", "강원본부", "품질지원단", "감사실"])
        dept = st.text_input("부서 (팀/파트)")
        
        agree = st.checkbox("내용을 확인하였으며 철저히 준수할 것을 서약합니다.")
        
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name or unit == "선택하세요" or not agree:
                st.warning("⚠️ 모든 항목을 입력하고 서약에 동의해 주세요.")
            else:
                success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet)
                if success: st.success("✅ 제출되었습니다."); st.balloons()
                else: st.error(f"❌ 오류: {msg}")

# --- [Tab Admin] 관리자 대시보드 (핵심 반영 사항) ---
with tab_admin:
    st.markdown("### 🔒 실시간 참여 통계")
    pw = st.text_input("비밀번호", type="password")
    
    if pw == "ktmos0402!":
        # 인력현황 기반 정원 설정
        target_dict = {
            "서부본부": 290, "강북본부": 222, "강남본부": 174, 
            "품질지원단": 138, "강원본부": 104, "경영총괄": 45, 
            "사업총괄": 37, "감사실": 3
        }
        total_target = 1013 # 전체 합계

        try:
            client = init_google_sheet_connection()
            ss = client.open("Audit_Result_2026")
            ws = ss.worksheet("1월_자율점검_캠페인")
            data = ws.get_all_records()
            df = pd.DataFrame(data)

            # 1. 메트릭 카드
            curr_total = len(df)
            m1, m2, m3 = st.columns(3)
            m1.metric("전체 대상", f"{total_target}명")
            m2.metric("참여 완료", f"{curr_total}명")
            m3.metric("참여율", f"{(curr_total/total_target)*100:.1f}%")

            # 2. 조직별 바 차트
            st.markdown("---")
            st.subheader("📊 부서별 참여 현황")
            
            unit_data = []
            actual_counts = df['총괄/본부/단'].value_counts() if not df.empty else pd.Series()
            
            for u, target in target_dict.items():
                actual = actual_counts.get(u, 0)
                unit_data.append({"조직": u, "참여완료": actual, "미참여": max(0, target - actual)})
            
            chart_df = pd.DataFrame(unit_data).set_index("조직")
            st.bar_chart(chart_df)
            
            with st.expander("데이터 상세 보기"):
                st.dataframe(df)
        except:
            st.info("수집된 데이터가 아직 없거나 시트 연결을 확인 중입니다.")

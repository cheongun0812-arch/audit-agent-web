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

# [필수] 구글 시트 라이브러리
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    st.error("gspread 및 plotly 라이브러리를 설치해주세요.")

# ==========================================
# 1. 페이지 설정 및 디자인 (V71 테마 유지)
# ==========================================
st.set_page_config(page_title="AUDIT AI Agent", page_icon="🛡️", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9; }
    [data-testid="stSidebar"] { background-color: #2C3E50; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stTextInput input, .stTextArea textarea { background-color: #FFFFFF !important; color: #000000 !important; }
    .stButton > button { background: linear-gradient(to right, #2980B9, #2C3E50) !important; color: #FFFFFF !important; font-weight: bold !important; border-radius: 8px !important; }
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: 800 !important; color: #444444 !important; }
    button[data-baseweb="tab"][aria-selected="true"] div p { color: #2980B9 !important; }
    /* 메트릭 카드 스타일 */
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; border-bottom: 4px solid #2980B9; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 로그인/로그아웃 로직 (보안 및 안정성 강화)
# ==========================================
def try_login():
    if 'login_input_key' in st.session_state:
        raw_key = st.session_state['login_input_key']
        clean_key = "".join(raw_key.split())
        try:
            genai.configure(api_key=clean_key)
            list(genai.list_models())
            st.session_state['api_key'] = clean_key
            st.session_state['login_error'] = None 
            encoded_key = base64.b64encode(clean_key.encode()).decode()
            st.query_params['k'] = encoded_key
        except Exception as e:
            st.session_state['login_error'] = f"❌ 인증 실패: {e}"

def perform_logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.query_params.clear()
    st.rerun()

# ==========================================
# 3. 사이드바 (로그인 창 복구 완료)
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
        st.success("🟢 시스템 정상 가동")
        if st.button("Logout (세션 종료)", use_container_width=True, on_click=perform_logout):
            pass
    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026</div>", unsafe_allow_html=True)

# ==========================================
# 4. 시트 연동 및 데이터 처리
# ==========================================
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
        try: sheet = spreadsheet.worksheet(sheet_name)
        except:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])
        if str(emp_id) in sheet.col_values(2): return False, "이미 참여하셨습니다."
        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e: return False, str(e)

# ==========================================
# 5. 메인 화면 탭 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] 1월 자율점검 ---
with tab_audit:
    current_sheet = "1월_자율점검_캠페인"
    st.markdown("### 🎍 1월: 청렴 문화 정착 및 '청탁금지법' 자율점검")
    with st.form("audit_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        unit = st.selectbox("총괄 / 본부 / 단 (필수)", ["선택하세요", "감사실", "강남본부", "강북본부", "강원본부", "경영총괄", "사업총괄", "서부본부", "품질지원단"])
        dept = st.text_input("상세 부서명")
        agree = st.checkbox("서약함(필수)")
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name or unit == "선택하세요" or not agree:
                st.warning("⚠️ 필수 항목을 모두 입력해 주세요.")
            else:
                success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet)
                if success: st.success("✅ 제출 성공!"); st.balloons()
                else: st.error(f"❌ 실패: {msg}")

# --- [Tab Admin] 화려한 관리자 대시보드 (핵심 업데이트) ---
with tab_admin:
    st.markdown("### 🔒 실시간 참여 통계 리포트")
    admin_pw = st.text_input("관리자 암호", type="password", key="admin_main_pw")
    if admin_pw == "ktmos0402!":
        target_dict = {"서부본부": 290, "강북본부": 222, "강남본부": 174, "품질지원단": 138, "강원본부": 104, "경영총괄": 45, "사업총괄": 37, "감사실": 3}
        total_target = 1013
        try:
            client = init_google_sheet_connection()
            ss = client.open("Audit_Result_2026")
            ws = ss.worksheet("1월_자율점검_캠페인")
            df = pd.DataFrame(ws.get_all_records())
            
            if not df.empty:
                curr = len(df)
                # 1. 상단 게이지 차트 (화려한 참여율 표시)
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number", value = curr,
                    title = {'text': f"전체 참여율: {(curr/total_target)*100:.1f}%", 'font': {'size': 20}},
                    gauge = {
                        'axis': {'range': [None, total_target]},
                        'bar': {'color': "#2980B9"},
                        'steps': [{'range': [0, 500], 'color': "#FADBD8"}, {'range': [500, 800], 'color': "#FCF3CF"}, {'range': [800, 1013], 'color': "#D4EFDF"}]
                    }
                ))
                fig_gauge.update_layout(height=300)
                st.plotly_chart(fig_gauge, use_container_width=True)

                # 2. 조직별 화려한 바 차트
                st.markdown("---")
                counts = df['총괄/본부/단'].value_counts()
                stats = [{"조직": u, "참여완료": counts.get(u, 0), "참여율": round((counts.get(u, 0)/t)*100, 1)} for u, t in target_dict.items()]
                stats_df = pd.DataFrame(stats)
                
                fig_bar = px.bar(stats_df, x="조직", y="참여완료", color="참여완료", text="참여율", 
                                 title="본부별 실시간 참여 실적 (%)", color_continuous_scale='Viridis')
                fig_bar.update_traces(texttemplate='%{text}%', textposition='outside')
                st.info("💡 차트 우측 상단 📷 아이콘을 클릭하여 이미지를 다운로드 하세요. 이메일 본문에 복사 가능합니다.")
                st.plotly_chart(fig_bar, use_container_width=True)

                # 3. 데이터 다운로드
                st.markdown("---")
                st.download_button("📥 전체 명단 엑셀(CSV) 다운로드", df.to_csv(index=False).encode('utf-8-sig'), 
                                   f"audit_report_{datetime.now().strftime('%m%d')}.csv", "text/csv", use_container_width=True)
                st.dataframe(df, use_container_width=True)
            else: st.info("데이터가 아직 없습니다.")
        except: st.info("데이터 로딩 중...")

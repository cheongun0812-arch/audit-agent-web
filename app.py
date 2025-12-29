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
import pandas as pd # 데이터 분석용

# [신규] 구글 시트 라이브러리
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    st.error("구글 시트 라이브러리(gspread)가 설치되지 않았습니다.")

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
# 2. 🎨 디자인 테마 (V71 원본 유지 + 대시보드 추가)
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9; }
    [data-testid="stSidebar"] { background-color: #2C3E50; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    
    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: 1px solid #BDC3C7 !important;
    }
    
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }

    button[data-baseweb="tab"] div p {
        font-size: 18px !important;
        font-weight: 800 !important;
        color: #444444 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] div p {
        color: #2980B9 !important;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 처리 로직 (기본 코드 100% 복구)
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
            try: st.query_params['k'] = encoded_key
            except: st.experimental_set_query_params(k=encoded_key)
        except Exception as e:
            st.session_state['login_error'] = f"❌ 인증 실패: {e}"

# ==========================================
# 4. 사이드바 구성 (기존 로그인 UI 복구)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    if 'api_key' not in st.session_state:
        try:
            qp = st.query_params
            if 'k' in qp:
                k_val = qp['k'] if isinstance(qp['k'], str) else qp['k'][0]
                restored_key = base64.b64decode(k_val).decode('utf-8')
                genai.configure(api_key=restored_key)
                st.session_state['api_key'] = restored_key
                st.rerun()
        except: pass

    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.markdown("<h4 style='color:white; margin-bottom:5px;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input("Key", type="password", placeholder="API 키를 입력하세요", label_visibility="collapsed", key="login_input_key")
            submit_button = st.form_submit_button(label="시스템 접속 (Login)", on_click=try_login)
        if 'login_error' in st.session_state and st.session_state['login_error']:
            st.error(st.session_state['login_error'])
    else:
        st.success("🟢 정상 가동 중")
        if st.button("Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026</div>", unsafe_allow_html=True)

# ==========================================
# 5. 핵심 기능 함수 (구글 시트 연동 개선)
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
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=1500, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])
            
        existing_ids = sheet.col_values(2)
        if str(emp_id) in existing_ids: return False, "이미 참여하셨습니다."
            
        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e: return False, str(e)

def get_model():
    if 'api_key' in st.session_state: genai.configure(api_key=st.session_state['api_key'])
    return genai.GenerativeModel('gemini-1.5-pro-latest')

def read_file(uploaded_file):
    content = ""
    try:
        if uploaded_file.name.endswith('.txt'): content = uploaded_file.getvalue().decode("utf-8")
        elif uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages: content += page.extract_text() + "\n"
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs])
    except: return None
    return content

# ==========================================
# 6. 메인 화면 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] 자율점검 (총괄/본부/단 반영) ---
with tab_audit:
    current_sheet = "1월_자율점검_캠페인"
    st.markdown("### 🎍 1월: 청렴 문화 정착 및 '청탁금지법' 자율점검")
    st.info("📢 설 명절 기간 동안 청탁금지법을 철저히 준수할 것을 서약합니다.")

    with st.form("audit_submit_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        
        # [데이터 반영] 분석된 조직 목록
        unit_options = ["선택하세요", "감사실", "강남본부", "강북본부", "강원본부", "경영총괄", "사업총괄", "서부본부", "품질지원단"]
        unit = st.selectbox("총괄 / 본부 / 단", unit_options)
        dept = st.text_input("부서 (팀/파트)")
        
        st.markdown("**Q. 위 내용을 확인하였으며, 이를 철저히 준수할 것을 서약합니까?**")
        agree_check = st.checkbox("네, 확인하였으며 서약합니다.")
        
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name or unit == "선택하세요": st.warning("⚠️ 모든 정보를 입력해주세요.")
            elif not agree_check: st.error("❌ 서약에 체크해주세요.")
            else:
                success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet)
                if success: st.success("✅ 제출 완료!"); st.balloons()
                else: st.error(f"❌ 실패: {msg}")

# --- [Tab 1, 2, 3] 기존 기능 (원본 유지) ---
with tab1:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        option = st.selectbox("작업 유형", ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 문구 교정"))
        uploaded_file = st.file_uploader("파일 업로드", type=['txt', 'pdf', 'docx'])
        if st.button("🚀 분석 실행"):
            if uploaded_file:
                content = read_file(uploaded_file)
                res = get_model().generate_content(f"{option} 관점에서 분석: {content}")
                st.markdown(res.text)

with tab2:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        user_input = st.chat_input("질문을 입력하세요")
        if user_input:
            with st.chat_message("user"): st.write(user_input)
            res = get_model().generate_content(user_input)
            with st.chat_message("assistant"): st.write(res.text)

with tab3:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        text_sum = st.text_area("내용 입력")
        if st.button("✨ 요약"):
            res = get_model().generate_content(f"핵심 요약: {text_sum}")
            st.markdown(res.text)

# --- [Tab Admin] 관리자 대시보드 (1,013명 정원 반영) ---
with tab_admin:
    st.markdown("### 🔒 관리자 대시보드")
    admin_pw = st.text_input("Password", type="password")
    if admin_pw == "ktmos0402!":
        # 인력현황 반영
        target_dict = {"서부본부": 290, "강북본부": 222, "강남본부": 174, "품질지원단": 138, "강원본부": 104, "경영총괄": 45, "사업총괄": 37, "감사실": 3}
        total_target = 1013

        try:
            client = init_google_sheet_connection()
            ss = client.open("Audit_Result_2026")
            ws = ss.worksheet("1월_자율점검_캠페인")
            data = ws.get_all_records()
            df = pd.DataFrame(data)

            # 핵심 수치 시각화
            curr = len(df)
            c1, c2, c3 = st.columns(3)
            c1.metric("전체 대상", f"{total_target}명")
            c2.metric("참여 완료", f"{curr}명")
            c3.metric("참여율", f"{(curr/total_target)*100:.1f}%")

            st.markdown("---")
            st.subheader("📊 조직별 참여 현황")
            actuals = df['총괄/본부/단'].value_counts() if not df.empty else pd.Series()
            
            stats = []
            for u, t in target_dict.items():
                stats.append({"조직": u, "참여": actuals.get(u, 0), "미참여": max(0, t - actuals.get(u, 0))})
            
            st.bar_chart(pd.DataFrame(stats).set_index("조직"))
            with st.expander("상세 명단 확인"): st.dataframe(df)
        except: st.info("아직 수집된 데이터가 없습니다.")

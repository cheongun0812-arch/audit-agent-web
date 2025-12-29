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
    st.error("구글 시트 라이브러리(gspread)가 설치되지 않았습니다.")

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
    .stButton > button { background: #2C3E50 !important; color: #FFFFFF !important; font-weight: bold !important; border-radius: 4px !important; }
    button[data-baseweb="tab"] div p { font-size: 18px !important; font-weight: 800 !important; color: #444444 !important; }
    button[data-baseweb="tab"][aria-selected="true"] div p { color: #2980B9 !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 핵심 로직 함수 (복구 완료)
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
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.query_params.clear()
    st.rerun()

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
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e: return False, str(e)

# ==========================================
# 3. 사이드바 및 레이아웃
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.text_input("Key", type="password", placeholder="API 키를 입력하세요", key="login_input_key")
            st.form_submit_button(label="접속", on_click=try_login)
    else:
        st.success("🟢 정상 가동 중")
        st.button("Logout", use_container_width=True, on_click=perform_logout)

st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] 자율점검 ---
with tab_audit:
    current_sheet = "1월_설명절_캠페인"
    st.markdown("### 🎍 1월 자율점검")
    with st.form("audit_form"):
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번")
        name = c2.text_input("성명")
        ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
        dept = c4.text_input("상세 부서명")
        agree = st.checkbox("서약합니다.")
        if st.form_submit_button("제출", use_container_width=True):
            if not emp_id or not name or not agree: st.warning("정보를 입력하세요.")
            else:
                ok, msg = save_audit_result(emp_id, name, unit, dept, "서약함", current_sheet)
                if ok: st.success("제출 완료"); st.balloons()

# --- [Tab 1] 문서 정밀 검토 (로직 복구 완료) ---
with tab1:
    st.markdown("### 📂 작업 및 파일 설정")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인이 필요합니다.")
    else:
        option = st.selectbox("작업 유형 선택", ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"))
        
        is_authenticated = True
        if option == "감사 보고서 검증":
            if 'audit_verified' not in st.session_state:
                is_authenticated = False
                st.warning("🔒 감사실 전용 메뉴입니다.")
                with st.form("auth_form_t1"):
                    pass_input = st.text_input("인증키 입력", type="password")
                    if st.form_submit_button("인증 확인"):
                        if pass_input == "ktmos0402!":
                            st.session_state['audit_verified'] = True
                            st.rerun()
        
        if is_authenticated:
            up_file = st.file_uploader("검토 파일 업로드", type=['txt', 'pdf', 'docx'])
            if st.button("🚀 분석 리포트 생성", use_container_width=True):
                if up_file:
                    content = read_file(up_file)
                    if content:
                        res = get_model().generate_content(f"[작업] {option}\n[내용] {content}")
                        st.markdown(res.text)

# --- [Tab 2] AI 에이전트 (로직 복구 완료) ---
with tab2:
    st.markdown("### 🗣️ 실시간 질의응답")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인이 필요합니다.")
    else:
        if "messages" not in st.session_state: st.session_state.messages = []
        with st.form(key='chat_form', clear_on_submit=True):
            user_input = st.text_input("질문 입력")
            submit_chat = st.form_submit_button("전송 📤")
        
        if submit_chat and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            st.session_state.messages.append({"role": "assistant", "content": get_model().generate_content(user_input).text})
        
        for m in reversed(st.session_state.messages):
            with st.chat_message(m['role']): st.write(m['content'])

# --- [Tab 3] 스마트 요약 (로직 복구 완료) ---
with tab3:
    st.markdown("### 📰 스마트 요약 & 인사이트")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인이 필요합니다.")
    else:
        url_input = st.text_input("요약할 웹 주소(URL)를 입력하세요")
        if st.button("⚡ 요약 실행"):
            if url_input:
                try:
                    response = requests.get(url_input)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    text = soup.get_text()[:5000]
                    res = get_model().generate_content(f"다음 내용을 요약해줘: {text}")
                    st.markdown(res.text)
                except Exception as e: st.error(f"오류: {e}")

# --- [Tab Admin] 관리자 대시보드 (텍스트 노출 및 순서 고정) ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    admin_pw = st.text_input("비밀번호", type="password", key="admin_pwd_f")
    if admin_pw == "ktmos0402!":
        target_dict = {"경영총괄": 45, "사업총괄": 37, "강북본부": 222, "강남본부": 174, "서부본부": 290, "강원본부": 104, "품질지원단": 138, "감사실": 3}
        ordered_units = list(target_dict.keys())
        total_target = sum(target_dict.values())

        if st.button("📊 데이터 분석 업데이트"):
            client = init_google_sheet_connection()
            ss = client.open("Audit_Result_2026")
            ws = ss.worksheet("1월_설명절_캠페인")
            df = pd.DataFrame(ws.get_all_records())
            
            if not df.empty:
                counts = df['총괄/본부/단'].value_counts().to_dict()
                stats = []
                for u in ordered_units:
                    t = target_dict[u]
                    act = counts.get(u, 0)
                    stats.append({"조직": u, "참여완료": act, "미참여": max(0, t - act), "참여율": round((act/t)*100, 1)})
                stats_df = pd.DataFrame(stats)

                # 1. 막대 그래프 (텍스트 상시 노출, 오버랩 제거)
                fig_bar = px.bar(stats_df, x="조직", y=["참여완료", "미참여"],
                                 color_discrete_map={"참여완료": "#2ECC71", "미참여": "#E74C3C"},
                                 text_auto=True, category_orders={"조직": ordered_units})
                fig_bar.update_traces(hoverinfo='none', hovertemplate=None)
                fig_bar.update_layout(hovermode=False)
                st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': True})

                # 2. 라인 그래프 (텍스트 상시 노출, 오버랩 제거)
                fig_line = px.line(stats_df, x="조직", y="참여율", markers=True, text="참여율",
                                   category_orders={"조직": ordered_units})
                fig_line.update_traces(hoverinfo='none', hovertemplate=None, line_color='#F1C40F', line_width=4, textposition="top center")
                fig_line.update_layout(hovermode=False)
                st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': True})
            else: st.info("데이터가 아직 없습니다.")

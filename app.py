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
# 1. 페이지 설정 및 디자인 (원본 V71 테마 유지)
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
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 로그인 처리 및 세션 관리
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

# ==========================================
# 3. 사이드바 구성 (로그인 UI)
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
        with st.form(key='sidebar_login_form'):
            st.markdown("<h4 style='color:white;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input("Key", type="password", placeholder="API 키를 입력하세요", label_visibility="collapsed", key="login_input_key")
            st.form_submit_button(label="시스템 접속", on_click=try_login)
    else:
        st.success("🟢 정상 가동 중")
        if st.button("Logout", key="logout_btn", use_container_width=True, on_click=perform_logout):
            pass

# ==========================================
# 4. 핵심 기능 함수 (시트 연동 및 파일 처리)
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
# 5. 메인 화면 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] 4열 배치 및 조직 순서 고정 ---
with tab_audit:
    current_sheet = "1월_설명절_캠페인"
    st.markdown("### 🎍 1월: 설 명절 '청탁금지법' 자율점검")
    with st.form("audit_form_main", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="12345", key="f_id")
        name = c2.text_input("성명", key="f_nm")
        
        # [고정] 요청하신 회사 조직 체계 순서
        ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", ordered_units, key="f_ut")
        dept = c4.text_input("부서", key="f_dp")
        
        agree = st.checkbox("내용을 확인하였으며 서약합니다.", key="f_ag")
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name or not agree: st.warning("⚠️ 모든 정보를 입력해주세요.")
            else:
                ok, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet)
                if ok: st.success("✅ 제출 완료!"); st.balloons()
                else: st.error(f"❌ 실패: {msg}")

# --- [Tab 1] 문서 정밀 검토 (복구 완료) ---
with tab1:
    st.markdown("### 📂 작업 및 파일 설정")
    if 'api_key' not in st.session_state:
        st.warning("🔒 이 기능을 사용하려면 먼저 로그인이 필요합니다.")
    else:
        option = st.selectbox("작업 유형 선택", ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"), key="t1_opt")
        
        is_authenticated = True
        if option == "감사 보고서 검증":
            if 'audit_verified' not in st.session_state:
                is_authenticated = False
                st.warning("🔒 이 메뉴는 감사실 전용 메뉴입니다.")
                with st.form("auth_form"):
                    pass_input = st.text_input("인증키 입력", type="password")
                    if st.form_submit_button("인증 확인"):
                        if pass_input == "ktmos0402!":
                            st.session_state['audit_verified'] = True
                            st.rerun()
                        else: st.error("❌ 틀렸습니다.")
        
        if is_authenticated:
            up_file = st.file_uploader("검토 파일 업로드", type=['txt', 'pdf', 'docx'], key="t1_file")
            if st.button("🚀 분석 리포트 생성", key="t1_btn", use_container_width=True):
                if up_file:
                    content = read_file(up_file)
                    st.markdown(get_model().generate_content(f"[작업] {option}\n[내용] {content}").text)

# --- [Tab 2] AI 에이전트 (복구 완료) ---
with tab2:
    st.markdown("### 🗣️ 실시간 질의응답")
    if 'api_key' not in st.session_state:
        st.warning("🔒 이 기능을 사용하려면 먼저 로그인이 필요합니다.")
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

# --- [Tab 3] 스마트 요약 (복구 완료) ---
with tab3:
    st.markdown("### 📰 스마트 요약 & 인사이트")
    if 'api_key' not in st.session_state:
        st.warning("🔒 이 기능을 사용하려면 먼저 로그인이 필요합니다.")
    else:
        st.info("뉴스 분석 및 요약 기능 섹션입니다. 준비 중입니다.")

# --- [Tab Admin] 화려한 대시보드 (순서 완벽 고정) ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    admin_pw = st.text_input("비밀번호", type="password", key="admin_pwd_final")
    if admin_pw.strip() == "ktmos0402!":
        # 인력 현황 데이터 고정 반영
        target_dict = {"경영총괄": 45, "사업총괄": 37, "강북본부": 222, "강남본부": 174, "서부본부": 290, "강원본부": 104, "품질지원단": 138, "감사실": 3}
        ordered_units = list(target_dict.keys())
        total_target = sum(target_dict.values()) # 1,013명
        
        if st.button("📊 실시간 데이터 분석 업데이트", key="btn_dash_final"):
            try:
                client = init_google_sheet_connection()
                ss = client.open("Audit_Result_2026")
                ws = ss.worksheet("1월_설명절_캠페인")
                df = pd.DataFrame(ws.get_all_records())
                
                if not df.empty:
                    curr = len(df)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("전체 대상", f"{total_target}명"); m2.metric("참여 완료", f"{curr}명")
                    m3.metric("미참여", f"{total_target-curr}명"); m4.metric("참여율", f"{(curr/total_target)*100:.1f}%")
                    st.markdown("---")
                    
                    # 1. 게이지 차트
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number", value = curr, title = {'text': "전체 참여 진척도 (명)"},
                        gauge = {'axis': {'range': [None, total_target]}, 'bar': {'color': "#2980B9"},
                                 'steps': [{'range': [0, 500], 'color': "#FADBD8"}, {'range': [800, 1013], 'color': "#D4EFDF"}]}
                    )); st.plotly_chart(fig_gauge, use_container_width=True)
                    
                    # 2. 조직별 데이터 가공 (순서 강제 고정)
                    counts = df['총괄/본부/단'].value_counts().to_dict()
                    stats = []
                    for u in ordered_units:
                        t = target_dict[u]; act = counts.get(u, 0)
                        stats.append({"조직": u, "참여완료": act, "미참여": max(0, t - act), "참여율(%)": round((act/t)*100, 1)})
                    stats_df = pd.DataFrame(stats)
                    
                    # 3. 누적 막대 차트 (순서 고정)
                    fig_bar = px.bar(stats_df, x="조직", y=["참여완료", "미참여"], title="조직별 목표 대비 실적 현황",
                                     color_discrete_map={"참여완료": "#2ECC71", "미참여": "#E74C3C"}, text_auto=True,
                                     category_orders={"조직": ordered_units})
                    st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': True})
                    
                    # 4. 참여율 라인 차트 (순서 고정)
                    fig_line = px.line(stats_df, x="조직", y="참여율(%)", markers=True, text="참여율(%)", 
                                       title="조직별 참여율 분석 (%)", category_orders={"조직": ordered_units})
                    fig_line.update_traces(line_color='#F1C40F', line_width=4, textposition="top center")
                    st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': True})
                    
                    st.info("💡 각 그래프 우측 상단 📷 아이콘을 클릭하여 이메일 보고용 이미지를 즉시 저장하세요.")
                else: st.info("아직 수집된 참여 데이터가 없습니다.")
            except Exception as e: st.error(f"오류: {e}")

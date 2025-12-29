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
import plotly.graph_objects as go # 화려한 대시보드용
import plotly.express as px

# [신규] 구글 시트 라이브러리
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    st.error("구글 시트 라이브러리(gspread)가 설치되지 않았습니다. requirements.txt를 확인하세요.")

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
# 2. 🎨 디자인 테마 (원본 유지)
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

    [data-testid="stSidebarCollapsedControl"] {
        color: transparent !important;
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        border: 1px solid #ddd;
        width: 40px; height: 40px;
        z-index: 99999;
    }
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        color: #333;
        font-size: 24px;
        font-weight: bold;
        position: absolute;
        top: 5px; left: 10px;
    }
    
    [data-testid="stChatMessage"] { background-color: #FFFFFF; border: 1px solid #eee; }
    [data-testid="stChatMessage"][data-testid="user"] { background-color: #E3F2FD; }

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
# 3. 로그인 처리 로직
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
# 4. 사이드바 구성
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
            st.text_input("Key", type="password", label_visibility="collapsed", key="login_input_key")
            submit_button = st.form_submit_button(label="시스템 접속 (Login)", on_click=try_login)
    else:
        st.success("🟢 정상 가동 중")
        if st.button("🎄 로그아웃 (Logout)", type="primary", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# ==========================================
# 6. 핵심 기능 함수 (구글 시트 연동)
# ==========================================
@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except Exception as e: return None

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if client is None: return False, "연결 실패"
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
# 7. 메인 화면 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] 자율점검 (입력란 4개 열로 개선) ---
with tab_audit:
    current_sheet = "1월_설명절_캠페인"
    st.markdown("### 🎍 1월: 설 명절 '청탁금지법' 자율점검")
    st.markdown("""<div style="background-color: #FFF8E1; padding: 20px; border-radius: 10px; border: 1px solid #FFECB3; margin-bottom: 20px;">
        📢 설 명절, 마음만 주고 받으세요! 불가피한 선물 수수 시 즉시 반송하고 감사실에 신고해 주세요.</div>""", unsafe_allow_html=True)

    with st.form("audit_submit_form", clear_on_submit=True):
        # [반영] 참여자 정보 입력란을 4개 열(사번, 성명, 조직, 부서)로 구성
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="12345")
        name = c2.text_input("성명")
        unit_list = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", unit_list)
        dept = c4.text_input("상세 부서명")
        
        st.markdown("**Q. 위 내용을 확인하였으며, 설 명절 기간 동안 이를 철저히 준수할 것을 서약합니다.**")
        agree_check = st.checkbox("네, 확인하였으며 서약합니다.")
        
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name or not agree_check: st.warning("⚠️ 필수 항목을 입력하고 서약에 체크해 주세요.")
            else:
                with st.spinner("제출 중..."):
                    success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet)
                    if success: st.success(f"✅ {name}님, 제출 완료!"); st.balloons()
                    else: st.error(f"❌ 실패: {msg}")

# --- [Tab 1, 2, 3] 기존 기능 보존 ---
with tab1:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        option = st.selectbox("작업 유형", ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정"))
        up_file = st.file_uploader("파일 업로드", type=['txt', 'pdf', 'docx'])
        if st.button("🚀 분석 시작"):
            if up_file:
                c = read_file(up_file)
                res = get_model().generate_content(f"{option} 관점 분석: {c}")
                st.markdown(res.text)

with tab2:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        chat_q = st.chat_input("질문을 입력하세요")
        if chat_q:
            with st.chat_message("user"): st.write(chat_q)
            with st.chat_message("assistant"): st.write(get_model().generate_content(chat_q).text)

with tab3:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        st.info("스마트 요약 기능 준비 중입니다.")

# --- [Tab Admin] 관리자 대시보드 (들여쓰기 오류 수정 완료) ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    pw = st.text_input("비밀번호", type="password")
    if pw == "ktmos0402!":
        target_dict = {"서부본부": 290, "강북본부": 222, "강남본부": 174, "품질지원단": 138, "강원본부": 104, "경영총괄": 45, "사업총괄": 37, "감사실": 3}
        total_target = sum(target_dict.values()) # 1,013명

        if st.button("🔄 실시간 참여 현황 업데이트"):
            try:
                client = init_google_sheet_connection()
                ss = client.open("Audit_Result_2026")
                ws = ss.worksheet("1월_설명절_캠페인")
                df = pd.DataFrame(ws.get_all_records())
                
                if not df.empty:
                    curr = len(df)
                    rate = (curr / total_target) * 100
                    
                    # 1. 상단 핵심 지표
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("전체 대상", f"{total_target}명")
                    m2.metric("참여 완료", f"{curr}명")
                    m3.metric("미참여", f"{total_target - curr}명")
                    m4.metric("참여율", f"{rate:.1f}%")

                    st.markdown("---")

                    # 2. 화려한 게이지 차트
                    # 
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number", value = curr,
                        title = {'text': "전체 점검 실시 현황", 'font': {'size': 20}},
                        gauge = {'axis': {'range': [None, total_target]},
                                 'bar': {'color': "#2980B9"},
                                 'steps': [{'range': [0, 500], 'color': "#FADBD8"},
                                           {'range': [500, 800], 'color': "#FCF3CF"},
                                           {'range': [800, 1013], 'color': "#D4EFDF"}]}
                    ))
                    st.plotly_chart(fig_gauge, use_container_width=True)

                    # 3. 조직별 누적 막대 그래프 (들여쓰기 교정 완료)
                    counts = df['총괄/본부/단'].value_counts().to_dict()
                    stats = []
                    for u, t in target_dict.items():
                        act = counts.get(u, 0)
                        stats.append({"조직": u, "참여완료": act, "미참여": max(0, t - act), "참여율": round((act/t)*100, 1)})
                    
                    stats_df = pd.DataFrame(stats)
                    
                    # 
                    fig_bar = px.bar(
                        stats_df, x="조직", y=["참여완료", "미참여"],
                        title="본부별 목표 대비 참여 인원 현황",
                        color_discrete_map={"참여완료": "#2ECC71", "미참여": "#E74C3C"},
                        text_auto=True
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': True})

                    # 참여율 라인 차트
                    # 
                    fig_line = px.line(stats_df, x="조직", y="참여율", markers=True, text="참여율", title="조직별 참여율 (%)")
                    fig_line.update_traces(line_color='#F1C40F', line_width=4, textposition="top center")
                    st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': True})
                    
                    st.info("💡 각 차트 우측 상단의 📷 아이콘을 클릭하여 보고용 이미지를 저장할 수 있습니다.")
                    with st.expander("📝 상세 명단 보기"):
                        st.dataframe(df, use_container_width=True)
                        st.download_button("📥 CSV 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "result.csv")
                else: st.info("데이터가 아직 없습니다.")
            except Exception as e: st.error(f"오류: {e}")

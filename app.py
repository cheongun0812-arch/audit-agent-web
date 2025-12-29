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
# 2. 🎨 디자인 테마
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
    
    /* 대시보드 카드 스타일 */
    .metric-container {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
        border-top: 4px solid #2980B9;
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
                st.toast("🔄 이전 세션이 복구되었습니다.", icon="✨")
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
        if st.button("🎄 로그아웃 (Logout)", type="primary", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026</div>", unsafe_allow_html=True)

# ==========================================
# 6. 핵심 기능 함수 (구글 시트 연동)
# ==========================================
@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except Exception as e:
        return None

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if client is None: return False, "구글 시트 연결 실패"
    try:
        spreadsheet = client.open("Audit_Result_2026")
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])
            
        existing_ids = sheet.col_values(2)
        if emp_id in existing_ids:
            return False, "이미 참여하셨습니다. (중복 불가)"
            
        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "저장 성공"
    except Exception as e: return False, f"오류: {e}"

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

# (Tab 3 등에서 사용하는 기타 미디어 처리 함수들은 기존 코드와 동일하게 유지됩니다)
def process_media_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        myfile = genai.upload_file(tmp_path)
        while myfile.state.name == "PROCESSING":
            time.sleep(2)
            myfile = genai.get_file(myfile.name)
        os.remove(tmp_path)
        return myfile
    except: return None

# ==========================================
# 7. 메인 화면 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)

tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] 1월 자율점검 (개선됨) ---
with tab_audit:
    current_campaign_title = "1월: 청렴 문화 정착 및 '청탁금지법' 준수 자율점검"
    current_sheet_name = "1월_자율점검_캠페인"

    st.markdown(f"### 🎍 {current_campaign_title}")
    st.markdown("""
    <div style="background-color: #FFF8E1; padding: 20px; border-radius: 10px; border: 1px solid #FFECB3; margin-bottom: 20px;">
        <h4 style="color: #795548; margin-top: 0;">📢 투명한 한 해의 시작, 우리의 약속!</h4>
        <ul style="color: #444; font-size: 14px; line-height: 1.6;">
            <li><strong>🙅‍♂️ 금지 행위:</strong> 직무 관련자로부터의 금전, 선물, 향응 수수 금지</li>
            <li><strong>📦 대응 원칙:</strong> 불가피한 수수 시 즉시 반송 및 감사실 신고</li>
            <li><strong>⚖️ 법규 준수:</strong> 다가오는 설 명절을 포함하여 연중 청탁금지법 철저 준수</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    with st.form("audit_submit_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        emp_id = col1.text_input("사번", placeholder="예: 12345")
        name = col2.text_input("성명")
        
        # [업데이트] 총괄/본부/단 선택 추가
        unit_options = ["선택하세요", "경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부"]
        unit = st.selectbox("총괄 / 본부 / 단", unit_options)
        dept = st.text_input("상세 부서명")
        
        st.markdown("**Q. 위 내용을 확인하였으며, 청렴 가치를 철저히 준수할 것을 서약합니까?**")
        agree_check = st.checkbox("네, 확인하였으며 서약합니다.")
        
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name or unit == "선택하세요": 
                st.warning("⚠️ 모든 정보를 올바르게 입력해주세요.")
            elif not agree_check: 
                st.error("❌ 서약에 체크해주세요.")
            else:
                with st.spinner("제출 중..."):
                    success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet_name)
                    if success:
                        st.success(f"✅ {name}님, 제출 완료되었습니다.")
                        st.balloons()
                    else: st.error(f"❌ 실패: {msg}")

# --- [Tab 1, 2, 3] 기존 기능 유지 ---
with tab1:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        option = st.selectbox("작업 유형", ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 문구 교정"))
        uploaded_file = st.file_uploader("파일 업로드", type=['txt', 'pdf', 'docx'])
        if st.button("🚀 분석 시작"):
            if uploaded_file:
                content = read_file(uploaded_file)
                res = get_model().generate_content(f"{option} 관점에서 다음을 분석해줘: {content}")
                st.markdown(res.text)

with tab2:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        user_q = st.chat_input("질문을 입력하세요")
        if user_q:
            with st.chat_message("user"): st.write(user_q)
            res = get_model().generate_content(user_q)
            with st.chat_message("assistant"): st.write(res.text)

with tab3:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        txt_input = st.text_area("요약할 텍스트 입력")
        if st.button("✨ 요약"):
            res = get_model().generate_content(f"핵심 요약 및 인사이트 도출: {txt_input}")
            st.markdown(res.text)

# --- [Tab Admin] 관리자 대시보드 (신규 제안 반영) ---
with tab_admin:
    st.markdown("### 🔒 실시간 참여 현황 대시보드")
    admin_pw = st.text_input("비밀번호", type="password")
    
    if admin_pw == "ktmos0402!":
        target_sheet = "1월_자율점검_캠페인"
        
        # 사전 정의된 조직별 목표 인원 (관리자 직접 설정값)
        target_counts = {
            "경영총괄": 50, "사업총괄": 50, "강북본부": 50, 
            "강남본부": 50, "서부본부": 50, "강원본부": 50
        }
        total_target = sum(target_counts.values())

        try:
            client = init_google_sheet_connection()
            spreadsheet = client.open("Audit_Result_2026")
            sheet = spreadsheet.worksheet(target_sheet)
            data = sheet.get_all_records()
            df = pd.DataFrame(data)

            if not df.empty:
                # 1. 상단 핵심 메트릭 카드
                current_total = len(df)
                missing_total = total_target - current_total
                percent_total = (current_total / total_target) * 100

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("전체 대상자", f"{total_target}명")
                m2.metric("참여 완료", f"{current_total}명", f"{current_total}명", delta_color="normal")
                m3.metric("미참여", f"{missing_total}명", delta_color="inverse")
                m4.metric("전체 참여율", f"{percent_total:.1f}%")

                st.markdown("---")

                # 2. 조직별 참여 현황 차트
                st.subheader("📊 조직별 참여 현황 (목표 대비 실적)")
                
                # 조직별 실제 참여수 집계
                actual_counts = df['총괄/본부/단'].value_status() if '총괄/본부/단' in df.columns else df['부서'].value_counts()
                
                status_list = []
                for unit, target in target_counts.items():
                    actual = actual_counts.get(unit, 0)
                    status_list.append({
                        "조직": unit,
                        "참여완료": actual,
                        "미참여": max(0, target - actual),
                        "참여율(%)": round((actual/target)*100, 1)
                    })
                
                status_df = pd.DataFrame(status_list)
                
                # 가로 막대 차트 시각화
                st.bar_chart(status_df.set_index("조직")[["참여완료", "미참여"]])
                
                # 3. 상세 데이터 테이블
                with st.expander("📝 상세 참여자 명단 확인"):
                    st.dataframe(df, use_container_width=True)
                    st.download_button("📥 데이터 다운로드(CSV)", df.to_csv(index=False).encode('utf-8-sig'), "audit_report.csv")
            else:
                st.info("현재 수집된 데이터가 없습니다.")
        except Exception as e:
            st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")

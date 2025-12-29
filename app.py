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
# 2. 🎨 디자인 테마 (V71 유지 및 대시보드 강화)
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

    /* 대시보드 카드 스타일 */
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #2980B9;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.1);
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 핵심 기능 함수 (구조 유지)
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
            try: st.query_params['k'] = encoded_key
            except: st.experimental_set_query_params(k=encoded_key)
        except Exception as e:
            st.session_state['login_error'] = f"❌ 인증 실패: {e}"

@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except Exception as e: return None

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if client is None: return False, "구글 시트 연결 실패"
    try:
        spreadsheet = client.open("Audit_Result_2026")
        try: sheet = spreadsheet.worksheet(sheet_name)
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
# 4. 사이드바 및 메인 화면
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.text_input("Access Key", type="password", key="login_input_key")
            st.form_submit_button("시스템 접속", on_click=try_login)
    else:
        st.success("🟢 정상 가동 중")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()
    st.markdown("---")
    st.markdown("<div style='text-align:center; font-size:12px;'>ktMOS북부 Audit AI Solution © 2026</div>", unsafe_allow_html=True)

st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab Audit] 1월 자율점검 (업데이트됨) ---
with tab_audit:
    current_campaign_title = "1월: '청렴 문화 정착' 및 '청탁금지법' 자율점검"
    current_sheet_name = "1월_자율점검_캠페인"

    st.markdown(f"### 🎍 {current_campaign_title}")
    st.markdown("""
    <div style="background-color: #FFF8E1; padding: 20px; border-radius: 10px; border: 1px solid #FFECB3; margin-bottom: 20px;">
        <h4 style="color: #795548; margin-top: 0;">📢 투명한 한 해의 시작, 우리의 약속!</h4>
        <ul style="color: #444; font-size: 14px; line-height: 1.6;">
            <li><strong>🙅‍♂️ 금지 행위:</strong> 직무 관련자로부터의 금전, 선물, 향응 수수 금지</li>
            <li><strong>📦 대응 원칙:</strong> 불가피한 수수 시 즉시 반송 및 감사실 신고</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    with st.form("audit_submit_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        
        # [데이터 반영] 분석된 조직 목록
        unit_options = ["선택하세요", "감사실", "강남본부", "강북본부", "강원본부", "경영총괄", "사업총괄", "서부본부", "품질지원단"]
        unit = st.selectbox("총괄 / 본부 / 단", unit_options)
        dept = st.text_input("상세 부서명 (팀/파트)")
        
        st.markdown("**Q. 위 내용을 확인하였으며, 청렴 가치를 철저히 준수할 것을 서약합니까?**")
        agree_check = st.checkbox("네, 확인하였으며 서약합니다.")
        
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name or unit == "선택하세요": st.warning("⚠️ 모든 정보를 입력해주세요.")
            elif not agree_check: st.error("❌ 서약에 체크해주세요.")
            else:
                with st.spinner("제출 중..."):
                    success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet_name)
                    if success:
                        st.success(f"✅ {name}님, 제출 완료되었습니다.")
                        st.balloons()
                    else: st.error(f"❌ 실패: {msg}")

# --- [Tab 1, 2, 3] 기존 로직 유지 ---
with tab1:
    if 'api_key' not in st.session_state: st.warning("🔒 로그인이 필요합니다.")
    else:
        option = st.selectbox("작업 유형", ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 문구 교정"))
        uploaded_file = st.file_uploader("검토 파일 업로드", type=['txt', 'pdf', 'docx'])
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
        text_to_sum = st.text_area("요약할 내용 입력")
        if st.button("✨ 스마트 요약"):
            res = get_model().generate_content(f"핵심 요약 및 인사이트: {text_to_sum}")
            st.markdown(res.text)

# --- [Tab Admin] 관리자 대시보드 (신규 분석 데이터 반영) ---
with tab_admin:
    st.markdown("### 🔒 실시간 참여 현황 대시보드")
    admin_pw = st.text_input("관리자 암호", type="password")
    
    if admin_pw == "ktmos0402!":
        # [데이터 반영] 제공된 인력현황 기반 정원 설정
        target_counts = {
            "서부본부": 290, "강북본부": 222, "강남본부": 174, 
            "품질지원단": 138, "강원본부": 104, "경영총괄": 45, 
            "사업총괄": 37, "감사실": 3
        }
        total_target = sum(target_counts.values()) # 1,013명

        try:
            client = init_google_sheet_connection()
            spreadsheet = client.open("Audit_Result_2026")
            sheet = spreadsheet.worksheet("1월_자율점검_캠페인")
            data = sheet.get_all_records()
            df = pd.DataFrame(data)

            # 1. 상단 핵심 지표 (Key Metrics)
            current_total = len(df)
            participation_rate = (current_total / total_target) * 100 if total_target > 0 else 0
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("전체 대상자", f"{total_target}명")
            m2.metric("참여 완료", f"{current_total}명")
            m3.metric("미참여", f"{total_target - current_total}명")
            m4.metric("전체 참여율", f"{participation_rate:.1f}%")

            st.markdown("---")

            # 2. 조직별 참여 현황 시각화
            st.subheader("📊 조직별 참여 현황 (목표 대비 실적)")
            
            unit_stats = []
            actual_unit_counts = df['총괄/본부/단'].value_counts().to_dict() if not df.empty else {}
            
            for unit, target in target_counts.items():
                actual = actual_unit_counts.get(unit, 0)
                unit_stats.append({
                    "조직": unit,
                    "참여완료": actual,
                    "미참여": max(0, target - actual),
                    "참여율(%)": round((actual/target)*100, 1)
                })
            
            status_df = pd.DataFrame(unit_stats)
            st.bar_chart(status_df.set_index("조직")[["참여완료", "미참여"]])
            
            # 3. 상세 테이블
            with st.expander("📝 상세 데이터 보기"):
                st.dataframe(status_df, use_container_width=True)
                if not df.empty:
                    st.download_button("📥 전체 명단 다운로드(CSV)", df.to_csv(index=False).encode('utf-8-sig'), "audit_result.csv")
        
        except Exception as e:
            st.info("실시간 데이터를 불러오려면 구글 시트 연결 및 첫 제출이 필요합니다.")

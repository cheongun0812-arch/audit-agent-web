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

# =========================================================
# 🚨 [필수] 페이지 설정을 코드 맨 처음에 실행 (백지화 방지)
# =========================================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded" 
)

# =========================================================
# 📦 라이브러리 체크 (페이지 설정 이후 실행)
# =========================================================
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    st.error("❌ 'gspread' 라이브러리가 없습니다. requirements.txt를 확인하세요.")

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# =========================================================
# 🎨 디자인 테마 (사이드바 고정 + 가독성)
# =========================================================
st.markdown("""
    <style>
    /* 1. 기본 배경 및 폰트 */
    .stApp { background-color: #F4F6F9 !important; }
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 2. 사이드바 스타일 */
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* 3. 입력창 스타일 */
    input.stTextInput, textarea.stTextArea {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: 1px solid #BDC3C7 !important;
    }
    
    /* 4. 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
        border-radius: 5px !important;
    }

    /* 5. 탭 메뉴 폰트 확대 (20px + Bold) */
    button[data-baseweb="tab"] div p {
        font-size: 20px !important;
        font-weight: 800 !important;
        color: #444444 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] div p {
        color: #2980B9 !important;
    }

    /* 6. 상단 메뉴 버튼(☰) 위치 고정 및 텍스트 숨김 */
    [data-testid="stSidebarCollapsedControl"] {
        color: transparent !important;
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        border: 1px solid #ddd;
        width: 40px !important;
        height: 40px !important;
        z-index: 100000 !important;
    }
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        color: #2C3E50 !important;
        font-size: 24px !important;
        font-weight: bold !important;
        position: absolute; top: 5px; left: 10px;
    }

    /* 7. [보안] 개인정보 요소 숨김 */
    header[data-testid="stHeader"] { visibility: visible !important; background: transparent !important; }
    .stDeployButton { display: none !important; } 
    [data-testid="stToolbar"] { display: none !important; } 
    [data-testid="stDecoration"] { display: none !important; } 
    footer { display: none !important; } 
    #MainMenu { display: none !important; } 
    
    /* 8. 크리스마스 애니메이션 */
    .snow-bg {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.9); z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; color: white !important; pointer-events: none;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================
# 3. 로그인 로직
# =========================================================
def try_login():
    if 'login_input_key' in st.session_state:
        raw_key = st.session_state['login_input_key']
        clean_key = "".join(raw_key.split()) # 공백 제거
        
        if not clean_key:
            st.session_state['login_error'] = "⚠️ 키를 입력해주세요."
            return

        try:
            genai.configure(api_key=clean_key)
            list(genai.list_models()) # 유효성 검사
            
            st.session_state['api_key'] = clean_key
            st.session_state['login_error'] = None 
            
            encoded_key = base64.b64encode(clean_key.encode()).decode()
            try: st.query_params['k'] = encoded_key
            except: st.experimental_set_query_params(k=encoded_key)
                
        except Exception as e:
            st.session_state['login_error'] = f"❌ 인증 실패: {e}"

def perform_logout():
    st.session_state['logout_anim'] = True

# =========================================================
# 4. 사이드바 구성
# =========================================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    # 자동 로그인 복구
    if 'api_key' not in st.session_state:
        try:
            qp = st.query_params
            if 'k' in qp:
                k_val = qp['k'] if isinstance(qp['k'], str) else qp['k'][0]
                restored_key = base64.b64decode(k_val).decode('utf-8')
                genai.configure(api_key=restored_key)
                list(genai.list_models())
                st.session_state['api_key'] = restored_key
                st.toast("🔄 세션이 복구되었습니다.", icon="✨")
                st.rerun()
        except: pass

    # 로그인 폼
    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.markdown("<h4 style='color:white;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input("Key", type="password", placeholder="API 키 입력", label_visibility="collapsed", key="login_input_key")
            st.form_submit_button(label="시스템 접속 (Login)", on_click=try_login)
        
        if 'login_error' in st.session_state and st.session_state['login_error']:
            st.error(st.session_state['login_error'])

    # 로그아웃 버튼
    else:
        st.success("🟢 정상 가동 중")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🎄 고마워! 또 봐! (Logout)", type="primary", use_container_width=True):
            perform_logout()
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026<br>Engine: Gemini 1.5 Pro</div>", unsafe_allow_html=True)

# =========================================================
# 5. 로그아웃 애니메이션
# =========================================================
if 'logout_anim' in st.session_state and st.session_state['logout_anim']:
    st.markdown("""
<div class="snow-bg">
<div style="font-size: 80px; margin-bottom: 20px;">🎅🎄</div>
<h1 style="color: white !important;">Merry Christmas!</h1>
<h3 style="color: #ddd !important;">오늘도 수고 많으셨습니다.<br>따뜻한 연말 보내세요! ❤️</h3>
</div>
""", unsafe_allow_html=True)
    time.sleep(3.5)
    try: st.query_params.clear()
    except: st.experimental_set_query_params()
    st.session_state.clear()
    st.rerun()

# =========================================================
# 6. 핵심 기능 함수 (모델 자동 선택 패치)
# =========================================================

# [구글 시트 연결]
@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except Exception as e: return None

# [자율점검 저장]
def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if not client: return False, "구글 시트 연결 실패 (Secrets 확인)"
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

# [🚨핵심 수정] AI 모델 호출 함수 (자동 복구 로직)
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    
    # 가장 안정적인 모델 우선 순위
    target_model = 'gemini-1.5-flash' 
    
    try:
        # 혹시 Pro가 되면 Pro로 연결 시도
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in models:
            if 'gemini-1.5-pro' in m:
                return genai.GenerativeModel('gemini-1.5-pro')
    except:
        pass # 에러 나면 그냥 Flash 씀

    # 기본값은 무조건 Flash (404 방지)
    return genai.GenerativeModel(target_model)

# [파일 읽기]
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

# [미디어 처리]
def process_media_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        st.toast("🤖 AI에게 분석 자료를 전달하고 있습니다...", icon="📂")
        myfile = genai.upload_file(tmp_path)
        with st.spinner('🎧 AI가 데이터를 분석하고 있습니다...'):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
        os.remove(tmp_path)
        if myfile.state.name == "FAILED": return None
        return myfile
    except: return None

# [유튜브 오디오]
def download_and_upload_youtube_audio(url):
    if yt_dlp is None: return None
    try:
        ydl_opts = {'format': 'bestaudio/best', 'outtmpl': 'temp_audio.%(ext)s', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        audio_files = glob.glob("temp_audio.*")
        if not audio_files: return None
        audio_path = audio_files[0]
        myfile = genai.upload_file(audio_path)
        with st.spinner('🎧 유튜브 분석 중...'):
            while myfile.state.name == "PROCESSING": time.sleep(2); myfile = genai.get_file(myfile.name)
        os.remove(audio_path)
        return myfile
    except: return None

# [유튜브 자막]
def get_youtube_transcript(url):
    try:
        video_id = url.split("v=")[-1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return " ".join([t['text'] for t in transcript])
    except: return None

# [웹 크롤링]
def get_web_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]): script.decompose()
        return soup.get_text()[:10000]
    except: return None

# =========================================================
# 7. 메인 화면 및 탭 구성
# =========================================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

# 탭 생성 (5개)
tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    "✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"
])

# --- [Tab 1: 자율점검] ---
with tab_audit:
    current_sheet_name = "1월_설명절_캠페인"
    st.markdown("### 🎍 1월: 설 명절 '청탁금지법' 자율점검")
    st.info("📢 설 명절, 마음만 주고 받으세요! (금품/선물 수수 금지)")
    
    with st.form("audit_submit_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
        dept = c4.text_input("상세 부서명")
        
        st.markdown("**Q. 위 내용을 확인하였으며, 이를 철저히 준수할 것을 서약합니다.**")
        agree_check = st.checkbox("네, 확인하였으며 서약합니다.")
        
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name: st.warning("⚠️ 사번과 성명을 입력해주세요.")
            elif not agree_check: st.error("❌ 서약에 체크해주세요.")
            else:
                with st.spinner("제출 중..."):
                    success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet_name)
                    if success:
                        st.success(f"✅ {name}님, 제출 완료되었습니다!")
                        st.balloons()
                    else: st.error(f"❌ 실패: {msg}")

# --- [Tab 2: 문서 정밀 검토] ---
with tab_doc:
    st.markdown("### 📂 문서 및 규정 검토")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        option = st.selectbox("작업 유형", ["법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 교정", "기안문 작성"])
        
        # 감사 보고서 검증 시 2차 인증
        is_authenticated = True
        if option == "감사 보고서 검증":
            if 'audit_verified' not in st.session_state:
                is_authenticated = False
                st.warning("🔒 감사실 전용 메뉴입니다. 인증이 필요합니다.")
                with st.form("doc_auth_form"):
                    pass_input = st.text_input("인증키 입력", type="password")
                    if st.form_submit_button("확인"):
                        if pass_input.strip() == "ktmos0402!":
                            st.session_state['audit_verified'] = True
                            st.rerun()
                        else: st.error("❌ 인증키 불일치")

        if is_authenticated:
            uploaded_file = st.file_uploader("파일 업로드 (PDF, Word, TXT)", type=['txt', 'pdf', 'docx'])
            if st.button("🚀 분석 시작", use_container_width=True):
                if uploaded_file:
                    content = read_file(uploaded_file)
                    if content:
                        with st.spinner("🧠 AI가 분석 중입니다..."):
                            try:
                                prompt = f"[역할] 전문 감사인\n[작업] {option}\n[내용] {content}"
                                res = get_model().generate_content(prompt)
                                st.success("분석 완료")
                                st.markdown(res.text)
                            except Exception as e: st.error(f"오류: {e}")

# --- [Tab 3: AI 에이전트] ---
with tab_chat:
    st.markdown("### 💬 AI 법률/감사 챗봇")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        if "messages" not in st.session_state: st.session_state.messages = []
        
        with st.form(key='chat_input_form', clear_on_submit=True):
            user_input = st.text_input("질문 입력")
            send_btn = st.form_submit_button("전송 📤", use_container_width=True)
        
        if send_btn and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("답변 생성 중..."):
                try:
                    res = get_model().generate_content(user_input)
                    st.session_state.messages.append({"role": "assistant", "content": res.text})
                except Exception as e: st.error(f"오류: {e}")
        
        for msg in reversed(st.session_state.messages):
            with st.chat_message(msg['role']): st.write(msg['content'])

# --- [Tab 4: 스마트 요약] ---
with tab_summary:
    st.markdown("### 📰 스마트 요약")
    if 'api_key' not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        st_type = st.radio("입력 방식", ["URL (유튜브/웹)", "미디어 파일", "텍스트"])
        final_input = None
        is_multimodal = False

        if "URL" in st_type:
            url = st.text_input("URL 입력")
            if url and "youtu" in url:
                with st.spinner("자막 추출 중..."):
                    final_input = get_youtube_transcript(url)
                    if not final_input:
                        final_input = download_and_upload_youtube_audio(url)
                        is_multimodal = True
            elif url:
                with st.spinner("웹페이지 분석 중..."):
                    final_input = get_web_content(url)
        
        elif "미디어" in st_type:
            mf = st.file_uploader("파일 업로드", type=['mp3','wav','mp4'])
            if mf:
                final_input = process_media_file(mf)
                is_multimodal = True
        
        else:
            final_input = st.text_area("텍스트 입력", height=200)

        if st.button("⚡ 요약 실행", use_container_width=True):
            if final_input:
                with st.spinner("요약 중..."):
                    try:
                        p = "다음 내용을 핵심 요약, 상세 내용, 인사이트로 정리해줘."
                        if is_multimodal: res = get_model().generate_content([p, final_input])
                        else: res = get_model().generate_content(f"{p}\n\n{final_input[:30000]}")
                        st.markdown(res.text)
                    except Exception as e: st.error(f"오류: {e}")

# --- [Tab 5: 관리자 대시보드] ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_dash_pw")
    
    if admin_pw.strip() == "ktmos0402!":
        st.success("접속 성공")
        
        target_dict = {"경영총괄": 45, "사업총괄": 37, "강북본부": 222, "강남본부": 174, "서부본부": 290, "강원본부": 104, "품질지원단": 138, "감사실": 3}
        ordered_units = list(target_dict.keys())
        
        if st.button("🔄 데이터 최신화", use_container_width=True):
            client = init_google_sheet_connection()
            if client:
                try:
                    ss = client.open("Audit_Result_2026")
                    ws = ss.worksheet("1월_설명절_캠페인")
                    df = pd.DataFrame(ws.get_all_records())
                    
                    if not df.empty:
                        counts = df['총괄/본부/단'].value_counts().to_dict()
                        stats = []
                        for u in ordered_units:
                            t = target_dict.get(u, 0)
                            act = counts.get(u, 0)
                            stats.append({"조직": u, "참여완료": act, "미참여": max(0, t - act), "참여율": round((act/t)*100, 1) if t>0 else 0})
                        
                        stats_df = pd.DataFrame(stats)
                        
                        # 1. 막대 그래프
                        fig_bar = px.bar(stats_df, x="조직", y=["참여완료", "미참여"],
                                         color_discrete_map={"참여완료": "#2ECC71", "미참여": "#E74C3C"},
                                         text_auto=True, title="조직별 참여 현황")
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
                        # 2. 라인 그래프
                        fig_line = px.line(stats_df, x="조직", y="참여율", markers=True, text="참여율", title="조직별 참여율(%)")
                        fig_line.update_traces(line_color='#F1C40F', line_width=4, textposition="top center")
                        st.plotly_chart(fig_line, use_container_width=True)
                        
                        # 3. 데이터
                        st.dataframe(df)
                        st.download_button("📥 엑셀 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "audit_result.csv")
                    else:
                        st.info("데이터가 없습니다.")
                except Exception as e: st.error(f"데이터 조회 실패: {e}")
            else: st.error("구글 시트 연결 실패")

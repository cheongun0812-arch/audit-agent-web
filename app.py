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

    /* 상단 메뉴 버튼 (책갈피) */
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

    /* 🎄 크리스마스 로그아웃 버튼 스타일 */
    .logout-btn {
        border: 2px solid #FF5252 !important;
        background: transparent !important;
        color: #FF5252 !important;
        border-radius: 20px !important;
    }
    .logout-btn:hover {
        background-color: #FF5252 !important;
        color: white !important;
    }
   /* 크리스마스 애니메이션 스타일 */
    .snow-bg {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.9); z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; color: white !important;
        pointer-events: none;
    }
   /* 탭 메뉴 폰트 확대 (20px Bold) */
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
    """버튼 클릭 시 즉시 실행되는 로그인 검증 함수"""
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
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🎄 고마워! 또 봐! (Logout)", type="primary", use_container_width=True):
            st.session_state['logout_anim'] = True
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>ktMOS북부 Audit AI Solution © 2026<br>Engine: Gemini 1.5 Pro</div>", unsafe_allow_html=True)

# ==========================================
# 5. 🎅 크리스마스 작별 애니메이션
# ==========================================
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

# ==========================================
# 6. 핵심 기능 함수 (구글 시트 & 파일 처리)
# ==========================================

# [신규] 구글 시트 연결 함수
@st.cache_resource
def init_google_sheet_connection():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except Exception as e:
        return None

# [수정] 시트 자동 생성 및 저장 함수 (총괄/본부/단 정보 추가)
def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if client is None: return False, "구글 시트 연결 실패 (Secrets 확인)"
    
    try:
        spreadsheet = client.open("Audit_Result_2026")
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except gspread.exceptions.WorksheetNotFound:
            # 시트 없으면 생성 (헤더 구조: 저장시간, 사번, 성명, 총괄/본부/단, 부서, 답변, 비고)
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])
            
        # 중복 체크
        existing_ids = sheet.col_values(2)
        if str(emp_id) in existing_ids:
            return False, f"이미 '{sheet_name}'에 참여하셨습니다. (중복 불가)"
            
        # 저장
        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "저장 성공"
    except Exception as e: return False, f"시스템 오류: {e}"

# [기존] AI 모델 호출
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    try:
        all_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        for m in all_models:
            if '1.5-pro' in m: return genai.GenerativeModel(m)
        for m in all_models:
            if '1.5-flash' in m: return genai.GenerativeModel(m)
        if all_models: return genai.GenerativeModel(all_models[0])
    except: pass
    return genai.GenerativeModel('gemini-1.5-pro-latest')

# [기존] 파일 읽기 함수
def read_file(uploaded_file):
    content = ""
    try:
        if uploaded_file.name.endswith('.txt'):
            content = uploaded_file.getvalue().decode("utf-8")
        elif uploaded_file.name.endswith('.pdf'):
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages: content += page.extract_text() + "\n"
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs])
    except: return None
    return content

# [기존] 미디어 파일 처리
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
    except Exception as e:
        st.error(f"파일 처리 오류: {e}")
        return None

# [기존] 유튜브 오디오 다운로드
def download_and_upload_youtube_audio(url):
    if yt_dlp is None:
        st.error("서버에 yt-dlp가 설치되지 않았습니다.")
        return None
    try:
        st.toast("유튜브 오디오 추출을 시작합니다...", icon="🎵")
        ydl_opts = {
            'format': 'bestaudio/best', 'outtmpl': 'temp_audio.%(ext)s', 'quiet': True,
            'overwrites': True, 'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {'User-Agent': 'Mozilla/5.0'}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
        
        audio_files = glob.glob("temp_audio.*")
        if not audio_files: return None
        audio_path = audio_files[0]
        
        st.toast("🤖 AI에게 데이터를 전달합니다...", icon="📂")
        myfile = genai.upload_file(audio_path)
        with st.spinner('🎧 유튜브 콘텐츠를 심층 분석 중입니다...'):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
        os.remove(audio_path)
        return myfile
    except Exception as e: return None

# [기존] 유튜브 자막 및 웹 콘텐츠
def get_youtube_transcript(url):
    try:
        if "youtu.be" in url: video_id = url.split("/")[-1]
        else: video_id = url.split("v=")[-1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        return " ".join([t['text'] for t in transcript])
    except: return None

def get_web_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style"]): script.decompose()
        return soup.get_text()[:10000]
    except Exception as e: return f"[오류] {e}"

# ==========================================
# 7. 메인 화면 구성
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

# 탭 구성 (총 5개)
tab_audit, tab1, tab2, tab3, tab_admin = st.tabs(["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"])

# --- [Tab New] 자율점검 (참여자 정보 추가 반영) ---
with tab_audit:
    # [관리자 설정 구역]
    current_campaign_title = "1월: 설 명절 '청탁금지법' 자율점검"
    current_sheet_name = "1월_설명절_캠페인"  
    # ----------------------------------------

    st.markdown(f"### 🎍 {current_campaign_title}")
    st.markdown("""
    <div style="background-color: #FFF8E1; padding: 20px; border-radius: 10px; border: 1px solid #FFECB3; margin-bottom: 20px;">
        <h4 style="color: #795548; margin-top: 0;">📢 설 명절, 마음만 주고 받으세요!</h4>
        <ul style="color: #444; font-size: 14px; line-height: 1.6;">
            <li><strong>🙅‍♂️ 금지 행위:</strong> 직무 관련성 있는 자로부터의 금전, 선물, 향응 수수</li>
            <li><strong>📦 선물 반송:</strong> 불가피하게 선물을 받은 경우, 즉시 반송하고 감사실에 신고</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    with st.form("audit_submit_form", clear_on_submit=True):
        # [수정] 입력란을 4개 열로 구성 (사번, 성명, 조직, 부서)
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        
        # [데이터 반영] 분석된 조직 목록
        unit_list = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", unit_list)
        dept = c4.text_input("상세 부서명")
        
        st.markdown("**Q. 위 내용을 확인하였으며, 설 명절 기간 동안 이를 철저히 준수할 것을 서약합니다.**")
        agree_check = st.checkbox("네, 확인하였으며 서약합니다.")
        
        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name: st.warning("⚠️ 사번과 성명을 입력해주세요.")
            elif not agree_check: st.error("❌ 서약에 체크해주세요.")
            else:
                with st.spinner("제출 중..."):
                    # unit 인자 추가하여 저장
                    success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet_name)
                    if success:
                        st.success(f"✅ {name}님, 제출 완료! ({current_sheet_name}에 저장됨)")
                        st.balloons()
                    else: st.error(f"❌ 실패: {msg}")

# --- [Tab 1] 문서 정밀 검토 (기본 유지) ---
with tab1:
    st.markdown("### 📂 작업 및 파일 설정")
    if 'api_key' not in st.session_state:
        st.warning("🔒 이 기능을 사용하려면 먼저 로그인이 필요합니다.")
    else:
        option = st.selectbox("작업 유형 선택", ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"))
        
        is_authenticated = True
        if option == "감사 보고서 검증":
            if 'audit_verified' not in st.session_state:
                is_authenticated = False
                st.warning("🔒 이 메뉴는 감사실 전용 메뉴입니다.")
                with st.form("auth_form"):
                    pass_input = st.text_input("계속하시려면 인증키를 입력하세요", type="password")
                    if st.form_submit_button("인증 확인"):
                        real_key = "ktmos0402!"
                        if hashlib.sha256(pass_input.encode()).hexdigest() == hashlib.sha256(real_key.encode()).hexdigest():
                            st.session_state['audit_verified'] = True
                            st.rerun()
        
        st.markdown("---")
        if is_authenticated:
            uploaded_file = st.file_uploader("검토 파일 업로드", type=['txt', 'pdf', 'docx'], key="target")
            if st.button("🚀 분석 리포트 생성", use_container_width=True):
                if uploaded_file:
                    content = read_file(uploaded_file)
                    if content:
                        model = get_model()
                        res = model.generate_content(f"[작업] {option}\n[내용] {content}")
                        st.markdown(res.text)

# --- [Tab 2] 챗봇 (기본 유지) ---
with tab2:
    st.markdown("### 🗣️ 실시간 질의응답")
    if 'api_key' not in st.session_state:
        st.warning("🔒 이 기능을 사용하려면 먼저 로그인이 필요합니다.")
    else:
        with st.form(key='chat_form', clear_on_submit=True):
            user_input = st.text_input("질문 입력")
            submit_chat = st.form_submit_button("전송 📤")
        if "messages" not in st.session_state: st.session_state.messages = []
        if submit_chat and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            model = get_model()
            res = model.generate_content(user_input)
            st.session_state.messages.append({"role": "assistant", "content": res.text})
        for m in reversed(st.session_state.messages):
            with st.chat_message(m['role']): st.write(m['content'])

# --- [Tab 3] 스마트 요약 (기본 유지) ---
with tab3:
    st.markdown("### 📰 스마트 요약 & 인사이트")
    if 'api_key' not in st.session_state:
        st.warning("🔒 이 기능을 사용하려면 먼저 로그인이 필요합니다.")

# --- [Tab Admin] 관리자 대시보드 (화려한 그래프 반영) ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    admin_pw_input = st.text_input("비밀번호", type="password", key="admin_pw")
    
    if admin_pw_input.strip() == "ktmos0402!":
        st.success("접속 완료")
        
        # [데이터 분석] 제공된 인력현황 기반 정원 데이터 고정 반영
        target_dict = {
            "서부본부": 290, "강북본부": 222, "강남본부": 174, 
            "품질지원단": 138, "강원본부": 104, "경영총괄": 45, 
            "사업총괄": 37, "감사실": 3
        }
        total_target = sum(target_dict.values()) # 총 1,013명

        if st.button("🔄 실시간 참여 현황 업데이트"):
            try:
                client = init_google_sheet_connection()
                spreadsheet = client.open("Audit_Result_2026")
                sheet = spreadsheet.worksheet("1월_설명절_캠페인")
                data = sheet.get_all_records()
                
                if data:
                    df = pd.DataFrame(data)
                    curr_total = len(df)
                    participation_rate = (curr_total / total_target) * 100

                    # 1. 핵심 숫자 표시 (Key Metrics)
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("전체 대상자", f"{total_target}명")
                    m2.metric("참여 완료", f"{curr_total}명")
                    m3.metric("미참여", f"{total_target - curr_total}명")
                    m4.metric("전체 참여율", f"{participation_rate:.1f}%")

                    st.markdown("---")

                    # 2. 화려한 게이지 차트 (전체 진척도)
                    fig_gauge = go.Figure(go.Indicator(
                        mode = "gauge+number",
                        value = curr_total,
                        domain = {'x': [0, 1], 'y': [0, 1]},
                        title = {'text': "실시간 점검 완료 현황 (명)", 'font': {'size': 20}},
                        gauge = {
                            'axis': {'range': [None, total_target]},
                            'bar': {'color': "#2980B9"},
                            'steps': [
                                {'range': [0, total_target*0.5], 'color': "#FADBD8"}, # 50% 미만 빨강 계열
                                {'range': [total_target*0.5, total_target*0.8], 'color': "#FCF3CF"}, # 80% 미만 노랑 계열
                                {'range': [total_target*0.8, total_target], 'color': "#D4EFDF"}  # 80% 이상 초록 계열
                            ],
                            'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': curr_total}
                        }
                    ))
                    fig_gauge.update_layout(height=350)
                    st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': True}) # 카메라 아이콘 지원

                    # 3. 조직별 참여 상세 (목표 대비 실적)
                    st.subheader("📊 조직별 참여 상세 분석")
                    
                    # 시트 데이터에서 '총괄/본부/단' 열 기준 집계
                    if '총괄/본부/단' in df.columns:
                        actual_counts = df['총괄/본부/단'].value_counts().to_dict()
                    else:
                        actual_counts = {}
                    
                    stats_list = []
                    for unit, target in target_dict.items():
                        actual = actual_counts.get(unit, 0)
                        stats_list.append({
                            "조직": unit,
                            "참여완료": actual,
                            "미참여": max(0, target - actual),
                            "참여율(%)": round((actual/target)*100, 1)
                        })
                    
                    stats_df = pd.DataFrame(stats_list)

                    # 화려한 누적 막대 차트 (Plotly Express)
                    #                     fig_bar = px.bar(
                        stats_df, x="조직", y=["참여완료", "미참여"],
                        title="본부별 목표 대비 참여 인원 현황",
                        color_discrete_map={"참여완료": "#2ECC71", "미참여": "#E74C3C"},
                        text_auto=True
                    )
                    st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': True})

                    # 조직별 참여율 라인 차트
                    #                     fig_line = px.line(
                        stats_df, x="조직", y="참여율(%)",
                        title="조직별 참여율 (%)",
                        markers=True, text="참여율(%)"
                    )
                    fig_line.update_traces(line_color='#F1C40F', line_width=4, textposition="top center")
                    st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': True})

                    st.info("💡 각 그래프 우측 상단의 카메라 아이콘을 클릭하면 보고용 이미지로 저장할 수 있습니다.")

                    with st.expander("📝 상세 참여 데이터 명단 보기"):
                        st.dataframe(df, use_container_width=True)
                        st.download_button("📥 데이터 다운로드(CSV)", df.to_csv(index=False).encode('utf-8-sig'), "audit_result.csv")
                else:
                    st.info("데이터가 아직 없습니다. 첫 참여자가 발생하면 대시보드가 활성화됩니다.")
            except Exception as e:
                st.error(f"조회 오류: {e}. 시트 헤더가 [저장시간, 사번, 성명, 총괄/본부/단, 부서, 답변, 비고] 순서인지 확인해주세요.")

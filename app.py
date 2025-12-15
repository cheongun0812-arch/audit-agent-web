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

# yt_dlp 라이브러리 체크
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# ==========================================
# 1. 페이지 설정 (사이드바 강제 확장 고정)
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded" # [🚨핵심] 앱 시작 시 무조건 로그인창(사이드바) 열림
)

# ==========================================
# 2. 🎨 디자인 테마 (현관문 복구 + 핀셋 보안)
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

    /* 1. 기본 배경 및 폰트 */
    .stApp { background-color: #F4F6F9 !important; }
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 2. 사이드바 디자인 (무조건 보이게 설정) */
    [data-testid="stSidebar"] { 
        background-color: #2C3E50 !important; 
        display: block !important;
    }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* 3. 입력창 디자인 */
    input.stTextInput, textarea.stTextArea {
        background-color: #FFFFFF !important;
        color: #000000 !important; 
        -webkit-text-fill-color: #000000 !important;
        caret-color: #000000 !important;
        border: 1px solid #BDC3C7 !important;
    }
    input.stTextInput:focus, textarea.stTextArea:focus {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border-color: #2980B9 !important;
    }
    ::placeholder {
        color: #666666 !important;
        -webkit-text-fill-color: #666666 !important;
        opacity: 1 !important;
    }

    /* 4. 버튼 디자인 */
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }

    /* 🚨 5. [현관문 복구] 상단 메뉴 버튼 강제 노출 */
    /* 헤더가 가려져도 이 버튼만큼은 최상위(z-index)로 끌어올려 무조건 보이게 함 */
    [data-testid="stSidebarCollapsedControl"] {
        display: block !important;
        visibility: visible !important;
        color: transparent !important; /* 글씨만 투명 (keyboard... 제거용) */
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        border: 1px solid #ddd;
        width: 40px !important;
        height: 40px !important;
        z-index: 9999999 !important; /* 화면 맨 위로 */
        position: fixed;
        top: 15px; /* 위치 고정 */
        left: 0;
    }
    /* ☰ 아이콘 그리기 */
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        visibility: visible !important;
        color: #2C3E50 !important;
        font-size: 24px !important;
        font-weight: bold !important;
        position: absolute;
        top: 5px; left: 10px;
    }
    
    /* 6. 크리스마스 애니메이션 스타일 */
    .snow-bg {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.9); z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; color: white !important;
        pointer-events: none;
    }
    
    /* 7. 채팅 메시지 박스 */
    [data-testid="stChatMessage"] { background-color: #FFFFFF; border: 1px solid #eee; }
    [data-testid="stChatMessage"][data-testid="user"] { background-color: #E3F2FD; }

    /* 8. 탭 메뉴 폰트 확대 (20px Bold) */
    button[data-baseweb="tab"] div p {
        font-size: 20px !important;
        font-weight: 800 !important;
        color: #444444 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] div p {
        color: #2980B9 !important;
    }

    /* 🚨 9. [보안 수정] 헤더는 살리고, 내부 개인정보만 핀셋 삭제 */
    
    /* (1) 헤더 컨테이너: 보이게 하되 배경만 투명 (이래야 사이드바 버튼이 삼) */
    header[data-testid="stHeader"] {
        visibility: visible !important;
        background: transparent !important;
    }

    /* (2) Manage App 버튼 (ID 노출 주범) -> 삭제 */
    .stDeployButton { display: none !important; }
    
    /* (3) 우측 상단 툴바 (GitHub, 점3개 메뉴) -> 삭제 */
    [data-testid="stToolbar"] { display: none !important; }
    
    /* (4) 상단 알록달록 데코레이션 바 -> 삭제 */
    [data-testid="stDecoration"] { display: none !important; }
    
    /* (5) 하단 Footer -> 삭제 */
    footer { display: none !important; }
    
    /* (6) 햄버거 메뉴(우측 상단) -> 삭제 */
    #MainMenu { display: none !important; }

    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 처리 로직 (콜백 함수)
# ==========================================
def try_login():
    if 'login_input_key' in st.session_state:
        raw_key = st.session_state['login_input_key']
        clean_key = "".join(raw_key.split()) # 공백 제거
        
        if not clean_key:
            st.session_state['login_error'] = "⚠️ 키를 입력해주세요."
            return

        try:
            genai.configure(api_key=clean_key)
            list(genai.list_models()) # 검증
            
            st.session_state['api_key'] = clean_key
            st.session_state['login_error'] = None 
            
            encoded_key = base64.b64encode(clean_key.encode()).decode()
            try:
                st.query_params['k'] = encoded_key
            except:
                st.experimental_set_query_params(k=encoded_key)
                
        except Exception as e:
            st.session_state['login_error'] = f"❌ 인증 실패: {e}"

# ==========================================
# 4. 사이드바 구성
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    # 자동 로그인 복구
    if 'api_key' not in st.session_state:
        try:
            qp = st.query_params
        except:
            qp = st.experimental_get_query_params()

        if 'k' in qp:
            try:
                k_val = qp['k'][0] if isinstance(qp['k'], list) else qp['k']
                restored_key = base64.b64decode(k_val).decode('utf-8')
                genai.configure(api_key=restored_key)
                list(genai.list_models())
                st.session_state['api_key'] = restored_key
                st.toast("🔄 이전 세션이 복구되었습니다.", icon="✨")
                time.sleep(0.1)
                st.rerun()
            except:
                try:
                    st.query_params.clear()
                except:
                    st.experimental_set_query_params()

    # 로그인 전 (폼 표시)
    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.markdown("<h4 style='color:white; margin-bottom:5px;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input("Key", type="password", placeholder="API 키를 입력하세요", label_visibility="collapsed", key="login_input_key")
            submit_button = st.form_submit_button(label="시스템 접속 (Login)", on_click=try_login)
        
        if 'login_error' in st.session_state and st.session_state['login_error']:
            st.error(st.session_state['login_error'])

    # 로그인 후 (로그아웃 버튼 표시)
    else:
        st.success("🟢 정상 가동 중")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🎄 고마워! 또 봐! (Logout)", type="primary", use_container_width=True):
            st.session_state['logout_anim'] = True
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>Audit AI Solution © 2025<br>Engine: Gemini 1.5 Pro</div>", unsafe_allow_html=True)

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
    try:
        st.query_params.clear()
    except:
        st.experimental_set_query_params()
    st.session_state.clear()
    st.rerun()

# ==========================================
# 6. 핵심 기능 함수
# ==========================================
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

def process_media_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        st.toast("🤖 AI에게 분석 자료를 전달하고 있습니다...", icon="📂")
        myfile = genai.upload_file(tmp_path)
        
        with st.spinner('🎧 AI가 오디오/비디오 데이터를 분석하고 있습니다... (잠시만 기다려주세요)'):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
        
        os.remove(tmp_path)
        if myfile.state.name == "FAILED":
            st.error("❌ 파일 변환 실패")
            return None
        st.toast("✅ AI 분석 준비 완료!", icon="🎉")
        return myfile
    except Exception as e:
        st.error(f"파일 처리 오류: {e}")
        return None

def download_and_upload_youtube_audio(url):
    if yt_dlp is None:
        st.error("서버에 yt-dlp가 설치되지 않았습니다.")
        return None
    try:
        st.toast("유튜브 오디오 추출을 시작합니다...", icon="🎵")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'temp_audio.%(ext)s',
            'quiet': True,
            'overwrites': True,
            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
            'http_headers': {'User-Agent': 'Mozilla/5.0'}
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
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
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e):
            st.error("🔒 [유튜브 보안] 차단됨. 파일로 다운받아 업로드해주세요.")
        else:
            st.error(f"오디오 오류: {e}")
        return None

def get_youtube_transcript(url):
    try:
        if "youtu.be" in url: video_id = url.split("/")[-1]
        else: video_id = url.split("v=")[-1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        text = " ".join([t['text'] for t in transcript])
        return text
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

# 탭 구성
tab1, tab2, tab3 = st.tabs(["📄 문서 정밀 검토", "💬 Audit AI 에이전트 대화", "📰 스마트 요약"])

# --- Tab 1: 문서 검토 ---
with tab1:
    st.markdown("### 📂 작업 및 파일 설정")
    
    option = st.selectbox("작업 유형 선택", 
        ("법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"))
    
    # 🔒 감사실 보안 로직
    is_authenticated = True 
    
    if option == "감사 보고서 검증":
        if 'audit_verified' not in st.session_state:
            is_authenticated = False
            st.warning("🔒 이 메뉴는 감사실 전용 메뉴입니다.")
            
            with st.form("auth_form"):
                pass_input = st.text_input("계속하시려면 인증키를 입력하세요", type="password")
                check_btn = st.form_submit_button("인증 확인")
                
                if check_btn:
                    k1 = "kt"
                    k2 = "mos"
                    k3 = "0402"
                    k4 = "!"
                    real_key = k1 + k2 + k3 + k4
                    
                    if hashlib.sha256(pass_input.encode()).hexdigest() == hashlib.sha256(real_key.encode()).hexdigest():
                        st.session_state['audit_verified'] = True
                        st.success("🔓 인증되었습니다.")
                        st.rerun()
                    else:
                        st.error("❌ 인증키가 올바르지 않습니다.")
    
    st.markdown("---")
    
    if is_authenticated:
        st.info("👇 **검토할 파일 (필수)**")
        uploaded_file = st.file_uploader("검토 파일 업로드", type=['txt', 'pdf', 'docx'], key="target", label_visibility="collapsed")
        st.warning("📚 **참고 규정/지침 (선택)**")
        uploaded_refs = st.file_uploader("참고 파일 업로드", type=['txt', 'pdf', 'docx'], accept_multiple_files=True, label_visibility="collapsed")

        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                c = read_file(ref_file)
                if c: ref_content += c + "\n"

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 분석 리포트 생성 (Start)", use_container_width=True):
            if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
            elif not uploaded_file: st.warning("⚠️ 검토할 파일을 업로드해주세요.")
            else:
                st.toast("🤖 AI가 사용자의 질문을 충분히 이해하고 분석 중입니다.", icon="🔍")
                
                persona_name = "AI 감사 전문가"
                greeting = "안녕하세요. 업무를 도와드릴 AI 감사 전문가입니다."
                if "법률" in option: 
                    persona_name = "법률 전문가 AI 에이전트"
                    greeting = "안녕하세요. '법률 전문가 AI 에이전트'입니다."
                elif "오타" in option:
                    persona_name = "AI 에디터"
                    greeting = "안녕하세요. 'AI 에디터'입니다."
                elif "기안" in option:
                    persona_name = "AI 도큐멘트 페이퍼"
                    greeting = "안녕하세요. 'AI 도큐멘트 페이퍼'입니다."

                with st.spinner(f'🧠 {persona_name}가 문서를 정밀 분석 중입니다...'):
                    content = read_file(uploaded_file)
                    if content:
                        ref_final = ref_content if ref_content else "일반적인 비즈니스 및 법률 표준"
                        prompt = f"""[역할] {persona_name}
[지시] 반드시 다음 인사말로 시작: "{greeting}"
[작업] {option}
[기준] {ref_final}
[내용] {content}
[지침] 전문가로서 명확한 보고서 작성"""
                        try:
                            model = get_model()
                            response = model.generate_content(prompt)
                            st.success(f"✅ {persona_name} 분석 완료")
                            st.markdown(response.text)
                        except Exception as e: st.error(f"시스템 오류: {e}")

# --- Tab 2: 챗봇 ---
with tab2:
    st.markdown("### 🗣️ 실시간 질의응답")
    st.info("파일 내용이나 업무 관련 궁금한 점을 물어보세요.")
    
    with st.form(key='chat_form', clear_on_submit=True):
        user_input = st.text_input("질문 입력", placeholder="예: 하도급법 위반 사례를 알려줘")
        submit_chat = st.form_submit_button("전송 📤", use_container_width=True)

    if "messages" not in st.session_state: st.session_state.messages = []

    if submit_chat and user_input:
        if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("🤖 Audit AI 에이전트가 답변을 생성하고 있습니다..."):
                try:
                    genai.configure(api_key=st.session_state['api_key'])
                    context = ""
                    if ref_content: context += f"[참고자료]\n{ref_content}\n"
                    if uploaded_file: 
                        c = read_file(uploaded_file)
                        if c: context += f"[검토대상파일]\n{c}\n"
                    
                    full_prompt = f"""당신은 'AI 파인더'입니다. 친절하고 명확하게 답변하세요.
                    인사말: "안녕하세요. 여러분의 궁금증을 해소해 드릴 'AI 파인더'입니다." (필요시 사용)
                    [컨텍스트] {context}
                    [질문] {user_input}"""
                    
                    model = get_model()
                    response = model.generate_content(full_prompt)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e: st.error(f"오류: {e}")

    st.markdown("---")
    msgs = st.session_state.messages
    if len(msgs) >= 2:
        for i in range(len(msgs) - 1, 0, -2):
            asst_msg = msgs[i]
            user_msg = msgs[i-1]
            with st.chat_message("user", avatar="👤"): st.write(user_msg['content'])
            with st.chat_message("assistant", avatar="🛡️"): st.markdown(asst_msg['content'])
            st.divider()

# --- Tab 3: 스마트 요약 ---
with tab3:
    st.markdown("### 📰 스마트 요약 & 인사이트")
    
    summary_type = st.radio("입력 방식 선택", ["🌐 URL 입력", "📁 미디어 파일 업로드", "✍️ 텍스트 입력"])
    
    final_input = None
    is_multimodal = False

    if "URL" in summary_type:
        target_url = st.text_input("🔗 URL을 붙여넣으세요")
        if target_url:
            if "youtu" in target_url:
                with st.spinner("📺 유튜브 자막을 확인하고 있습니다..."):
                    text_data = get_youtube_transcript(target_url)
                    if text_data:
                        st.success("✅ 자막 확보 완료")
                        final_input = text_data
                    else:
                        st.warning("⚠️ 자막 없음 -> 오디오 직접 분석을 시도합니다.")
                        audio_file = download_and_upload_youtube_audio(target_url)
                        if audio_file:
                            final_input = audio_file
                            is_multimodal = True
            else:
                with st.spinner("🌐 웹페이지 콘텐츠를 가져오고 있습니다..."):
                    final_input = get_web_content(target_url)

    elif "미디어" in summary_type:
        media_file = st.file_uploader("영상/음성 파일 (MP3, WAV, MP4, M4A)", type=['mp3', 'wav', 'mp4', 'm4a'])
        if media_file:
            final_input = process_media_file(media_file)
            is_multimodal = True
            if final_input:
                st.success("✅ 파일 준비 완료! 요약 버튼을 눌러주세요.")

    else:
        final_input = st.text_area("내용을 직접 입력하세요", height=200)

    if st.button("✨ 요약 시작", use_container_width=True):
        if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
        elif not final_input: st.warning("분석할 대상을 입력하세요.")
        else:
            st.toast("🤖 AI가 사용자의 질문을 충분히 이해하고 분석 중입니다.", icon="🧠")
            
            with st.spinner('📊 전체 내용을 분석하여 요약 보고서를 작성 중입니다...'):
                try:
                    prompt = """[역할] 스마트 정보 분석가
[작업] 다음 내용을 분석하여 보고서 작성
1. 핵심 요약 (Executive Summary)
2. 상세 내용 (Key Details)
3. 감사/리스크 인사이트 (Insights)"""
                    model = get_model()
                    
                    if is_multimodal:
                        response = model.generate_content([prompt, final_input])
                    else: 
                        response = model.generate_content(f"{prompt}\n\n{final_input[:30000]}")
                        
                    st.success("분석 완료")
                    st.markdown(response.text)
                except Exception as e: st.error(f"오류: {e}")


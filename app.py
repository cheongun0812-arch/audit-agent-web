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
# 2. 🎨 [디자인] V48 성공 로직 복원 + 필수 수정 사항 통합
# ==========================================
st.markdown("""
    <style>
    /* 1. 기본 배경 */
    .stApp { background-color: #F4F6F9 !important; }
    * { font-family: 'Pretendard', sans-serif !important; }

    /* 2. 사이드바 디자인 */
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* 🚨 3. [V48 방식 복원] 상단 메뉴 버튼: 글씨 투명화 기법 (성공했던 방식) 🚨 */
    [data-testid="stSidebarCollapsedControl"] {
        color: transparent !important; /* 글씨를 투명하게 만듦 */
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        border: 1px solid #ddd;
        width: 40px !important;
        height: 40px !important;
        z-index: 99999;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* ☰ 햄버거 아이콘 덮어쓰기 */
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰";
        color: #2C3E50 !important; /* 아이콘 색상 */
        font-size: 24px !important;
        font-weight: bold !important;
        position: absolute;
    }

    /* 4. 입력창 디자인 (모바일 텍스트 실종 방지) */
    input.stTextInput, textarea.stTextArea {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important; /* 모바일 크롬 강제 */
        caret-color: #000000 !important;
        border: 1px solid #BDC3C7 !important;
        font-weight: 500 !important;
    }
    ::placeholder {
        color: #666666 !important;
        -webkit-text-fill-color: #666666 !important;
        opacity: 1 !important;
    }

    /* 5. 버튼 디자인 */
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
        height: 45px !important;
    }

    /* 6. 크리스마스 애니메이션 스타일 */
    .snow-bg {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0, 0, 0, 0.9); z-index: 999999;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        text-align: center; color: white !important;
    }
    
    /* 7. 채팅 메시지 박스 */
    [data-testid="stChatMessage"] { background-color: #FFFFFF; border: 1px solid #eee; }
    [data-testid="stChatMessage"][data-testid="user"] { background-color: #E3F2FD; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 사이드바 (로그인 & 로그아웃)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    # 로그인 전
    if 'api_key' not in st.session_state:
        with st.form(key='login_form'):
            st.markdown("<h4 style='color:gray; margin-bottom:5px;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            api_key_input = st.text_input("Key", type="password", placeholder="API 키 입력", label_visibility="collapsed")
            submit_button = st.form_submit_button(label="시스템 접속 (Login)")
        
        if submit_button:
            if api_key_input:
                clean_key = api_key_input.strip()
                try:
                    genai.configure(api_key=clean_key)
                    st.session_state['api_key'] = clean_key
                    st.success("✅ 접속 완료")
                    time.sleep(0.5)
                    st.rerun()
                except:
                    st.error("❌ 키 오류")
            else:
                st.warning("⚠️ 키 입력 필요")

    # 로그인 후
    else:
        st.success("🟢 정상 가동 중")
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🎄 고마워! 또 봐! (Logout)", type="primary", use_container_width=True):
            st.session_state['logout_anim'] = True
            st.rerun()

    st.markdown("---")
    st.markdown("<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>Audit AI Solution © 2025<br>Engine: Gemini 1.5 Pro</div>", unsafe_allow_html=True)

# ==========================================
# 4. 🎅 크리스마스 작별 애니메이션 (코드 노출 방지)
# ==========================================
if 'logout_anim' in st.session_state and st.session_state['logout_anim']:
    # HTML 들여쓰기를 제거하여 코드로 인식되는 문제 해결
    st.markdown("""
<div class="snow-bg">
<div style="font-size: 80px; margin-bottom: 20px;">🎅🎄</div>
<h1 style="color: white !important;">Merry Christmas!</h1>
<h3 style="color: #ddd !important;">오늘도 수고 많으셨습니다.<br>따뜻한 연말 보내세요! ❤️</h3>
</div>
""", unsafe_allow_html=True)
    
    time.sleep(3.0)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ==========================================
# 5. 핵심 기능 함수
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

def download_and_upload_youtube_audio(url):
    if yt_dlp is None:
        st.error("서버에 yt-dlp가 설치되지 않았습니다.")
        return None
    try:
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
        myfile = genai.upload_file(audio_path)
        while myfile.state.name == "PROCESSING":
            time.sleep(2)
            myfile = genai.get_file(myfile.name)
        os.remove(audio_path)
        return myfile
    except Exception as e:
        if "403" in str(e) or "Forbidden" in str(e):
            st.error("🔒 [보안 차단] 유튜브 정책상 자동 다운로드가 제한됩니다.")
            st.info("💡 해당 영상을 파일로 다운받아 '미디어 파일 업로드' 기능을 이용해주세요.")
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

def process_media_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{uploaded_file.name.split('.')[-1]}") as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        myfile = genai.upload_file(tmp_path)
        with st.spinner('🎧 파일 분석 준비 중...'):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)
        os.remove(tmp_path)
        return myfile
    except Exception as e:
        st.error(f"파일 오류: {e}")
        return None

# ==========================================
# 6. 메인 화면 구성
# ==========================================

st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

# [수정] 탭 명칭 및 아이콘 최종 확인
tab1, tab2, tab3 = st.tabs(["📄 문서 정밀 검토", "💬 Audit AI 에이전트 대화", "📰 스마트 요약"])

# --- Tab 1: 문서 검토 ---
with tab1:
    # [수정] 📂 폴더 아이콘 적용
    st.markdown("### 📂 작업 및 파일 설정")
    option = st.selectbox("작업 유형 선택", 
        ("법률 리스크 정밀 검토", "감사 보고서 초안 작성", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"))
    st.markdown("---")
    
    # [수정] 모바일 깨짐 방지: 1단 배치 (st.columns 제거)
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

            with st.spinner(f'🧠 {persona_name}가 문서를 분석 중입니다...'):
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
    
    # [수정] 모바일 깨짐 방지: 1단 배치
    with st.form(key='chat_form', clear_on_submit=True):
        user_input = st.text_input("질문 입력", placeholder="예: 하도급법 위반 사례를 알려줘")
        submit_chat = st.form_submit_button("전송 📤", use_container_width=True)

    if "messages" not in st.session_state: st.session_state.messages = []

    if submit_chat and user_input:
        if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("Audit AI 에이전트가 답변을 생성 중입니다..."):
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
    
    # [수정] 라디오 버튼 단순화
    summary_type = st.radio("입력 방식 선택", ["🌐 URL 입력", "📁 미디어 파일 업로드", "✍️ 텍스트 입력"])
    
    final_input = None
    is_multimodal = False

    if "URL" in summary_type:
        target_url = st.text_input("🔗 URL을 붙여넣으세요")
        if target_url:
            if "youtu" in target_url:
                with st.spinner("자막 확인 중..."):
                    text_data = get_youtube_transcript(target_url)
                    if text_data:
                        st.success("✅ 자막 확보 완료")
                        final_input = text_data
                    else:
                        st.warning("⚠️ 자막 없음 -> 오디오 다운로드 시도")
                        audio_file = download_and_upload_youtube_audio(target_url)
                        if audio_file:
                            final_input = audio_file
                            is_multimodal = True
            else:
                with st.spinner("웹사이트 분석 중..."):
                    final_input = get_web_content(target_url)

    elif "미디어" in summary_type:
        media_file = st.file_uploader("영상/음성 파일 (MP3, MP4)", type=['mp3', 'mp4', 'm4a', 'wav'])
        if media_file:
            final_input = process_media_file(media_file)
            is_multimodal = True

    else:
        final_input = st.text_area("내용을 직접 입력하세요", height=200)

    if st.button("✨ 요약 시작", use_container_width=True):
        if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
        elif not final_input: st.warning("분석할 대상을 입력하세요.")
        else:
            with st.spinner('🧠 AI가 핵심 내용을 요약 중입니다...'):
                try:
                    prompt = """[역할] 스마트 정보 분석가
[작업] 다음 내용을 분석하여 보고서 작성
1. 핵심 요약 (Executive Summary)
2. 상세 내용 (Key Details)
3. 감사/리스크 인사이트 (Insights)"""
                    model = get_model()
                    if is_multimodal: response = model.generate_content([prompt, final_input])
                    else: response = model.generate_content(f"{prompt}\n\n{final_input[:30000]}")
                    st.success("분석 완료")
                    st.markdown(response.text)

                except Exception as e: st.error(f"오류: {e}")

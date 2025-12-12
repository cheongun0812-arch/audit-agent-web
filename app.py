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
# 2. 🎨 [디자인] 책갈피 UI & V27 테마 적용
# ==========================================
st.markdown("""
    <style>
    /* 1. 기본 배경 및 폰트 */
    .stApp { background-color: #F4F6F9 !important; }
    html, body, p, div, span, label, h1, h2, h3, h4, h5, h6, li {
        color: #333333 !important; font-family: 'Pretendard', sans-serif !important;
    }

    /* 2. 사이드바 디자인 */
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    /* 3. [핵심] 상단 못생긴 버튼 -> '책갈피' 스타일로 성형수술 🔖 */
    
    /* (1) 버튼 껍데기 디자인 (책갈피 모양) */
    [data-testid="stSidebarCollapsedControl"] {
        background-color: #FFFFFF !important;
        color: transparent !important; /* 기존 글씨(keyboard...)를 투명하게 만듦 */
        border-radius: 0 12px 12px 0 !important; /* 오른쪽만 둥글게 */
        border: 1px solid #E0E0E0 !important;
        border-left: none !important;
        box-shadow: 2px 2px 8px rgba(0,0,0,0.1) !important;
        top: 60px !important; /* 위치를 살짝 아래로 */
        left: 0 !important;
        width: 40px !important;
        height: 40px !important;
        z-index: 99999 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    /* (2) 기존 아이콘(SVG) 강제로 숨김 */
    [data-testid="stSidebarCollapsedControl"] > svg, 
    [data-testid="stSidebarCollapsedControl"] > img {
        display: none !important;
    }
    
    /* (3) 새로운 햄버거 아이콘(☰) 심기 */
    [data-testid="stSidebarCollapsedControl"]::after {
        content: "☰"; 
        font-size: 24px;
        color: #2C3E50 !important; /* 아이콘 색상 (네이비) */
        font-weight: bold;
        position: absolute;
        margin-top: -2px;
    }
    
    /* (4) 마우스 올렸을 때 효과 */
    [data-testid="stSidebarCollapsedControl"]:hover {
        background-color: #F8F9FA !important;
        width: 45px !important; /* 살짝 튀어나옴 */
        transition: width 0.2s ease;
    }

    /* 4. 입력창 & 버튼 */
    .stTextInput input {
        background-color: #FFFFFF !important; color: #000000 !important;
        border: 1px solid #BDC3C7 !important; border-radius: 8px !important;
    }
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important; border: none; border-radius: 8px; font-weight: bold;
    }
    
    /* 5. 채팅 메시지 박스 */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF !important; border: 1px solid #E0E0E0;
        border-radius: 12px;
    }
    [data-testid="stChatMessage"][data-testid="user"] { background-color: #EBF5FB !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 사이드바 (로그인)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    with st.form(key='login_form'):
        st.markdown("**🔐 Access Key**")
        api_key_input = st.text_input("키 입력", type="password", label_visibility="collapsed", placeholder="API 키를 붙여넣으세요")
        submit_button = st.form_submit_button(label="시스템 접속 (Log in)")
    
    if submit_button:
        if api_key_input:
            clean_key = api_key_input.strip()
            try:
                genai.configure(api_key=clean_key)
                st.session_state['api_key'] = clean_key
                st.success("✅ 접속 승인됨")
            except:
                st.error("❌ 유효하지 않은 키")
        else:
            st.warning("⚠️ 키를 입력하세요")
            
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("🟢 Pro Engine 가동 중")
        
    st.markdown("---")
    st.markdown("<div style='text-align: center; font-size: 11px; opacity: 0.7;'>Audit AI Solution © 2025<br>Engine: Gemini 1.5 Pro</div>", unsafe_allow_html=True)

# ==========================================
# 4. 기능 함수
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
            st.error("🔒 [보안 차단] 유튜브 보안으로 인해 자동 다운로드가 막혔습니다.")
            st.info("💡 '미디어 파일 업로드' 탭을 이용해 다운받은 파일을 직접 올려주세요.")
        else:
            st.error(f"오디오 처리 중 오류: {e}")
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
# 5. 메인 화면
# ==========================================

st.markdown("<h1 style='text-align: center; color: #2C3E50 !important;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #7F8C8D !important; margin-bottom: 25px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["  📄 문서 정밀 검토  ", "  💬 AI 감사관 대화  ", "  📰 스마트 요약  "])

# --- Tab 1 ---
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container():
        st.markdown("#### 1️⃣ 작업 선택")
        option = st.selectbox("작업 유형", ("법률 리스크 정밀 검토", "감사 보고서 초안 작성", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"), label_visibility="collapsed")
        
        st.markdown("#### 2️⃣ 파일 업로드")
        col1, col2 = st.columns(2)
        with col1:
            st.info("👇 **검토 파일**")
            uploaded_file = st.file_uploader("검토 파일", type=['txt', 'pdf', 'docx'], key="target", label_visibility="collapsed")
        with col2:
            st.warning("📚 **참고 규정**")
            uploaded_refs = st.file_uploader("참고 파일", type=['txt', 'pdf', 'docx'], accept_multiple_files=True, label_visibility="collapsed")

        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                c = read_file(ref_file)
                if c: ref_content += c + "\n"

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 분석 리포트 생성 (Start Analysis)", use_container_width=True):
            if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
            elif not uploaded_file: st.warning("⚠️ 파일 필요")
            else:
                with st.spinner('🧠 AI(Pro)가 분석 중...'):
                    content = read_file(uploaded_file)
                    if content:
                        ref_final = ref_content if ref_content else "일반 표준"
                        prompt = f"[역할]수석감사관 [작업]{option} [기준]{ref_final} [내용]{content} [지침]전문가보고서작성"
                        try:
                            model = get_model()
                            response = model.generate_content(prompt)
                            st.success("✅ 완료")
                            st.markdown(response.text)
                        except Exception as e: st.error(f"오류: {e}")

# --- Tab 2 ---
with tab2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🗣️ 실시간 질의응답")
    with st.container():
        with st.form(key='chat_form', clear_on_submit=True):
            col_icon, col_input, col_btn = st.columns([0.15, 0.6, 0.25])
            with col_icon: st.markdown("<div style='text-align: center; font-size: 24px;'>🤖</div>", unsafe_allow_html=True)
            with col_input: user_input = st.text_input("질문", placeholder="질문 입력", label_visibility="collapsed")
            with col_btn: submit_chat = st.form_submit_button("전송", use_container_width=True)

    if "messages" not in st.session_state: st.session_state.messages = []
    loading_placeholder = st.empty()

    if submit_chat and user_input:
        if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with loading_placeholder.container():
                st.markdown("""<div style='text-align: center; margin: 20px 0;'><span style='font-size: 30px;'>🤖 🔍</span><br><span style='color: #2980B9; font-weight: bold;'>답변 생성 중...</span></div>""", unsafe_allow_html=True)
            try:
                genai.configure(api_key=st.session_state['api_key'])
                context = ""
                if ref_content: context += f"[참고자료]\n{ref_content}\n"
                if uploaded_file: 
                    c = read_file(uploaded_file)
                    if c: context += f"[검토대상파일]\n{c}\n"
                full_prompt = f"당신은 AI 감사 전문가입니다. 상세하게 답변하세요.\n{context}\n질문: {user_input}"
                model = get_model()
                response = model.generate_content(full_prompt)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e: st.error(f"오류: {e}")
            loading_placeholder.empty()

    st.markdown("---")
    msgs = st.session_state.messages
    if len(msgs) >= 2:
        for i in range(len(msgs) - 1, 0, -2):
            asst_msg = msgs[i]
            user_msg = msgs[i-1]
            with st.chat_message("user", avatar="👤"): st.markdown(f"**질문:** {user_msg['content']}")
            with st.chat_message("assistant", avatar="🛡️"): st.markdown(asst_msg['content'])
            st.markdown("<hr style='border: 0; height: 1px; background: #BDC3C7; margin: 10px 0;'>", unsafe_allow_html=True)

# --- Tab 3: 스마트 요약 (변수명 버그 수정 완료) ---
with tab3:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📰 스마트 요약 & 인사이트")
    st.info("유튜브/뉴스 URL 또는 파일을 업로드하세요.")
    
    summary_type = st.radio("입력 방식", ("🌐 URL 입력 (유튜브/뉴스)", "📁 미디어 파일 업로드 (MP3/MP4)", "✍️ 텍스트 입력"), horizontal=True)
    
    final_input = None
    is_multimodal = False

    if summary_type == "🌐 URL 입력 (유튜브/뉴스)":
        target_url = st.text_input("🔗 URL 붙여넣기")
        if target_url:
            if "youtu" in target_url:
                with st.spinner("1단계: 자막 확인 중..."):
                    text_data = get_youtube_transcript(target_url)
                    if text_data:
                        st.success("✅ 자막 확보 완료")
                        final_input = text_data
                    else:
                        st.warning("⚠️ 자막이 없습니다. 오디오 듣기 모드로 전환합니다.")
                        with st.spinner("2단계: 오디오 다운로드 중..."):
                            audio_file = download_and_upload_youtube_audio(target_url)
                            if audio_file:
                                final_input = audio_file
                                is_multimodal = True
            else:
                with st.spinner("웹사이트 분석 중..."):
                    final_input = get_web_content(target_url)

    elif summary_type == "📁 미디어 파일 업로드 (MP3/MP4)":
        media_file = st.file_uploader("영상/음성 파일 (MP3/MP4)", type=['mp3', 'mp4', 'm4a', 'wav'])
        if media_file:
            final_input = process_media_file(media_file)
            is_multimodal = True

    else:
        final_input = st.text_area("내용 붙여넣기", height=200)

    if st.button("✨ 요약 시작", use_container_width=True):
        if 'api_key' not in st.session_state: st.error("🔒 로그인 필요")
        elif not final_input: st.warning("대상 입력 필요")
        else:
            with st.spinner('🧠 AI 심층 분석 중...'):
                try:
                    prompt = """
                    [역할] 감사실 수석 전문가
                    [작업] 제공된 내용을 바탕으로 다음 보고서 작성
                    1. 핵심 요약 (3줄)
                    2. 상세 내용 (논리적 정리)
                    3. 감사/리스크 인사이트 (시사점)
                    """
                    model = get_model()
                    
                    if is_multimodal:
                        response = model.generate_content([prompt, final_input])
                    else:
                        response = model.generate_content(f"{prompt}\n\n{final_input[:30000]}")
                    
                    st.success("분석 완료")
                    st.markdown("### 📑 요약 보고서")
                    st.markdown(response.text)
                except Exception as e: st.error(f"오류: {e}")
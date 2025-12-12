import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# ==========================================
# 2. 디자인 테마 (V27 절대 테마 유지)
# ==========================================
st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9 !important; }
    html, body, p, div, span, label, h1, h2, h3, h4, h5, h6, li {
        color: #333333 !important; font-family: 'Pretendard', sans-serif !important;
    }
    [data-testid="stSidebar"] { background-color: #2C3E50 !important; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stTextInput input {
        background-color: #FFFFFF !important; color: #000000 !important;
        border: 1px solid #BDC3C7 !important; border-radius: 8px !important;
    }
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important; border: none; border-radius: 8px; font-weight: bold;
    }
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
# 4. 기능 함수들 (모델, 파일읽기, 유튜브/웹 크롤링)
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

# [New] 유튜브 자막 추출 함수
def get_youtube_transcript(url):
    try:
        if "youtu.be" in url:
            video_id = url.split("/")[-1]
        else:
            query = urlparse(url).query
            params = parse_qs(query)
            video_id = params["v"][0]
        
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        text = " ".join([t['text'] for t in transcript])
        return text
    except Exception as e:
        return f"[오류] 자막을 가져올 수 없습니다. (원인: {e})"

# [New] 웹사이트 본문 추출 함수
def get_web_content(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 스크립트/스타일 제거
        for script in soup(["script", "style"]):
            script.decompose()
            
        return soup.get_text()[:10000] # 너무 길면 자름
    except Exception as e:
        return f"[오류] 웹사이트를 읽을 수 없습니다. (원인: {e})"

# ==========================================
# 5. 메인 화면
# ==========================================

st.markdown("<h1 style='text-align: center; color: #2C3E50 !important;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #7F8C8D !important; margin-bottom: 25px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

# 탭 메뉴가 3개로 늘어났습니다!
tab1, tab2, tab3 = st.tabs(["  📄 문서 정밀 검토  ", "  💬 AI 감사관 대화  ", "  📰 스마트 요약  "])

# --- Tab 1: 문서 검토 (기존 유지) ---
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
            if 'api_key' not in st.session_state:
                st.error("🔒 로그인 필요")
            elif not uploaded_file:
                st.warning("⚠️ 파일 필요")
            else:
                with st.spinner('🧠 AI(Pro)가 분석 중입니다...'):
                    content = read_file(uploaded_file)
                    if content:
                        ref_final = ref_content if ref_content else "일반 표준"
                        prompt = f"[역할]수석감사관 [작업]{option} [기준]{ref_final} [내용]{content} [지침]전문가보고서작성"
                        try:
                            model = get_model()
                            response = model.generate_content(prompt)
                            st.success("✅ 완료")
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"오류: {e}")

# --- Tab 2: 채팅 (기존 유지) ---
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
        if 'api_key' not in st.session_state:
            st.error("🔒 로그인 필요")
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
            except Exception as e:
                st.error(f"오류: {e}")
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

# --- Tab 3: [New!] 스마트 요약 (유튜브/뉴스) ---
with tab3:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 📰 스마트 요약 & 인사이트")
    st.info("유튜브 영상 링크나 뉴스 기사 URL, 또는 텍스트를 직접 입력하면 핵심만 요약해 드립니다.")
    
    summary_type = st.radio("입력 방식 선택", ("🌐 URL 입력 (유튜브/뉴스)", "✍️ 텍스트 직접 입력"), horizontal=True)
    
    input_content = ""
    
    if summary_type == "🌐 URL 입력 (유튜브/뉴스)":
        target_url = st.text_input("🔗 URL을 여기에 붙여넣으세요 (유튜브, 신문기사 등)")
        if target_url:
            if "youtube.com" in target_url or "youtu.be" in target_url:
                st.caption("📺 유튜브 링크가 감지되었습니다. 자막을 추출합니다...")
                with st.spinner("자막 다운로드 중..."):
                    input_content = get_youtube_transcript(target_url)
            else:
                st.caption("🌐 웹사이트 링크가 감지되었습니다. 본문을 추출합니다...")
                with st.spinner("웹사이트 읽는 중..."):
                    input_content = get_web_content(target_url)
                    
            if "[오류]" in input_content:
                st.error(input_content)
                input_content = "" # 오류 시 초기화
                
    else:
        input_content = st.text_area("📝 요약할 내용을 여기에 붙여넣으세요", height=200)

    if st.button("✨ 핵심 요약 및 인사이트 도출", use_container_width=True):
        if 'api_key' not in st.session_state:
            st.error("🔒 로그인 필요")
        elif not input_content:
            st.warning("요약할 내용이나 URL을 입력해주세요.")
        else:
            with st.spinner('🧠 AI가 내용을 분석하고 요약 중입니다...'):
                try:
                    prompt = f"""
                    당신은 감사실 수석 전문가입니다. 
                    아래 제공된 내용(기사, 영상 자막 등)을 읽고 다음 형식으로 보고서를 작성해 주세요.
                    
                    1. **핵심 요약 (Executive Summary)**: 전체 내용을 3~5줄로 요약
                    2. **주요 포인트 (Key Takeaways)**: 중요한 사실이나 주장 5가지 (불렛포인트)
                    3. **감사/리스크 관점의 시사점 (Insights)**: 우리 회사나 업무에 미칠 수 있는 영향, 리스크, 기회요인 등 전문가적 견해 추가
                    
                    [대상 텍스트]
                    {input_content[:20000]} 
                    (내용이 너무 길면 앞부분 20000자만 처리)
                    """
                    
                    model = get_model()
                    response = model.generate_content(prompt)
                    
                    st.success("분석 완료!")
                    st.markdown("### 📑 AI 요약 보고서")
                    st.markdown(response.text)
                    
                except Exception as e:
                    st.error(f"오류: {e}")
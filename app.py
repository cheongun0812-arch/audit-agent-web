import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2
import time

# ==========================================
# 1. 페이지 설정 & 디자인 테마 적용
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# 🎨 [고급 인테리어] CSS 스타일 주입
st.markdown("""
    <style>
    /* 1. 전체 배경 및 폰트 설정 */
    .stApp {
        background-color: #F8F9FA; /* 아주 연한 회색 (눈이 편안함) */
        font-family: 'Pretendard', sans-serif;
    }
    
    /* 2. 메인 타이틀 디자인 (그라데이션 텍스트) */
    h1 {
        background: linear-gradient(to right, #0F2027, #203A43, #2C5364);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        text-align: center;
        padding-bottom: 20px;
    }

    /* 3. 버튼 디자인 (고급스러운 네이비 & 골드 호버) */
    .stButton>button {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        color: white;
        border: none;
        border-radius: 12px;
        font-weight: bold;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0,0,0,0.2);
        background: linear-gradient(90deg, #D4AF37 0%, #C5A028 100%); /* 골드 효과 */
    }

    /* 4. 입력창 및 박스 스타일 */
    .stTextInput>div>div>input {
        border-radius: 10px;
        border: 1px solid #E0E0E0;
        padding: 10px;
    }
    
    /* 5. 챗봇 메시지 스타일 강화 */
    .stChatMessage {
        background-color: white;
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        margin-bottom: 10px;
        border: 1px solid #f0f0f0;
    }

    /* 6. 탭 메뉴 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #ffffff;
        border-radius: 10px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [aria-selected="true"] {
        background-color: #E3F2FD;
        color: #1565C0;
        font-weight: bold;
    }
    
    /* 7. 로더 애니메이션 스타일 */
    .loader {
        text-align: center;
        font-size: 40px;
        margin: 20px 0;
        animation: bounce 0.8s infinite alternate;
    }
    @keyframes bounce {
        from { transform: translateY(0); }
        to { transform: translateY(-10px); }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 사이드바 (로그인)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center") # 제목 변경
    with st.form(key='login_form'):
        st.info("🔐 보안 접속을 위해 API Key가 필요합니다.")
        api_key_input = st.text_input("Access Key", type="password", placeholder="여기에 키를 입력하세요")
        submit_button = st.form_submit_button(label="시스템 접속 🚀")
    
    if submit_button:
        if api_key_input:
            clean_key = api_key_input.strip()
            try:
                genai.configure(api_key=clean_key)
                st.session_state['api_key'] = clean_key
                st.success("접속 승인되었습니다.")
            except:
                st.error("유효하지 않은 키입니다.")
        else:
            st.warning("키를 입력해주세요.")
            
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("🟢 시스템 정상 가동 중")
        
    st.markdown("---")
    st.markdown("<div style='text-align: center; color: gray; font-size: 12px;'>Audit AI Solution © 2025</div>", unsafe_allow_html=True)

# ==========================================
# 3. 모델 및 파일 함수 (V23 동일)
# ==========================================
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    try:
        my_models = [m.name for m in genai.list_models()]
        for m in my_models:
            if 'flash' in m.lower(): return genai.GenerativeModel(m)
        for m in my_models:
            if 'pro' in m.lower() and 'vision' not in m.lower(): return genai.GenerativeModel(m)
        if my_models: return genai.GenerativeModel(my_models[0])
    except: pass
    return genai.GenerativeModel('gemini-pro')

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

# ==========================================
# 4. 메인 화면 구성
# ==========================================

# 헤더 섹션 (고급스러운 배지 효과)
st.markdown("<h1 style='text-align: center;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666; margin-top: -15px;'>Professional Legal & Audit Assistant System</p>", unsafe_allow_html=True)
st.divider()

tab1, tab2 = st.tabs(["📄 문서 정밀 검토", "💬 AI 감사관 대화"])

# --- Tab 1: 문서 검토 ---
with tab1:
    st.markdown("#### 📋 작업 설정")
    # 카드를 흉내낸 컨테이너
    with st.container():
        option = st.selectbox("수행할 작업을 선택하세요", 
            ("1. ⚖️ 법률 리스크 정밀 검토", "2. 📝 감사 보고서 초안 작성", "3. ✨ 오타 수정 및 문구 교정", "4. 📑 기안문/공문 초안 생성"))
        
        col1, col2 = st.columns(2)
        with col1:
            st.info("👇 **검토 대상 파일**")
            uploaded_file = st.file_uploader("파일 업로드", type=['txt', 'pdf', 'docx'], key="target", label_visibility="collapsed")
        with col2:
            st.warning("📚 **참고 규정/지침** (선택)")
            uploaded_refs = st.file_uploader("참고 파일", type=['txt', 'pdf', 'docx'], accept_multiple_files=True, label_visibility="collapsed")

        # 참고자료 처리
        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                c = read_file(ref_file)
                if c: ref_content += c + "\n"

        st.markdown("<br>", unsafe_allow_html=True) # 여백
        if st.button("🚀 분석 시작 (Start Analysis)", use_container_width=True):
            if 'api_key' not in st.session_state:
                st.error("🔒 로그인이 필요합니다.")
            elif not uploaded_file:
                st.warning("⚠️ 검토할 파일을 업로드해주세요.")
            else:
                with st.spinner('🔍 AI가 정밀 분석 중입니다...'):
                    content = read_file(uploaded_file)
                    if content:
                        ref_final = ref_content if ref_content else "일반적인 비즈니스 및 법률 표준"
                        prompt = f"역할:수석감사관. 모드:{option}. 기준:{ref_final}. 내용:{content}. 전문적인 보고서 형식으로 작성."
                        try:
                            model = get_model()
                            response = model.generate_content(prompt)
                            st.success("✅ 분석 완료")
                            st.markdown("### 📊 분석 결과 리포트")
                            st.markdown("---")
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"오류: {e}")

# --- Tab 2: 채팅 (피드형) ---
with tab2:
    st.markdown("#### 🗣️ 실시간 질의응답")
    
    # 입력창 디자인 (아이콘 + 입력 + 버튼)
    with st.container():
        with st.form(key='chat_form', clear_on_submit=True):
            col_icon, col_input, col_btn = st.columns([0.5, 4, 1.2])
            with col_icon:
                st.markdown("<div style='font-size: 28px; padding-top: 5px;'>🤖</div>", unsafe_allow_html=True)
            with col_input:
                user_input = st.text_input("질문", placeholder="예: 이 조항의 독소조항 여부를 판단해줘", label_visibility="collapsed")
            with col_btn:
                submit_chat = st.form_submit_button("전송 📤", use_container_width=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 로딩 애니메이션
    loading_placeholder = st.empty()

    if submit_chat and user_input:
        if 'api_key' not in st.session_state:
            st.error("🔒 로그인 후 이용 가능합니다.")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # 고급스러운 로딩 애니메이션
            with loading_placeholder.container():
                st.markdown("""
                <div class="loader">
                    🤖<br>
                    <span style='font-size: 18px; color: #2C5364;'>Data Analyzing...</span>
                </div>
                """, unsafe_allow_html=True)

            try:
                genai.configure(api_key=st.session_state['api_key'])
                
                context = ""
                if ref_content: context += f"[참고자료]\n{ref_content}\n"
                if uploaded_file: 
                    c = read_file(uploaded_file)
                    if c: context += f"[검토대상파일]\n{c}\n"
                
                full_prompt = f"{context}\n질문: {user_input}"
                
                model = get_model()
                response = model.generate_content(full_prompt)
                
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except Exception as e:
                st.error(f"System Error: {e}")
            
            loading_placeholder.empty()

    # 대화 목록 출력 (최신순 페어링)
    st.markdown("---")
    msgs = st.session_state.messages
    
    if len(msgs) >= 2:
        for i in range(len(msgs) - 1, 0, -2):
            asst_msg = msgs[i]
            user_msg = msgs[i-1]
            
            # 질문 카드 (파란색 포인트)
            with st.chat_message("user", avatar="👤"):
                st.markdown(f"**Question:**\n\n{user_msg['content']}")
                
            # 답변 카드 (회색 배경)
            with st.chat_message("assistant", avatar="🛡️"):
                st.markdown(f"**Answer:**\n\n{asst_msg['content']}")
            
            st.markdown("<hr style='border-top: 1px dashed #bbb;'>", unsafe_allow_html=True)
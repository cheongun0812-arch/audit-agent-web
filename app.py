import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2

# ==========================================
# 1. 페이지 설정 (디자인 기초)
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# ==========================================
# 2. 🎨 [핵심] 모바일/PC 통합 디자인 (CSS)
# ==========================================
st.markdown("""
    <style>
    /* 1. 강제 라이트 테마 적용 (다크모드 방지) */
    [data-testid="stAppViewContainer"] {
        background-color: #F5F7F9 !important; /* 아주 연한 블루그레이 (고급짐) */
    }
    [data-testid="stSidebar"] {
        background-color: #1A2530 !important; /* 사이드바: 딥 네이비 */
    }
    [data-testid="stSidebar"] * {
        color: #FFFFFF !important; /* 사이드바 글씨: 무조건 흰색 */
    }
    
    /* 2. 메인 텍스트 가독성 확보 */
    h1, h2, h3, p, div, span, label {
        color: #333333 !important; /* 본문 글씨: 진한 회색 (가독성 최우선) */
        font-family: 'Pretendard', sans-serif;
    }
    
    /* 3. 입력창 디자인 (경계선 명확하게) */
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border: 2px solid #E0E0E0 !important;
        border-radius: 8px !important;
    }
    .stTextInput input:focus {
        border-color: #2a5298 !important; /* 포커스 시 파란색 */
    }

    /* 4. 버튼 디자인 (그라데이션 & 그림자) */
    .stButton > button {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1) !important;
    }
    .stButton > button:active {
        transform: scale(0.98);
    }

    /* 5. 챗봇 메시지 카드 디자인 */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #EAEAEA !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
        margin-bottom: 12px !important;
    }
    /* 사용자 메시지 배경 (연한 파랑) */
    [data-testid="stChatMessage"][data-testid="user"] {
        background-color: #F0F7FF !important;
    }

    /* 6. 탭 메뉴 디자인 */
    .stTabs [data-baseweb="tab-list"] button {
        background-color: #FFFFFF !important;
        border-radius: 8px 8px 0 0 !important;
        color: #666666 !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        background-color: #1e3c72 !important; /* 선택된 탭: 네이비 */
        color: #FFFFFF !important;
    }

    /* 7. 모바일 폰트 크기 최적화 */
    @media (max-width: 640px) {
        h1 { font-size: 24px !important; }
        p, div { font-size: 16px !important; }
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 사이드바 (로그인)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")
    
    with st.form(key='login_form'):
        st.markdown("🔑 **Access Key**") # info 대신 markdown 사용 (색상 강제)
        api_key_input = st.text_input("키 입력", type="password", placeholder="여기에 붙여넣기", label_visibility="collapsed")
        submit_button = st.form_submit_button(label="시스템 접속 🚀")
    
    if submit_button:
        if api_key_input:
            clean_key = api_key_input.strip()
            try:
                genai.configure(api_key=clean_key)
                st.session_state['api_key'] = clean_key
                st.success("접속 승인 (Authorized)")
            except:
                st.error("유효하지 않은 키")
        else:
            st.warning("키를 입력하세요")
            
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("🟢 시스템 가동 중")
        
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.markdown("<div style='text-align: center; color: #888; font-size: 11px;'>Audit AI Solution © 2025</div>", unsafe_allow_html=True)

# ==========================================
# 4. 모델 자동 감지 (오류 해결 로직 포함)
# ==========================================
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    try:
        # 사용 가능한 모델 조회
        my_models = [m.name for m in genai.list_models()]
        
        # 1순위: Flash (속도/가성비)
        for m in my_models:
            if 'flash' in m.lower(): return genai.GenerativeModel(m)
        # 2순위: Pro (성능)
        for m in my_models:
            if 'pro' in m.lower() and 'vision' not in m.lower(): return genai.GenerativeModel(m)
        # 3순위: 아무거나
        if my_models: return genai.GenerativeModel(my_models[0])
    except: pass
    
    # 조회 실패 시 기본값 (404 방지)
    return genai.GenerativeModel('gemini-1.5-flash')

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
# 5. 메인 화면 구성
# ==========================================

# 헤더
st.markdown("<h1 style='text-align: center; padding-bottom: 10px;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; font-size: 14px; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["  📄 문서 정밀 검토  ", "  💬 AI 감사관 대화  "])

# --- Tab 1: 문서 검토 ---
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 카드형 UI
    with st.container():
        st.markdown("#### 1️⃣ 작업 선택")
        option = st.selectbox("작업 유형", 
            ("법률 리스크 정밀 검토", "감사 보고서 초안 작성", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"), label_visibility="collapsed")
        
        st.markdown("#### 2️⃣ 파일 업로드")
        col1, col2 = st.columns(2)
        with col1:
            st.info("👇 **검토할 파일**")
            uploaded_file = st.file_uploader("검토 파일", type=['txt', 'pdf', 'docx'], key="target", label_visibility="collapsed")
        with col2:
            st.warning("📚 **참고 규정** (선택)")
            uploaded_refs = st.file_uploader("참고 파일", type=['txt', 'pdf', 'docx'], accept_multiple_files=True, label_visibility="collapsed")

        # 참고자료 처리
        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                c = read_file(ref_file)
                if c: ref_content += c + "\n"

        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("🚀 분석 리포트 생성 (Start)", use_container_width=True):
            if 'api_key' not in st.session_state:
                st.error("🔒 왼쪽 메뉴에서 로그인을 먼저 해주세요.")
            elif not uploaded_file:
                st.warning("⚠️ 파일을 업로드해주세요.")
            else:
                with st.spinner('🔍 AI가 문서를 정밀 분석 중입니다...'):
                    content = read_file(uploaded_file)
                    if content:
                        ref_final = ref_content if ref_content else "일반적인 비즈니스 및 법률 표준"
                        prompt = f"역할:수석감사관. 모드:{option}. 기준:{ref_final}. 내용:{content}. 전문적인 보고서 형식으로 작성."
                        try:
                            model = get_model()
                            response = model.generate_content(prompt)
                            st.success("✅ 분석 완료")
                            st.markdown("### 📊 분석 결과")
                            st.markdown("---")
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"시스템 오류: {e}")

# --- Tab 2: 채팅 (피드형 + 디자인 개선) ---
with tab2:
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 채팅 입력창 UI
    st.markdown("#### 🗣️ 실시간 질의응답")
    with st.container():
        with st.form(key='chat_form', clear_on_submit=True):
            col_icon, col_input, col_btn = st.columns([0.15, 0.6, 0.25])
            with col_icon:
                st.markdown("<div style='font-size: 24px; padding-top: 5px; text-align: center;'>🤖</div>", unsafe_allow_html=True)
            with col_input:
                user_input = st.text_input("질문", placeholder="내용을 입력하세요", label_visibility="collapsed")
            with col_btn:
                submit_chat = st.form_submit_button("전송", use_container_width=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 로딩 애니메이션
    loading_placeholder = st.empty()

    if submit_chat and user_input:
        if 'api_key' not in st.session_state:
            st.error("🔒 로그인 필요")
        else:
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # 애니메이션
            with loading_placeholder.container():
                st.markdown("""
                <div style='text-align: center; margin: 20px 0;'>
                    <span style='font-size: 30px;'>🤖 🔍</span><br>
                    <span style='color: #2a5298; font-weight: bold;'>답변을 찾고 있습니다...</span>
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
                st.error(f"오류: {e}")
            
            loading_placeholder.empty()

    # 대화 목록 출력 (최신순)
    st.markdown("---")
    msgs = st.session_state.messages
    
    if len(msgs) >= 2:
        for i in range(len(msgs) - 1, 0, -2):
            asst_msg = msgs[i]
            user_msg = msgs[i-1]
            
            # 질문 (파란색 아이콘)
            with st.chat_message("user", avatar="👤"):
                st.markdown(f"**질문:** {user_msg['content']}")
                
            # 답변 (방패 아이콘)
            with st.chat_message("assistant", avatar="🛡️"):
                st.markdown(asst_msg['content'])
            
            st.markdown("<hr style='border: 0; height: 1px; background: #E0E0E0; margin: 10px 0;'>", unsafe_allow_html=True)
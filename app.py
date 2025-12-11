import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# ==========================================
# 2. 🎨 [디자인 교정] 모바일/PC 완벽 호환 CSS
# ==========================================
st.markdown("""
    <style>
    /* 1. 기본 배경 및 폰트 강제 설정 (다크모드 무시) */
    .stApp {
        background-color: #F4F6F9 !important; /* 아주 연한 회색 배경 */
    }
    html, body, p, div, span, label, h1, h2, h3, h4, h5, h6, li {
        color: #333333 !important; /* 글씨는 무조건 진한 회색 */
        font-family: 'Pretendard', sans-serif !important;
    }

    /* 2. 사이드바 (Control Center) 디자인 수정 */
    [data-testid="stSidebar"] {
        background-color: #2C3E50 !important; /* 고급스러운 미드나잇 블루 */
    }
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important; /* 사이드바 제목은 흰색 */
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label {
        color: #ECF0F1 !important; /* 사이드바 본문은 밝은 회색 */
    }

    /* 3. 입력창 디자인 (흰 배경 + 검은 글씨 강제) */
    .stTextInput input {
        background-color: #FFFFFF !important;
        color: #000000 !important; /* 입력 글씨 검은색 강제 */
        border: 1px solid #BDC3C7 !important;
        border-radius: 8px !important;
    }
    .stTextInput input::placeholder {
        color: #95A5A6 !important; /* 플레이스홀더 잘 보이게 */
    }
    /* 셀렉트박스(메뉴) 디자인 */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        border-color: #BDC3C7 !important;
    }
    
    /* 4. 파일 업로더 디자인 */
    [data-testid="stFileUploader"] {
        background-color: #FFFFFF !important;
        border-radius: 10px;
        padding: 15px;
        border: 1px dashed #BDC3C7;
    }
    [data-testid="stFileUploader"] section {
        background-color: #F8F9FA !important;
    }
    [data-testid="stFileUploader"] span {
        color: #555555 !important;
    }

    /* 5. 탭(Tab) 메뉴 디자인 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #FFFFFF !important;
        border-radius: 8px 8px 0 0;
        border: 1px solid #E0E0E0;
        border-bottom: none;
        padding: 10px 20px;
        color: #7F8C8D !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2980B9 !important; /* 선택된 탭: 파란색 */
        color: #FFFFFF !important; /* 선택된 글씨: 흰색 */
        font-weight: bold;
    }

    /* 6. 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* 7. 채팅 메시지 박스 */
    [data-testid="stChatMessage"] {
        background-color: #FFFFFF !important;
        border: 1px solid #E0E0E0;
        border-radius: 12px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    [data-testid="stChatMessage"][data-testid="user"] {
        background-color: #EBF5FB !important; /* 사용자 질문: 아주 연한 파랑 */
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
        st.markdown("**🔐 Access Key**")
        # placeholder 색상 문제 해결을 위해 안내 문구 수정
        api_key_input = st.text_input("키 입력", type="password", label_visibility="collapsed", placeholder="API 키를 여기에 붙여넣으세요")
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
        st.success("🟢 정상 가동 중")
        
    st.markdown("---")
    st.markdown("<div style='text-align: center; font-size: 11px; opacity: 0.7;'>Audit AI Solution © 2025<br>Security Level: High</div>", unsafe_allow_html=True)

# ==========================================
# 4. 모델 함수 (Gemini Pro 제거, Flash 고정)
# ==========================================
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
    
    # 묻지도 따지지도 않고 Flash 모델 사용 (오류 원천 차단)
    target_model = 'gemini-1.5-flash'
    try:
        # 혹시 목록에 정확한 명칭이 있다면 그걸 씀
        all_models = [m.name for m in genai.list_models()]
        for m in all_models:
            if '1.5-flash' in m:
                target_model = m
                break
    except: pass
    
    return genai.GenerativeModel(target_model)

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
# 5. 메인 화면
# ==========================================

# 헤더 디자인
st.markdown("<h1 style='text-align: center; color: #2C3E50 !important;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #7F8C8D !important; margin-bottom: 25px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["  📄 문서 정밀 검토  ", "  💬 AI 감사관 대화  "])

# --- Tab 1 ---
with tab1:
    st.markdown("<br>", unsafe_allow_html=True)
    with st.container():
        st.markdown("#### 1️⃣ 작업 선택")
        option = st.selectbox("작업 유형", ("법률 리스크 정밀 검토", "감사 보고서 초안 작성", "오타 수정 및 문구 교정", "기안문/공문 초안 생성"), label_visibility="collapsed")
        
        st.markdown("#### 2️⃣ 파일 업로드")
        col1, col2 = st.columns(2)
        with col1:
            st.info("👇 **검토 파일**") # 파란색 박스
            uploaded_file = st.file_uploader("검토 파일", type=['txt', 'pdf', 'docx'], key="target", label_visibility="collapsed")
        with col2:
            st.warning("📚 **참고 규정**") # 노란색 박스
            uploaded_refs = st.file_uploader("참고 파일", type=['txt', 'pdf', 'docx'], accept_multiple_files=True, label_visibility="collapsed")

        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                c = read_file(ref_file)
                if c: ref_content += c + "\n"

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 분석 리포트 생성 (Start Analysis)", use_container_width=True):
            if 'api_key' not in st.session_state:
                st.error("🔒 Control Center에서 로그인이 필요합니다.")
            elif not uploaded_file:
                st.warning("⚠️ 파일을 업로드해주세요.")
            else:
                with st.spinner('🔍 AI가 정밀 분석 중입니다...'):
                    content = read_file(uploaded_file)
                    if content:
                        ref_final = ref_content if ref_content else "일반 표준"
                        prompt = f"역할:수석감사관. 모드:{option}. 기준:{ref_final}. 내용:{content}. 전문적인 보고서 형식으로 작성."
                        try:
                            model = get_model()
                            response = model.generate_content(prompt)
                            st.success("✅ 분석 완료")
                            st.markdown("### 📊 분석 결과")
                            st.markdown(response.text)
                        except Exception as e:
                            st.error(f"오류: {e}")

# --- Tab 2 ---
with tab2:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### 🗣️ 실시간 질의응답")
    
    with st.container():
        with st.form(key='chat_form', clear_on_submit=True):
            col_icon, col_input, col_btn = st.columns([0.15, 0.6, 0.25])
            with col_icon: st.markdown("<div style='font-size: 24px; padding-top: 5px; text-align: center;'>🤖</div>", unsafe_allow_html=True)
            with col_input: 
                user_input = st.text_input("질문", placeholder="질문을 입력하세요", label_visibility="collapsed")
            with col_btn: 
                submit_chat = st.form_submit_button("전송", use_container_width=True)

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
                
                full_prompt = f"{context}\n질문: {user_input}"
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
import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="AUDIT AI agent",
    page_icon="🛡️",
    layout="centered"
)

# ==========================================
# 2. 사이드바 (로그인)
# ==========================================
with st.sidebar:
    st.header("🔐 로그인")
    with st.form(key='login_form'):
        st.info("⚠️ API Key를 입력하세요.")
        api_key_input = st.text_input("Google API Key", type="password")
        submit_button = st.form_submit_button(label="인증하기 ✅")
    
    if submit_button:
        if api_key_input:
            clean_key = api_key_input.strip()
            try:
                genai.configure(api_key=clean_key)
                st.session_state['api_key'] = clean_key
                st.success("인증 완료!")
            except:
                st.error("유효하지 않은 키입니다.")
        else:
            st.warning("키를 입력해주세요.")
            
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("인증 유지 중 ✅")

# ==========================================
# 3. 모델 자동 사냥 함수 (오류 방지용)
# ==========================================
def get_model():
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])

    try:
        my_models = [m.name for m in genai.list_models()]
        # 우선순위: Flash -> Pro
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
# 4. 메인 화면
# ==========================================

st.title("🛡️ AUDIT AI agent")

tab1, tab2 = st.tabs(["📑 문서 검토", "💬 AI 대화 (피드형)"])

# --- Tab 1 (기존과 동일) ---
with tab1:
    option = st.selectbox("작업 선택", 
        ("1. 법률 리스크 검토", "2. 감사 보고서 작성", "3. 문구 교정", "4. 기안문 생성"))
    uploaded_file = st.file_uploader("파일 선택", type=['txt', 'pdf', 'docx'], key="target")
    
    with st.expander("참고 자료 (선택)"):
        uploaded_refs = st.file_uploader("규정 업로드", type=['txt', 'pdf', 'docx'], accept_multiple_files=True)
        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                c = read_file(ref_file)
                if c: ref_content += c + "\n"

    if st.button("🚀 실행", use_container_width=True):
        if 'api_key' not in st.session_state:
            st.error("먼저 로그인해주세요.")
        elif not uploaded_file:
            st.warning("파일을 올려주세요.")
        else:
            with st.spinner('분석 중...'):
                content = read_file(uploaded_file)
                if content:
                    ref_final = ref_content if ref_content else "일반 표준"
                    prompt = f"역할:감사전문가. 모드:{option}. 기준:{ref_final}. 내용:{content}. 보고서작성."
                    try:
                        model = get_model()
                        response = model.generate_content(prompt)
                        st.success("완료!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"오류: {e}")

# --- Tab 2 (UI 전면 수정: 입력창 상단 + 최신순 정렬) ---
with tab2:
    # 1. 입력창을 최상단에 배치 (Form 사용)
    with st.container():
        st.markdown("##### 🗣️ 무엇이든 물어보세요")
        with st.form(key='chat_form', clear_on_submit=True):
            # clear_on_submit=True 덕분에 전송 후 입력창이 자동으로 비워집니다.
            user_input = st.text_input("질문 입력 (예: 하도급의 정의가 뭐야?)", key="input_text")
            col1, col2 = st.columns([4, 1])
            with col2:
                submit_chat = st.form_submit_button("전송 📤", use_container_width=True)

    # 대화 기록 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 2. 질문 처리 로직
    if submit_chat and user_input:
        if 'api_key' not in st.session_state:
            st.error("🔐 로그인 후 이용해주세요.")
        else:
            # (1) 사용자 질문 저장
            st.session_state.messages.append({"role": "user", "content": user_input})
            
            # (2) AI 답변 생성
            try:
                genai.configure(api_key=st.session_state['api_key'])
                
                context = ""
                if ref_content: context += f"[참고자료]\n{ref_content}\n"
                if uploaded_file: 
                    c = read_file(uploaded_file)
                    if c: context += f"[검토대상파일]\n{c}\n"
                
                full_prompt = f"{context}\n질문: {user_input}"
                
                model = get_model() # 자동 사냥 모델
                response = model.generate_content(full_prompt)
                
                # (3) AI 답변 저장
                st.session_state.messages.append({"role": "assistant", "content": response.text})
                
            except Exception as e:
                st.error(f"오류: {e}")

    # 3. 대화 목록 출력 (🚨 핵심: 역순 정렬 reversed)
    # 최신 대화가 입력창 바로 아래에 오도록 거꾸로 출력합니다.
    st.markdown("---")
    for msg in reversed(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
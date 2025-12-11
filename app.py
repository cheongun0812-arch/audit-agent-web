import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2
import time

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="AUDIT AI agent",
    page_icon="🛡️",
    layout="centered"
)

# ==========================================
# 2. 사이드바 (로그인 폼)
# ==========================================
with st.sidebar:
    st.header("🔐 로그인")
    
    with st.form(key='login_form'):
        st.info("⚠️ 본인의 API Key를 입력하세요.\n(모바일 복사 시 공백 주의!)")
        api_key_input = st.text_input("Google API Key", type="password")
        submit_button = st.form_submit_button(label="인증하기 ✅")
    
    if submit_button:
        if api_key_input:
            clean_key = api_key_input.strip() # 공백 제거 안전장치
            try:
                genai.configure(api_key=clean_key)
                st.session_state['api_key'] = clean_key
                st.success("인증 되었습니다!")
            except:
                st.error("유효하지 않은 키입니다.")
        else:
            st.warning("키를 입력해주세요.")
            
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("인증 상태 유지 중 ✅")

    st.markdown("---")
    st.markdown("**[모바일 사용 팁]**")
    st.markdown("1. 키 입력 후 **[인증하기]**")
    st.markdown("2. 팝업 뜨면 **[비밀번호 저장]**")
    st.markdown("3. 다음부턴 **자동 입력!**")

# ==========================================
# 3. 기능 함수 [🚨 핵심 수정: 모델 강제 고정]
# ==========================================

def get_model():
    # 복잡하게 찾지 말고, 무조건 '1.5 Flash'를 쓰도록 명령합니다.
    # 이 모델은 무료 한도가 매우 넉넉해서 429 오류가 거의 안 뜹니다.
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
    except Exception as e: return None
    return content

# ==========================================
# 4. 메인 화면
# ==========================================

st.title("🛡️ AUDIT AI agent")
st.markdown("### PC와 모바일 어디서든 쉽고 빠르게!")

tab1, tab2 = st.tabs(["📑 문서 검토/작성", "💬 AI 감사관과 대화"])

# --- [Tab 1] 문서 검토 ---
with tab1:
    option = st.selectbox(
        "작업을 선택하세요",
        ("1. ⚖️ 법률 리스크 정밀 검토", "2. 📝 감사 보고서 초안 작성", "3. ✨ 오타 수정 및 문구 교정", "4. 📑 기안문/공문 초안 생성")
    )

    st.markdown("##### 📂 검토 대상 파일")
    uploaded_file = st.file_uploader("파일 선택", type=['txt', 'pdf', 'docx'], key="target")

    with st.expander("📚 참고 자료 (선택)"):
        uploaded_refs = st.file_uploader("규정 업로드", type=['txt', 'pdf', 'docx'], accept_multiple_files=True)
        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                content = read_file(ref_file)
                if content: ref_content += content + "\n"

    if st.button("🚀 AI 검토 시작", use_container_width=True):
        if 'api_key' not in st.session_state:
            st.error("⛔ [오류] 먼저 사이드바에서 인증을 완료해주세요.")
        elif not uploaded_file:
            st.warning("파일을 업로드해주세요.")
        else:
            with st.spinner('분석 중... (Flash 모델 가동)'):
                content = read_file(uploaded_file)
                if content:
                    final_ref = ref_content if ref_content else "일반 표준"
                    prompt = f"당신은 감사 전문가입니다. 모드:{option}. 참고:{final_ref}. 내용:{content}. 보고서로 작성해."
                    try:
                        # 여기서 강제 고정된 Flash 모델을 불러옵니다.
                        model = get_model()
                        response = model.generate_content(prompt)
                        st.success("완료!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"오류: {e}")

# --- [Tab 2] 챗봇 기능 ---
with tab2:
    st.info("파일 내용에 대해 질문하세요.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("질문 입력..."):
        if 'api_key' not in st.session_state:
            st.error("⛔ API 키 인증이 풀렸습니다. 왼쪽 메뉴에서 다시 인증해주세요.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                context = ""
                if ref_content: context += f"[참고자료]\n{ref_content}\n"
                if uploaded_file: 
                    target_content = read_file(uploaded_file)
                    if target_content: context += f"[검토대상파일]\n{target_content}\n"
                
                final_prompt = f"{context}\n\n질문: {prompt}"
                
                try:
                    # 여기서도 강제 고정된 Flash 모델 사용
                    genai.configure(api_key=st.session_state['api_key'])
                    model = get_model()
                    
                    response = model.generate_content(final_prompt)
                    message_placeholder.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    if "400" in str(e) or "API_KEY_INVALID" in str(e):
                        st.error("⛔ 키가 잘못되었습니다. 다시 입력해주세요.")
                    else:
                        st.error(f"오류 발생: {e}")
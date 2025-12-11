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
# 2. 사이드바 (로그인 폼 - 공백 제거 기능 추가)
# ==========================================
with st.sidebar:
    st.header("🔐 로그인")
    
    with st.form(key='login_form'):
        st.info("⚠️ 본인의 API Key를 입력하세요.\n(모바일 복사 시 공백 주의!)")
        # [수정] 입력받은 키의 앞뒤 공백을 자동으로 제거 (.strip)
        api_key_input = st.text_input("Google API Key", type="password")
        submit_button = st.form_submit_button(label="인증하기 ✅")
    
    if submit_button:
        if api_key_input:
            clean_key = api_key_input.strip() # 공백 제거
            try:
                genai.configure(api_key=clean_key)
                st.session_state['api_key'] = clean_key # 깨끗한 키 저장
                st.success("인증 되었습니다!")
            except:
                st.error("유효하지 않은 키입니다.")
        else:
            st.warning("키를 입력해주세요.")
            
    # 새로고침 되어도 키가 있으면 다시 설정
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("인증 상태 유지 중 ✅")

    st.markdown("---")
    st.markdown("**[모바일 사용 팁]**")
    st.markdown("1. 키 복사 후 붙여넣기")
    st.markdown("2. **[인증하기]** 버튼 꼭 누르기")
    st.markdown("3. (오류 시) 키를 지우고 다시 입력")

# ==========================================
# 3. 기능 함수 (모델 자동 선택)
# ==========================================

def get_model():
    # 400 오류 방지를 위해, 키가 설정되었는지 확실히 체크
    if 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])

    candidates = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro']
    try:
        my_models = [m.name for m in genai.list_models()]
        for cand in candidates:
            for m in my_models:
                if cand in m: return genai.GenerativeModel(m)
    except: pass
    
    # 기본값
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
            with st.spinner('분석 중...'):
                content = read_file(uploaded_file)
                if content:
                    final_ref = ref_content if ref_content else "일반 표준"
                    prompt = f"당신은 감사 전문가입니다. 모드:{option}. 참고:{final_ref}. 내용:{content}. 보고서로 작성해."
                    try:
                        model = get_model()
                        response = model.generate_content(prompt)
                        st.success("완료!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"오류: {e}")

# --- [Tab 2] 챗봇 기능 (안전장치 강화) ---
with tab2:
    st.info("파일 내용에 대해 질문하세요.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("질문 입력..."):
        # [핵심] 채팅 시도 시 키가 있는지 다시 확인
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
                    # 모델 호출 전 재설정 (안전장치)
                    genai.configure(api_key=st.session_state['api_key'])
                    model = get_model()
                    
                    response = model.generate_content(final_prompt)
                    message_placeholder.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    # 400 오류가 뜨면 사용자에게 명확히 알려줌
                    if "400" in str(e) or "API_KEY_INVALID" in str(e):
                        st.error("⛔ [오류] API 키가 잘못되었습니다. 키를 지우고 다시 정확하게 입력해주세요. (공백 주의)")
                    else:
                        st.error(f"오류 발생: {e}")

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
# 2. 사이드바 (로그인 폼 적용 - 핵심 수정!)
# ==========================================
with st.sidebar:
    st.header("🔐 로그인")
    
    # 폼(Form)으로 감싸서 브라우저가 '로그인'으로 인식하게 유도
    with st.form(key='login_form'):
        st.info("⚠️ 본인의 API Key를 입력하세요.\n(최초 1회 입력 후 '저장' 권장)")
        
        # 비밀번호 입력창
        api_key_input = st.text_input("Google API Key", type="password")
        
        # 로그인 버튼 (이걸 눌러야 전송됨)
        submit_button = st.form_submit_button(label="인증하기 ✅")
    
    # 폼 제출 후 처리 로직
    if submit_button:
        if api_key_input:
            try:
                genai.configure(api_key=api_key_input)
                st.session_state['api_key'] = api_key_input # 세션에 저장
                st.success("인증 되었습니다!")
            except:
                st.error("잘못된 키입니다.")
        else:
            st.warning("키를 입력해주세요.")
            
    # 세션 유지용 (새로고침 전까지 유지)
    elif 'api_key' in st.session_state:
        genai.configure(api_key=st.session_state['api_key'])
        st.success("인증 상태 유지 중 ✅")

    st.markdown("---")
    st.markdown("**[모바일 사용 팁]**")
    st.markdown("1. 키 입력 후 **[인증하기]** 클릭")
    st.markdown("2. 팝업 뜨면 **[비밀번호 저장]** 누르기")
    st.markdown("3. 다음부턴 **생체인증**으로 자동 입력!")

# ==========================================
# 3. 기능 함수
# ==========================================
def get_model():
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
    except Exception as e: return None
    return content

# ==========================================
# 4. 메인 화면
# ==========================================

st.title("🛡️ AUDIT AI agent")
st.markdown("### PC와 모바일 어디서든 쉽고 빠르게!")

# 탭 메뉴
tab1, tab2 = st.tabs(["📑 문서 검토/작성", "💬 AI 감사관과 대화"])

# --- [Tab 1] 문서 검토 ---
with tab1:
    option = st.selectbox(
        "작업을 선택하세요",
        ("1. ⚖️ 법률 리스크 정밀 검토", "2. 📝 감사 보고서 초안 작성", "3. ✨ 오타 수정 및 문구 교정", "4. 📑 기안문/공문 초안 생성")
    )

    st.markdown("##### 📂 검토 대상(Target) 파일 업로드")
    uploaded_file = st.file_uploader("파일 선택 (폰 내장 파일/다운로드함)", type=['txt', 'pdf', 'docx'], key="target")

    # 참고 자료 업로드 (Tab1용)
    with st.expander("📚 참고 자료(Reference) 함께 올리기 (선택)"):
        uploaded_refs = st.file_uploader("규정/지침 파일 업로드", type=['txt', 'pdf', 'docx'], accept_multiple_files=True)
        ref_content = ""
        if uploaded_refs:
            for ref_file in uploaded_refs:
                content = read_file(ref_file)
                if content: ref_content += content + "\n"

    if st.button("🚀 AI 검토 시작", use_container_width=True):
        if 'api_key' not in st.session_state:
            st.error("⛔ 왼쪽 메뉴(>)에서 [인증하기]를 먼저 진행해주세요.")
        elif not uploaded_file:
            st.warning("검토할 파일을 업로드해주세요.")
        else:
            with st.spinner('분석 중입니다...'):
                content = read_file(uploaded_file)
                if content:
                    final_ref = ref_content if ref_content else "일반적인 비즈니스/법률 표준 및 상식"
                    prompt = f"""
                    당신은 감사실 수석 전문가입니다.
                    [작업 모드: {option}]
                    [참고 자료: {final_ref}]
                    [대상 파일 내용]
                    {content}
                    위 내용을 바탕으로 작업을 수행하고, 보고서로 작성해줘.
                    """
                    try:
                        model = get_model()
                        response = model.generate_content(prompt)
                        st.success("완료!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"오류: {e}")

# --- [Tab 2] 챗봇 기능 ---
with tab2:
    st.info("파일 내용에 대해 대화하듯 물어보세요.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("질문 입력..."):
        if 'api_key' not in st.session_state:
            st.error("API 키 인증이 필요합니다.")
        else:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                context = ""
                # Tab 1에서 올린 내용이 있다면 대화에 포함
                if ref_content: context += f"[참고자료]\n{ref_content}\n"
                if uploaded_file: 
                    target_content = read_file(uploaded_file)
                    if target_content: context += f"[검토대상파일]\n{target_content}\n"
                
                final_prompt = f"{context}\n\n질문: {prompt}"
                
                try:
                    model = get_model()
                    response = model.generate_content(final_prompt)
                    message_placeholder.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"오류: {e}")

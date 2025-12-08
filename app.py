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
# 2. 사이드바 (설정 및 참고자료)
# ==========================================
with st.sidebar:
    st.header("⚙️ 설정 및 자료")
    
    # 1. API 키
    with st.expander("🔐 API 키 설정", expanded=True):
        api_key_input = st.text_input("Google API Key", type="password", help="본인의 키를 입력하세요.")
        if api_key_input:
            try:
                genai.configure(api_key=api_key_input)
                st.success("인증 완료 ✅")
            except:
                st.error("잘못된 키입니다.")
        else:
            st.warning("키 입력 필요")

    st.markdown("---")
    
    # 2. [핵심 업그레이드] 참고 자료 업로드 기능
    st.header("📚 참고 자료(Reference)")
    st.info("검토 기준이 될 규정/지침 파일을 여기에 올려주세요.")
    uploaded_refs = st.file_uploader(
        "규정/매뉴얼 업로드 (여러 개 가능)", 
        type=['txt', 'pdf', 'docx'], 
        accept_multiple_files=True
    )
    
    # 참고 자료 텍스트 변환
    ref_content = ""
    if uploaded_refs:
        for ref_file in uploaded_refs:
            if ref_file.name.endswith('.txt'):
                ref_content += ref_file.getvalue().decode("utf-8") + "\n"
            elif ref_file.name.endswith('.pdf'):
                pdf_reader = PyPDF2.PdfReader(ref_file)
                for page in pdf_reader.pages: ref_content += page.extract_text() + "\n"
            elif ref_file.name.endswith('.docx'):
                doc = Document(ref_file)
                ref_content += "\n".join([para.text for para in doc.paragraphs]) + "\n"
        st.success(f"{len(uploaded_refs)}개의 참고 자료 로드 완료!")

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

# 탭 메뉴로 기능 분리
tab1, tab2 = st.tabs(["📑 문서 검토/작성", "💬 AI 감사관과 대화"])

# --- [Tab 1] 기존 문서 검토 기능 ---
with tab1:
    option = st.selectbox(
        "작업을 선택하세요",
        ("1. ⚖️ 법률 리스크 정밀 검토", "2. 📝 감사 보고서 초안 작성", "3. ✨ 오타 수정 및 문구 교정", "4. 📑 기안문/공문 초안 생성")
    )

    st.markdown("##### 📂 검토 대상(Target) 파일 업로드")
    uploaded_file = st.file_uploader("여기를 눌러 파일을 선택하세요", type=['txt', 'pdf', 'docx'], key="target")

    if st.button("🚀 AI 검토 시작", use_container_width=True):
        if not api_key_input:
            st.error("사이드바에 API 키를 입력해주세요.")
            st.stop()
        
        if not uploaded_file:
            st.warning("검토할 대상 파일을 업로드해주세요.")
        else:
            with st.spinner('분석 중입니다...'):
                content = read_file(uploaded_file)
                if content:
                    # 참고자료가 없으면 일반 모드
                    final_ref = ref_content if ref_content else "일반적인 비즈니스/법률 표준 및 상식"
                    
                    prompt = f"""
                    당신은 감사실 수석 전문가입니다.
                    [작업 모드: {option}]
                    [참고 자료(기준): {final_ref}]
                    [대상 파일 내용]
                    {content}
                    
                    위 내용을 바탕으로 작업을 수행하고, 가독성 좋은 보고서로 작성해줘.
                    """
                    try:
                        model = get_model()
                        response = model.generate_content(prompt)
                        st.success("완료!")
                        st.markdown(response.text)
                    except Exception as e:
                        st.error(f"오류: {e}")

# --- [Tab 2] 챗봇 기능 (New!) ---
with tab2:
    st.info("파일 내용에 대해 궁금한 점을 대화하듯 물어보세요.")
    
    # 채팅 기록 초기화
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 이전 대화 내용 표시
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 사용자 입력 처리
    if prompt := st.chat_input("질문을 입력하세요 (예: 이 계약서의 독소조항이 뭐야?)"):
        if not api_key_input:
            st.error("API 키가 필요합니다.")
        else:
            # 사용자 메시지 표시
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # AI 답변 생성
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""
                
                # 컨텍스트 구성 (참고자료 + 업로드된 파일이 있다면 포함)
                context = ""
                if ref_content: context += f"[참고자료]\n{ref_content}\n"
                # Tab1에서 올린 파일이 있다면 챗봇도 그걸 알게 함
                if uploaded_file: 
                    target_content = read_file(uploaded_file)
                    if target_content: context += f"[검토대상파일]\n{target_content}\n"
                
                final_prompt = f"{context}\n\n질문: {prompt}"
                
                try:
                    model = get_model()
                    response = model.generate_content(final_prompt)
                    full_response = response.text
                    message_placeholder.markdown(full_response)
                    
                    st.session_state.messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    st.error(f"오류: {e}")

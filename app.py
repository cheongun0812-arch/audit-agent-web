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
# 2. 사이드바 (API 키 설정)
# ==========================================
with st.sidebar:
    st.header("🔐 로그인")
    api_key_input = st.text_input("Google API Key 입력", type="password")
    
    if api_key_input:
        try:
            genai.configure(api_key=api_key_input)
            st.success("인증 완료 ✅")
        except:
            st.error("잘못된 키입니다.")
    else:
        st.warning("API 키를 입력해주세요.")

    st.markdown("---")
    st.markdown("**[모바일 사용 팁]**")
    st.markdown("1. 메일/카톡에서 파일 다운로드")
    st.markdown("2. 'Browse files' 버튼 터치")
    st.markdown("3. [내 파일] 또는 [다운로드] 폴더 선택")

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
            for page in reader.pages:
                content += page.extract_text() + "\n"
        elif uploaded_file.name.endswith('.docx'):
            doc = Document(uploaded_file)
            content = "\n".join([para.text for para in doc.paragraphs])
    except Exception as e:
        st.error(f"파일 읽기 오류: {e}")
        return None
    return content

# ==========================================
# 4. 메인 화면
# ==========================================

st.title("🛡️ AUDIT AI agent")
st.caption("언제 어디서나, 내 손안의 감사실")

# 1. 작업 모드 선택
option = st.selectbox(
    "작업을 선택하세요",
    (
        "1. ⚖️ 법률 리스크 정밀 검토",
        "2. 📝 감사 보고서 초안 작성", 
        "3. ✨ 오타 수정 및 문구 교정",
        "4. 📑 기안문/공문 초안 생성"
    )
)

st.divider()

# 2. 파일 업로드 (문구 개선)
st.markdown("##### 📂 검토할 파일 업로드")
st.info("👇 아래 버튼을 누르면 핸드폰의 [다운로드/내 파일]함이 열립니다.")

uploaded_file = st.file_uploader(
    label="여기를 눌러 파일을 선택하세요", # 버튼 문구
    type=['txt', 'pdf', 'docx'],
    label_visibility="collapsed" # 라벨 숨김 (깔끔하게)
)

# 3. 추가 참고 자료
with st.expander("➕ 추가 규정이나 지침 직접 입력하기 (선택)"):
    reference_text = st.text_area("내용을 붙여넣으세요", height=100)

# 4. 실행 버튼
if st.button("🚀 AI 검토 시작", use_container_width=True):
    if not api_key_input:
        st.error("⛔ 왼쪽 메뉴(>)를 열어 API 키를 먼저 입력해주세요.")
        st.stop()
    
    if not uploaded_file:
        st.warning("⚠️ 파일을 먼저 업로드해주세요.")
    else:
        with st.spinner('AI가 문서를 분석 중입니다... 잠시만 기다려주세요.'):
            content = read_file(uploaded_file)
            
            if content:
                prompt = f"""
                당신은 감사실 수석 전문가입니다.
                [작업 모드: {option}]
                [참고 자료: {reference_text if reference_text else '일반적인 비즈니스/법률 표준'}]
                [대상 파일 내용]
                {content}
                
                위 내용을 바탕으로 요청된 작업을 전문적으로 수행하고, 
                모바일에서 읽기 편하도록 가독성 좋은 보고서 형식으로 작성해줘.
                """
                
                try:
                    model = get_model()
                    response = model.generate_content(prompt)
                    
                    st.success("분석 완료!")
                    st.divider()
                    st.markdown(response.text)
                    
                except Exception as e:
                    st.error(f"오류 발생: {e}")

import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2

# --- 1. 설정 및 초기화 ---
st.set_page_config(page_title="감사실 AI 에이전트", page_icon="🤖")

with st.sidebar:
    st.header("🔐 로그인 설정")
    st.info("⚠️ 원활한 업무 처리를 위해\n반드시 '본인 계정의 API Key'를\n입력해야 합니다.")
    
    # API 키 입력받기 (비밀번호처럼 가려서 보임)
    api_key_input = st.text_input("Google API Key 입력", type="password")
    
    # 키가 입력되면 설정 적용
    if api_key_input:
        try:
            genai.configure(api_key=api_key_input)
            st.success("인증 성공! ✅")
        except:
            st.error("잘못된 키입니다.")
    else:
        st.warning("키가 입력되지 않았습니다.")

    st.markdown("---")
    st.markdown("**[사용 가이드]**")
    st.markdown("1. 본인 API 키 입력 (필수)")
    st.markdown("2. 작업 모드 선택")
    st.markdown("3. 파일 업로드")
    st.markdown("4. '검토 시작' 클릭")

# 모델 설정
def get_model():
    return genai.GenerativeModel('gemini-pro')

# 파일 읽기 함수
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

# --- 2. 메인 화면 ---
st.title("🤖 감사실 AI 에이전트 Web")
st.markdown("### PC와 모바일 어디서든 쉽고 빠르게!")

# 작업 모드 선택
option = st.selectbox(
    "어떤 작업을 진행하시겠습니까?",
    (
        "1. ⚖️ 법률 리스크 정밀 검토",
        "2. 📝 감사 보고서 초안 작성", 
        "3. ✨ 오타 수정 및 문구 교정",
        "4. 📑 기안문/공문 초안 생성"
    )
)

# 파일 업로드
uploaded_file = st.file_uploader("검토할 파일을 올려주세요", type=['txt', 'pdf', 'docx'])

# 추가 참고 자료
reference_text = st.text_area("추가로 참고할 규정이나 지침이 있다면 여기에 적어주세요 (선택사항)", height=100)

# 실행 버튼
if st.button("🚀 AI 검토 시작", use_container_width=True):
    # [수정됨] 키가 없으면 절대 실행 안 함
    if not api_key_input:
        st.error("⛔ [실행 불가] 왼쪽 사이드바에 본인의 API Key를 입력해주세요.")
        st.stop() # 프로그램 강제 중단
    
    if not uploaded_file:
        st.error("⚠️ 파일을 먼저 업로드해주세요!")
    else:
        with st.spinner('AI가 문서를 분석하고 보고서를 작성 중입니다...'):
            content = read_file(uploaded_file)
            
            if content:
                prompt = f"""
                당신은 감사실 수석 전문가입니다.
                [작업 모드: {option}]
                [참고 자료: {reference_text if reference_text else '일반적인 비즈니스/법률 표준'}]
                [대상 파일 내용]
                {content}
                
                위 내용을 바탕으로 요청된 작업을 전문적으로 수행하고, 
                가독성 좋은 보고서 형식으로 작성해줘.
                """
                
                try:
                    model = get_model()
                    response = model.generate_content(prompt)
                    
                    st.success("분석이 완료되었습니다!")
                    st.divider()
                    st.markdown(response.text)
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"오류 발생: {e}\n(API 키가 올바른지 확인해주세요)")
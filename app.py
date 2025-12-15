import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

# --- 1. 기본 설정 ---
st.set_page_config(page_title="감사실 AI 에이전트", page_icon="🛡️")

# --- 2. 구글 시트 연결 함수 (열쇠 사용) ---
@st.cache_resource
def init_connection():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Secrets에서 열쇠 꺼내기
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    return gspread.authorize(creds)

def save_data(emp_id, name, dept, answer):
    try:
        client = init_connection()
        sheet = client.open("Audit_Result_2026").sheet1 # 시트 이름 확인!
        
        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        
        sheet.append_row([now, emp_id, name, dept, answer, "완료"])
        return True
    except Exception as e:
        st.error(f"저장 오류: {e}")
        return False

# --- 3. 메인 화면 ---
def main():
    st.title("🛡️ 감사실 통합 지원 시스템")
    
    # 탭을 나눠서 기능 분리
    tab1, tab2 = st.tabs(["🤖 AI 감사 챗봇", "📝 1월 자율점검"])

    # [탭 1] 기존 챗봇 기능
    with tab1:
        st.header("무엇을 도와드릴까요?")
        # (여기에 기존에 쓰시던 챗봇 코드가 들어가면 됩니다.)
        # 지금은 예시로 간단히 넣겠습니다.
        user_input = st.text_input("질문을 입력하세요")
        if user_input:
            st.write("AI 응답: " + user_input + "에 대한 답변입니다.")

    # [탭 2] 새로운 자율점검 기능
    with tab2:
        st.header("📢 1월 부패방지 교육 및 서약")
        st.info("이달의 주제: 직무 관련 금품수수 금지")
        
        st.markdown("""
        **[교육 내용]**
        임직원은 직무와 관련하여 대가성 여부를 불문하고 
        금품 등을 받거나 요구해서는 안 됩니다.
        """)

        with st.form("audit_check"):
            c1, c2, c3 = st.columns(3)
            emp_id = c1.text_input("사번")
            name = c2.text_input("성명")
            dept = c3.text_input("부서")
            
            agree = st.checkbox("위 내용을 충분히 숙지하였으며 준수할 것을 서약합니다.")
            
            submit = st.form_submit_button("제출하기")
            
            if submit:
                if emp_id and name and agree:
                    if save_data(emp_id, name, dept, "서약함"):
                        st.success(f"{name}님, 제출 완료되었습니다. 감사합니다!")
                        st.balloons()
                else:
                    st.warning("사번, 성명을 입력하고 서약에 체크해주세요.")

if __name__ == "__main__":
    main()

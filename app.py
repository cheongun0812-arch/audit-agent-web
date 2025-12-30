# =====================================================
# AUDIT AI AGENT - FULL INTEGRATED STABLE VERSION
# =====================================================

import streamlit as st
import google.generativeai as genai
import pandas as pd
import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import plotly.express as px

# =====================================================
# 1. PAGE CONFIG (⚠️ 반드시 최상단)
# =====================================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered"
)

# =====================================================
# 2. SAFE CSS (Rimlet OK)
# =====================================================
st.markdown("""
<style>
.stApp { background-color: #F4F6F9; }

[data-testid="stSidebar"] { background-color: #2C3E50; }
[data-testid="stSidebar"] * { color: white !important; }

.stButton > button {
    background: linear-gradient(to right, #2980B9, #2C3E50);
    color: white;
    font-weight: bold;
    border: none;
}

.stTextInput input {
    background-color: white;
    color: black;
}
</style>
""", unsafe_allow_html=True)

# =====================================================
# 3. LOGIN
# =====================================================
def try_login():
    key = st.session_state.get("login_key", "").strip()
    if not key:
        st.session_state.login_error = "API 키를 입력하세요."
        return
    try:
        genai.configure(api_key=key)
        list(genai.list_models())
        st.session_state.api_key = key
        st.session_state.login_error = None
    except Exception as e:
        st.session_state.login_error = str(e)

# =====================================================
# 4. GOOGLE SHEET
# =====================================================
@st.cache_resource
def init_gsheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    return gspread.authorize(creds)

def save_result(emp_id, name, unit, dept, sheet_name):
    client = init_gsheet()
    ss = client.open("Audit_Result_2026")

    try:
        ws = ss.worksheet(sheet_name)
    except:
        ws = ss.add_worksheet(title=sheet_name, rows=2000, cols=10)
        ws.append_row(["저장시간", "사번", "성명", "본부", "부서", "결과"])

    if emp_id in ws.col_values(2):
        return False, "이미 참여하셨습니다."

    tz = pytz.timezone("Asia/Seoul")
    now = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([now, emp_id, name, unit, dept, "서약완료"])
    return True, "저장 완료"

# =====================================================
# 5. SIDEBAR
# =====================================================
with st.sidebar:
    st.markdown("## 🏛️ Control Center")
    st.divider()

    if "api_key" not in st.session_state:
        with st.form("login"):
            st.text_input("Gemini API Key", type="password", key="login_key")
            st.form_submit_button("Login", on_click=try_login)
        if st.session_state.get("login_error"):
            st.error(st.session_state.login_error)
    else:
        st.success("🟢 로그인됨")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    st.divider()
    st.caption("Audit AI Agent © 2026")

# =====================================================
# 6. HEADER
# =====================================================
st.markdown("<h1 style='text-align:center;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;'>Legal & Audit Assistant</p>", unsafe_allow_html=True)

# =====================================================
# 7. TABS
# =====================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "✅ 자율점검",
    "💬 AI 챗",
    "📰 요약",
    "📊 관리자 대시보드",
    "ℹ️ 시스템"
])

# =====================================================
# TAB 1 - AUDIT
# =====================================================
with tab1:
    st.subheader("설 명절 청탁금지법 자율점검")

    with st.form("audit"):
        c1, c2 = st.columns(2)
        emp_id = c1.text_input("사번")
        name = c2.text_input("성명")
        unit = st.selectbox("본부", [
            "경영총괄", "사업총괄", "강북본부", "강남본부",
            "서부본부", "강원본부", "품질지원단", "감사실"
        ])
        dept = st.text_input("부서명")
        agree = st.checkbox("청탁금지법을 준수하겠습니다.")

        if st.form_submit_button("제출"):
            if not (emp_id and name and agree):
                st.warning("모든 항목을 입력하세요.")
            else:
                ok, msg = save_result(
                    emp_id, name, unit, dept, "1월_설명절_캠페인"
                )
                if ok:
                    st.success("제출 완료")
                    st.balloons()
                else:
                    st.error(msg)

# =====================================================
# TAB 2 - CHAT
# =====================================================
with tab2:
    if "api_key" not in st.session_state:
        st.warning("로그인 필요")
    else:
        q = st.text_input("질문 입력")
        if q:
            model = genai.GenerativeModel("gemini-1.5-pro-latest")
            st.write(model.generate_content(q).text)

# =====================================================
# TAB 3 - SUMMARY
# =====================================================
with tab3:
    if "api_key" not in st.session_state:
        st.warning("로그인 필요")
    else:
        text = st.text_area("요약할 텍스트")
        if st.button("요약"):
            model = genai.GenerativeModel("gemini-1.5-pro-latest")
            st.write(
                model.generate_content(
                    f"다음 내용을 요약하고 인사이트를 제시해줘:\n{text}"
                ).text
            )

# =====================================================
# TAB 4 - ADMIN DASHBOARD
# =====================================================
with tab4:
    pw = st.text_input("관리자 비밀번호", type="password")

    if pw.strip() == "ktmos0402!":
        client = init_gsheet()
        ws = client.open("Audit_Result_2026").worksheet("1월_설명절_캠페인")
        df = pd.DataFrame(ws.get_all_records())

        if not df.empty:
            cnt = df["본부"].value_counts().reset_index()
            cnt.columns = ["본부", "참여인원"]

            fig = px.bar(cnt, x="본부", y="참여인원", text_auto=True)
            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(df)
            st.download_button(
                "엑셀 다운로드",
                df.to_csv(index=False).encode("utf-8-sig"),
                "audit_result.csv"
            )
        else:
            st.info("데이터 없음")

# =====================================================
# TAB 5
# =====================================================
with tab5:
    st.info("시스템 정상 동작 중")

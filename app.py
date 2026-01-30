import streamlit as st
import os
import google.generativeai as genai
from docx import Document
import PyPDF2
from youtube_transcript_api import YouTubeTranscriptApi
import requests
from bs4 import BeautifulSoup
import time
import glob
import tempfile
import hashlib
import base64
import datetime
import pytz
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# ==========================================
# 1. 전역 설정 및 상수
# ==========================================
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
    "doubleClick": "reset",
}

# 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 프리미엄 디자인 테마 (CSS)
# ==========================================
st.markdown("""
<style>
    @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
    html { font-size: 16.2px; }
    * { font-family: 'Pretendard', sans-serif; letter-spacing: -0.02em; }
    .stApp { background-color: #020617; }
    
    /* 탭 디자인 최적화 */
    .stTabs [data-baseweb="tab-list"] { gap: 12px; background-color: #0f172a; padding: 10px; border-radius: 15px; }
    .stTabs [data-baseweb="tab"] { 
        height: 50px; font-weight: 800; color: #94a3b8; border-radius: 10px; padding: 0 20px;
    }
    .stTabs [data-baseweb="tab--active"] { background-color: #1e293b; color: #ffffff; border-bottom: 3px solid #E11D48; }

    /* 자율점검 탭 내부 폭 강제 확장 */
    [data-testid="stHorizontalBlock"] { width: 100% !important; max-width: 100% !important; }
    .stTabs [data-baseweb="tab-panel"] { padding: 0 !important; }
    
    /* iframe 시인성 강화 */
    iframe { border: none !important; border-radius: 25px; width: 100%; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 3. 핵심 기능 함수 (구글시트 및 유틸리티)
# ==========================================
@st.cache_resource
def init_google_sheet_connection():
    if gspread is None: return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except: return None

def _korea_now():
    return datetime.datetime.now(pytz.timezone("Asia/Seoul"))

def validate_emp_id(emp_id):
    s = (emp_id or "").strip()
    if s == "00000000": return True, ""
    if len(s) == 8 and s.isdigit() and s.startswith("10"): return True, ""
    return False, "사번 8자리를 정확히 입력하세요. (10******)"

def save_audit_result(emp_id, name, unit, answer, sheet_name):
    client = init_google_sheet_connection()
    if not client: return False, "구글 시트 연결 실패"
    try:
        spreadsheet = client.open("Audit_Result_2026")
        sheet = spreadsheet.worksheet(sheet_name)
        # 중복 체크 (사번 기준)
        all_ids = sheet.col_values(2)
        if str(emp_id).strip() in all_ids and str(emp_id).strip() != "00000000":
            return False, f"이미 참여한 사번입니다."
        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, "현소속", answer, "완료"])
        return True, "성공"
    except Exception as e: return False, str(e)

# ==========================================
# 4. 메인 화면 및 탭 구성
# ==========================================
tab_audit, tab_legal, tab_chat, tab_summary, tab_admin = st.tabs([
    "✅ 자율점검", "📄 법률 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자 모드"
])

# --- [Tab 1: 자율점검 (이미지 1~5번 테마 통합)] ---
with tab_audit:
    # 동영상 배경 파일 인코딩
    v_src = ""
    v_path = "2026년 New year.mp4"
    if os.path.exists(v_path):
        with open(v_path, "rb") as f:
            v_src = f"data:video/mp4;base64,{base64.b64encode(f.read()).decode()}"
    else:
        v_src = "https://assets.mixkit.co/videos/preview/mixkit-abstract-red-and-white-flow-2336-large.mp4"

    # inpor.html 로드 및 5가지 테마 구현
    inpor_path = "inpor.html"
    if os.path.exists(inpor_path):
        with open(inpor_path, "r", encoding="utf-8") as f:
            inpor_content = f.read()
        
        # 배경 영상 교체
        inpor_content = inpor_content.replace(
            "https://assets.mixkit.co/videos/preview/mixkit-abstract-red-and-white-flow-2336-large.mp4", 
            v_src
        )
        
        # 이미지의 모든 테마(Hero, AI스캔, 아젠다, 채널, 서약) 표시
        st.components.v1.html(inpor_content, height=4300, scrolling=False)
    else:
        st.error("⚠️ 'inpor.html' 파일을 찾을 수 없습니다.")

    # 실시간 데이터 연동 서약 폼 (이미지 5번 테마 하단)
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_pledge, _ = st.columns([1, 1.5, 1])
    with col_pledge:
        with st.form("audit_pledge_form_final"):
            st.markdown("### 🖋️ 2026 설맞이 청렴 서약서")
            e_id = st.text_input("사번 (8자리)", placeholder="10******")
            e_name = st.text_input("성명")
            unit = st.selectbox("소속", ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"])
            
            if st.form_submit_button("🛡️ 서약 완료 및 이벤트 응모"):
                if e_id and e_name:
                    ok, msg = validate_emp_id(e_id)
                    if ok:
                        success, s_msg = save_audit_result(e_id, e_name, unit, "2026 설맞이 서약 완료", "2026_02_자율점검")
                        if success: st.success("🎊 서약이 완료되었습니다! 50% 참여 달성 시 추첨 이벤트에 포함됩니다.")
                        else: st.error(s_msg)
                    else: st.warning(msg)
                else: st.warning("필수 정보를 입력해 주세요.")

# --- [Tab 2: 법률 검토 (원래 위치로 이동)] ---
with tab_legal:
    st.markdown("### 📄 법률 리스크(계약서)·규정 검토 / 감사보고서 작성·검증")
    if "api_key" not in st.session_state:
        st.warning("🔒 해당 메뉴는 로그인 후 이용 가능합니다.")
        # 로그인 폼 생략 (기존 사이드바 로직 활용)
    else:
        l_tab1, l_tab2 = st.tabs(["⚖️ 법률/규정 분석", "🔍 보고서 검증"])
        with l_tab1:
            st.file_uploader("검토 대상 파일 업로드", type=["pdf", "docx", "txt"], key="legal_upload")
            st.button("🚀 리스크 분석 실행", use_container_width=True)
        with l_tab2:
            st.text_area("검증할 보고서 내용", height=300, key="audit_verify")
            st.button("✅ 검증 시작", use_container_width=True)

# --- [Tab 3: AI 에이전트] ---
with tab_chat:
    st.markdown("### 💬 AI 법률/챗봇")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = []

        with st.form(key="chat_input_form", clear_on_submit=True):
            user_input = st.text_input("질문 입력")
            send_btn = st.form_submit_button("전송 📤", use_container_width=True)

        if send_btn and user_input:
            st.session_state.messages.append({"role": "user", "content": user_input})
            with st.spinner("답변 생성 중..."):
                try:
                    res = get_model().generate_content(user_input)
                    st.session_state.messages.append({"role": "assistant", "content": res.text})
                except Exception as e:
                    st.error(f"오류: {e}")

        for msg in reversed(st.session_state.messages):
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

# --- [Tab 4: 스마트 요약] ---
with tab_summary:
    st.markdown("### 📰 스마트 요약")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        st_type = st.radio("입력 방식", ["URL (유튜브/웹)", "미디어 파일", "텍스트"])
        final_input = None
        is_multimodal = False

        if "URL" in st_type:
            url = st.text_input("URL 입력")
            if url and "youtu" in url:
                with st.spinner("자막 추출 중..."):
                    final_input = get_youtube_transcript(url)
                    if not final_input:
                        final_input = download_and_upload_youtube_audio(url)
                        is_multimodal = True
            elif url:
                with st.spinner("웹페이지 분석 중..."):
                    final_input = get_web_content(url)

        elif "미디어" in st_type:
            mf = st.file_uploader("파일 업로드", type=["mp3", "wav", "mp4"])
            if mf:
                final_input = process_media_file(mf)
                is_multimodal = True
        else:
            final_input = st.text_area("텍스트 입력", height=200)

        if st.button("⚡ 요약 실행", use_container_width=True):
            if final_input:
                with st.spinner("요약 중..."):
                    try:
                        p = "다음 내용을 핵심 요약, 상세 내용, 인사이트로 정리해줘."
                        if is_multimodal:
                            res = get_model().generate_content([p, final_input])
                        else:
                            res = get_model().generate_content(f"{p}\n\n{str(final_input)[:30000]}")
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"오류: {e}")

# --- [Tab 5: 관리자 대시보드 최종 버전] ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    st.caption("실시간 참여율 분석 및 제출 데이터 통합 관리")

    # 1. 관리자 비밀번호 검증
    admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_dash_pw")
    if admin_pw.strip() != "ktmos0402!":
        st.info("관리자 비밀번호를 입력하세요.")
        st.stop()

    st.success("✅ 접속 성공")

    # 2. 데이터 로드 (구글 시트 연결)
    client = init_google_sheet_connection()
    if not client:
        st.error("❌ 구글 시트 연결 실패. API 권한 및 Secrets 설정을 확인하세요.")
        st.stop()

    try:
        spreadsheet = client.open("Audit_Result_2026")
        ws_list = spreadsheet.worksheets()
        sheet_names = [ws.title for ws in ws_list if ws.title != "Campaign_Config"]
        
        selected_sheet = st.selectbox("📊 분석 대상 시트 선택", sheet_names, key="admin_sheet_select")
        ws = spreadsheet.worksheet(selected_sheet)
        values = ws.get_all_values()
        
        if not values or len(values) < 2:
            st.warning("선택한 시트에 데이터가 없습니다.")
            st.stop()
            
        df = pd.DataFrame(values[1:], columns=values[0])
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        st.stop()

    # 3. 실시간 참여율 대시보드 (이미지 정원 데이터 반영)
    st.markdown("---")
    st.markdown("#### 📈 실시간 참여 현황 분석")

    # 조직별 정원 설정 (제공된 이미지 데이터 기반)
    total_staff_map = {
        "감사실": 3,
        "경영총괄": 27,
        "사업총괄": 39,
        "강북본부": 221,
        "강남본부": 173,
        "서부본부": 278,
        "강원본부": 101,
        "품질지원단": 137
    }

    # 현재 제출 현황 집계
    unit_counts = df['총괄/본부/단'].value_counts().to_dict()
    
    stats_data = []
    for unit, total in total_staff_map.items():
        current = unit_counts.get(unit, 0)
        ratio = (current / total) * 100 if total > 0 else 0
        stats_data.append({
            "조직": unit,
            "정원": total,
            "참여인원": current,
            "참여율(%)": round(ratio, 1)
        })
    
    stats_df = pd.DataFrame(stats_data)

    # 상단 요약 지표
    total_target = sum(total_staff_map.values()) # 총 979명
    total_current = len(df)
    total_ratio = (total_current / total_target) * 100

    m1, m2, m3 = st.columns(3)
    m1.metric("전체 대상자", f"{total_target}명")
    m2.metric("현재 참여자", f"{total_current}명")
    m3.metric("전체 참여율", f"{total_ratio:.1f}%")

    # 시각화 차트
    c1, c2 = st.columns(2)
    
    with c1:
        fig1 = px.bar(stats_df, x="조직", y="참여인원", text="참여인원",
                      title="조직별 참여 인원", color="참여인원", color_continuous_scale="Blues")
        st.plotly_chart(fig1, use_container_width=True, config=PLOTLY_CONFIG)
        
    with c2:
        fig2 = px.bar(stats_df, x="조직", y="참여율(%)", text="참여율(%)",
                      title="조직별 참여율(%)", color="참여율(%)", color_continuous_scale="Viridis")
        fig2.add_hline(y=100, line_dash="dash", line_color="red")
        st.plotly_chart(fig2, use_container_width=True, config=PLOTLY_CONFIG)

    # 4. 제출 데이터 상세 조회
    with st.expander("📄 제출 데이터 상세 보기 / 검색", expanded=False):
        # 간단한 검색 기능 추가
        search_term = st.text_input("🔍 성명 또는 부서 검색", "")
        if search_term:
            display_df = df[df.apply(lambda row: row.astype(str).str.contains(search_term).any(), axis=1)]
        else:
            display_df = df
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    # 5. 데이터 다운로드
    st.markdown("---")
    st.markdown("#### ⬇️ 데이터 내보내기")
    d1, d2 = st.columns(2)
    
    with d1:
        csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
        st.download_button("📥 CSV 다운로드", csv_bytes, f"{selected_sheet}.csv", "text/csv", use_container_width=True)
        
    with d2:
        try:
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='참여현황')
            st.download_button("📥 Excel 다운로드", output.getvalue(), f"{selected_sheet}.xlsx", use_container_width=True)
        except Exception:
            st.info("Excel 엔진 미설치로 CSV 이용을 권장합니다.")

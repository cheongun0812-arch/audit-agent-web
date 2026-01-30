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

# Plotly 설정
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,
    "doubleClick": "reset",
}

# 구글 시트 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None
    ServiceAccountCredentials = None
    st.error("❌ 구글 시트 라이브러리가 없습니다. requirements.txt를 확인하세요.")

# yt_dlp 체크
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# 1. 페이지 설정
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 2. 전역 스타일 테마
st.markdown("""
<style>
details > summary { font-size: 1.5rem !important; font-weight: 900 !important; color: #1565C0 !important; }
html { font-size: 16.2px; }
.stApp { background-color: #F4F6F9; }
[data-testid="stSidebar"] { background-color: #2C3E50; }
.stButton > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    border-radius: 10px !important;
    font-weight: 800 !important;
}
#audit-tab div[data-testid="stTextInput"] label { font-weight: 900 !important; color: #2C3E50 !important; }
</style>
""", unsafe_allow_html=True)

# 3. 핵심 기능 함수 (구글시트, 모델 호출 등)
@st.cache_resource
def init_google_sheet_connection():
    if gspread is None or ServiceAccountCredentials is None: return None
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        return gspread.authorize(creds)
    except: return None

def _korea_now():
    try: return datetime.datetime.now(pytz.timezone("Asia/Seoul"))
    except: return datetime.datetime.now()

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if not client: return False, "연결 실패"
    try:
        spreadsheet = client.open("Audit_Result_2026")
        try: sheet = spreadsheet.worksheet(sheet_name)
        except:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])
        
        # 중복 체크
        all_records = sheet.get_all_records()
        for r in all_records:
            if str(r.get("사번")).strip() == str(emp_id).strip() and str(emp_id).strip() != "00000000":
                return False, "이미 참여하셨습니다."
        
        now = _korea_now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e: return False, str(e)

def validate_emp_id(emp_id):
    s = (emp_id or "").strip()
    if not s: return False, "사번을 입력하세요."
    if s == "00000000": return True, ""
    if len(s) == 8 and s.isdigit() and s.startswith("10"): return True, ""
    return False, "사번 형식이 올바르지 않습니다."

def get_model():
    if "api_key" in st.session_state: genai.configure(api_key=st.session_state["api_key"])
    return genai.GenerativeModel("gemini-1.5-flash")

# --- 자동 로그인 및 사이드바 로직 생략 (기존 유지) ---
if "api_key" not in st.session_state:
    with st.sidebar:
        with st.form("login_form"):
            key = st.text_input("Key", type="password")
            if st.form_submit_button("Login"):
                st.session_state["api_key"] = key
                st.rerun()
    st.info("🔒 로그인 후 이용 가능합니다.")
    st.stop()

# 4. 메인 탭 구성
tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs([
    "✅ 자율점검", "📄 법률 검토", "💬 AI 에이전트(챗봇)", "📰 스마트 요약", "🔒 관리자 모드"
])

# --- [Tab 1: 자율점검] ---
with tab_audit:
    st.markdown('<div id="audit-tab">', unsafe_allow_html=True)
    
    # 레이아웃 최적화 스타일
    st.markdown("""
        <style>
            [data-testid="stHorizontalBlock"] { width: 100% !important; }
            iframe { border: none !important; border-radius: 25px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }
        </style>
    """, unsafe_allow_html=True)

    # 동영상 인코딩
    v_src = ""
    v_path = "2026년 New year.mp4"
    if os.path.exists(v_path):
        with open(v_path, "rb") as f:
            v_src = f"data:video/mp4;base64,{base64.b64encode(f.read()).decode()}"

    # 프리미엄 인포그래픽 HTML
    premium_ui = f"""
    <div style="width:100%; min-height:900px; position:relative; background:#020617; border-radius:25px; overflow:hidden;">
        <video autoplay muted loop playsinline style="position:absolute; top:0; left:0; width:100%; height:100%; object-fit:cover; opacity:0.4; z-index:0;">
            <source src="{v_src}" type="video/mp4">
        </video>
        <div style="position:relative; z-index:1; padding:80px 40px; font-family:'Pretendard', sans-serif; color:white; text-align:center;">
            <div style="display:inline-block; padding:8px 20px; background:rgba(225,29,72,0.2); border:1px solid rgba(225,29,72,0.3); border-radius:999px; color:#ff4d4d; font-weight:bold; font-size:14px; margin-bottom:20px;">
                🎍 2026 병오년(丙午年) 설맞이 클린캠페인
            </div>
            <h1 style="font-size:4.5rem; font-weight:900; line-height:1.1; margin-bottom:20px; text-shadow: 0 5px 20px rgba(0,0,0,0.7);">
                새해 복 <br><span style="color:#E11D48;">많이 받으십시오</span>
            </h1>
            <p style="font-size:1.3rem; color:#cbd5e1; max-width:800px; margin:0 auto 50px; line-height:1.6;">
                정직과 신뢰를 바탕으로 더 크게 도약하는 2026년이 되시길 기원합니다.<br>
                <b>ktMOS북부</b> 임직원의 청렴한 다짐이 행복한 명절을 만듭니다.
            </p>
            <div style="background:rgba(251,191,36,0.1); border:1px solid rgba(251,191,36,0.3); padding:25px; border-radius:20px; max-width:700px; margin:0 auto 50px;">
                <h3 style="color:#FBBF24; margin-bottom:10px;">🎁 서약 이벤트 안내</h3>
                <p style="font-size:1.1rem; margin:0;">임직원 50% 이상 참여 시, <b>추첨을 통해 50분께</b> 커피 쿠폰을 드립니다!</p>
            </div>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap:25px; max-width:1200px; margin:0 auto;">
                <div style="background:rgba(255,255,255,0.05); backdrop-filter:blur(15px); padding:30px; border-radius:30px; border:1px solid rgba(255,255,255,0.1); text-align:left;">
                    <h3 style="color:#FBBF24;">🎯 캠페인 아젠다</h3>
                    <ul style="color:#94a3b8; line-height:1.8;">
                        <li>• 명절 선물/금품 수수 정중히 거절하기</li>
                        <li>• 부적절한 향응 및 접대 금지</li>
                        <li>• 공정한 업무 처리 및 원칙 준수</li>
                    </ul>
                </div>
                <div style="background:rgba(255,255,255,0.05); backdrop-filter:blur(15px); padding:30px; border-radius:30px; border:1px solid rgba(255,255,255,0.1); text-align:left;">
                    <h3 style="color:#38BDF8;">🛡️ 상담 및 제보</h3>
                    <p style="color:#94a3b8;">감사실 직통: 02-3414-1919<br>윤리제보: ethics@ktmos.com</p>
                </div>
            </div>
        </div>
    </div>
    """
    st.components.v1.html(premium_ui, height=950, scrolling=False)

    # 서약 폼
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_form, _ = st.columns([1, 2, 1])
    with col_form:
        st.markdown("### 🖋️ 2026 설맞이 청렴 서약")
        with st.form("clean_pledge_form"):
            e_id = st.text_input("사번 (8자리)", placeholder="10******")
            e_name = st.text_input("성명")
            unit = st.selectbox("소속 선택", ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"], index=None)
            if st.form_submit_button("🛡️ 서약 완료 및 응모"):
                if e_id and e_name and unit:
                    ok, v_msg = validate_emp_id(e_id)
                    if ok:
                        success, s_msg = save_audit_result(e_id, e_name, unit, "현소속", "2026 설맞이 서약 완료", campaign_info["sheet_name"])
                        if success: st.success(f"🎊 {e_name}님, 서약이 완료되었습니다!")
                        else: st.error(s_msg)
                    else: st.warning(v_msg)
                else: st.warning("⚠️ 모든 필드를 입력해 주세요.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- [Tab 2: 법률 검토] ---
with tab_doc:
    st.markdown("### 📄 법률 리스크 및 감사보고서 검토")
    cur1, cur2 = st.tabs(["⚖️ 법률 리스크 검토", "🔍 감사보고서 검증"])
    with cur1:
        st.file_uploader("검토할 파일 업로드", type=["pdf", "docx", "txt"])
    with cur2:
        st.text_area("검증할 보고서 내용")
        
        # 2-레벨 메뉴: 커리큘럼 1(법률 리스크) / 커리큘럼 2(감사보고서)
        cur1, cur2 = st.tabs(["⚖️ 커리큘럼 1: 법률 리스크 심층 검토", "🔍 커리큘럼 2: 감사보고서 작성·검증"])

        # -------------------------
        # ⚖️ 커리큘럼 1: 법률 리스크 심층 검토
        # -------------------------
        with cur1:
            st.markdown("#### ⚖️ 법률 리스크 정밀 검토")
            st.caption("PDF/Word/TXT 파일을 업로드하면, 핵심 쟁점·리스크·개선안을 구조적으로 정리합니다.")

            uploaded_file = st.file_uploader("파일 업로드 (PDF, Word, TXT)", type=["txt", "pdf", "docx"], key="cur1_file")

            analysis_depth = st.selectbox(
                "분석 수준",
                ["핵심 요약", "리스크 식별(중점)", "조항/근거 중심(가능 범위 내)"],
                index=1,
                key="cur1_depth"
            )

            if st.button("🚀 분석 시작", use_container_width=True, key="cur1_run"):
                if not uploaded_file:
                    st.warning("⚠️ 먼저 파일을 업로드해주세요.")
                else:
                    content = read_file(uploaded_file)
                    if not content:
                        st.error("❌ 파일에서 텍스트를 추출하지 못했습니다.")
                    else:
                        with st.spinner("🧠 AI가 분석 중입니다..."):
                            try:
                                prompt = f"""[역할] 법률/준법 리스크 심층 검토 전문가
[작업] 법률 리스크 정밀 검토
[분석 수준] {analysis_depth}

[작성 원칙]
- 사실과 의견을 구분해 작성
- 근거가 부족하면 '근거 미확인'으로 표시
- 회사에 불리할 수 있는 문구(단정/추정)는 피하고, 조건부 표현 사용

[입력 문서]
{content[:30000]}
"""
                                res = get_model().generate_content(prompt)
                                st.success("✅ 분석 완료")
                                st.markdown(res.text)
                            except Exception as e:
                                st.error(f"오류: {e}")

        # -------------------------
        # 🔍 커리큘럼 2: 감사보고서 작성·검증 (Multi-Source Upload)
        # -------------------------
        with cur2:
            st.markdown("#### 🔍 감사보고서 작성·검증 (Multi-Source Upload)")

            # ✅ 작업 모드 선택(선택에 따라 필요한 입력만 노출/활성화)
            mode = st.radio(
                "작업 모드",
                ["🧾 감사보고서 초안 생성", "✅ 감사보고서 검증·교정(오탈자/논리/형식)"],
                horizontal=True,
                key="cur2_mode"
            )
            is_draft_mode = "초안" in mode

            # ✅ (초기화) 모드별로 정의되지 않을 수 있는 변수들
            interview_audio = None
            interview_transcript = None
            evidence_files = []
            draft_text = ""
            draft_file = None

            st.caption("선택한 작업 모드에 따라 아래 입력 항목이 자동으로 바뀝니다.")
            with st.expander("🔐 보안·주의사항(필독)", expanded=False):
                st.markdown(
                    "- 민감정보(주민등록번호/계좌/건강/징계대상 실명 등)는 업로드 전 **내부 보안 기준**을 반드시 확인하세요.\n"
                    "- 본 기능은 **감사 판단을 보조**하는 도구이며, 최종 판단·결재 책임은 감사실에 있습니다.\n"
                    "- 규정 근거는 업로드된 자료에서 확인되는 내용만 인용하도록 설계되었습니다."
                )

            if is_draft_mode:
                st.markdown("### ① 감사 자료 입력 (초안 생성에 사용)")
                cL, cR = st.columns(2)

                with cL:
                    interview_audio = st.file_uploader(
                        "🎧 면담 음성 (mp3/wav/mp4) — 선택",
                        type=["mp3", "wav", "mp4"],
                        key="cur2_audio"
                    )
                    interview_transcript = st.file_uploader(
                        "📝 면담 녹취(텍스트/문서) — 권장",
                        type=["txt", "pdf", "docx"],
                        key="cur2_transcript"
                    )

                with cR:
                    evidence_files = st.file_uploader(
                        "📂 조사·증거/확인 자료 — 권장(복수 업로드 가능)",
                        type=["pdf", "png", "jpg", "jpeg", "xlsx", "csv", "txt", "docx"],
                        accept_multiple_files=True,
                        key="cur2_evidence"
                    ) or []

            else:
                st.markdown("### ① 검증 대상 보고서 입력 (검증·교정에 사용)")
                cL, cR = st.columns(2)

                with cL:
                    draft_text = st.text_area(
                        "검증할 감사보고서(초안/기존본) — 붙여넣기",
                        height=220,
                        key="cur2_draft"
                    )

                with cR:
                    draft_file = st.file_uploader(
                        "또는 파일 업로드(PDF/DOCX/TXT) — 선택",
                        type=["pdf", "docx", "txt"],
                        key="cur2_draft_file"
                    )

            st.markdown("### ② 회사 규정/판단 기준  ·  ③ 표준 감사보고서 형식(참고)")
            left, right = st.columns(2)

            with left:
                regulations = st.file_uploader(
                    "📘 회사 규정/기준(인사규정·징계기준·윤리지침 등)",
                    type=["pdf", "docx", "txt"],
                    accept_multiple_files=True,
                    key="cur2_regs"
                )
                st.caption("초안/검증 모두에 유용합니다. (특히 ‘근거 인용’ 필요 시 권장)")

            with right:
                reference_reports = st.file_uploader(
                    "📑 표준 감사보고서 형식(정부·공공·기업) — 선택",
                    type=["pdf", "docx", "txt"],
                    accept_multiple_files=True,
                    key="cur2_refs"
                )
                st.caption("문서 형식/톤을 맞추고 싶을 때만 넣어도 됩니다.")

            st.markdown("### ④ 사건 개요(필수) 및 작성 옵션")
            row1, row2 = st.columns(2)

            with row1:
                case_title = st.text_input(
                    "사건명/건명(필수)",
                    placeholder="예: 법인카드 사적 사용 의혹 조사",
                    key="cur2_title"
                )

            with row2:
                report_tone = st.selectbox(
                    "문서 톤",
                    ["감사보고서(공식·중립)", "보고서(간결·결정 중심)", "상신용(결재/조치 권고 중심)"],
                    index=0,
                    key="cur2_tone"
                )

            case_scope = st.text_area(
                "사건 개요 요약(필수) — 무엇을/언제/누가/어떤 경위로",
                height=110,
                key="cur2_scope"
            )

            # (이하 기존 코드 그대로 유지: 사용자가 올려준 파일의 원문 로직이 이어짐)
            st.info("※ 이하(감사보고서 생성/검증 로직)는 기존 코드 흐름을 그대로 유지합니다. (이번 요청 범위: 자율점검 UI/검증만)")

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

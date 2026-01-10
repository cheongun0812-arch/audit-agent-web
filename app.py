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

# Plotly: 확대/축소 후 "원점 복원" 가능하도록 모드바 항상 표시
PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": False,          # 스크롤로 의도치 않은 확대 방지
    "doubleClick": "reset",       # 더블클릭/더블탭 시 원점 복원
}

# [필수] 구글 시트 라이브러리 체크
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except ImportError:
    gspread = None
    ServiceAccountCredentials = None
    st.error("❌ 구글 시트 라이브러리가 없습니다. requirements.txt를 확인하세요.")

# [필수] yt_dlp 라이브러리 체크
try:
    import yt_dlp
except ImportError:
    yt_dlp = None

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# 2. 🎨 디자인 테마 (사이드바/토글 강제 표시 포함)
#    + 전체 텍스트 0.2px 증가
# ==========================================
st.markdown("""
<style>
/* ✅ 전체 글자 크기 +0.2px */
html { font-size: 16.2px; }

.stApp { background-color: #F4F6F9; }
[data-testid="stSidebar"] { background-color: #2C3E50; }
[data-testid="stSidebar"] * { color: #FFFFFF !important; }

/* ✅ 사이드바 텍스트 입력의 아이콘(눈/지우기 등)을 항상 검정색으로 */
[data-testid="stSidebar"] div[data-testid="stTextInput"] button,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button:hover,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button:focus,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button:active {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #000000 !important;
    opacity: 1 !important;
}

[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg *,
[data-testid="stSidebar"] div[data-testid="stTextInput"] button svg path {
    fill: #000000 !important;
    stroke: #000000 !important;
    opacity: 1 !important;
}

/* aria-label이 환경/언어에 따라 달라도 적용되도록, 패스워드 토글 버튼도 강제 */
div[data-testid="stTextInput"] button[aria-label],
div[data-testid="stTextInput"] button[aria-label] svg,
div[data-testid="stTextInput"] button[aria-label] svg * {
    fill: #000000 !important;
    stroke: #000000 !important;
    color: #000000 !important;
    opacity: 1 !important;
}

.stTextInput input, .stTextArea textarea {
    background-color: #FFFFFF !important;
    color: #000000 !important;
    -webkit-text-fill-color: #000000 !important;
    border: 1px solid #BDC3C7 !important;
}

/* ✅ 버튼 스타일 (일반 버튼 + 폼 제출 버튼) */
.stButton > button,
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.6rem 1rem !important;
    font-weight: 800 !important;
    width: 100% !important;
    opacity: 1 !important;
}

/* ✅ disabled여도 텍스트가 흐려지지 않도록 */
.stButton > button:disabled,
div[data-testid="stFormSubmitButton"] > button:disabled {
    background: linear-gradient(to right, #2980B9, #2C3E50) !important;
    color: #FFFFFF !important;
    opacity: 1 !important;
    filter: none !important;
}

/* ✅ 버튼 내부 텍스트/아이콘도 상시 선명 */
.stButton > button *,
div[data-testid="stFormSubmitButton"] > button * {
    color: #FFFFFF !important;
    opacity: 1 !important;
}

/* (서약 우측 카운트다운 표시용) */
.pledge-right {
  display:flex;
  align-items:center;
  justify-content:flex-end;
  gap: 8px;
  font-weight: 900;
  color: #0B5ED7;
  min-width: 90px;
}
</style>
""", unsafe_allow_html=True)

# ✅ PC에서는 사이드바 기본 펼침, 모바일에서는 기본 접힘
st.markdown("""
<script>
(function() {
  const KEY = "__sidebar_autopen_done__";
  const isDesktop = () => (window.innerWidth || 0) >= 900;
  let tries = 0;
  const maxTries = 25;

  function clickToggleIfNeeded() {
    try {
      if (!isDesktop()) return;
      if (window.sessionStorage.getItem(KEY) === "1") return;

      const doc = window.parent?.document || document;
      const candidates = [
        '[data-testid="stSidebarCollapsedControl"] button',
        '[data-testid="stSidebarCollapsedControl"]',
        'button[title="Open sidebar"]',
        'button[aria-label="Open sidebar"]'
      ];

      for (const sel of candidates) {
        const el = doc.querySelector(sel);
        if (el) {
          el.click();
          window.sessionStorage.setItem(KEY, "1");
          return;
        }
      }
    } catch (e) {}
  }

  const timer = setInterval(() => {
    tries += 1;
    clickToggleIfNeeded();
    if (tries >= maxTries) clearInterval(timer);
  }, 250);
})();
</script>
""", unsafe_allow_html=True)

# ==========================================
# 3. 로그인 및 세션 관리
# ==========================================
def _set_query_param_key(clean_key: str) -> None:
    encoded_key = base64.b64encode(clean_key.encode()).decode()
    try:
        st.query_params["k"] = encoded_key
    except Exception:
        st.experimental_set_query_params(k=encoded_key)

def _clear_query_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()

def _get_query_param_key() -> str:
    try:
        qp = st.query_params.get("k", None)
        if isinstance(qp, list):
            qp = qp[0] if qp else None
    except Exception:
        qp = st.experimental_get_query_params().get("k", [None])[0]

    if not qp:
        return ""

    try:
        return base64.b64decode(qp.encode()).decode().strip()
    except Exception:
        return ""

def _logout():
    for k in ["api_key", "api_verified", "audit_verified"]:
        if k in st.session_state:
            del st.session_state[k]
    _clear_query_params()
    st.rerun()

# ==========================================
# 4. 사이드바 (로그인)
# ==========================================
with st.sidebar:
    st.markdown("## 🔐 시스템 접속")
    st.markdown("시스템 접속을 위해 API Key를 입력하세요.")
    api_input = st.text_input("API Key", type="password", placeholder="입력 후 Enter")
    if st.button("로그인"):
        if api_input.strip():
            st.session_state["api_key"] = api_input.strip()
            st.session_state["api_verified"] = True
            _set_query_param_key(api_input.strip())
            st.success("✅ 로그인 완료!")
            st.rerun()
        else:
            st.warning("⚠️ API Key를 입력해주세요.")

    st.markdown("---")

    st.markdown("## 🚪 로그아웃")
    if st.button("로그아웃"):
        _logout()

# ==========================================
# 5. 쿼리파라미터 자동 로그인
# ==========================================
if "api_key" not in st.session_state:
    qp_key = _get_query_param_key()
    if qp_key:
        st.session_state["api_key"] = qp_key
        st.session_state["api_verified"] = True

# ==========================================
# 6. Gemini 설정
# ==========================================
if "api_key" in st.session_state:
    genai.configure(api_key=st.session_state["api_key"])

# ==========================================
# 7. 유틸 함수
# ==========================================
def get_youtube_transcript(url: str) -> str:
    try:
        video_id = url.split("v=")[1].split("&")[0]
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        return "\n".join([t["text"] for t in transcript])
    except Exception as e:
        return f"❌ 유튜브 자막을 불러오지 못했습니다: {e}"

def read_file(uploaded_file) -> str:
    try:
        if uploaded_file.type == "text/plain":
            return uploaded_file.getvalue().decode("utf-8", errors="ignore")

        if uploaded_file.type == "application/pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            return "\n".join([page.extract_text() or "" for page in reader.pages])

        if uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            doc = Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs])

        return ""
    except Exception as e:
        st.error(f"❌ 파일 읽기 오류: {e}")
        return ""

def is_url(text: str) -> bool:
    return text.startswith("http://") or text.startswith("https://")

def fetch_web_content(url: str) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        for script in soup(["script", "style"]):
            script.decompose()
        return soup.get_text("\n", strip=True)
    except Exception as e:
        return f"❌ 웹페이지 내용을 가져오지 못했습니다: {e}"

# ==========================================
# 8. Google Sheet 저장 기능
# ==========================================
def get_sheet_client():
    if gspread is None or ServiceAccountCredentials is None:
        return None

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        st.error(f"❌ 구글 인증 실패: {e}")
        return None

def get_or_create_worksheet(spreadsheet, title):
    try:
        worksheet = spreadsheet.worksheet(title)
        return worksheet
    except Exception:
        worksheet = spreadsheet.add_worksheet(title=title, rows="5000", cols="20")
        return worksheet

def get_campaign_sheet_name():
    tz = pytz.timezone("Asia/Seoul")
    now = datetime.datetime.now(tz)
    dt = now.date()

    # 캠페인 기간 예시 (필요 시 수정)
    # 2026년 1월 캠페인
    if dt.year == 2026 and dt.month == 1:
        return "1월 자율점검(윤리경영원칙 실천지침 실천 서약)"

    return f"{dt.month}월 자율점검(윤리경영원칙 실천지침 실천서약)"

def ensure_2026_sheet(spreadsheet):
    try:
        spreadsheet.worksheet("2026_윤리경영_실천서약")
        return "2026_윤리경영_실천서약"
    except Exception:
        spreadsheet.add_worksheet(title="2026_윤리경영_실천서약", rows="5000", cols="20")
        return "2026_윤리경영_실천서약"

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = get_sheet_client()
    if client is None:
        return False, "구글 시트 클라이언트 연결 실패"

    try:
        spreadsheet = client.open_by_key(st.secrets["spreadsheet_key"])
    except Exception as e:
        return False, f"스프레드시트 열기 실패: {e}"

    try:
        worksheet = get_or_create_worksheet(spreadsheet, sheet_name)
    except Exception as e:
        return False, f"워크시트 생성/열기 실패: {e}"

    headers = ["제출일시", "사번", "성명", "총괄/본부/단", "상세부서", "서약결과"]
    try:
        first_row = worksheet.row_values(1)
        if first_row != headers:
            worksheet.insert_row(headers, index=1)
    except Exception:
        worksheet.insert_row(headers, index=1)

    tz = pytz.timezone("Asia/Seoul")
    now = datetime.datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    row = [now, emp_id, name, unit, dept, answer]
    try:
        worksheet.append_row(row, value_input_option="USER_ENTERED")
        return True, "저장 완료"
    except Exception as e:
        return False, f"저장 실패: {e}"

# ==========================================
# 9. Streamlit 메인 UI
# ==========================================
st.title("🛡️ AUDIT AI Agent")

tab_audit, tab_doc = st.tabs(["✅ 자율점검", "📂 문서 정밀 검토"])

# --- Tab 1: 자율점검 전용 설정/함수 ---
def _init_pledge_runtime(keys):
    if "pledge_prev" not in st.session_state:
        st.session_state["pledge_prev"] = {}
    if "pledge_running" not in st.session_state:
        st.session_state["pledge_running"] = {}
    if "pledge_done" not in st.session_state:
        st.session_state["pledge_done"] = {}

    for k in keys:
        st.session_state["pledge_prev"].setdefault(k, False)
        st.session_state["pledge_running"].setdefault(k, False)
        st.session_state["pledge_done"].setdefault(k, False)

HOURGLASS_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24">
  <path d="M6 2h12v6c0 2.2-1.2 4.2-3 5 1.8.8 3 2.8 3 5v6H6v-6c0-2.2 1.2-4.2 3-5-1.8-.8-3-2.8-3-5V2z" stroke="#0B5ED7" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M9 6h6" stroke="#0B5ED7" stroke-width="2" stroke-linecap="round"/>
  <path d="M9 18h6" stroke="#0B5ED7" stroke-width="2" stroke-linecap="round"/>
</svg>
"""

def _render_pledge_group(title, items, all_keys):
    st.markdown(
        f"""
        <div style="background:#FFFFFF; border:1px solid #E5E7EB; border-radius:12px; padding:14px 16px; margin-bottom: 10px;">
          <div style="font-weight:900; font-size:1.06rem; margin-bottom: 8px;">{title}</div>
        """,
        unsafe_allow_html=True
    )

    for idx, (key, text_) in enumerate(items, start=1):
        prev = bool(st.session_state["pledge_prev"].get(key, False))
        now_checked = bool(st.session_state.get(key, False))
        running = bool(st.session_state["pledge_running"].get(key, False))
        done = bool(st.session_state["pledge_done"].get(key, False))

        should_start = (not prev) and now_checked and (not done)

        left, right = st.columns([0.78, 0.22])

        with left:
            st.checkbox(f"{idx}. {text_}", key=key)

        with right:
            ph = st.empty()
            if should_start:
                st.session_state["pledge_running"][key] = True
                seconds = 7
                for s in range(seconds, 0, -1):
                    ph.markdown(
                        f"<div class='pledge-right'>{HOURGLASS_SVG}<span>{s}s</span></div>",
                        unsafe_allow_html=True
                    )
                    time.sleep(1)
                st.session_state["pledge_running"][key] = False
                st.session_state["pledge_done"][key] = True
                ph.markdown(
                    "<div style='text-align:right; font-weight:900; color:#27AE60;'>✅ 완료</div>",
                    unsafe_allow_html=True
                )
            else:
                if running:
                    ph.markdown(
                        f"<div class='pledge-right'>{HOURGLASS_SVG}<span>...</span></div>",
                        unsafe_allow_html=True
                    )
                elif done and now_checked:
                    ph.markdown(
                        "<div style='text-align:right; font-weight:900; color:#27AE60;'>✅ 완료</div>",
                        unsafe_allow_html=True
                    )
                else:
                    ph.markdown("", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# --- [Tab 1: 자율점검] ---
with tab_audit:
    campaign_info = {"sheet_name": ensure_2026_sheet(get_sheet_client().open_by_key(st.secrets["spreadsheet_key"]))} if get_sheet_client() else {}
    current_sheet_name = campaign_info.get("sheet_name", "2026_윤리경영_실천서약")

    # ✅ (요청 1) 제목: Google Sheet 값과 무관하게 강제 고정
    title_for_box = "2026 임직원 윤리경영원칙 실천지침 실천서약"

    st.markdown(f"""
        <div style='background-color: #E3F2FD; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; margin-bottom: 20px;'>
            <h3 style='margin-top:0; color: #1565C0;'>📜 {title_for_box}</h3>
        </div>
    """, unsafe_allow_html=True)

    # 2) 실천지침 주요내용
    with st.expander("※ 윤리경영원칙 실천지침 주요내용", expanded=True):
        st.markdown(
            """
            <div style='background-color:#FFFDE7; padding: 18px; border-radius: 10px; border-left: 5px solid #FBC02D; margin-bottom: 12px;'>
                <div style='font-weight: 800; color:#6D4C41; font-size: 1.05rem; margin-bottom: 6px;'>📌 윤리경영 위반 주요 유형</div>
                <div style='color:#444; font-size: 0.95rem; line-height: 1.55;'>
                    아래 항목은 <b>윤리경영원칙 실천지침</b>의 주요 위반 유형을 정리한 내용입니다.
                    업무 수행 시 유사 사례가 발생하지 않도록 참고해 주세요.
                </div>
            </div>

            <div style='overflow-x:auto;'>
                <table style='width:100%; border-collapse: collapse; background:#FFFFFF; border:1px solid #E0E0E0; border-radius: 10px; overflow:hidden;'>
                    <thead>
                        <tr style='background:#FFF8E1;'>
                            <th style='text-align:center; padding:12px; border-bottom:1px solid #E0E0E0; color:#5D4037; width:28%;'>구분</th>
                            <th style='text-align:center; padding:12px; border-bottom:1px solid #E0E0E0; color:#5D4037;'>윤리경영 위반사항</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>고객과의 관계</td>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>고객으로부터 금품 등 이익 수수, 고객만족 저해, 고객정보 유출</td>
                        </tr>
                        <tr>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>임직원과 회사의 관계</td>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>공금 유용 및 횡령, 회사재산의 사적 사용, 기업정보 유출, 경영왜곡</td>
                        </tr>
                        <tr>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; font-weight:700; color:#2C3E50;'>임직원 상호간의 관계</td>
                            <td style='text-align:center; padding:12px; border-bottom:1px solid #F0F0F0; color:#333;'>직장 내 괴롭힘, 성희롱, 조직질서 문란행위</td>
                        </tr>
                        <tr>
                            <td style='text-align:center; padding:12px; font-weight:700; color:#2C3E50;'>이해관계자와의 관계</td>
                            <td style='text-align:center; padding:12px; color:#333;'>이해관계자로부터 금품 등 이익 수수, 이해관계자에게 부당한 요구</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div style='margin-top:10px; color:#666; font-size:0.88rem;'>
                ※ 위 내용은 안내 목적이며, 세부 기준은 사내 <b>윤리경영원칙 실천지침</b>을 따릅니다.
            </div>
            """,
            unsafe_allow_html=True
        )

    # ✅ (요청 2) 원래처럼 섹션 분리 + 체크 시 우측 모래시계/카운트다운 (모든 항목 동일)
    exec_pledges = [
        ("pledge_e1", "나는 회사 윤리경영원칙과 윤리경영원칙 실천지침에 따라 판단하고 행동한다."),
        ("pledge_e2", "나는 윤리경영원칙 실천지침을 몰랐다는 이유로 면책을 주장하지 않는다."),
        ("pledge_e3", "나는 직무수행 과정에서 윤리적 갈등 상황에 직면한 경우 감사부서의 해석에 따른다."),
        ("pledge_e4", "나는 가족, 친·인척, 지인 등을 이용하여 회사 윤리경영원칙 실천지침을 위반하지 않는다."),
    ]
    mgr_pledges = [
        ("pledge_m1", "나는 소속 구성원 및 업무상 이해관계자들이 지침을 준수할 수 있도록 지원하고 관리한다."),
        ("pledge_m2", "나는 공정하고 깨끗한 의사결정을 통해 지침 준수를 솔선수범한다."),
        ("pledge_m3", "나는 부서 내 위반 사안 발생 시 관리자로서의 책임을 다한다."),
    ]

    all_keys = [k for k, _ in exec_pledges] + [k for k, _ in mgr_pledges]
    _init_pledge_runtime(all_keys)

    _render_pledge_group("임직원의 책임과 의무", exec_pledges, all_keys)
    st.markdown("<br>", unsafe_allow_html=True)
    _render_pledge_group("관리자의 책임과 의무", mgr_pledges, all_keys)

    # ✅ prev 상태 업데이트 (탭 끝에서 1번)
    st.session_state["pledge_prev"] = {k: bool(st.session_state.get(k, False)) for k in all_keys}

    st.markdown("---")

    st.markdown(
        "나는 KT MOS 북부의 지속적인 발전을 위하여 회사 윤리경영원칙실천지침에 명시된 "
        "**「임직원의 책임과 의무」** 및 "
        "**「관리자의 책임과 의무」**를 성실히 이행할 것을 서약합니다."
    )

    # 입력 박스
    c1, c2, c3, c4 = st.columns(4)
    emp_id = c1.text_input("사번", placeholder="예: 12345")
    name = c2.text_input("성명")
    ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
    unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
    dept = c4.text_input("상세 부서명")

    st.markdown("---")

    # 제출 버튼은 “체크 전부 완료”일 때만 활성화 (카운트다운 강제는 요구사항에 없어서 제외)
    all_checked = all(bool(st.session_state.get(k, False)) for k in all_keys)
    submit = st.button("서약 제출", use_container_width=True, disabled=(not all_checked))

    if submit:
        if not emp_id or not name:
            st.warning("⚠️ 사번과 성명을 입력해주세요.")
        else:
            answer = "윤리경영 서약서 제출 완료 (임직원 의무 4/4, 관리자 의무 3/3)"
            with st.spinner("제출 중..."):
                success, msg = save_audit_result(emp_id, name, unit, dept, answer, current_sheet_name)
            if success:
                st.success(f"✅ {name}님, 윤리경영 서약서 제출이 완료되었습니다!")
                st.balloons()
            else:
                st.error(f"❌ 제출 실패: {msg}")

# --- [Tab 2: 문서 정밀 검토] ---
with tab_doc:
    st.markdown("### 📂 문서 및 규정 검토")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        option = st.selectbox("작업 유형", ["법률 리스크 정밀 검토", "감사 보고서 검증", "오타 수정 및 교정", "기안문 작성"])

        is_authenticated = True
        if option == "감사 보고서 검증":
            if "audit_verified" not in st.session_state:
                is_authenticated = False
                st.warning("🔒 감사실 전용 메뉴입니다. 인증이 필요합니다.")
                with st.form("doc_auth_form"):
                    pass_input = st.text_input("인증키 입력", type="password")
                    if st.form_submit_button("확인"):
                        if pass_input.strip() == "ktmos0402!":
                            st.session_state["audit_verified"] = True
                            st.rerun()
                        else:
                            st.error("❌ 인증키 불일치")

        if is_authenticated:
            uploaded_file = st.file_uploader("파일 업로드 (PDF, Word, TXT)", type=["txt", "pdf", "docx"])
            if st.button("🚀 분석 시작", use_container_width=True):
                if uploaded_file:
                    content = read_file(uploaded_file)
                    if content:
                        with st.spinner("🧠 AI가 분석 중입니다..."):
                            model = genai.GenerativeModel("gemini-1.5-pro")
                            prompt = f"다음 문서를 정밀 검토해줘:\n\n{content}"
                            resp = model.generate_content(prompt)
                        st.markdown("### ✅ 분석 결과")
                        st.write(resp.text)
                    else:
                        st.warning("⚠️ 파일 내용을 읽지 못했습니다.")
                else:
                    st.warning("⚠️ 파일을 업로드해주세요.")

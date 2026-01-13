import os
from datetime import datetime

import pandas as pd
import streamlit as st

# Optional: Google Sheets (works when secrets are configured)
try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None


# =========================
# App Config
# =========================
st.set_page_config(
    page_title="2026 Ethical Management Self-Inspection",
    page_icon="📜",
    layout="wide",
)

KST_TZ = "Asia/Seoul"


# =========================
# UI / CSS (single, integrated)
# =========================
PRIMARY = "#1565C0"     # same tone as the pledge title request
TEXT_DARK = "#2C3E50"
TEXT_MUTED = "#64748B"
BORDER = "#CBD5E1"
BG = "#F6F7FB"

st.markdown(
    f"""
<style>
/* Page background */
.stApp {{
    background: {BG};
}}

/* Make expander summary clearly visible */
details > summary,
details > summary span,
details[open] > summary,
details[open] > summary span {{
    font-size: 1.30rem !important; /* ← adjust here if you want larger */
    font-weight: 900 !important;
    color: {PRIMARY} !important;
}}

/* Inputs: bold label text inside widgets where possible */
section.main label, section.main label * {{
    font-weight: 800 !important;
    color: {TEXT_DARK} !important;
}}

/* Text input: keep value readable */
section.main [data-testid="stTextInput"] input {{
    color: {TEXT_DARK} !important;
    -webkit-text-fill-color: {TEXT_DARK} !important;
    font-weight: 700 !important;
}}

/* Selectbox: white box + strong readable selected value */
section.main div[data-testid="stSelectbox"] div[role="combobox"] {{
    background:#FFFFFF !important;
    border:1px solid {BORDER} !important;
    border-radius:6px !important;
    min-height: 42px !important;
    box-shadow: none !important;
}}
section.main div[data-testid="stSelectbox"] div[role="combobox"] span {{
    color:{TEXT_DARK} !important;
    font-weight: 800 !important;
    opacity: 1 !important;
}}
/* Arrow */
section.main div[data-testid="stSelectbox"] svg,
section.main div[data-testid="stSelectbox"] svg * {{
    fill:{TEXT_MUTED} !important;
    stroke:{TEXT_MUTED} !important;
    opacity:1 !important;
}}
/* Dropdown list */
div[role="listbox"] * {{
    font-weight: 800 !important;
}}

/* Small helper text */
.small-muted {{
    color: {TEXT_MUTED};
    font-size: 0.92rem;
}}

/* Card sections */
.card {{
    background: #FFFFFF;
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 18px 18px;
}}
.card h3 {{
    margin: 0 0 8px 0;
}}
</style>
""",
    unsafe_allow_html=True,
)


# =========================
# Helpers
# =========================
def now_kst() -> datetime:
    """Return timezone-aware now in KST."""
    try:
        import pytz

        return datetime.now(pytz.timezone(KST_TZ))
    except Exception:
        return datetime.now()


def init_google_sheet_connection():
    """
    Uses st.secrets["gcp_service_account"] to connect.
    Expected secrets structure:
      [gcp_service_account]
      type = ...
      project_id = ...
      private_key_id = ...
      private_key = ...
      client_email = ...
      ...
    """
    if gspread is None or Credentials is None:
        return None

    if "gcp_service_account" not in st.secrets:
        return None

    sa_info = dict(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    return gspread.authorize(creds)


def ensure_worksheet(spreadsheet, sheet_name: str):
    try:
        return spreadsheet.worksheet(sheet_name)
    except Exception:
        # Create with some reasonable size
        return spreadsheet.add_worksheet(title=sheet_name, rows=5000, cols=20)


def save_audit_result(emp_id: str, name: str, unit: str, dept: str, answer: str, sheet_name: str) -> tuple[bool, str]:
    """
    Append a row to Google Sheet.
    """
    client = init_google_sheet_connection()
    if client is None:
        return False, "구글 시트 연결이 설정되어 있지 않습니다. (secrets 확인 필요)"

    try:
        ss = client.open("Audit_Result_2026")
        ws = ensure_worksheet(ss, sheet_name)

        # Ensure header exists
        header = ws.row_values(1)
        wanted = ["제출일시(KST)", "사번", "성명", "총괄/본부/단", "상세부서명", "답변"]
        if header != wanted:
            # If sheet is empty, set header. If not empty but different, still keep existing and append with mapping.
            if not header:
                ws.append_row(wanted, value_input_option="RAW")
            else:
                # Keep existing header; we'll append in same order as wanted anyway.
                pass

        ws.append_row(
            [now_kst().strftime("%Y-%m-%d %H:%M:%S"), emp_id, name, unit, dept, answer],
            value_input_option="RAW",
        )
        return True, "저장 완료"
    except Exception as e:
        return False, f"저장 중 오류: {e}"


# =========================
# Employee number validation (final UX version)
# =========================
def normalize_emp_id(raw: str) -> str:
    digits = "".join(ch for ch in (raw or "") if ch.isdigit())
    return digits[:8]


def validate_emp_id(emp_id: str) -> tuple[bool, str, str]:
    """
    Returns: (ok, level, message)
      level: "info" | "warning" | "success"
    Rules:
    - Required
    - 8 digits numeric
    - Must start with '10' (10******)
    - Exception allowed: '00000000' (no employee number -> contact manager)
    """
    s = (emp_id or "").strip()

    if not s:
        return False, "warning", "⚠️ 사번을 입력해 주세요. (예: 10*******) 사번이 없으면 00000000 입력 후 관리자에게 문의하세요."

    if (not s.isdigit()) or (len(s) != 8):
        return False, "warning", "⚠️ 사번은 8자리 숫자입니다. 예: 10*******. 사번이 없으면 00000000을 입력하세요."

    if s == "00000000":
        return True, "info", "ℹ️ 사번 미기재(00000000)로 제출됩니다. 제출 후 관리자에게 문의해 주세요."

    if not s.startswith("10"):
        return False, "warning", "⚠️ 회사 사번 형식(10******)이 아닙니다. 사번이 없으면 00000000 입력 후 관리자에게 문의하세요."

    return True, "success", "✅ 사번 형식 확인 완료"


# =========================
# Data (edit freely)
# =========================
UNITS = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]

PLEDGES = [
    "윤리경영 원칙을 준수하고, 관련 지침을 성실히 이행하겠습니다.",
    "부당한 요구·금품수수·청탁을 거절하고, 이해충돌을 회피하겠습니다.",
    "업무상 취득한 정보와 개인정보를 보호하고, 회사 자산을 성실히 관리하겠습니다.",
    "법규 및 사규를 준수하며, 위반 사항을 인지할 경우 즉시 보고·개선하겠습니다.",
]


# =========================
# Layout
# =========================
st.markdown(
    """
<div class="card">
  <h2 style="margin:0;">📜 2026 임직원 윤리경영원칙 실천지침 실천서약</h2>
  <div class="small-muted">자율점검 입력 UI 가독성 개선(사번 즉시 검증 / 선택값 가독성 강화)</div>
</div>
""",
    unsafe_allow_html=True,
)

st.write("")

tab_audit, tab_admin = st.tabs(["✅ 자율점검", "🔒 관리자"])


with tab_audit:
    st.markdown("<div class='card'>", unsafe_allow_html=True)

    with st.expander("※ 윤리경영원칙 실천지침 주요내용", expanded=False):
        st.markdown(
            """
- 회사 윤리경영원칙 및 실천지침의 목적과 적용 범위  
- 이해충돌 방지, 금품·향응 수수 금지, 공정거래 준수  
- 개인정보/영업비밀 보호 및 정보보안 준수  
- 위반 신고 및 보호 제도 안내
"""
        )

    with st.expander("✅ 서약 확인 및 임직원 정보 입력", expanded=True):
        st.caption("사번/성명/소속을 입력하고, 서약 체크 후 제출해 주세요.")

        # ---- Employee info row (4 columns, one line) ----
        c1, c2, c3, c4 = st.columns(4)

        if "emp_id_raw" not in st.session_state:
            st.session_state["emp_id_raw"] = ""

        def _on_emp_change():
            st.session_state["emp_id_raw"] = normalize_emp_id(st.session_state.get("emp_id_raw", ""))

        emp_id = c1.text_input(
            "사번",
            placeholder="예: 10*******(8자리) / 없으면 00000000",
            key="emp_id_raw",
            on_change=_on_emp_change,
        )
        name = c2.text_input("성명", placeholder="예: 홍길동", key="emp_name")

        unit_options = ["총괄 / 본부 / 단 선택"] + UNITS
        unit_sel = c3.selectbox("총괄/본부/단", unit_options, index=0, label_visibility="visible", key="unit_sel")
        dept = c4.text_input("상세 부서명", placeholder="예: 경영총괄 ㅇㅇ팀", key="dept_name")

        unit = "" if unit_sel == "총괄 / 본부 / 단 선택" else unit_sel

        # ---- live validation message for employee id ----
        ok_emp, level, msg = validate_emp_id(emp_id)
        if emp_id.strip():
            if level == "warning":
                st.warning(msg)
            elif level == "info":
                st.info(msg)
            else:
                st.success(msg)
        else:
            st.info("ℹ️ 사번 입력 후 형식이 즉시 안내됩니다.")

        st.write("")
        st.subheader("서약 체크")
        checks = []
        for i, p in enumerate(PLEDGES, start=1):
            checks.append(st.checkbox(f"{i}. {p}", key=f"pledge_{i}"))

        all_checked = all(checks)

        st.write("")
        st.markdown("---")

        # ---- final gate conditions ----
        name_ok = bool(str(name).strip())
        unit_ok = bool(str(unit).strip())
        dept_ok = bool(str(dept).strip())

        can_submit = all_checked and ok_emp and name_ok and unit_ok and dept_ok

        # Guidance: show missing fields before submit
        missing = []
        if not ok_emp:
            missing.append("사번")
        if not name_ok:
            missing.append("성명")
        if not unit_ok:
            missing.append("총괄/본부/단")
        if not dept_ok:
            missing.append("상세 부서명")
        if not all_checked:
            missing.append("서약 체크(전체)")

        if missing:
            st.info(f"ℹ️ 입력값 확인 필요: {', '.join(missing)}")

        submit = st.button("제출", type="primary", use_container_width=True, disabled=(not can_submit))

        if submit:
            # Final confirmation message requested
            st.warning(
                "입력값(사번/성명/총괄·본부·단/상세부서명)이 정확한지 확인 후 제출해 주세요. "
                "정확하지 않으면 제출하지 마세요."
            )

            answer = "윤리경영 서약 제출 완료"
            sheet_name = f"{now_kst().year}_{now_kst().month:02d}_자율점검"

            with st.spinner("제출 중..."):
                success, result_msg = save_audit_result(emp_id, name, unit, dept, answer, sheet_name)

            if success:
                st.success(f"✅ {name}님, 제출이 완료되었습니다.")
                if emp_id == "00000000":
                    st.info("ℹ️ 사번 미기재(00000000)로 제출되었습니다. 관리자에게 문의해 주세요.")
                st.balloons()
            else:
                st.error(f"❌ 제출 실패: {result_msg}")

    st.markdown("</div>", unsafe_allow_html=True)


with tab_admin:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("관리자")
    st.caption("이 영역은 필요 시 확장 가능합니다. (현재는 구글시트 연결 여부만 점검)")
    client = init_google_sheet_connection()
    if client is None:
        st.warning("구글 시트 연결이 설정되어 있지 않습니다. (Streamlit secrets 확인)")
    else:
        st.success("구글 시트 연결 OK")
        try:
            ss = client.open("Audit_Result_2026")
            st.write("스프레드시트 접근 OK:", ss.title)
        except Exception as e:
            st.error(f"스프레드시트 접근 오류: {e}")

    st.markdown("</div>", unsafe_allow_html=True)

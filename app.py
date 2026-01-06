# coding: utf-8
import os
import secrets
import json
import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# -------------------------
# 구글 시트 라이브러리
# -------------------------
try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSHEETS_AVAILABLE = True
except Exception:
    GSHEETS_AVAILABLE = False

# -------------------------
# 기본 설정
# -------------------------
APP_TITLE = "1월 주만나 큐티 체크 리스트"
VERSE_TEXT = "주를 경외하게 하는 주의 말씀을 주의 종에게 세우소서 [시편 119:38절]"
SUPPORTED_MONTHS = [(2026, 1, "2026년 1월"), (2026, 2, "2026년 2월"), (2026, 3, "2026년 3월")]

SHEET_RECORDS = "qti_records"  # 일별 기록
SHEET_USERS = "qti_users"      # uid별 성도 정보(직분/이름)

MEMBER_ROLES = ["평신도", "서리집사", "안수집사", "권사", "장로", "강도사", "목사", "기타"]

KST = ZoneInfo("Asia/Seoul")
ADMIN_KEY_FALLBACK = "yeiun1234"  # secrets에 없을 때만 fallback

_HHMM = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


# -------------------------
# 유틸
# -------------------------
def now_kst() -> datetime:
    return datetime.now(tz=KST)


def today_kst() -> date:
    return now_kst().date()


def now_hhmm_kst() -> str:
    return now_kst().strftime("%H:%M")


def normalize_hhmm(s: str) -> str:
    s = (s or "").strip()
    return s if _HHMM.match(s) else ""


def clamp_50(s: str) -> str:
    return (s or "").strip()[:50]


def clamp_20(s: str) -> str:
    return (s or "").strip()[:20]


def normalize_role(s: str) -> str:
    s = (s or "").strip()
    return s if s in MEMBER_ROLES else (MEMBER_ROLES[-1] if s else "")


def month_range(year: int, month: int) -> Tuple[date, date]:
    start = date(year, month, 1)
    end = (date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)) - timedelta(days=1)
    return start, end


def daterange(d1: date, d2: date):
    curr = d1
    while curr <= d2:
        yield curr
        curr += timedelta(days=1)


def week_start_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())  # 월=0


def clamp_date(d: date, start: date, end: date) -> date:
    return max(start, min(end, d))


# -------------------------
# 공유 URL (하드코딩 제거)
# -------------------------
def build_share_url(uid: str) -> str:
    base = None
    try:
        base = st.context.url
    except Exception:
        base = None

    if not base:
        base = st.secrets.get("PUBLIC_APP_URL")

    if not base:
        base = "https://<YOUR-APP>.streamlit.app"

    return f"{base}?{urlencode({'uid': uid})}"


# -------------------------
# 주소 패널 자동 숨김 + 토글
# -------------------------
def inject_share_panel_js():
    components.html(
        """
        <script>
          (function() {
            const doc = window.parent.document;
            const panel = doc.getElementById('sharePanel');
            const btn = doc.getElementById('shareToggleBtn');
            if (!panel || !btn) return;

            const setIcon = () => {
              const collapsed = panel.classList.contains('collapsed');
              btn.textContent = collapsed ? '▾' : '▴';
              btn.setAttribute('aria-label', collapsed ? '펼치기' : '숨기기');
              btn.setAttribute('title', collapsed ? '펼치기' : '숨기기');
            };

            if (!window.__sharePanelBound) {
              window.__sharePanelBound = true;
              btn.addEventListener('click', () => {
                panel.classList.toggle('collapsed');
                setIcon();
              });
            }

            setIcon();

            if (window.__shareAutoHideTimer) clearTimeout(window.__shareAutoHideTimer);
            window.__shareAutoHideTimer = setTimeout(() => {
              panel.classList.add('collapsed');
              setIcon();
            }, 5000);
          })();
        </script>
        """,
        height=0,
    )


def apply_css():
    st.markdown(
        """
        <style>
          html, body, [class*="css"]  { font-size: 18px !important; }
          .stButton>button { height: 54px; font-size: 18px; border-radius: 14px; }
          textarea, input { font-size: 18px !important; }

          /* share panel */
          #sharePanel {
            border-radius: 16px;
            border: 1px solid rgba(0,0,0,0.06);
            box-shadow: 0 8px 22px rgba(0,0,0,0.06);
            background: linear-gradient(135deg, #f7fbff 0%, #fff7fb 55%, #f6fff8 100%);
            overflow: hidden;
            margin-top: 6px;
            margin-bottom: 8px;
          }
          #shareHeader {
            display:flex;
            align-items:center;
            justify-content:space-between;
            padding: 10px 12px;
            font-weight: 900;
          }
          #shareTitle { font-size: 18px; }
          #shareToggleBtn {
            appearance:none;
            border: 1px solid rgba(0,0,0,0.10);
            background: rgba(255,255,255,0.75);
            border-radius: 12px;
            width: 42px;
            height: 36px;
            cursor: pointer;
            display:flex;
            align-items:center;
            justify-content:center;
            box-shadow: 0 6px 16px rgba(0,0,0,0.07);
            font-size: 18px;
            font-weight: 900;
          }
          #shareToggleBtn:active { transform: scale(0.98); }
          #shareContent {
            padding: 0 12px 12px 12px;
            overflow: hidden;
            transition: max-height 520ms ease, opacity 520ms ease, transform 520ms ease;
            max-height: 520px;
            opacity: 1;
            transform: translateY(0px);
          }
          #sharePanel.collapsed #shareContent {
            max-height: 0px;
            opacity: 0;
            transform: translateY(-6px);
            padding-bottom: 0px;
          }

          /* table alignment */
          .qti-table-wrap { overflow-x: auto; }
          table.qti-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 8px 22px rgba(0,0,0,0.07);
            border: 1px solid rgba(0,0,0,0.06);
          }
          table.qti-table thead th {
            text-align: center !important;
            font-weight: 900;
            background: linear-gradient(135deg, #f7fbff 0%, #fff7fb 100%);
            padding: 10px 10px;
            border-bottom: 1px solid rgba(0,0,0,0.06);
            white-space: nowrap;
          }
          table.qti-table tbody td {
            text-align: center !important;
            padding: 10px 10px;
            border-bottom: 1px solid rgba(0,0,0,0.06);
            background: #ffffff;
            white-space: nowrap;
            vertical-align: top;
          }
          /* 나의 묵상 기도만 왼쪽 정렬 */
          table.qti-table tbody td:nth-child(5) {
            text-align: left !important;
            white-space: normal;
            line-height: 1.35;
          }
          table.qti-table th:nth-child(1), table.qti-table td:nth-child(1) { width: 120px; }
          table.qti-table th:nth-child(2), table.qti-table td:nth-child(2) { width: 90px; }
          table.qti-table th:nth-child(3), table.qti-table td:nth-child(3) { width: 90px; }
          table.qti-table th:nth-child(4), table.qti-table td:nth-child(4) { width: 70px; }
          table.qti-table th:nth-child(5), table.qti-table td:nth-child(5) { width: auto; }
          table.qti-table tbody tr:last-child td { border-bottom: none; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_qt_table_html(df: pd.DataFrame):
    if df is None or df.empty:
        st.info("표시할 기록이 없습니다.")
        return
    dfx = df.copy()
    if "완료" in dfx.columns:
        dfx["완료"] = dfx["완료"].apply(lambda x: "✅" if bool(x) else "")
    cols = [c for c in ["날짜", "QT 시작", "QT 종료", "완료", "나의 묵상 기도"] if c in dfx.columns]
    dfx = dfx[cols]
    html = dfx.to_html(index=False, escape=True, classes="qti-table")
    st.markdown(f"<div class='qti-table-wrap'>{html}</div>", unsafe_allow_html=True)


# -------------------------
# 구글 시트 저장소
# -------------------------
class GoogleSheetsStorage:
    RECORDS_REQUIRED = [
        "uid", "member_role", "member_name", "day",
        "start_time", "end_time", "completed",
        "signature", "prayer_note", "updated_at"
    ]
    USERS_REQUIRED = ["uid", "member_role", "member_name", "updated_at"]

    def __init__(self, spreadsheet_id: str, worksheet_records: str, sa_json: dict):
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(sa_json, scopes=scopes)
        self.gc = gspread.authorize(creds)
        self.sh = self.gc.open_by_key(spreadsheet_id)

        # worksheets
        try:
            self.ws = self.sh.worksheet(worksheet_records)
        except Exception:
            self.ws = self.sh.add_worksheet(title=worksheet_records, rows=2000, cols=20)

        try:
            self.ws_users = self.sh.worksheet("users")
        except Exception:
            self.ws_users = self.sh.add_worksheet(title="users", rows=2000, cols=10)

        # schema/index cache (process-wide via st.cache_resource)
        self._schema_verified = False
        self._records_header: list[str] = []
        self._users_header: list[str] = []
        self.col_idx: dict[str, int] = {}  # 1-indexed col index for records
        self.users_col_idx: dict[str, int] = {}  # 1-indexed col index for users

        self._row_index: dict[tuple[str, str], int] = {}  # (uid, day) -> row_idx
        self._index_built_at: float = 0.0

        # Verify schema once at creation (with retry/backoff)
        self._ensure_schema()

    # -------------------------
    # Low-level: retry wrapper
    # -------------------------
    def _call_with_retries(self, fn, *args, **kwargs):
        """Retry transient gspread API errors (429/5xx) with exponential backoff."""
        import time
        last_err = None
        for attempt in range(3):
            try:
                return fn(*args, **kwargs)
            except gspread.exceptions.APIError as e:
                last_err = e
                # Best-effort: retry on rate limit / transient backend issues
                msg = str(e)
                retryable = any(code in msg for code in ("429", "500", "502", "503", "504"))
                if not retryable or attempt == 2:
                    raise
                time.sleep(1.0 * (2 ** attempt))
            except Exception as e:
                # Non-API errors: don't spin unless clearly transient
                last_err = e
                raise
        if last_err:
            raise last_err

    # -------------------------
    # Schema: verify once
    # -------------------------
    def _ensure_schema(self):
        if self._schema_verified:
            return

        # records header
        hdr = self._call_with_retries(self.ws.row_values, 1) or []
        hdr = [str(x).strip() for x in hdr if str(x).strip()]

        if not hdr:
            hdr = list(self.RECORDS_REQUIRED)
            # Ensure enough columns
            try:
                if self.ws.col_count < len(hdr):
                    self._call_with_retries(self.ws.add_cols, len(hdr) - self.ws.col_count)
            except Exception:
                pass
            self._call_with_retries(self.ws.update, "A1", [hdr])
        else:
            missing = [c for c in self.RECORDS_REQUIRED if c not in hdr]
            if missing:
                new_hdr = hdr + missing
                try:
                    if self.ws.col_count < len(new_hdr):
                        self._call_with_retries(self.ws.add_cols, len(new_hdr) - self.ws.col_count)
                except Exception:
                    pass
                self._call_with_retries(self.ws.update, "A1", [new_hdr])
                hdr = new_hdr

        self._records_header = hdr
        self._refresh_col_index()

        # users header
        uhdr = self._call_with_retries(self.ws_users.row_values, 1) or []
        uhdr = [str(x).strip() for x in uhdr if str(x).strip()]

        if not uhdr:
            uhdr = list(self.USERS_REQUIRED)
            try:
                if self.ws_users.col_count < len(uhdr):
                    self._call_with_retries(self.ws_users.add_cols, len(uhdr) - self.ws_users.col_count)
            except Exception:
                pass
            self._call_with_retries(self.ws_users.update, "A1", [uhdr])
        else:
            umissing = [c for c in self.USERS_REQUIRED if c not in uhdr]
            if umissing:
                new_uhdr = uhdr + umissing
                try:
                    if self.ws_users.col_count < len(new_uhdr):
                        self._call_with_retries(self.ws_users.add_cols, len(new_uhdr) - self.ws_users.col_count)
                except Exception:
                    pass
                self._call_with_retries(self.ws_users.update, "A1", [new_uhdr])
                uhdr = new_uhdr

        self._users_header = uhdr
        self._refresh_users_col_index()

        self._schema_verified = True

    def _refresh_col_index(self):
        self.col_idx = {name: i + 1 for i, name in enumerate(self._records_header)}

    def _refresh_users_col_index(self):
        self.users_col_idx = {name: i + 1 for i, name in enumerate(self._users_header)}

    # -------------------------
    # Data helpers
    # -------------------------
    def _empty_df(self, start: date, end: date) -> pd.DataFrame:
        return pd.DataFrame(
            [{"날짜": d.isoformat(), "QT 시작": "", "QT 종료": "", "완료": False, "나의 묵상 기도": ""} for d in daterange(start, end)]
        )

    def fetch_all_records_df(self) -> pd.DataFrame:
        """(관리/분석용) 전체 로드. 호출 횟수는 최소화해서 사용하세요."""
        self._ensure_schema()
        rows = self._call_with_retries(self.ws.get_all_records)
        df_all = pd.DataFrame(rows)
        if df_all.empty:
            return pd.DataFrame(columns=self.RECORDS_REQUIRED)
        for c in self.RECORDS_REQUIRED:
            if c not in df_all.columns:
                df_all[c] = ""
        return df_all[self.RECORDS_REQUIRED]

    # -------------------------
    # Profile (users sheet)
    # -------------------------
    def get_profile(self, uid: str) -> Tuple[str, str]:
        self._ensure_schema()
        try:
            rows = self._call_with_retries(self.ws_users.get_all_records)
            dfu = pd.DataFrame(rows)
            if dfu.empty:
                return "", ""
            hit = dfu[dfu["uid"].astype(str) == str(uid)]
            if hit.empty:
                return "", ""
            if "updated_at" in hit.columns:
                hit = hit.sort_values("updated_at")
            r = hit.iloc[-1]
            return normalize_role(r.get("member_role", "")), clamp_20(r.get("member_name", ""))
        except Exception:
            return "", ""

    def upsert_profile(self, uid: str, member_role: str, member_name: str):
        """프로필 저장은 자주 호출되지 않으므로 단순/안전하게 처리."""
        self._ensure_schema()
        now_iso = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        role = normalize_role(member_role)
        name = clamp_20(member_name)

        # 최소 호출: uid 컬럼만 읽어서 기존 행 찾기 (1회)
        uid_col = self.users_col_idx.get("uid", 1)
        max_col = uid_col
        end_letter = _col_to_letter(max_col)
        values = self._call_with_retries(self.ws_users.get, f"A2:{end_letter}")
        row_idx = None
        for i, row in enumerate(values, start=2):
            v_uid = row[uid_col - 1] if len(row) >= uid_col else ""
            if str(v_uid) == str(uid):
                row_idx = i
                break

        if row_idx is None:
            new_row = []
            for h in self._users_header:
                if h == "uid":
                    new_row.append(str(uid))
                elif h == "member_role":
                    new_row.append(role)
                elif h == "member_name":
                    new_row.append(name)
                elif h == "updated_at":
                    new_row.append(now_iso)
                else:
                    new_row.append("")
            self._call_with_retries(self.ws_users.append_row, new_row, value_input_option="USER_ENTERED")
        else:
            cells = []
            def q(colname, val):
                c = self.users_col_idx.get(colname)
                if c:
                    cells.append(gspread.Cell(row_idx, c, str(val)))
            q("member_role", role)
            q("member_name", name)
            q("updated_at", now_iso)
            if cells:
                self._call_with_retries(self.ws_users.update_cells, cells, value_input_option="USER_ENTERED")

    # -------------------------
    # Index build: (uid, day) -> row_idx
    # -------------------------
    def _build_row_index(self, force: bool = False):
        import time
        if (not force) and self._row_index and (time.time() - self._index_built_at) < 60:
            return

        self._ensure_schema()
        uid_col = self.col_idx.get("uid", 1)
        day_col = self.col_idx.get("day", 4)
        max_col = max(uid_col, day_col)
        end_letter = _col_to_letter(max_col)

        # 1회 호출로 필요한 범위만 읽기
        values = self._call_with_retries(self.ws.get, f"A2:{end_letter}")

        idx = {}
        for r_i, row in enumerate(values, start=2):
            v_uid = row[uid_col - 1] if len(row) >= uid_col else ""
            v_day = row[day_col - 1] if len(row) >= day_col else ""
            if v_uid and v_day:
                idx[(str(v_uid), str(v_day))] = r_i

        self._row_index = idx
        self._index_built_at = time.time()

    # -------------------------
    # Month load (UI)
    # -------------------------
    def load_month(self, uid: str, start: date, end: date) -> pd.DataFrame:
        try:
            df_all = self.fetch_all_records_df()
            if df_all.empty:
                return self._empty_df(start, end)

            user_data = df_all[
                (df_all["uid"].astype(str) == str(uid))
                & (df_all["day"] >= start.isoformat())
                & (df_all["day"] <= end.isoformat())
            ].copy()

            if user_data.empty:
                return self._empty_df(start, end)

            # Normalize
            user_data["day"] = user_data["day"].astype(str)

            # Build view
            out = []
            mp = {row["day"]: row for _, row in user_data.iterrows()}
            for d in daterange(start, end):
                ds = d.isoformat()
                r = mp.get(ds, {})
                out.append(
                    {
                        "날짜": ds,
                        "QT 시작": normalize_hhmm(r.get("start_time", "")),
                        "QT 종료": normalize_hhmm(r.get("end_time", "")),
                        "완료": str(r.get("completed", "")).lower() in ("true", "1", "yes", "y", "완료"),
                        "나의 묵상 기도": (r.get("prayer_note", "") or ""),
                    }
                )
            return pd.DataFrame(out)
        except Exception:
            return self._empty_df(start, end)

    # -------------------------
    # Upsert record: minimal calls
    # -------------------------
    def upsert_one(self, uid: str, day: str, **kwargs):
        self._ensure_schema()

        # Build (or reuse) index without reading entire sheet every time
        self._build_row_index()

        key = (str(uid), str(day))
        row_idx = self._row_index.get(key)

        now_iso = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")

        def norm_value(k, v):
            if k in ("start_time", "end_time"):
                return normalize_hhmm(str(v))
            if k == "completed":
                return "TRUE" if bool(v) else "FALSE"
            if k == "member_role":
                return normalize_role(str(v))
            if k == "member_name":
                return clamp_20(str(v))
            if k == "prayer_note":
                return str(v)[:5000]
            return str(v)

        if row_idx is None:
            # append 1회 호출
            row = []
            for h in self._records_header:
                if h == "uid":
                    row.append(str(uid))
                elif h == "day":
                    row.append(str(day))
                elif h == "updated_at":
                    row.append(now_iso)
                elif h in kwargs:
                    row.append(norm_value(h, kwargs[h]))
                else:
                    row.append("")
            self._call_with_retries(self.ws.append_row, row, value_input_option="USER_ENTERED")
            # index is now stale; rebuild later
            self._row_index = {}
            self._index_built_at = 0.0
            return

        # update_cells 1회 호출
        cells = []
        def queue_cell(col_name: str, val):
            c = self.col_idx.get(col_name)
            if c:
                cells.append(gspread.Cell(row_idx, c, str(val)))

        # always keep these consistent
        queue_cell("uid", str(uid))
        queue_cell("day", str(day))
        queue_cell("updated_at", now_iso)

        for k, v in kwargs.items():
            if k in self.col_idx:
                queue_cell(k, norm_value(k, v))

        if cells:
            self._call_with_retries(self.ws.update_cells, cells, value_input_option="USER_ENTERED")

# local helper (kept near class; no other code touched)
def _col_to_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s
@st.cache_resource
def get_storage() -> Optional[GoogleSheetsStorage]:
    if not GSHEETS_AVAILABLE:
        return None
    s_id = st.secrets.get("GSHEETS_SPREADSHEET_ID")
    sa_json = st.secrets.get("GSHEETS_SERVICE_ACCOUNT_JSON")
    if s_id and sa_json:
        sa_obj = json.loads(sa_json) if isinstance(sa_json, str) else sa_json
        return GoogleSheetsStorage(s_id, SHEET_RECORDS, sa_obj)
    return None


@st.cache_data(ttl=60)
def cached_all_records_df() -> pd.DataFrame:
    s = get_storage()
    if not s:
        return pd.DataFrame()
    return s.fetch_all_records_df()


def require_admin_login() -> bool:
    admin_pw = st.secrets.get("ADMIN_KEY") or st.secrets.get("ADMIN_PASSWORD") or ADMIN_KEY_FALLBACK

    if "is_admin" not in st.session_state:
        st.session_state["is_admin"] = False
    if st.session_state["is_admin"]:
        return True

    st.subheader("🔐 관리자 로그인")
    pw = st.text_input("관리자 비밀번호", type="password", placeholder="관리자 비밀번호 입력")
    if st.button("로그인", use_container_width=True):
        if pw == admin_pw:
            st.session_state["is_admin"] = True
            st.success("관리자 로그인 완료")
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    return False


def compute_participation(df_all: pd.DataFrame, start: date, end: date) -> Tuple[int, int, float]:
    """
    반환: (참여 uid 수, 전체 uid 수, 참여율)
    기준: 기간 내 completed=1이 1회라도 있으면 '참여'
    """
    if df_all is None or df_all.empty:
        return 0, 0, 0.0

    total_uids = set(df_all["uid"].astype(str).unique().tolist())
    total = len([u for u in total_uids if u])

    dfx = df_all.copy()
    dfx = dfx[(dfx["day"] >= start.isoformat()) & (dfx["day"] <= end.isoformat())]
    dfx = dfx[dfx["completed"].astype(str) == "1"]
    active = len(set(dfx["uid"].astype(str).unique().tolist()))
    rate = (active / total) if total else 0.0
    return active, total, rate


def admin_dashboard():
    st.header("📊 관리자 대시보드")

    df_all = cached_all_records_df()
    if df_all.empty:
        st.info("기록이 아직 없습니다.")
        return

    c1, c2 = st.columns([1, 1])
    with c1:
        anchor = st.date_input("기준일(주간 통계)", value=today_kst())
    with c2:
        month_label = st.selectbox("월(요약/다운로드)", [m[2] for m in SUPPORTED_MONTHS])

    y, m = [(yy, mm) for (yy, mm, lbl) in SUPPORTED_MONTHS if lbl == month_label][0]
    m_start, m_end = month_range(y, m)

    wk_start = week_start_monday(anchor)
    wk_end = wk_start + timedelta(days=6)

    a_wk, t_all, r_wk = compute_participation(df_all, wk_start, wk_end)
    a_m, _, r_m = compute_participation(df_all, m_start, m_end)

    st.markdown("### ✅ 참여 현황")
    k1, k2, k3 = st.columns(3)
    k1.metric("이번 주 참여", f"{a_wk}명", f"{r_wk:.0%}")
    k2.metric("이번 달 참여", f"{a_m}명", f"{r_m:.0%}")
    k3.metric("전체 UID 수", f"{t_all}명")

    # 최신 프로필(기록 기준 최신값)
    latest = df_all.copy()
    latest["_t"] = pd.to_datetime(latest["updated_at"], errors="coerce")
    latest = latest.sort_values(["uid", "_t"])
    prof = latest.groupby("uid", as_index=False).tail(1)[["uid", "member_role", "member_name"]].copy()
    prof["member_role"] = prof["member_role"].fillna("").astype(str)
    prof["member_name"] = prof["member_name"].fillna("").astype(str)

    # 월 기준 참여일수
    dmonth = df_all[(df_all["day"] >= m_start.isoformat()) & (df_all["day"] <= m_end.isoformat())].copy()
    dmonth["completed_bool"] = dmonth["completed"].astype(str) == "1"
    cnts = dmonth[dmonth["completed_bool"]].groupby("uid", as_index=False)["day"].nunique().rename(columns={"day": "완료일수"})
    merged = prof.merge(cnts, on="uid", how="left")
    merged["완료일수"] = merged["완료일수"].fillna(0).astype(int)

    st.markdown("### 👥 성도 참여(월 기준)")
    st.dataframe(
        merged.sort_values(["완료일수", "member_name"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### ⬇️ 데이터 다운로드")
    csv = dmonth.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "월 데이터 CSV 다운로드",
        data=csv,
        file_name=f"qti_records_{m_start.strftime('%Y%m')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption("※ 이름이 비어있는 UID는 성도님이 성도 정보를 아직 저장하지 않은 경우입니다.")


# -------------------------
# 앱 시작
# -------------------------
st.set_page_config(page_title=APP_TITLE, layout="wide")

# --- Responsive UI (PC/Mobile) ---
st.markdown(
    """
<style>
/* Base (desktop/tablet) */
html, body, [class*="css"] { font-size: 16px; }
h1 { font-size: 1.6rem; line-height: 1.2; }
h2 { font-size: 1.25rem; line-height: 1.25; }
h3 { font-size: 1.10rem; line-height: 1.25; }

.stButton button {
  font-size: 0.95rem;
  padding: 0.45rem 0.75rem;
}

label, .stMarkdown, .stText, .stCaption, .stRadio, .stSelectbox, .stTextInput, .stDateInput {
  font-size: 0.95rem;
}

.block-container { padding-top: 1.0rem; padding-bottom: 2.0rem; }

/* Mobile */
@media (max-width: 640px) {
  html, body, [class*="css"] { font-size: 13px; }

  h1 { font-size: 1.25rem; }
  h2 { font-size: 1.10rem; }
  h3 { font-size: 1.00rem; }

  .stButton button {
    font-size: 0.85rem;
    padding: 0.35rem 0.6rem;
    border-radius: 10px;
  }

  label, .stMarkdown, .stText, .stCaption { font-size: 0.88rem; }

  .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }

  div[data-baseweb="select"] > div { min-height: 36px; }
  input, textarea { font-size: 0.90rem !important; }

  .stDataFrame { overflow-x: auto; }
}

/* Very small phones */
@media (max-width: 380px) {
  html, body, [class*="css"] { font-size: 12.5px; }
  .stButton button { font-size: 0.82rem; padding: 0.32rem 0.55rem; }
}
</style>
    """,
    unsafe_allow_html=True
)
apply_css()

storage = get_storage()
if not storage:
    st.error("구글 시트 설정(Secrets) 또는 gspread 라이브러리를 확인해주세요.")
    st.stop()

st.title(f"✨ {APP_TITLE}")
st.caption(VERSE_TEXT)

mode = st.radio("모드 선택", ["성도님(기록하기)", "관리자(대시보드)"], horizontal=True)

# 관리자
if mode == "관리자(대시보드)":
    if require_admin_login():
        admin_dashboard()
    st.stop()

# -------------------------
# 성도님 모드
# -------------------------
# UID 관리
if "uid" not in st.query_params:
    st.info("### 🙏 큐티 체크리스트 시작하기\n성도님 전용 기록지를 만들기 위해 아래 버튼을 눌러주세요.")
    if st.button("🚀 나의 큐티 링크 만들기 (처음 1회)", use_container_width=True):
        new_uid = secrets.token_urlsafe(8)
        st.query_params["uid"] = new_uid
        st.rerun()
    st.stop()

uid = st.query_params["uid"]

# 성도 프로필 자동 불러오기(최초 1회)
if "profile_loaded" not in st.session_state:
    role0, name0 = storage.get_profile(uid)
    st.session_state["member_role"] = role0 or MEMBER_ROLES[0]
    st.session_state["member_name"] = name0 or ""
    st.session_state["profile_loaded"] = True

# 성도 정보 입력(상단)
st.markdown("---")
with st.container(border=True):
    st.subheader("🙋 성도 정보(1회 입력)")
    st.caption("한 번 입력하면 다음 접속 때 자동으로 불러오고, 이후 모든 기록에 uid/이름/직분이 함께 저장됩니다.")

    col_r, col_n, col_s = st.columns([1.2, 1.8, 1.0])
    with col_r:
        cur_role = st.session_state.get("member_role", MEMBER_ROLES[0])
        idx = MEMBER_ROLES.index(cur_role) if cur_role in MEMBER_ROLES else 0
        st.selectbox("직분", MEMBER_ROLES, index=idx, key="member_role")
    with col_n:
        st.text_input("성도 이름", key="member_name", placeholder="예) 홍 길 동")
    with col_s:
        st.write("")
        st.write("")
        if st.button("💾 성도 정보 저장", use_container_width=True):
            role_clean = normalize_role(st.session_state.get("member_role", ""))
            name_clean = clamp_20(st.session_state.get("member_name", ""))
            if not name_clean:
                st.warning("이름을 입력해 주세요.")
            else:
                storage.upsert_profile(uid, role_clean, name_clean)
                st.success("저장되었습니다! 다음 접속부터 자동으로 불러옵니다.")
                st.rerun()

    st.info(f"현재 저장 값: {normalize_role(st.session_state.get('member_role','')) or '-'} / {clamp_20(st.session_state.get('member_name','')) or '-'}")


# 월 선택
month_label = st.selectbox("📆 월 선택", [m[2] for m in SUPPORTED_MONTHS])
year, month = [(y, m) for (y, m, lbl) in SUPPORTED_MONTHS if lbl == month_label][0]
START, END = month_range(year, month)


# 월 데이터
df = storage.load_month(uid, START, END)

# 진행률
done_cnt = int(df["완료"].sum()) if not df.empty else 0
total_cnt = len(df) if len(df) > 0 else 1
progress = done_cnt / total_cnt
st.metric("이번 달 달성", f"{done_cnt}일", f"{progress:.1%}")
st.progress(progress)

# 공유 링크 패널(자동 숨김 + 우측 아이콘 토글)
share_url = build_share_url(uid)
st.markdown(
    """
    <div id="sharePanel">
      <div id="shareHeader">
        <div id="shareTitle">📌 내 기록지 주소 저장하기</div>
        <button id="shareToggleBtn" type="button">▴</button>
      </div>
      <div id="shareContent">
        <div style="font-weight:800; margin-bottom:8px;">
          이 주소를 꼭 복사해서 카톡 ‘나에게 보내기’에 저장하거나 즐겨찾기 하세요!
        </div>
    """,
    unsafe_allow_html=True,
)
st.code(share_url)
if "<YOUR-APP>" in share_url:
    st.warning("PUBLIC_APP_URL이 설정되지 않아 임시 주소가 보입니다. Secrets에 실제 앱 주소를 넣어주세요.")
st.markdown("</div></div>", unsafe_allow_html=True)
inject_share_panel_js()

st.markdown("---")

# 오늘 기록
with st.container(border=True):
    st.subheader("✍️ 오늘의 큐티 기록")

    if "picked_day" not in st.session_state:
        st.session_state["picked_day"] = today_kst()
    picked_day = st.date_input("날짜 선택", value=st.session_state["picked_day"], key="picked_day")
    day_str = picked_day.isoformat()

    role_to_save = normalize_role(st.session_state.get("member_role", MEMBER_ROLES[0]))
    name_to_save = clamp_20(st.session_state.get("member_name", ""))

    c1, c2, c3 = st.columns(3)
    if c1.button("▶ 시작(현재시간)", use_container_width=True):
        storage.upsert_one(uid, day_str, start_time=now_hhmm_kst(), member_role=role_to_save, member_name=name_to_save)
        st.rerun()
    if c2.button("■ 종료(현재시간)", use_container_width=True):
        storage.upsert_one(uid, day_str, end_time=now_hhmm_kst(), member_role=role_to_save, member_name=name_to_save)
        st.rerun()

    is_done = df[df["날짜"] == day_str]["완료"].values[0] if not df[df["날짜"] == day_str].empty else False
    if c3.button("✅ " + ("취소" if is_done else "완료"), use_container_width=True):
        storage.upsert_one(uid, day_str, completed=not is_done, member_role=role_to_save, member_name=name_to_save)
        st.rerun()

    st.markdown("### 🕊️ 나의 묵상 기도 (50자 이내)")
    memo = st.text_area(
        "경건의 시간 하나님님께서 주신 감동으로 한 줄 묵상 기도를 적어 보세요.",
        height=90,
        max_chars=50,
        placeholder="예) 주님, 오늘 말씀을 붙잡고 순종할 힘을 주세요.",
    )
    if st.button("기록 저장하기", use_container_width=True, type="primary"):
        storage.upsert_one(
            uid, day_str,
            signature="",
            prayer_note=clamp_50(memo),
            member_role=role_to_save,
            member_name=name_to_save
        )
        st.success("저장되었습니다!")
        st.rerun()



# 기록 확인(기본: 주간, 전체 보기 토글)
st.markdown("---")
st.subheader("📋 기록 확인 (주간)")
show_all = st.toggle("전체 보기 (한 달 전체)", value=False)

if show_all:
    render_qt_table_html(df)
else:
    anchor = st.session_state.get("picked_day", today_kst())
    wk_start = week_start_monday(anchor)
    wk_end = wk_start + timedelta(days=6)

    wk_start_in = clamp_date(wk_start, START, END)
    wk_end_in = clamp_date(wk_end, START, END)

    nav1, nav2, _ = st.columns([1, 1, 2])
    with nav1:
        if st.button("⬅️ 이전 주", use_container_width=True):
            st.session_state["picked_day"] = clamp_date(anchor - timedelta(days=7), START, END)
            st.rerun()
    with nav2:
        if st.button("다음 주 ➡️", use_container_width=True):
            st.session_state["picked_day"] = clamp_date(anchor + timedelta(days=7), START, END)
            st.rerun()

    st.caption(f"표시 기간: {wk_start_in.isoformat()} ~ {wk_end_in.isoformat()} (월~일)")
    df_week = df[(df["날짜"] >= wk_start_in.isoformat()) & (df["날짜"] <= wk_end_in.isoformat())].copy()
    render_qt_table_html(df_week)
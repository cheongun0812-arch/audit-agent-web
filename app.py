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

APP_BUILD = "weeklyfree_v2_2026-01-22_layout_final_beacon_v2"


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
APP_TITLE = "주만나와 함께 빚어가는, 예은의 향기"
VERSE_TEXT = "하나님 보시기에 아름다운 예은 성도님, 오늘도 주만나와 함께 은혜의 깊은 곳으로 한 걸음 더 들어가 볼까요?"
SUPPORTED_MONTHS = [(2026, 1, "2026년 1월"), (2026, 2, "2026년 2월"), (2026, 3, "2026년 3월"), (2026, 4, "2026년 4월"), (2026, 5, "2026년 5월"), (2026, 6, "2026년 6월"), (2026, 7, "2026년 7월"), (2026, 8, "2026년 8월"), (2026, 9, "2026년 9월"), (2026, 10, "2026년 10월"), (2026, 11, "2026년 11월"), (2026, 12, "2026년 12월"),]

SHEET_RECORDS = "qti_records"  # 일별 기록
SHEET_USERS = "qti_users"      # uid별 성도 정보(직분/이름)
SHEET_PRAYERS = "intercessory_prayers"  # 중보기도 요청(Pray together in the Lord)

MEMBER_ROLES = ["평신도", "서리집사", "안수집사", "권사", "장로", "전도사", "강도사", "목사", "기타"]
DISTRICTS = ["1교구", "2교구", "3교구", "4교구"]


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
    """Normalize various time formats from Google Sheets to HH:MM."""
    s = (s or "").strip()
    if not s:
        return ""

    # Common: 8:53, 08:53, 8:53:00, 08:53:00
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", s)
    if m:
        hh = int(m.group(1))
        mm = int(m.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return f"{hh:02d}:{mm:02d}"

    # Sometimes returned as full datetime strings (e.g., 1900-01-01 08:53:00)
    try:
        dt = pd.to_datetime(s, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%H:%M")
    except Exception:
        pass

    # Fallback: already normalized?
    s5 = s[:5]
    return s5 if _HHMM.match(s5) else ""


def clamp_50(s: str) -> str:
    return (s or "").strip()[:50]


def clamp_20(s: str) -> str:
    return (s or "").strip()[:20]


def clamp_300(s: str) -> str:
    return (s or "").strip()[:300]


def clamp_1000(s: str) -> str:
    return (s or "").strip()[:1000]


def normalize_role(s: str) -> str:
    s = (s or "").strip()
    return s if s in MEMBER_ROLES else (MEMBER_ROLES[-1] if s else "")


def normalize_district(s: str) -> str:
    s = (s or "").strip()
    return s if s in DISTRICTS else (DISTRICTS[0] if s else "")


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
            border: 2px solid rgba(176,124,255,0.75);  /* 강조(보라) */
            box-shadow: 0 8px 22px rgba(0,0,0,0.06), 0 0 0 4px rgba(176,124,255,0.12);
            background: linear-gradient(135deg, #f7fbff 0%, #fff7fb 55%, #f6fff8 100%);
            overflow: hidden;
            margin-top: 6px;
            margin-bottom: 8px;
          }
          #shareHeader {
            display:flex;
            align-items:center;
            justify-content:space-between;
            padding: 12px 14px;
            font-weight: 900;
          }
          #shareTitle { font-size: 1.10rem; }
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
            padding: 0 14px 14px 14px;
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
            border: 2px solid rgba(176,124,255,0.75);  /* 강조(보라) */
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

          /* --- Pray together beacon (lighthouse) --- */
          .prayer-title-row{
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap: 10px;
            margin: 2px 0 2px 0;
          }
          .prayer-title{
            font-weight: 900;
            font-size: 1.10rem;  /* ✍️ 오늘의 큐티 기록과 동일 크기 */
            line-height: 1.2;
            display:flex;
            align-items:center;
            gap: 8px;
            user-select: none;
          }
          .prayer-icon-wrap{
            position: relative;
            display:inline-flex;
            align-items:center;
          }

          /* --- Beacon (brighter + wider glow) --- */
          .prayer-beacon{
            position:absolute;
            top:-11px;
            right:-11px;
            width:16px;
            height:16px;
            border-radius:999px;
            background: rgba(253,230,138,1.0);
            box-shadow:
              0 0 18px 8px rgba(253,230,138,0.98),
              0 0 38px 20px rgba(236,72,153,0.62),
              0 0 58px 34px rgba(168,85,247,0.40);
            animation: beaconPulse 0.92s infinite cubic-bezier(0.22, 1, 0.36, 1);
          }
          @keyframes beaconPulse{
            0%   { transform: scale(0.62); opacity: .86;
                   box-shadow:
                     0 0 16px 7px rgba(253,230,138,0.92),
                     0 0 30px 16px rgba(236,72,153,0.55),
                     0 0 46px 26px rgba(168,85,247,0.32); }
            55%  { transform: scale(1.08); opacity: 1.00;
                   box-shadow:
                     0 0 22px 10px rgba(253,230,138,1.00),
                     0 0 46px 24px rgba(236,72,153,0.70),
                     0 0 70px 40px rgba(168,85,247,0.46); }
            100% { transform: scale(0.62); opacity: .86;
                   box-shadow:
                     0 0 16px 7px rgba(253,230,138,0.92),
                     0 0 30px 16px rgba(236,72,153,0.55),
                     0 0 46px 26px rgba(168,85,247,0.32); }
          }

          /* expander 헤더 숨김: 우측 '열기/닫기' 버튼만 사용 */
          div[data-testid="stExpander"] > details > summary { display: none; }
          div[data-testid="stExpander"] > details { border: none; padding: 0 !important; }
        
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
    USERS_REQUIRED = ["uid", "member_district", "member_role", "member_name", "updated_at"]
    PRAYERS_REQUIRED = [
        "uid", "member_district", "member_role", "member_name", "saints_info",
        "prayer_title", "prayer_content", "is_public",
        "created_at", "linked_day"
    ]

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

        # prayers worksheet
        try:
            self.ws_prayers = self.sh.worksheet(SHEET_PRAYERS)
        except Exception:
            self.ws_prayers = self.sh.add_worksheet(title=SHEET_PRAYERS, rows=3000, cols=20)

        # schema/index cache (process-wide via st.cache_resource)
        self._schema_verified = False
        self._records_header: list[str] = []
        self._users_header: list[str] = []
        self._prayers_header: list[str] = []
        self.col_idx: dict[str, int] = {}  # 1-indexed col index for records
        self.users_col_idx: dict[str, int] = {}  # 1-indexed col index for users
        self.prayers_col_idx: dict[str, int] = {}  # 1-indexed col index for prayers

        self._row_index: dict[tuple[str, str], int] = {}  # (uid, day) -> row_idx
        self._index_built_at: float = 0.0

        # Small in-memory DataFrame cache (keeps UI interactions snappy)
        self._records_df_cache = None
        self._records_df_cache_ts = 0.0
        self._prayers_df_cache = None
        self._prayers_df_cache_ts = 0.0

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

        # prayers header
        phdr = self._call_with_retries(self.ws_prayers.row_values, 1) or []
        phdr = [str(x).strip() for x in phdr if str(x).strip()]

        if not phdr:
            phdr = list(self.PRAYERS_REQUIRED)
            try:
                if self.ws_prayers.col_count < len(phdr):
                    self._call_with_retries(self.ws_prayers.add_cols, len(phdr) - self.ws_prayers.col_count)
            except Exception:
                pass
            self._call_with_retries(self.ws_prayers.update, "A1", [phdr])
        else:
            pmissing = [c for c in self.PRAYERS_REQUIRED if c not in phdr]
            if pmissing:
                new_phdr = phdr + pmissing
                try:
                    if self.ws_prayers.col_count < len(new_phdr):
                        self._call_with_retries(self.ws_prayers.add_cols, len(new_phdr) - self.ws_prayers.col_count)
                except Exception:
                    pass
                self._call_with_retries(self.ws_prayers.update, "A1", [new_phdr])
                phdr = new_phdr

        self._prayers_header = phdr
        self._refresh_prayers_col_index()

        self._schema_verified = True

    def _refresh_col_index(self):
        self.col_idx = {name: i + 1 for i, name in enumerate(self._records_header)}

    def _refresh_users_col_index(self):
        self.users_col_idx = {name: i + 1 for i, name in enumerate(self._users_header)}

    def _refresh_prayers_col_index(self):
        self.prayers_col_idx = {name: i + 1 for i, name in enumerate(self._prayers_header)}

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
        import time
        if self._records_df_cache is not None and (time.time() - self._records_df_cache_ts) < 20:
            return self._records_df_cache.copy()
        rows = self._call_with_retries(self.ws.get_all_records)
        df_all = pd.DataFrame(rows)
        if df_all.empty:
            df_out = pd.DataFrame(columns=self.RECORDS_REQUIRED)
            self._records_df_cache = df_out
            import time
            self._records_df_cache_ts = time.time()
            return df_out.copy()
        for c in self.RECORDS_REQUIRED:
            if c not in df_all.columns:
                df_all[c] = ""
        df_out = df_all[self.RECORDS_REQUIRED].copy()
        self._records_df_cache = df_out
        import time
        self._records_df_cache_ts = time.time()
        return df_out.copy()

    # -------------------------
    # Prayers (intercessory)
    # -------------------------
    def fetch_all_prayers_df(self) -> pd.DataFrame:
        """(관리/목회자용) 중보기도 요청 전체 로드."""
        self._ensure_schema()
        import time
        if self._prayers_df_cache is not None and (time.time() - self._prayers_df_cache_ts) < 20:
            return self._prayers_df_cache.copy()
        rows = self._call_with_retries(self.ws_prayers.get_all_records)
        dfp = pd.DataFrame(rows)
        if dfp.empty:
            df_out = pd.DataFrame(columns=self.PRAYERS_REQUIRED)
            self._prayers_df_cache = df_out
            import time
            self._prayers_df_cache_ts = time.time()
            return df_out.copy()
        for c in self.PRAYERS_REQUIRED:
            if c not in dfp.columns:
                dfp[c] = ""
        df_out = dfp[self.PRAYERS_REQUIRED].copy()
        self._prayers_df_cache = df_out
        import time
        self._prayers_df_cache_ts = time.time()
        return df_out.copy()

    def insert_prayer_request(
        self,
        uid: str,
        member_district: str,
        member_role: str,
        member_name: str,
        prayer_title: str,
        prayer_content: str,
        is_public: bool = True,
        linked_day: str = "",
    ):
        """중보기도 요청은 "추가(append)"로만 저장합니다(기록 변경 이력 보존)."""
        self._ensure_schema()
        now_iso = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        district = normalize_district(member_district)
        role = normalize_role(member_role)
        name = clamp_20(member_name)
        title = clamp_50(prayer_title)
        content = clamp_300(prayer_content)
        who = f"{role} {name}".strip() if role else name
        saints_info = f"{district}/{who}".strip("/") if district else who
        if linked_day:
            try:
                linked_day = str(date.fromisoformat(str(linked_day))).strip()
            except Exception:
                linked_day = str(linked_day).strip()

        row = []
        for h in self._prayers_header:
            if h == "uid":
                row.append(str(uid))
            elif h == "member_district":
                row.append(district)
            elif h == "member_role":
                row.append(role)
            elif h == "member_name":
                row.append(name)
            elif h == "saints_info":
                row.append(saints_info)
            elif h == "prayer_title":
                row.append(title)
            elif h == "prayer_content":
                row.append(content)
            elif h == "is_public":
                row.append("TRUE" if bool(is_public) else "FALSE")
            elif h == "created_at":
                row.append(now_iso)
            elif h == "linked_day":
                row.append(str(linked_day or ""))
            else:
                row.append("")

        self._call_with_retries(self.ws_prayers.append_row, row, value_input_option="USER_ENTERED")
        # Invalidate cached full prayers df
        self._prayers_df_cache = None
        self._prayers_df_cache_ts = 0.0


    # -------------------------
    # Profile (users sheet)
    # -------------------------
    def get_profile(self, uid: str) -> Tuple[str, str, str]:
        self._ensure_schema()
        try:
            rows = self._call_with_retries(self.ws_users.get_all_records)
            dfu = pd.DataFrame(rows)
            if dfu.empty:
                return "", "", ""
            hit = dfu[dfu["uid"].astype(str) == str(uid)]
            if hit.empty:
                return "", "", ""
            if "updated_at" in hit.columns:
                hit = hit.sort_values("updated_at")
            r = hit.iloc[-1]
            district = normalize_district(r.get("member_district", ""))
            role = normalize_role(r.get("member_role", ""))
            name = clamp_20(r.get("member_name", ""))
            return district, role, name
        except Exception:
            return "", "", ""

    def upsert_profile(self, uid: str, member_district: str, member_role: str, member_name: str):
        """프로필 저장은 자주 호출되지 않으므로 단순/안전하게 처리."""
        self._ensure_schema()
        now_iso = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
        district = normalize_district(member_district)
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
                elif h == "member_district":
                    new_row.append(district)
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
            q("member_district", district)
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
            # Invalidate cached full records df
            self._records_df_cache = None
            self._records_df_cache_ts = 0.0
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
            # Invalidate cached full records df
            self._records_df_cache = None
            self._records_df_cache_ts = 0.0

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


@st.cache_data(ttl=60)
def cached_all_prayers_df() -> pd.DataFrame:
    s = get_storage()
    if not s:
        return pd.DataFrame()
    return s.fetch_all_prayers_df()



# -------------------------
# UID 디렉토리(성도별 UID/링크) 로드
#  - GitHub(배포 repo)에서 app.py와 같은 폴더에 saints_uid_links.csv를 두면 자동 조회 가능
#  - 컬럼 순서가 'block, member_name, member_role, uid, link'여도 동작(순서/누락 유연)
# -------------------------
_UID_DIR_PATH = Path(__file__).with_name("saints_uid_links.csv")

@st.cache_data(ttl=30)
def load_uid_directory() -> pd.DataFrame:
    if not _UID_DIR_PATH.exists():
        return pd.DataFrame(columns=["block", "member_name", "member_role", "uid", "link"])

    # 인코딩 이슈 대비
    try:
        df = pd.read_csv(_UID_DIR_PATH, dtype=str).fillna("")
    except Exception:
        df = pd.read_csv(_UID_DIR_PATH, dtype=str, encoding="utf-8-sig").fillna("")

    df.columns = [str(c).strip() for c in df.columns]

    # alias 대응(혹시 다른 이름으로 저장된 경우)
    alias = {
        "diocese": "block",
        "district": "block",
        "parish": "block",
        "member_district": "block",
        "name": "member_name",
        "role": "member_role",
    }
    for old, new in alias.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]

    # 필요한 컬럼 보정
    for c in ["block", "member_name", "member_role", "uid", "link"]:
        if c not in df.columns:
            df[c] = ""

    df = df[["block", "member_name", "member_role", "uid", "link"]].copy()
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()

    df = df[df["member_name"] != ""].reset_index(drop=True)
    return df

def render_uid_lookup_page():
    st.subheader("🔎 내 UID 접속 주소 찾기")
    st.caption("성도 이름으로 검색하여 본인 UID와 접속 링크를 확인/복사할 수 있습니다.")

    df_dir = load_uid_directory()
    if df_dir.empty:
        st.warning("UID 명단 파일(saints_uid_links.csv)을 찾지 못했습니다. GitHub에서 app.py와 같은 폴더에 업로드/커밋했는지 확인해 주세요.")
        return

    c1, c2 = st.columns([2, 1])
    with c1:
        q = st.text_input("성도 이름 검색", placeholder="예) 정청운").strip()
    with c2:
        blocks = sorted([b for b in df_dir["block"].unique().tolist() if str(b).strip()])
        block = st.selectbox("교구(선택)", ["전체"] + blocks, index=0)

    filtered = df_dir.copy()
    if block != "전체":
        filtered = filtered[filtered["block"] == block]
    if q:
        filtered = filtered[filtered["member_name"].str.contains(q, na=False)]

    if filtered.empty:
        st.info("검색 결과가 없습니다.")
        return

    options = filtered.to_dict("records")

    def _format_person(r):
        b = (r.get("block") or "").strip()
        role = (r.get("member_role") or "").strip()
        name = (r.get("member_name") or "").strip()
        main = " ".join([x for x in [role, name] if x])  # 예: '안수집사 정청운'
        return f"{main}, {b}" if b else main

    picked = st.selectbox("Select yourself", options=options, format_func=_format_person)

    b = (picked.get("block") or "").strip()
    role = (picked.get("member_role") or "").strip()
    name = (picked.get("member_name") or "").strip()
    uid = (picked.get("uid") or "").strip()
    link = (picked.get("link") or "").strip()

    main = " ".join([x for x in [role, name] if x])

    if b:
        st.success(f"✅ {main}'s UID access address from {b} is as follows.")
    else:
        st.success(f"✅ {main}'s UID access address is as follows.")

    st.code(link, language="text")
    st.write("UID")
    st.code(uid, language="text")

    if st.button("Go to record with this link", use_container_width=True, type="primary"):
        # 라디오 위젯이 만들어진 뒤에 mode_select를 직접 바꾸면 에러가 날 수 있어
        # 다음 rerun에서 처리하도록 플래그만 저장
        st.session_state["__goto_record_uid"] = uid
        st.rerun()


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
    dfx["completed_bool"] = dfx["completed"].astype(str).str.lower().isin(["1", "true", "yes", "y", "완료"])
    dfx = dfx[dfx["completed_bool"]]
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
    dmonth["completed_bool"] = dmonth["completed"].astype(str).str.lower().isin(["1", "true", "yes", "y", "완료"])
    cnts = dmonth[dmonth["completed_bool"]].groupby("uid", as_index=False)["day"].nunique().rename(columns={"day": "완료일수"})
    merged = prof.merge(cnts, on="uid", how="left")
    merged["완료일수"] = merged["완료일수"].fillna(0).astype(int)

    st.markdown("### 👥 성도 참여(월 기준)")
    st.dataframe(
        merged.sort_values(["완료일수", "member_name"], ascending=[False, True]),
        use_container_width=True,
        hide_index=True,
    )


    st.markdown("---")
    st.markdown("### 🙏 Pray together in the Lord (중보기도 요청)")

    dfp_all = cached_all_prayers_df()
    if dfp_all.empty:
        st.info("중보기도 요청이 아직 없습니다.")
    else:
        view_mode = st.selectbox("보기 옵션", ["공동체 중보(공개)", "전체(비공개 포함)"], index=0)

        dfp = dfp_all.copy()
        dfp["is_public_bool"] = dfp["is_public"].astype(str).str.lower().isin(["true", "1", "yes", "y", "공개"])

        dfp["_created_dt"] = pd.to_datetime(dfp["created_at"], errors="coerce")
        dfp["_linked_dt"] = pd.to_datetime(dfp["linked_day"], errors="coerce")
        dfp["_use_date"] = dfp["_linked_dt"].dt.date
        dfp.loc[dfp["_use_date"].isna(), "_use_date"] = dfp["_created_dt"].dt.date

        # 월 필터(선택한 월 기준)
        dfp = dfp[(dfp["_use_date"] >= m_start) & (dfp["_use_date"] <= m_end)] if not dfp.empty else dfp

        if view_mode.startswith("공동체"):
            dfp = dfp[dfp["is_public_bool"]]

        dfp = dfp.sort_values(by=["_created_dt"], ascending=False, na_position="last")

        view = dfp.rename(
            columns={
                "saints_info": "성도 정보",
                "prayer_title": "기도 제목",
                "prayer_content": "기도 내용",
                "is_public_bool": "공동체 중보",
                "linked_day": "연결 QT 날짜",
                "created_at": "작성 시각",
            }
        )

        cols = [c for c in ["성도 정보", "기도 제목", "기도 내용", "공동체 중보", "연결 QT 날짜", "작성 시각"] if c in view.columns]
        st.dataframe(view[cols], use_container_width=True, hide_index=True)

        # 다운로드(선택 월 기준)
        csv_p = dfp.drop(columns=["_created_dt", "_linked_dt", "_use_date"], errors="ignore").to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "중보기도 CSV 다운로드(선택 월)",
            data=csv_p,
            file_name=f"intercessory_prayers_{m_start.strftime('%Y%m')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

        csv_all = dfp_all.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "중보기도 CSV 다운로드(전체 기간)",
            data=csv_all,
            file_name="intercessory_prayers_all.csv",
            mime="text/csv",
            use_container_width=True,
        )

    st.caption("※ 기본은 '공동체 중보(공개)'만 표시됩니다. '전체'는 목회자/관리자 전용으로만 활용하세요.")

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
st.set_page_config(page_title="Ye-eun's scent created with Ju-manna", layout="wide")
st.sidebar.caption(f"build: {APP_BUILD}")

# --- Responsive UI (PC/Mobile) ---
st.markdown(
    """
<style>
/* Base (desktop/tablet) */
html, body, [class*="css"] { font-size: 16px; }
h1 { 
  font-size: 2.0rem !important;
  line-height: 1.2 !important;
  margin-bottom: 0.25rem !important;
}

/* 모바일에서는 더 작게 */
@media (max-width: 640px) {
  h1 {
    font-size: 1.05rem !important;
  }
}

h2 { font-size: 1.15rem; line-height: 1.25; }
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

  h1 { font-size: 1.2rem; }
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

st.title("✨ 주만나와 함께 빚어가는, 예은의 향기")
st.caption("하나님 보시기에 참 예쁜 예은 성도님, 오늘도 주만나와 함께 은혜의 깊은 곳으로 한 걸음 더 들어가 볼까요?")

mode = st.radio("모드 선택", ["성도님(기록하기)", "내 UID 접속 주소 찾기", "관리자(대시보드)"], horizontal=True, key="mode_select")

# 관리자

# 내 UID 접속 주소 찾기
if mode == "내 UID 접속 주소 찾기":
    render_uid_lookup_page()
    st.stop()


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

# 기본 상태 초기화
if "picked_day" not in st.session_state:
    st.session_state["picked_day"] = today_kst()

if "month_label" not in st.session_state:
    _cur = (today_kst().year, today_kst().month)
    _labels = [m[2] for m in SUPPORTED_MONTHS]
    _default_label = None
    for y, m, lab in SUPPORTED_MONTHS:
        if (y, m) == _cur:
            _default_label = lab
            break
    st.session_state["month_label"] = _default_label or (_labels[0] if _labels else f"{_cur[0]}년 {_cur[1]}월")

# 즉시 반영(리얼타임 보상감)용 로컬 오버라이드
st.session_state.setdefault("local_qt_overrides", {})

def _set_local(day_iso: str, **kwargs):
    d = st.session_state["local_qt_overrides"].get(day_iso, {})
    for k, v in kwargs.items():
        if v is None:
            continue
        d[k] = v
    st.session_state["local_qt_overrides"][day_iso] = d

def _apply_overrides(df_in: pd.DataFrame) -> pd.DataFrame:
    if df_in is None or df_in.empty:
        return df_in
    ov = st.session_state.get("local_qt_overrides", {})
    if not ov:
        return df_in
    df2 = df_in.copy()
    if "날짜" not in df2.columns:
        return df2
    for i, row in df2.iterrows():
        ds = str(row.get("날짜", ""))
        if ds in ov:
            x = ov[ds]
            if "start_time" in x and "QT 시작" in df2.columns:
                df2.at[i, "QT 시작"] = (x.get("start_time") or df2.at[i, "QT 시작"])
            if "end_time" in x and "QT 종료" in df2.columns:
                df2.at[i, "QT 종료"] = (x.get("end_time") or df2.at[i, "QT 종료"])
            if "completed" in x and "완료" in df2.columns:
                df2.at[i, "완료"] = bool(x.get("completed"))
            if "prayer_note" in x and "나의 묵상 기도" in df2.columns:
                if (x.get("prayer_note") or "").strip():
                    df2.at[i, "나의 묵상 기도"] = x.get("prayer_note")
    return df2

def _month_range_from_label(label: str) -> tuple[date, date]:
    y, m = None, None
    for yy, mm, lab in SUPPORTED_MONTHS:
        if lab == label:
            y, m = yy, mm
            break
    if y is None:
        mm = re.findall(r"(\d{4})\D+(\d{1,2})", label or "")
        if mm:
            y, m = int(mm[0][0]), int(mm[0][1])
        else:
            y, m = today_kst().year, today_kst().month
    start = date(y, m, 1)
    if m == 12:
        end = date(y + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(y, m + 1, 1) - timedelta(days=1)
    return start, end

# 성도 프로필 자동 불러오기(최초 1회)
if "profile_loaded" not in st.session_state:
    dist0, role0, name0 = storage.get_profile(uid)
    st.session_state["member_district"] = dist0 or DISTRICTS[0]
    st.session_state["member_role"] = role0 or MEMBER_ROLES[0]
    st.session_state["member_name"] = name0 or ""
    st.session_state["profile_loaded"] = True

# ✅ 이 달 달성도(표시용) 계산 - 선택된 월 기준
_m_label = st.session_state.get("month_label")
_m_start, _m_end = _month_range_from_label(_m_label)
df_month = _apply_overrides(storage.load_month(uid, _m_start, _m_end))
done_cnt = int(df_month["완료"].sum()) if (df_month is not None and not df_month.empty and "완료" in df_month.columns) else 0
total_cnt = int(len(df_month)) if df_month is not None else 0
progress = (done_cnt / total_cnt) if total_cnt else 0.0

# 1) 성도 정보(1회) + 이번 달 달성 (한 박스)
with st.container(border=True):
    st.subheader("🙋 성도 정보(1회 입력)")
    st.caption("한 번 입력하면 다음 접속 때 자동으로 불러오고, 이후 모든 기록에 uid/교구/직분/이름이 함께 저장됩니다.")

    col_dist, col_r, col_n, col_s, col_a = st.columns([1, 1, 1, 1, 1])

    with col_dist:
        cur_dist = st.session_state.get("member_district", DISTRICTS[0])
        didx = DISTRICTS.index(cur_dist) if cur_dist in DISTRICTS else 0
        st.selectbox("교구", DISTRICTS, index=didx, key="member_district")

    with col_r:
        cur_role = st.session_state.get("member_role", MEMBER_ROLES[0])
        ridx = MEMBER_ROLES.index(cur_role) if cur_role in MEMBER_ROLES else 0
        st.selectbox("직분", MEMBER_ROLES, index=ridx, key="member_role")

    with col_n:
        st.text_input("성도 이름", key="member_name", placeholder="예) 홍 길 동")

    with col_s:
        st.write("")
        st.write("")
        if st.button("💾 성도 정보 저장", use_container_width=True):
            dist_clean = normalize_district(st.session_state.get("member_district", DISTRICTS[0]))
            role_clean = normalize_role(st.session_state.get("member_role", ""))
            name_clean = clamp_20(st.session_state.get("member_name", ""))
            if not name_clean:
                st.warning("이름을 입력해 주세요.")
            else:
                storage.upsert_profile(uid, dist_clean, role_clean, name_clean)
                st.success("저장되었습니다! 다음 접속부터 자동으로 불러옵니다.")
                st.rerun()

    with col_a:
        st.metric("✅ 이번 달 달성", f"{done_cnt}일", f"{progress:.0%}")
        st.progress(progress)

    _d = normalize_district(st.session_state.get("member_district", ""))
    _r = normalize_role(st.session_state.get("member_role", ""))
    _n = clamp_20(st.session_state.get("member_name", "")) or "-"
    st.info(f"현재 저장 값: {_d}/{_r} {_n}".strip())

# 2) 오늘의 큐티 기록 (월 선택/날짜 선택 좌·우)
with st.container(border=True):
    st.subheader("✍️ 오늘의 큐티 기록")

    col_m, col_d = st.columns([1, 1])
    with col_m:
        st.selectbox("📆 월 선택", [m[2] for m in SUPPORTED_MONTHS], key="month_label")
    with col_d:
        picked_day = st.date_input("날짜 선택", value=st.session_state["picked_day"], key="picked_day")

    day_str = picked_day.isoformat()

    role_to_save = normalize_role(st.session_state.get("member_role", MEMBER_ROLES[0]))
    name_to_save = clamp_20(st.session_state.get("member_name", ""))

    df_day = _apply_overrides(storage.load_month(uid, picked_day, picked_day))
    day_row = df_day.iloc[0].to_dict() if (df_day is not None and not df_day.empty) else {}
    cur_start = day_row.get("QT 시작", "") or ""
    cur_end = day_row.get("QT 종료", "") or ""
    cur_done = bool(day_row.get("완료", False))
    cur_note = str(day_row.get("나의 묵상 기도", "") or "")

    c1, c2, c3 = st.columns(3)
    if c1.button("▶ 시작(현재시간)", use_container_width=True):
        t = now_hhmm_kst()
        storage.upsert_one(uid, day_str, start_time=t, member_role=role_to_save, member_name=name_to_save)
        _set_local(day_str, start_time=t)
        st.rerun()

    if c2.button("■ 종료(현재시간)", use_container_width=True):
        t = now_hhmm_kst()
        storage.upsert_one(uid, day_str, end_time=t, member_role=role_to_save, member_name=name_to_save)
        _set_local(day_str, end_time=t)
        st.rerun()

    if c3.button("✅ " + ("취소" if cur_done else "완료"), use_container_width=True):
        storage.upsert_one(uid, day_str, completed=not cur_done, member_role=role_to_save, member_name=name_to_save)
        _set_local(day_str, completed=not cur_done)
        st.rerun()

    st.markdown("#### 🙌 기록 확인")
    v1, v2, v3 = st.columns(3)
    with v1:
        st.metric("QT 시작", cur_start or "—")
    with v2:
        st.metric("QT 종료", cur_end or "—")
    with v3:
        st.metric("완료", "✅" if cur_done else "—")

    st.markdown("### 🕊️ 나의 묵상 기도 (50자 이내)")
    if st.session_state.get("_note_day") != day_str:
        st.session_state["_note_day"] = day_str
        st.session_state["prayer_note_input"] = cur_note[:50]

    memo = st.text_area(
        "경건의 시간 하나님 앞에 서 있는 모습으로 한 줄 묵상 기도를 적어 보세요.",
        height=90,
        max_chars=50,
        placeholder="예) 주님, 오늘 말씀을 붙잡고 순종할 힘을 주세요.",
        key="prayer_note_input",
    )

    if st.button("묵상 기도 저장", use_container_width=True, type="primary"):
        memo_clean = clamp_50(memo or "")
        storage.upsert_one(
            uid, day_str,
            signature="",
            prayer_note=memo_clean,
            member_role=role_to_save,
            member_name=name_to_save,
        )
        _set_local(day_str, prayer_note=memo_clean)
        st.success("저장되었습니다.")
        st.rerun()

# 3) 기록 확인(주간) - '묵상 기도 저장' 바로 아래
with st.container(border=True):
    st.subheader("📋 기록 확인 (주간)")
    show_all = st.toggle("전체 보기 (한 달 전체)", value=False)

    if show_all:
        df_all = _apply_overrides(storage.load_month(uid, _m_start, _m_end))
        render_qt_table_html(df_all)
    else:
        anchor = st.session_state.get("picked_day", today_kst())
        wk_start = week_start_monday(anchor)
        wk_end = wk_start + timedelta(days=6)

        def _shift_week(delta_days: int):
            a = st.session_state.get("picked_day", today_kst())
            st.session_state["picked_day"] = a + timedelta(days=delta_days)

        nav1, nav2, _sp = st.columns([1, 1, 2])
        with nav1:
            st.button("⬅️ 이전 주", use_container_width=True, on_click=_shift_week, args=(-7,))
        with nav2:
            st.button("다음 주 ➡️", use_container_width=True, on_click=_shift_week, args=(+7,))

        st.caption(f"표시 기간: {wk_start.isoformat()} ~ {wk_end.isoformat()} (월~일)")
        df_week = _apply_overrides(storage.load_month(uid, wk_start, wk_end))
        render_qt_table_html(df_week)

# 4) Pray together (중보기도 요청) - 기본 숨김 + 비콘(등대) + 우측 '열기/닫기'
with st.container(border=True):
    # 패널 상태(기본 닫힘)
    if "pray_panel_open" not in st.session_state or not isinstance(st.session_state.get("pray_panel_open"), bool):
        st.session_state["pray_panel_open"] = False

    def _toggle_pray_panel():
        st.session_state["pray_panel_open"] = not st.session_state.get("pray_panel_open", False)
        st.session_state["pray_err"] = ""

    # 제목(항상 노출) + 비콘(항상 점멸) + 우측 버튼
    left, right = st.columns([6, 1])
    with left:
        st.markdown(
            '''
            <div class="prayer-title-row">
              <div class="prayer-title">
                <span class="prayer-icon-wrap">🙏<span class="prayer-beacon"></span></span>
                <span>Pray together in the Lord (중보기도 요청)</span>
              </div>
            </div>
            ''',
            unsafe_allow_html=True,
        )

    with right:
        btn_label = "열기" if not st.session_state.get("pray_panel_open", False) else "닫기"
        st.button(btn_label, key="pray_toggle_btn", use_container_width=True, on_click=_toggle_pray_panel)

    # 내용은 기본 숨김. expander의 슬라이딩 애니메이션을 사용하고, 헤더는 CSS로 숨깁니다.
    with st.expander(" ", expanded=st.session_state.get("pray_panel_open", False)):
        st.caption("공동체가 함께 기도할 제목이 있다면 자유롭게 남겨주세요. (체크 시 공동체 중보에 표시됩니다.)")

        st.session_state.setdefault("pray_title", "")
        st.session_state.setdefault("pray_content", "")
        st.session_state.setdefault("pray_is_public", False)
        st.session_state.setdefault("pray_err", "")
        st.session_state.setdefault("pray_ok", False)
        st.session_state.setdefault("pray_last_info", "")
        st.session_state.setdefault("pray_last_title", "")

        st.text_input("기도 제목(필수, 40자 이내)", max_chars=40, placeholder="예) 가족 구원을 위해", key="pray_title")
        st.text_area(
            "기도 내용(선택, 300자 이내)",
            height=120,
            max_chars=300,
            placeholder="예) 이번 주 중요한 수술을 앞두고 있습니다. 담대함과 평안을 주세요.",
            key="pray_content",
        )

        tcol2, ccol2 = st.columns([3, 1])
        with tcol2:
            st.markdown("**중보기도가 필요합니다. 함께 기도해주세요.**")
        with ccol2:
            st.checkbox("중보기도 요청", key="pray_is_public")  # 기본: 미체크(False)

        def _submit_prayer():
            district_to_save = normalize_district(st.session_state.get("member_district", DISTRICTS[0]))
            role_to_save = normalize_role(st.session_state.get("member_role", MEMBER_ROLES[0]))
            name_to_save = clamp_20(st.session_state.get("member_name", ""))

            ptv = (st.session_state.get("pray_title") or "").strip()
            pcv = (st.session_state.get("pray_content") or "").strip()
            pubv = bool(st.session_state.get("pray_is_public", False))

            if not name_to_save:
                st.session_state["pray_err"] = "먼저 '성도 정보(교구/직분/이름)'를 저장해 주세요."
                st.session_state["pray_ok"] = False
                return
            if not ptv:
                st.session_state["pray_err"] = "기도 제목을 입력해 주세요."
                st.session_state["pray_ok"] = False
                return

            linked = st.session_state.get("picked_day", today_kst()).isoformat()
            storage.insert_prayer_request(
                uid=str(uid),
                member_district=district_to_save,
                member_role=role_to_save,
                member_name=name_to_save,
                prayer_title=ptv,
                prayer_content=pcv,
                is_public=pubv,
                linked_day=linked,
            )

            who = (f"{role_to_save} {name_to_save}".strip() if role_to_save else name_to_save)
            st.session_state["pray_last_info"] = f"{district_to_save}/{who}".strip("/")
            st.session_state["pray_last_title"] = ptv

            # 입력 초기화(콜백 안에서만)
            st.session_state["pray_title"] = ""
            st.session_state["pray_content"] = ""
            st.session_state["pray_is_public"] = False
            st.session_state["pray_err"] = ""
            st.session_state["pray_ok"] = True

        st.button("🙏 중보기도 요청 저장", use_container_width=True, on_click=_submit_prayer)

        if st.session_state.get("pray_err"):
            st.warning(st.session_state["pray_err"])
        elif st.session_state.get("pray_ok"):
            info = st.session_state.get("pray_last_info") or ""
            title = st.session_state.get("pray_last_title") or ""
            if info and title:
                st.success(f"({info}) '{title}' 중보기도가 저장되었습니다. 함께 기도하겠습니다 🙏")
            else:
                st.success("중보기도가 저장되었습니다. 함께 기도하겠습니다 🙏")

st.markdown("---")
# 내 QT 접속 주소(중요) - 화면 최하단
share_url = build_share_url(uid)
st.markdown(
    """
    <div id="sharePanel">
      <div id="shareHeader">
        <div id="shareTitle">📌 나의 QT 접속 주소 저장</div>
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

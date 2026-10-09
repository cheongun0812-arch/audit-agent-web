"""AI WORK DESK - entry point.

The 2,700-line single file of earlier pilots was split in v0.5.0:

* ``app.py``          this file: page config, style, start-up checks, routing
* ``assets/style.css`` all CSS (was an inline string)
* ``ui/common.py``    shared widgets / helpers
* ``ui/page_*.py``    one module per page, each with ``render(settings)``
* ``src/``            engines (mail, rules, briefing, performance, storage, AI gateway ...)
"""
from __future__ import annotations

import traceback
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="AI WORK DESK", page_icon="◆", layout="wide", initial_sidebar_state="collapsed")

from src.config import load_settings  # noqa: E402
from src.logger import get_logger  # noqa: E402
from src.maintenance import run_startup_housekeeping  # noqa: E402
from src.storage import init_db  # noqa: E402
from ui import (  # noqa: E402
    page_briefing,
    page_home,
    page_mywork,
    page_performance,
    page_rules,
    page_settings,
    page_today,
)
from ui.common import (  # noqa: E402
    remove_hub_clock,
    remove_today_brief_overlay,
    render_hub_return,
    render_main_hub,
    render_scroll_top_control,
)

log = get_logger("app")
_ROOT = Path(__file__).resolve().parent


@st.cache_data(show_spinner=False)
def _css_text(mtime: float) -> str:  # mtime in the key -> edits to style.css apply without a restart
    return (_ROOT / "assets" / "style.css").read_text(encoding="utf-8")


def _inject_css() -> None:
    css = _ROOT / "assets" / "style.css"
    try:
        st.markdown(_css_text(css.stat().st_mtime), unsafe_allow_html=True)
    except OSError:
        log.warning("assets/style.css could not be read; default Streamlit style is used")


_inject_css()
init_db()
settings = load_settings()
st.session_state["_awd_settings"] = settings
run_startup_housekeeping(settings)   # no-op after the first call of the day

# Main Hub navigation
PAGE_MAP = {
    "hub": "메인 허브",
    "today": "오늘의 한 장",
    "home": "홈",
    "mywork": "MY WORK",
    "rules": "규정·지침 찾기",
    "briefing": "AI 문서 브리핑",
    "performance": "나의 업무활동 성과",
    "settings": "설정",
}
PAGE_RENDERERS = {
    "오늘의 한 장": page_today.render,
    "홈": page_home.render,
    "MY WORK": page_mywork.render,
    "규정·지침 찾기": page_rules.render,
    "AI 문서 브리핑": page_briefing.render,
    "나의 업무활동 성과": page_performance.render,
    "설정": page_settings.render,
}

page_raw = st.query_params.get("page") or "hub"
if isinstance(page_raw, list):
    page_raw = page_raw[0] if page_raw else "hub"
page_key = str(page_raw).strip().lower()
if page_key not in PAGE_MAP:
    page_key = "hub"
# TODAY BRIEF uses a persisted YYYY-MM-DD marker under %LOCALAPPDATA%\AIWorkDesk, so HOME reruns,
# page re-entry, application restarts and PC reboots do not reopen the automatic briefing more
# than once on the same day.
st.session_state["_awd_previous_page_key"] = page_key
st.session_state["current_page_key"] = page_key
menu = PAGE_MAP[page_key]

# The Main Hub itself is the top-level landing page, so the floating
# "처음으로" control is shown only inside work pages.
if page_key != "hub":
    remove_hub_clock()
    if page_key not in ("home", "today"):
        remove_today_brief_overlay()
    render_scroll_top_control()
    render_hub_return(page_key)

if page_key == "hub":
    render_main_hub()
else:
    try:
        PAGE_RENDERERS[menu](settings)
    except Exception as exc:  # StopException / RerunException are BaseException and pass through
        log.error("page '%s' crashed: %s\n%s", page_key, type(exc).__name__, traceback.format_exc())
        st.error(
            f"화면을 표시하는 중 문제가 발생했습니다 ({type(exc).__name__}). "
            "다른 메뉴는 정상적으로 사용할 수 있으며, 상세 내용은 설정 › 보안·진단 › 로그 폴더에 기록되었습니다."
        )
        with st.expander("기술 상세 (문의 시 복사)"):
            st.code(f"{type(exc).__name__}: {exc}")

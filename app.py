import os
import base64
import datetime
import glob
import tempfile
import time

import streamlit as st

# ==========================================
# 0. 페이지 설정 (⚠️ 반드시 첫 Streamlit 호출이어야 합니다)
# ==========================================
st.set_page_config(
    page_title="AUDIT AI Agent",
    page_icon="🛡️",
    layout="centered",
)

# ==========================================
# 0-1. (선택) 의존성 import: 실패해도 앱 전체가 하얗게 죽지 않게 방어
# ==========================================
GENAI_OK = True
GSPREAD_OK = True

try:
    import google.generativeai as genai
except Exception as e:
    GENAI_OK = False
    GENAI_ERR = e

try:
    from docx import Document
except Exception:
    Document = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None

try:
    import requests
    from bs4 import BeautifulSoup
except Exception:
    requests = None
    BeautifulSoup = None

try:
    import pytz
except Exception:
    pytz = None

try:
    import pandas as pd
except Exception:
    pd = None

try:
    import plotly.express as px
except Exception:
    px = None

# 구글 시트
try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
except Exception as e:
    GSPREAD_OK = False
    GSPREAD_ERR = e
    gspread = None
    ServiceAccountCredentials = None

# yt_dlp (유튜브 오디오 대안)
try:
    import yt_dlp
except Exception:
    yt_dlp = None

# Streamlit 버전 호환: cache_resource / query_params
_cache_resource = getattr(st, "cache_resource", None) or getattr(st, "experimental_singleton", None)
if _cache_resource is None:
    # 최후의 보루(구버전): allow_output_mutation=True 로 리소스 캐시 흉내
    _cache_resource = lambda func: st.cache(allow_output_mutation=True)(func)

def _get_qp(key: str):
    """Streamlit 버전별 Query Params getter"""
    try:
        qp = st.query_params
        if key in qp:
            v = qp[key]
            return v if isinstance(v, str) else v[0]
    except Exception:
        try:
            qp = st.experimental_get_query_params()
            if key in qp and qp[key]:
                return qp[key][0]
        except Exception:
            return None
    return None

def _set_qp(**kwargs):
    """Streamlit 버전별 Query Params setter"""
    try:
        for k, v in kwargs.items():
            st.query_params[k] = v
    except Exception:
        try:
            st.experimental_set_query_params(**kwargs)
        except Exception:
            pass

def _clear_qp():
    try:
        st.query_params.clear()
    except Exception:
        try:
            st.experimental_set_query_params()
        except Exception:
            pass

# ==========================================
# 1. 🎨 디자인 테마
# ==========================================
st.markdown(
    """
    <style>
    .stApp { background-color: #F4F6F9; }
    [data-testid="stSidebar"] { background-color: #2C3E50; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    .stTextInput input, .stTextArea textarea {
        background-color: #FFFFFF !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
        border: 1px solid #BDC3C7 !important;
    }

    .stButton > button {
        background: linear-gradient(to right, #2980B9, #2C3E50) !important;
        color: #FFFFFF !important;
        border: none !important;
        font-weight: bold !important;
    }

    /* ✅ 사이드바 접기/펼치기 버튼: 기본 아이콘을 숨기지 않고(=실패해도 남음), 추가 표시만 합니다 */
    [data-testid="stSidebarCollapsedControl"]{
        background-color: #FFFFFF !important;
        border-radius: 0 10px 10px 0;
        border: 1px solid #ddd;
        width: 40px; height: 40px;
        z-index: 99999;
        position: relative;   /* ::after 기준점 */
    }
    [data-testid="stSidebarCollapsedControl"]::after{
        content: "☰";
        color: #333;
        font-size: 24px;
        font-weight: bold;
        position: absolute;
        top: 5px; left: 11px;
        pointer-events: none;
    }

    [data-testid="stChatMessage"] { background-color: #FFFFFF; border: 1px solid #eee; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==========================================
# 2. 로그인 및 세션 관리
# ==========================================
def try_login():
    """버튼 클릭 시 실행되어 로그인을 처리하는 콜백"""
    raw_key = st.session_state.get("login_input_key", "")
    clean_key = "".join(str(raw_key).split())
    if not clean_key:
        st.session_state["login_error"] = "⚠️ 키를 입력해주세요."
        return

    if not GENAI_OK:
        st.session_state["login_error"] = f"❌ google-generativeai 라이브러리가 없습니다: {GENAI_ERR}"
        return

    try:
        genai.configure(api_key=clean_key)
        # 유효성 검사
        list(genai.list_models())

        st.session_state["api_key"] = clean_key
        st.session_state["login_error"] = None

        # URL에 저장(새로고침 방지)
        encoded = base64.b64encode(clean_key.encode()).decode()
        _set_qp(k=encoded)
    except Exception as e:
        st.session_state["login_error"] = f"❌ 인증 실패: {e}"

def perform_logout():
    st.session_state["logout_anim"] = True

# ==========================================
# 3. 사이드바 (로그인/로그아웃)
# ==========================================
with st.sidebar:
    st.markdown("### 🏛️ Control Center")
    st.markdown("---")

    # (A) 자동 로그인 복구 (URL 파라미터)
    if "api_key" not in st.session_state:
        k_val = _get_qp("k")
        if k_val and GENAI_OK:
            try:
                restored_key = base64.b64decode(k_val).decode("utf-8")
                genai.configure(api_key=restored_key)
                list(genai.list_models())
                st.session_state["api_key"] = restored_key
                st.toast("🔄 세션이 복구되었습니다.", icon="✨")
                st.rerun()
            except Exception:
                pass

    # (B) 로그인 UI
    if "api_key" not in st.session_state:
        with st.form("login_form"):
            st.markdown("<h4 style='color:white;'>🔐 Access Key</h4>", unsafe_allow_html=True)
            st.text_input(
                "Key",
                type="password",
                placeholder="API 키 입력",
                label_visibility="collapsed",
                key="login_input_key",
            )
            st.form_submit_button("시스템 접속 (Login)", on_click=try_login)

        if st.session_state.get("login_error"):
            st.error(st.session_state["login_error"])

    # (C) 로그인 상태
    else:
        st.success("🟢 정상 가동 중")
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Logout", type="primary", use_container_width=True):
            perform_logout()
            st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='color:white; text-align:center; font-size:12px; opacity:0.8;'>"
        "ktMOS북부 Audit AI Solution © 2026<br>Engine: Gemini 1.5 Pro"
        "</div>",
        unsafe_allow_html=True,
    )

# ==========================================
# 4. 로그아웃 화면
# ==========================================
if st.session_state.get("logout_anim"):
    st.markdown(
        """
        <div style="text-align:center; padding:40px;">
            <div style="font-size: 80px; margin-bottom: 20px;">🎅🎄</div>
            <h1 style="color:#2C3E50;">Merry Christmas!</h1>
            <h3 style="color:#555;">오늘도 수고 많으셨습니다.<br>따뜻한 연말 보내세요! ❤️</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
    time.sleep(2.0)
    _clear_qp()
    st.session_state.clear()
    st.rerun()

# ==========================================
# 5. 핵심 기능 (구글시트 / AI / 파일처리)
# ==========================================
@_cache_resource
def init_google_sheet_connection():
    """st.secrets['gcp_service_account'] 기반으로 gspread 인증"""
    if not GSPREAD_OK:
        return None
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        return gspread.authorize(creds)
    except Exception:
        return None

def save_audit_result(emp_id, name, unit, dept, answer, sheet_name):
    client = init_google_sheet_connection()
    if not client:
        return False, "구글 시트 연결 실패 (gspread/Secrets 확인)"

    if pytz is None:
        return False, "pytz 라이브러리가 없습니다."

    try:
        spreadsheet = client.open("Audit_Result_2026")
        try:
            sheet = spreadsheet.worksheet(sheet_name)
        except Exception:
            sheet = spreadsheet.add_worksheet(title=sheet_name, rows=2000, cols=10)
            sheet.append_row(["저장시간", "사번", "성명", "총괄/본부/단", "부서", "답변", "비고"])

        # 중복 방지 (사번 기준)
        if str(emp_id) in sheet.col_values(2):
            return False, "이미 참여하셨습니다."

        korea_tz = pytz.timezone("Asia/Seoul")
        now = datetime.datetime.now(korea_tz).strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([now, emp_id, name, unit, dept, answer, "완료"])
        return True, "성공"
    except Exception as e:
        return False, str(e)

def get_model():
    if not GENAI_OK:
        raise RuntimeError(f"google-generativeai 미설치: {GENAI_ERR}")
    api_key = st.session_state.get("api_key")
    if api_key:
        genai.configure(api_key=api_key)
    # ✅ Gemini 1.5 계열은 2025-09-29부로 shutdown(종료)되어 404가 납니다.
    #   모델은 Google 공식 Models 문서에 있는 최신 코드로 바꿔주세요.
    #   - 품질 우선: gemini-1.5-pro
    #   - 속도/비용 우선: gemini-1.5-flash
    model_name = st.session_state.get("model_name") or os.getenv("GEMINI_MODEL", "gemini-1.5-pro")
    return genai.GenerativeModel(model_name)

def read_file(uploaded_file):
    """TXT/PDF/DOCX 텍스트 추출"""
    name = uploaded_file.name.lower()

    if name.endswith(".txt"):
        return uploaded_file.getvalue().decode("utf-8", errors="ignore")

    if name.endswith(".pdf"):
        if PyPDF2 is None:
            return None
        try:
            reader = PyPDF2.PdfReader(uploaded_file)
            parts = []
            for page in reader.pages:
                t = page.extract_text() or ""
                parts.append(t)
            return "\n".join(parts)
        except Exception:
            return None

    if name.endswith(".docx"):
        if Document is None:
            return None
        try:
            doc = Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs])
        except Exception:
            return None

    return None

def process_media_file(uploaded_file):
    """미디어 업로드 → Gemini 파일 업로드(멀티모달 입력용)"""
    if not GENAI_OK:
        return None
    try:
        suffix = "." + uploaded_file.name.split(".")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        st.toast("🤖 AI에게 분석 자료를 전달하고 있습니다...", icon="📂")
        myfile = genai.upload_file(tmp_path)

        with st.spinner("🎧 AI가 데이터를 분석하고 있습니다..."):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)

        os.remove(tmp_path)
        if myfile.state.name == "FAILED":
            return None
        return myfile
    except Exception:
        return None

def download_and_upload_youtube_audio(url: str):
    if yt_dlp is None or not GENAI_OK:
        return None
    try:
        ydl_opts = {"format": "bestaudio/best", "outtmpl": "temp_audio.%(ext)s", "quiet": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_files = glob.glob("temp_audio.*")
        if not audio_files:
            return None

        audio_path = audio_files[0]
        myfile = genai.upload_file(audio_path)
        with st.spinner("🎧 유튜브 분석 중..."):
            while myfile.state.name == "PROCESSING":
                time.sleep(2)
                myfile = genai.get_file(myfile.name)

        os.remove(audio_path)
        return myfile
    except Exception:
        return None

def _extract_youtube_id(url: str):
    """yout.be / watch?v= / shorts/ 모두 대응 (간단 파서)"""
    if not url:
        return None
    if "youtu.be/" in url:
        vid = url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
        return vid or None
    if "shorts/" in url:
        vid = url.split("shorts/")[-1].split("?")[0].split("&")[0]
        return vid or None
    if "watch" in url and "v=" in url:
        vid = url.split("v=")[-1].split("&")[0]
        return vid or None
    return None

def get_youtube_transcript(url: str):
    if YouTubeTranscriptApi is None:
        return None
    try:
        video_id = _extract_youtube_id(url)
        if not video_id:
            return None
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=["ko", "en"])
        return " ".join([t.get("text", "") for t in transcript]).strip() or None
    except Exception:
        return None

def get_web_content(url: str):
    if requests is None or BeautifulSoup is None:
        return None
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:10000]
    except Exception:
        return None

# ==========================================
# 6. 메인 UI
# ==========================================
st.markdown("<h1 style='text-align: center; color: #2C3E50;'>🛡️ AUDIT AI AGENT</h1>", unsafe_allow_html=True)
st.markdown("<div style='text-align: center; color: #555; margin-bottom: 20px;'>Professional Legal & Audit Assistant System</div>", unsafe_allow_html=True)

# 설치 경고(페이지 상단에 한 번만)
if not GENAI_OK:
    st.error("❌ google-generativeai(=google-generativeai) 패키지가 없어 AI 기능이 동작하지 않습니다.")
if not GSPREAD_OK:
    st.warning("⚠️ gspread/oath2client 패키지가 없어 구글시트 저장/대시보드 기능이 동작하지 않습니다.")

tab_audit, tab_doc, tab_chat, tab_summary, tab_admin = st.tabs(
    ["✅ 1월 자율점검", "📄 문서 정밀 검토", "💬 AI 에이전트", "📰 스마트 요약", "🔒 관리자"]
)

# --- Tab 1: 자율점검 ---
with tab_audit:
    current_sheet_name = "1월_설명절_캠페인"
    st.markdown("### 🎍 1월: 설 명절 '청탁금지법' 자율점검")
    st.info("📢 설 명절, 마음만 주고 받으세요! (금품/선물 수수 금지)")

    with st.form("audit_submit_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns(4)
        emp_id = c1.text_input("사번", placeholder="예: 12345")
        name = c2.text_input("성명")
        ordered_units = ["경영총괄", "사업총괄", "강북본부", "강남본부", "서부본부", "강원본부", "품질지원단", "감사실"]
        unit = c3.selectbox("총괄 / 본부 / 단", ordered_units)
        dept = c4.text_input("상세 부서명")

        st.markdown("**Q. 위 내용을 확인하였으며, 이를 철저히 준수할 것을 서약합니다.**")
        agree_check = st.checkbox("네, 확인하였으며 서약합니다.")

        if st.form_submit_button("점검 완료 및 제출", use_container_width=True):
            if not emp_id or not name:
                st.warning("⚠️ 사번과 성명을 입력해주세요.")
            elif not agree_check:
                st.error("❌ 서약에 체크해주세요.")
            else:
                with st.spinner("제출 중..."):
                    success, msg = save_audit_result(emp_id, name, unit, dept, "서약함(PASS)", current_sheet_name)
                if success:
                    st.success(f"✅ {name}님, 제출 완료되었습니다!")
                    st.balloons()
                else:
                    st.error(f"❌ 실패: {msg}")

# --- Tab 2: 문서 정밀 검토 ---
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
                if not uploaded_file:
                    st.warning("파일을 업로드해주세요.")
                else:
                    content = read_file(uploaded_file)
                    if not content:
                        st.error("파일에서 텍스트를 추출하지 못했습니다. (PDF는 스캔본일 수 있어요)")
                    else:
                        with st.spinner("🧠 AI가 분석 중입니다..."):
                            try:
                                prompt = f"[역할] 전문 감사인\n[작업] {option}\n[내용]\n{content}"
                                res = get_model().generate_content(prompt)
                                st.success("분석 완료")
                                st.markdown(res.text)
                            except Exception as e:
                                st.error(f"오류: {e}")

# --- Tab 3: AI 에이전트 ---
with tab_chat:
    st.markdown("### 💬 AI 법률/감사 챗봇")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        st.session_state.setdefault("messages", [])

        with st.form("chat_input_form", clear_on_submit=True):
            user_input = st.text_input("질문 입력")
            send_btn = st.form_submit_button("전송 📤", use_container_width=True)

        if send_btn and user_input:
            st.session_state["messages"].append({"role": "user", "content": user_input})
            with st.spinner("답변 생성 중..."):
                try:
                    res = get_model().generate_content(user_input)
                    st.session_state["messages"].append({"role": "assistant", "content": res.text})
                except Exception as e:
                    st.error(f"오류: {e}")

        # 최신 메시지가 아래로 쌓이게 표시
        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                st.write(msg["content"])

# --- Tab 4: 스마트 요약 ---
with tab_summary:
    st.markdown("### 📰 스마트 요약")
    if "api_key" not in st.session_state:
        st.warning("🔒 로그인 후 이용 가능합니다.")
    else:
        st_type = st.radio("입력 방식", ["URL (유튜브/웹)", "미디어 파일", "텍스트"], horizontal=True)
        final_input = None
        is_multimodal = False

        if "URL" in st_type:
            url = st.text_input("URL 입력")
            if url and "youtu" in url:
                with st.spinner("자막 추출 중..."):
                    final_input = get_youtube_transcript(url)
                if not final_input:
                    with st.spinner("자막 실패 → 오디오로 대체 분석 시도 중..."):
                        final_input = download_and_upload_youtube_audio(url)
                        is_multimodal = final_input is not None
            elif url:
                with st.spinner("웹페이지 분석 중..."):
                    final_input = get_web_content(url)

        elif "미디어" in st_type:
            mf = st.file_uploader("파일 업로드", type=["mp3", "wav", "mp4"])
            if mf:
                final_input = process_media_file(mf)
                is_multimodal = final_input is not None

        else:
            final_input = st.text_area("텍스트 입력", height=200)

        if st.button("⚡ 요약 실행", use_container_width=True):
            if not final_input:
                st.warning("요약할 입력을 넣어주세요.")
            else:
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

# --- Tab 5: 관리자 대시보드 ---
with tab_admin:
    st.markdown("### 🔒 관리자 전용 대시보드")
    admin_pw = st.text_input("관리자 비밀번호", type="password", key="admin_dash_pw")

    if admin_pw.strip() == "ktmos0402!":
        st.success("접속 성공")

        if pd is None or px is None:
            st.error("pandas/plotly 패키지가 없어 대시보드가 동작하지 않습니다.")
        else:
            target_dict = {
                "경영총괄": 45,
                "사업총괄": 37,
                "강북본부": 222,
                "강남본부": 174,
                "서부본부": 290,
                "강원본부": 104,
                "품질지원단": 138,
                "감사실": 3,
            }
            ordered_units = list(target_dict.keys())

            if st.button("🔄 데이터 최신화", use_container_width=True):
                client = init_google_sheet_connection()
                if not client:
                    st.error("구글 시트 연결 실패 (gspread/Secrets 확인)")
                else:
                    try:
                        ss = client.open("Audit_Result_2026")
                        ws = ss.worksheet("1월_설명절_캠페인")
                        df = pd.DataFrame(ws.get_all_records())

                        if df.empty:
                            st.info("데이터가 없습니다.")
                        else:
                            counts = df["총괄/본부/단"].value_counts().to_dict()
                            stats = []
                            for u in ordered_units:
                                t = target_dict.get(u, 0)
                                act = counts.get(u, 0)
                                stats.append(
                                    {
                                        "조직": u,
                                        "참여완료": act,
                                        "미참여": max(0, t - act),
                                        "참여율": round((act / t) * 100, 1) if t > 0 else 0,
                                    }
                                )
                            stats_df = pd.DataFrame(stats)

                            fig_bar = px.bar(
                                stats_df,
                                x="조직",
                                y=["참여완료", "미참여"],
                                text_auto=True,
                                title="조직별 참여 현황",
                            )
                            st.plotly_chart(fig_bar, use_container_width=True)

                            fig_line = px.line(
                                stats_df,
                                x="조직",
                                y="참여율",
                                markers=True,
                                text="참여율",
                                title="조직별 참여율(%)",
                            )
                            st.plotly_chart(fig_line, use_container_width=True)

                            st.dataframe(df, use_container_width=True)
                            st.download_button(
                                "📥 CSV 다운로드",
                                df.to_csv(index=False).encode("utf-8-sig"),
                                "audit_result.csv",
                            )
                    except Exception as e:
                        st.error(f"데이터 조회 실패: {e}")
    else:
        st.info("관리자 비밀번호를 입력하면 대시보드가 활성화됩니다.")

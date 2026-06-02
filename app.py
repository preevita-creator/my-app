import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import socket

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="인테리어 연단가 순번관리 시스템",
    page_icon="🏢",
    layout="wide",
)

# ── 로그인 정보 ───────────────────────────────────────────────
ADMIN_ID = "admin"
ADMIN_PW = "flower1004"

# ── 스타일 ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

/* 로그인 화면 */
.login-wrap {
    max-width: 420px;
    margin: 6rem auto 0 auto;
    background: #fff;
    border-radius: 20px;
    padding: 3rem 2.5rem 2.5rem;
    box-shadow: 0 8px 40px rgba(15,52,96,0.13);
    text-align: center;
}
.login-icon { font-size: 3rem; margin-bottom: 0.5rem; }
.login-title {
    font-size: 1.35rem; font-weight: 700;
    color: #1a1a2e; margin-bottom: 0.3rem;
}
.login-sub {
    font-size: 0.88rem; color: #6b7280; margin-bottom: 1.8rem;
}

/* 메인 화면 */
.main-title {
    font-size: 1.9rem; font-weight: 700;
    color: #1a1a2e; margin-bottom: 0.2rem;
}
.sub-title {
    font-size: 0.95rem; color: #6b7280; margin-bottom: 1.2rem;
}
.company-card {
    border-radius: 16px;
    padding: 2rem 2.5rem;
    text-align: center;
    box-shadow: 0 8px 32px rgba(15,52,96,0.25);
    margin-bottom: 1rem;
}
.company-label {
    font-size: 0.85rem; font-weight: 600;
    letter-spacing: 0.15em; color: #94a3b8;
    text-transform: uppercase; margin-bottom: 0.5rem;
}
.company-name {
    font-size: 3.2rem; font-weight: 700;
    color: #e2e8f0; line-height: 1;
}
.company-sub {
    font-size: 0.9rem; color: #94a3b8; margin-top: 0.6rem;
}
.next-badge {
    display: inline-block;
    background: #f1f5f9;
    border-radius: 8px;
    padding: 0.4rem 1rem;
    font-size: 0.85rem; color: #475569;
    font-weight: 600;
}
div[data-testid="stButton"] > button {
    border: none !important;
    border-radius: 10px !important;
    padding: 0.65rem 2.5rem !important;
    font-size: 1rem !important;
    font-weight: 600 !important;
    font-family: 'Noto Sans KR', sans-serif !important;
    transition: all 0.2s ease !important;
    width: 100% !important;
}
.log-header {
    font-size: 1.05rem; font-weight: 700;
    color: #1a1a2e; margin-bottom: 0.5rem;
}
.logout-area {
    text-align: right; margin-bottom: 0.5rem;
    font-size: 0.85rem; color: #6b7280;
}
</style>
""", unsafe_allow_html=True)

# ── 상수 ─────────────────────────────────────────────────────
COMPANIES = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
DB_PATH = "extraction_log.db"

TABS = [
    {
        "name": "🛋 인테리어 설계",
        "key": "interior",
        "gradient": "linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%)",
    },
    {
        "name": "💡 조명 설계",
        "key": "lighting",
        "gradient": "linear-gradient(135deg, #2d1b00 0%, #7c4a00 60%, #c97b00 100%)",
    },
    {
        "name": "🔍 브랜드 인테리어 공사 감리",
        "key": "supervision",
        "gradient": "linear-gradient(135deg, #0d2b1a 0%, #145a32 60%, #1e8449 100%)",
    },
]

# ── DB 초기화 ─────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    for tab in TABS:
        k = tab["key"]
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS logs_{k} (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                company       TEXT NOT NULL,
                admin         TEXT NOT NULL,
                ip            TEXT NOT NULL,
                extracted_at  TEXT NOT NULL,
                status        TEXT NOT NULL DEFAULT '대기중',
                reject_reason TEXT DEFAULT ''
            )
        """)
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS state_{k} (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.execute(f"INSERT OR IGNORE INTO state_{k} (key, value) VALUES ('current_index', '0')")
    conn.commit()
    conn.close()

def get_current_index(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(f"SELECT value FROM state_{key} WHERE key='current_index'").fetchone()
    conn.close()
    return int(row[0]) if row else 0

def save_extraction(key, company, admin, ip):
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        f"INSERT INTO logs_{key} (company, admin, ip, extracted_at, status, reject_reason) VALUES (?,?,?,?,?,?)",
        (company, admin, ip, now, "대기중", "")
    )
    current = int(conn.execute(f"SELECT value FROM state_{key} WHERE key='current_index'").fetchone()[0])
    new_index = (current + 1) % len(COMPANIES)
    conn.execute(f"UPDATE state_{key} SET value=? WHERE key='current_index'", (str(new_index),))
    conn.commit()
    conn.close()

def update_status(key, log_id, status, reason=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        f"UPDATE logs_{key} SET status=?, reject_reason=? WHERE id=?",
        (status, reason, log_id)
    )
    conn.commit()
    conn.close()

def get_pending_log(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        f"SELECT id, company, admin FROM logs_{key} WHERE status='대기중' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row

def load_logs(key):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        f"""SELECT extracted_at AS '추출 시각', id AS '번호', company AS '업체',
                   admin AS '관리자', ip AS 'IP 주소',
                   status AS '상태', reject_reason AS '거절 사유'
            FROM logs_{key} ORDER BY id DESC""",
        conn
    )
    conn.close()
    return df

def get_client_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"

# ── 세션 상태 초기화 ──────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

init_db()

# ══════════════════════════════════════════════════════════════
# 로그인 화면
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:

    # 가운데 정렬을 위한 컬럼 트릭
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown("""
        <div class="login-wrap">
            <div class="login-icon">🏢</div>
            <div class="login-title">인테리어 연단가 순번관리 시스템</div>
            <div class="login-sub">관리자 계정으로 로그인하세요</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        user_id = st.text_input("아이디", placeholder="아이디를 입력하세요", key="login_id")
        user_pw = st.text_input("비밀번호", placeholder="비밀번호를 입력하세요", type="password", key="login_pw")

        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

        if st.button("🔐 로그인", key="login_btn"):
            if user_id == ADMIN_ID and user_pw == ADMIN_PW:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 올바르지 않습니다.")

# ══════════════════════════════════════════════════════════════
# 메인 화면 (로그인 후)
# ══════════════════════════════════════════════════════════════
else:

    # 상단: 제목 + 로그아웃
    title_col, logout_col = st.columns([5, 1])
    with title_col:
        st.markdown('<div class="main-title">🏢 인테리어 연단가 순번관리 시스템</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">탭을 선택하여 각 분야별 순번을 관리하세요</div>', unsafe_allow_html=True)
    with logout_col:
        st.markdown("<div style='height:1.2rem'></div>", unsafe_allow_html=True)
        if st.button("🚪 로그아웃", key="logout_btn"):
            st.session_state.logged_in = False
            st.rerun()

    # ── 탭 렌더링 ─────────────────────────────────────────────
    def render_tab(tab):
        key = tab["key"]
        idx = get_current_index(key)
        current_company = COMPANIES[idx]
        next_company = COMPANIES[(idx + 1) % len(COMPANIES)]

        col_left, col_right = st.columns([1, 1.6], gap="large")

        with col_left:
            st.markdown(f"""
            <div class="company-card" style="background:{tab['gradient']};">
                <div class="company-label">다음 순번 업체</div>
                <div class="company-name">업체 {current_company}</div>
                <div class="company-sub">{idx + 1} / {len(COMPANIES)} 번째 순번</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f'<div style="text-align:center;margin-bottom:1rem;">그 다음 → <span class="next-badge">업체 {next_company}</span></div>', unsafe_allow_html=True)

            pending = get_pending_log(key)

            if pending:
                pending_id, pending_company, _ = pending
                st.warning(f"⏳ **업체 {pending_company}** 응답 대기중...")
                st.markdown("**업체 수락 여부를 선택하세요**")

                col_a, col_r = st.columns(2)
                with col_a:
                    if st.button("✅ 수락", key=f"accept_{key}"):
                        update_status(key, pending_id, "수락")
                        st.success(f"업체 {pending_company} 수락 완료!")
                        st.rerun()
                with col_r:
                    if st.button("❌ 거절", key=f"reject_{key}"):
                        st.session_state[f"show_reject_{key}"] = True

                if st.session_state.get(f"show_reject_{key}"):
                    reject_reason = st.text_input("거절 사유를 입력하세요", key=f"reason_{key}")
                    if st.button("거절 확정", key=f"confirm_reject_{key}"):
                        if not reject_reason.strip():
                            st.warning("⚠️ 거절 사유를 입력해 주세요.")
                        else:
                            update_status(key, pending_id, "거절", reject_reason.strip())
                            st.session_state[f"show_reject_{key}"] = False
                            st.success(f"업체 {pending_company} 거절 처리 완료. 다음 순번으로 넘어갑니다.")
                            st.rerun()
            else:
                admin_name = st.text_input("관리자 이름", placeholder="이름을 입력하세요", key=f"admin_{key}")
                if st.button("⬆ 지금 추출하기", key=f"extract_{key}"):
                    if not admin_name.strip():
                        st.warning("⚠️ 관리자 이름을 먼저 입력해 주세요.")
                    else:
                        save_extraction(key, current_company, admin_name.strip(), get_client_ip())
                        st.success(f"✅ **업체 {current_company}** 추출 완료!")
                        st.rerun()

        with col_right:
            st.markdown('<div class="log-header">📋 순번 이력</div>', unsafe_allow_html=True)
            logs_df = load_logs(key)
            if logs_df.empty:
                st.info("아직 기록이 없습니다. 버튼을 눌러 추출을 시작하세요.")
            else:
                st.dataframe(logs_df, use_container_width=True, hide_index=True, height=420)
                st.caption(f"총 {len(logs_df)}건의 기록")

    tab1, tab2, tab3 = st.tabs([t["name"] for t in TABS])
    with tab1:
        render_tab(TABS[0])
    with tab2:
        render_tab(TABS[1])
    with tab3:
        render_tab(TABS[2])

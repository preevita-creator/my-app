import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import socket
import os
import shutil
from pathlib import Path

# ── 페이지 설정 ──────────────────────────────────────────────
st.set_page_config(
    page_title="인테리어 연단가 순번관리 시스템",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── 로그인 정보 ───────────────────────────────────────────────
ADMIN_ID = "admin"
ADMIN_PW = "flower1004"

# ── 스타일 ───────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.main-title {
    font-size: 1.8rem; font-weight: 700;
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
</style>
""", unsafe_allow_html=True)

# ── 상수 ─────────────────────────────────────────────────────
DB_PATH = "extraction_log.db"

# 탭별 업체 리스트
COMPANY_LISTS = {
    "interior": ["우리디자인", "문건축", "웰킵스디웰", "선미인터내셔널", "한스아이디", "에스피앤파트너", "이오에스앤디"],
    "lighting": ["라잇톨로지", "라미디자인연구소", "디자인루나", "라이팅랩와츠", "루미노", "플로이 라이츠온"],
    "supervision": ["무유에이엔디", "로담건축"],
}

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
        
        # 테이블이 존재하는지 확인
        cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='logs_{k}'")
        table_exists = cursor.fetchone() is not None
        
        if not table_exists:
            # 새 테이블 생성
            conn.execute(f"""
                CREATE TABLE logs_{k} (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    company       TEXT NOT NULL,
                    user_name     TEXT NOT NULL,
                    user_id       TEXT NOT NULL,
                    extracted_at  TEXT NOT NULL,
                    status        TEXT NOT NULL DEFAULT '대기중',
                    reject_reason TEXT DEFAULT '',
                    reject_file   TEXT DEFAULT '',
                    approval_no   TEXT DEFAULT '',
                    client_local_ip TEXT DEFAULT ''
                )
            """)
        else:
            # 기존 테이블 마이그레이션 (필요한 컬럼 추가)
            try:
                conn.execute(f"ALTER TABLE logs_{k} ADD COLUMN user_name TEXT DEFAULT ''")
            except:
                pass
            try:
                conn.execute(f"ALTER TABLE logs_{k} ADD COLUMN user_id TEXT DEFAULT ''")
            except:
                pass
            try:
                conn.execute(f"ALTER TABLE logs_{k} ADD COLUMN client_local_ip TEXT DEFAULT ''")
            except:
                pass
            try:
                conn.execute(f"ALTER TABLE logs_{k} ADD COLUMN approval_no TEXT DEFAULT ''")
            except:
                pass
        
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
    index = int(row[0]) if row else 0
    max_companies = len(COMPANY_LISTS[key])
    return index % max_companies

def save_extraction(key, company, user_name, user_id, approval_no="", client_local_ip=""):
    conn = sqlite3.connect(DB_PATH)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        f"INSERT INTO logs_{key} (company, user_name, user_id, extracted_at, status, reject_reason, reject_file, approval_no, client_local_ip) VALUES (?,?,?,?,?,?,?,?,?)",
        (company, user_name, user_id, now, "대기중", "", "", approval_no, client_local_ip)
    )
    current = int(conn.execute(f"SELECT value FROM state_{key} WHERE key='current_index'").fetchone()[0])
    max_companies = len(COMPANY_LISTS[key])
    new_index = (current + 1) % max_companies
    conn.execute(f"UPDATE state_{key} SET value=? WHERE key='current_index'", (str(new_index),))
    conn.commit()
    conn.close()

def update_status(key, log_id, status, reason="", file_data=None, file_name=""):
    conn = sqlite3.connect(DB_PATH)
    
    file_path = ""
    if file_data and file_name and status == "거부":
        reject_dir = "거부사유_파일"
        Path(reject_dir).mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file_name}"
        file_path = os.path.join(reject_dir, safe_filename)
        with open(file_path, "wb") as f:
            f.write(file_data)
    
    conn.execute(
        f"UPDATE logs_{key} SET status=?, reject_reason=?, reject_file=? WHERE id=?",
        (status, reason, file_path, log_id)
    )
    conn.commit()
    conn.close()

def get_pending_log(key):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        f"SELECT id, company, user_name FROM logs_{key} WHERE status='대기중' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row

def load_logs(key):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        f"""SELECT id AS '번호', extracted_at AS '추출시각', user_name AS '사용자', user_id AS '사번',
                   client_local_ip AS '접속자IP', company AS '업체명',
                   approval_no AS '품의번호', status AS '상태', reject_reason AS '거부사유', reject_file AS 'reject_file'
            FROM logs_{key} ORDER BY id DESC""",
        conn
    )
    conn.close()
    return df

def export_to_excel(key, tab_name):
    df = load_logs(key)
    if df.empty:
        return None
    
    from io import BytesIO
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name=tab_name, index=False)
        
        worksheet = writer.sheets[tab_name]
        
        from openpyxl.styles import Alignment
        for row in worksheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 30)
            worksheet.column_dimensions[column_letter].width = adjusted_width
    
    output.seek(0)
    return output.getvalue()

def get_client_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"

# ── 세션 상태 초기화 ──────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_type = None  # "admin" or "user"
    st.session_state.user_name = None
    st.session_state.user_id = None

init_db()

# ══════════════════════════════════════════════════════════════
# 관리자 로그인
# ══════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown("""
    <div style="max-width: 420px; margin: 4rem auto 0 auto; background: #fff; border-radius: 20px; padding: 3rem 2.5rem; box-shadow: 0 8px 40px rgba(15,52,96,0.13); text-align: center;">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">🏢</div>
        <div style="font-size: 1.35rem; font-weight: 700; color: #1a1a2e; margin-bottom: 0.3rem;">인테리어 연단가 순번관리 시스템</div>
        <div style="font-size: 0.88rem; color: #6b7280; margin-bottom: 1.5rem;">로그인하세요</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    
    login_type = st.radio("로그인 유형", ["👨‍💼 관리자", "👤 사용자"], horizontal=True)
    
    if login_type == "👨‍💼 관리자":
        admin_id = st.text_input("아이디", placeholder="아이디를 입력하세요", key="admin_id")
        admin_pw = st.text_input("비밀번호", placeholder="비밀번호를 입력하세요", type="password", key="admin_pw")
        
        if st.button("🔐 관리자 로그인", use_container_width=True):
            if admin_id == ADMIN_ID and admin_pw == ADMIN_PW:
                st.session_state.logged_in = True
                st.session_state.user_type = "admin"
                st.rerun()
            else:
                st.error("❌ 아이디 또는 비밀번호가 올바르지 않습니다.")
    
    else:  # 사용자
        user_name = st.text_input("이름", placeholder="이름을 입력하세요", key="user_name_input")
        user_id = st.text_input(
            "사번", 
            placeholder="사번을 입력하세요 (숫자만, 최대 9자)",
            key="user_id_input",
            max_chars=9
        )
        
        # 사번이 숫자만인지 확인
        if user_id and not user_id.isdigit():
            st.warning("⚠️ 사번은 숫자만 입력 가능합니다.")
            user_id = ""
        
        if st.button("📱 입장", use_container_width=True):
            if not user_name.strip() or not user_id.strip():
                st.warning("⚠️ 이름과 사번을 모두 입력해 주세요.")
            elif not user_id.isdigit():
                st.warning("⚠️ 사번은 숫자만 입력 가능합니다.")
            else:
                st.session_state.logged_in = True
                st.session_state.user_type = "user"
                st.session_state.user_name = user_name.strip()
                st.session_state.user_id = user_id.strip()
                st.rerun()

# ══════════════════════════════════════════════════════════════
# 관리자 화면
# ══════════════════════════════════════════════════════════════
elif st.session_state.user_type == "admin":
    title_col, logout_col = st.columns([4, 1])
    with title_col:
        st.markdown('<div class="main-title">🏢 인테리어 연단가 순번관리 시스템</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-title">관리자 화면 - 탭을 선택하여 각 분야별 순번을 관리하세요</div>', unsafe_allow_html=True)
    with logout_col:
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
        if st.button("🚪 로그아웃", key="logout_btn", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_type = None
            st.rerun()

    def render_admin_tab(tab):
        key = tab["key"]
        companies = COMPANY_LISTS[key]
        
        idx = get_current_index(key)
        current_company = companies[idx]
        next_company = companies[(idx + 1) % len(companies)]

        col_left, col_right = st.columns([1, 1.6], gap="large")

        with col_left:
            st.markdown(f"""
            <div class="company-card" style="background:{tab['gradient']};">
                <div class="company-label">이번 순번 업체</div>
                <div class="company-name">{current_company}</div>
                <div class="company-sub">{idx + 1} / {len(companies)} 번째 순번</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f'<div style="text-align:center;margin-bottom:1rem;">그 다음 → <span class="next-badge">{next_company}</span></div>', unsafe_allow_html=True)

            pending = get_pending_log(key)

            if pending:
                pending_id, pending_company, pending_user = pending
                st.warning(f"⏳ **{pending_company}** 응답 대기중... (사용자: {pending_user})")
                st.markdown("**업체 수락 여부를 선택하세요**")

                col_a, col_r = st.columns(2)
                with col_a:
                    if st.button("✅ 수락", key=f"accept_{key}"):
                        update_status(key, pending_id, "수락")
                        st.success(f"{pending_company} 수락 완료!")
                        st.rerun()
                with col_r:
                    if st.button("❌ 거부", key=f"reject_{key}"):
                        st.session_state[f"show_reject_{key}"] = True

                if st.session_state.get(f"show_reject_{key}"):
                    reject_reason = st.text_input("거부 사유를 입력하세요", key=f"reason_{key}")
                    reject_file = st.file_uploader("거부 사유 파일 첨부 (선택사항)", key=f"reject_file_{key}")
                    
                    if st.button("거부 확정", key=f"confirm_reject_{key}"):
                        if not reject_reason.strip():
                            st.warning("⚠️ 거부 사유를 입력해 주세요.")
                        else:
                            file_data = None
                            file_name = ""
                            if reject_file is not None:
                                file_data = reject_file.read()
                                file_name = reject_file.name
                            
                            update_status(key, pending_id, "거부", reject_reason.strip(), file_data, file_name)
                            st.session_state[f"show_reject_{key}"] = False
                            st.success(f"{pending_company} 거부 처리 완료. 다음 순번으로 넘어갑니다.")
                            st.rerun()

        with col_right:
            st.markdown('<div class="log-header">📋 순번 이력</div>', unsafe_allow_html=True)
            logs_df = load_logs(key)
            if logs_df.empty:
                st.info("아직 기록이 없습니다.")
            else:
                # 테이블 헤더
                header_cols = st.columns([1, 1.8, 1.3, 1.3, 1.3, 1.8, 1.3, 1, 1.8, 1.2])
                with header_cols[0]:
                    st.markdown("**번호**")
                with header_cols[1]:
                    st.markdown("**시각**")
                with header_cols[2]:
                    st.markdown("**사용자**")
                with header_cols[3]:
                    st.markdown("**사번**")
                with header_cols[4]:
                    st.markdown("**접속자IP**")
                with header_cols[5]:
                    st.markdown("**업체명**")
                with header_cols[6]:
                    st.markdown("**품의번호**")
                with header_cols[7]:
                    st.markdown("**상태**")
                with header_cols[8]:
                    st.markdown("**거부사유**")
                with header_cols[9]:
                    st.markdown("**다운**")
                
                st.divider()
                
                # 테이블 행
                for idx, row in logs_df.iterrows():
                    row_cols = st.columns([1, 1.8, 1.3, 1.3, 1.3, 1.8, 1.3, 1, 1.8, 1.2])
                    
                    with row_cols[0]:
                        st.write(str(row['번호']))
                    with row_cols[1]:
                        st.write(str(row['추출시각'])[:16])
                    with row_cols[2]:
                        st.write(str(row['사용자']))
                    with row_cols[3]:
                        st.write(str(row['사번']))
                    with row_cols[4]:
                        st.write(str(row['접속자IP']) if row['접속자IP'] else "-")
                    with row_cols[5]:
                        st.write(str(row['업체명']))
                    with row_cols[6]:
                        st.write(str(row['품의번호']) if row['품의번호'] else "-")
                    with row_cols[7]:
                        st.write(str(row['상태']))
                    with row_cols[8]:
                        st.write(str(row['거부사유']) if row['거부사유'] else "-")
                    with row_cols[9]:
                        if row['reject_file'] and os.path.exists(row['reject_file']):
                            with open(row['reject_file'], 'rb') as f:
                                file_data = f.read()
                            file_name = os.path.basename(row['reject_file'])
                            st.download_button(
                                label="📥",
                                data=file_data,
                                file_name=file_name,
                                key=f"download_{key}_{row['번호']}",
                                help="다운로드",
                                use_container_width=True
                            )
                        else:
                            st.write("-")
                
                st.markdown("---")
                
                # 엑셀 다운로드 버튼
                excel_data = export_to_excel(key, tab['name'])
                if excel_data:
                    col_info, col_excel = st.columns([2, 1])
                    with col_info:
                        st.caption(f"총 {len(logs_df)}건의 기록")
                    with col_excel:
                        st.download_button(
                            label="📥 엑셀 저장",
                            data=excel_data,
                            file_name=f"{tab['name'].replace(' ', '_')}_순번이력.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"excel_{key}"
                        )

    tab1, tab2, tab3 = st.tabs([t["name"] for t in TABS])
    with tab1:
        render_admin_tab(TABS[0])
    with tab2:
        render_admin_tab(TABS[1])
    with tab3:
        render_admin_tab(TABS[2])

# ══════════════════════════════════════════════════════════════
# 사용자 화면
# ══════════════════════════════════════════════════════════════
else:
    col_left, col_right = st.columns([4, 1])
    with col_left:
        st.markdown('<div class="main-title">🏢 인테리어 연단가 순번관리 시스템</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="sub-title">안녕하세요, {st.session_state.user_name}님!</div>', unsafe_allow_html=True)
    with col_right:
        st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
        if st.button("🚪 나가기", key="user_logout_btn", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.user_type = None
            st.session_state.user_name = None
            st.session_state.user_id = None
            st.rerun()

    def render_user_tab(tab):
        key = tab["key"]
        companies = COMPANY_LISTS[key]
        
        idx = get_current_index(key)
        current_company = companies[idx]
        next_company = companies[(idx + 1) % len(companies)]

        st.markdown(f"""
        <div class="company-card" style="background:{tab['gradient']};">
            <div class="company-label">이번 순번 업체</div>
            <div class="company-name">{current_company}</div>
            <div class="company-sub">{idx + 1} / {len(companies)} 번째 순번</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f'<div style="text-align:center;margin-bottom:1rem;">그 다음 → <span class="next-badge">{next_company}</span></div>', unsafe_allow_html=True)

        approval_no = st.text_input("품의번호", placeholder="품의번호를 입력하세요", key=f"approval_{key}")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬆ 지금 의뢰하기", key=f"extract_{key}", use_container_width=True):
                st.session_state[f"show_confirm_{key}"] = True
        
        if st.session_state.get(f"show_confirm_{key}"):
            with col2:
                if st.button("의뢰완료", key=f"confirm_{key}", use_container_width=True):
                    save_extraction(key, current_company, st.session_state.user_name, st.session_state.user_id, approval_no, "")
                    st.balloons()
                    st.success(f"✅ **{current_company}** 의뢰 완료!")
                    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
                    st.markdown(f"""
                    <div style="text-align:center; padding:2rem; background:#e8f5e9; border-radius:10px;">
                    <div style="font-size:1.2rem; font-weight:bold; color:#2e7d32; margin-bottom:1rem;">의뢰가 완료되었습니다!</div>
                    <div style="font-size:0.9rem; color:#558b2f;">3초 후 자동으로 로그아웃됩니다...</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # JavaScript로 자동 새로고침
                    st.markdown("""
                    <script>
                    setTimeout(function() {
                        window.location.reload();
                    }, 3000);
                    </script>
                    """, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs([t["name"] for t in TABS])
    with tab1:
        render_user_tab(TABS[0])
    with tab2:
        render_user_tab(TABS[1])
    with tab3:
        render_user_tab(TABS[2])

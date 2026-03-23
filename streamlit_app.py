import streamlit as st
import json
import pandas as pd

from database import init_db, save_student, save_extracted_items, get_all_students, get_student_data, get_config, set_config
from extractor import extract_theories_and_books, extract_text_from_pdf

try:
    from sheets_manager import create_master_sheet, append_student_to_sheet
    SHEETS_AVAILABLE = True
except Exception:
    SHEETS_AVAILABLE = False

# ── 초기화 ─────────────────────────────────────────────────────────
init_db()

st.set_page_config(
    page_title="생기부 이론·도서 DB",
    page_icon="📚",
    layout="wide",
)

st.title("📚 생활기록부 이론·도서 추출기")
st.caption("생활기록부(PDF 또는 텍스트)에서 이론과 도서를 추출하여 DB에 저장합니다.")
st.markdown(
    "<div style='text-align:right; color:#888; font-size:13px;'>by <b>학종 강선생</b></div>",
    unsafe_allow_html=True,
)

# ── 사이드바 ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")
    anthropic_key = st.text_input(
        "Anthropic API Key",
        type="password",
        help="Claude API 키를 입력하세요.",
    )

    st.divider()
    st.subheader("📊 Google Sheets 연동")
    use_sheets = st.toggle("구글 시트 내보내기 사용", value=False)

    credentials_json = None
    if use_sheets and SHEETS_AVAILABLE:
        uploaded_creds = st.file_uploader(
            "서비스 계정 JSON 파일 업로드",
            type=["json"],
            help="Google Cloud Console에서 발급한 서비스 계정 키 파일입니다.",
        )
        if uploaded_creds:
            credentials_json = json.load(uploaded_creds)
            st.success("✅ 인증 파일 로드 완료")

        # 저장된 마스터 시트 표시
        saved_sheet_id = get_config("master_sheet_id")
        saved_sheet_url = get_config("master_sheet_url")
        if saved_sheet_id:
            st.success("📋 연결된 DB 시트")
            st.link_button("📊 시트 열기", saved_sheet_url, use_container_width=True)
            if st.button("🔗 연결 해제", use_container_width=True):
                set_config("master_sheet_id", "")
                set_config("master_sheet_url", "")
                st.rerun()
        else:
            st.info("내보내기 시 새 DB 시트가 자동 생성됩니다.")

    st.divider()
    st.markdown(
        "<div style='text-align:center; color:#aaa; font-size:12px;'>📌 학종 강선생</div>",
        unsafe_allow_html=True,
    )

# ── 탭 구성 ───────────────────────────────────────────────────────
tab_input, tab_db = st.tabs(["➕ 생기부 입력", "🗄️ DB 조회"])

# ════════════════════════════════════════════════════════════════════
# 탭 1: 생기부 입력
# ════════════════════════════════════════════════════════════════════
with tab_input:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("📝 생활기록부 입력")
        student_name = st.text_input("학생 이름", placeholder="예: 홍길동")

        # PDF 업로드
        uploaded_pdf = st.file_uploader(
            "📎 생활기록부 PDF 첨부 (선택)",
            type=["pdf"],
            help="PDF를 첨부하면 텍스트를 자동으로 인식합니다. 스캔 파일도 지원합니다.",
        )

        if uploaded_pdf is not None:
            pdf_key = f"pdf_{uploaded_pdf.name}_{uploaded_pdf.size}"
            if st.session_state.get("last_pdf_key") != pdf_key:
                if not anthropic_key:
                    st.warning("PDF 인식을 위해 사이드바에서 API Key를 먼저 입력해주세요.")
                else:
                    with st.spinner("📄 PDF에서 텍스트를 인식하는 중..."):
                        try:
                            extracted_pdf_text = extract_text_from_pdf(uploaded_pdf.read(), anthropic_key)
                            st.session_state["pdf_text"] = extracted_pdf_text
                            st.session_state["last_pdf_key"] = pdf_key
                            st.success(f"✅ PDF 인식 완료 ({len(extracted_pdf_text):,}자)")
                        except Exception as e:
                            st.error(f"PDF 인식 실패: {e}")

        default_text = st.session_state.get("pdf_text", "")
        record_text = st.text_area(
            "생활기록부 내용",
            value=default_text,
            height=420,
            placeholder="""예시:
교과학습 발달상황:
존 내시의 '내시균형' 이론을 자발적으로 조사하여 발표함.
케인즈의 유효수요이론에 관심을 보임.

독서활동:
- '넛지' (리처드 탈러, 캐스 선스타인)
- '국부론' (애덤 스미스)
- '정의란 무엇인가' (마이클 샌델)""",
            help="PDF를 첨부하면 자동으로 채워집니다. 직접 수정도 가능합니다.",
        )

        extract_btn = st.button("🔍 이론·도서 추출 및 저장", type="primary", use_container_width=True)

    # ── 결과 컬럼 ──────────────────────────────────────────────────
    with col2:
        st.subheader("📊 추출 결과")

        if extract_btn:
            if not anthropic_key:
                st.error("사이드바에서 Anthropic API Key를 먼저 입력해주세요.")
            elif not student_name.strip():
                st.error("학생 이름을 입력해주세요.")
            elif not record_text.strip():
                st.error("생활기록부 내용을 입력하거나 PDF를 첨부해주세요.")
            else:
                with st.spinner("📖 이론과 도서를 추출하는 중..."):
                    try:
                        extracted = extract_theories_and_books(record_text, anthropic_key)
                        theories = extracted.get("theories", [])
                        books = extracted.get("books", [])
                        st.session_state["theories"] = theories
                        st.session_state["books"] = books
                        st.session_state["student_name"] = student_name
                        st.session_state["record_text"] = record_text
                    except Exception as e:
                        st.error(f"추출 실패: {e}")
                        theories, books = [], []

                if theories or books:
                    student_id = save_student(student_name, record_text)
                    save_extracted_items(student_id, theories, books)
                    st.session_state["last_student_id"] = student_id
                    st.success(f"✅ 저장 완료 — 이론 {len(theories)}개, 도서 {len(books)}개")
                    st.caption("📌 출처: 학종 강선생")
                else:
                    st.warning("추출된 이론·도서가 없습니다. 생기부 내용을 확인해주세요.")

        # 추출 결과 표시
        if "theories" in st.session_state:
            theories = st.session_state["theories"]
            books = st.session_state["books"]

            t_col, b_col = st.columns(2)
            with t_col:
                st.markdown(f"**📚 이론 ({len(theories)}개)**")
                if theories:
                    for t in theories:
                        with st.expander(t["name"]):
                            st.caption(t.get("context", ""))
                else:
                    st.info("추출된 이론 없음")

            with b_col:
                st.markdown(f"**📖 도서 ({len(books)}개)**")
                if books:
                    for b in books:
                        with st.expander(b["name"]):
                            st.caption(b.get("context", ""))
                else:
                    st.info("추출된 도서 없음")

            # 구글 시트 내보내기
            if SHEETS_AVAILABLE and use_sheets:
                st.divider()
                if st.button("📊 구글 시트 DB에 추가", use_container_width=True):
                    if not credentials_json:
                        st.error("사이드바에서 서비스 계정 JSON 파일을 업로드해주세요.")
                    else:
                        with st.spinner("구글 시트 업데이트 중..."):
                            try:
                                sheet_id = get_config("master_sheet_id")
                                if not sheet_id:
                                    # 최초: 마스터 시트 생성
                                    sheet_id, sheet_url = create_master_sheet(credentials_json)
                                    set_config("master_sheet_id", sheet_id)
                                    set_config("master_sheet_url", sheet_url)
                                    st.success("✅ DB 시트가 새로 생성되었습니다!")
                                else:
                                    sheet_url = get_config("master_sheet_url")

                                append_student_to_sheet(
                                    credentials_json,
                                    sheet_id,
                                    st.session_state.get("student_name", "학생"),
                                    theories,
                                    books,
                                )
                                st.success(f"✅ DB에 추가 완료! (이론 {len(theories)}개, 도서 {len(books)}개)")
                                st.link_button("📊 구글 시트 열기", sheet_url)
                                st.rerun()
                            except Exception as e:
                                st.error(f"구글 시트 업데이트 실패: {e}")

# ════════════════════════════════════════════════════════════════════
# 탭 2: DB 조회
# ════════════════════════════════════════════════════════════════════
with tab_db:
    st.subheader("🗄️ 저장된 이론·도서 DB")

    students = get_all_students()

    if not students:
        st.info("아직 저장된 데이터가 없습니다. '생기부 입력' 탭에서 먼저 분석해주세요.")
    else:
        # 전체 통계
        all_theories, all_books = [], []
        for s in students:
            _, items = get_student_data(s[0])
            all_theories += [i for i in items if i[0] == "theory"]
            all_books += [i for i in items if i[0] == "book"]

        m1, m2, m3 = st.columns(3)
        m1.metric("총 학생 수", f"{len(students)}명")
        m2.metric("총 이론 수", f"{len(all_theories)}개")
        m3.metric("총 도서 수", f"{len(all_books)}개")

        st.divider()

        # 탭: 학생별 / 이론 전체 / 도서 전체
        view_student, view_theories, view_books = st.tabs(["👤 학생별", "📚 이론 전체", "📖 도서 전체"])

        with view_student:
            for s in students:
                sid, sname, screated = s
                _, items = get_student_data(sid)
                t_list = [i for i in items if i[0] == "theory"]
                b_list = [i for i in items if i[0] == "book"]
                with st.expander(f"**{sname}** | {screated[:16]} | 이론 {len(t_list)}개 · 도서 {len(b_list)}개"):
                    hc1, hc2 = st.columns(2)
                    with hc1:
                        st.markdown("**이론**")
                        for item in t_list:
                            st.markdown(f"- {item[1]}")
                            if item[2]:
                                st.caption(f"  {item[2]}")
                    with hc2:
                        st.markdown("**도서**")
                        for item in b_list:
                            st.markdown(f"- {item[1]}")
                            if item[2]:
                                st.caption(f"  {item[2]}")

        with view_theories:
            if all_theories:
                rows = []
                for s in students:
                    _, items = get_student_data(s[0])
                    for i in items:
                        if i[0] == "theory":
                            rows.append({"학생": s[1], "이론명": i[1], "맥락": i[2]})
                df = pd.DataFrame(rows)
                st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                st.info("저장된 이론이 없습니다.")

        with view_books:
            if all_books:
                rows = []
                for s in students:
                    _, items = get_student_data(s[0])
                    for i in items:
                        if i[0] == "book":
                            rows.append({"학생": s[1], "도서명": i[1], "맥락": i[2]})
                df = pd.DataFrame(rows)
                st.dataframe(df, hide_index=True, use_container_width=True)
            else:
                st.info("저장된 도서가 없습니다.")

        st.divider()
        st.markdown(
            "<div style='text-align:center; color:#aaa; font-size:12px;'>📌 출처: 학종 강선생</div>",
            unsafe_allow_html=True,
        )

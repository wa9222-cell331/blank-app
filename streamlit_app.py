import streamlit as st
import json
import pandas as pd

from database import init_db, save_student, save_extracted_items, save_recommendations, get_all_students, get_student_data
from extractor import extract_theories_and_books, recommend_majors

try:
    from sheets_manager import create_recommendation_sheet
    SHEETS_AVAILABLE = True
except Exception:
    SHEETS_AVAILABLE = False

# ── 초기화 ─────────────────────────────────────────────────────────
init_db()

st.set_page_config(
    page_title="생기부 학과 추천 시스템",
    page_icon="🎓",
    layout="wide",
)

st.title("🎓 생활기록부 학과 추천 시스템")
st.caption("생활기록부에서 이론과 도서를 추출하여 맞춤형 학과를 추천합니다.")

# ── 사이드바: API 설정 ────────────────────────────────────────────
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
    if use_sheets:
        uploaded_creds = st.file_uploader(
            "서비스 계정 JSON 파일 업로드",
            type=["json"],
            help="Google Cloud Console에서 발급한 서비스 계정 키 파일입니다.",
        )
        if uploaded_creds:
            credentials_json = json.load(uploaded_creds)
            st.success("✅ 인증 파일 로드 완료")

    st.divider()
    st.subheader("📁 분석 기록")
    students = get_all_students()
    if students:
        st.selectbox(
            "이전 분석 결과 조회",
            options=["선택하세요..."] + [f"{s[0]}. {s[1]} ({s[2][:10]})" for s in students],
        )
    else:
        st.info("아직 분석 기록이 없습니다.")

# ── 탭 구성 ───────────────────────────────────────────────────────
tab_analyze, tab_history = st.tabs(["✨ 새 분석", "📋 분석 기록"])

# ════════════════════════════════════════════════════════════════════
# 탭 1: 새 분석
# ════════════════════════════════════════════════════════════════════
with tab_analyze:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.subheader("📝 생활기록부 입력")
        student_name = st.text_input("학생 이름", placeholder="예: 홍길동")
        record_text = st.text_area(
            "생활기록부 내용을 붙여넣으세요",
            height=400,
            placeholder="""예시:
교과학습 발달상황:
수학 시간에 게임이론을 적용한 경제 문제 풀이에 흥미를 보임.
존 내시의 '내시균형' 이론을 자발적으로 조사하여 발표함.

독서활동:
- '넛지' (리처드 탈러, 캐스 선스타인) 읽고 행동경제학에 관심 가짐
- '국부론' (애덤 스미스) 독후감 작성
- '정의란 무엇인가' (마이클 샌델) 토론에 참여

행동특성 및 종합의견:
케인즈의 유효수요이론과 밀턴 프리드먼의 통화주의를 비교 분석하는
자율 탐구 활동을 진행함...""",
        )

        analyze_btn = st.button("🔍 이론·도서 추출 및 학과 추천", type="primary", use_container_width=True)

    with col2:
        st.subheader("📊 분석 결과")

        if analyze_btn:
            if not anthropic_key:
                st.error("사이드바에서 Anthropic API Key를 먼저 입력해주세요.")
            elif not student_name.strip():
                st.error("학생 이름을 입력해주세요.")
            elif not record_text.strip():
                st.error("생활기록부 내용을 입력해주세요.")
            else:
                # 추출 단계
                with st.spinner("📖 이론과 도서를 추출하는 중..."):
                    try:
                        extracted = extract_theories_and_books(record_text, anthropic_key)
                        theories = extracted.get("theories", [])
                        books = extracted.get("books", [])
                        st.session_state["theories"] = theories
                        st.session_state["books"] = books
                    except Exception as e:
                        st.error(f"추출 실패: {e}")
                        theories, books = [], []

                if theories or books:
                    # 추천 단계
                    with st.spinner("🎯 학과를 추천하는 중..."):
                        try:
                            recommendations = recommend_majors(theories, books, anthropic_key)
                            st.session_state["recommendations"] = recommendations
                        except Exception as e:
                            st.error(f"추천 실패: {e}")
                            recommendations = []

                    # DB 저장
                    student_id = save_student(student_name, record_text)
                    save_extracted_items(student_id, theories, books)
                    if recommendations:
                        save_recommendations(student_id, recommendations)
                    st.session_state["student_id"] = student_id
                    st.session_state["student_name"] = student_name
                    st.session_state["credentials_json"] = credentials_json
                    st.success("✅ 분석 완료! 결과가 DB에 저장되었습니다.")
                else:
                    st.warning("이론 또는 도서를 추출하지 못했습니다. 생기부 내용을 확인해주세요.")

        # 결과 표시 ──────────────────────────────────────────────
        if "theories" in st.session_state and "books" in st.session_state:
            theories = st.session_state["theories"]
            books = st.session_state["books"]
            recommendations = st.session_state.get("recommendations", [])

            # 추출 결과
            res_col1, res_col2 = st.columns(2)
            with res_col1:
                st.markdown(f"**📚 추출된 이론 ({len(theories)}개)**")
                if theories:
                    for t in theories:
                        with st.expander(f"• {t['name']}"):
                            st.caption(t.get("context", ""))
                else:
                    st.info("추출된 이론 없음")

            with res_col2:
                st.markdown(f"**📖 추출된 도서 ({len(books)}개)**")
                if books:
                    for b in books:
                        with st.expander(f"• {b['name']}"):
                            st.caption(b.get("context", ""))
                else:
                    st.info("추출된 도서 없음")

            st.divider()

            # 학과 추천 결과
            if recommendations:
                st.markdown("**🎯 추천 학과 TOP 5**")
                for i, rec in enumerate(recommendations, 1):
                    score = rec.get("score", 0)
                    bar_color = "🟢" if score >= 80 else "🟡" if score >= 60 else "🔴"
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{i}위. {rec.get('major', '')}**")
                            st.caption(rec.get("reason", ""))
                            if rec.get("related_theories"):
                                st.caption(f"관련 이론: {', '.join(rec['related_theories'])}")
                            if rec.get("related_books"):
                                st.caption(f"관련 도서: {', '.join(rec['related_books'])}")
                        with c2:
                            st.metric("적합도", f"{bar_color} {score}점")

            # 구글 시트 내보내기 ──────────────────────────────────
            st.divider()
            if not SHEETS_AVAILABLE:
                st.warning("⚠️ Google Sheets 라이브러리를 불러올 수 없습니다. 환경 설정을 확인해주세요.")
            elif use_sheets:
                if st.button("📊 구글 시트로 내보내기", use_container_width=True):
                    creds = st.session_state.get("credentials_json")
                    if not creds:
                        st.error("사이드바에서 서비스 계정 JSON 파일을 업로드해주세요.")
                    else:
                        with st.spinner("구글 시트 생성 중..."):
                            try:
                                sheet_url = create_recommendation_sheet(
                                    creds,
                                    st.session_state.get("student_name", "학생"),
                                    theories,
                                    books,
                                    recommendations,
                                )
                                st.success("✅ 구글 시트가 생성되었습니다!")
                                st.link_button("📊 구글 시트 열기", sheet_url)
                            except Exception as e:
                                st.error(f"구글 시트 생성 실패: {e}")
            else:
                st.info("💡 사이드바에서 '구글 시트 내보내기 사용'을 켜면 결과를 구글 시트로 내보낼 수 있습니다.")

# ════════════════════════════════════════════════════════════════════
# 탭 2: 분석 기록
# ════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📋 저장된 분석 기록")
    students = get_all_students()

    if not students:
        st.info("아직 분석된 학생이 없습니다. '새 분석' 탭에서 생기부를 분석해보세요.")
    else:
        for student in students:
            sid, sname, screated = student
            with st.expander(f"**{sname}** | {screated[:16]}"):
                _, items, recs = get_student_data(sid)
                theories_hist = [i for i in items if i[0] == "theory"]
                books_hist = [i for i in items if i[0] == "book"]

                hcol1, hcol2 = st.columns(2)
                with hcol1:
                    st.markdown(f"**📚 이론 ({len(theories_hist)}개)**")
                    for item in theories_hist:
                        st.markdown(f"- {item[1]}")
                with hcol2:
                    st.markdown(f"**📖 도서 ({len(books_hist)}개)**")
                    for item in books_hist:
                        st.markdown(f"- {item[1]}")

                if recs:
                    st.markdown("**🎯 추천 학과**")
                    df = pd.DataFrame(recs, columns=["학과", "점수", "추천 이유"])
                    st.dataframe(df, hide_index=True, use_container_width=True)

                if use_sheets and credentials_json:
                    if st.button("📊 구글 시트로 내보내기", key=f"export_{sid}"):
                        theories_export = [{"name": i[1], "context": i[2]} for i in theories_hist]
                        books_export = [{"name": i[1], "context": i[2]} for i in books_hist]
                        recs_export = [{"major": r[0], "score": r[1], "reason": r[2]} for r in recs]
                        with st.spinner("구글 시트 생성 중..."):
                            try:
                                url = create_recommendation_sheet(
                                    credentials_json, sname,
                                    theories_export, books_export, recs_export
                                )
                                st.success("✅ 생성 완료!")
                                st.link_button("📊 시트 열기", url)
                            except Exception as e:
                                st.error(f"실패: {e}")

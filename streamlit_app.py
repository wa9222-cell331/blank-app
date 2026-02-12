import re
from dataclasses import dataclass

import pandas as pd
import streamlit as st
try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

st.set_page_config(page_title="생활기록부 분석 대시보드", page_icon="📘", layout="wide")

st.title("📘 생활기록부 기반 성장 피드백 대시보드")
st.caption("PDF 생활기록부를 업로드하면 영역별 강점/보완점과 다음 활동 제안을 확인할 수 있습니다.")


SECTION_PATTERNS = {
    "자율활동": r"자율활동",
    "동아리활동": r"동아리활동|동아리",
    "진로활동": r"진로활동|진로",
    "봉사활동": r"봉사활동|봉사",
    "독서활동": r"독서활동|독서",
    "세부능력특기사항": r"세부능력.*특기사항|세특",
    "행동특성종합의견": r"행동특성.*종합의견",
}

COMPETENCIES = {
    "주도성": {
        "positive": ["주도", "기획", "스스로", "리더", "주체"],
        "negative": ["소극", "지시", "수동"],
        "activities": [
            "학급/동아리 프로젝트에서 일정 관리 역할 맡기",
            "월 1회 개인 탐구 주제를 정해 결과 공유하기",
        ],
    },
    "협업역량": {
        "positive": ["협력", "소통", "배려", "팀", "공동"],
        "negative": ["갈등", "충돌", "개별", "독단"],
        "activities": [
            "팀 기반 메이커/연구 활동 참여 후 회고 기록",
            "토론 활동에서 찬반 모두 요약하는 퍼실리테이터 경험",
        ],
    },
    "탐구심": {
        "positive": ["탐구", "분석", "실험", "질문", "심화"],
        "negative": ["피상", "단순", "암기"],
        "activities": [
            "교과 연계 미니 리서치(문제 정의→자료 조사→발표) 수행",
            "관심 분야 독서 후 비판적 서평 작성",
        ],
    },
    "진로명확성": {
        "positive": ["진로", "목표", "계획", "로드맵", "전공"],
        "negative": ["미정", "불분명", "막연"],
        "activities": [
            "희망 전공 관련 직업인 인터뷰 또는 멘토링 참여",
            "학기별 진로 로드맵(교과·비교과·포트폴리오) 업데이트",
        ],
    },
}


@dataclass
class AnalysisResult:
    section_summary: pd.DataFrame
    competency_scores: pd.DataFrame
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


def extract_text_from_pdf(uploaded_file) -> str:
    if PdfReader is None:
        raise RuntimeError("PDF 분석을 위해 pypdf 설치가 필요합니다. (pip install pypdf)")

    reader = PdfReader(uploaded_file)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def split_sections(text: str) -> dict[str, str]:
    normalized = re.sub(r"\s+", " ", text)
    positions = []

    for section, pattern in SECTION_PATTERNS.items():
        match = re.search(pattern, normalized)
        if match:
            positions.append((match.start(), section))

    if not positions:
        return {"전체": normalized}

    positions.sort()
    sections = {}

    for idx, (start, section) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(normalized)
        sections[section] = normalized[start:end].strip()

    return sections


def score_competencies(text: str) -> pd.DataFrame:
    rows = []
    for competency, cfg in COMPETENCIES.items():
        pos = sum(text.count(word) for word in cfg["positive"])
        neg = sum(text.count(word) for word in cfg["negative"])
        raw = pos - neg
        score = max(0, min(100, 50 + raw * 10))
        rows.append(
            {
                "역량": competency,
                "긍정 신호": pos,
                "보완 신호": neg,
                "점수": score,
            }
        )
    return pd.DataFrame(rows).sort_values("점수", ascending=False)


def analyze_student_record(text: str) -> AnalysisResult:
    sections = split_sections(text)

    section_rows = []
    for name, content in sections.items():
        section_rows.append(
            {
                "영역": name,
                "글자 수": len(content),
                "핵심 문장": content[:120] + ("..." if len(content) > 120 else ""),
            }
        )
    section_df = pd.DataFrame(section_rows).sort_values("글자 수", ascending=False)

    competency_df = score_competencies(text)

    strengths = competency_df["역량"].head(2).tolist()
    weaknesses = competency_df.sort_values("점수").head(2)["역량"].tolist()

    recommendations = []
    for competency in weaknesses:
        recommendations.extend(COMPETENCIES[competency]["activities"])

    return AnalysisResult(
        section_summary=section_df,
        competency_scores=competency_df,
        strengths=strengths,
        weaknesses=weaknesses,
        recommendations=recommendations,
    )


with st.sidebar:
    st.header("업로드")
    uploaded_file = st.file_uploader("생활기록부 PDF를 선택하세요", type=["pdf"])
    st.info("※ 민감한 개인정보는 업로드 전에 가급적 비식별화하세요.")

if uploaded_file is None:
    st.markdown(
        """
        ### 사용 방법
        1. 좌측에서 PDF 생활기록부 파일을 업로드합니다.
        2. 영역별 텍스트량과 핵심 문장을 확인합니다.
        3. 역량 점수 기반 강점/보완점 및 추천 활동을 확인합니다.

        > 이 도구는 키워드 기반 1차 분석용이며, 최종 평가는 교사·상담자 검토가 필요합니다.
        """
    )
else:
    try:
        text = extract_text_from_pdf(uploaded_file)
        result = analyze_student_record(text)

        left, right = st.columns([1, 1])
        with left:
            st.subheader("영역별 요약")
            st.dataframe(result.section_summary, use_container_width=True, hide_index=True)

        with right:
            st.subheader("역량 점수")
            st.bar_chart(result.competency_scores.set_index("역량")["점수"])
            st.dataframe(result.competency_scores, use_container_width=True, hide_index=True)

        s1, s2 = st.columns(2)
        with s1:
            st.subheader("강점")
            for item in result.strengths:
                st.success(f"{item} 역량이 상대적으로 높습니다.")

        with s2:
            st.subheader("보완 필요")
            for item in result.weaknesses:
                st.warning(f"{item} 역량 보완 활동을 추천합니다.")

        st.subheader("다음 활동 제안")
        for idx, rec in enumerate(result.recommendations, start=1):
            st.markdown(f"{idx}. {rec}")

    except Exception as exc:
        st.error(f"PDF를 처리하는 중 오류가 발생했습니다: {exc}")

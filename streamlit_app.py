import io
import re
import json
import time
import os
import urllib.request
import warnings
import logging
from typing import Dict, Any, List

import pandas as pd
import streamlit as st
from pypdf import PdfReader
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader
import google.generativeai as genai

logger = logging.getLogger(__name__)

# -----------------------------
# 0. 기본 설정
# -----------------------------
warnings.filterwarnings("ignore")
st.set_page_config(page_title="학종 강선생 - AI 컨설턴트", page_icon="🎓", layout="wide")

# -----------------------------
# 1. 운영/비용 방어 설정
# -----------------------------
MAX_UPLOAD_MB = 25
MAX_SCAN_PAGES = 5
SCAN_TEXT_MIN_LEN = 100
PDF_RENDER_ZOOM = 2.0
MAX_CALLS_PER_SESSION = 10
RETRY_ON_FAILURE = 1
MAX_TEXT_CHARS = 80_000  # Gemini 전송 텍스트 최대 길이 (토큰 폭주 방지)

# -----------------------------
# 2. 프롬프트 데이터 (평가 기준 및 제외 설정)
# -----------------------------
NEGATIVE_FEEDBACK_GUIDELINES = """
너는 입학사정관들의 '부정 평가 사례집'을 완벽하게 숙지한 생기부 컨설턴트야.
아래의 기준을 엄격하게 적용해.
[대학별 부정 평가 핵심 기준]
1. 학업역량: 단순 성실함이나 태도 강조는 감점. 구체적 탐구 과정과 사고력이 드러나야 함.
2. 진로역량: 전공 관련 키워드 단순 나열은 감점. 깊이 있는 탐구와 확장이 보여야 함.
3. 공동체역량: 단순 직책 수행이나 봉사 시간 나열은 감점. 구체적 기여와 변화를 이끈 경험이 중요함.
"""

IGNORE_TEXT_INSTRUCTION = """
[중요: 평가 제외 대상]
아래 영역은 학생부 종합전형 평가 트렌드에 따라 **평가에서 완전히 제외**하고 분석하지 마.
1. 3. 수상경력
2. 4. 자격증 및 인증 취득상황
3. 7. 독서활동상황 (단, 세특이나 창체에 녹아있는 독서 연계 활동은 평가 포함)
4. "공공기관의 정보공개에 관한 법률" 관련 비공개 문구
오직 **'교과세부능력 및 특기사항(세특)', '창의적 체험활동(자율/동아리/진로)', '행동특성 및 종합의견'** 위주로 분석해.
"""

SETEUK_REWRITE_INSTRUCTION = """
### [세특 첨삭 마스터 지침: 최상위권 대학 학업역량 강조]
분석 결과 중 **가장 보완이 필요한(학업 역량이 드러나지 않은) 세특 문항 하나를 선정**하여, 아래 '학업 역량 및 계열 적합성 분석 전문가'의 기준에 맞춰 1,500바이트(공백 포함 약 500자) 내외로 다시 작성(Rewriting)하라.
**1. 작성 핵심 전략 (Focus: Academic Excellence)**
* **교과 연계성:** 모든 활동의 시작점은 '교과서 개념'이어야 함. 수업 시간에 배운 개념에 대한 **지적 호기심**이 활동의 동기가 되었음을 명시.
* **학업 역량의 구체화:**
    * 비판적 사고: 기존 이론의 한계나 조건 분석.
    * 심화 탐구: 논문, 전문 도서, 수식/매커니즘을 통한 깊이 있는 탐구.
    * 융합적 사고: 개념의 타 분야 적용 및 실생활 문제 해결.
* **계열별 사고 방식:**
    * 자연/공학/의학: 인과관계, 데이터 추론, 가설 검증, 수리적 모델링, 오차 분석.
    * 인문/사회: 맥락 해석, 텍스트 이면 분석, 가치 판단의 논리적 근거, 통계 해석.
**2. 글의 구조 (3단 논법)**
1.  **동기 (교과 심화):** "[단원명] 수업 중 ~에 대해 학습하며 ~한 의문을 가짐"
2.  **과정 (탐구의 치열함):** 학술지, 데이터, 실험 등을 통해 답을 찾는 **논리적 사고 과정**을 디테일하게 묘사 (변인 통제, 상반된 관점 비교 등).
3.  **결과 및 발전:** 도출한 자신만의 인사이트와 이것이 후속 탐구로 이어짐을 서술.
**3. 필수 준수 사항**
* **진로 강박 탈피:** 학과명 언급보다 해당 분야의 **기초 소양(분석력, 통찰력)**을 보여주는 데 주력.
* **팩트 위주 서술:** "열정적임" 같은 형용사 배제. **무엇을 읽고, 계산하고, 도출했는지** 동사 위주로.
* **문체:** '~함', '~임' 등의 명료한 개조식.
"""

# -----------------------------
# 3. 유틸리티
# -----------------------------
def ensure_session_counters():
    if "call_count" not in st.session_state:
        st.session_state["call_count"] = 0

def bump_call_count():
    st.session_state["call_count"] += 1

def can_call_model() -> bool:
    ensure_session_counters()
    return st.session_state["call_count"] < MAX_CALLS_PER_SESSION

def file_size_mb(uploaded_file) -> float:
    return len(uploaded_file.getvalue()) / (1024 * 1024)

def configure_gemini() -> bool:
    api_key = st.secrets.get("GEMINI_API_KEY", None)
    if not api_key:
        if "GEMINI_API_KEY" in st.session_state:
            api_key = st.session_state["GEMINI_API_KEY"]
        else:
            api_key = st.sidebar.text_input("Google Gemini API Key", type="password")
            st.session_state["GEMINI_API_KEY"] = api_key

    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False

# PII 마스킹
PII_PATTERNS = [
    (r"\b010[-\s]?\d{4}[-\s]?\d{4}\b", "[전화번호]"),
    (r"\b\d{6}[-\s]?[1-4]\d{6}\b", "[주민번호]"),
]

def mask_pii(text: str) -> str:
    masked = text
    for pat, repl in PII_PATTERNS:
        masked = re.sub(pat, repl, masked)
    return masked

def truncate_text(text: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    """Gemini 컨텍스트 초과를 방지하기 위해 텍스트를 잘라냄."""
    if len(text) <= max_chars:
        return text
    logger.warning("텍스트 길이 %d → %d로 잘림", len(text), max_chars)
    return text[:max_chars] + "\n\n...(이하 생략: 원문이 너무 길어 잘렸습니다)..."

def extract_json_safely(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    t = t.replace("```json", "").replace("```", "").strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start:end+1]
    t = re.sub(r",\s*([}\]])", r"\1", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError as e:
        logger.error("JSON 파싱 실패: %s / 원문 앞 200자: %s", e, t[:200])
        return {"error": f"AI 응답을 JSON으로 변환하지 못했습니다: {e}"}

# 모델 자동 선택 — 세션 내 1회만 조회하여 API 호출 절약
def get_best_available_model() -> str:
    # 이미 조회한 결과가 있으면 재사용
    if "cached_model_name" in st.session_state:
        return st.session_state["cached_model_name"]

    selected = "gemini-1.5-flash"  # 기본 폴백
    try:
        models = [
            m.name for m in genai.list_models()
            if 'generateContent' in m.supported_generation_methods
        ]
        # 우선순위: 3.0 → 2.0-flash → 2.0-pro → 1.5-flash → 1.5-pro
        for prefix in ("gemini-3.0", "gemini-3", "gemini-2.0-flash",
                        "gemini-2.0-pro", "gemini-1.5-flash", "gemini-1.5-pro"):
            match = next((m for m in models if prefix in m), None)
            if match:
                selected = match
                break
        else:
            if models:
                selected = models[0]
    except Exception as e:
        logger.warning("모델 목록 조회 실패, 기본 모델 사용: %s", e)

    st.session_state["cached_model_name"] = selected
    return selected

# -----------------------------
# 4. PDF 처리
# -----------------------------
def extract_text_pypdf(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        text = []
        for p in reader.pages:
            text.append(p.extract_text() or "")
        return "\n".join(text).strip()
    except Exception as e:
        logger.error("pypdf 텍스트 추출 실패: %s", e)
        return ""

def render_pdf_to_images(file_bytes: bytes) -> List[Dict[str, Any]]:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        logger.error("PDF 열기 실패: %s", e)
        return []

    images = []
    pages_to_scan = min(len(doc), MAX_SCAN_PAGES)

    for i in range(pages_to_scan):
        try:
            page = doc.load_page(i)
            pix = page.get_pixmap(matrix=fitz.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM))
            img_bytes = pix.tobytes("png")
            if img_bytes:
                images.append({"mime_type": "image/png", "data": img_bytes})
        except Exception as e:
            logger.warning("PDF %d페이지 렌더링 실패: %s", i + 1, e)
    return images

# -----------------------------
# 5. Gemini 프롬프트
# -----------------------------
def get_prompt(mode: str) -> str:
    base = f"""
    너는 입학사정관이자 생기부 컨설팅 전문가야. 제공된 자료를 분석해줘.
    {NEGATIVE_FEEDBACK_GUIDELINES}
    {IGNORE_TEXT_INSTRUCTION}

    [출력 규칙]
    - 반드시 유효한 JSON 형식 하나만 반환.
    - 코드블록, 설명 금지.
    """

    if mode == "grade":
        return base + """
        [요청] 성적표 이미지/텍스트에서 성적 데이터를 추출해.
        [규칙] 등급이 산출되는 과목(석차등급 1~9)만 추출.
        [출력 JSON] {"grades": [{"grade": 1, "semester": 1, "subject": "과목", "units": 4, "rank": 2}]}
        """
    elif mode == "analysis":
        return base + f"""
        [요청]
        1. 3대 역량(학업/진로/공동체)을 비판적으로 분석해.
        2. 학생부에서 발견된 키워드를 바탕으로 이를 보완할 수 있는 심화 활동 2가지를 추천해. (논문 개념 적용, 도서 추천)
        3. '세특 첨삭 마스터'로서 가장 부족한 역량이 드러난 문장을 하나 골라 수정해.
        {SETEUK_REWRITE_INSTRUCTION}
        [출력 JSON 구조]
        {{
            "scores": {{ "academic": "상/중/하", "career": "상/중/하", "community": "상/중/하" }},
            "analysis": {{
                "academic_critique": "- 비판점1\\n- 비판점2",
                "career_critique": "- ...",
                "community_critique": "- ..."
            }},
            "lacking_competency": "가장 부족한 역량(예: 탐구력)",
            "improvements": [
                {{"section": "영역명", "original_text": "원문", "diagnosis": "진단", "suggestion": "수정안"}}
            ],
            "complementary_activities": [
                {{
                    "type": "논문 기반 실생활 탐구",
                    "topic": "구체적인 탐구 주제 명",
                    "rationale": "추천 이유와 생기부 키워드와의 연관성 설명"
                }},
                {{
                    "type": "심화 도서 추천",
                    "title": "도서명 (저자)",
                    "rationale": "추천 이유와 이를 통해 얻을 수 있는 통찰 설명"
                }}
            ],
            "seteuk_rewrite_master": {{
                "weak_point": "발견된 약점 (예: 과정 없이 결과만 나열)",
                "original_sentence": "원문 문장",
                "rewritten_sentence": "수정된 명품 세특 문장 (동기-과정-심화-후속활동이 드러나게 500자 내외)",
                "master_comment": "첨삭 마스터의 한마디 (왜 이렇게 고쳤는지)"
            }}
        }}
        """
    return base

# 재시도 불필요한 에러 키워드 (API 키 오류, 권한 문제 등)
_NON_TRANSIENT_ERRORS = ("invalid api key", "permission", "quota", "forbidden", "401", "403")

def call_gemini(parts: List[Any]) -> Dict[str, Any]:
    model_name = get_best_available_model()
    try:
        model = genai.GenerativeModel(model_name)
    except Exception as e:
        return {"error": f"모델 초기화 실패 ({model_name}): {e}"}

    cfg = {"temperature": 0.2, "response_mime_type": "application/json"}

    last_error = ""
    for attempt in range(RETRY_ON_FAILURE + 1):
        try:
            resp = model.generate_content(parts, generation_config=cfg)
            return extract_json_safely(resp.text)
        except Exception as e:
            last_error = str(e)
            lower_err = last_error.lower()
            # 인증/권한/할당량 에러는 재시도해도 소용없으므로 즉시 중단
            if any(kw in lower_err for kw in _NON_TRANSIENT_ERRORS):
                logger.error("비일시적 에러로 재시도 중단: %s", last_error)
                break
            if attempt < RETRY_ON_FAILURE:
                time.sleep(2)

    return {"error": f"API 호출 실패 (모델: {model_name}): {last_error}"}

# -----------------------------
# 6. PDF 리포트 생성
# -----------------------------
@st.cache_resource
def get_korean_font():
    font_name = "NanumGothic"
    font_file = "NanumGothic.ttf"
    if not os.path.exists(font_file):
        url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        try:
            urllib.request.urlretrieve(url, font_file)
        except Exception as e:
            logger.warning("폰트 다운로드 실패: %s", e)
            return "Helvetica", False
    try:
        pdfmetrics.registerFont(TTFont(font_name, font_file))
        return font_name, True
    except Exception as e:
        logger.warning("폰트 등록 실패: %s", e)
        return "Helvetica", False

def create_pdf_report(analysis_data: Dict[str, Any], lacking_area: str) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    font_name, success = get_korean_font()

    # 로고 삽입
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        try:
            logo_img = ImageReader(logo_path)
            c.drawImage(logo_img, width - 80, height - 80, width=50, height=50, mask='auto')
        except Exception as e:
            logger.warning("로고 삽입 실패: %s", e)

    c.setFont(font_name, 12)
    y = height - 50

    c.setFont(font_name, 16)
    c.drawString(50, y, "AI 생기부 정밀 진단 리포트")
    y -= 20

    c.setFont(font_name, 10)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawString(50, y, "Provided by 학종 강선생")
    c.setFillColorRGB(0, 0, 0)
    y -= 40

    if not success:
        c.drawString(50, y, "Warning: Korean font download failed. Text may appear broken.")
        y -= 20

    c.setFont(font_name, 12)
    c.drawString(50, y, f"■ 가장 시급한 보완 역량: {lacking_area}")
    y -= 30

    scores = analysis_data.get("scores", {})
    score_str = f"학업: {scores.get('academic','-')} | 진로: {scores.get('career','-')} | 공동체: {scores.get('community','-')}"
    c.drawString(50, y, f"■ 역량 진단: {score_str}")
    y -= 40

    # 세특 첨삭 마스터
    rewrite = analysis_data.get("seteuk_rewrite_master", {})
    if rewrite:
        c.setFont(font_name, 14)
        c.drawString(50, y, "■ 세특 첨삭 마스터의 Rewriting")
        y -= 25
        c.setFont(font_name, 10)
        c.drawString(60, y, f"약점 진단: {rewrite.get('weak_point', '')}")
        y -= 20
        c.drawString(60, y, f"원문: {rewrite.get('original_sentence', '')[:60]}...")
        y -= 20
        c.setFont(font_name, 10)
        c.setFillColorRGB(0, 0, 1)

        suggestion = rewrite.get('rewritten_sentence', '')
        chars_per_line = 65
        lines = [suggestion[i:i+chars_per_line] for i in range(0, len(suggestion), chars_per_line)]

        c.drawString(60, y, f"수정안: {lines[0] if lines else ''}")
        y -= 15
        for line in lines[1:5]:
             c.drawString(60, y, f"       {line}")
             y -= 15

        c.setFillColorRGB(0, 0, 0)
        y -= 30

    if y < 150:
        c.showPage()
        y = height - 50

    c.setFont(font_name, 14)
    c.drawString(50, y, "■ 보완을 위한 추천 심화 활동")
    y -= 25
    c.setFont(font_name, 10)

    activities = analysis_data.get("complementary_activities", [])
    for act in activities:
        c.drawString(60, y, f"[{act.get('type')}] {act.get('topic') or act.get('title')}")
        y -= 15
        rationale = act.get('rationale', '')
        if len(rationale) > 70:
            rationale = rationale[:70] + "..."
        c.drawString(70, y, f"- {rationale}")
        y -= 25

        if y < 80:
            c.showPage()
            c.setFont(font_name, 10)
            y = height - 50

    c.setFont(font_name, 8)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(width / 2, 30, "ⓒ 학종 강선생 - 무단 배포 금지")
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

# -----------------------------
# 7. Main UI
# -----------------------------
try:
    with st.sidebar:
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            st.image(logo_path, width=150)
        st.markdown("### **학종 강선생**")
        st.caption("AI 기반 생활기록부 정밀 진단 솔루션")
        st.divider()

    st.title("🎓 AI 생기부 컨설턴트 Pro")
    st.caption("수상/독서/자격증을 제외하고, **세특과 창체**를 중심으로 정밀 진단합니다.")

    ensure_session_counters()

    with st.sidebar:
        st.header("설정 및 업로드")
        ready = configure_gemini()
        if not ready:
            st.warning("⚠️ Gemini API Key 입력 필요")

        st.divider()
        mode = st.radio("분석 모드", ["성적표 분석 (내신)", "생기부 정밀 진단"])

        if mode.startswith("성적"):
            uploaded_file = st.file_uploader("성적표 이미지", type=["png", "jpg", "jpeg"])
        else:
            uploaded_file = st.file_uploader("생기부 PDF", type=["pdf"])

        st.divider()
        remaining = MAX_CALLS_PER_SESSION - st.session_state["call_count"]
        st.write(f"남은 분석 횟수: {remaining} / {MAX_CALLS_PER_SESSION}")
        st.divider()
        st.caption("ⓒ 학종 강선생 All rights reserved.")

    if uploaded_file and ready:
        if file_size_mb(uploaded_file) > MAX_UPLOAD_MB:
            st.error(f"파일 크기 초과 ({MAX_UPLOAD_MB}MB 제한)")
            st.stop()

        if not can_call_model():
            st.error("세션 호출 한도 초과. 새로고침하세요.")
            st.stop()

        if st.button("🚀 분석 시작", type="primary"):
            bump_call_count()

            # A. 성적표 분석
            if mode.startswith("성적"):
                with st.spinner("성적표 이미지를 분석 중입니다..."):
                    img_bytes = uploaded_file.getvalue()
                    mime = "image/png" if uploaded_file.name.endswith(".png") else "image/jpeg"
                    parts = [get_prompt("grade"), {"mime_type": mime, "data": img_bytes}]

                    result = call_gemini(parts)

                    if "grades" in result:
                        df = pd.DataFrame(result["grades"])
                        if not df.empty:
                            st.success("분석 완료!")
                            st.dataframe(df)
                        else:
                            st.warning("데이터 추출 실패")
                    else:
                        st.error(f"분석 오류: {result.get('error', '알 수 없는 오류')}")

            # B. 생기부 정밀 진단
            else:
                with st.spinner("세특과 창체를 집중 분석하고 솔루션을 생성 중입니다..."):
                    file_bytes = uploaded_file.getvalue()
                    text_content = extract_text_pypdf(file_bytes)

                    parts = []
                    prompt = get_prompt("analysis")

                    if len(text_content) > SCAN_TEXT_MIN_LEN:
                        st.toast("텍스트 모드로 분석합니다.", icon="📄")
                        masked_text = mask_pii(text_content)
                        trimmed_text = truncate_text(masked_text)
                        parts = [prompt, f"\n[생기부 텍스트]\n{trimmed_text}"]
                    else:
                        st.toast("스캔본(이미지)으로 분석합니다.", icon="📸")
                        images = render_pdf_to_images(file_bytes)
                        if not images:
                            st.error("PDF 변환 실패")
                            st.stop()
                        parts = [prompt, "\n[생기부 스캔 이미지]"]
                        parts.extend(images)

                    result = call_gemini(parts)

                    if "error" in result:
                        st.error(f"분석 중 오류 발생: {result.get('error')}")
                    else:
                        st.success("진단 완료!")

                        tab1, tab2 = st.tabs(["🚨 역량 정밀 진단", "✨ 강선생 솔루션"])

                        scores = result.get("scores", {})
                        analysis = result.get("analysis", {})
                        lacking = result.get("lacking_competency", "정보 없음")

                        with tab1:
                            st.subheader("📊 3대 역량 분석")
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.info(f"학업역량: {scores.get('academic', '-')}")
                                st.markdown(analysis.get('academic_critique', '-'))
                            with c2:
                                st.info(f"진로역량: {scores.get('career', '-')}")
                                st.markdown(analysis.get('career_critique', '-'))
                            with c3:
                                st.info(f"공동체역량: {scores.get('community', '-')}")
                                st.markdown(analysis.get('community_critique', '-'))

                            st.divider()
                            st.error(f"🚨 **가장 시급한 보완 역량: {lacking}**")

                        with tab2:
                            st.subheader("🔥 세특 첨삭 마스터의 Rewriting")
                            st.caption("최상위권 대학 입학사정관의 시각으로 재구성한 '명품 세특'입니다.")

                            rewrite = result.get("seteuk_rewrite_master", {})
                            if rewrite:
                                with st.container(border=True):
                                    st.markdown(f"**🎯 약점 포인트:** {rewrite.get('weak_point')}")
                                    st.markdown(f"**❌ 원문:**")
                                    st.caption(rewrite.get('original_sentence'))
                                    st.divider()
                                    st.markdown(f"**✅ 강선생 수정안 (학업역량 강화):**")
                                    st.info(rewrite.get('rewritten_sentence'))
                                    st.markdown(f"**💡 마스터 코멘트:** {rewrite.get('master_comment')}")
                            else:
                                st.warning("첨삭 결과가 생성되지 않았습니다.")

                            st.divider()
                            st.subheader("📚 부족 역량 보완을 위한 활동 추천")
                            activities = result.get("complementary_activities", [])
                            if activities:
                                for act in activities:
                                    icon = "📖" if "도서" in act.get('type', '') else "🔬"
                                    with st.expander(f"{icon} [{act.get('type')}] {act.get('topic') or act.get('title')}"):
                                        st.write(f"**추천 이유:** {act.get('rationale')}")
                            else:
                                st.info("추천 활동 데이터가 없습니다.")

                            st.divider()
                            try:
                                pdf_data = create_pdf_report(result, lacking)
                                st.download_button(
                                    label="📄 강선생 리포트 다운로드 (PDF)",
                                    data=pdf_data,
                                    file_name="학종강선생_분석리포트.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            except Exception as e:
                                st.error(f"PDF 생성 실패: {e}")

    elif not uploaded_file:
        st.info("👈 파일을 업로드해주세요.")

except Exception as e:
    st.error(f"앱 실행 중 치명적인 오류가 발생했습니다: {e}")
    logger.exception("앱 치명적 오류")

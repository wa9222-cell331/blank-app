import io
import re
import json
import os
import time
import warnings
from typing import Dict, Any, List

import streamlit as st
import streamlit.components.v1 as components

import google.generativeai as genai
from pypdf import PdfReader
import fitz  # PyMuPDF
from json_repair import repair_json

# ============================================================
# 0. 기본 설정
# ============================================================
warnings.filterwarnings("ignore")
st.set_page_config(
    page_title="학종 강선생 - AI 생기부 컨설턴트",
    page_icon="🎓",
    layout="wide",
)

MAX_UPLOAD_MB = 25
MAX_SCAN_PAGES = 8
SCAN_TEXT_MIN_LEN = 100
PDF_RENDER_ZOOM = 2.0
MAX_RETRIES = 3

# ============================================================
# 1. 프롬프트 지침 데이터
# ============================================================
NEGATIVE_FEEDBACK_GUIDELINES = """
너는 입학사정관들의 '부정 평가 사례집'을 완벽하게 숙지한 생기부 컨설턴트야.

[대학별 부정 평가 핵심 기준]
1. 학업역량 — 단순 성실함이나 태도 강조 → 감점. 구체적 탐구 과정과 사고력이 드러나야 함.
2. 진로역량 — 전공 관련 키워드 단순 나열 → 감점. 깊이 있는 탐구와 확장이 보여야 함.
3. 공동체역량 — 단순 직책 수행 · 봉사 시간 나열 → 감점. 구체적 기여와 변화를 이끈 경험이 중요함.

[평가 척도]
- 상 : 입학사정관이 밑줄을 치며 감탄하는 수준
- 중 : 평균적이며 특별한 인상이 없는 수준
- 하 : 부정 평가 사례에 해당, 즉시 보완 필요
"""

IGNORE_TEXT_INSTRUCTION = """
[중요 — 평가 제외 대상]
1) 수상경력  2) 자격증 및 인증 취득상황  3) 독서활동 단순 목록  4) 정보공개법 비공개 문구
→ 오직 '교과세부능력 및 특기사항(세특)', '창의적 체험활동(창체)', '행동특성 및 종합의견(행특)' 위주로 분석.
"""

SETEUK_REWRITE_INSTRUCTION = """
### [세특 첨삭 마스터 지침 — 최상위 대학 입학사정관 수준]

가장 보완이 필요한 세특 문장 하나를 골라 **공백 포함 약 500자(1,500바이트 이내)**로 재작성하라.

#### 핵심 전략 (Focus: Academic Excellence)
특정 학과(전공)에 억지로 끼워 맞추는 서술을 지양하고, **교과 내용을 얼마나 깊이 있게 파고들었는지(학업 역량)**와 **해당 계열 특유의 사고력(계열 적합성)**을 강조하라.

- **교과 연계성 강화 (Curriculum Link):** 모든 활동의 시작점은 '교과서 개념'. 수업 시간에 배운 A개념에 대한 **지적 호기심**이 활동의 동기가 되었음을 명시.
- **학업 역량의 구체화 (Deepening):**
  - **비판적 사고:** 기존 이론의 조건이나 한계를 따져봄.
  - **심화 탐구:** 교과 수준을 넘어선 논문, 전문 도서, 원리(수식/메커니즘)를 찾아봄.
  - **융합적 사고:** 해당 개념을 타 분야나 실생활 문제 해결에 논리적으로 적용함.
- **계열별 사고 방식 (Field Mindset):**
  - **자연/공학/의학 계열:** 인과관계 분석, 데이터 기반 추론, 가설 설정 및 검증, 수리적 모델링, 오차 원인 분석.
  - **인문/사회 계열:** 사회적 맥락 해석, 텍스트의 이면 분석, 가치 판단의 논리적 근거 제시, 통계 자료의 해석.

#### 글의 구조 (3단 논법)
1. **동기 (교과 심화):** "[교과 단원명] 수업 중 ~에 대해 학습하며 ~한 의문을 가짐" 또는 "~의 원리를 더 깊이 이해하고자 함."
2. **과정 (탐구의 치열함):** 구체적인 매체(학술지, 심화 도서, 실험, 데이터)를 활용하여 답을 찾는 과정. **어떤 논리적 사고 과정**을 거쳤는지 디테일하게 묘사. (단순 검색이 아니라, 변인 통제를 고려하여 실험을 재설계하거나 상반된 관점의 자료를 비교 분석함)
3. **결과 및 발전 (학문적 성취):** 탐구를 통해 도출한 자신만의 결론(인사이트)을 제시하고, **지적 성장이나 후속 탐구**로 어떻게 이어졌는지 마무리.

#### 필수 준수 사항
- **진로 강박 탈피:** 희망 학과명을 직접 언급하기보다, 그 학과에서 요구하는 **'기초 소양(분석력, 통찰력)'**을 보여주는 데 주력.
- **팩트 위주 서술:** "열정적임", "뛰어남" 같은 형용사를 빼고, **무엇을 읽고, 무엇을 계산하고, 무엇을 도출했는지** 동사 위주로 서술.
- **문체:** '~함', '~임', '~을 도출함' 등의 명료한 개조식 문체.
"""

WRITING_STYLE_INSTRUCTION = """
[중요 — 서술 스타일 규칙]
1. **관찰자 시점 금지:** "OOO 학생은~", "학생의~", "이 학생은~", "해당 학생은~" 등 3인칭 관찰자 시점의 서술을 절대 하지 마라.
   - 활동·역량·성과 자체를 주어로 삼아 서술. 필요 시 주어 생략 가능.

2. **문단 분리:** 3문장 이상이 연속되면 반드시 의미 단위별로 문단을 나누어라.
   - 각 문단 사이에 줄바꿈(\\n\\n)을 삽입. 분량은 줄이지 말고, 가독성을 높이기 위한 문단 분리만 적용.

3. **문체 통일:** 분석 텍스트는 '~다', '~이다' 체. 추천/조언 부분은 '~하십시오', '~할 필요가 있다' 체.
"""

KEYWORD_INSTRUCTION = """
[핵심 키워드 작성 규칙]
- 단순 단어 나열 금지. 각 키워드는 **구체적이고 설명적인 복합어**로 작성.
- 가능하면 영문 부연 표기를 괄호로 포함.
- 3~5개 작성.

좋은 예시: "#간호정보학(Nursing_Informatics)", "#데이터드리븐_의사결정", "#기술기반_ESG전략", "#취약계층_의료접근성", "#에비던스기반_간호"
나쁜 예시: "#간호", "#데이터", "#ESG", "#의료", "#간호학"
"""

# ============================================================
# 2. 유틸리티 함수
# ============================================================
def get_best_available_model() -> str:
    try:
        models = [
            m.name for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
        ]
        for pref in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            for m in models:
                if pref in m:
                    return m
        if models:
            return models[0]
    except Exception:
        pass
    return "gemini-2.0-flash"


def configure_gemini() -> bool:
    api_key = st.secrets.get("GEMINI_API_KEY", st.session_state.get("GEMINI_API_KEY", ""))
    if not api_key:
        api_key = st.sidebar.text_input(
            "🔑 Google Gemini API Key",
            type="password",
            help="[Google AI Studio](https://aistudio.google.com/apikey)에서 무료로 발급 가능합니다.",
        )
        st.session_state["GEMINI_API_KEY"] = api_key
    if api_key:
        genai.configure(api_key=api_key)
        return True
    return False


def extract_json_safely(text: str) -> Dict[str, Any]:
    """JSON 파싱 시도 → 실패 시 json-repair로 자동 복구 후 재시도."""
    t = text.strip().replace("```json", "").replace("```", "").strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1 and end > start:
        t = t[start : end + 1]
    # 후행 쉼표 제거
    t = re.sub(r",\s*([}\]])", r"\1", t)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # json-repair 로 손상된 JSON 복구 후 재파싱
        repaired = repair_json(t, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        return json.loads(repair_json(t))


def render_pdf_to_images(file_bytes: bytes) -> List[Dict[str, Any]]:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    for i in range(min(len(doc), MAX_SCAN_PAGES)):
        page = doc.load_page(i)
        pix = page.get_pixmap(matrix=fitz.Matrix(PDF_RENDER_ZOOM, PDF_RENDER_ZOOM))
        img_bytes = pix.tobytes("png")
        if img_bytes:
            images.append({"mime_type": "image/png", "data": img_bytes})
    return images


def nl2br(text: str) -> str:
    """줄바꿈을 HTML 문단으로 변환"""
    if not text:
        return ""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    if len(paragraphs) <= 1:
        return text
    return "</p><p class='mt-2'>".join(paragraphs)


# ============================================================
# 3. 프롬프트 & API 호출
# ============================================================
def build_analysis_prompt(target_university: str, target_major: str) -> str:
    return f"""
너는 최고 수준의 입학사정관이자 '학종 강선생'이야.
{NEGATIVE_FEEDBACK_GUIDELINES}
{IGNORE_TEXT_INSTRUCTION}
{SETEUK_REWRITE_INSTRUCTION}
{WRITING_STYLE_INSTRUCTION}
{KEYWORD_INSTRUCTION}

학생의 지원 목표: {target_university} {target_major}

[출력 JSON 구조] — 반드시 아래 키를 **모두** 포함하여 **JSON만** 출력하라.
문단이 3문장 이상이면 반드시 \\n\\n 으로 문단을 나누어라.
"OOO 학생은~" 같은 관찰자 시점은 절대 쓰지 마라. 학생의 이름을 주어로 쓰지 마라.

{{
    "target_major": "{target_major}",
    "keywords": ["#구체적_복합키워드1(English)", "#구체적_복합키워드2", "#구체적_복합키워드3"],
    "scores": {{
        "academic": "상/중/하",
        "career": "상/중/하",
        "community": "상/중/하"
    }},
    "analysis": {{
        "academic_strength": "학업역량에서 긍정적으로 평가되는 부분만 서술. 관찰자 시점 금지. 문단 분리 적용. 2~3문단.",
        "academic_weakness": "학업역량에서 보완이 필요한 부분만 서술. 구체적 개선 방향 포함. 보완 사항이 없으면 빈 문자열. 1~2문단.",
        "career_strength": "진로역량의 강점만 서술. 관찰자 시점 금지. 문단 분리 적용. 2~3문단.",
        "career_weakness": "진로역량의 보완 필요 사항만 서술. 없으면 빈 문자열. 1~2문단.",
        "community_strength": "공동체역량의 강점만 서술. 관찰자 시점 금지. 문단 분리 적용. 2~3문단.",
        "community_weakness": "공동체역량의 보완 필요 사항만 서술. 없으면 빈 문자열. 1~2문단."
    }},
    "grade_analysis": {{
        "title": "성적 추이 분석 소제목",
        "content": "교과 등급 변화와 회복탄력성, 상승세 등에 대한 심층 분석. 문단 분리 적용."
    }},
    "subject_depth": {{
        "title": "교과 연계 심화 탐구 소제목",
        "content": "세특에서 보이는 학문적 깊이와 융합적 사고에 대한 분석. 문단 분리 적용."
    }},
    "vertical_connectivity": {{
        "yearly_flow": [
            {{"year": "1학년", "description": "1학년 때의 방향성 요약"}},
            {{"year": "2학년", "description": "2학년 전환/심화 요약"}},
            {{"year": "3학년(목표)", "description": "3학년에서 도달해야 할 방향 제시"}}
        ],
        "gap_analysis": "단절되거나 보완이 필요한 지점에 대한 분석. 문단 분리 적용."
    }},
    "killer_quotes": [
        {{"quote": "생기부에서 발췌한 인상적 문구 1", "source": "출처 (세특: 교과명 등)"}},
        {{"quote": "인상적 문구 2", "source": "출처"}},
        {{"quote": "인상적 문구 3", "source": "출처"}}
    ],
    "seteuk_rewrite_master": {{
        "target_subject": "첨삭 대상 교과목명",
        "weak_point": "발견된 약점 (예: 단순 나열, 깊이 부족, 탐구 동기 불명확 등)",
        "original_sentence": "원문 문장 그대로 발췌",
        "rewritten_sentence": "위의 세특 첨삭 마스터 지침을 철저히 따른 재작성. 3단 논법(동기→과정→결과). 개조식 문체(~함, ~임). 형용사 배제, 동사 위주. 500자 내외.",
        "master_comment": "수정 의도와 전략 코멘트. 어떤 점이 어떻게 개선되었는지 구체적으로."
    }},
    "complementary_activities": [
        {{
            "type": "세특용",
            "title": "활동 주제",
            "motive": "추천 동기 (관찰자 시점 금지)",
            "method": "구체적 실행 방법",
            "effect": "기대 효과"
        }},
        {{
            "type": "창체용",
            "title": "활동 주제",
            "motive": "추천 동기 (관찰자 시점 금지)",
            "method": "구체적 실행 방법",
            "effect": "기대 효과"
        }}
    ],
    "talent_match": {{
        "percentage": 75,
        "description": "{target_university} 인재상과의 매칭 분석. 관찰자 시점 금지. 문단 분리 적용.",
        "strengths": ["강점1", "강점2"],
        "gaps": [
            {{"name": "Gap 영역명", "description": "보완 필요 설명"}},
            {{"name": "Gap 영역명2", "description": "보완 필요 설명"}}
        ]
    }},
    "expert_comment": "학부모가 읽어도 이해할 수 있는 종합 전략 코멘트. 관찰자 시점 절대 금지. 3~4문장. 구체적이고 실행 가능한 조언."
}}
"""


def call_gemini(parts: List[Any]) -> Dict[str, Any]:
    """Gemini API 호출. JSON 파싱 실패 시 최대 MAX_RETRIES회 재시도."""
    model_name = get_best_available_model()
    model = genai.GenerativeModel(model_name)
    cfg = {"temperature": 0.25, "response_mime_type": "application/json"}

    last_error = ""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = model.generate_content(parts, generation_config=cfg)
            return extract_json_safely(resp.text)
        except (json.JSONDecodeError, ValueError) as e:
            last_error = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)  # 지수 백오프: 2s, 4s
        except Exception as e:
            # API 자체 오류는 즉시 반환
            return {"error": f"API 호출 실패 ({model_name}): {str(e)}"}

    return {"error": f"JSON 파싱 실패 ({MAX_RETRIES}회 시도, 모델: {model_name}): {last_error}"}


# ============================================================
# 4. HTML 보고서 생성 함수 (premium 템플릿)
# ============================================================
def build_html_report(data: Dict[str, Any], university: str, major: str) -> str:

    def score_color(s: str) -> str:
        s = s.strip()
        if s == "상":
            return "bg-emerald-100 text-emerald-700 border-emerald-200"
        elif s == "중":
            return "bg-amber-100 text-amber-700 border-amber-200"
        return "bg-red-100 text-red-700 border-red-200"

    scores = data.get("scores", {})
    analysis = data.get("analysis", {})
    grade_analysis = data.get("grade_analysis", {})
    subject_depth = data.get("subject_depth", {})
    vert = data.get("vertical_connectivity", {})
    rewrite = data.get("seteuk_rewrite_master", {})
    talent = data.get("talent_match", {})
    match_pct = talent.get("percentage", 75)

    # --- 키워드 배지 ---
    kw_styles = [
        "bg-brand-50 text-brand-800 border-brand-100",
        "bg-teal-50 text-teal-800 border-teal-100",
        "bg-slate-100 text-slate-800 border-slate-200",
        "bg-amber-50 text-amber-800 border-amber-100",
        "bg-violet-50 text-violet-800 border-violet-100",
    ]
    keywords_html = ""
    for i, kw in enumerate(data.get("keywords", [])):
        keywords_html += f'<span class="keyword-badge px-6 py-3 {kw_styles[i % len(kw_styles)]} border rounded-2xl font-bold text-lg">{kw}</span>\n'

    # --- 3대 역량 카드 (강점/보완 분리) ---
    competency_cards = ""
    comp_items = [
        ("📚", "학업역량", scores.get("academic", "-"),
         analysis.get("academic_strength", ""), analysis.get("academic_weakness", ""), "brand-500"),
        ("🚀", "진로역량", scores.get("career", "-"),
         analysis.get("career_strength", ""), analysis.get("career_weakness", ""), "accent-teal"),
        ("🤝", "공동체역량", scores.get("community", "-"),
         analysis.get("community_strength", ""), analysis.get("community_weakness", ""), "slate-500"),
    ]
    for icon, name, score, strength, weakness, border_c in comp_items:
        weakness_section = ""
        if weakness and weakness.strip():
            weakness_section = f"""
                <div class="pt-4 border-t border-slate-100">
                    <div class="flex items-center gap-1.5 mb-2">
                        <span class="w-2 h-2 bg-amber-500 rounded-full flex-shrink-0"></span>
                        <span class="text-xs font-bold text-amber-700 uppercase tracking-wide">보완해야 할 점</span>
                    </div>
                    <p class="text-sm text-slate-500 leading-relaxed">{nl2br(weakness)}</p>
                </div>"""

        competency_cards += f"""
        <div class="bg-white/80 p-6 rounded-2xl border-t-4 border-{border_c} shadow-sm">
            <div class="flex items-center justify-between mb-4">
                <h3 class="font-bold text-lg">{icon} {name}</h3>
                <span class="px-3 py-1 {score_color(score)} border rounded-full text-sm font-bold">{score}</span>
            </div>
            <div class="space-y-4">
                <div>
                    <div class="flex items-center gap-1.5 mb-2">
                        <span class="w-2 h-2 bg-emerald-500 rounded-full flex-shrink-0"></span>
                        <span class="text-xs font-bold text-emerald-700 uppercase tracking-wide">강점</span>
                    </div>
                    <p class="text-sm text-slate-600 leading-relaxed">{nl2br(strength)}</p>
                </div>
                {weakness_section}
            </div>
        </div>"""

    # --- 학년별 흐름 ---
    year_colors = ["text-slate-400", "text-brand-600", "text-accent-teal"]
    yearly_html = ""
    for i, item in enumerate(vert.get("yearly_flow", [])):
        c = year_colors[i % len(year_colors)]
        yearly_html += f'<li><span class="font-bold {c}">{item["year"]}:</span> {item["description"]}</li>\n'

    # --- 킬러 문구 ---
    quote_borders = ["border-brand-500", "border-accent-teal", "border-slate-400"]
    quote_labels = ["text-brand-600", "text-accent-teal", "text-slate-500"]
    quotes_html = ""
    for i, q in enumerate(data.get("killer_quotes", [])):
        quotes_html += f"""
        <div class="p-6 bg-slate-50 border-l-4 {quote_borders[i%3]} rounded-r-2xl italic text-slate-700">
            "{q.get('quote','')}"
            <div class="mt-2 text-xs font-bold {quote_labels[i%3]} uppercase tracking-widest">— {q.get('source','')}</div>
        </div>"""

    # --- 추천 활동 ---
    activities_html = ""
    for i, act in enumerate(data.get("complementary_activities", [])):
        if i % 2 == 0:
            badge_bg, label_c = "bg-brand-100 text-brand-700", "text-brand-600"
        else:
            badge_bg, label_c = "bg-accent-teal/10 text-accent-teal", "text-accent-teal"
        activities_html += f"""
        <div class="bg-white rounded-3xl p-8 shadow-xl border border-slate-100 flex flex-col">
            <div class="mb-6">
                <span class="px-3 py-1 {badge_bg} text-xs font-bold rounded-full uppercase">추천 활동 {i+1} ({act.get('type','')})</span>
                <h2 class="text-xl font-bold mt-3 text-slate-800">{act.get('title','')}</h2>
            </div>
            <div class="space-y-5 flex-grow text-sm">
                <div><h4 class="font-bold {label_c} mb-1 uppercase tracking-tighter text-xs">[동기]</h4><p class="text-slate-600">{nl2br(act.get('motive',''))}</p></div>
                <div><h4 class="font-bold {label_c} mb-1 uppercase tracking-tighter text-xs">[실행 방법]</h4><p class="text-slate-600">{nl2br(act.get('method',''))}</p></div>
                <div class="pt-4 border-t border-slate-50"><h4 class="font-bold {label_c} mb-1 uppercase tracking-tighter text-xs">[기대 효과]</h4><p class="text-slate-700 font-medium">{nl2br(act.get('effect',''))}</p></div>
            </div>
        </div>"""

    # --- Gap 카드 ---
    gaps_html = ""
    for i, gap in enumerate(talent.get("gaps", [])):
        gaps_html += f"""
        <div class="bg-slate-800 p-4 rounded-xl border border-slate-700">
            <span class="text-xs font-bold text-accent-teal uppercase block mb-1">Gap {i+1}</span>
            <span class="text-sm font-bold">{gap.get('name','')}</span>
            <p class="text-xs text-slate-500 mt-1 italic">{gap.get('description','')}</p>
        </div>"""

    # --- SVG 원형 게이지 계산 ---
    circumference = round(2 * 3.14159 * 58, 2)
    offset = round(circumference * (1 - match_pct / 100), 2)

    # --- 별 아이콘 ---
    star_svg = '<svg class="w-5 h-5 fill-current" viewBox="0 0 20 20"><path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/></svg>'
    stars = star_svg * 5

    # ========================
    # 최종 HTML 조립
    # ========================
    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>학생부 전략 보고서 | {university} {major}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700;900&family=Outfit:wght@400;600;800&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    colors: {{
                        brand: {{ 50:'#f0f9ff',100:'#e0f2fe',200:'#bae6fd',500:'#0ea5e9',600:'#0284c7',700:'#0369a1',800:'#075985',900:'#0c4a6e' }},
                        accent: {{ teal:'#14b8a6', gold:'#d4af37' }},
                    }},
                    fontFamily: {{ sans:['Noto Sans KR','sans-serif'], display:['Outfit','Noto Sans KR','sans-serif'] }},
                    animation: {{ 'fade-in-up':'fadeInUp 0.8s ease-out forwards', 'float':'float 6s ease-in-out infinite' }},
                    keyframes: {{
                        fadeInUp: {{ '0%':{{ opacity:'0', transform:'translateY(20px)' }}, '100%':{{ opacity:'1', transform:'translateY(0)' }} }},
                        float: {{ '0%,100%':{{ transform:'translateY(0)' }}, '50%':{{ transform:'translateY(-10px)' }} }}
                    }}
                }}
            }}
        }}
    </script>
    <style>
        body {{ background-color:#f8fafc; color:#1e293b; line-height:1.7; }}
        .glass-card {{ background:rgba(255,255,255,0.85); backdrop-filter:blur(12px); border:1px solid rgba(255,255,255,0.4); box-shadow:0 10px 30px -5px rgba(0,0,0,0.05); }}
        .keyword-badge {{ transition:all .3s cubic-bezier(.4,0,.2,1); }}
        .keyword-badge:hover {{ transform:translateY(-2px); box-shadow:0 4px 12px rgba(20,184,166,.2); }}
        @media print {{
            header {{ padding-top:2rem!important; padding-bottom:2rem!important; }}
            .no-print {{ display:none!important; }}
            .glass-card {{ box-shadow:none; border:1px solid #e2e8f0; }}
        }}
    </style>
</head>
<body class="antialiased">

    <header class="relative overflow-hidden pt-16 pb-24 md:pt-24 md:pb-32 bg-slate-900 text-white">
        <div class="absolute inset-0 opacity-20">
            <div class="absolute top-[-10%] left-[-10%] w-[40%] h-[60%] bg-brand-600 rounded-full blur-[120px] animate-float"></div>
            <div class="absolute bottom-[-10%] right-[-10%] w-[30%] h-[50%] bg-accent-teal rounded-full blur-[100px] opacity-50"></div>
        </div>
        <div class="container mx-auto px-6 relative z-10 text-center">
            <div class="inline-block px-4 py-1.5 mb-6 rounded-full bg-brand-600/20 border border-brand-500/30 text-brand-200 text-sm font-semibold tracking-wider uppercase animate-fade-in-up">
                학종 강선생 · Strategic Roadmap Report
            </div>
            <h1 class="text-4xl md:text-6xl font-display font-extrabold mb-6 tracking-tight animate-fade-in-up" style="animation-delay:0.1s">
                학생부 전략 보고서
            </h1>
            <p class="text-xl md:text-2xl text-slate-300 font-light max-w-2xl mx-auto animate-fade-in-up" style="animation-delay:0.2s">
                {university} {major} 맞춤형 심층 분석
            </p>
        </div>
    </header>

    <main class="container mx-auto px-6 -mt-16 relative z-20 pb-20">
        <div class="max-w-5xl mx-auto space-y-10">

            <div class="flex gap-4 justify-end no-print animate-fade-in-up" style="animation-delay:0.25s">
                <button onclick="window.print()" class="px-5 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-600 text-sm font-bold hover:bg-slate-50 transition flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z"/></svg>
                    인쇄 / PDF 저장
                </button>
            </div>

            <!-- 핵심 키워드 -->
            <section class="glass-card rounded-3xl p-8 md:p-10 animate-fade-in-up" style="animation-delay:0.3s">
                <div class="flex items-center gap-3 mb-8">
                    <div class="w-1.5 h-8 bg-accent-teal rounded-full"></div>
                    <h2 class="text-2xl font-bold text-slate-800">핵심 타겟 키워드</h2>
                </div>
                <div class="flex flex-wrap gap-4">{keywords_html}</div>
            </section>

            <!-- 01. 3대 핵심 역량 진단 -->
            <section class="glass-card rounded-3xl p-8 md:p-10 animate-fade-in-up" style="animation-delay:0.35s">
                <h2 class="text-xl font-bold text-brand-700 mb-6 flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                    01. 3대 핵심 역량 진단
                </h2>
                <div class="grid md:grid-cols-3 gap-6">{competency_cards}</div>
            </section>

            <!-- 02. 학업 역량 심층 -->
            <section class="glass-card rounded-3xl p-8 md:p-10 animate-fade-in-up" style="animation-delay:0.4s">
                <h2 class="text-xl font-bold text-brand-700 mb-6 flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                    02. 학업 역량의 질적 평가 (Academic Rigor)
                </h2>
                <div class="space-y-6">
                    <div class="bg-white/50 p-6 rounded-2xl border border-slate-100">
                        <h3 class="text-lg font-bold mb-3 text-slate-800">{grade_analysis.get('title', '성적 추이 및 회복 탄력성')}</h3>
                        <p class="text-slate-600">{nl2br(grade_analysis.get('content', ''))}</p>
                    </div>
                    <div class="bg-white/50 p-6 rounded-2xl border border-slate-100">
                        <h3 class="text-lg font-bold mb-3 text-slate-800">{subject_depth.get('title', '교과 연계 심화 탐구')}</h3>
                        <p class="text-slate-600">{nl2br(subject_depth.get('content', ''))}</p>
                    </div>
                </div>
            </section>

            <!-- 03. 전공 역량 -->
            <section class="glass-card rounded-3xl p-8 md:p-10 animate-fade-in-up" style="animation-delay:0.45s">
                <h2 class="text-xl font-bold text-brand-700 mb-6 flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/></svg>
                    03. 전공 역량 · 학년별 흐름 (Vertical Connectivity)
                </h2>
                <div class="grid md:grid-cols-2 gap-6">
                    <div class="bg-slate-50 p-6 rounded-2xl">
                        <h3 class="font-bold mb-4 text-slate-800 border-b pb-2">학년별 흐름 추적</h3>
                        <ul class="space-y-4 text-sm">{yearly_html}</ul>
                    </div>
                    <div class="bg-slate-50 p-6 rounded-2xl">
                        <h3 class="font-bold mb-4 text-slate-800 border-b pb-2">단절된 지점 및 보완점</h3>
                        <p class="text-sm text-slate-600">{nl2br(vert.get('gap_analysis', ''))}</p>
                    </div>
                </div>
            </section>

            <!-- 04. 킬러 문구 -->
            <section class="glass-card rounded-3xl p-8 md:p-10 animate-fade-in-up" style="animation-delay:0.5s">
                <h2 class="text-xl font-bold text-brand-700 mb-8 flex items-center gap-2">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                    04. '킬러 문구' 발췌
                </h2>
                <div class="space-y-4">{quotes_html}</div>
            </section>

            <!-- 05. 세특 첨삭 마스터 -->
            <section class="glass-card rounded-3xl p-8 md:p-10 bg-brand-50 border-2 border-brand-100 animate-fade-in-up" style="animation-delay:0.55s">
                <h2 class="text-xl font-bold text-brand-700 mb-6 flex items-center gap-2">
                    🔥 05. 세특 첨삭 마스터 (Rewriting){(' — ' + rewrite.get('target_subject', '')) if rewrite.get('target_subject') else ''}
                </h2>
                <div class="bg-white p-6 rounded-2xl shadow-sm space-y-5">
                    <div>
                        <span class="inline-block px-3 py-1 bg-red-100 text-red-700 text-xs font-bold rounded-full mb-2">❌ 원문 (약점: {rewrite.get('weak_point', '')})</span>
                        <p class="text-slate-500 text-sm leading-relaxed bg-red-50 p-4 rounded-xl">{nl2br(rewrite.get('original_sentence', ''))}</p>
                    </div>
                    <div class="pt-4 border-t border-slate-100">
                        <span class="inline-block px-3 py-1 bg-brand-100 text-brand-700 text-xs font-bold rounded-full mb-2">✅ 강선생 수정안</span>
                        <p class="text-slate-800 font-medium leading-relaxed bg-brand-50 p-4 rounded-xl">{nl2br(rewrite.get('rewritten_sentence', ''))}</p>
                    </div>
                    <div class="pt-4 border-t border-slate-100 bg-slate-50 p-4 rounded-xl">
                        <span class="font-bold text-slate-700 text-sm">💡 마스터 코멘트</span>
                        <p class="text-slate-600 text-sm mt-1">{nl2br(rewrite.get('master_comment', ''))}</p>
                    </div>
                </div>
            </section>

            <!-- 06. 보완 활동 추천 -->
            <section class="animate-fade-in-up" style="animation-delay:0.6s">
                <div class="mb-6">
                    <h2 class="text-xl font-bold text-brand-700 flex items-center gap-2">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/></svg>
                        06. 맞춤형 보완 활동 추천
                    </h2>
                </div>
                <div class="grid md:grid-cols-2 gap-8">{activities_html}</div>
            </section>

            <!-- 07. 인재상 매칭 -->
            <section class="glass-card rounded-3xl p-8 md:p-10 bg-slate-900 text-white border-none animate-fade-in-up" style="animation-delay:0.65s">
                <div class="flex flex-col md:flex-row gap-10 items-center">
                    <div class="flex-shrink-0 text-center">
                        <div class="relative inline-flex items-center justify-center">
                            <svg class="w-32 h-32 transform -rotate-90">
                                <circle cx="64" cy="64" r="58" stroke="currentColor" stroke-width="8" fill="transparent" class="text-slate-700"/>
                                <circle cx="64" cy="64" r="58" stroke="currentColor" stroke-width="8" fill="transparent"
                                    stroke-dasharray="{circumference}"
                                    stroke-dashoffset="{offset}"
                                    class="text-accent-teal"/>
                            </svg>
                            <span class="absolute text-2xl font-display font-bold">{match_pct}%</span>
                        </div>
                        <p class="mt-4 text-sm font-bold text-slate-400">인재상 매칭률</p>
                    </div>
                    <div class="flex-grow space-y-6">
                        <h2 class="text-2xl font-bold">{university} 인재상 &amp; Gap 분석</h2>
                        <p class="text-slate-400 text-sm leading-relaxed">{nl2br(talent.get('description', ''))}</p>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">{gaps_html}</div>
                    </div>
                </div>
            </section>

            <!-- 강선생 한 마디 -->
            <section class="relative animate-fade-in-up" style="animation-delay:0.7s">
                <div class="absolute inset-0 bg-brand-600 rounded-3xl transform rotate-1 opacity-10"></div>
                <div class="relative bg-white border-2 border-brand-100 rounded-3xl p-8 md:p-12 shadow-2xl">
                    <div class="flex items-start gap-6">
                        <div class="hidden sm:flex flex-shrink-0 w-16 h-16 bg-brand-600 rounded-full items-center justify-center text-white text-3xl font-serif">"</div>
                        <div>
                            <h2 class="text-xl font-bold text-slate-900 mb-4">강선생 한 마디</h2>
                            <p class="text-lg md:text-xl text-slate-700 leading-relaxed font-medium">
                                "{nl2br(data.get('expert_comment', ''))}"
                            </p>
                            <div class="mt-8 pt-6 border-t border-slate-100 flex items-center justify-between">
                                <div class="text-sm text-slate-500">
                                    <span class="font-bold text-slate-800">학종 강선생</span> | {university} {major} 특화
                                </div>
                                <div class="text-accent-teal flex gap-1">{stars}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

        </div>
    </main>

    <div class="h-20"></div>

    <script>
        document.addEventListener('DOMContentLoaded', () => {{
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach(entry => {{
                    if (entry.isIntersecting) {{
                        entry.target.classList.add('animate-fade-in-up');
                        entry.target.style.opacity = '1';
                    }}
                }});
            }}, {{ threshold: 0.1 }});
            document.querySelectorAll('section').forEach(s => {{
                s.style.opacity = '0';
                observer.observe(s);
            }});
        }});
    </script>
</body>
</html>"""
    return html


# ============================================================
# 5. Streamlit Main UI
# ============================================================
try:
    with st.sidebar:
        st.markdown("### 🎓 **학종 강선생**")
        st.markdown("AI 기반 생기부 정밀 진단 & 전략 보고서")
        st.divider()
        ready = configure_gemini()
        st.divider()

        st.markdown("**📎 입력 방식 선택**")
        input_mode = st.radio(
            "입력 방식",
            ["📄 PDF 업로드", "✏️ 직접 입력"],
            label_visibility="collapsed",
        )

        uploaded_file = None
        if input_mode == "📄 PDF 업로드":
            uploaded_file = st.file_uploader(
                "생기부 PDF 업로드",
                type=["pdf"],
                help=f"최대 {MAX_UPLOAD_MB}MB. 텍스트/스캔 PDF 모두 지원.",
            )

        st.divider()
        target_university = st.text_input("🏫 지원 대학교", placeholder="예: 국민대학교")
        target_major = st.text_input("📚 지원 학과", placeholder="예: 경영학과")

    st.title("🎓 학종 강선생 — AI 생기부 컨설턴트")
    st.caption(
        "생기부를 업로드하거나 직접 입력하면, AI가 **3대 역량 진단 · 세특 첨삭 · 맞춤형 전략 보고서**를 생성합니다."
    )

    manual_text = ""
    if input_mode == "✏️ 직접 입력":
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            grades_input = st.text_area(
                "📊 주요 교과 등급",
                height=120,
                placeholder="[1학년] 국어:2/2, 수학:5/4, 영어:2/2\n[2학년] 국어:2/1, 수학:2/2, 영어:2/1",
            )
        with col2:
            haengteuk_input = st.text_area(
                "🌟 행동특성 및 종합의견",
                height=120,
                placeholder="[1학년] 수학에서 어려움을 겪었으나...",
            )
        seukteuk_input = st.text_area(
            "📝 세부능력 및 특기사항 (세특)",
            height=200,
            placeholder="[수학II] 한계비용 개념을 미분과 연결하여...\n[통합사회] ESG 경영의 중요성을 인식하고...",
        )
        changche_input = st.text_area(
            "🏫 창의적 체험활동 (창체)",
            height=150,
            placeholder="[동아리] 경영동아리에서 마케팅 전략 기획...\n[진로활동] 화학 산업의 환경 비용 분석...",
        )
        additional_input = st.text_area(
            "💬 추가 정보 (선택)",
            height=80,
            placeholder="진로 희망, 수상 경력 개요, 기타 특이사항 등",
        )

        parts_list = []
        if grades_input:
            parts_list.append(f"[교과 등급]\n{grades_input}")
        if seukteuk_input:
            parts_list.append(f"[세특]\n{seukteuk_input}")
        if changche_input:
            parts_list.append(f"[창체]\n{changche_input}")
        if haengteuk_input:
            parts_list.append(f"[행특]\n{haengteuk_input}")
        if additional_input:
            parts_list.append(f"[추가정보]\n{additional_input}")
        manual_text = "\n\n".join(parts_list)

    can_analyze = False
    if input_mode == "📄 PDF 업로드" and uploaded_file and ready:
        can_analyze = True
    elif input_mode == "✏️ 직접 입력" and manual_text.strip() and ready:
        can_analyze = True

    if not ready:
        st.warning("👈 사이드바에서 Gemini API Key를 입력해주세요.")
    elif not can_analyze:
        st.info("👈 사이드바에서 생기부를 업로드하거나 위에서 직접 입력해주세요.")

    if can_analyze:
        if st.button("🚀 정밀 진단 & 전략 보고서 생성", type="primary", use_container_width=True):

            uni = target_university.strip() or "미지정 대학"
            maj = target_major.strip() or "미지정 학과"

            with st.spinner("🔬 생기부를 분석하여 프리미엄 보고서를 생성 중입니다... (약 30~60초 소요)"):

                prompt = build_analysis_prompt(uni, maj)
                parts = [prompt]

                if input_mode == "📄 PDF 업로드":
                    file_bytes = uploaded_file.getvalue()
                    text_content = ""
                    try:
                        reader = PdfReader(io.BytesIO(file_bytes))
                        text_content = "\n".join(
                            [p.extract_text() for p in reader.pages if p.extract_text()]
                        )
                    except Exception:
                        pass

                    if len(text_content) > SCAN_TEXT_MIN_LEN:
                        parts.append(f"\n[생기부 텍스트]\n{text_content}")
                    else:
                        images = render_pdf_to_images(file_bytes)
                        if not images:
                            st.error("PDF에서 텍스트/이미지를 추출할 수 없습니다.")
                            st.stop()
                        st.info(f"📷 스캔 PDF 감지 — {len(images)}페이지를 이미지로 분석합니다.")
                        parts.extend(images)
                else:
                    parts.append(f"\n[생기부 텍스트]\n{manual_text}")

                result = call_gemini(parts)

            if "error" in result:
                st.error(f"❌ 오류 발생: {result['error']}")
            else:
                st.success("✅ 분석 완료! 아래에서 보고서를 확인하고 다운로드하세요.")

                final_html = build_html_report(result, uni, maj)

                st.divider()
                st.markdown("### 📊 맞춤형 전략 보고서 Preview")
                components.html(final_html, height=2400, scrolling=True)

                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button(
                        label="💾 HTML 보고서 다운로드",
                        data=final_html,
                        file_name=f"학종강선생_{uni}_{maj}_전략보고서.html",
                        mime="text/html",
                        help="다운로드 후 크롬에서 열고 Ctrl+P로 PDF 저장 가능",
                        type="primary",
                        use_container_width=True,
                    )
                with col_d2:
                    st.download_button(
                        label="📋 JSON 원본 데이터 다운로드",
                        data=json.dumps(result, ensure_ascii=False, indent=2),
                        file_name=f"학종강선생_{uni}_{maj}_분석결과.json",
                        mime="application/json",
                        use_container_width=True,
                    )

                with st.expander("📝 AI 분석 원본 데이터 (JSON)"):
                    st.json(result)

except Exception as e:
    st.error(f"시스템 오류: {e}")

import anthropic
import json


def extract_theories_and_books(text: str, api_key: str) -> dict:
    """생활기록부 텍스트에서 이론과 도서를 추출합니다."""
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""아래는 학생의 생활기록부 내용입니다. 이 내용에서 언급된 모든 '이론'과 '도서(책)'를 추출해주세요.

생활기록부:
{text}

다음 JSON 형식으로 응답해주세요:
{{
  "theories": [
    {{"name": "이론 이름", "context": "이 이론이 언급된 맥락 또는 설명"}}
  ],
  "books": [
    {{"name": "책 제목 (저자)", "context": "이 책이 언급된 맥락 또는 설명"}}
  ]
}}

규칙:
- 명시적으로 언급된 이론, 법칙, 원리, 개념만 추출 (예: 케인즈 이론, 상대성 이론, 진화론 등)
- 명시적으로 언급된 책, 논문, 저서만 추출
- 추측하지 말고 텍스트에 실제로 나온 것만 추출
- 없으면 빈 배열 반환
- 반드시 유효한 JSON만 반환"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    # JSON 블록 파싱
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    return json.loads(response_text)


def recommend_majors(theories: list, books: list, api_key: str) -> list:
    """추출된 이론과 도서를 바탕으로 대학 학과를 추천합니다."""
    client = anthropic.Anthropic(api_key=api_key)

    theories_str = "\n".join([f"- {t['name']}: {t['context']}" for t in theories]) or "없음"
    books_str = "\n".join([f"- {b['name']}: {b['context']}" for b in books]) or "없음"

    prompt = f"""학생의 생활기록부에서 추출된 이론과 도서를 분석하여 대학 학과를 추천해주세요.

【이론 목록】
{theories_str}

【도서 목록】
{books_str}

이 학생에게 적합한 대학 학과 TOP 5를 추천해주세요.
각 학과에 대해 점수(100점 만점)와 추천 이유를 설명해주세요.

반드시 아래 JSON 형식으로만 응답하세요:
[
  {{
    "major": "학과명",
    "score": 점수,
    "reason": "이 학과를 추천하는 구체적인 이유 (어떤 이론/도서와 연관되는지 포함)",
    "related_theories": ["관련 이론1", "관련 이론2"],
    "related_books": ["관련 도서1", "관련 도서2"]
  }}
]

점수가 높은 순서로 정렬하고, 반드시 유효한 JSON만 반환하세요."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    return json.loads(response_text)

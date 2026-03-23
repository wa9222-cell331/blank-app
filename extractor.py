import anthropic
import base64
import json


def extract_text_from_pdf(pdf_bytes: bytes, api_key: str) -> str:
    """PDF 파일에서 생활기록부 전체 텍스트를 추출합니다. 스캔 PDF도 처리 가능합니다."""
    client = anthropic.Anthropic(api_key=api_key)

    pdf_data = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        "이 PDF는 학생의 생활기록부입니다. "
                        "PDF에 있는 모든 텍스트를 원문 그대로 추출해주세요. "
                        "서식(줄바꿈, 항목 구분 등)을 최대한 유지하고, "
                        "어떠한 요약이나 수정 없이 전체 내용을 그대로 출력해주세요."
                    ),
                },
            ],
        }],
    )

    return message.content[0].text.strip()


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
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()

    return json.loads(response_text)

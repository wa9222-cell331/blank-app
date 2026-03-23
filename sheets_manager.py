import gspread
from google.oauth2.service_account import Credentials
import json
from datetime import datetime


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_gspread_client(credentials_json: dict):
    creds = Credentials.from_service_account_info(credentials_json, scopes=SCOPES)
    return gspread.authorize(creds)


def create_recommendation_sheet(
    credentials_json: dict,
    student_name: str,
    theories: list,
    books: list,
    recommendations: list,
) -> str:
    """학생 생기부 분석 결과를 구글 시트에 작성하고 URL을 반환합니다."""
    gc = get_gspread_client(credentials_json)

    title = f"[생기부 분석] {student_name} - {datetime.now().strftime('%Y%m%d_%H%M')}"
    spreadsheet = gc.create(title)
    spreadsheet.share(None, perm_type="anyone", role="reader")

    # ── 시트 1: 학과 추천 ──────────────────────────────────────────
    rec_sheet = spreadsheet.sheet1
    rec_sheet.update_title("📊 학과 추천")

    rec_headers = ["순위", "추천 학과", "적합도 점수", "추천 이유", "관련 이론", "관련 도서"]
    rec_rows = [rec_headers]
    for i, rec in enumerate(recommendations, 1):
        rec_rows.append([
            i,
            rec.get("major", ""),
            rec.get("score", ""),
            rec.get("reason", ""),
            ", ".join(rec.get("related_theories", [])),
            ", ".join(rec.get("related_books", [])),
        ])

    rec_sheet.update(rec_rows, "A1")
    _format_header(rec_sheet, len(rec_headers))

    # ── 시트 2: 추출된 이론 ────────────────────────────────────────
    theory_sheet = spreadsheet.add_worksheet(title="📚 이론 목록", rows=100, cols=10)
    theory_headers = ["번호", "이론명", "언급 맥락"]
    theory_rows = [theory_headers]
    for i, t in enumerate(theories, 1):
        theory_rows.append([i, t.get("name", ""), t.get("context", "")])

    theory_sheet.update(theory_rows, "A1")
    _format_header(theory_sheet, len(theory_headers))

    # ── 시트 3: 추출된 도서 ────────────────────────────────────────
    book_sheet = spreadsheet.add_worksheet(title="📖 도서 목록", rows=100, cols=10)
    book_headers = ["번호", "도서명", "언급 맥락"]
    book_rows = [book_headers]
    for i, b in enumerate(books, 1):
        book_rows.append([i, b.get("name", ""), b.get("context", "")])

    book_sheet.update(book_rows, "A1")
    _format_header(book_sheet, len(book_headers))

    # ── 시트 4: 요약 대시보드 ─────────────────────────────────────
    summary_sheet = spreadsheet.add_worksheet(title="🎯 요약", rows=50, cols=10)
    summary_data = [
        ["생활기록부 분석 요약"],
        [],
        ["학생명", student_name],
        ["분석일시", datetime.now().strftime("%Y년 %m월 %d일 %H:%M")],
        ["추출된 이론 수", len(theories)],
        ["추출된 도서 수", len(books)],
        ["추천 학과 수", len(recommendations)],
        [],
        ["TOP 3 추천 학과"],
    ]
    for i, rec in enumerate(recommendations[:3], 1):
        summary_data.append([f"{i}위", rec.get("major", ""), f"{rec.get('score', '')}점"])

    summary_sheet.update(summary_data, "A1")

    return spreadsheet.url


def _format_header(sheet, col_count: int):
    """헤더 행을 굵게 처리하고 배경색을 설정합니다."""
    sheet.format(
        f"A1:{chr(64 + col_count)}1",
        {
            "textFormat": {"bold": True, "fontSize": 11},
            "backgroundColor": {"red": 0.26, "green": 0.52, "blue": 0.96},
            "horizontalAlignment": "CENTER",
        }
    )
    # 헤더 텍스트 색상을 흰색으로
    sheet.format(
        f"A1:{chr(64 + col_count)}1",
        {"textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}}}
    )

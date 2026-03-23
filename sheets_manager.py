import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SOURCE = "학종 강선생"


def get_gspread_client(credentials_json: dict):
    creds = Credentials.from_service_account_info(credentials_json, scopes=SCOPES)
    return gspread.authorize(creds)


def create_recommendation_sheet(
    credentials_json: dict,
    student_name: str,
    theories: list,
    books: list,
    recommendations: list,  # 사용하지 않음 (학과 추천 제거)
) -> str:
    """학생 생기부 분석 결과를 구글 시트에 작성하고 URL을 반환합니다."""
    gc = get_gspread_client(credentials_json)

    title = f"[{SOURCE}] {student_name} 생기부 분석 - {datetime.now().strftime('%Y%m%d_%H%M')}"
    spreadsheet = gc.create(title)
    spreadsheet.share(None, perm_type="anyone", role="reader")

    # ── 시트 1: 이론 목록 ──────────────────────────────────────────
    theory_sheet = spreadsheet.sheet1
    theory_sheet.update_title("📚 이론 목록")

    theory_rows = [["번호", "이론명", "언급 맥락", "출처"]]
    for i, t in enumerate(theories, 1):
        theory_rows.append([i, t.get("name", ""), t.get("context", ""), SOURCE])
    theory_sheet.update(theory_rows, "A1")
    _format_header(theory_sheet, 4)

    # ── 시트 2: 도서 목록 ──────────────────────────────────────────
    book_sheet = spreadsheet.add_worksheet(title="📖 도서 목록", rows=100, cols=10)
    book_rows = [["번호", "도서명", "언급 맥락", "출처"]]
    for i, b in enumerate(books, 1):
        book_rows.append([i, b.get("name", ""), b.get("context", ""), SOURCE])
    book_sheet.update(book_rows, "A1")
    _format_header(book_sheet, 4)

    # ── 시트 3: 요약 ───────────────────────────────────────────────
    summary_sheet = spreadsheet.add_worksheet(title="📋 요약", rows=20, cols=5)
    summary_sheet.update([
        ["생활기록부 분석 결과"],
        [],
        ["학생명", student_name],
        ["분석일시", datetime.now().strftime("%Y년 %m월 %d일 %H:%M")],
        ["추출된 이론 수", len(theories)],
        ["추출된 도서 수", len(books)],
        [],
        ["출처", SOURCE],
    ], "A1")

    return spreadsheet.url


def _format_header(sheet, col_count: int):
    range_str = f"A1:{chr(64 + col_count)}1"
    sheet.format(range_str, {
        "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "backgroundColor": {"red": 0.26, "green": 0.52, "blue": 0.96},
        "horizontalAlignment": "CENTER",
    })

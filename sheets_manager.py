import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SOURCE = "학종 강선생"

# 마스터 시트의 워크시트 이름
SHEET_THEORIES = "📚 이론 목록"
SHEET_BOOKS = "📖 도서 목록"
SHEET_SUMMARY = "📋 학생 요약"


def get_gspread_client(credentials_json: dict):
    creds = Credentials.from_service_account_info(credentials_json, scopes=SCOPES)
    return gspread.authorize(creds)


# ── 최초 1회: 마스터 DB 시트 생성 ──────────────────────────────────────
def create_master_sheet(credentials_json: dict) -> tuple[str, str]:
    """마스터 DB 시트를 생성하고 (spreadsheet_id, url)을 반환합니다."""
    gc = get_gspread_client(credentials_json)

    title = f"[{SOURCE}] 생기부 분석 DB"
    spreadsheet = gc.create(title)
    spreadsheet.share(None, perm_type="anyone", role="reader")

    # 시트1: 이론 목록
    theory_sheet = spreadsheet.sheet1
    theory_sheet.update_title(SHEET_THEORIES)
    theory_sheet.append_row(["학생명", "이론명", "언급 맥락", "분석일시", "출처"])
    _format_header(theory_sheet, 5)

    # 시트2: 도서 목록
    book_sheet = spreadsheet.add_worksheet(title=SHEET_BOOKS, rows=1000, cols=10)
    book_sheet.append_row(["학생명", "도서명", "언급 맥락", "분석일시", "출처"])
    _format_header(book_sheet, 5)

    # 시트3: 학생 요약
    summary_sheet = spreadsheet.add_worksheet(title=SHEET_SUMMARY, rows=1000, cols=10)
    summary_sheet.append_row(["학생명", "이론 수", "도서 수", "분석일시", "출처"])
    _format_header(summary_sheet, 5)

    return spreadsheet.id, spreadsheet.url


# ── 이후: 기존 시트에 학생 데이터 추가 ────────────────────────────────
def append_student_to_sheet(
    credentials_json: dict,
    spreadsheet_id: str,
    student_name: str,
    theories: list,
    books: list,
) -> str:
    """기존 마스터 시트에 학생 데이터를 추가하고 url을 반환합니다."""
    gc = get_gspread_client(credentials_json)
    spreadsheet = gc.open_by_key(spreadsheet_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # 이론 추가
    theory_sheet = spreadsheet.worksheet(SHEET_THEORIES)
    for t in theories:
        theory_sheet.append_row([student_name, t.get("name", ""), t.get("context", ""), now, SOURCE])

    # 도서 추가
    book_sheet = spreadsheet.worksheet(SHEET_BOOKS)
    for b in books:
        book_sheet.append_row([student_name, b.get("name", ""), b.get("context", ""), now, SOURCE])

    # 요약 추가
    summary_sheet = spreadsheet.worksheet(SHEET_SUMMARY)
    summary_sheet.append_row([student_name, len(theories), len(books), now, SOURCE])

    return spreadsheet.url


def _format_header(sheet, col_count: int):
    range_str = f"A1:{chr(64 + col_count)}1"
    sheet.format(range_str, {
        "textFormat": {"bold": True, "fontSize": 11, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "backgroundColor": {"red": 0.26, "green": 0.52, "blue": 0.96},
        "horizontalAlignment": "CENTER",
    })


# ── 하위 호환용 래퍼 (기존 코드에서 호출하던 함수명 유지) ──────────────
def create_recommendation_sheet(credentials_json, student_name, theories, books, recommendations=None):
    """deprecated: append_student_to_sheet 사용 권장"""
    _id, url = create_master_sheet(credentials_json)
    append_student_to_sheet(credentials_json, _id, student_name, theories, books)
    return url

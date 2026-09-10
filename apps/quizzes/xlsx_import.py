"""O'qituvchi yuklagan .xlsx fayldan test savollarini ajratib olish (import).

Kutilgan jadval (1-qator — sarlavha, o'tkazib yuboriladi):

    | Savol       | A        | B        | C        | D        | E        | To'g'ri javob |
    |-------------|----------|----------|----------|----------|----------|---------------|
    | Savol matni | Variant1 | Variant2 | Variant3 | Variant4 | Variant5 | B             |

Har bir ustun harfi (A-E) doim bir xil pozitsiyaga bog'langan (B ustuni =
A varianti, C ustuni = B varianti, ...) — "To'g'ri javob" ustunidagi harf
shu pozitsiyalardan biriga ishora qiladi. Variant ustunlaridan ba'zilari
bo'sh bo'lishi mumkin (masalan faqat 4 ta variant bo'lsa, E ustuni bo'sh
qoladi) — bu xato emas, shunchaki o'sha variant qatorga qo'shilmaydi.

`docx_import.py` bilan bir xil preview strukturasini qaytaradi, shuning
uchun `QuizImportView` ikkalasini ham bab-baravar ishlatadi.
"""
from pathlib import Path

MAX_IMPORT_FILE_SIZE_MB = 10
# Pozitsiyaga bog'liq ustunlar (0-indeksli): 0=Savol, 1-5=A..E variant, 6=javob.
_OPTION_COLUMN_INDEXES = [1, 2, 3, 4, 5]
_ANSWER_COLUMN_INDEX = 6


def _cell_text(value) -> str:
    return str(value).strip() if value is not None else ''


def _row_value(row, index):
    """`row` — cell obyektlar tuple'i (oddiy rejim) yoki qiymatlar tuple'i
    (`values_only=True`). Ikkalasini ham qo'llab-quvvatlaydi, qatordan
    tashqariga chiqib ketsa (qisqaroq qator) `None` qaytaradi."""
    if index >= len(row):
        return None
    cell = row[index]
    return cell.value if hasattr(cell, 'value') else cell


def parse_xlsx_questions(file_obj) -> dict:
    """`.xlsx` fayl (fayl-obyekt yoki yo'l)ni preview strukturasiga aylantiradi.

    Qaytaradi: {'title': '', 'description': '',
                'questions': [{'text', 'order', 'options': [{'text','is_correct','order'}]}],
                'warnings': [{'question_number', 'reason'}]}

    Excel jadvalida erkin sarlavha/tavsif joyi yo'q (birinchi qator doim
    ustun nomlari), shuning uchun title/description hamisha bo'sh qaytadi —
    o'qituvchi buni allaqachon test yaratish oynasida kiritgan bo'ladi.

    `read_only` rejimi ATAYLAB ishlatilmaydi — bo'sh (yozilmagan) katakchalar
    o'sha rejimda `EmptyCell` sentinel sifatida qaytadi va oddiy `Cell`dan
    farqli xususiyatlarga ega, bu esa variant ustunlaridan biri bo'sh
    qoldirilganda (masalan faqat 4 ta variant) chalkashlikka olib keladi.
    """
    import openpyxl

    workbook = openpyxl.load_workbook(file_obj, data_only=True)
    sheet = workbook.active

    questions = []
    warnings = []
    for row in sheet.iter_rows(min_row=2):
        question_text = _cell_text(_row_value(row, 0))
        if not question_text:
            continue  # bo'sh qator — o'tkazib yuboriladi

        options = []
        for index, col_index in enumerate(_OPTION_COLUMN_INDEXES):
            text = _cell_text(_row_value(row, col_index))
            if not text:
                continue
            options.append({'letter': chr(ord('A') + index), 'text': text})

        answer_letter = _cell_text(_row_value(row, _ANSWER_COLUMN_INDEX)).upper()[:1] or None
        order = len(questions)
        questions.append({
            'text': question_text,
            'order': order,
            'options': [{
                'text': opt['text'],
                'is_correct': bool(answer_letter) and opt['letter'] == answer_letter,
                'order': i,
            } for i, opt in enumerate(options)],
        })

        correct_count = sum(1 for o in questions[-1]['options'] if o['is_correct'])
        if len(options) < 2:
            warnings.append({'question_number': order + 1, 'reason': 'not_enough_options'})
        elif correct_count != 1:
            warnings.append({'question_number': order + 1, 'reason': 'answer_not_detected'})

    return {'title': '', 'description': '', 'questions': questions, 'warnings': warnings}


def is_xlsx(filename: str) -> bool:
    return Path(filename or '').suffix.lower() == '.xlsx'

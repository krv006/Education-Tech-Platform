"""AI o'quv yordamchisi — Gemini bilan test (quiz) qoralamasi tuzish va
o'quvchi savoliga fan/o'tilgan mavzular kontekstida javob berish.

`apps/homework/ai.py` bilan bir xil naqsh (kalit, model, JSON-mode,
qayta urinish) — shu yerda takrorlanmaydi, faqat kerakli qismlar
(`detect_profile`, `SUBJECTS`) import qilinadi.
"""
import json
import re
import time

from django.conf import settings


class TutorAIError(Exception):
    pass


def _strip_markdown_fences(text: str) -> str:
    cleaned = (text or '').strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    return cleaned.strip()


def _model(system_prompt: str):
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise TutorAIError("GEMINI_API_KEY sozlanmagan — serverda env o'zgaruvchisini bering.")

    import google.generativeai as genai  # lazy — paket faqat shu yerda kerak

    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        model_name=getattr(settings, 'GEMINI_MODEL', 'gemini-3.5-flash'),
        system_instruction=system_prompt,
    )


# ─── Test (quiz) qoralamasi ─────────────────────────────────────────────────

_QUIZ_OUTPUT_FORMAT = """# OUTPUT FORMAT

Return ONLY valid JSON, no markdown fences, no commentary:

{
  "title": "Qisqa, mavzuga mos test nomi (o'zbek tilida)",
  "questions": [
    {
      "text": "Savol matni (o'zbek tilida)",
      "options": [
        {"text": "...", "is_correct": true},
        {"text": "...", "is_correct": false},
        {"text": "...", "is_correct": false},
        {"text": "...", "is_correct": false}
      ]
    }
  ]
}

Rules:
- Exactly 4 options per question, exactly 1 with "is_correct": true.
- Questions must be answerable using only the listed topics — do not invent
  content outside them.
- Write ALL text in simple, clear UZBEK (latin script) appropriate for a
  school student.
"""


def generate_quiz_draft(*, subject_text: str, lesson_titles: list[str], question_count: int = 5) -> dict:
    """O'tilgan mavzular asosida MCQ test qoralamasini tuzadi.

    Natija `QuizCreateSerializer` kutgan shaklga mos (`title`, `questions`)
    — hech narsa bazaga yozilmaydi, o'qituvchi ko'rib chiqib tahrirlagach
    o'zi POST /api/v1/quizzes/ orqali yaratadi."""
    subject = subject_text or 'umumiy fan'
    topics = '\n'.join(f'- {t}' for t in lesson_titles)
    system_prompt = f"""You are an expert {subject} school teacher creating a
multiple-choice quiz for students, strictly based on topics already covered
in class.

# TOPICS COVERED (the quiz MUST be based only on these)
{topics}

# TASK
Create exactly {question_count} multiple-choice questions covering these
topics, at a difficulty appropriate for a school student who just learned
this material.

{_QUIZ_OUTPUT_FORMAT}"""

    model = _model(system_prompt)
    content = f'Generate the quiz now — exactly {question_count} questions, valid JSON only.'

    last_error = None
    for attempt in range(3):
        try:
            response = model.generate_content(
                content,
                generation_config={
                    'temperature': 0.4, 'top_p': 0.9,
                    'max_output_tokens': 4096, 'response_mime_type': 'application/json',
                },
            )
            data = json.loads(_strip_markdown_fences(response.text))
            if not isinstance(data.get('questions'), list) or not data['questions']:
                raise TutorAIError("Model javobida 'questions' bo'sh yoki yo'q.")
            for q in data['questions']:
                options = q.get('options') or []
                if len(options) < 2 or sum(1 for o in options if o.get('is_correct')) != 1:
                    raise TutorAIError('Model bir yoki bir nechta savolda variant sonini yoki to\'g\'ri javobni buzdi.')
            return data
        except (json.JSONDecodeError, TutorAIError) as exc:
            last_error = exc
            content = (
                'Your previous response did not match the required JSON schema '
                f'({exc}). Return ONLY the corrected JSON object, nothing else.'
            )
            time.sleep(1)
        except Exception as exc:  # noqa: BLE001 — tarmoq/API xatolari
            last_error = exc
            time.sleep(1.5 * (attempt + 1))

    raise TutorAIError(f'Test qoralamasini tuzib bo\'lmadi: {last_error}')


# ─── O'quvchi savoliga javob ────────────────────────────────────────────────

def answer_course_question(*, subject_text: str, lesson_titles: list[str], question: str) -> str:
    """O'quvchining "tushunmadim" savoliga fan va o'tilgan mavzular
    kontekstida oddiy o'zbek tilida tushuntirish beradi."""
    subject = subject_text or 'umumiy fan'
    topics = '\n'.join(f'- {t}' for t in lesson_titles) or '(hali o\'tilgan dars yo\'q)'
    system_prompt = f"""You are a patient, encouraging {subject} school tutor
helping a student who is confused about something from class.

# TOPICS COVERED SO FAR IN THIS COURSE
{topics}

# TASK
Answer the student's question clearly and simply, in UZBEK (latin script),
at a level appropriate for a school student. Prefer explanations grounded in
the topics listed above. If the question is clearly unrelated to {subject},
gently say this assistant only helps with {subject} questions for this
course, and suggest they ask their teacher. Keep the answer focused —
a few short paragraphs, not an essay. Plain text only, no markdown, no JSON."""

    model = _model(system_prompt)
    last_error = None
    for attempt in range(3):
        try:
            response = model.generate_content(
                question, generation_config={'temperature': 0.5, 'max_output_tokens': 1024},
            )
            text = (response.text or '').strip()
            if not text:
                raise TutorAIError('Model bo\'sh javob qaytardi.')
            return text
        except TutorAIError as exc:
            last_error = exc
            time.sleep(1)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(1.5 * (attempt + 1))

    raise TutorAIError(f'Javob olib bo\'lmadi: {last_error}')

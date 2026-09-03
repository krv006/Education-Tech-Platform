"""Quizzes service qatlami — barcha yozuvchi biznes-logika shu yerda."""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.lessons.models import Course, Enrollment, Lesson

from .models import AnswerResponse, Option, Question, Quiz, QuizAttempt

_ENROLLED = Enrollment.Status.APPROVED


def _enrolled_students(course: Course):
    return User.objects.filter(enrollments__course=course, enrollments__status=_ENROLLED)


def _notify_new_quiz(quiz: Quiz) -> None:
    """apps.homework._notify_new_assignment bilan bir xil naqsh — real-time
    push (WebSocket) send_notification ichida avtomatik bo'ladi."""
    from apps.notifications.models import Notification
    from apps.notifications.services import send_notification

    description = f'«{quiz.course.title}»: yangi test qo\'shildi — «{quiz.title}».'
    for student in _enrolled_students(quiz.course):
        send_notification(
            sender=quiz.course.teacher, description=description,
            target_type=Notification.Target.USER, user_id=student.id,
            link_type='quiz', link_id=str(quiz.id),
        )


@transaction.atomic
def create_quiz(
    *, teacher: User, course: Course, title: str, questions: list,
    lesson: Lesson | None = None, description: str = '', due_at=None, opens_at=None,
) -> Quiz:
    if course.teacher_id != teacher.id:
        raise PermissionDenied('Bu kurs sizga tegishli emas.')
    if lesson is not None and lesson.course_id != course.id:
        raise ValidationError({'lesson': 'Bu dars ushbu kursga tegishli emas.'})

    quiz = Quiz.objects.create(
        course=course, lesson=lesson, title=title, description=description,
        due_at=due_at, opens_at=opens_at,
    )
    for q_index, q_data in enumerate(questions):
        question = Question.objects.create(
            quiz=quiz, text=q_data['text'], points=q_data.get('points', 1),
            order=q_data.get('order', q_index),
        )
        for o_index, o_data in enumerate(q_data['options']):
            Option.objects.create(
                question=question, text=o_data['text'],
                is_correct=o_data.get('is_correct', False), order=o_data.get('order', o_index),
            )

    # Faqat DARHOL ochiq test uchun bildirishnoma yuboriladi — kelajakdagi
    # "ochilish kuni"si bo'lgan testda hali ko'ra olmaydigan havolaga
    # bildirishnoma yuborish chalkashlik keltirib chiqaradi (buzuq link).
    if opens_at is None or opens_at <= timezone.now():
        transaction.on_commit(lambda: _notify_new_quiz(quiz))
    return quiz


def delete_quiz(*, teacher: User, quiz: Quiz) -> None:
    if quiz.course.teacher_id != teacher.id:
        raise PermissionDenied('Bu test sizga tegishli emas.')
    quiz.delete()


@transaction.atomic
def submit_attempt(*, student: User, quiz: Quiz, answers: list) -> QuizAttempt:
    is_enrolled = Enrollment.objects.filter(
        course=quiz.course, student=student, status=_ENROLLED,
    ).exists()
    if not is_enrolled:
        raise PermissionDenied('Siz bu kursga yozilmagansiz.')

    all_questions = list(quiz.questions.all())
    answered_ids = set()
    attempt = QuizAttempt.objects.create(quiz=quiz, student=student)

    score = 0
    for answer in answers:
        question = answer['question']
        selected = answer['selected_option']
        if question.quiz_id != quiz.id:
            raise ValidationError({'answers': 'Savol ushbu testga tegishli emas.'})
        if question.id in answered_ids:
            raise ValidationError({'answers': "Bir savolga faqat bitta javob yuborilishi mumkin."})
        if selected.question_id != question.id:
            raise ValidationError({'answers': 'Tanlangan variant bu savolga tegishli emas.'})
        answered_ids.add(question.id)

        is_correct = selected.is_correct
        AnswerResponse.objects.create(
            attempt=attempt, question=question, selected_option=selected, is_correct=is_correct,
        )
        if is_correct:
            score += question.points

    # Javobsiz qolgan savollar ham maksimal ballga qo'shiladi (adolatli ball).
    max_score = sum(q.points for q in all_questions)

    attempt.score = score
    attempt.max_score = max_score
    attempt.save(update_fields=['score', 'max_score'])
    return attempt

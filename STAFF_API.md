# O'qituvchi / ota-ona / admin uchun API endpointlari

Bu hujjat `STUDENT_API.md`ni **to'ldiradi** — u yerda yozilganlar takrorlanmaydi. Bu yerda faqat o'qituvchi, ota-ona, admin va super_admin uchun ochiq (yoki ularga xos qo'shimcha xatti-harakatga ega) endpointlar bor.

**Base URL**: `/api/v1/`
**Auth**: JWT (`Authorization: Bearer <access_token>`)

Rol → ruxsat jadvali (`apps/core/permissions.py`):

```
super_admin: '*' (hammasi)
admin:       course.view, course.moderate, lesson.view, lesson.cancel,
             attendance.view, audit.view, user.manage, notification.send
teacher:     course.create/edit/view/enroll, lesson.schedule/edit/cancel/finish/view,
             room.token, room.moderate, attendance.view, chat.use,
             homework.assign/view, child.create
parent:      child.create, link.request/view, consent.manage,
             course.view/enroll, lesson.view, attendance.view, homework.view
```

**Muhim eslatmalar**:
- `admin`da `course.create/edit`, `chat.use`, `homework.assign`, `room.token` **yo'q** — admin faqat ko'rish/moderatsiya + bildirishnoma yuborish + foydalanuvchi qidirish uchun, kurs/dars/chatni faqat `super_admin` (wildcard) boshqara oladi.
- `parent`da `chat.use` **yo'q** — ota-ona chatga umuman kira olmaydi (na REST, na WebSocket), garchi farzandining darsi/vazifasi/davomatini ko'rsa ham.
- `course.moderate`/`lesson.cancel` ruxsatlari admin ro'yxatida bor, lekin ularni tekshiradigan **hech qanday endpoint yo'q** (ulanmagan).

---

## 1. Auth / Accounts (`/api/v1/auth/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/auth/register/` | Hammaga ochiq, lekin `role` faqat `teacher`\|`parent` | `username, password, first_name, last_name, role, phone` | `id, username, first_name, last_name, role, phone` | Ochiq ro'yxatdan o'tish (faqat o'qituvchi/ota-ona; o'quvchi faqat `/children/` orqali yaratiladi) |
| GET | `/auth/logins/?student=<id>` | ota-ona (o'z tasdiqlangan farzandi uchun) | — | `[{at, ip, user_agent, new_ip, new_device}]` | Farzandining login tarixi |
| POST | `/auth/children/` | teacher, parent (`child.create`) | `username, password, first_name, last_name` | `id, username, first_name, last_name, invite_code` | O'quvchi hisobini yaratadi. Ota-ona yaratsa — `ParentChildLink` darhol APPROVED. O'qituvchi yaratsa — bog'lanish yaratilmaydi, faqat `invite_code` beriladi (haqiqiy ota-ona keyin bog'lanadi) |
| GET | `/auth/users/search/?q=` | admin, super_admin (`user.manage`) | — | `UserSerializer[]` (max 10) | Barcha rollar bo'yicha foydalanuvchi qidirish (bildirishnoma yuborish uchun) |
| POST | `/auth/links/request/` | parent (`link.request`) | `invite_code` | `id, parent, student, status, created_at, responded_at` | Ota-ona bola invite_code'i orqali bog'lanish so'rovi yuboradi (PENDING, o'quvchi tasdiqlashi kerak) |
| GET/POST | `/auth/consents/` | parent (`consent.manage`) | POST: `student, kind(recording\|camera\|analytics), granted` | `id, student, kind, granted, updated_at` | Ota-ona farzandi uchun rozilik (recording/camera/analytics) belgilaydi |

---

## 2. Kurslar (`/api/v1/courses/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/courses/` | teacher (`course.create`) | `title, subject, description` | `CourseSerializer` | Kurs yaratadi (guruh chati avtomatik ochiladi) |
| PUT/PATCH | `/courses/{id}/` | teacher, faqat o'zi | xuddi yuqoridagidek | `CourseSerializer` | Kursni tahrirlash |
| DELETE | `/courses/{id}/` | teacher, faqat o'zi | — | 204 | **Qaytarib bo'lmaydi**: video yozuvlar, doska (chizma+PDF), chat xonasi+xabarlar+fayllar, barcha a'zolik butunlay o'chadi; darslar faqat yashiriladi (Davomat/Baho tarixi saqlanadi) |
| GET | `/courses/requests/` | teacher (`course.edit`) | — | `EnrollmentSerializer[]` (paginated) | O'z kurslariga kelgan kutilayotgan yozilish so'rovlari |
| POST | `/courses/requests/respond/` | teacher | `enrollment_id, action(approve\|decline)` | `EnrollmentSerializer` | So'rovga javob |
| POST | `/courses/{id}/schedule/` | teacher (`lesson.schedule`) | `title, days:[0-6], start_time, end_time, weeks(1-52), start_date, note` | `{count, lessons:[...]}` (201) | Haftalik jadval bo'yicha ko'plab dars yaratadi; o'qituvchining BARCHA kurslari bo'yicha vaqt to'qnashuvini tekshiradi (`{conflicts:[...]}` 400) |
| GET | `/courses/{id}/search-students/?q=` | teacher (o'ziniki), admin, super_admin | — | `[{...user, enroll_status}]` (max 10) | O'quvchi qidirish, kursga biriktirish uchun |
| GET | `/courses/{id}/students/` | teacher (o'ziniki), admin, super_admin | — | `EnrollmentSerializer[]` (paginated) | Kursga yozilgan o'quvchilar |
| POST | `/courses/{id}/enroll/` | teacher (o'ziniki), parent (farzandi uchun) | `student_id` yoki `student`(username/invite_code) | `EnrollmentSerializer` | O'qituvchi/ota-ona to'g'ridan-to'g'ri biriktiradi — **darhol APPROVED** (o'quvchi/ota-ona so'rovidan farqli) |
| POST | `/courses/{id}/unenroll/` | teacher, parent | `student_id` | `{"removed": bool}` | Kursdan chiqarish |

**`CourseSerializer`** (barcha rol uchun bir xil): `id, teacher, title, subject, description, is_active, student_count, my_status, is_language_subject, created_at`
- `is_language_subject` — **yangi maydon**: `course.subject`dan (`apps.homework.ai.detect_profile`) avtomatik aniqlanadi. Til fani (ingliz/rus/turk...) bo'lsa `true`. Frontend shu asosida vazifa yaratishda "tekshiruv turi" (writing/reading/listening/speaking) tanlovini **faqat shunda** ko'rsatishi kerak.

---

## 3. Darslar va video yozuv (`/api/v1/lessons/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/lessons/` | teacher (`lesson.schedule`) | `course, title, starts_at, duration_min` | `LessonSerializer` | Bitta dars yaratadi (faqat o'z kursiga; `starts_at` o'tgan vaqt bo'lishi mumkin emas) |
| PUT/PATCH | `/lessons/{id}/` | teacher (o'ziniki) | xuddi yuqoridagidek | `LessonSerializer` | Tahrirlash |
| DELETE | `/lessons/{id}/` | teacher (o'ziniki) | — | 204 | O'chirish (soft-delete) |
| POST | `/lessons/{id}/finish/` | teacher (o'ziniki, `lesson.finish`) | `recording_title` (ixtiyoriy) | `LessonSerializer` | Darsni yakunlaydi: davomatlarni yopadi, chatga `lesson_ended` yuboradi, doska PDF'ini guruh chatga tashlaydi, video yozuvni to'xtatadi va (haqiqatan yozib olingan bo'lsa) "🎥 yozuv tayyor" xabarini beradi |
| GET/DELETE | `/lessons/{id}/recording/` | GET: teacher/o'quvchi/tasdiqlangan ota-ona; DELETE: faqat teacher (o'ziniki) | — | GET: `{lesson_id, title, status, ready, created_at, ended_at, error, stream_url}`; DELETE: 204 | GET — yozuv holati + tayyor bo'lsa **imzolangan, 3 soatlik** `stream_url`; DELETE — faylni butunlay o'chiradi |
| GET | `/lessons/{id}/recording/stream/?t=<token>` | Auth shart emas — faqat imzolangan token orqali | — | video/mp4 oqim (Range qo'llab-quvvatlanadi) | `recording_info` bergan muddatli tokensiz ochilmaydi |

---

## 4. Davomat (`/api/v1/attendance/`)

Barcha rol uchun (`attendance.view`): teacher — o'z kurslari, parent — tasdiqlangan farzandlari, admin — hammasi. Maydonlar: `id, lesson, lesson_title, student, joined_at, left_at, minutes, attention_total, attention_answered, focus_exits, focus{exits, away_seconds, longest_seconds, timeline:[{left_at, returned_at, seconds}]}, focus_alert`.

---

## 5. Live (`/api/v1/live/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/live/allow-share/` | teacher (o'ziniki, `room.moderate`) | `lesson_id, identity` | `{"ok": true}` | O'quvchiga ekran ulashish ruxsatini jonli beradi (LiveKit orqali) |

`POST /live/token/`ni **o'qituvchi** chaqirsa: `is_teacher: true`, birinchi kirishda dars `LIVE` bo'ladi, chatga `lesson_live` yuboriladi, video yozuv kafolatlanadi — bularning barchasi xuddi shu (o'quvchi ham ishlatadigan) endpoint javobida.

---

## 6. Chat (`/api/v1/chat/`)

**Diqqat**: `chat.use` faqat `teacher` va `student`da bor — **`parent` chatga umuman kira olmaydi** (REST ham, WebSocket ham).

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/chat/rooms/direct/respond/` | teacher (o'z shaxsiy xonasi) | `room_id, action(accept\|block)` | `ChatRoomSerializer` | O'quvchining shaxsiy chat so'roviga javob |
| POST | `/chat/rooms/{id}/image/` | teacher (o'z kurs guruhi) | multipart: `image` | `ChatRoomSerializer` | Guruh chat rasmini o'rnatadi |

---

## 7. Doska (`/api/v1/board/{lesson_id}/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/board/{lesson_id}/sheet/` | teacher (o'ziniki, `room.moderate`) | — | `{"index": int}` | Yangi bo'sh sheet ochadi |
| POST | `/board/{lesson_id}/grant/` | teacher (o'ziniki, `room.moderate`) | `student_id` | `{"ok": true}` | O'quvchiga chizish ruxsati beradi |

`GET /board/{lesson_id}/` — `is_teacher=true` bo'lganda javobga qo'shimcha `away_students: [{student_id, name}]` qo'shiladi (hozir darsdan "chiqib ketgan" o'quvchilar).

---

## 8. Uyga vazifa (`/api/v1/homework/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/homework/assignments/` | teacher (o'ziniki, `homework.assign`) | multipart/JSON: `course_id, title, description, body, due_at, skill_key(writing\|reading\|listening\|speaking), **lesson_id**(yangi, ixtiyoriy), extra_instructions, attachment` | `id, course_id, course_title, subject, title, description, body, attachment_name, has_attachment, due_at, skill_key, lesson_id, lesson_title, created_at` | Vazifa yaratadi. **`lesson_id`** — shu kursning **tugagan (finished)** darsiga bog'lash; boshqa holatda 400 (`"Faqat tugagan darsga vazifa bog'lash mumkin."`). Bitta darsga bir nechta vazifa berish mumkin, cheklov yo'q. `is_language_subject=false` bo'lgan kurslarda `skill_key` ko'rsatilmasin (frontend qarori) |
| DELETE | `/homework/assignments/{id}/` | teacher (o'ziniki) | — | 204 | Vazifani o'chiradi |
| POST | `/homework/submissions/{id}/recheck/` | teacher (o'ziniki, `homework.assign`) | — | `_submission_dict` + `result` | AI tekshiruvini qayta ishga tushiradi |

**Teacherga xos farqlar**:
- `GET /homework/assignments/?course=<id>` — o'qituvchiga har bir vazifada `submissions_count` (o'quvchining `my_submission` o'rniga)
- `GET /homework/assignments/{id}/` — o'qituvchiga `submissions:[...]` (hammasi) + `stats:{students_count, submitted_count, avg_score}`
- Ota-ona ham `GET /homework/assignments/` va `/{id}/` chaqira oladi (`homework.view`), farzandining topshirig'ini ko'radi, lekin topshira/yarata olmaydi

---

## 9. Bildirishnomalar (`/api/v1/notifications/`) — hujjatlashtirilmagan edi

**Modellar**: `Notification` (`sender, description, target_type(user\|all), created_at`), `NotificationRecipient` (`notification, user, read_at`).

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/notifications/` | har qanday login qilgan | — | `InboxItemSerializer[]` (paginated): `id, notification{id,sender,description,target_type,created_at}, is_read, read_at, created_at` | O'z inbox'i (barcha rol) |
| POST | `/notifications/read/{id}/` | har qanday login qilgan | — | `{"ok": true}` | Bitta xabarni o'qilgan deb belgilaydi |
| GET | `/notifications/unread-count/` | har qanday login qilgan | — | `{"count": int}` | O'qilmagan sони |
| POST | `/notifications/send/` | **admin, super_admin** (`notification.send`) | `description`(HTML, tozalanadi), `target_type(user\|all)`, `user_id`(target_type=user bo'lsa majburiy) | `id, sender, description, target_type, created_at` | Bitta foydalanuvchiga yoki **hammaga** bildirishnoma yuboradi (real-vaqt WS orqali ham) |
| GET | `/notifications/sent/` | admin, super_admin | — | `id, description, target_type, created_at, read_count, total_count` (paginated) | Yuborilgan bildirishnomalar ro'yxati |
| GET | `/notifications/{id}/recipients/` | admin, super_admin (faqat o'zi yuborgan) | — | `[{user, read_at}]` | Bitta bildirishnoma bo'yicha kim o'qigan/o'qimagan |

**WebSocket**: `wss://<domain>/ws/notifications/?token=<JWT access>` — **barcha rol** uchun ochiq. Kelib turadi: `{"type":"notification", "notification":{...}}`.

---

## Yopiq/mavjud bo'lmagan narsalar

- `course.moderate`, `lesson.cancel` — admin ruxsat jadvalida bor, lekin **ulanган endpoint yo'q**
- Admin kurs/dars/chat yarata yoki tahrirlay olmaydi — faqat `super_admin` (wildcard)

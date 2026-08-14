# Qilingan ishlar — to'liq API va funksiyalar ro'yxati

Bu — loyihada bajarilgan barcha backend ishlarining **yagona, jamlangan** hujjati
(oldin `STAFF_API.md`, `STUDENT_API.md`, `HOMEWORK_AI_REVIEW_API.md` va shu faylga
bo'lib yozilgan edi — endi bittaga birlashtirildi). Frontend jamoasi shu hujjat
asosida UI qura oladi: har bo'limda aniq endpoint, kim chaqira olishi, so'rov/javob
shakli berilgan.

**Base URL**: `/api/v1/`
**Auth**: JWT (`Authorization: Bearer <access_token>`)

---

## Mundarija

1. [Rol va ruxsatlar](#1-rol-va-ruxsatlar)
2. [Auth / Accounts](#2-auth--accounts)
3. [Kurslar](#3-kurslar)
4. [Darslar va video yozuv](#4-darslar-va-video-yozuv)
5. [Davomat](#5-davomat)
6. [Live / video dars xonasi](#6-live--video-dars-xonasi)
7. [Chat](#7-chat)
8. [Doska / Whiteboard](#8-doska--whiteboard)
9. [Uyga vazifa (Homework + AI tekshiruv)](#9-uyga-vazifa-homework--ai-tekshiruv)
10. [Bildirishnomalar](#10-bildirishnomalar)
11. [O'quvchiga yopiq endpointlar](#11-oquvchiga-yopiq-endpointlar)

---

## 1. Rol va ruxsatlar

`apps/core/permissions.py`:

```
super_admin: '*' (hammasi)
admin:       course.view, course.moderate, lesson.view, lesson.cancel,
             attendance.view, audit.view, user.manage, notification.send
teacher:     course.create/edit/view/enroll, lesson.schedule/edit/cancel/finish/view,
             lesson.rate, room.token, room.moderate, attendance.view, chat.use,
             homework.assign/view, child.create
student:     course.view/enroll, lesson.view/rate, room.token/leave, link.respond,
             attendance.view, chat.use, homework.submit/view
parent:      child.create, link.request/view, consent.manage,
             course.view/enroll, lesson.view, attendance.view, homework.view
```

**Muhim eslatmalar**:
- `admin`da `course.create/edit`, `chat.use`, `homework.assign`, `room.token` **yo'q** — admin faqat ko'rish/moderatsiya + bildirishnoma yuborish + foydalanuvchi qidirish uchun, kurs/dars/chatni faqat `super_admin` (wildcard) boshqara oladi.
- `parent`da `chat.use` **yo'q** — ota-ona chatga umuman kira olmaydi (na REST, na WebSocket), garchi farzandining darsi/vazifasi/davomatini ko'rsa ham.
- `course.moderate`/`lesson.cancel` ruxsatlari admin ro'yxatida bor, lekin ularni tekshiradigan **hech qanday endpoint yo'q** (ulanmagan).
- **Bitta akkaunt = bitta qurilma cheklovi olib tashlangan** — endi bir akkaunt bilan bir vaqtda istalgancha qurilmadan kirish mumkin (qarang: §2).

---

## 2. Auth / Accounts (`/api/v1/auth/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/auth/register/` | Hammaga ochiq, lekin `role` faqat `teacher`\|`parent` | `username, password, first_name, last_name, role, phone` | `id, username, first_name, last_name, role, phone` | Ochiq ro'yxatdan o'tish (o'quvchi faqat `/children/` orqali yaratiladi) |
| POST | `/auth/login/` | Hammaga ochiq | `username, password` | `refresh, access` | Login. **Bir akkaunt bilan bir vaqtda istalgancha qurilmadan kirish mumkin** (cheklov olib tashlangan) |
| POST | `/auth/logout/` | Login qilgan | `refresh`(ixtiyoriy) | 204 | Chiqish — berilgan refresh token bekor qilinadi (qayta ishlatib bo'lmaydi); boshqa qurilmalardagi sessiyalarga ta'sir qilmaydi |
| POST | `/auth/token/refresh/` | — | `refresh` | `access` | Access tokenni yangilash |
| GET | `/auth/me/` | Login qilgan | — | `id, username, first_name, last_name, role, phone, invite_code, avatar` | O'z profili |
| PUT/PATCH | `/auth/me/` | Login qilgan | `username, first_name, last_name, phone, avatar`(multipart, rasm fayl) | yuqoridagidek | Profilni tahrirlash (profil rasmi shu orqali o'rnatiladi) |
| GET | `/auth/logins/?student=<id>` | O'zi; ota-ona (tasdiqlangan farzandi uchun) | — | ro'yxat: `{at, ip, user_agent, new_ip, new_device}` | Login tarixi (qurilma/IP o'zgargan hollari belgilangan) |
| POST | `/auth/children/` | teacher, parent (`child.create`) | `username, password, first_name, last_name` | `id, username, first_name, last_name, invite_code` | O'quvchi hisobini yaratadi. Ota-ona yaratsa — `ParentChildLink` darhol APPROVED. O'qituvchi yaratsa — bog'lanish yaratilmaydi, faqat `invite_code` beriladi |
| GET | `/auth/users/search/?q=` | admin, super_admin (`user.manage`) | — | `UserSerializer[]` (max 10) | Barcha rollar bo'yicha foydalanuvchi qidirish |
| GET | `/auth/links/` | student | — | ro'yxat: `id, parent, student, status, created_at, responded_at` | Ota-onadan kelgan bog'lanish so'rovlari |
| POST | `/auth/links/request/` | parent (`link.request`) | `invite_code` | link obyekti | Ota-ona bola invite_code'i orqali bog'lanish so'raydi (PENDING) |
| POST | `/auth/links/{id}/respond/` | student | `action`: `approve`\|`decline` | link obyekti | So'rovni tasdiqlash/rad etish |
| GET/POST | `/auth/consents/` | parent (`consent.manage`) | POST: `student, kind(recording\|camera\|analytics), granted` | `id, student, kind, granted, updated_at` | Ota-ona farzandi uchun rozilik belgilaydi |

---

## 3. Kurslar (`/api/v1/courses/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/courses/` | student | `?search=` | ro'yxat: `CourseSerializer` | Yozilgan kurslarim |
| GET | `/courses/catalog/` | student | — | `CourseSerializer[]` | Barcha ochiq kurslar (yozilish uchun) |
| GET | `/courses/{id}/` | a'zolar | — | `CourseSerializer` | Kurs tafsiloti |
| POST | `/courses/` | teacher (`course.create`) | `title, subject, description` | `CourseSerializer` | Kurs yaratadi (guruh chati avtomatik ochiladi) |
| PUT/PATCH | `/courses/{id}/` | teacher (o'ziniki) | yuqoridagidek | `CourseSerializer` | Tahrirlash |
| DELETE | `/courses/{id}/` | teacher (o'ziniki) | — | 204 | **Qaytarib bo'lmaydi**: video yozuvlar, doska (chizma+PDF), chat xonasi+xabarlar+fayllar, barcha a'zolik butunlay o'chadi; darslar faqat yashiriladi (Davomat/Baho tarixi saqlanadi) |
| GET | `/courses/requests/` | teacher (`course.edit`) | — | `EnrollmentSerializer[]` | O'z kurslariga kelgan kutilayotgan yozilish so'rovlari |
| POST | `/courses/requests/respond/` | teacher | `enrollment_id, action(approve\|decline)` | `EnrollmentSerializer` | So'rovga javob |
| POST | `/courses/{id}/schedule/` | teacher (`lesson.schedule`) | `title, days:[0-6], start_time, end_time, weeks(1-52), start_date, note` | `{count, lessons:[...]}` (201) | Haftalik jadval bo'yicha ko'plab dars yaratadi; vaqt to'qnashuvini tekshiradi (`{conflicts:[...]}` 400) |
| GET | `/courses/{id}/search-students/?q=` | teacher (o'ziniki), admin | — | `[{...user, enroll_status}]` (max 10) | O'quvchi qidirish |
| GET | `/courses/{id}/students/` | teacher (o'ziniki), admin | — | `EnrollmentSerializer[]` | Kursga yozilgan o'quvchilar |
| POST | `/courses/{id}/enroll/` | student; teacher (o'ziniki); parent (farzandi uchun) | student: — ; teacher/parent: `student_id`/`student` | `EnrollmentSerializer` | Student uchun so'rov (`pending`); teacher/parent uchun **darhol APPROVED** |
| POST | `/courses/{id}/unenroll/` | teacher, parent, student | `student_id` | `{"removed": bool}` | Kursdan chiqarish. **Yon ta'sir**: chiqarilgan o'quvchining o'sha guruh chatida ochiq WebSocket ulanishi bo'lsa, server darhol `{"type": "removed"}` yuboradi va ulanishni `code=4403` bilan yopadi |

**`CourseSerializer`**: `id, teacher, title, subject, description, is_active, student_count, my_status, is_language_subject, created_at`
- `is_language_subject` — `course.subject`dan (`apps.homework.ai.detect_profile`) avtomatik aniqlanadi. Til fani bo'lsa `true`. Frontend shu asosida vazifa yaratishda "tekshiruv turi" (writing/reading/listening/speaking) tanlovini **faqat shunda** ko'rsatishi kerak.

---

## 4. Darslar va video yozuv (`/api/v1/lessons/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/lessons/` | a'zolar | `?course=`, `?status=`, `?ordering=starts_at` | ro'yxat: `id, course, course_title, title, starts_at, duration_min, status, room_name, created_at, avg_rating, rating_count` | Mening darslarim |
| GET | `/lessons/{id}/` | a'zolar | — | yuqoridagidek | Dars tafsiloti |
| POST | `/lessons/` | teacher (`lesson.schedule`) | `course, title, starts_at, duration_min` | `LessonSerializer` | Bitta dars yaratadi (`starts_at` o'tgan vaqt bo'lishi mumkin emas) |
| PUT/PATCH | `/lessons/{id}/` | teacher (o'ziniki) | yuqoridagidek | `LessonSerializer` | Tahrirlash |
| DELETE | `/lessons/{id}/` | teacher (o'ziniki) | — | 204 | O'chirish (soft-delete) |
| POST | `/lessons/{id}/finish/` | teacher (o'ziniki, `lesson.finish`) | `recording_title`(ixtiyoriy) | `LessonSerializer` | Darsni yakunlaydi: davomatlarni yopadi, chatga `lesson_ended`, doska PDF'ini guruh chatga fayl sifatida tashlaydi, video yozuvni to'xtatadi |
| POST | `/lessons/{id}/rate/` | student | `stars`(1-5), `description`(ixtiyoriy) | `id, lesson, student, stars, description, created_at` | Tugagan darsga baho (dars `finished` bo'lishi shart) |
| GET | `/lessons/{id}/ratings/` | a'zolar | — | `LessonRating[]` | Darsga qoldirilgan barcha baholar |
| GET | `/lessons/{id}/recording/` | a'zolar | — | `{lesson_id, title, status, ready, created_at, ended_at, error, stream_url}` | Yozuv holati. `status`: `recording`\|`completed`\|`failed`. `stream_url` faqat `ready:true`da keladi |
| DELETE | `/lessons/{id}/recording/` | teacher (o'ziniki) | — | 204 | Yozuvni butunlay o'chiradi (fayl + baza) |
| GET | `/lessons/{id}/recording/stream/?t=<token>` | Auth shart emas — faqat imzolangan token | — | video/mp4 oqim (Range/seek qo'llab-quvvatlanadi) | Video oqimi |

**Video yozuv haqida muhim**: `stream_url` — **muddatli imzolangan havola (3 soat)**, doimiy URL emas — har safar `GET /recording/` bilan yangisini olish kerak. Yuklab olish tugmasi yo'q, faqat platforma ichida ko'rish (`inline`). Yozuv o'qituvchi darsga har kirganida **avtomatik** boshlanadi (720p/30fps preset — CPU tejash uchun), dars tugaganda to'xtaydi.

---

## 5. Davomat (`/api/v1/attendance/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/attendance/` | teacher (o'z kurslari), parent (tasdiqlangan farzandi), student (o'zi), admin (hammasi) | `?lesson=`, `?student=` | ro'yxat: `id, lesson, lesson_title, student, joined_at, left_at, minutes, attention_total, attention_answered, focus_exits, focus{exits, away_seconds, longest_seconds, timeline:[{left_at, returned_at, seconds}]}, focus_alert` | Davomat yozuvlari |
| GET | `/attendance/{id}/` | yuqoridagidek | — | yuqoridagidek | Bitta yozuv tafsiloti |

`focus_alert` (`true`/`false`) — o'quvchi shu darsda diqqat-nazoratida belgilangan chegaradan (default **3** marta oynadan chiqish, `.env`dagi `FOCUS_PARENT_ALERT_THRESHOLD`) oshib ketganmi — ota-onaga signal shu orqali ko'rinadi.

---

## 6. Live / video dars xonasi (`/api/v1/live/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/live/token/` | teacher, student | `lesson_id` | `{token, url, room, is_teacher}` | LiveKit video xonaga kirish tokeni. O'qituvchi kirsa: dars `LIVE` bo'ladi, chatga `lesson_live`, video yozuv avtomatik boshlanadi. O'quvchi kirsa: davomat avtomatik belgilanadi |
| POST | `/live/leave/` | teacher, student | `lesson_id` | `{"updated": bool}` | Darsdan chiqish (davomat yopiladi) |
| GET | `/live/attention/?lesson_id=` | student | — | `{"check": null}` yoki `{"check": {id, due_at}}` | "Sen hali shu yerdamisan?" so'rovi bormi (polling) |
| POST | `/live/attention/` | student | `check_id` | `{"answered_at"}` | Attention check'ga javob |
| POST | `/live/focus/` | student | `lesson_id`, `kind`: `exit`\|`return` | `{"ok", "kind", "exit_count", "threshold", "parent_notified"}` | Anti-cheat: darsdan chiqib/qaytganini belgilash |
| POST | `/live/allow-share/` | teacher (o'ziniki, `room.moderate`) | `lesson_id, identity` | `{"ok": true}` | O'quvchiga ekran ulashish ruxsatini jonli beradi |
| POST | `/live/request-mic/` | student | `lesson_id` | `{"ok": true}` | **Yangi**: mikrofon so'rash ("qo'l ko'tarish") — o'qituvchiga doska WebSocket kanali orqali darhol ko'rinadi |
| POST | `/live/grant-mic/` | teacher (o'ziniki, `room.moderate`) | `lesson_id, student_id` | `{"ok": true}` | **Yangi**: o'quvchiga mikrofon ruxsatini jonli ochadi |
| POST | `/live/invite/` | teacher (o'ziniki, `room.moderate`) | `lesson_id`, `student_id`(ixtiyoriy) | `{"invited": N}` | **Yangi**: darsga taklif bildirishnomasi. `student_id` bo'lmasa — kursga yozilgan hammaga |
| POST | `/live/ban/` | teacher (o'ziniki, `room.moderate`) | `lesson_id, student_id` | `{"ok": true}` | **Yangi**: o'quvchini shu darsdan chetlashtiradi — hozir xonada bo'lsa darhol chiqaradi, qayta kirishini bloklaydi (faqat shu darsga, kursga emas) |
| POST | `/live/unban/` | teacher (o'ziniki, `room.moderate`) | `lesson_id, student_id` | `{"unbanned": bool}` | **Yangi**: chetlashtirishni bekor qiladi |

### Mikrofon: standart holat o'zgardi

**Endi o'quvchi darsga kirganda mikrofon O'CHIQ holda kiradi** (kamera esa erkin) —
avval ikkalasi ham avtomatik yoqiq edi. O'quvchi gapirish uchun avval
`POST /live/request-mic/` chaqiradi ("qo'l ko'tarish"), o'qituvchi buni doska
WebSocket kanali orqali jonli ko'radi (`{"type": "mic_request", "student_id", "name"}`),
`POST /live/grant-mic/` bilan ruxsat beradi. Ruxsat berilgach, ikkala tomonga ham
(o'quvchining o'ziga — mikrofon tugmasini yoqish uchun; o'qituvchiga — kutish
ro'yxatidan olib tashlash uchun) doska kanali orqali `{"type": "mic_granted", "student_id"}`
signali keladi.

So'rov bazada ham saqlanadi (faqat WS xabari emas) — `GET /board/{lesson_id}/`
javobida (teacher uchun, `away_students` bilan bir qatorda) `pending_mic_requests:
[{student_id, name}]` maydoni bor, shuning uchun o'qituvchi so'rovdan keyin kirsa
yoki sahifani yangilasa ham joriy so'rovlar yo'qolib qolmaydi.

### Darsdan chetlashtirish (invite/ban) — frontendda nima kutish kerak

- **Taklif** (`invite`) real-time bildirishnoma orqali keladi (mavjud `/ws/notifications/` kanali, yangisi shart emas): `{"type": "notification", "notification": {..., "description": "«<dars>» darsi boshlandi — hoziroq kiring."}}`.
- **Ban** qilingan o'quvchi hozir xonada bo'lsa — LiveKit client SDK'da `disconnected`/kicked hodisasi keladi. Qayta `POST /live/token/` chaqirsa — `403 {"code": "permission_denied", "message": "Siz bu darsdan chetlashtirilgansiz."}`.
- Ban faqat **shu bitta darsga** tegishli — boshqa darslarga yoki `Enrollment`ga ta'sir qilmaydi.

---

## 7. Chat (`/api/v1/chat/`)

**Diqqat**: `chat.use` faqat `teacher` va `student`da bor — **`parent` chatga umuman kira olmaydi** (REST ham, WebSocket ham).

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/chat/rooms/` | teacher, student | — | ro'yxat: `id, kind(course/direct), course, direct_status, image, title, last_message{text, sender, created_at, file_url}, unread, other_user, live_lesson{id,title,room_name}\|null, updated_at` | Mening chat xonalarim. `live_lesson` bo'lsa — kurs guruhida hozir jonli dars ketyapti |
| GET | `/chat/rooms/{id}/` | a'zolar | — | yuqoridagidek | Xona tafsiloti |
| GET | `/chat/rooms/{id}/messages/` | a'zolar | `?after=<ISO datetime>` | xabarlar: `id, room, sender, text, file_url, created_at` | Xabarlar tarixi / polling |
| POST | `/chat/rooms/{id}/send/` | a'zolar | `text`(max 4000) | xabar obyekti | Xabar yuborish |
| POST | `/chat/rooms/direct/request/` | student | `teacher`(id/username) | `ChatRoomSerializer` | O'qituvchi bilan shaxsiy chat so'rovi |
| POST | `/chat/rooms/direct/respond/` | teacher (o'z shaxsiy xonasi) | `room_id, action(accept\|block)` | `ChatRoomSerializer` | Shaxsiy chat so'roviga javob |
| GET | `/chat/rooms/teachers/` | student | — | `[{...user, direct_status, room_id}]` | Mening o'qituvchilarim (shaxsiy chat boshlash uchun) |
| POST | `/chat/rooms/{id}/image/` | teacher (o'z kurs guruhi) | multipart: `image` | `ChatRoomSerializer` | Guruh chat rasmini o'rnatadi |
| GET | `/chat/files/{message_id}/` | a'zolar | — | fayl | Chatga biriktirilgan faylni ko'rish (doska PDF va h.k.) |

**WebSocket**: `wss://<domain>/ws/chat/<room_id>/?token=<JWT access>`
- Kelib turadi: `{type:"message", message:{...}}`, `{type:"typing", user_id, name}`, `{type:"lesson_live", lesson:{id,title,room_name}}`, `{type:"lesson_ended", lesson_id}`, `{type:"removed"}` (guruhdan chiqarilganda — ulanish `4403` bilan yopiladi)
- Yuboriladi: `{type:"message", text}`, `{type:"typing"}`

---

## 8. Doska / Whiteboard (`/api/v1/board/{lesson_id}/`)

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/board/{lesson_id}/` | a'zolar | — | `{sheets:[{index, strokes}], can_draw, is_teacher, size, subject}` (teacher uchun qo'shimcha `away_students: [{student_id, name}]`, `pending_mic_requests: [{student_id, name}]`) | Doska holati |
| POST | `/board/{lesson_id}/stroke/` | a'zolar (ruxsat bilan) | `sheet`(int), `stroke` | saqlangan stroke | Chizish/matn qo'shish |
| POST | `/board/{lesson_id}/erase/` | a'zolar (ruxsat bilan) | `sheet`, `stroke_ids`, `reason`(majburiy) | `{"removed": count}` | O'chirish |
| POST | `/board/{lesson_id}/solve/` | a'zolar | `expr` | yechim | Formula yechish (Photomath uslubida) |
| GET | `/board/{lesson_id}/pdf/` | a'zolar | — | PDF | Doskani PDF yuklab olish |
| POST | `/board/{lesson_id}/sheet/` | teacher (o'ziniki, `room.moderate`) | — | `{"index": int}` | Yangi bo'sh sheet |
| POST | `/board/{lesson_id}/grant/` | teacher (o'ziniki, `room.moderate`) | `student_id` | `{"ok": true}` | O'quvchiga chizish ruxsati |

**WebSocket**: `wss://<domain>/ws/board/<lesson_id>/?token=<JWT access>`
- Kelib turadi: `{type:"stroke", ...}`, `{type:"erase", ...}`, `{type:"sheet", index}`, `{type:"focus", student_id, name, kind}` (teacher uchun — o'quvchi oynadan chiqdi/qaytdi), `{type:"mic_request", student_id, name}` (teacher uchun), `{type:"mic_granted", student_id}` (hammaga)
- Yuboriladi: `{type:"stroke", sheet, stroke}`

---

## 9. Uyga vazifa (Homework + AI tekshiruv) (`/api/v1/homework/`)

### 9.1 Asosiy endpointlar

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/homework/assignments/?course=<id>` | a'zolar | — | student: ro'yxat + `my_submission`; teacher: + `submissions_count` | Kurs bo'yicha vazifalar |
| GET | `/homework/assignments/{id}/` | a'zolar | — | teacher: `submissions[...]` (hammasi) + `stats`; student: faqat o'ziniki | Vazifa tafsiloti |
| GET | `/homework/assignments/{id}/file/` | a'zolar | — | fayl | Vazifaga biriktirilgan faylni yuklab olish |
| POST | `/homework/assignments/` | teacher (o'ziniki, `homework.assign`) | multipart/JSON: `course_id, title, description, body, due_at, skill_key(writing\|reading\|listening\|speaking), lesson_id(ixtiyoriy), extra_instructions, attachment` | `id, course_id, ..., lesson_id, lesson_title, is_language_subject, created_at` | Vazifa yaratadi. `lesson_id` — shu kursning **tugagan** darsiga bog'lash (400 aks holda). Bitta darsga bir nechta vazifa berish mumkin |
| DELETE | `/homework/assignments/{id}/` | teacher (o'ziniki) | — | 204 | Vazifani o'chiradi |
| POST | `/homework/assignments/{id}/submit/` | student | multipart: `file`(PDF/rasm/DOCX, yoki `speaking` uchun audio) | submission obyekti, `status="pending_review"` | Topshirish — AI tekshiruvi fonda boshlanadi |
| GET | `/homework/submissions/{id}/` | a'zolar | — | quyida (§9.2) | AI natijasini kuzatish (polling) |
| GET | `/homework/submissions/{id}/file/` | a'zolar | — | fayl | Topshirilgan faylni yuklab olish |
| POST | `/homework/submissions/{id}/recheck/` | teacher (o'ziniki, `homework.assign`) | — | teacher shaklida (§9.2) | AI tekshiruvini qayta ishga tushiradi |
| POST | `/homework/submissions/{id}/review/` | teacher (o'ziniki, `homework.assign`) | `overall_score`(ixtiyoriy), `grade`(ixtiyoriy), `result`(ixtiyoriy, to'liq JSON) | teacher shaklida | AI natijasini tasdiqlaydi — quyida §9.3 |
| POST | `/homework/assignments/{id}/focus/` | student | `kind`: `exit`\|`return` | `{"ok": true}` | Vazifa sahifasida vaqt kuzatuvi |

### 9.2 AI baholash — ish oqimi: AI taklif qiladi, o'qituvchi tasdiqlaydi

Ilgari AI tekshirgach natija darhol `done` bo'lib hammaga ko'rinardi. Endi:

1. AI tekshiradi → status `pending_review` — bu AI'ning **taklifi**, hali yakuniy emas. **Bu bosqichda o'quvchi/ota-onaga natija ko'rinmaydi** (`overall_score`, `grade`, `result` — `null`), faqat status "ko'rib chiqilmoqda" ko'rinadi.
2. **Faqat o'qituvchi** shu bosqichda AI'ning taklifini (ball, baho, feedback) darhol ko'radi.
3. O'qituvchi ko'rib chiqadi — xohlasa ball/baho/feedbackni **tahrirlab**, `POST /review/` bilan tasdiqlaydi. Tasdiqlash **AI natijasining ustidan yoziladi** (bitta yakuniy natija). Shundan keyingina status `done` bo'ladi va natija o'quvchi/ota-onaga ochiladi.
4. AI'ning asl (o'zgarmas) natijasi audit/taqqoslash uchun fonda saqlanadi — faqat o'qituvchiga ko'rinadi.

**`Submission.status` qiymatlari**: `checking` (AI tekshiryapti) → `pending_review` (o'qituvchini kutmoqda) → `done` (tasdiqlangan) yoki `error`.

**Submission javobi — o'quvchi/ota-ona uchun**:
```json
{
  "id": "...", "assignment_id": "...", "student_id": "...", "student_name": "...",
  "file_name": "...", "status": "pending_review",
  "overall_score": null, "grade": "", "result": null,
  "error": "", "is_late": false, "created_at": "...", "checked_at": "..."
}
```
`status == "done"` bo'lsa `overall_score`/`grade`/`result` to'liq qiymat bilan qaytadi.

**Submission javobi — o'qituvchi uchun** (yuqoridagilarga qo'shimcha):
```json
{
  "overall_score": 78, "grade": "Yaxshi", "result": { "...": "AI/yakuniy natija" },
  "reviewed_at": null, "reviewed_by": null,
  "ai_overall_score": 78, "ai_grade": "Yaxshi", "ai_result": { "...": "AI'ning asl natijasi" },
  "focus": {
    "exits": 2, "away_seconds": 340, "longest_seconds": 210,
    "on_page_seconds": 610, "total_seconds": 950,
    "timeline": [{"left_at": "...", "returned_at": "...", "seconds": 210}]
  }
}
```
O'qituvchi `overall_score`ni **PENDING_REVIEW bosqichida ham darhol** ko'radi (AI taklifi) — faqat o'quvchi/ota-onadan yashiriladi. `ai_result`/`focus` faqat tafsilot javobida bor, ro'yxat ko'rinishida yo'q.

### 9.3 Tasdiqlash

```
POST /homework/submissions/{id}/review/
{}                                                    → AI natijasi o'zgarishsiz tasdiqlanadi
{"overall_score": 90, "grade": "A'lo", "result": {...}}  → tahrirlab tasdiqlanadi
```
Faqat `status == "pending_review"` bo'lgan topshiriqni tasdiqlash mumkin (aks holda 400).

### 9.4 Vaqt kuzatuvi (focus)

`focus_summary` — darslardagi diqqat kuzatuvi bilan bir xil chiqish/qaytish algoritmi, faqat yopilmagan chiqish `hozir`gacha hisoblanadi (vazifa sahifasida darsning "tugash" chegarasi yo'qligi sababli): `exits`, `away_seconds`, `longest_seconds`, `on_page_seconds`, `total_seconds`, `timeline`. Faqat o'qituvchiga ko'rinadi.

---

## 10. Bildirishnomalar (`/api/v1/notifications/`)

**Modellar**: `Notification` (`sender, description, target_type(user\|all), created_at`), `NotificationRecipient` (`notification, user, read_at`).

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| GET | `/notifications/` | har kim | — | `InboxItemSerializer[]`: `id, notification{id,sender,description,target_type,created_at}, is_read, read_at, created_at` | O'z inbox'i |
| POST | `/notifications/{id}/read/` | qabul qiluvchi | — | `{"ok": true}` | O'qildi deb belgilash |
| GET | `/notifications/unread-count/` | har kim | — | `{"count": int}` | Bell/badge uchun |
| POST | `/notifications/send/` | admin, super_admin (`notification.send`) | `description`(HTML, `nh3` bilan tozalanadi — faqat formatlash teglari, rasm/skript yo'q), `target_type(user\|all)`, `user_id`(target_type=user bo'lsa majburiy) | `id, sender, description, target_type, created_at` | Bitta foydalanuvchiga yoki hammaga yuboradi (real-vaqt WS orqali ham) |
| GET | `/notifications/sent/` | admin, super_admin | — | `id, description, target_type, created_at, read_count, total_count` | Yuborilganlar ro'yxati |
| GET | `/notifications/{id}/recipients/` | admin, super_admin (o'zi yuborgan) | — | `[{user, read_at}]` | Kim o'qidi/o'qimadi |

**WebSocket**: `wss://<domain>/ws/notifications/?token=<JWT access>` — barcha rol uchun ochiq. Kelib turadi: `{"type":"notification", "notification":{...}}`. Ulanish yopilishi: `4401` — token yaroqsiz.

**Django admin** (`/admin/notifications/notification/`) — faqat ko'rish/jurnal; yuborish uchun ro'yxat tepasidagi "Yangi xabar yuborish" havolasi (`/admin/notifications/notification/send/`) orqali maxsus forma ishlatiladi (xom "Add" formasi ataylab o'chirilgan — u fan-out qatorlarini yaratmaydi).

---

## 11. O'quvchiga yopiq endpointlar

Frontendda o'quvchi rolida ko'rsatilmasin:

- Auth: `/register/`, `/children/`, `/links/request/`, `/consents/` — faqat ota-ona/o'qituvchi
- Kurs/dars: yaratish/tahrirlash/o'chirish, `/courses/requests/`, `/courses/{id}/schedule/`, `/courses/{id}/search-students/`, `/courses/{id}/students/`, `/lessons/{id}/finish/` — faqat o'qituvchi/admin
- Live: `/live/allow-share/`, `/live/grant-mic/`, `/live/invite/`, `/live/ban/`, `/live/unban/` — faqat o'qituvchi
- Chat: `/chat/rooms/direct/respond/` — faqat o'qituvchi
- Doska: `/board/{id}/sheet/`, `/board/{id}/grant/` — faqat o'qituvchi
- Homework: vazifa yaratish/o'chirish, `/submissions/{id}/recheck/`, `/submissions/{id}/review/` — faqat o'qituvchi
- Notifications: `/notifications/send/`, `/notifications/sent/`, `/notifications/{id}/recipients/` — faqat admin/super_admin

**Frontend uchun umumiy eslatma**: yozilish va chat so'rovlari **async** (`pending` → tasdiqlash/rad etish kutiladi) — UI `status`/`my_status`/`direct_status` maydonlariga qarab holatni ko'rsatsin, darhol kirish huquqi berilgan deb hisoblamasin.

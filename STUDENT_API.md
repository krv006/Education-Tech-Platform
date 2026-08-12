# O'quvchi uchun API endpointlari

Frontend hali qurilmagan qism — o'quvchi (student) roli uchun mavjud barcha backend endpointlar ro'yxati. Frontend dasturchi shu hujjat asosida UI qura oladi.

**Base URL**: `/api/v1/`
**Auth**: JWT (`Authorization: Bearer <access_token>`)

Deyarli barcha "list" endpointlar serverda avtomatik login qilgan o'quvchiga moslashtirilgan (scoped) — frontendda qo'shimcha `student_id` filtri kerak emas, backend o'zi "mening kurslarim", "mening darslarim" kabi natija qaytaradi.

---

## 1. Autentifikatsiya (`/api/v1/auth/`)

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| POST | `/login/` | `username`, `password`, `force`(ixtiyoriy, `"true"`) | `refresh`, `access` **yoki** 409 `{code:"device_conflict", device_label}` | Login. **Bitta akkaunt = bitta faol qurilma**: boshqa qurilmada faol sessiya bo'lsa 409 qaytadi (`device_label` bilan); `force:"true"` yuborilsa eski qurilma darhol chiqarib yuboriladi |
| POST | `/token/refresh/` | `refresh` | `access` | Access tokenni yangilash |
| GET | `/me/` | — | `id, username, first_name, last_name, role, phone, invite_code, avatar` | O'z profili |
| PUT/PATCH | `/me/` | `username, first_name, last_name, phone, avatar`(multipart, rasm fayl) | yuqoridagidek | Profilni tahrirlash (profil rasmini shu orqali o'rnatadi) |
| GET | `/sessions/` | — | `{device_label, ip_address, last_seen_at, created_at}` yoki `null` | Hozir qaysi qurilmada faol ekanligim |
| GET | `/logins/` | — | ro'yxat: `{at, ip, user_agent, new_ip, new_device}` | O'z login tarixim (qurilma/IP o'zgargan hollari belgilangan) |
| GET | `/links/` | — | ro'yxat: `id, parent, student, status(pending/approved/declined), created_at, responded_at` | Ota-onadan kelgan bog'lanish so'rovlari |
| POST | `/links/{id}/respond/` | `action`: `"approve"` \| `"decline"` | link obyekti | Ota-ona so'rovini tasdiqlash/rad etish |

---

## 2. Kurslar va yozilish (`/api/v1/courses/`)

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| GET | `/courses/` | — (`?search=`) | ro'yxat: `id, teacher, title, subject, description, is_active, student_count, my_status, created_at` | Yozilgan kurslarim |
| GET | `/courses/{id}/` | — | yuqoridagi CourseSerializer | Kurs tafsiloti |
| GET | `/courses/catalog/` | — | CourseSerializer ro'yxati | Barcha ochiq kurslar (yozilish uchun) |
| POST | `/courses/{id}/enroll/` | — | `id, course, course_title, student, status, created_at` | Kursga yozilish so'rovi (`pending` holatda, o'qituvchi tasdiqlashi kerak) |
| POST | `/courses/{id}/unenroll/` | — | `{"removed": bool}` | Kursdan chiqish |

---

## 3. Darslar va reyting (`/api/v1/lessons/`)

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| GET | `/lessons/` | `?course=`, `?status=`, `?ordering=starts_at` | ro'yxat: `id, course, course_title, title, starts_at, duration_min, status, room_name, created_at, avg_rating, rating_count` | Mening darslarim |
| GET | `/lessons/{id}/` | — | yuqoridagidek | Dars tafsiloti |
| POST | `/lessons/{id}/rate/` | `stars`(1-5), `description`(ixtiyoriy) | `id, lesson, student, stars, description, created_at` | Tugagan darsga baho berish (dars `finished` bo'lishi shart) |
| GET | `/lessons/{id}/ratings/` | — | LessonRating ro'yxati | Darsga qoldirilgan barcha baholar |

---

## 4. Davomat (`/api/v1/attendance/`) — faqat o'qish

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| GET | `/attendance/` | `?lesson=`, `?student=` | ro'yxat: `id, lesson, lesson_title, student, joined_at, left_at, minutes, attention_total, attention_answered, focus_exits, focus_alert` | Mening davomatim |
| GET | `/attendance/{id}/` | — | yuqoridagidek | Bitta yozuv tafsiloti |

---

## 5. Live / video dars (`/api/v1/live/`)

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| POST | `/live/token/` | `lesson_id` | `{token, url, room, is_teacher}` | LiveKit video xonaga kirish tokeni (davomatni avtomatik belgilaydi) |
| POST | `/live/leave/` | `lesson_id` | `{"updated": bool}` | Darsdan chiqish (davomat yopiladi) |
| GET | `/live/attention/` | `?lesson_id=` | `{"check": null}` yoki `{"check": {id, due_at}}` | "Sen hali shu yerdamisan?" so'rovi bormi, tekshirish (polling) |
| POST | `/live/attention/` | `check_id` | `{"answered_at"}` | Attention check'ga javob berish |
| POST | `/live/focus/` | `lesson_id`, `kind`: `"exit"` \| `"return"` | `{"ok", "kind", "exit_count", "threshold", "parent_notified"}` | Anti-cheat: darsdan chiqib/qaytganini belgilash |

---

## 6. Chat (`/api/v1/chat/`)

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| GET | `/chat/rooms/` | — | ro'yxat: `id, kind(course/direct), course, direct_status, image, title, last_message{text, sender, created_at, file_url}, unread, other_user, live_lesson{id,title,room_name}\|null, updated_at` | Mening chat xonalarim (guruh + shaxsiy). `live_lesson` bo'lsa — kurs guruhida hozir jonli dars ketyapti (Telegram uslubi "qo'shilish" chizig'i) |
| GET | `/chat/rooms/{id}/` | — | yuqoridagidek | Xona tafsiloti |
| GET | `/chat/rooms/{id}/messages/` | `?after=<ISO datetime>` | xabarlar ro'yxati: `id, room, sender, text, file_url, created_at` | Xabarlar tarixi / polling |
| POST | `/chat/rooms/{id}/send/` | `text` (max 4000 belgi) | xabar obyekti | Xabar yuborish |
| POST | `/chat/rooms/direct/request/` | `teacher` (id yoki username) | ChatRoom obyekti | O'qituvchi bilan shaxsiy chat so'rovi |
| GET | `/chat/rooms/teachers/` | — | ro'yxat: `{...user, direct_status, room_id}` | Mening o'qituvchilarim ro'yxati (shaxsiy chat boshlash uchun) |
| GET | `/chat/files/{message_id}/` | — | fayl (PDF va h.k.) | Chatga biriktirilgan faylni ko'rish (masalan, doska PDF) |

**WebSocket**: `wss://<domain>/ws/chat/<room_id>/?token=<JWT access>` — polling o'rniga real-vaqt:
- Kelib turadi: `{type:"message", message:{...}}`, `{type:"typing", user_id, name}`, `{type:"lesson_live", lesson:{id,title,room_name}}`, `{type:"lesson_ended", lesson_id}`
- Yuboriladi: `{type:"message", text}`, `{type:"typing"}`

---

## 7. Doska / Whiteboard (`/api/v1/board/{lesson_id}/`)

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| GET | `/board/{lesson_id}/` | — | `{sheets:[{index, strokes}], can_draw, is_teacher, size, subject}` | Doska holatini olish (polling) |
| POST | `/board/{lesson_id}/stroke/` | `sheet`(int), `stroke` (chizish yoki matn obyekti) | saqlangan stroke obyekti | Doskaga chizish/matn qo'shish (o'qituvchi ruxsat bergan bo'lishi kerak) |
| POST | `/board/{lesson_id}/erase/` | `sheet`, `stroke_ids`, `reason` (majburiy) | `{"removed": count}` | Chizilganlarni o'chirish |
| POST | `/board/{lesson_id}/solve/` | `expr` (matematik ifoda) | yechim natijasi | Formula yechish (Photomath uslubida) |
| GET | `/board/{lesson_id}/pdf/` | — | PDF fayl | Doskani PDF sifatida yuklab olish |

**WebSocket**: `wss://<domain>/ws/board/<lesson_id>/?token=<JWT access>` — polling o'rniga real-vaqt chizish:
- Kelib turadi: `{type:"stroke", sheet, stroke}`, `{type:"erase", sheet, stroke_ids, by, reason}`, `{type:"sheet", index}`
- Yuboriladi: `{type:"stroke", sheet, stroke}`

---

## 8. Uyga vazifa (`/api/v1/homework/`)

| Method | Path | Body | Javob | Tavsif |
|---|---|---|---|---|
| GET | `/homework/assignments/?course=<id>` | — | ro'yxat: `id, course_id, course_title, subject, title, description, body, attachment_name, has_attachment, due_at, skill_key, created_at, my_submission{...}` | Kurs bo'yicha vazifalar + mening topshirganim holati |
| GET | `/homework/assignments/{id}/` | — | vazifa + `submissions`(mening topshirganlarim) | Vazifa tafsiloti |
| GET | `/homework/assignments/{id}/file/` | — | fayl | Vazifaga biriktirilgan faylni yuklab olish |
| POST | `/homework/assignments/{id}/submit/` | multipart: `file` (PDF/rasm/DOCX, yoki `speaking` uchun audio) | `status="checking"` bilan submission obyekti | Vazifani topshirish (AI tekshiruvi fonda ishga tushadi) |
| GET | `/homework/submissions/{id}/` | — | `result{overall_score, grade, questions, summary}`, `error, is_late, checked_at` | AI natijasini kuzatish (polling) |
| GET | `/homework/submissions/{id}/file/` | — | fayl | O'zim topshirgan faylni yuklab olish |

---

## O'quvchiga yopiq endpointlar (frontendda ko'rsatilmasin)

- Auth: `/register/`, `/children/`, `/links/request/`, `/consents/` — faqat ota-ona/o'qituvchi
- Kurs/dars: yaratish, tahrirlash, o'chirish; `/courses/requests/`, `/courses/{id}/schedule/`, `/courses/{id}/search-students/`, `/courses/{id}/students/`, `/lessons/{id}/finish/` — faqat o'qituvchi/admin
- Live: `/live/allow-share/` — faqat o'qituvchi
- Chat: `/chat/rooms/direct/respond/` — faqat o'qituvchi
- Doska: `/board/{id}/sheet/`, `/board/{id}/grant/` — faqat o'qituvchi
- Homework: vazifa yaratish/o'chirish, `/submissions/{id}/recheck/` — faqat o'qituvchi

---

## Frontend uchun eslatmalar

- Yozilish va chat so'rovlari **async** (`pending` → o'qituvchi tasdiqlaydi/rad etadi) — UI `status` / `my_status` / `direct_status` maydonlariga qarab holatni ko'rsatishi kerak, darhol kirish huquqi berilgan deb hisoblamasin.
- Doska, live-token va chat barchasi `lesson_id` / `room_id` orqali ishlaydi — ketma-ketlik: darslar ro'yxatini olish → live token olish → shu darsning kursi chatini/doskasini ochish.

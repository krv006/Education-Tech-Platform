# Yangi backend funksiyalar (2026-09-03) — frontend uchun

Bu hujjat shu sessiyada qo'shilgan **hamma yangi/o'zgargan endpoint**larni
qamrab oladi: o'qituvchi reytingi, o'quvchi ro'yxatdan o'tishi, o'qituvchi
tasdiqlash oqimi, Test (Quiz), sertifikat yuklash, va bitta chat bug-fix.

**Base URL**: `/api/v1/`
**Auth**: hammasida JWT (`Authorization: Bearer <access_token>`), alohida
belgilanmagan bo'lsa.

---

## 1. O'qituvchi reytingi

Hech qanday yangi endpoint yo'q — mavjud foydalanuvchi ma'lumotiga (`UserSerializer`
qaytaradigan har qanday joyga: `/auth/me/`, qidiruv, o'qituvchilar ro'yxati) ikkita
yangi maydon qo'shildi:

```json
{
  "id": "uuid", "username": "...", "role": "teacher",
  "avg_rating": 4.75,
  "rating_count": 12
}
```

- Faqat `role: "teacher"` bo'lganda hisoblanadi — boshqa rollarda ikkalasi ham `null`.
- `avg_rating` — o'qituvchining **BARCHA** darslari bo'yicha o'rtacha ball (1-5), 2 xona aniqlikda. Hech kim baholamagan bo'lsa `null`.
- `rating_count` — jami baholar soni.

### Yangi endpoint — admin uchun o'qituvchilar ro'yxati

| Method | Path | Ruxsat | Tavsif |
|---|---|---|---|
| GET | `/auth/teachers/` | admin/super_admin | Barcha o'qituvchilar, `avg_rating`/`rating_count` bilan |

---

## 2. O'quvchi ro'yxatdan o'tishi

`POST /auth/register/` — endi `role` maydonida `"student"` ham qabul qilinadi
(avval faqat `"teacher"`/`"parent"`).

```json
{ "username": "...", "password": "...", "role": "student", "first_name": "..." }
```

O'quvchi o'zi ro'yxatdan o'tsa ham, javobda `invite_code` keladi — ota-ona
keyinroq shu kod bilan bog'lanishi mumkin (mavjud oqim, o'zgarmagan).

---

## 3. O'qituvchi tasdiqlash oqimi (faollashtirish)

**O'qituvchi ro'yxatdan o'tgach KIRA OLADI**, lekin admin tasdiqlamaguncha
kurs/dars yaratish kabi amallarga ruxsati yo'q — bunday urinish `403` qaytaradi.

`POST /auth/register/` va `/auth/me/` javobida yangi maydon:

```json
{ "id": "uuid", "username": "...", "role": "teacher", "is_approved": false }
```

### Yangi endpointlar (admin uchun)

| Method | Path | Tavsif |
|---|---|---|
| GET | `/auth/teachers/pending/` | Hali tasdiqlanmagan (`is_approved=false`) o'qituvchilar |
| POST | `/auth/teachers/{id}/approve/` | Tasdiqlaydi — shundan keyin `is_approved: true`, hammasi ochiladi |

**Frontend uchun muhim**: agar o'qituvchi kirgach kurs/dars yaratishda `403`
olsa, sabab shu bo'lishi mumkin — UI'da "hisobingiz admin tasdig'ini kutmoqda"
degan xabar ko'rsatish kerak (`/auth/me/`dan `is_approved` bilan tekshirib).

---

## 4. Chat: real-time bug-fix (yangi endpoint yo'q)

Dars tugagach avtomatik yuboriladigan ikkita chat xabari — **video-yozuv
havolasi** va **doska PDF** — avval faqat bazaga yozilib, WebSocket orqali
DARHOL yuborilmasdi (chatni qayta ochmaguncha ko'rinmasdi). Endi tuzatildi —
oddiy xabarlar bilan bir xil real-time push.

**Frontend'da hech narsa o'zgartirish shart emas** — agar WebSocket handler
allaqachon oddiy `chat.message` eventini to'g'ri ishlatayotgan bo'lsa, bu
ikkita xabar turi ham endi xuddi shunday avtomatik keladi.

---

## 5. Test (Quiz) — YANGI to'liq feature

**Base**: `/api/v1/quizzes/`

Xususiyatlari: faqat variantli savollar (MCQ), **vaqt chegarasi yo'q**,
o'quvchi **cheklanmagan marta qayta topshirishi** mumkin, baholash **darhol
va avtomatik** (AI kerak emas).

### 5.1. Test yaratish — o'qituvchi

`POST /quizzes/` (ruxsat: teacher, faqat `is_approved: true` bo'lsa)

**So'rov**:
```json
{
  "course": "<course-uuid>",
  "lesson": "<lesson-uuid yoki null>",
  "title": "1-bob testi",
  "description": "Ixtiyoriy",
  "due_at": "2026-09-20T18:00:00Z",
  "opens_at": "2026-09-10T00:00:00Z",
  "questions": [
    {
      "text": "2 + 2 = ?",
      "points": 1,
      "options": [
        { "text": "3", "is_correct": false },
        { "text": "4", "is_correct": true },
        { "text": "5", "is_correct": false }
      ]
    }
  ]
}
```

- `lesson`, `description`, `due_at`, `opens_at` — hammasi **ixtiyoriy** (`null` yoki tushirib qoldirish mumkin).
- Har bir savolda **kamida 2 ta variant** va **aynan 1 ta** `is_correct: true` bo'lishi shart — aks holda `400`.
- `opens_at` — belgilansa, o'quvchi/ota-ona shu vaqtgacha testni **umuman ko'rmaydi** (`404`). O'qituvchi/admin har doim ko'radi.
- **Bildirishnoma**: agar test darhol ochiq bo'lsa (`opens_at` yo'q yoki o'tgan), kursga yozilgan barcha o'quvchilarga real-time bildirishnoma boradi (mavjud notifications infratuzilmasi, `link_type: "quiz"`, `link_id: "<quiz-id>"`). Agar `opens_at` kelajakda bo'lsa — bildirishnoma hozircha YUBORILMAYDI.

**Javob** (`201`) — to'liq struktura, `id`lar bilan (savol/variant `id`lari keyin javob yuborishda kerak bo'ladi):
```json
{
  "id": "quiz-uuid", "course": "...", "lesson": null, "title": "1-bob testi",
  "description": "...", "due_at": "...", "opens_at": null, "created_at": "...",
  "questions": [
    {
      "id": "q1-uuid", "text": "2 + 2 = ?", "points": 1, "order": 0,
      "options": [
        { "id": "o1-uuid", "text": "3", "is_correct": false, "order": 0 },
        { "id": "o2-uuid", "text": "4", "is_correct": true, "order": 1 },
        { "id": "o3-uuid", "text": "5", "is_correct": false, "order": 2 }
      ]
    }
  ]
}
```

### 5.2. Testlar ro'yxati

`GET /quizzes/` — rolga qarab avtomatik filtrlanadi (o'qituvchi: o'z kurslari;
o'quvchi: yozilgan kurslari, `opens_at` o'tganlar; ota-ona: bog'langan
bolasining kurslari).

```json
[
  { "id": "...", "course": "...", "lesson": null, "title": "...", "description": "...",
    "due_at": null, "opens_at": null, "question_count": 5, "created_at": "..." }
]
```

### 5.3. Testni ochish

`GET /quizzes/{id}/`

- **O'qituvchi/admin** — `is_correct` bilan (javob kaliti ko'rinadi).
- **O'quvchi/ota-ona** — `is_correct` **YO'Q** (yechish uchun, javob yashiringan).
- Boshqa kursning/yozilmagan kursning testi — `404` (mavjudligi ham bilinmaydi).

### 5.4. Testni o'chirish

`DELETE /quizzes/{id}/` — faqat egasi o'qituvchi. Boshqasiniki bo'lsa `404`.

### 5.5. Topshirish — o'quvchi

`POST /quizzes/{id}/attempts/`

**So'rov**:
```json
{
  "answers": [
    { "question": "q1-uuid", "selected_option": "o2-uuid" }
  ]
}
```

Har bir savolga faqat bitta javob; javobsiz qoldirilgan savol ham
maksimal ballga qo'shiladi (adolatli hisob).

**Javob** (`201`) — natija DARHOL, har bir savol bo'yicha to'g'ri javob ochiladi:
```json
{
  "id": "attempt-uuid", "quiz": "...", "student": "...",
  "score": 4, "max_score": 5, "created_at": "...",
  "answers": [
    {
      "question": "q1-uuid", "question_text": "2 + 2 = ?",
      "selected_option": "o2-uuid", "selected_option_text": "4",
      "is_correct": true,
      "correct_option": { "id": "o2-uuid", "text": "4" }
    }
  ]
}
```

`correct_option` — HAR DOIM keladi (to'g'ri javob bo'lsa ham, xato bo'lsa
ham) — o'quvchi xato qilgan bo'lsa, to'g'ri javobni shu yerdan ko'rib,
qayta urinishda tuzatishi mumkin.

### 5.6. Urinishlar tarixi

`GET /quizzes/{id}/attempts/` — o'quvchi faqat o'zinikini, o'qituvchi/admin/
ota-ona barchasini (ota-ona faqat o'z bolasinikini) ko'radi.

```json
[
  { "id": "...", "quiz": "...", "student": "...", "student_name": "s1",
    "score": 4, "max_score": 5, "created_at": "..." }
]
```

Cheklanmagan qayta urinish — har safar yangi qator qo'shiladi, eskisi o'chmaydi.

---

## 6. O'qituvchi sertifikatlari — YANGI

`/auth/me/certificates/` — faqat o'qituvchi (`certificate.manage` ruxsati),
faqat **o'zinikiga**.

### Yuklash

`POST /auth/me/certificates/` — `multipart/form-data`

| Maydon | Majburiymi | Izoh |
|---|---|---|
| `file` | ha | Rasm yoki PDF |
| `title` | yo'q | Masalan "IELTS 8.0" |

Javob (`201`):
```json
{ "id": "cert-uuid", "file": "https://.../media/certificates/2026/09/....png", "title": "IELTS 8.0", "created_at": "..." }
```

### O'chirish

`DELETE /auth/me/certificates/{id}/` — faqat o'zi yuklaganini. Begonaniki — `404`.

### Ko'rish

Alohida GET endpoint shart emas — sertifikatlar `UserSerializer` qaytaradigan
HAR QANDAY joyda (`/auth/me/`, o'qituvchilar ro'yxati va h.k.) `certificates`
massivi sifatida avtomatik keladi:

```json
{ "id": "...", "role": "teacher", "certificates": [
  { "id": "cert-uuid", "file": "https://.../....png", "title": "IELTS 8.0", "created_at": "..." }
] }
```

Boshqa rollarda `certificates: []` (bo'sh massiv).

---

## Muhim eslatmalar

- Barcha yangi endpointlar mavjud RBAC (`RequirePerm`) orqali himoyalangan — noto'g'ri rol/kirish `403`, ko'rishga haqli bo'lmagan obyekt (masalan begona kurs testi) `404` (mavjudligi ham bilinmaydi).
- Migratsiyalar production'da `docker compose ... up -d --build` bilan avtomatik ishga tushadi (`DEPLOY.md`ga qarang) — qo'lda `migrate` kerak emas.

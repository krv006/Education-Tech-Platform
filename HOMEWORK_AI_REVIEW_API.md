# Uy vazifasi: AI baholaydi, o'qituvchi tasdiqlaydi + vaqt kuzatuvi

Bu hujjat `STUDENT_API.md` va `STAFF_API.md`ni **to'ldiradi** — faqat shu yangi ish oqimi bo'yicha o'zgargan/qo'shilgan narsalar shu yerda. Asosiy `/homework/` endpointlari (`assignments/`, `submit/`, va h.k.) uchun o'sha ikkala hujjatga qarang.

**Base URL**: `/api/v1/homework/`
**Auth**: JWT (`Authorization: Bearer <access_token>`)

## Nima o'zgardi

Ilgari AI tekshirgach `Submission.status` darhol `done` bo'lib, ball/baho hammaga (o'quvchi, ota-ona, o'qituvchi) bir xil ko'rinardi. Endi:

1. AI tekshirgach status `pending_review` bo'ladi — bu AI'ning **taklifi**, hali yakuniy emas.
2. **Faqat o'qituvchi** shu bosqichda natijani ko'radi (ball, baho, feedback). O'quvchi/ota-onaga status `"pending_review"` ko'rinadi, lekin `overall_score`/`grade`/`result` — `null`.
3. O'qituvchi natijani ko'rib chiqadi — xohlasa ball/baho/feedbackni **tahrirlab**, `POST /review/` bilan tasdiqlaydi. Shundan keyingina status `done` bo'ladi va o'quvchi/ota-ona natijani ko'radi.
4. Tasdiqlash **AI natijasining ustidan yoziladi** — bitta yakuniy `result`/`overall_score`/`grade` bor. AI'ning asl (o'zgarmas) natijasi fon/audit sifatida `ai_result`/`ai_overall_score`/`ai_grade`da saqlanadi — faqat o'qituvchiga ko'rinadi.
5. O'quvchining vazifa sahifasida qancha vaqt bo'lgani va undan qancha vaqt chiqib ketgani endi kuzatiladi (`AssignmentFocusEvent`, darsdagi diqqat kuzatuvi bilan bir xil naqsh).

## `Submission.status` qiymatlari

| Qiymat | Ma'no |
|---|---|
| `checking` | AI hali tekshiryapti |
| `pending_review` | AI tekshirdi, o'qituvchi tasdiqlashini kutmoqda — **o'quvchiga natija ko'rinmaydi** |
| `done` | O'qituvchi tasdiqladi — natija yakuniy, hammaga ko'rinadi |
| `error` | AI xatolik berdi (`error` maydonida sabab) |

## Submission javob shakli (`GET /submissions/{id}/`, va h.k.)

O'quvchi/ota-ona uchun (`is_teacher=false`):

```json
{
  "id": "...", "assignment_id": "...", "student_id": "...", "student_name": "...",
  "file_name": "...", "status": "pending_review",
  "overall_score": null, "grade": "",
  "result": null,
  "error": "", "is_late": false, "created_at": "...", "checked_at": "..."
}
```
`status == "done"` bo'lganda `overall_score`/`grade`/`result` to'liq qiymat bilan qaytadi.

O'qituvchi uchun (`is_teacher=true`) — yuqoridagilarga qo'shimcha:

```json
{
  "...": "...",
  "overall_score": 78, "grade": "Yaxshi", "result": { "...": "AI/yakuniy natija" },
  "reviewed_at": null, "reviewed_by": null,
  "ai_overall_score": 78, "ai_grade": "Yaxshi", "ai_result": { "...": "AI'ning asl natijasi" },
  "focus": {
    "exits": 2, "away_seconds": 340, "longest_seconds": 210,
    "on_page_seconds": 610, "total_seconds": 950,
    "timeline": [
      { "left_at": "...", "returned_at": "...", "seconds": 210 },
      { "left_at": "...", "returned_at": null, "seconds": 130 }
    ]
  }
}
```
Muhim: `overall_score`ni o'qituvchi **PENDING_REVIEW bosqichida ham darhol ko'radi** (AI'ning taklifi) — u faqat o'quvchi/ota-onadan yashiriladi. `ai_result`/`focus` faqat submission tafsilotlari (`GET /submissions/{id}/`, `recheck`, `review`) javobida bo'ladi, ro'yxat ko'rinishida (`assignments/{id}/`dagi `submissions[]`) yo'q.

`GET /homework/assignments/{id}/` javobidagi `stats.avg_score` — o'qituvchining o'z statistikasi, AI taklif qilgan ballarni ham darhol hisobga oladi (tasdiqlanmagan bo'lsa ham).

---

## Yangi endpointlar

| Method | Path | Rol | Body | Javob | Tavsif |
|---|---|---|---|---|---|
| POST | `/homework/submissions/{id}/review/` | teacher (o'ziniki, `homework.assign`) | JSON, hammasi ixtiyoriy: `overall_score` (raqam), `grade` (matn), `result` (to'liq JSON obyekt — feedbackni tahrirlash uchun) | `_submission_dict` (`is_teacher=true` shakli) | Faqat `status == "pending_review"` bo'lgan topshiriqni tasdiqlaydi. Berilgan maydonlar AI taklifining ustidan yoziladi, berilmagani (masalan `grade` bo'sh qoldirilsa) o'zgarmaydi. `status` → `done`, `reviewed_by`/`reviewed_at` to'ldiriladi. `pending_review` bo'lmagan topshiriqqa qayta chaqirilsa — 400. |
| POST | `/homework/assignments/{id}/focus/` | student (o'ziniki, ro'yxatdan o'tgan kursga, `homework.submit`) | JSON: `kind` = `"exit"` \| `"return"` | `{"ok": true}` | Frontend vazifa bajarish sahifasidan chiqqanda `exit`, qaytganda `return` yuboradi (browser `visibilitychange`/`blur`/`focus` bilan). Noto'g'ri `kind` — 400; kursga yozilmagan bo'lsa — 403. |

### Review misoli — o'zgartirmasdan tasdiqlash
```
POST /api/v1/homework/submissions/{id}/review/
{}
```
→ AI'ning ball/baho/feedbacki o'zgarishsiz tasdiqlanadi.

### Review misoli — ballni va feedbackni tahrirlab tasdiqlash
```
POST /api/v1/homework/submissions/{id}/review/
{
  "overall_score": 90,
  "grade": "A'lo",
  "result": { "...": "o'qituvchi tahrirlagan to'liq natija JSON'i" }
}
```

## Focus (vaqt kuzatuvi) hisob-kitobi

`focus_summary` — darslardagi diqqat kuzatuvi bilan bir xil chiqish/qaytish juftlash algoritmi, faqat vazifa sahifasida darsning "tugash" chegarasi yo'qligi sababli **yopilmagan chiqish `hozir`gacha hisoblanadi** (darsda esa ochiq qoladi):

- `exits` — nechta marta sahifadan chiqqan
- `away_seconds` — jami tashqarida o'tgan vaqt
- `longest_seconds` — eng uzun bitta chiqish
- `on_page_seconds` — sahifada o'tgan taxminiy vaqt (`total_seconds - away_seconds`)
- `total_seconds` — birinchi va oxirgi hodisa orasidagi umumiy oraliq
- `timeline` — har bir chiqish/qaytish jufti (`left_at`, `returned_at` — ochiq bo'lsa `null`, `seconds`)

Bu ma'lumot faqat o'qituvchiga (`GET /submissions/{id}/` javobida `focus` maydoni orqali) ko'rinadi.

## Migratsiya

`apps/homework/migrations/0004_submission_ai_grade_submission_ai_overall_score_and_more.py` — `Submission`ga `ai_result`/`ai_overall_score`/`ai_grade`/`reviewed_by`/`reviewed_at` maydonlari va yangi `AssignmentFocusEvent` modelini qo'shadi.

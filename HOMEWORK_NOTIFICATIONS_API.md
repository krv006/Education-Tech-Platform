# Uy vazifasi bildirishnomalari — frontend uchun

Bu — **yangi endpoint emas**. Yangi vazifa berilganda va deadline
yaqinlashganda (yarim vaqt / 1 soat qoldi) yuboriladigan bildirishnomalar
**mavjud** `notifications` infratuzilmasi orqali keladi — shu hujjat o'sha
mavjud endpointlarni va yangi xabar matnlarini tasvirlaydi.

**Base URL**: `/api/v1/notifications/`
**Auth**: JWT (`Authorization: Bearer <access_token>`)

## Endpointlar (mavjud, hozirgacha alohida hujjatlanmagan)

| Method | Path | Tavsif |
|---|---|---|
| GET | `/notifications/` | Mening inbox'im — sahifalangan, eng yangisi tepada |
| GET | `/notifications/unread-count/` | `{"count": N}` — o'qilmagan xabarlar soni (badge uchun) |
| POST | `/notifications/{id}/read/` | O'qildi deb belgilash |

**WebSocket (real-time push)**: `wss://<domain>/ws/notifications/?token=<JWT access>`
```json
{ "type": "notification", "notification": { "id", "sender", "description", "target_type": "user", "created_at" } }
```
Yopilish kodi: `4401` — token yaroqsiz.

## Inbox javob shakli (`GET /notifications/`)

```json
{
  "results": [
    {
      "id": "uuid",
      "notification": {
        "id": "uuid",
        "sender": { "id", "username", "first_name", ... },
        "description": "«Algebra — 7-sinf»: yangi uy vazifasi — «Kvadrat tenglamalar».",
        "target_type": "user",
        "created_at": "2026-08-24T10:00:00Z"
      },
      "is_read": false,
      "read_at": null,
      "created_at": "2026-08-24T10:00:00Z"
    }
  ]
}
```

## Yangi qo'shilgan uy-vazifa xabarlari — matn andozalari

Bular **maxsus "type" maydoniga ega emas** — oddiy `Notification` sifatida
keladi (`sender` = kursning o'qituvchisi), faqat `description` matni orqali
farqlanadi. Agar UI'da alohida ikonka/rang ko'rsatmoqchi bo'lsangiz, matnni
shu qoliplar bilan solishtiring:

| Voqea | Kimga | `description` qolipi |
|---|---|---|
| O'qituvchi yangi vazifa berdi | Kursga yozilgan **hamma** o'quvchi, darhol | `«<kurs nomi>»: yangi uy vazifasi — «<vazifa nomi>».` |
| Deadline'ning **yarmi** o'tdi | Hali **topshirmagan** o'quvchilar | `«<kurs nomi>»: «<vazifa nomi>» topshirish muddatining yarmi o'tdi.` |
| Deadline'ga **1 soat** qoldi | Hali **topshirmagan** o'quvchilar | `«<kurs nomi>»: «<vazifa nomi>» topshirish muddatiga 1 soat qoldi!` |

## Muhim xatti-harakatlar

- Deadline eslatmalari **faqat hali `Submission` topshirmagan** o'quvchilarga boradi — allaqachon topshirgan o'quvchi bu ikkala eslatmani olmaydi.
- Har ikkala eslatma (yarim vaqt, 1 soat) **faqat bir marta** yuboriladi — takror kelmaydi.
- Agar `due_at` belgilanmagan bo'lsa (vazifada muddat yo'q) — deadline eslatmalari umuman yuborilmaydi, faqat "yangi vazifa" xabari keladi.
- Eslatmalar server tomonda **davriy tekshiruv** orqali yuboriladi (real vaqtli emas — cron orqali har 5-15 daqiqada tekshiriladi), shuning uchun deadline vaqtidan bir necha daqiqa kechikish normal.

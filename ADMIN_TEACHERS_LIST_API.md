# Admin panel — o'qituvchilar ro'yxati (reyting bilan)

Admin panelga (`admin-dashboard-page.tsx`) yangi bo'lim qo'shish kerak:
**"O'qituvchilar"** — har biri ism + o'rtacha reyting + baholar soni bilan.

## Endpoint

```
GET /api/v1/auth/teachers/
Authorization: Bearer <admin access token>
```

Faqat `admin` yoki `super_admin` roli kira oladi.

## Javob

```json
[
  {
    "id": "uuid",
    "username": "ustoz1",
    "first_name": "Aziz",
    "last_name": "Karimov",
    "avatar": "https://.../media/avatars/....png",
    "avg_rating": 4.75,
    "rating_count": 12,
    "is_approved": true,
    "certificates": [
      { "id": "uuid", "file": "https://.../....pdf", "title": "IELTS 8.0", "created_at": "..." }
    ]
  }
]
```

- `avg_rating` — o'qituvchining barcha darslari bo'yicha o'rtacha ball (1-5). Hech kim baholamagan bo'lsa `null`.
- `rating_count` — jami baholar soni.
- `is_approved` — `false` bo'lsa, bu o'qituvchi hali admin tasdig'ini kutmoqda (pastga qarang).
- `certificates` — o'qituvchi yuklagan malaka sertifikatlari (bo'lsa).

## Bonus: tasdiq kutayotgan o'qituvchilar

Agar admin panelida "yangi ro'yxatdan o'tgan o'qituvchilar" bo'limi ham kerak bo'lsa:

```
GET /api/v1/auth/teachers/pending/     # is_approved=false bo'lganlar
POST /api/v1/auth/teachers/{id}/approve/   # tasdiqlash
```

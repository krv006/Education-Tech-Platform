# Fokus — EdTech Platformasi (MVP v0)

Onlayn ta'lim platformasi: jonli video darslar (LiveKit), avtomatik davomat va
rozilikka asoslangan ota-ona paneli. O'zbekiston bozori uchun.

> **Loyihaning to'liq umumiy hujjati: [PROJECT.md](PROJECT.md)** — modullar, API/WS
> shartnomasi, deploy, talablar holati.
> Arxitektura qoidalari: [ARCHITECTURE.md](ARCHITECTURE.md) — yangi kod yozishdan oldin o'qing.

## Stack

- **Backend:** Django + DRF + SimpleJWT (`root/` — settings, `apps/` — modullar)
- **Video:** LiveKit (self-hosted, docker-compose)
- **DB:** PostgreSQL (dev'da sqlite fallback)
- **Frontend:** ALOHIDA loyihada (boshqa jamoa) — bu repo faqat API beradi.
  Frontend domenini `.env` dagi `CORS_ALLOWED_ORIGINS` ga qo'shish kerak.
  API hujjatlari: `/api/docs/` (Swagger), sxema: `/api/schema/`

## Modullar

| Modul | Vazifasi |
|---|---|
| `apps/accounts` | Auth (JWT), 4 rol, ota-ona↔bola bog'lash (taklif-kod + tasdiq), rozilik (consent) |
| `apps/lessons` | Kurs, dars jadvali, yozilish, davomat hisoboti |
| `apps/live` | LiveKit xona tokeni + avtomatik davomat, diqqat tekshiruvi, fokus jurnali |
| `apps/chat` | Telegram uslubidagi chat: kurs guruhlari + o'qituvchi↔o'quvchi direct (so'rov/block) |
| `apps/board` | Jonli dars doskasi: chizish, matn/formula, o'chirish sababi, PDF → chat |
| `apps/homework` | AI uy vazifasi (Gemini): vazifa berish, fayl topshirish, savolma-savol o'zbekcha baholash |
| `apps/core` | UUID/timestamp baza modellari, RBAC (`permissions.py`), audit log |

## Frontend integratsiyasi (alohida loyiha uchun shartnoma)

- **Auth:** `POST /api/v1/auth/login/` → `{access, refresh}`; har so'rovda `Authorization: Bearer <access>`
- **Chat real-time (WebSocket):** `wss://<domain>/ws/chat/<room_id>/?token=<access>`
  - Yopilish kodlari: `4401` token yaroqsiz, `4403` xonaga a'zo emas
  - Yuborish: `{"type":"message","text":"..."}` (yoki avvalgidek REST `POST .../send/` — ikkalasi ham broadcast bo'ladi)
  - "Yozmoqda...": `{"type":"typing"}` yuboriladi → boshqalarga `{"type":"typing","user_id","name"}` keladi (o'zingizni filtrlab tashlang)
  - Kelgan xabar: `{"type":"message","message":{id,room,sender,text,created_at}}`
  - Tarix/o'qilgan belgisi avvalgidek REST orqali (`GET .../messages/`, `POST .../read/`)
- **Hujjatlar:** `/api/docs/` (Swagger UI), `/api/schema/` (OpenAPI — client generatsiya qilsa bo'ladi)
- **LiveKit:** token `POST /api/v1/live/token/` (`{lesson_id}`), ulanish `wss://<domain>/livekit`
- **Doska PDF havolasi:** dars tugaganda backend kurs chatiga `"... /boards/<lesson_id>"`
  matnli xabar yuboradi — frontend shu yo'l uchun sahifa qilishi kerak
  (doska ma'lumoti: `GET /api/v1/board/<lesson_id>/`, PDF: `.../pdf/`)
- **Fayllar:** uy vazifasi fayllari auth talab qiladi — `GET /api/v1/homework/submissions/<id>/file/`
  va `.../assignments/<id>/file/` (to'g'ridan-to'g'ri `/media/` URL ishlatilmaydi)
- **CORS:** frontend domenini `.env` → `CORS_ALLOWED_ORIGINS` ga qo'shish shart

## Ishga tushirish

```bash
# 1. Muhit
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env

# 2. Infratuzilma (ixtiyoriy — sqlite bilan ham ishlaydi)
docker compose up -d          # Postgres + Redis + LiveKit

# 3. Migratsiya va server
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

API hujjatlari: http://localhost:8000/api/docs/

## Smoke test

To'liq oqim (ro'yxat → bola → taklif-kod → dars → LiveKit token → davomat):

```bash
python scripts/smoke_test.py
```

## Muhim qarorlar

- **Rozilik-modeli:** ota-ona bolani faqat bolaning taklif-kodi va tasdig'i bilan
  kuzatadi; bola istalgan payt uzadi (prototipdagi Tahlil oqimi).
- **Self-hosted LiveKit:** birlik iqtisodi + data localization talabi
  (Tanqidiy Tahlil v4, 5- va 7-bo'limlar).
- **Migratsiyalar git'da yo'q:** har muhitda `makemigrations` qilinadi.

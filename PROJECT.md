# Fokus — Onlayn Ta'lim Platformasi (umumiy hujjat)

O'zbekiston maktab o'quvchilari uchun onlayn ta'lim platformasi: jonli video
darslar, Telegram uslubidagi chat, interaktiv doska, AI uy vazifasi tekshiruvi
va ota-ona nazorati. **Bu repo — faqat backend (API)**; frontend alohida
loyihada rivojlantiriladi va shu API'ni chaqiradi.

- Prod: `https://edu.thesofmebel.uz` (API), Swagger: `/api/docs/`
- Repo: `https://github.com/krv006/Education-Tech-Platform`
- Arxitektura qoidalari: [ARCHITECTURE.md](ARCHITECTURE.md) · Deploy: [DEPLOY.md](DEPLOY.md)

---

## 1. Stack

| Qatlam | Texnologiya |
|---|---|
| Backend | Django 6 + DRF + SimpleJWT (ASGI) |
| Real-time chat | Django Channels 4 + Redis channel layer (WebSocket) |
| Video darslar | LiveKit (self-hosted, WebRTC) |
| AI tekshiruv | Google Gemini (`google-generativeai`) |
| DB / Cache | PostgreSQL 17 / Redis 7 (dev'da sqlite/in-memory fallback) |
| Server | Docker Compose: gunicorn+uvicorn worker, Caddy (TLS + proxy) |

## 2. Arxitektura

```
Internet ──443──> Caddy (TLS avto, Let's Encrypt)
                   ├── /api, /admin, /static -> backend:8000 (gunicorn/uvicorn, ASGI)
                   ├── /ws/*                 -> backend:8000 (chat WebSocket)
                   ├── /media                -> umumiy volume
                   ├── /livekit              -> livekit:7880 (WebRTC signaling)
                   └── /                     -> 302 /api/docs/
Internet ──7881/tcp, 50000-50100/udp──> LiveKit (WebRTC media)
test-admin-api.navigocrm.com ──> navigo tarmog'idagi nginx (boshqa loyiha, shu Caddy orqali)
```

Kod qatlamlari (ARCHITECTURE.md qoidasi): `views.py` yupqa → biznes-logika
`services.py`da → o'qish `selectors.py`da. Ruxsatlar faqat
`apps/core/permissions.py` (RBAC matritsasi) orqali.

## 3. Modullar

| Modul | Nima qiladi | Asosiy endpointlar |
|---|---|---|
| `apps/accounts` | JWT auth, 4 rol (teacher/student/parent/admin), ota-ona↔bola bog'lash (taklif-kod + bolaning tasdig'i), rozilik (consent) | `/api/v1/auth/*` |
| `apps/lessons` | Kurs, dars jadvali, yozilish (enroll), davomat hisoboti | `/api/v1/courses/`, `/api/v1/lessons/`, `/api/v1/attendance/` |
| `apps/live` | LiveKit token, avtomatik davomat (kirdi/chiqdi), "Siz shu yerdamisiz?" diqqat tekshiruvi (random, 15s), fokus jurnali (oynadan chiqib-kirish) | `/api/v1/live/*` |
| `apps/chat` | Telegram uslubi: har kurs = guruh chat; direct faqat o'qituvchi↔o'quvchi (1 martalik so'rov → qabul/block); real-time WebSocket | `/api/v1/chat/*`, `ws /ws/chat/<room_id>/` |
| `apps/board` | Jonli dars doskasi: chizish, matn/formula bloklari, bir nechta sheet, o'chirish SABABI majburiy (jurnal), dars tugagach PDF → kurs chatiga | `/api/v1/board/<lesson_id>/*` |
| `apps/homework` | AI uy vazifasi: o'qituvchi vazifani rich-matn (sanitized HTML) yoki fayl (Word/PDF/rasm) bilan beradi, muddat qo'yadi; o'quvchi PDF/rasm/DOCX (Speaking'da audio) topshiradi; Gemini savolma-savol O'ZBEKCHA baholaydi; statistika, kech topshirish belgisi | `/api/v1/homework/*` |
| `apps/core` | UUID+timestamp baza modellari, soft-delete, RBAC, audit log, yagona xato formati | — |

## 4. Rollar (RBAC qisqacha)

- **O'qituvchi:** kurs/dars yaratish, doska boshqaruvi, vazifa berish/natijalar,
  chat guruhlari, direct so'rovlarni qabul/block
- **O'quvchi:** darsga kirish, doskada ruxsat so'rash, vazifa topshirish,
  chat (guruh + faqat o'qituvchi bilan direct)
- **Ota-ona:** bola hisobini yaratish/bog'lash (bola tasdig'i bilan), davomat,
  fokus jurnali, vazifa natijalarini ko'rish
- To'liq matritsa: `apps/core/permissions.py` (`ROLE_PERMISSIONS`)

## 5. Real-time chat (WebSocket)

```
wss://<domain>/ws/chat/<room_id>/?token=<JWT access>
```

| Yo'nalish | Payload | Izoh |
|---|---|---|
| C→S | `{"type":"message","text":"..."}` | Xabar yuborish (REST `POST .../send/` bilan teng kuchli) |
| C→S | `{"type":"typing"}` | "Yozmoqda..." signali |
| S→C | `{"type":"message","message":{id,room,sender,text,created_at}}` | Yangi xabar (REST orqali yuborilgani ham keladi) |
| S→C | `{"type":"typing","user_id","name"}` | Kimdir yozmoqda (o'zingizni filtrlang) |
| S→C | `{"type":"error","detail"}` | Yuborish xatosi |

Yopilish kodlari: `4401` — token yaroqsiz, `4403` — xonaga a'zo emas.
Tarix va o'qilgan belgisi REST'da: `GET .../messages/`, `POST .../read/`.
Texnik: Channels 4, JWT query-param auth (`apps/chat/ws_auth.py`), xona guruhi
`chat_<room_id>`, broadcast `transaction.on_commit`dan keyin (`realtime.py`).

## 6. AI uy vazifasi oqimi

1. O'qituvchi vazifa beradi (rich matn `nh3` bilan sanitize, ixtiyoriy fayl, muddat, til fanlari uchun skill: writing/reading/listening/speaking)
2. O'quvchi fayl topshiradi → `Submission(status=checking)` → tekshiruv fon thread'ida
3. `apps/homework/ai.py` fan profilini kurs `subject`idan avtomatik aniqlaydi
   (Matematika→math, Fizika→physics, Ingliz tili→language rejimi...), Gemini'ga
   multimodal yuboradi (PDF/rasm to'g'ridan-to'g'ri, DOCX matni lokal ajratiladi)
4. Natija JSON: `{overall_score, grade, questions[{score, mistakes, suggestions...}], summary}` —
   barcha matnlar o'zbekcha; baholar: A'lo / Juda yaxshi / Yaxshi / Qoniqarli / ...
5. Frontend polling: `GET /api/v1/homework/submissions/<id>/` (`checking→done|error`)

**Talab:** serverda `GEMINI_API_KEY` env (aistudio.google.com/apikey).

## 7. Muhit o'zgaruvchilari (asosiylari)

| Env | Nima uchun |
|---|---|
| `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Django |
| `CORS_ALLOWED_ORIGINS` | **Frontend domeni SHU YERGA yoziladi** (vergul bilan) |
| `POSTGRES_*` | DB (bo'lmasa sqlite) |
| `REDIS_URL` | Cache + WebSocket channel layer (prod'da shart) |
| `LIVEKIT_API_KEY/SECRET/URL` | Video darslar |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | AI uy vazifasi |

To'liq namuna: `.env.prod.example` (prod), `.env.example` (dev).

## 8. Ishga tushirish

**Dev (Windows/Linux):**
```bash
python -m venv .venv && .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
docker compose up -d              # ixtiyoriy: Postgres+Redis+LiveKit
python manage.py migrate && python manage.py runserver   # runserver ASGI (daphne)
python manage.py seed_fake        # demo: teacher/student/perents, parol: 1
```

**Prod (serverda):**
```bash
cd /var/www/edu_platform && git pull && make up
```
Birinchi o'rnatish: `bash scripts/deploy.sh`. Lokaldan: `bash scripts/deploy-remote.sh`.

## 9. Testlar

```bash
python manage.py test            # hammasi
python manage.py test apps.chat apps.board apps.homework
```
Qamrov: chat oqimi + 5 ta WebSocket testi (JWT, ruxsat, broadcast, typing),
doska (ruxsat/o'chirish sababi/PDF), homework (24 test — AI mock, RBAC, fayllar),
davomat/auth oqimlari. AI chaqiruvi testlarda mock — kalit kerak emas.

## 10. EduTech.docx talablar holati

- ✅ Telegram uslubidagi chat, 1 martalik direct so'rov, block
- ✅ Kurs = guruh chat; o'quvchilar orasida DM yo'q
- ✅ Random diqqat tekshiruvi (3-5 marta, 15s, vaqti sirlangan)
- ✅ Doska: ruxsat so'rash, chizish, sheet'lar, sababli o'chirish, PDF→chat, faqat platformada
- ✅ Fokus jurnali (oynadan chiqib-kirish — ota-onaga)
- ✅ AI uy vazifasi (qo'shimcha talab sifatida qo'shildi)
- ⚠️ Skrinshot/screenrecord taqiqlash — brauzerda IMKONSIZ; yechim: desktop app
  (Electron `setContentProtection`) yoki mobil ilova (`FLAG_SECURE`) — reja
- ⚠️ Qo'shimcha ekran taqiqlash — brauzerda imkonsiz; desktop app'da amaliy hal bo'ladi
- ⏳ Dars video yozuvi avtomatik saqlash — LiveKit Egress bilan qilinadi (reja)

## 11. Keyingi qadamlar

1. LiveKit Egress — dars yozuvini avtomatik saqlash (guruh o'chirilguncha)
2. Desktop app (Electron qobiq): skrinshot-himoya + ikkinchi ekran nazorati + kiosk
3. Video ustiga o'quvchi ismli watermark
4. Mobil ilova (WebView + FLAG_SECURE)

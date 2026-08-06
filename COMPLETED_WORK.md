# Qilingan ishlar — backend

Bu fayl shu sessiyada backend'ga qilingan qo'shimchalarni hujjatlashtiradi.
Frontend jamoasi uchun: har bir bo'limda **aniq endpoint, so'rov/javob shakli**
berilgan — shunga qarab UI qurish mumkin. Loyiha manbasi: `krv006/Education-Tech-Platform`
(GitHub) klonlangan asosda ishlandi.

---

## 1) Video yozib olish (LiveKit Egress) — muammo tuzatildi

**Muammo:** dars video yozuvi hech qachon saqlanmayotgan edi.

**Sabab:** `docker-compose.yml` (dev muhiti)da **egress konteyneri umuman yo'q
edi** va `livekit.yaml`da Redis manzili ko'rsatilmagan edi — bu ikkalasisiz
LiveKit Egress ishga tusha olmaydi.

**Tuzatildi:**
- `docker-compose.yml` ga `egress` xizmati qo'shildi (`livekit/egress:latest`, Redis bilan bog'landi, `./recordings:/out` volume).
- Bu bilan `docker compose up -d` qilinganda video yozuv avtomatik ishlaydi (dars LIVE bo'lganda boshlanadi — kod tomoni allaqachon mavjud edi, `apps/live/services.py: start_recording()`).

**Backend endpoint'lari (o'zgarmagan, faqat endi ishlaydi):**

| Method | Path | Kim | Tavsif |
|---|---|---|---|
| POST | `/api/v1/live/token/` | teacher/student | Xonaga kirish tokeni. O'qituvchi kirganda dars LIVE bo'ladi va yozuv **avtomatik** boshlanadi |
| POST | `/api/v1/lessons/{id}/finish/` | teacher | Darsni yakunlaydi. Body: `{"recording_title": "..."}` (ixtiyoriy — bo'sh bo'lsa dars nomi olinadi). Yozuv shu nom bilan **guruh chatga** e'lon qilinadi |
| GET | `/api/v1/lessons/{id}/recording/` | a'zolar | Yozuv holati. Javob: `{lesson_id, title, status, ready, created_at, ended_at, error, stream_url}`. `status`: `recording` \| `completed` \| `failed`. `stream_url` faqat `ready:true` bo'lsa keladi |
| DELETE | `/api/v1/lessons/{id}/recording/` | faqat teacher | Yozuvni butunlay o'chiradi (fayl + baza) |
| GET | `{stream_url}` | ochiq (imzolangan token bilan) | Video oqimi — `<video src>` ga to'g'ridan-to'g'ri qo'yiladi, Authorization header kerak emas. Range (seek) qo'llab-quvvatlanadi |

**Frontend uchun muhim:** `stream_url` — **muddatli imzolangan havola** (3 soat),
doimiy URL emas. Har safar `GET /recording/` chaqirib yangisini olish kerak.
Yuklab olish tugmasi YO'Q — faqat platforma ichida ko'rish (`Content-Disposition: inline`).

**Ma'lum cheklov:** kod to'liq to'g'ri ishlashi Django-tomonda (status, egress_id,
boshlash/to'xtatish) API orqali tasdiqlangan. Lekin haqiqiy video faylning
diskka yozilishini **shu Windows/Docker Desktop dev muhitida** oxirigacha
tekshirib bo'lmadi — WebRTC/ICE tarmoq cheklovi tufayli (egress konteyneri
STUN orqali ochiq internet IP'sini ishlatishga urinib, mahalliy tarmoqqa
qaytib kelolmayapti). Bu — Windows Docker Desktop'ga xos muhit muammosi,
real Linux serverda kuzatilishi kutilmaydi.

---

## 2) Bildirishnoma tizimi (admin → user) — yangi

Yangi Django app: `apps/notifications`. Admin istalgan foydalanuvchini
qidirib, unga (yoki hammaga) xabar yuboradi; xabar CKEditor'dan keladigan
HTML matn (`description`); har qabul qiluvchi uchun alohida o'qildi/o'qilmadi
holati kuzatiladi.

### Foydalanuvchi qidirish

| Method | Path | Kim | Tavsif |
|---|---|---|---|
| GET | `/api/v1/auth/users/search/?q=<matn>` | admin | Barcha rol bo'yicha qidiruv (username/ism), 2+ belgidan. Javob: `UserSerializer` massivi (10 tagacha) |

### Bildirishnoma endpoint'lari (`/api/v1/notifications/`)

| Method | Path | Kim | Tavsif |
|---|---|---|---|
| POST | `/notifications/send/` | admin | Yuborish. Body: `{"description": "<p>HTML matn</p>", "target_type": "user"\|"all", "user_id": "<uuid>"}` (`user_id` faqat `target_type=user`da kerak) |
| GET | `/notifications/` | har kim | O'zining inbox'i, paginatsiyalangan |
| POST | `/notifications/{notification_id}/read/` | qabul qiluvchi | O'qildi deb belgilaydi |
| GET | `/notifications/unread-count/` | har kim | `{"count": N}` — bell/badge uchun |
| GET | `/notifications/sent/` | admin | O'zi yuborganlari, `read_count`/`total_count` bilan |
| GET | `/notifications/{id}/recipients/` | admin | Aynan kim o'qidi, kim yo'q (ism + vaqt) |

### JSON shakllar

**Inbox qatori** (`GET /notifications/`):
```json
{
  "id": "recipient-uuid",
  "notification": {
    "id": "notification-uuid",
    "sender": {"id": "...", "username": "demo_admin", "first_name": "Admin", "role": "admin", ...},
    "description": "<p>Ertaga <b>nazorat ishi</b> bo'ladi</p>",
    "target_type": "user",
    "created_at": "2026-08-06T15:05:05Z"
  },
  "is_read": false,
  "read_at": null,
  "created_at": "2026-08-06T15:05:05Z"
}
```

**Admin "sent" qatori** (`GET /notifications/sent/`):
```json
{"id": "...", "description": "...", "target_type": "all", "created_at": "...", "read_count": 3, "total_count": 5}
```

**Recipients tafsiloti** (`GET /notifications/{id}/recipients/`):
```json
[{"user": {"username": "demo_teacher", ...}, "read_at": "2026-08-06T15:05:26Z"}]
```

### Real-time (WebSocket)

```
wss://<domain>/ws/notifications/?token=<JWT access>
```
Ulangandan keyin yangi xabar kelganda serverdan darhol:
```json
{"type": "notification", "notification": { ...NotificationSerializer... }}
```
Bu — badge/toast uchun (masalan "yangi xabar" belgisi darhol yonishi).
Ulanish yopilishi: `4401` — token yaroqsiz.

**Xavfsizlik:** HTML matn `nh3` bilan tozalanadi — faqat formatlash teglariga
(qalin, ro'yxat, havola va h.k.) ruxsat, rasm/skript yo'q (FRD talabi shu edi).

**Ruxsat:** faqat `admin`/`super_admin` roli yubora oladi (`notification.send`
permission). Boshqa hamma faqat o'z inbox'ini ko'radi/o'qiydi.

### Django admin panelida (frontend tayyor bo'lguncha qo'lda test qilish uchun)

`/admin/notifications/notification/` — faqat **ko'rish/jurnal** (kim nima
yuborgan, kim o'qigan). Standart "Add" (qo'shish) formasi **ataylab
o'chirilgan** — chunki xom Django formasi orqali saqlash `NotificationRecipient`
qatorlarini yaratmaydi (fan-out faqat `services.send_notification()`da bo'ladi),
ya'ni xabar hech kimga bormay qoladi.

Shuning o'rniga ro'yxat tepasida **ko'k "Yangi xabar yuborish"** havolasi —
u to'g'ridan-to'g'ri `/admin/notifications/notification/send/` sahifasiga olib
boradi (maxsus forma, to'g'ri service qatlamini chaqiradi):
- **Kimga**: "Bitta foydalanuvchi" / "Hammaga" (radio) — tanlovga qarab
  foydalanuvchi tanlash maydoni ko'rinadi/yashiriladi
- **Foydalanuvchi**: select2 (qidiriladigan dropdown), faqat "Bitta
  foydalanuvchi" tanlanganda ko'rinadi
- **Xabar matni**: oddiy textarea (CKEditor frontend tomonda ulanadi)
- Sender maydoni **yo'q** — avtomatik tizimga kirgan admin

---

## 3) Fokus nazorati eskalatsiyasi (1-2 marta ogohlantirish, 3-chisida ota-onaga)

Eski loyihada qilingan EPAM imtihon uslubidagi mantiq yangi backend'ga
ko'chirildi (yangi repo'da bu funksiya umuman yo'q edi).

| Method | Path | Kim | Tavsif |
|---|---|---|---|
| POST | `/api/v1/live/focus/` | student | Body: `{"lesson_id": "...", "kind": "exit"\|"return"}` |

**Javob shakli** (`kind=exit` bo'lganda):
```json
{"ok": true, "kind": "exit", "exit_count": 3, "threshold": 3, "parent_notified": true}
```
- `exit_count` — shu darsda jami necha marta oynadan chiqqani
- `threshold` — chegara (default **3**, `.env`dagi `FOCUS_PARENT_ALERT_THRESHOLD` bilan sozlanadi)
- `parent_notified` — `true` bo'lsa, chegaradan oshgan va ota-onaga signal yaratilgan (faqat birinchi marta `true` bo'lganda yaratiladi, keyingi chiqishlarda ham `true` qaytadi, lekin qayta signal yaratilmaydi — spam yo'q)

`kind=return` bo'lsa — hisoblagichga ta'sir qilmaydi, `exit_count`/`parent_notified` bo'sh/`false` qaytadi.

**Ota-ona ko'rishi:** `GET /api/v1/attendance/` javobida (`AttendanceSerializer`)
yangi maydon: **`focus_alert`** (`true`/`false`) — o'sha o'quvchi shu darsda
chegaradan oshib chiqqanmi. Mavjud `focus` maydoni (taymlayn: chiqish/qaytish
vaqtlari) o'zgarmagan.

---

## Lokal ishga tushirish (frontend jamoasi uchun)

```bash
cd Education-Tech-Platform
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.txt
./.venv/Scripts/python.exe -m pip install "Django>=6.0,<6.1"   # muhim: 6.1 DRF bilan mos emas
./.venv/Scripts/python.exe manage.py migrate
./.venv/Scripts/python.exe manage.py seed_demo
./.venv/Scripts/python.exe manage.py runserver 8001
```

Video yozuvni sinash uchun qo'shimcha: `docker compose up -d redis livekit egress`.

**Demo hisoblar** (parol hammasida `Demo1234!`):

| Rol | Username | Izoh |
|---|---|---|
| O'qituvchi | `demo_teacher` | `seed_demo` yaratadi |
| O'quvchi | `demo_child` | `seed_demo` yaratadi |
| Ota-ona | `demo_parent` | `seed_demo` yaratadi |
| **Admin** | `demo_admin` | Qo'lda yaratilgan (pastga qarang) — `/admin/` panelga kirish uchun `is_staff`/`is_superuser` ham vaqtinchalik yoqilgan |
| O'qituvchi (test) | `test_teacher2` | Bildirishnoma "hammaga" ssenariysini sinash uchun qo'shimcha |
| O'quvchi (test) | `test_student2`, `test_student3` | — |
| Ota-ona (test) | `test_parent2` | — |

`seed_demo` admin hisob yaratmaydi — kerak bo'lsa Django shell orqali qo'shish kerak:
```python
from apps.accounts.models import User
u = User(username='demo_admin', role=User.Role.ADMIN, first_name='Admin')
u.set_password('Demo1234!')
u.is_staff = True       # /admin/ panelga kirish uchun (vaqtinchalik, testdan keyin qaytariladi)
u.is_superuser = True
u.save()
```

**API docs:** `http://localhost:8001/api/docs/` (Swagger, drf-spectacular).

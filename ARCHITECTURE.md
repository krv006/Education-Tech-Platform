# Fokus — Backend Arxitektura

Bu hujjat tizimning qatlamli arxitekturasini, qoidalarini va nima uchun shunday
qurilganini tavsiflaydi. **Yangi kod yozishdan oldin shu qoidalarga qarang.**

## 1. Qatlamlar (Layered Architecture)

```
HTTP so'rov
   │
   ▼
┌─────────────────────────────────────────────────┐
│  MIDDLEWARE   RequestID → CORS → Auth → Throttle │
├─────────────────────────────────────────────────┤
│  VIEW (yupqa) faqat: parse → service → serialize │   apps/*/views.py
├────────────────────────┬────────────────────────┤
│  SERVICE (yozish)      │  SELECTOR (o'qish)      │   services.py / selectors.py
│  biznes-qarorlar,      │  "kim nimani ko'radi"   │
│  transaction, audit    │  querylari              │
├────────────────────────┴────────────────────────┤
│  MODEL   UUID PK · timestamps · soft delete      │   models.py
└─────────────────────────────────────────────────┘
```

### Qat'iy qoidalar

1. **View'da biznes-logika YO'Q.** View faqat HTTP bilan ishlaydi. Qaror qabul
   qilish (`if role == ...`, holat o'zgartirish) — service'da.
2. **Yozuv faqat service orqali.** Har bir service `@transaction.atomic` va
   muhim harakatda `audit.record()` chaqiradi.
3. **Ko'rish huquqi faqat selector'da.** Ota-ona faqat APPROVED bog'lanishdagi
   bolasini ko'rishi — bu selector'larda kodlangan, view unutib qo'yolmaydi.
4. **Ruxsatlar faqat registry'da** (`apps/core/permissions.py`). View'da
   `RequirePerm('kalit')` ishlatiladi, rol tekshiruvi qo'lda yozilmaydi.

## 2. Core qatlam (`apps/core`)

| Komponent | Vazifasi |
|---|---|
| `TimeStampedUUIDModel` | UUID PK (ID taxmin qilib bo'lmaydi) + created/updated |
| `SoftDeleteModel` | `delete()` belgilaydi, o'chirmaydi — huquqiy/audit talab |
| `AuditLog` + `audit.record()` | FRD security.audit: kim, qachon, nima qildi, qaysi IP |
| `permissions.py` | FRD RBAC matritsasi kodda — rol → ruxsat kalitlari |
| `exceptions.py` | Yagona xato formati (pastda) |
| `middleware.RequestIDMiddleware` | Har so'rovga X-Request-ID — log/debug bog'lash |
| `pagination.py` | Default 20, `?page_size=` max 100 |
| `views.HealthView` | `GET /api/health/` — DB + cache monitoring |

## 3. Xato formati (Error Envelope)

Barcha xatolar bitta shaklda — frontend bitta handler yozadi:

```json
{
  "success": false,
  "error": {
    "code": "permission_denied",
    "message": "Sizning rolingizda bu amal uchun ruxsat yo'q.",
    "details": { }
  }
}
```

Kutilmagan xatolar (500) log'ga to'liq yoziladi, mijozga ichki tafsilot chiqmaydi.

## 4. RBAC — ruxsat kalitlari

Rollar: `super_admin`, `admin`, `teacher`, `student`, `parent` (+ guest = anonim).
Kalitlar FRD uslubida: `course.create`, `lesson.finish`, `link.request`,
`consent.manage`, `room.token` ... To'liq matritsa: `apps/core/permissions.py`.

Rolga ruxsat qo'shish/olish — faqat o'sha faylda bitta satr.

## 5. Xavfsizlik

- **JWT** (60 daq access / 7 kun refresh, refresh rotation)
- **Rate limiting:** anon 60/min, user 240/min, auth endpointlar 30/min (bruteforce)
- **Rozilik modeli:** ota-ona kuzatuvi faqat bola tasdig'i bilan (ParentChildLink),
  bola istalgan payt uzadi; Consent bayroqlari (camera/recording/analytics)
- **Audit log:** har muhim harakat (register, link, consent, dars, room join) yoziladi
- **Prod hardening:** `DJANGO_ENV=prod` — HSTS, secure cookies, SSL redirect,
  insecure SECRET_KEY bilan ishga tushmaydi

## 6. Muhitlar

```
root/settings/
  base.py   — umumiy (DRF, JWT, RBAC, LiveKit, logging)
  dev.py    — DEBUG, sqlite fallback, locmem cache
  prod.py   — Postgres majburiy, security headers
```

`DJANGO_ENV=prod` bilan prod rejim. Hamma sozlama `.env` dan.

## 7. Kengayish nuqtalari (keyingi bosqichlar)

| Ehtiyoj | Qayerga qo'shiladi |
|---|---|
| To'lov (Click/Payme) | `apps/payments` — service qatlami tayyor naqsh |
| OTP (Eskiz SMS) | `apps/accounts/services.py` + `auth` throttle scope bor |
| Chat | LiveKit data channels yoki `apps/chat` (WebSocket/Channels) |
| Fokus hodisalari | `apps/focus` — exit_log FRD moduli, Attendance naqshida |
| Celery (hisobot, eslatma) | Redis allaqachon compose'da |

## 8. Testlar

```bash
python manage.py test          # 14 test: auth, link/consent, RBAC, davomat, soft-delete
python scripts/smoke_test.py   # jonli e2e: 18 tekshiruv
python manage.py seed_demo     # demo ma'lumot
```

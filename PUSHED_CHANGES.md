# `asem-mirzaeva` branch — push qilingan o'zgarishlar

`main` bilan solishtirganda 3 ta commit, 14 ta fayl, 545(+)/9(-) qator.
Hech biri `main`ga merge qilinmagan — hozircha faqat shu branch'da,
PR ochilmagan.

```
git log main..asem-mirzaeva --oneline
f2a4d88 fix: grant TEACHER the room.leave permission
d68bbf1 perf(egress): lower lesson recording to 480p/15fps to cut CPU cost
740ea59 feat: live-room invite/ban moderation + auto-kick chat on unenroll
```

---

## Commit 1 — `740ea59`: invite/ban moderatsiyasi + guruhdan avtomatik chiqarish

**Nima uchun:** Zoom uslubidagi talab — o'qituvchi darsga o'quvchilarni taklif
qila olishi, xohlaganini chetlashtira olishi kerak edi. Buni qurish jarayonida
alohida bog'liq bug ham topildi va tuzatildi (guruhdan chiqarilgan o'quvchining
ochiq chat WebSocket ulanishi avtomatik yopilmasligi).

### Yangi endpointlar (`room.moderate` — faqat kurs o'qituvchisi)

| Endpoint | Vazifasi |
|---|---|
| `POST /api/v1/live/invite/` | `{lesson_id, student_id?}` — bittasiga yoki (student_id yo'q bo'lsa) hammasiga real-time bildirishnoma |
| `POST /api/v1/live/ban/` | `{lesson_id, student_id}` — xonadan chiqaradi + shu darsga qayta kirishni bloklaydi |
| `POST /api/v1/live/unban/` | Chetlashtirishni bekor qiladi |

### Yangi model
`LessonBan` ([apps/lessons/models.py](apps/lessons/models.py)) — `lesson + student + banned_by`, migratsiya `0009_lessonban.py`. `issue_room_token()` endi shu jadvalni tekshiradi.

### Kuchaytirilgan mavjud endpoint
`POST /courses/{id}/unenroll/` — endi o'chirilgan o'quvchining ochiq guruh-chat WebSocket ulanishi bo'lsa, `{"type": "removed"}` yuborib `code=4403` bilan yopadi (`apps/chat/realtime.py`: `broadcast_member_removed`, `apps/chat/consumers.py`: `chat_member_removed`).

### Testlar
`apps/lessons/tests.py: InviteBanTests` (9 ta), `apps/chat/tests.py: test_unenroll_closes_removed_students_socket` (real WebSocket testi).

### Hujjat
[LIVE_MODERATION_API.md](LIVE_MODERATION_API.md) — frontend uchun to'liq shartnoma (request/response, WS event'lari, xato holatlari).

---

## Commit 2 — `d68bbf1`: dars yozuvini 480p/15fps'ga tushirish (CPU tejash)

**Nima uchun:** LiveKit egress CPU sarfini kamaytirish — 720p/30 preset o'rniga.

### Kod o'zgarishi
`apps/live/services.py: _egress_start()` — `EncodingOptionsPreset.H264_720P_30` o'rniga custom `EncodingOptions(width=854, height=480, framerate=15, video_bitrate=900, audio_bitrate=64)`. **Muhim:** LiveKit'ning tayyor preset ro'yxatida 480p/540p umuman yo'q (faqat 720p/1080p) — shuning uchun `advanced` maydoni ishlatildi, tayyor preset emas.

### Infra o'zgarishi
`docker-compose.prod.yml`: egress `cpus: 4 → 3` — **PROVISIONAL**, real `docker stats egress` bilan hali tasdiqlanmagan (izohda aniq yozilgan). LiveKit hujjati: room-composite egress 2-6 CPU oralig'ida ishlatishi mumkin, rezolyutsiyadan qat'iy nazar sobit emas.

### Diqqat
Bu o'zgarish production'da **hali sinovdan o'tkazilmagan** — real dars yozib, CPU sarfini tekshirish kerak (buyruq: `docker stats egress`), aks holda yozuvlar "resource exhausted" bilan rad etilishi mumkin.

---

## Commit 3 — `f2a4d88`: TEACHER'ga `room.leave` ruxsati

**Nima uchun:** Frontend `/api/v1/live/leave/`ni o'qituvchi uchun ham chaqiradi (WebRTC uzilganda tozalash), lekin RBAC registrida bu ruxsat faqat STUDENT'da bor edi — o'qituvchi har safar `403` olardi (real skrinshotda ko'ringan xato).

### Kod o'zgarishi
`apps/core/permissions.py`: `TEACHER` ro'yxatiga `'room.leave'` qo'shildi (1 qator). Xavfsiz — `mark_left()` o'qituvchi uchun mos Attendance topmasa, shunchaki `False` qaytaradi.

---

## Push qilinmagan, hali ochiq masalalar

- **2 ta stuck LIVE dars** (`lesson-a9371dba4a2a`, `lesson-4edbb7705271`) — production serverda qo'lda `FINISHED`ga o'tkazish kerak (admin panel yoki `manage.py shell`), avtomatik tozalovchi hali yozilmagan.
- **`ENGINEERING_DEEP_DIVE.md`** — lokal, hali push qilinmagan (LiveKit/backend konseptual hujjat).
- **480p/`cpus: 3`** — real serverda tasdiqlanmagan, deploy qilishdan oldin `docker stats` bilan tekshirish kerak.
- **Doskaga chizish uchun "ruxsat so'rash" tugmasi** — backend'da bunday endpoint umuman yo'q (faqat o'qituvchi tomondan `grant/` bor), qurish rejalashtirilgan, hali boshlanmagan.

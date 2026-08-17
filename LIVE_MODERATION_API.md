# Dars moderatsiyasi: Invite / Ban / Guruhdan avtomatik chiqarish

Bugun qo'shilgan 3 ta yangi imkoniyat uchun frontend shartnomasi (Zoom
uslubidagi: o'qituvchi darsga taklif qiladi, xohlagan o'quvchini
chetlashtiradi; guruhdan chiqarilgan o'quvchining ochiq chati o'zi yopiladi).

**Base URL**: `/api/v1/live/`
**Auth**: JWT (`Authorization: Bearer <access_token>`)
**Ruxsat**: uchalasi ham `room.moderate` kaliti bilan ishlaydi — bu allaqachon
TEACHER rolida bor, yangi ruxsat kaliti qo'shilmagan. Faqat **shu darsning
kursiga tegishli o'qituvchi** chaqira oladi — boshqa o'qituvchi `403` oladi.

Xato javoblari umumiy shaklda keladi (`ARCHITECTURE.md`dagi Error Envelope):
```json
{"success": false, "error": {"code": "...", "message": "...", "details": {...}}}
```

---

## 1. Darsga taklif — `POST /api/v1/live/invite/`

O'quvchiga (yoki hammasiga) "dars boshlandi, kiring" degan **ogohlantirish**
yuboradi. Bu shunchaki bildirishnoma — o'quvchi xonaga baribir o'zi
`POST /api/v1/live/token/` chaqirib kiradi, invite shart emas, faqat uni
xabardor qiladi.

**Body:**
```json
{ "lesson_id": "uuid", "student_id": "uuid | ixtiyoriy" }
```
- `student_id` **berilmasa** → kursga `APPROVED` yozilgan **hamma o'quvchiga**.
- `student_id` **berilsa** → faqat o'sha bittasiga (kursga yozilmagan bo'lsa `404`).

**Javob:**
```json
{ "invited": 5 }
```
(nechta o'quvchiga yuborilgani — sonli)

**Xatolar:** `403` — chaqiruvchi shu kursning o'qituvchisi emas. `404` — dars yoki (student_id berilganda) o'quvchi topilmadi.

### O'quvchi tomonida qanday keladi

Mavjud bildirishnoma infratuzilmasi orqali — yangi WS kanal shart emas, allaqachon bor:

- **Real-time (onlayn bo'lsa):** `wss://<domain>/ws/notifications/?token=<access>` orqali darhol keladi:
  ```json
  { "type": "notification", "notification": { "id", "sender", "description", "target_type": "user", "created_at" } }
  ```
  `description` matni: `«<dars nomi>» darsi boshlandi — hoziroq kiring.`
- **Oflayn bo'lsa ham:** inboxida qoladi — `GET /api/v1/notifications/` (badge uchun `GET /api/v1/notifications/unread-count/`).

---

## 2. Chetlashtirish — `POST /api/v1/live/ban/`

O'quvchini shu darsdan **chetlashtiradi**: hozir xonada bo'lsa LiveKit orqali
darhol video/audio ulanishini uzadi, va **qayta kirishini bloklaydi**.

**Body:**
```json
{ "lesson_id": "uuid", "student_id": "uuid" }
```
**Javob:** `{ "ok": true }`
**Xatolar:** `403` — chaqiruvchi egasi emas. `404` — dars yoki o'quvchi topilmadi.

### Frontendda nima kutish kerak

- Agar o'quvchi hozir xonada bo'lsa — LiveKit client SDK'da `disconnected`/`participant kicked` hodisasi keladi (LiveKit'ning o'z mexanizmi) — shuni ushlab, o'quvchini darsdan chiqaring.
- Ban qilingan o'quvchi **qayta** `POST /api/v1/live/token/` chaqirsa — endi `403`:
  ```json
  {"success": false, "error": {"code": "permission_denied", "message": "Siz bu darsdan chetlashtirilgansiz.", "details": null}}
  ```
- Ban faqat **shu bitta darsga** tegishli (`lesson_id` bo'yicha) — boshqa darslarga yoki kursning o'ziga ta'sir qilmaydi, kurs yozilishi (`Enrollment`) o'zgarmaydi.

## Chetlashtirishni bekor qilish — `POST /api/v1/live/unban/`

**Body:** `{ "lesson_id": "uuid", "student_id": "uuid" }`
**Javob:** `{ "unbanned": true }` (ban topilmasa `false`)

---

## 3. Guruhdan chiqarilganda chat avtomatik yopiladi

Bu **yangi endpoint emas** — mavjud `POST /api/v1/courses/{id}/unenroll/`
xatti-harakati kuchaytirildi. Muammo: o'qituvchi o'quvchini kursdan
chiqarganda, agar o'quvchining brauzerida guruh chati **allaqachon ochiq**
(WebSocket ulangan) bo'lsa, u avvalgidek xabarlarni qabul qilib turaverardi —
endi bunday emas.

**O'zgargan xatti-harakat:** `unenroll` muvaffaqiyatli bo'lgach, agar
chiqarilgan o'quvchining o'sha kurs guruh chatida ochiq WS ulanishi bo'lsa,
server unga darhol yuboradi:
```json
{ "type": "removed" }
```
va ulanishni **`code=4403`** bilan yopadi.

**Frontendda nima qilish kerak:** chat WebSocket handlerida `type === "removed"`
kelganda — foydalanuvchini shu chat oynasidan chiqarib yuboring / ro'yxatdan
olib tashlang (server socketni baribir yopadi, lekin foydalanuvchiga tushunarli
signal berish uchun shu eventni alohida ushlash tavsiya etiladi). Qayta
ulanishga urinsa (`wss://<domain>/ws/chat/<room_id>/?token=...`) — endi
`can_read` `false` qaytaradi, ulanish umuman ochilmaydi (`4403`).

Bu faqat **kurs guruh chatiga** tegishli — direct (shaxsiy) chatlarga ta'sir qilmaydi.

---

## Xulosa jadvali

| Endpoint | Kim chaqiradi | Natija |
|---|---|---|
| `POST /live/invite/` | Kurs o'qituvchisi | O'quvchi(lar)ga real-time + inbox bildirishnoma |
| `POST /live/ban/` | Kurs o'qituvchisi | Xonadan chiqaradi + shu darsga qayta kirishni bloklaydi |
| `POST /live/unban/` | Kurs o'qituvchisi | Ban bekor, qayta kirish mumkin |
| `POST /courses/{id}/unenroll/` (mavjud, kuchaytirildi) | O'qituvchi/o'quvchi/ota-ona | Kursdan chiqaradi + ochiq chat socketini `removed` bilan yopadi |

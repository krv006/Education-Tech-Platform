# Frontend uchun qolgan ishlar — kamera ruxsati + doska signali (2026-09-04)

Backend tomoni **to'liq tayyor va production'da**. Bu hujjat faqat frontendda
qolgan ikkita narsani tasvirlaydi. Ikkalasi ham mavjud **mikrofon** oqimi
bilan bir xil naqsh — `useMicSignals` hook'ini nusxalab, nomlarni almashtirish
kifoya.

**WebSocket**: hammasi mavjud `wss://<domain>/ws/board/<lesson_id>/?token=<JWT>`
ulanishining o'zidan keladi — yangi ulanish ochish shart emas.

---

## 1. Kamera endi ruxsat bilan ochiladi (avval hammaga erkin edi)

**O'zgargan xatti-harakat**: o'quvchining LiveKit tokeni endi kamera nashr
qilish huquqisiz keladi. O'qituvchi ruxsat berguncha, o'quvchi **kamerasini
umuman yoqolmaydi** (`TrackToggle`/`setCameraEnabled` xato qaytaradi yoki
jimgina ishlamaydi — LiveKit server rad etadi).

### REST — mikrofon bilan AYNAN bir xil naqsh

| Method | Path | Kim | Tavsif |
|---|---|---|---|
| POST | `/api/v1/live/request-camera/` | O'quvchi | `{lesson_id}` — kamera so'raydi |
| POST | `/api/v1/live/grant-camera/` | O'qituvchi | `{lesson_id, student_id}` — ruxsat beradi |
| POST | `/api/v1/live/deny-camera/` | O'qituvchi | `{lesson_id, student_id}` — rad etadi |

Javoblar `request-mic`/`grant-mic`/`deny-mic` bilan bir xil shaklda
(`{"ok": true}` yoki `{"denied": true/false}`).

### WebSocket eventlari (board kanali orqali, `mic_*` bilan bir xil qatordan)

```json
{ "type": "camera_request", "student_id": "uuid", "name": "Sardor" }
{ "type": "camera_granted", "student_id": "uuid" }
{ "type": "camera_denied", "student_id": "uuid" }
```

Frontend logikasi mikrofonnikiga bir xil bo'lishi kerak:
- **`camera_request`** — faqat `is_teacher=true` bo'lganda ko'rsatiladi ("qo'l ko'tarish" belgisi, mikrofon so'rovi qatoriga o'xshab).
- **`camera_granted`** — HAMMAGA keladi, har bir client o'zi filtrlaydi: `studentId === room.localParticipant.identity` bo'lsa — o'zining kamera tugmasini yoqadi/faollashtiradi.
- **`camera_denied`** — shu o'quvchining o'zi "so'rash" tugmasini qayta faollashtiradi.

### Sahifa yangilanganda / qayta ulanganda holatni tiklash

`GET /api/v1/board/{lesson_id}/` javobiga yangi maydon qo'shildi (faqat
`is_teacher=true` bo'lganda, `pending_mic_requests` bilan bir qatorda):

```json
{
  "pending_mic_requests": [{ "student_id": "uuid", "name": "Sardor" }],
  "pending_camera_requests": [{ "student_id": "uuid", "name": "Sardor" }]
}
```

### UI

`live-room.tsx`dagi `TrackToggle source={Track.Source.Camera}` hozircha
**shartsiz** ko'rsatiladi (mikrofon esa `canPublishSource` bilan tekshiriladi).
Kamerani ham xuddi shunday — `useLocalParticipantPermissions()` +
`canPublishSource(permissions, CAMERA_SOURCE)` bilan tekshirish, ruxsat
bo'lmasa `StudentMicControl`ga o'xshash "so'rash" tugmasi ko'rsatish kerak.

---

## 2. Doska ruxsati — yangi WebSocket signali

**Bug**: o'qituvchi doskaga chizish ruxsatini bergach, o'quvchi sahifani
yangilamaguncha buni bilmay, chiza olmay turardi (backend ruxsat berilgan
edi, lekin frontendga signal ketmagan). Endi tuzatildi:

```json
{ "type": "board_granted", "student_id": "uuid" }
```

Frontend: bu event kelganda, agar `student_id === o'zim` bo'lsa — doskaning
`can_draw` holatini `true`ga o'rnatish (yoki oddiygina `GET /board/{id}/`ni
qayta chaqirish) kerak. Hozircha bu event uchun HECH QANDAY handler yo'q —
qo'shilishi kerak.

---

## Eslatma

Kamera cheklovi **hozir productionda faol** — frontend bu ishni qilib
bo'lmaguncha, o'quvchilar kamerani umuman yoqa olmaydi. Tezroq qilingani
ma'qul.

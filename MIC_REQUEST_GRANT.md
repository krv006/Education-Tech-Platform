# Mikrofon so'rov/ruxsat — yangi funksiya

## Nima o'zgardi

Ilgari o'quvchi darsga kirganda **kamera va mikrofon ikkalasi ham avtomatik
yoqiq** edi. Endi: **kamera yoqiq qoladi, mikrofon esa o'chiq holda kiradi** —
o'quvchi gapirish uchun avval so'rashi, o'qituvchi ruxsat berishi kerak
(Zoom/Google Meet uslubidagi "qo'l ko'tarish").

## Endpointlar

| Method | Path | Kim | Body | Javob |
|---|---|---|---|---|
| POST | `/api/v1/live/request-mic/` | student | `{"lesson_id": "uuid"}` | `{"ok": true}` |
| POST | `/api/v1/live/grant-mic/` | teacher (shu darsning o'qituvchisi) | `{"lesson_id": "uuid", "student_id": "uuid"}` | `{"ok": true}` |
| POST | `/api/v1/live/deny-mic/` | teacher (shu darsning o'qituvchisi) | `{"lesson_id": "uuid", "student_id": "uuid"}` | `{"denied": bool}` |

**Navbat qoidalari**:
- **FIFO** — `pending_mic_requests` har doim so'ralgan tartibda qaytadi (eng birinchi so'ragan birinchi).
- Bitta o'quvchi bir vaqtda **faqat bitta** faol so'rovga ega bo'ladi — qayta-qayta bossa ham navbatga dublikat qo'shilmaydi.
- So'rov faqat ikki holatda navbatdan chiqadi: **ruxsat berilsa** (`grant-mic`, mikrofon yoqiladi) yoki **rad etilsa** (`deny-mic`, mikrofon berilmaydi, LiveKit'ga umuman murojaat qilinmaydi). Ikkalasidan birontasi bo'lgach, o'quvchi yana yangi so'rov yubora oladi.

## Qanday ishlaydi

1. O'quvchi "Mikrofon so'rash" tugmasini bosadi → `POST /live/request-mic/`.
2. O'qituvchi ekraniga **darhol** (real-time) signal keladi — yangi WebSocket
   ulanish ochish shart emas, dars davomida allaqachon ochiq bo'lgan **doska**
   kanali orqali keladi:
   ```
   wss://<domain>/ws/board/<lesson_id>/?token=<JWT>
   ```
   ```json
   { "type": "mic_request", "student_id": "uuid", "name": "Alisher" }
   ```
   (Frontend faqat `is_teacher=true` bo'lganda shu eventni ko'rsatishi kerak.)

   **Muhim (tuzatildi)**: so'rov bazada ham saqlanadi, faqat WS xabari emas —
   shuning uchun o'qituvchi so'rovdan **keyin** kirsa yoki sahifani yangilasa
   ham, joriy kutayotgan so'rovlar yo'qolib qolmaydi. `GET /api/v1/board/{lesson_id}/`
   javobiga (o'qituvchi uchun, `away_students` bilan bir qatorda) yangi maydon
   qo'shildi:
   ```json
   "pending_mic_requests": [{"student_id": "uuid", "name": "Alisher"}]
   ```
   Frontend doska sahifasini ochganda/yangilaganda shu maydondan boshlang'ich
   ro'yxatni oling, keyin WS `mic_request`/`mic_granted`/`mic_denied` orqali
   jonli yangilang. Ro'yxat FIFO tartibida keladi — birinchi so'ragan birinchi.
3. O'qituvchi ikki xil javob bera oladi:
   - **Ruxsat berish** → `POST /live/grant-mic/` → hammaga `{"type": "mic_granted", "student_id": "uuid"}`.
   - **Rad etish** → `POST /live/deny-mic/` → hammaga `{"type": "mic_denied", "student_id": "uuid"}` (mikrofon berilmaydi, so'rov shunchaki navbatdan olib tashlanadi — o'quvchi xohlasa yana so'ray oladi).
4. Ikkala holatda ham:
   - Agar `student_id` **o'zingizniki** bo'lsa (o'quvchining o'zi) → `mic_granted`da mikrofon tugmasini yoqing, `mic_denied`da "so'rash" tugmasini qayta faollashtiring.
   - Agar siz **o'qituvchi** bo'lsangiz → shu o'quvchini "kutayotganlar"
     ro'yxatidan olib tashlang (server tomonida ham bazadagi so'rov yozuvi
     avtomatik o'chiriladi — keyingi `GET /board/` chaqiruvida ham qaytmaydi).

## Xato holatlari

- `grant-mic`/`deny-mic`ni darsning egasi bo'lmagan o'qituvchi chaqirsa → `403`
- `deny-mic`ni hech qanday faol so'rov yo'q o'quvchi uchun chaqirsa → `200 {"denied": false}` (xato emas, shunchaki hech narsa o'zgarmadi)
- `student_id` topilmasa → `404`
- `request-mic`ni kursga yozilmagan foydalanuvchi chaqirsa → `403`

## Muhim eslatma

Bu — **butun platformadagi barcha darslar uchun standart xatti-harakatni
o'zgartiradi**: bu deploy qilingandan keyin barcha o'quvchilar darsga
mikrofonsiz kira boshlaydi. Agar frontendda "so'rash" tugmasi hali qo'shilmagan
bo'lsa, o'quvchilar mikrofon ishlamayotganini ko'radi — shuning uchun bu ikki
endpoint frontend jamoasiga **tezroq** yetkazilishi kerak.

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
   ro'yxatni oling, keyin WS `mic_request`/`mic_granted` orqali jonli yangilang.
3. O'qituvchi "Ruxsat berish" tugmasini bosadi → `POST /live/grant-mic/`.
4. Shu zahoti ikkala tomonga ham xuddi shu doska kanali orqali signal keladi:
   ```json
   { "type": "mic_granted", "student_id": "uuid" }
   ```
   - Agar `student_id` **o'zingizniki** bo'lsa (o'quvchining o'zi) → mikrofon
     tugmasini yoqing (LiveKit SDK darajasida endi haqiqatan gapira oladi).
   - Agar siz **o'qituvchi** bo'lsangiz → shu o'quvchini "kutayotganlar"
     ro'yxatidan olib tashlang (server tomonida ham bazadagi so'rov yozuvi
     avtomatik o'chiriladi — keyingi `GET /board/` chaqiruvida ham qaytmaydi).

## Xato holatlari

- `grant-mic`ni darsning egasi bo'lmagan o'qituvchi chaqirsa → `403`
- `student_id` topilmasa → `404`
- `request-mic`ni kursga yozilmagan foydalanuvchi chaqirsa → `403`

## Muhim eslatma

Bu — **butun platformadagi barcha darslar uchun standart xatti-harakatni
o'zgartiradi**: bu deploy qilingandan keyin barcha o'quvchilar darsga
mikrofonsiz kira boshlaydi. Agar frontendda "so'rash" tugmasi hali qo'shilmagan
bo'lsa, o'quvchilar mikrofon ishlamayotganini ko'radi — shuning uchun bu ikki
endpoint frontend jamoasiga **tezroq** yetkazilishi kerak.

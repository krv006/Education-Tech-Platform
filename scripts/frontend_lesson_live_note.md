# "Dars ketmoqda" banneri — real-vaqtda yangilanmayapti (frontend fix kerak)

## Muammo
Chat sahifasida (`/teacher/chats/{room_id}`) dars boshlanganda "Dars ketmoqda"
banneri faqat sahifani **yangilagandan keyin** (REST so'rovdan) chiqadi.
WebSocket orqali kelayotgan signal frontendda **qabul qilinmayapti/UI
yangilanmayapti**. Backend tomonida signal to'g'ri ishlab turgani
tasdiqlangan (server loglari va kodga qarab tekshirildi).

## WebSocket ulanish
```
wss://<domain>/ws/chat/<room_id>/?token=<JWT access>
```
`room_id` — shu kurs uchun `ChatRoom.id` (masalan chat ro'yxatidagi
`fecc4afb-313a-4cd1-879c-7c7808e695fc`).

## Kelayotgan xabar turlari (qo'shimcha ravishda ishlov berish kerak)

### 1) `lesson_live` — dars boshlandi
```json
{"type": "lesson_live", "lesson": {"id": "...", "title": "matem", "room_name": "lesson-abc123"}}
```
**Qachon keladi:**
- O'qituvchi darsni birinchi marta boshlaganda (bir marta, guruh WS kanaliga)
- **YANGI**: WebSocket ulanishi o'rnatilgan zahoti, agar shu kursda hozir
  LIVE dars bo'lsa — darhol (backend'ga bugun qo'shildi, deploy qilindi)

**Frontend qilishi kerak:** shu xabar kelganda, chat/kurs holatidagi
`live_lesson` maydonini `message.lesson` qiymatiga o'rnatish va bannerni
ko'rsatish (xuddi REST javobidagi `live_lesson` maydoni bilan bir xil shakl
— pastga qarang).

### 2) `lesson_ended` — dars tugadi
```json
{"type": "lesson_ended", "lesson_id": "..."}
```
**Qachon keladi:** o'qituvchi darsni yakunlaganda (`finish_lesson`).

**Frontend qilishi kerak:** `live_lesson` maydonini `null` qilib, bannerni
yashirish.

## REST bilan mos kelishi (referens uchun)
`GET /api/v1/chat/rooms/` javobidagi har bir xona obyektida **xuddi shu
shakldagi** maydon bor:
```json
{"id": "...", "kind": "course", ..., "live_lesson": {"id": "...", "title": "...", "room_name": "..."} | null}
```
(`apps/chat/serializers.py` — `ChatRoomSerializer.get_live_lesson`)

Ya'ni WS orqali kelgan `lesson_live`/`lesson_ended` xabarlari — xuddi shu
`live_lesson` state'ni real-vaqtda yangilashi kerak, REST bilan bir xil
formatda. Agar hozircha frontendda bu WS xabar turlariga umuman `case`/handler
yo'q bo'lsa — aynan shu yetishmayotgan qism.

## Tekshirish
1. Ikki bo'lim ochib (bittasi o'qituvchi, bittasi darsni boshlaydigan joy)
2. Chat sahifasini ochiq qoldiring (WS ulangan holda)
3. Darsni boshlang
4. Chat sahifasi **sahifani yangilamasdan** "Dars ketmoqda" bannerini
   ko'rsatishi kerak

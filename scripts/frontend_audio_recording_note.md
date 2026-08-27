# Dars audio yozuvi — o'qituvchi brauzerida (frontend fix kerak)

## Nima uchun

Server CPU'sini tejash uchun (5-10+ parallel dars uchun): video serverda
arzon usulda (Track Egress) yoziladi, **audio esa endi o'qituvchi
brauzerida** yoziladi va bo'lak-bo'lak serverga yuklanadi. Backend qismi
tayyor va test qilingan.

## Frontend qilishi kerak bo'lgan ish

### 1) Barcha ovozlarni ichkarida aralashtirish (Web Audio API)

O'qituvchi darsga kirganda, LiveKit SDK orqali kelayotgan har bir
ishtirokchining audio `MediaStreamTrack`ini `AudioContext` +
`MediaStreamAudioDestinationNode`ga ulab, bitta aralashgan audio oqim hosil
qilish kerak (ekran/tab-share, maxsus ruxsat SHART EMAS — bu ichki, sahifa
darajasidagi mixing).

### 2) Yozib olish (MediaRecorder)

Shu aralashgan oqimni `MediaRecorder` bilan yozib olish (tavsiya:
`audio/webm;codecs=opus`). `ondataavailable`ni har **30-60 soniyada**
ishga tushirish (`recorder.start(30000)` yoki shunga o'xshash).

### 3) Boshlanish vaqtini eslab qolish

`MediaRecorder.start()` chaqirilgan **aniq vaqtni** (`new
Date().toISOString()`) saqlab qo'ying — birinchi chunk bilan birga
yuboriladi (server buni video bilan sinxronlash uchun ishlatadi).

### 4) Har bir bo'lakni serverga yuklash

```
POST /api/v1/lessons/{lesson_id}/recording/audio/
Content-Type: multipart/form-data

chunk: <Blob>              # majburiy
started_at: <ISO datetime> # faqat BIRINCHI so'rovda kerak (keyingilarida
                            # e'tiborga olinmaydi, yubormasa ham bo'ladi)
```
Javob: `204 No Content` (muvaffaqiyat), `400` (xato — masalan bo'lak 10MB
dan katta), `403` (faqat kurs o'qituvchisi yuklay oladi).

**Muhim — ishonchlilik:** bo'lak serverga **muvaffaqiyatli** (204)
yuklangandan keyin, brauzer xotirasidagi o'sha qismni o'chirib tashlang.
Agar so'rov muvaffaqiyatsiz bo'lsa (tarmoq xatosi) — qayta urinib ko'ring,
xotiradan o'chirmang. Shunda brauzer to'satdan yopilib qolsa ham, faqat
yuborilmagan oxirgi bo'lak yo'qoladi, hammasi emas.

### 5) Dars tugaganda — yakunlash

O'qituvchi darsni tugatgach (`finish` tugmasi bosilgach), `MediaRecorder`ni
to'xtatib, **oxirgi bo'lakni yuklab bo'lgach**, quyidagini chaqiring:

```
POST /api/v1/lessons/{lesson_id}/recording/audio/finalize/
```
Javob: `204` (video ham tayyor bo'lsa — server fonda birlashtirish
boshlaydi), `400` (agar umuman audio yuklanmagan bo'lsa).

## Diqqat qiling

- Agar `finalize` chaqirilmasa (masalan brauzer yopilib qolsa) — backend
  2 daqiqadan keyin **video-only** (ovozsiz) yozuvni avtomatik yakunlaydi,
  butun yozuv yo'qolmaydi, faqat audio bo'lmaydi.
- Yakuniy (birlashtirilgan) video+audio fayl `GET
  /api/v1/lessons/{id}/recording/` orqali odatdagidek olinadi — status
  `merging` bo'lsa hali tayyor emas, biroz kutib qayta so'rang (poll).
- Fayl formati (webm/opus) frontend tanlovi bilan mos kelishi kerak —
  agar boshqa format ishlatilsa (masalan mp4/aac), backend hozircha shuni
  ham xom holda saqlaydi va `-c:a aac`ga aylantiradi, ko'pchilik format
  ishlashi kerak, lekin **webm/opus tavsiya etiladi** (test qilingan).

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

### 2) Yozib olish (MediaRecorder) — MUHIM: BITTA uzluksiz sessiya

Shu aralashgan oqimni **BITTA** `MediaRecorder` obyekti bilan yozib
oling (tavsiya: `audio/webm;codecs=opus`), va uni **faqat bir marta**
ishga tushiring — `recorder.start(30000)` (30000ms = har 30 soniyada
`ondataavailable` o'zi bo'lak beradi):

```js
const recorder = new MediaRecorder(mixedStream, { mimeType: 'audio/webm;codecs=opus' });
recorder.ondataavailable = (e) => uploadChunk(e.data);
recorder.start(30000);  // BITTA marta chaqiriladi, dars oxirigacha
```

**QATTIQ TAQIQLANADI:** har bo'lak uchun **alohida-alohida**
`new MediaRecorder(...).start()` + `.stop()` chaqirish (masalan har
30 soniyada yangi recorder yaratib, eskisini to'xtatish). Bu yondashuv
bo'laklar orasida kichik **vaqt bo'shliqlari** hosil qiladi — server bu
bo'shliqni bila olmaydi, natijada video bilan audio orasidagi farq **dars
davomida asta-sekin kattalashib boradi** (lablar bilan ovoz mos
kelmaydigan bo'lib qoladi). Bu — aynan production'da 2026-08-28'da
uchragan, tasdiqlangan xato: bitta `MediaRecorder` sessiyasining
**ichidagi** `ondataavailable` bo'laklari esa bir xil uzluksiz oqimning
qismlari bo'lgani uchun bunday muammo umuman bo'lmaydi.

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
- Fayl formati **webm/opus BO'LISHI SHART** (`audio/webm;codecs=opus`) —
  backend endi buni qayta kodlamasdan to'g'ridan-to'g'ri video bilan
  bitta WebM faylga birlashtiradi (video ham VP8/WebM, brauzer kamerasi
  shu formatda kodlagani uchun — MP4 konteyner VP8'ni umuman qo'llab-
  quvvatlamaydi, shu sabab boshqa format ishlamaydi).

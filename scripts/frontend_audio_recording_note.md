# Dars video+audio yozuvi — o'qituvchi brauzerida (frontend fix kerak)

## Nima uchun (2026-08-28 yangilanish: video ham endi shu yerda)

Server CPU'sini tejash uchun: **video HAM, audio HAM** endi to'liq
o'qituvchi brauzerida yoziladi va bo'lak-bo'lak serverga yuklanadi.
Serverda endi LiveKit Egress ISHLATILMAYDI — bu qism butunlay olib
tashlandi.

**Video nega brauzerdan:** avval serverda (Track Egress) faqat
o'qituvchining KAMERA yoki EKRAN trackidan bittasini tanlab yozar edik —
bu noqulay edi (qay birini tanlash, dars davomida almashtirish
qo'llab-quvvatlanmasdi). Endi o'qituvchining **butun ekrani**
(`getDisplayMedia` — "print screen" kabi, LiveKit sahifasining o'zi)
yoziladi — kim gapirsa, kim ekran ulashsa, kim kamerasini yoqsa, HAMMASI
tabiiy ko'rinadi, tanlov mantig'i kerak emas.

Backend qismi tayyor va test qilingan (76 test).

## Frontend qilishi kerak bo'lgan ish

### 1) AUDIO — barcha ovozlarni ichkarida aralashtirish (Web Audio API)

O'qituvchi darsga kirganda, LiveKit SDK orqali kelayotgan har bir
ishtirokchining audio `MediaStreamTrack`ini `AudioContext` +
`MediaStreamAudioDestinationNode`ga ulab, bitta aralashgan audio oqim
hosil qilish kerak (maxsus ruxsat SHART EMAS — bu ichki, sahifa
darajasidagi mixing).

### 2) VIDEO — o'qituvchi ekranini yozib olish (`getDisplayMedia`)

```js
const screenStream = await navigator.mediaDevices.getDisplayMedia({
  video: { frameRate: 15 },  // 30fps shart emas, 15fps ancha arzon fayl beradi
  audio: false,  // audio alohida, Web Audio orqali (1-band)
});
```

Brauzer albatta ruxsat so'raydi ("shu sahifani/oynani ulashishga ruxsat
berasizmi?") — o'qituvchi buni **darsni boshlashda bir marta** bosadi.
Eng yaxshisi — shu tanlovni **"joriy tab"** (Chrome'da "This Tab") qilib
tavsiya qiling, shunda LiveKit sahifasining o'zi yoziladi.

### 3) Yozib olish (MediaRecorder) — MUHIM: BITTA uzluksiz sessiya

Video va audio uchun **alohida-alohida**, lekin har biri **BITTA**
`MediaRecorder` obyekti bilan (tavsiya: `video/webm;codecs=vp8`,
`audio/webm;codecs=opus`), **faqat bir marta** ishga tushiring:

```js
const videoRecorder = new MediaRecorder(screenStream, { mimeType: 'video/webm;codecs=vp8' });
videoRecorder.ondataavailable = (e) => uploadVideoChunk(e.data);
videoRecorder.start(30000);  // BITTA marta, dars oxirigacha

const audioRecorder = new MediaRecorder(mixedAudioStream, { mimeType: 'audio/webm;codecs=opus' });
audioRecorder.ondataavailable = (e) => uploadAudioChunk(e.data);
audioRecorder.start(30000);  // BITTA marta, dars oxirigacha
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

### 4) Boshlanish vaqtini eslab qolish

Har ikkala recorder uchun `.start()` chaqirilgan **aniq vaqtni** (`new
Date().toISOString()`) saqlab qo'ying — birinchi chunk bilan birga
yuboriladi (server video va audioni sinxronlash uchun ishlatadi).

### 5) Har bir bo'lakni serverga yuklash

**Video:**
```
POST /api/v1/lessons/{lesson_id}/recording/video/
Content-Type: multipart/form-data

chunk: <Blob>              # majburiy
started_at: <ISO datetime> # faqat BIRINCHI so'rovda kerak
```

**Audio:**
```
POST /api/v1/lessons/{lesson_id}/recording/audio/
Content-Type: multipart/form-data

chunk: <Blob>              # majburiy
started_at: <ISO datetime> # faqat BIRINCHI so'rovda kerak
```

Ikkalasi ham bir xil javob beradi: `204 No Content` (muvaffaqiyat), `400`
(xato — video 50MB, audio 10MB dan katta bo'lsa), `403` (faqat kurs
o'qituvchisi yuklay oladi).

**Muhim — ishonchlilik:** bo'lak serverga **muvaffaqiyatli** (204)
yuklangandan keyin, brauzer xotirasidagi o'sha qismni o'chirib tashlang.
Agar so'rov muvaffaqiyatsiz bo'lsa (tarmoq xatosi) — qayta urinib ko'ring,
xotiradan o'chirmang. Shunda brauzer to'satdan yopilib qolsa ham, faqat
yuborilmagan oxirgi bo'lak yo'qoladi, hammasi emas.

### 6) Dars tugaganda — yakunlash

O'qituvchi darsni tugatgach (`finish` tugmasi bosilgach), **ikkala**
`MediaRecorder`ni to'xtatib, oxirgi bo'laklarni yuklab bo'lgach, ikkala
`finalize`ni ham chaqiring (tartib muhim emas):

```
POST /api/v1/lessons/{lesson_id}/recording/video/finalize/
POST /api/v1/lessons/{lesson_id}/recording/audio/finalize/
```

Javob: `204` (ikkalasi ham tayyor bo'lsa — server fonda birlashtirish
boshlaydi), `400` (agar shu turdagi fayl umuman yuklanmagan bo'lsa).

## Diqqat qiling

- Agar `finalize`lardan **faqat bittasi** chaqirilsa (masalan brauzer
  yopilib qolsa, yoki o'qituvchi ekran ulashishga ruxsat bermasa) —
  backend 2 daqiqadan keyin **mavjud bo'lgan tomon bilan** (video-only
  YOKI audio-only) avtomatik yakunlaydi, hech narsa butunlay yo'qolmaydi.
- Guruh chatga "yozuv tayyor!" e'loni endi **darsni tugatgan zahoti
  EMAS** — video+audio haqiqatan birlashtirilib bo'lgach (fon jarayonida,
  bir necha soniyadan keyin) yuboriladi.
- Yakuniy (birlashtirilgan) fayl `GET /api/v1/lessons/{id}/recording/`
  orqali odatdagidek olinadi — status `merging` bo'lsa hali tayyor emas,
  biroz kutib qayta so'rang (poll).
- Fayl formati **webm BO'LISHI SHART** (video: `video/webm;codecs=vp8`,
  audio: `audio/webm;codecs=opus`) — backend ularni qayta kodlamasdan
  bitta WebM faylga birlashtiradi (MP4 konteyner VP8'ni qo'llab-
  quvvatlamaydi, shu sabab boshqa format ishlamaydi).

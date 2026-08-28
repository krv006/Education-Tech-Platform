# Dars video yozuvi — CPU optimallashtirish (2026-08-27)

Bu hujjat bugun qilingan ishlarni, topilgan muammolarni va yechimlarni
tartib bilan tushuntiradi — jamoa a'zolari (jumladan frontend) uchun.

## 1. Muammo va maqsad

Platforma 50 o'qituvchi / 5000 talabagacha o'sishi kutilmoqda, beta
boshlanishida esa **~10 ta dars bir vaqtda parallel** bo'lishi kutilmoqda
(kelajakda 100 tagacha). Serverimiz — **6 CPU yadroli** Contabo VPS.
Muammo: dars video yozuvi (LiveKit Egress) juda ko'p CPU yer edi — bir
nechta dars parallel yozilsa, server tiqilib qolish xavfi bor edi.

## 2. Ildiz sababi topish

Production kodda ([apps/live/services.py](../apps/live/services.py))
`RoomCompositeEgress` ishlatilgan — bu usul serverda **headless Chrome**
brauzerini ishga tushirib, xonadagi barcha video/audio oqimlarini bitta
veb-sahifada render qilib, keyin YANGIDAN videoga kodlaydi.

**Git tarixini tekshirib**, bu muammo bilan ikki marta (turli
muhandislar tomonidan) kurashilganini aniqladik:
- `0cb52fb` — 720p preset (CPU ~2x kam, deb yozilgan)
- `d68bbf1` — 480p/15fps ga pasaytirish

**Ikkalasi ham yordam bermagan**, chunki ular rezolyutsiyani
kamaytirgan — lekin muammo rezolyutsiyada emas edi. `RoomCompositeEgress`
turining o'zi (LiveKit'ning ichki xususiyati) — rezolyutsiyadan qat'i
nazar — kamida **~4 CPU yadrosini** talab qiladi, chunki asosiy og'irlik
Chrome'ning render qilishida, video hajmida emas.

## 3. Real yuklama testlari (ishonchli natija uchun)

Production LiveKit serverida haqiqiy sinovlar o'tkazildi (soxta
o'qituvchi+o'quvchilar, `lk` CLI orqali), bosqichma-bosqich kattalashtirib:
1 → 2 → 4 → 5 → 7 ta xona, har birida ~20 kishigacha (5 tasi faol
kamera/mikrofon bilan).

**Muhim metodologik tuzatish:** dastlabki testda `screen_share=True`
bayrog'i xato o'rnatilgan bo'lib, bu kamera trackini "e'tiborsiz
qoldirilgan" holatga keltirgan va sun'iy past (13-77%) natija bergan.
Tuzatilgach, haqiqiy narx (~150-260% bitta faol yozuv uchun) ma'lum bo'ldi.

### Topilgan yechim: Track Egress + audio_only

- **Video** — `TrackEgress`: o'qituvchi kamera trackini **xom nusxa
  ko'chiradi** (Chrome render, qayta kodlash YO'Q) → **~17-20% CPU**
- **Audio** — `RoomCompositeEgress(audio_only=True)`: video render
  yo'qligi uchun ancha arzon (faqat audio decode+mix) → **~25-30% CPU**
- **Jami: ~45-50% CPU/dars** (eskisidan ~5-7 barobar arzon)

5 xonalik (105 kishi) real testda tasdiqlangan: o'rtacha **224.97% / 5 =
44.99% xona boshiga**.

## 4. Yo'lda topilgan 2 ta real production xato (tuzatilgan va deploy qilingan)

### a) UDP port yetishmasligi
`docker-compose.prod.yml` va `livekit.prod.yaml`da WebRTC media uchun
faqat **100 ta port** (`50000-50100`) ochilgan edi — ko'p ishtirokchili
testda "could not connect after timeout" xatolari kelib chiqdi. **1000
portgacha** (`50000-51000`) kengaytirildi, firewall (`ufw`) yangilandi.
Tekshirildi: 147 ishtirokchi, 7 xona, xatosiz ulandi. ✅ Deploy qilingan.

### b) Egress boshlashda 503 xatosi (control-plane band bo'lib qolishi)
Bir nechta yozuvni **tez-tez ketma-ket** boshlashga urinilganda, ba'zan
`ServerError(no response from servers, status=503)` xatosi chiqar edi.
Sabab: egress xizmati allaqachon 8-9 ta ishni boshqarayotganda, YANGI
ishni boshlash so'rovi vaqtida javob berolmay qolar edi (timeout) — bu
CPU yetishmovchiligi EMAS, balki **vaqt/navbat** muammosi edi.

**Yechim:** har bir xonaning yozuvini boshlashdan keyin 2-3 soniya kutish
(pauza). Qayta test qilindi — 5 ta xona, 10 ta ish (5 video + 5 audio),
**hech qanday 503 xatosiz**. ✅ Yondashuv tasdiqlangan.

## 5. Keyingi qadam — audio ham brauzerga (server CPU'sini yanada tushirish)

45-50% ham yaxshi, lekin 10-100 parallel darsga chidash uchun yanada
arzonroq kerak. G'oya (sherigimning taklifi): **audio_only RoomComposite
o'rniga, o'qituvchi brauzerining o'zi** barcha ishtirokchilar ovozini
(Web Audio API orqali) ichkarida aralashtirib, yozib olib, serverga
**bo'lak-bo'lak (chunked) yuklasin**.

Bu server CPU'sini audio uchun deyarli **0%**ga tushiradi — server faqat
kichik fayl bo'laklarini diskka yozadi (og'ir emas, hatto 100 dars
parallel bo'lsa ham).

### Ishonchlilik uchun qo'shilgan himoya choralari
- **Bo'lak-bo'lak yuklash** (30-60s), butun darsni oxirida emas —
  brauzer qulasa faqat oxirgi bo'lak yo'qoladi
- **Vaqt farqiga moslab birlashtirish** — video va audio turli vaqtda
  boshlangan bo'lsa ham (`ffmpeg -itsoffset`), to'g'ri sinxronlanadi
- **Video-only fallback** — agar audio HECH QACHON kelmasa (brauzer
  qulab qolsa), 2 daqiqadan keyin faqat video bilan (ovozsiz) yakunlanadi
  — butun yozuv yo'qolib ketmaydi

### Amalga oshirilgan backend ishi — ✅ 2026-08-28 kuni production'ga
### joylashtirildi

- `LessonRecording` modeliga yangi maydonlar (`video_file_name`,
  `audio_file_name`, vaqt belgilari, `MERGING` holati)
- Video Track Egress'ga to'liq o'tkazildi (`apps/live/services.py`) —
  eski `RoomCompositeEgress` endi ishlatilmaydi
- Yangi endpoint'lar (production'da faol):
  - `POST /api/v1/lessons/{id}/recording/audio/` — audio bo'lagi yuklash
  - `POST /api/v1/lessons/{id}/recording/audio/finalize/` — yakunlash
- `ffmpeg` bilan avtomatik birlashtirish (fon jarayonida)
- Dockerfile'ga `ffmpeg` qo'shildi va serverda o'rnatildi (v7.1.5)
- **12 ta yangi test** (haqiqiy ffmpeg bilan birlashtirish ham tekshirilgan)

**Hozirgi cheklov:** frontend hali Web Audio mixing + chunked upload
qismini yozmagan — shuning uchun yangi darslar **video bilan, lekin
OVOZSIZ** yoziladi, frontend o'z qismini tugatgunicha. Backend API tayyor
turibdi, frontend shu ustida ishlashi mumkin. Texnik hujjat:
[`frontend_audio_recording_note.md`](frontend_audio_recording_note.md).

## 6. Deploy paytida topilgan real production xato (2026-08-28)

Birinchi haqiqiy darsda (`test 11.02`) yozuv abadiy "yozilmoqda" holatida
qolib ketdi. Sabab: **LiveKit Track Egress biz so'ragan `.mp4`
kengaytmasini e'tiborsiz qoldirib**, trackning haqiqiy kodekiga mos
(masalan VP8 uchun) `.webm` konteynerda yozgan — bu hujjatlashtirilmagan
xatti-harakat. Bazada `video_file_name` sifatida `...mp4` saqlanib
qolgan, diskda esa `...webm` fayl bo'lgani uchun tizim faylni topa
olmagan.

**Video yo'qolmagan edi** — fayl diskda sog'lom turgan, faqat baza yozuvi
noto'g'ri nom bilan edi. Qo'lda tuzatildi, keyin **kodga doimiy yechim**
qo'shildi: `_resolve_video_file()` — agar bazadagi nom bilan fayl
topilmasa, diskdan bir xil baza nomli faylni avtomatik qidirib topadi.
Bu endi `stop_recording`, `finalize_video_only` va `_merge_recording`ning
barchasida ishlaydi. Butun platforma tekshirildi — boshqa ta'sirlangan
dars topilmadi.

## 7. Hozirgi holat — xulosa jadvali

| Nima | Holat |
|---|---|
| UDP port kengaytirish | ✅ Production'da ishlamoqda |
| 503 xato uchun pauza yechimi | ✅ Production'da ishlamoqda |
| Track Egress (video, arzon) | ✅ Production'da ishlamoqda (~0.17-0.2 CPU/dars) |
| Track Egress kengaytma xatosi | ✅ Tuzatilgan va deploy qilingan |
| Audio — brauzerda yozish (backend) | ✅ API production'da tayyor; **frontend ishi kutilmoqda** |
| Audio — brauzerda yozish (frontend) | ⏳ Hali boshlanmagan |
| Lesson-live WebSocket sinxronizatsiya | ✅ Production'da ishlamoqda |

## 8. Keyingi qadamlar

1. Frontend jamoasi audio yozish qismini yozadi (hujjat tayyor, backend
   API allaqachon ishlaydi — sinab ko'rish mumkin)
2. Frontend tugagach, kichik miqyosda (1-2 xona) birga sinaladi
3. Audio ham ishga tushgach — haqiqiy CPU narxini (maqsad: ~0.1-0.2/dars)
   real darsda o'lchab tasdiqlaymiz
4. (Kelajakda, muhokama qilindi lekin hali qaror qilinmagan) — videoni
   ham to'liq brauzerga o'tkazish g'oyasi, server CPU'sini yanada
   (deyarli 0'ga) tushirish uchun — bunda ishonchlilik-arzonlik
   muvozanati alohida ko'rib chiqilishi kerak.

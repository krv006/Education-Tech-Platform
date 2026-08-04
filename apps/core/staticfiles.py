"""Static fayllar storage — prod (WhiteNoise manifest) uchun kechirimli variant.

Muammo: ba'zi kutubxonalar (masalan Jazzmin base.html'da
`{% static 'vendor/bootswatch' %}` — PAPKA!) manifest'da bo'lmagan yo'lni
so'raydi. Qat'iy ManifestStaticFilesStorage bunda ValueError otib butun
sahifani 500 qiladi. Bizning variant: topilmasa hash'siz asl nomni qaytaradi —
sahifa ishlayveradi, qolgan fayllar esa manifest hash bilan keshlanadi.
"""
from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    def stored_name(self, name):
        try:
            return super().stored_name(name)
        except ValueError:
            return name

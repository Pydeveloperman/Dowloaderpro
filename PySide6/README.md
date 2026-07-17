# 🎬 Video Yuklovchi GUI (PySide6)

YouTube, Instagram va TikTok'dan video yuklab olish uchun zamonaviy, flat-dizaynli, dark/light mavzu almashtiriladigan desktop dastur. Python + **PySide6 (Qt)** + `yt-dlp` asosida yozilgan.

## ✨ Imkoniyatlar

- 🔎 **YouTube'da qidirish** — kalit so'z bo'yicha qidirib, natijalar ro'yxatidan video tanlash
- 🔗 **URL orqali yuklash** — YouTube, Instagram yoki TikTok havolasini kiriting va yuklang
- 📃 **Pleylist yuklash** — butun pleylistni bir vaqtda yuklab olish
- 🎚 **Sifat tanlash** — video sifatini (masalan 1080p, 720p) yoki faqat audio (MP3) tanlash imkoniyati
- 📁 **Papka tanlash** — yuklamalar uchun saqlash papkasini "Papkani tanlash" tugmasi orqali belgilash
- 🌗 **Dark/Light mavzu** — bitta tugma bilan qorong'i/yorug' mavzu o'rtasida almashish
- 📊 **Progress-bar** — yuklanish jarayoni foiz va progress-bar orqali real vaqtda ko'rsatiladi
- 💾 **Sozlamalarni eslab qolish** — oxirgi tanlangan papka avtomatik saqlanadi (`~/.video_yuklovchi_sozlamalar.json`)
- 🍪 **Cookie qo'llab-quvvatlash** — YouTube "bot emasligingizni tasdiqlang" xatosiga qarshi cookie fayli/brauzer cookie'laridan foydalanish

## 🧰 Talablar

- Python 3.9+
- `PySide6` (Qt uchun Python bog'lovchisi)
- `ffmpeg` (video/audio birlashtirish va MP3'ga aylantirish uchun)
- Internet aloqasi

## 🚀 O'rnatish va ishga tushirish

Loyihani klonlab, `install.sh` skriptini ishga tushiring — u avtomatik ravishda virtual muhit (`.venv`) yaratadi, kerakli paketlarni o'rnatadi va dasturni ishga tushiradi:

```bash
git clone https://github.com/pydeveloperman/<repo-nomi>.git
cd <repo-nomi>
chmod +x install.sh
./install.sh
```

### `install.sh` nima qiladi?

1. Tizimda Python mavjudligini tekshiradi
2. `ffmpeg` mavjudligini tekshirib, yo'q bo'lsa qanday o'rnatishni ko'rsatadi
3. `.venv` nomli virtual muhitni 0'dan yaratadi
4. `pip`ni yangilaydi, `yt-dlp` va `PySide6` ni o'rnatadi
5. `panel.py` dasturini ishga tushiradi

### Qo'lda o'rnatish (agar `install.sh` ishlatilmasa)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -U yt-dlp
pip install PySide6
python panel.py
```

### `ffmpeg` yo'q bo'lsa

```bash
# Debian/Ubuntu/Kali
sudo apt install ffmpeg

# macOS (Homebrew)
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html dan yuklab, PATH'ga qo'shing
```

> **Eslatma:** YouTube 2026-yildan boshlab ba'zi formatlarni ochish uchun JavaScript-challenge (EJS) yechilishini talab qiladi. Bu uchun kompyuterda JS runtime (masalan, [Deno](https://deno.land/)) o'rnatilgan bo'lishi tavsiya etiladi:
> ```bash
> curl -fsSL https://deno.land/install.sh | sh
> ```

## 📖 Foydalanish

```bash
python panel.py
```

Dastur ochilgach uchta bo'lim mavjud:

1. **Qidirish** — kalit so'z kiritib YouTube'da qidiring, natijalar orasidan videoni tanlang
2. **URL** — video havolasini kiritib, "Formatlarni olish" tugmasini bosing, sifatni tanlang va yuklang
3. **Pleylist** — pleylist havolasini kiritib, sifatni belgilab, to'liq yuklab oling

Yuqori qismdagi tugma orqali dark/light mavzu o'rtasida istalgan vaqtda almashishingiz mumkin.

## 📂 Loyiha tuzilishi

```
.
├── panel.py       # Asosiy dastur (PySide6/Qt GUI)
├── install.sh     # Venv yaratib, o'rnatib, ishga tushiradigan skript
└── README.md
```

## ⚠️ Muhim eslatma

Bu dastur faqat sizga tegishli yoki ruxsat berilgan kontentni yuklab olish uchun mo'ljallangan. Mualliflik huquqi bilan himoyalangan materiallarni ruxsatsiz yuklab olish tegishli platformalarning foydalanish shartlariga zid bo'lishi mumkin.

## 📜 Litsenziya

MIT

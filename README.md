# 🎬 Video Yuklovchi GUI

YouTube, Instagram va TikTok'dan video yuklab olish uchun zamonaviy, flat-dizaynli, dark/light mavzu almashtiriladigan desktop dastur. Python va [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) asosida yozilgan.

Ushbu repo bir xil dasturning **ikkita GUI versiyasini** o'z ichiga oladi — xohlagan birini tanlab ishlatishingiz mumkin:

| Papka | GUI kutubxonasi | Tavsiya |
|---|---|---|
| [`Tkinter/`](./Tkinter) | Python bilan birga keladigan `tkinter` | Yengil, qo'shimcha o'rnatishlarsiz tezroq ishga tushadi |
| [`PySide6/`](./PySide6) | `PySide6` (Qt) | Zamonaviyroq ko'rinish, biroz og'irroq o'rnatish |

Ikkala versiya ham funksional jihatdan bir xil.

## ✨ Umumiy imkoniyatlar

- 🔎 **YouTube'da qidirish** — kalit so'z bo'yicha qidirib, natijalar ro'yxatidan video tanlash
- 🔗 **URL orqali yuklash** — YouTube, Instagram yoki TikTok havolasini kiriting va yuklang
- 📃 **Pleylist yuklash** — butun pleylistni bir vaqtda yuklab olish
- 🎚 **Sifat tanlash** — video sifatini (masalan 1080p, 720p) yoki faqat audio (MP3) tanlash imkoniyati
- 📁 **Papka tanlash** — yuklamalar uchun saqlash papkasini "Papkani tanlash" tugmasi orqali belgilash
- 🌗 **Dark/Light mavzu** — bitta tugma bilan qorong'i/yorug' mavzu o'rtasida almashish
- 📊 **Progress-bar** — yuklanish jarayoni foiz va progress-bar orqali real vaqtda ko'rsatiladi
- 💾 **Sozlamalarni eslab qolish** — oxirgi tanlangan papka (va Tkinter versiyada cookie fayli) avtomatik saqlanadi
- 🍪 **Cookie qo'llab-quvvatlash** — YouTube "bot emasligingizni tasdiqlang" xatosiga qarshi cookie fayli/brauzer cookie'laridan foydalanish

## 🧰 Umumiy talablar

- Python 3.9+
- `ffmpeg` (video/audio birlashtirish va MP3'ga aylantirish uchun)
- Internet aloqasi
- Tkinter versiyasi uchun: `python3-tk` (tizim paketi)
- PySide6 versiyasi uchun: `PySide6` (pip orqali, avtomatik o'rnatiladi)

### `ffmpeg` o'rnatish

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

## 🚀 Tez boshlash

Repozitoriyani klonlab, kerakli versiya papkasiga kiring va `install.sh` ni ishga tushiring — u venv yaratadi, kerakli paketlarni o'rnatadi va dasturni ishga tushiradi.

**Tkinter versiyasi:**
```bash
git clone https://github.com/pydeveloperman/<repo-nomi>.git
cd <repo-nomi>/Tkinter
chmod +x install.sh
./install.sh
```

**PySide6 versiyasi:**
```bash
git clone https://github.com/pydeveloperman/<repo-nomi>.git
cd <repo-nomi>/PySide6
chmod +x install.sh
./install.sh
```

Har bir papka ichidagi `README.md` faylida shu versiyaga xos batafsil yo'riqnoma mavjud.

## 📂 Repo tuzilishi

```
.
├── Tkinter/
│   ├── panel.py       # Tkinter GUI versiyasi
│   ├── install.sh     # Venv yaratib, o'rnatib, ishga tushiradigan skript
│   └── README.md
├── PySide6/
│   ├── panel.py       # PySide6 (Qt) GUI versiyasi
│   ├── install.sh     # Venv yaratib, o'rnatib, ishga tushiradigan skript
│   └── README.md
└── README.md          # Shu fayl
```

## ⚠️ Muhim eslatma

Bu dastur faqat sizga tegishli yoki ruxsat berilgan kontentni yuklab olish uchun mo'ljallangan. Mualliflik huquqi bilan himoyalangan materiallarni ruxsatsiz yuklab olish tegishli platformalarning foydalanish shartlariga zid bo'lishi mumkin.

## 📜 Litsenziya

MIT

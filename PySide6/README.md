# 🎬 Video Yuklovchi — YouTube / Instagram / TikTok

PySide6 (Qt) asosida yozilgan, zamonaviy va flat-dizaynli video yuklab olish dasturi. `yt-dlp` kutubxonasidan foydalanadi va quyidagilarni qo'llab-quvvatlaydi:

- 🔍 YouTube'da to'g'ridan-to'g'ri qidirish va natijadan video tanlash
- 🔗 Istalgan platformadan (YouTube / Instagram / TikTok) havola orqali yuklash
- 📋 Pleylistni to'liq yuklash
- 🎚️ Video sifatini tanlash yoki faqat audio (MP3) qilib olish
- 🌙 Dark / Light mavzu almashtirish
- 💾 Oxirgi tanlangan papka va cookie sozlamalari eslab qolinadi

---

## 📋 Talablar

| Dastur | Versiya | Nima uchun kerak |
|---|---|---|
| Python | 3.9+ | Asosiy dastur tili |
| PySide6 | so'nggi | Grafik interfeys (Qt) |
| yt-dlp | so'nggi | Video/audio yuklab olish |
| ffmpeg | so'nggi | Video+audio birlashtirish, MP3'ga aylantirish |
| Deno | 2.0+ | YouTube'ning JavaScript challenge'larini yechish (2026-yildan majburiy) |

---

## ⚙️ O'rnatish

### 1) Python paketlarini o'rnatish

```bash
pip install -U "yt-dlp[default]" --break-system-packages
pip install PySide6 --break-system-packages
```

> **Eslatma:** Kali/Debian/Ubuntu'da tizim Python'i "externally managed" bo'lgani uchun `--break-system-packages` flagi kerak bo'lishi mumkin. Virtual muhit (`venv`) ishlatsangiz, bu flag shart emas:
> ```bash
> python3 -m venv env
> source env/bin/activate
> pip install -U "yt-dlp[default]" PySide6
> ```

### 2) ffmpeg o'rnatish

```bash
# Linux (Debian/Ubuntu/Kali)
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# https://ffmpeg.org/download.html dan yuklab, PATH'ga qo'shing
```

### 3) Deno o'rnatish (YouTube JS-challenge yechuvchisi)

YouTube 2026-yildan boshlab ba'zi video/audio formatlarni "ochish" uchun JavaScript kodini bajarishni talab qiladi. Buning uchun **Deno** eng qulay va tavsiya etiladigan yechim:

```bash
curl -fsSL https://deno.land/install.sh | sh
echo 'export PATH="$HOME/.deno/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

O'rnatilganini tekshiring:
```bash
deno --version
```

> Deno o'rniga Node.js, Bun yoki QuickJS'dan ham foydalanish mumkin — batafsil: [yt-dlp EJS qo'llanmasi](https://github.com/yt-dlp/yt-dlp/wiki/EJS).

---

## ▶️ Ishga tushirish

```bash
python Panel.py
```

Oyna ochilgach, uchta tabdan birini tanlang:

1. **🔍 YouTube'da qidirish** — so'z kiriting, natijalar ro'yxatidan videoni tanlang.
2. **🔗 Havola orqali yuklash** — video havolasini kiritib, "Formatlarni olish" tugmasini bosing, so'ng kerakli sifatni tanlang.
3. **📋 Pleylist yuklash** — pleylist havolasi va sifatni kiritib, to'liq yuklab oling.

Yuklab olingan fayllar sozlamalar bo'limida ko'rsatilgan papkaga saqlanadi (standart: `~/Downloads/yuklamalar`).

---

## 🍪 "Sign in to confirm you're not a bot" xatosini hal qilish

YouTube ba'zan so'rovlarni bloklaydi va cookie orqali autentifikatsiya talab qiladi. Dastur buni **avtomatik** hal qilishga harakat qiladi:

1. Avval cookie'siz sinab ko'radi.
2. Bloklansa, kompyuteringizdagi brauzerlarni (Chrome, Firefox, Edge, Brave va h.k.) birma-bir sinab, ishlaydiganini eslab qoladi.
3. Baribir ishlamasa — quyidagi qo'lda usulni ishlating.

### cookies.txt faylini qo'lda olish

Bu — ayniqsa Linux'da (Snap orqali o'rnatilgan brauzerlarda cookie shifrlanadi) eng ishonchli yo'l:

1. Brauzeringizga kengaytma o'rnating:
   - **Chrome:** "Get cookies.txt LOCALLY"
   - **Firefox:** "cookies.txt"
2. `youtube.com`'ga kirib, hisobingizga login qilib qo'ying.
3. Kengaytma orqali cookie'larni `cookies.txt` fayliga eksport qiling.
4. Dastur oynasidagi **"🍪 Cookies fayli"** maydonidan shu faylni tanlang.

### Qo'shimcha tekshiruv (terminalda)

```bash
yt-dlp --version
pip install -U "yt-dlp[default]" --break-system-packages   # eng so'nggi versiyaga yangilash

yt-dlp --remote-components ejs:github --cookies /path/to/cookies.txt -v "https://www.youtube.com/watch?v=VIDEO_ID"
```

Agar bu buyruq ishласа, dastur ham ishlaydi — chunki u xuddi shu sozlamalardan (`remote_components: ejs:github`, cookie fayli) avtomatik foydalanadi.

---

## 🛠️ Muammolarni bartaraf etish

| Muammo | Yechim |
|---|---|
| `Sign in to confirm you're not a bot` | Yuqoridagi cookies.txt bo'limiga qarang |
| `Requested format is not available` / faqat rasm formatlari ko'rinadi | Deno o'rnatilganini va `remote_components: ejs:github` yoqilganini tekshiring |
| Yuklash juda sekin yoki `HTTP Error 429` | Bir necha daqiqa kutib qayta urinib ko'ring |
| `ffmpeg not found` | ffmpeg o'rnatilganini va PATH'da borligini tekshiring: `ffmpeg -version` |
| Dastur ochilmayapti / `ModuleNotFoundError` | `pip install PySide6 yt-dlp` bajarilganini tekshiring |

---

## 📁 Loyiha tuzilishi

```
Panel.py                                    # Asosiy dastur fayli
~/.video_yuklovchi_sozlamalar.json       # Saqlangan sozlamalar (avtomatik yaratiladi)
```

---

## ⚠️ Eslatma

Ushbu dastur faqat **shaxsiy va qonuniy maqsadlarda** foydalanish uchun mo'ljallangan. Mualliflik huquqi bilan himoyalangan kontentni yuklab olishdan oldin tegishli platformaning foydalanish shartlariga rioya qiling.

---

## 📄 Litsenziya

MIT License — erkin foydalanishingiz, o'zgartirishingiz va tarqatishingiz mumkin.

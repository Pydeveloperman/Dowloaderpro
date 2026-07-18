#!/usr/bin/env python3
"""
Video Yuklovchi GUI - YouTube, Instagram, TikTok  (Tkinter versiyasi)
=====================================================================
Zamonaviy, flat-dizaynli, dark/light mavzu almashtiriladigan interfeys orqali:
  - YouTube'da qidirish va natijadan video tanlash
  - Istalgan platformadan (YouTube/Instagram/TikTok) URL orqali yuklash
  - Pleylist to'liq yuklash
  - Saqlash papkasini "Papkani tanlash" tugmasi orqali tanlash
  - Video sifatini tanlash / faqat audio (MP3)
  - Yuklanish jarayoni progress-bar va foiz bilan ko'rsatiladi
  - Oxirgi tanlangan papka va cookie fayli eslab qolinadi (sozlamalar.json)

O'rnatish:
    pip install -U "yt-dlp[default]"
    # tkinter odatda Python bilan birga keladi. Agar yo'q bo'lsa:
    #   Linux (Debian/Ubuntu/Kali): sudo apt install python3-tk
    #   macOS/Windows: rasmiy python.org o'rnatuvchisida allaqachon bor
    #
    # ffmpeg ham kerak (video+audio birlashtirish, MP3'ga aylantirish uchun):
    #   Windows: https://ffmpeg.org/download.html dan yuklab, PATH'ga qo'shing
    #   Mac:     brew install ffmpeg
    #   Linux:   sudo apt install ffmpeg
    #
    # YouTube'ning JavaScript-challenge'larini yechish uchun Deno kerak:
    #   curl -fsSL https://deno.land/install.sh | sh

Ishga tushirish:
    python b2_tkinter.py
"""

import os
import re
import io
import json
import queue
import shutil
import threading
import urllib.request
import urllib.error

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

import yt_dlp

# Video-thumbnail (rasm) oldindan ko'rsatish uchun Pillow ixtiyoriy —
# o'rnatilmagan bo'lsa dastur baribir ishlayveradi, faqat thumbnail
# ko'rinmaydi va o'rniga tushunarli izoh chiqadi.
try:
    from PIL import Image, ImageTk
    PILLOW_MAVJUD = True
except ImportError:
    PILLOW_MAVJUD = False


SOZLAMALAR_FAYLI = os.path.join(os.path.expanduser("~"), ".video_yuklovchi_sozlamalar.json")
DEFAULT_PAPKA = os.path.join(os.path.expanduser("~"), "Downloads", "yuklamalar")

ASOSIY_YDL_SOZLAMALARI = {
    "quiet": True,
    "no_warnings": True,
    "socket_timeout": 20,
    "retries": 5,
    "windowsfilenames": True,
    # YouTube 2026-yildan boshlab formatlarni "ochish" uchun JavaScript
    # challenge (EJS) yechilishini talab qiladi. Buning uchun kompyuterda
    # JS runtime (masalan, Deno) o'rnatilgan bo'lishi va yt-dlp shu
    # skriptlarni GitHub'dan yuklab olishga ruxsat berilgan bo'lishi kerak
    # (aks holda faqat rasm-formatlar ko'rinadi, video/audio yo'q bo'lib
    # qoladi). Shu sabab bu yerda doimiy yoqib qo'yilgan:
    "remote_components": {"ejs:github"},
    # Eslatma: cookiesfrombrowser bu yerda statik yozilmagan. YouTube
    # so'rovni "bot" deb bloklasa, dastur pastdagi _ydl_bilan_bajarish()
    # funksiyasi orqali kompyuterdagi brauzerlar (Chrome, Firefox, Edge...)
    # cookie'sini avtomatik birma-bir sinab, ishlaganini eslab qoladi.
}


# ============================================================
# SOZLAMALARNI SAQLASH / O'QISH (oxirgi tanlangan papka, cookie fayli uchun)
# ============================================================

def sozlamalarni_oqish():
    try:
        with open(SOZLAMALAR_FAYLI, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def sozlamalarni_saqlash(sozlamalar):
    try:
        with open(SOZLAMALAR_FAYLI, "w", encoding="utf-8") as f:
            json.dump(sozlamalar, f)
    except Exception:
        pass


# ============================================================
# YORDAMCHI FUNKSIYALAR
# ============================================================

def hajmni_formatlash(baytlar):
    if not baytlar:
        return "noma'lum"
    for birlik in ["B", "KB", "MB", "GB"]:
        if baytlar < 1024:
            return f"{baytlar:.1f} {birlik}"
        baytlar /= 1024
    return f"{baytlar:.1f} TB"


def davomiylikni_formatlash(soniya):
    if not soniya:
        return "?"
    try:
        soniya = int(soniya)
    except (TypeError, ValueError):
        return "?"
    soat, qoldiq = divmod(soniya, 3600)
    daqiqa, son = divmod(qoldiq, 60)
    if soat:
        return f"{soat}:{daqiqa:02d}:{son:02d}"
    return f"{daqiqa}:{son:02d}"


def format_yorlig_yasash(f):
    """Bitta format uchun o'qilishi oson tavsif (label) yasaydi. Storyboard/rasm
    formatlarini (real video/audio bo'lmagan) o'tkazib yuborish uchun None qaytaradi."""
    vcodec = f.get("vcodec")
    acodec = f.get("acodec")
    videosi_bor = vcodec not in (None, "none")
    audiosi_bor = acodec not in (None, "none")

    if not videosi_bor and not audiosi_bor:
        return None  # storyboard yoki boshqa foydasiz format

    format_id = f.get("format_id") or f.get("ext") or "auto"
    ext = f.get("ext", "?")
    hajm = hajmni_formatlash(f.get("filesize") or f.get("filesize_approx"))

    if videosi_bor:
        balandlik = f.get("height")
        kenglik = f.get("width")
        # Ba'zi platformalar (masalan TikTok/Instagram) height/width
        # o'rniga faqat "resolution": "1080x1920" ko'rinishidagi matnni
        # beradi — shundan ham o'lchamni chiqarib olishga urinamiz.
        if not balandlik and not kenglik:
            oloshuv = f.get("resolution") or ""
            if "x" in oloshuv:
                bo_laklar = oloshuv.lower().split("x")
                if len(bo_laklar) == 2 and bo_laklar[1].strip().isdigit():
                    balandlik = int(bo_laklar[1].strip())
        fps = f.get("fps")
        if balandlik:
            olcham = f"{balandlik}p" + (f"{int(fps)}" if fps and fps != 30 else "")
        elif kenglik:
            olcham = f"{kenglik}px"
        else:
            olcham = f.get("format_note") or "noma'lum o'lcham"
        turi = "video+audio" if audiosi_bor else "video (audio avtomatik qo'shiladi)"
        return {
            "label": f"[{format_id}] {olcham} · {ext} · {turi} · {hajm}",
            "format_id": format_id,
            "audiosi_bor": audiosi_bor,
            "balandlik": balandlik or 0,
            "abr": f.get("abr") or f.get("tbr") or 0,
            "turkum": "video",
        }
    else:
        abr = f.get("abr") or f.get("tbr")
        abr_str = f"{int(abr)}kbps" if abr else ""
        return {
            "label": f"[{format_id}] faqat audio {abr_str} · {ext} · {hajm}",
            "format_id": format_id,
            "audiosi_bor": True,
            "balandlik": 0,
            "abr": abr or 0,
            "turkum": "audio",
        }


def barcha_formatlarni_tayyorla(malumot):
    """extract_info natijasidagi barcha formatlarni tartiblab, combobox uchun
    ro'yxat (avtomatik eng yaxshi + har bir format + MP3 audio) qaytaradi."""
    xom_formatlar = list(malumot.get("formats") or [])

    tayyorlangan = []
    korilgan_idlar = set()
    for f in xom_formatlar:
        yorliq = format_yorlig_yasash(f)
        if yorliq and yorliq["format_id"] not in korilgan_idlar:
            tayyorlangan.append(yorliq)
            korilgan_idlar.add(yorliq["format_id"])

    # MUHIM XATO TUZATILDI: YouTube'dan farqli ko'plab platformalar
    # (Instagram, TikTok, Facebook, X/Twitter va h.k.) har doim ham
    # bir nechta sifat variantini alohida 'formats' ro'yxatida
    # qaytaravermaydi — ko'pincha faqat bitta tayyor video havolasini
    # to'g'ridan-to'g'ri ma'lumot lug'atining o'zida ('url', 'ext',
    # 'vcodec' kabi maydonlar orqali) beradi. Aynan shu sabab bunday
    # platformalarda "sifat" ro'yxati bo'sh chiqib, foydalanuvchi hech
    # qanday tanlov ko'rmas edi. Endi 'formats' bo'sh bo'lsa (yoki
    # ichidagilar storyboard bo'lib chiqib, hammasi filtrlanib ketsa),
    # ma'lumotning o'zidan yagona formatni yasab, ro'yxatga qo'shamiz.
    if not tayyorlangan and malumot.get("url"):
        yorliq = format_yorlig_yasash(malumot)
        if yorliq:
            tayyorlangan.append(yorliq)

    video_variantlari = sorted(
        (v for v in tayyorlangan if v["turkum"] == "video"),
        key=lambda v: (v["balandlik"], v["abr"]), reverse=True,
    )
    audio_variantlari = sorted(
        (v for v in tayyorlangan if v["turkum"] == "audio"),
        key=lambda v: v["abr"], reverse=True,
    )

    natija = [{"label": "★ Eng yaxshi sifat (avtomatik video+audio)", "kind": "auto"}]
    for v in video_variantlari + audio_variantlari:
        natija.append({
            "label": v["label"], "kind": "format",
            "format_id": v["format_id"], "audiosi_bor": v["audiosi_bor"],
        })
    natija.append({"label": "🎵 Faqat audio (MP3'ga o'tkaziladi)", "kind": "mp3"})
    return natija


def xatolik_izohi(xato):
    matn = str(xato)
    if matn.startswith("Sign in to confirm: "):
        # Bu — _ydl_bilan_bajarish() o'zi chiqargan, allaqachon aniq va
        # tushunarli xabar (cookie fayli/brauzerlar sinalganidan keyin).
        # Uni umumiy matn bilan almashtirmaymiz.
        return matn[len("Sign in to confirm: "):]
    if "Sign in to confirm" in matn or "not a bot" in matn:
        return (
            "YouTube so'rovni 'bot' deb bloklayapti.\n"
            "Dastur avtomatik ravishda kompyuteringizdagi brauzerlar (Chrome, "
            "Firefox, Edge va h.k.) cookie'sini sinab ko'rdi, lekin birortasi "
            "ham ishlamadi.\n"
            "Yechim: shu brauzerlardan biriga o'rnatib, YouTube'ga hisobingiz "
            "bilan kirib qo'ying (login qilib qo'yish kifoya), so'ng qayta "
            "urinib ko'ring. Terminalda 'pip install -U yt-dlp' bilan "
            "yangilash ham foydali bo'lishi mumkin."
        )
    if "HTTP Error 429" in matn or "Too Many Requests" in matn:
        return "Juda ko'p so'rov yuborildi. Bir necha daqiqadan so'ng qayta urinib ko'ring."
    if "Unsupported URL" in matn:
        return "Bu havola qo'llab-quvvatlanmaydi yoki noto'g'ri kiritilgan."
    if "ffmpeg not found" in matn or "ffprobe and ffmpeg not found" in matn or "requires ffmpeg" in matn.lower():
        return (
            "ffmpeg kompyuterda topilmadi. MP3'ga o'tkazish yoki video+audio "
            "birlashtirish uchun ffmpeg kerak.\n"
            "O'rnatish: Linux — sudo apt install ffmpeg | Mac — brew install ffmpeg | "
            "Windows — ffmpeg.org'dan yuklab PATH'ga qo'shing."
        )
    if "No JS runtime" in matn or "no supported JavaScript runtime" in matn.lower():
        return (
            "JavaScript runtime (Deno) topilmadi — YouTube formatlarini to'liq "
            "ochish uchun kerak.\n"
            "O'rnatish: curl -fsSL https://deno.land/install.sh | sh"
        )
    return matn


# ============================================================
# FON OQIMLARI (threading.Thread) — navbat (queue) orqali UI bilan
# xavfsiz aloqa. Tkinter widget'lari faqat asosiy oqimda o'zgartirilishi
# kerak, shu sabab fon oqimi hech qachon to'g'ridan-to'g'ri UI'ga tegmaydi —
# u faqat navbatga xabar qo'yadi, asosiy oqim esa uni davriy o'qib turadi.
# ============================================================

class Signallar:
    """PySide6'dagi Signal'larga o'xshash, lekin thread-xavfsiz Queue orqali
    ishlaydigan yordamchi klass."""

    def __init__(self, navbat):
        self._navbat = navbat

    def log(self, matn):
        self._navbat.put(("log", matn))

    def holat(self, matn):
        self._navbat.put(("holat", matn))

    def progress(self, foiz):
        self._navbat.put(("progress", foiz))

    def qidiruv_natija(self, natijalar):
        self._navbat.put(("qidiruv_natija", natijalar))

    def sifatlar(self, malumot, formatlar):
        self._navbat.put(("sifatlar", (malumot, formatlar)))

    def xato(self, matn):
        self._navbat.put(("xato", matn))

    def tugadi(self, matn):
        self._navbat.put(("tugadi", matn))


class Ishchi(threading.Thread):
    """Har qanday uzun-davom funksiyani (qidirish, ma'lumot olish, yuklash)
    fon oqimida ishga tushiradigan umumiy klass."""

    def __init__(self, funksiya, signallar, *args, **kwargs):
        super().__init__(daemon=True)
        self.funksiya = funksiya
        self.signallar = signallar
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            self.funksiya(self.signallar, *self.args, **self.kwargs)
        except Exception as xato:  # kutilmagan xatolar ham UI'ga yetib borsin
            self.signallar.xato(xatolik_izohi(xato))


# ---------------- Fon vazifalari (Ishchi ichida chaqiriladi) ----------------

# Kompyuterda mavjud bo'lishi mumkin bo'lgan brauzerlar — YouTube "bot" deb
# bloklaganda shular orqali cookie olishga urinib ko'ramiz.
_SINALADIGAN_BROUZERLAR = ["chrome", "edge", "firefox", "brave", "chromium", "vivaldi", "opera"]

# "ANIQLANMAGAN" — hali birorta ham brauzer sinalmagan.
# Bror brauzer nomi — o'sha ishlagani va endi doim shu ishlatiladi.
# None — barcha brauzerlar sinalgan, lekin birortasi ham ishlamagan.
_ishlaydigan_brouzer = "ANIQLANMAGAN"

# Foydalanuvchi "Bekor qilish" tugmasini bosganda shu Event o'rnatiladi —
# progress_hook uni tekshirib, yt-dlp'ga yuklashni to'xtatishni buyuradi.
_bekor_bayrogi = threading.Event()


def bekor_qilishni_sorash():
    _bekor_bayrogi.set()


def bekor_bayrogini_tozalash():
    _bekor_bayrogi.clear()


# Foydalanuvchi UI orqali qo'lda ko'rsatgan cookies.txt fayli yo'li (bo'lsa).
# Bu ayniqsa Linux'da Snap orqali o'rnatilgan Chrome/Chromium/Firefox uchun
# eng ishonchli yo'l, chunki ular cookie'larini gnome-keyring/kwallet orqali
# shifrlaydi yoki sandbox tufayli profil yo'lini yashiradi — shu sabab
# cookiesfrombrowser ko'pincha ularda ishlamaydi.
_cookie_fayli = None


def cookie_faylini_ornatish(yol):
    global _cookie_fayli
    _cookie_fayli = yol or None


def _bot_xatosimi(xato):
    matn = str(xato)
    return "Sign in to confirm" in matn or "not a bot" in matn


def _ydl_bilan_bajarish(qoshimcha_sozlamalar, amal):
    """yt-dlp orqali biror amalni (qidirish / ma'lumot olish / yuklash)
    bajaradi. Agar YouTube so'rovni 'bot' deb bloklasa: avval foydalanuvchi
    ko'rsatgan cookies.txt fayli, keyin kompyuterdagi brauzerlarning
    cookie'si birma-bir sinaladi va ishlagani xotirada saqlab qo'yiladi —
    shu tufayli keyingi barcha so'rovlar avtomatik ketaveradi."""
    global _ishlaydigan_brouzer

    def _chaqirish(cookie_brouzeri=None, cookie_fayli=None):
        joriy = {**ASOSIY_YDL_SOZLAMALARI, **qoshimcha_sozlamalar}
        if cookie_fayli:
            joriy["cookiefile"] = cookie_fayli
        elif cookie_brouzeri:
            joriy["cookiesfrombrowser"] = (cookie_brouzeri,)
        with yt_dlp.YoutubeDL(joriy) as ydl:
            return amal(ydl)

    # 1) Foydalanuvchi cookies.txt ko'rsatgan bo'lsa — bu eng ishonchli yo'l
    if _cookie_fayli:
        try:
            return _chaqirish(cookie_fayli=_cookie_fayli)
        except Exception:
            pass  # fayl eskirgan/noto'g'ri bo'lishi mumkin — davom etamiz

    # 2) Avval ishlagan brauzer bo'lsa, to'g'ridan-to'g'ri o'shani sinaymiz
    if _ishlaydigan_brouzer not in ("ANIQLANMAGAN", None):
        try:
            return _chaqirish(_ishlaydigan_brouzer)
        except Exception:
            pass  # brauzer keyin o'zgargan/yopilgan bo'lishi mumkin — davom etamiz

    # 3) Cookie'siz sinab ko'ramiz (aksariyat hollarda shu yetarli)
    try:
        return _chaqirish()
    except Exception as birinchi_xato:
        if not _bot_xatosimi(birinchi_xato):
            raise

    # 4) 'Bot' deb bloklandi — mavjud brauzerlar cookie'sini birma-bir sinaymiz
    for brouzer in _SINALADIGAN_BROUZERLAR:
        try:
            natija = _chaqirish(brouzer)
            _ishlaydigan_brouzer = brouzer
            return natija
        except Exception:
            continue

    _ishlaydigan_brouzer = None
    raise RuntimeError(
        "Sign in to confirm: YouTube hali ham 'bot' deb bloklayapti — "
        "cookies.txt fayli ham, brauzer cookie'lari ham yordam bermadi.\n"
        "Ehtimoliy sabablar:\n"
        "1) yt-dlp eskirgan bo'lishi mumkin — terminalda:\n"
        "   pip install -U yt-dlp\n"
        "2) cookies.txt eksport qilinganda YouTube'da login qilinmagan "
        "bo'lgan yoki fayl eskirib qolgan — qaytadan youtube.com'da login "
        "qilib, kengaytma orqali qayta eksport qiling.\n"
        "3) Agar VPN/proksi ishlatayotgan bo'lsangiz — YouTube ba'zan IP "
        "manzilning o'zini shubhali deb bloklaydi, cookie'dan qat'i nazar. "
        "VPN'ni o'chirib qayta urinib ko'ring."
    )


def vazifa_qidirish(signallar, soro):
    sozlamalar = {
        "extract_flat": "in_playlist",
        "default_search": "ytsearch10",
    }
    try:
        natija = _ydl_bilan_bajarish(sozlamalar, lambda ydl: ydl.extract_info(soro, download=False))
        videolar = [v for v in (natija.get("entries") or []) if v]
        signallar.qidiruv_natija(videolar)
        signallar.holat(f"{len(videolar)} ta natija topildi." if videolar else "Hech narsa topilmadi.")
    except Exception as xato:
        signallar.xato(xatolik_izohi(xato))
        signallar.holat("Qidirishda xatolik.")


def vazifa_malumot_olish(signallar, url):
    try:
        malumot = _ydl_bilan_bajarish({}, lambda ydl: ydl.extract_info(url, download=False))
        if malumot.get("_type") in ("playlist", "multi_video"):
            signallar.xato(
                "Bu havola pleylist ko'rinadi. Pleylist yuklash uchun "
                "'Pleylist yuklash' tabidan foydalaning."
            )
            signallar.holat("Bu pleylist havolasi.")
            return
        format_variantlari = barcha_formatlarni_tayyorla(malumot)
        signallar.sifatlar(malumot, format_variantlari)
        signallar.holat("Formatlar yuklandi. Endi kerakli formatni tanlab yuklang.")
    except Exception as xato:
        signallar.xato(xatolik_izohi(xato))
        signallar.holat("Ma'lumot olishda xatolik.")


def _progress_hook_yasash(signallar):
    def hook(d):
        if _bekor_bayrogi.is_set():
            # yt-dlp shu maxsus xatoni kutadi — uni ko'rganda yuklashni
            # darhol, toza tarzda to'xtatadi.
            raise yt_dlp.utils.DownloadCancelled("Foydalanuvchi bekor qildi.")

        info = d.get("info_dict") or {}
        pleylist_indeks = info.get("playlist_index")
        pleylist_soni = info.get("playlist_count") or info.get("n_entries")
        pleylist_prefiks = ""
        if pleylist_indeks and pleylist_soni:
            pleylist_prefiks = f"[{pleylist_indeks}/{pleylist_soni}] "

        if d["status"] == "downloading":
            foiz_str = (d.get("_percent_str") or "0%").strip().replace("%", "")
            # yt-dlp foiz matniga ba'zan ANSI-rang kodlarini ham qo'shib
            # yuborishi mumkin — shularni tozalab, faqat raqamni qoldiramiz.
            foiz_toza = re.sub(r"[^0-9.]", "", foiz_str)
            try:
                foiz = float(foiz_toza) if foiz_toza else 0.0
            except ValueError:
                foiz = 0.0
            signallar.progress(foiz)
            tezlik = (d.get("_speed_str") or "").strip()

            # So'ralgan yangi funksiya: qancha yuklangani (hajm bo'yicha)
            # ham holat qatorida ko'rsatiladi, faqat foiz emas.
            yuklangan = d.get("downloaded_bytes")
            jami = d.get("total_bytes") or d.get("total_bytes_estimate")
            if yuklangan is not None and jami:
                hajm_matn = f"  |  {hajmni_formatlash(yuklangan)} / {hajmni_formatlash(jami)}"
            elif yuklangan is not None:
                hajm_matn = f"  |  {hajmni_formatlash(yuklangan)} yuklandi"
            else:
                hajm_matn = ""

            qolgan = (d.get("_eta_str") or "").strip()
            qolgan_matn = f"  |  Qoldi: {qolgan}" if qolgan and qolgan != "Unknown" else ""

            signallar.holat(
                f"{pleylist_prefiks}Yuklanmoqda: {foiz_toza or '0'}%{hajm_matn}  |  "
                f"Tezlik: {tezlik or 'nomalum'}{qolgan_matn}"
            )
        elif d["status"] == "finished":
            signallar.holat(f"{pleylist_prefiks}Yuklab olindi, qayta ishlanmoqda (ffmpeg)...")
            signallar.progress(100)
    return hook


def vazifa_url_yuklash(signallar, url, tanlangan, papka, subtitr_sozlama=None):
    try:
        asosiy_sozlama = {
            "outtmpl": os.path.join(papka, "%(title)s.%(ext)s"),
            "progress_hooks": [_progress_hook_yasash(signallar)],
        }
        if subtitr_sozlama:
            asosiy_sozlama.update(subtitr_sozlama)

        if tanlangan["kind"] == "mp3":
            sozlamalar = {
                **asosiy_sozlama,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192",
                }],
            }
            signallar.holat("Audio (MP3) sifatida yuklanmoqda...")
        elif tanlangan["kind"] == "auto":
            sozlamalar = {
                **asosiy_sozlama,
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
            }
            signallar.holat("Eng yaxshi sifatda yuklanmoqda...")
        else:
            format_id = tanlangan["format_id"]
            if tanlangan["audiosi_bor"]:
                # "/best" — agar aynan shu format_id endi mavjud bo'lmasa
                # (YouTube formatlarni tez-tez yangilaydi), oxirgi zaxira
                # sifatida eng yaxshi mavjud formatga o'tadi.
                format_satri = f"{format_id}/best"
            else:
                format_satri = f"{format_id}+bestaudio/best/best"
            sozlamalar = {
                **asosiy_sozlama,
                "format": format_satri,
                "merge_output_format": "mp4",
            }
            signallar.holat(f"[{format_id}] formatida yuklanmoqda...")

        try:
            _ydl_bilan_bajarish(sozlamalar, lambda ydl: ydl.download([url]))
        except yt_dlp.utils.DownloadError as birinchi_xato:
            if "Requested format is not available" in str(birinchi_xato):
                # Tanlangan aniq format endi ishlamayapti — avtomatik
                # eng yaxshi sifatga o'tib, qayta urinib ko'ramiz.
                signallar.holat(
                    "Tanlangan format endi mavjud emas, avtomatik eng yaxshi sifatga o'tilmoqda..."
                )
                zaxira_sozlama = {
                    **asosiy_sozlama,
                    "format": "bestvideo+bestaudio/best",
                    "merge_output_format": "mp4",
                }
                _ydl_bilan_bajarish(zaxira_sozlama, lambda ydl: ydl.download([url]))
            else:
                raise
        signallar.tugadi(f"Tayyor! '{papka}' papkasiga saqlandi.")
    except yt_dlp.utils.DownloadCancelled:
        signallar.holat("Yuklash bekor qilindi.")
        signallar.tugadi("Yuklash bekor qilindi.")
    except Exception as xato:
        signallar.xato(xatolik_izohi(xato))
        signallar.holat("Yuklashda xatolik.")


def vazifa_pleylist_yuklash(signallar, url, sifat_matn, papka, subtitr_sozlama=None):
    pleylist_papka = os.path.join(papka, "%(playlist_title)s")
    try:
        variant = PLEYLIST_SIFAT_VARIANTLARI.get(
            sifat_matn, PLEYLIST_SIFAT_VARIANTLARI["720p (HD)"]
        )
        if variant["faqat_audio"]:
            sozlamalar = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(pleylist_papka, "%(title)s.%(ext)s"),
                "progress_hooks": [_progress_hook_yasash(signallar)],
                "postprocessors": [{
                    "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192",
                }],
            }
        else:
            balandlik = variant["balandlik"]
            sozlamalar = {
                "format": f"bestvideo[height<={balandlik}]+bestaudio/best[height<={balandlik}]",
                "outtmpl": os.path.join(pleylist_papka, "%(title)s.%(ext)s"),
                "progress_hooks": [_progress_hook_yasash(signallar)],
                "merge_output_format": "mp4",
            }

        if subtitr_sozlama:
            sozlamalar.update(subtitr_sozlama)
        sozlamalar["ignoreerrors"] = "only_download"

        signallar.holat("Pleylist yuklanmoqda, biroz vaqt olishi mumkin...")
        _ydl_bilan_bajarish(sozlamalar, lambda ydl: ydl.download([url]))
        signallar.tugadi(f"Pleylist to'liq yuklandi! '{papka}' papkasini tekshiring.")
    except yt_dlp.utils.DownloadCancelled:
        signallar.holat("Pleylist yuklash bekor qilindi.")
        signallar.tugadi("Pleylist yuklash bekor qilindi.")
    except Exception as xato:
        signallar.xato(xatolik_izohi(xato))
        signallar.holat("Pleylist yuklashda xatolik.")


# Faqat shu amal turlari haqiqatan "Bekor qilish" tugmasi bilan
# to'xtatilishi mumkin, chunki ular progress_hook orqali ishlaydi.
BEKOR_QILINADIGAN_AMALLAR = {"yuklash", "pleylist_yuklash", "kop_url_yuklash"}


# Pleylist sifat combobox'idagi ko'rsatiladigan matn -> haqiqiy qiymat.
# Matnni keyin "1080p".split("p") kabi mo'rt tarzda parslash o'rniga,
# shu lug'atdan to'g'ridan-to'g'ri qiymat olinadi.
PLEYLIST_SIFAT_VARIANTLARI = {
    "1080p (Full HD)": {"balandlik": 1080, "faqat_audio": False},
    "720p (HD)": {"balandlik": 720, "faqat_audio": False},
    "480p (O'rta sifat)": {"balandlik": 480, "faqat_audio": False},
    "Faqat audio (MP3)": {"balandlik": None, "faqat_audio": True},
}


# Subtitr (subtitle) tanlash uchun ko'rsatiladigan matn -> yt-dlp til kodi.
SUBTITR_TILLARI = {
    "O'zbek": "uz",
    "Ingliz": "en",
    "Rus": "ru",
    "Barcha mavjud tillar": "all",
}


def _subtitr_ydl_sozlamalarini_yasash(subtitr_yoqilgan, til_matni):
    """Subtitr checkbox va til tanloviga qarab yt-dlp'ga qo'shiladigan
    qo'shimcha sozlamalarni qaytaradi. Subtitr o'chirilgan bo'lsa bo'sh
    lug'at qaytaradi."""
    if not subtitr_yoqilgan:
        return {}
    til_kodi = SUBTITR_TILLARI.get(til_matni, "uz")
    return {
        # Ham "asl" (qo'lda yozilgan), ham avtomatik-generatsiya qilingan
        # subtitrlar sinaladi — ko'p videolarda faqat avtomatik subtitr
        # mavjud bo'ladi, shu sabab ikkalasi ham yoqilgan.
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["all"] if til_kodi == "all" else [til_kodi, f"{til_kodi}.*"],
        "subtitlesformat": "srt/best",
        # Subtitr topilmasa ham yuklash umumiy xato bilan to'xtamasin.
        "ignore_no_formats_error": True,
    }


# ============================================================
# MAVZULAR — yorug' va qorong'i rang palitralari
# ============================================================

YORUGH_MAVZU = {
    "bg": "#f5f6fa", "fg": "#1c1e21", "panel": "#ffffff", "border": "#d7dbe0",
    "accent": "#4f8cff", "accent_hover": "#3d7bef", "accent_active": "#2f68d8",
    "success": "#34c38f", "success_hover": "#2aab7c",
    "ikkinchi": "#e7eaf0", "ikkinchi_hover": "#dde1e9",
    "muted": "#7a8291", "entry_bg": "#ffffff", "sel_bg": "#4f8cff", "sel_fg": "#ffffff",
    "disabled": "#b7c6e6",
}

QORONGI_MAVZU = {
    "bg": "#1b1d23", "fg": "#e6e8ec", "panel": "#22252d", "border": "#383c47",
    "accent": "#5a8dee", "accent_hover": "#4a7de0", "accent_active": "#3c6bc9",
    "success": "#2fbf8a", "success_hover": "#26a878",
    "ikkinchi": "#2d3039", "ikkinchi_hover": "#383c47",
    "muted": "#9aa1b0", "entry_bg": "#262933", "sel_bg": "#5a8dee", "sel_fg": "#ffffff",
    "disabled": "#33405e",
}


# ============================================================
# ASOSIY OYNA
# ============================================================

class VideoYuklovchiOyna(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Yuklovchi — YouTube / Instagram / TikTok")
        self.geometry("980x740")
        self.minsize(780, 580)

        self.sozlamalar = sozlamalarni_oqish()
        self.saqlash_papkasi = self.sozlamalar.get("papka", DEFAULT_PAPKA)
        self.qorongi_mi = self.sozlamalar.get("qorongi", False)

        self.qidiruv_natijalari = []
        self.tanlangan_video_url = None
        self.format_variantlari = []
        self.video_malumoti = None
        self.faol_ishchi = None  # bir vaqtda bitta fon oqimi
        self.joriy_amal = None

        self.navbat = queue.Queue()

        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self._ui_yaratish()
        self._mavzuni_qollash()

        self.protocol("WM_DELETE_WINDOW", self._yopishni_boshqarish)
        self.after(100, self._navbat_tekshirish)
        self.after(300, self._bogliqliklarni_tekshirish)

    def _bogliqliklarni_tekshirish(self):
        """Ishga tushganda ffmpeg va Deno (JS runtime) borligini tekshiradi
        va yo'q bo'lsa, foydalanuvchini oldindan ogohlantiradi — shunda
        yuklash paytida tushunarsiz xatoga duch kelmaydi."""
        if shutil.which("ffmpeg") is None:
            self._log(
                "OGOHLANTIRISH: ffmpeg topilmadi. MP3'ga o'tkazish va "
                "video+audio birlashtirish ishlamaydi. O'rnatish: "
                "Linux — sudo apt install ffmpeg | Mac — brew install ffmpeg | "
                "Windows — ffmpeg.org'dan yuklab PATH'ga qo'shing."
            )
        if shutil.which("deno") is None:
            self._log(
                "OGOHLANTIRISH: Deno topilmadi. YouTube ba'zan formatlarni "
                "to'liq ko'rsatishi uchun Deno kerak bo'lishi mumkin. "
                "O'rnatish: curl -fsSL https://deno.land/install.sh | sh"
            )

    # ---------------- UI qurish ----------------

    def _ui_yaratish(self):
        markaziy = ttk.Frame(self, padding=(18, 16, 18, 14))
        markaziy.pack(fill=tk.BOTH, expand=True)
        self._markaziy = markaziy

        # ---------- Sarlavha ----------
        header = ttk.Frame(markaziy)
        header.pack(fill=tk.X)

        sarlavha_ustun = ttk.Frame(header)
        sarlavha_ustun.pack(side=tk.LEFT)
        self.sarlavha_label = ttk.Label(sarlavha_ustun, text="🎬 Video Yuklovchi", font=("Segoe UI", 16, "bold"))
        self.sarlavha_label.pack(anchor="w")
        self.kichik_label = ttk.Label(sarlavha_ustun, text="YouTube · Instagram · TikTok")
        self.kichik_label.pack(anchor="w")

        self.mavzu_tugmasi = ttk.Button(header, text="🌙 Qorong'i", width=14,
                                         style="Ikkinchi.TButton", command=self._mavzu_almashtirish)
        self.mavzu_tugmasi.pack(side=tk.RIGHT, anchor="n")

        ttk.Separator(markaziy).pack(fill=tk.X, pady=(10, 10))

        # ---------- Papka tanlash ----------
        ttk.Label(markaziy, text="📁 Saqlash papkasi", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        papka_lay = ttk.Frame(markaziy)
        papka_lay.pack(fill=tk.X, pady=(4, 8))
        self.papka_maydon = ttk.Entry(papka_lay)
        self.papka_maydon.insert(0, self.saqlash_papkasi)
        self.papka_maydon.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(papka_lay, text="Papkani tanlash...", style="Ikkinchi.TButton",
                   command=self._papka_tanlash).pack(side=tk.LEFT, padx=(8, 0))

        # ---------- Cookies fayli ----------
        ttk.Label(markaziy, text="🍪 Cookies fayli (ixtiyoriy — 'bot' bloklansa kerak bo'ladi)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")
        cookie_lay = ttk.Frame(markaziy)
        cookie_lay.pack(fill=tk.X, pady=(4, 10))
        self.cookie_maydon = ttk.Entry(cookie_lay)
        self.cookie_maydon.insert(0, self.sozlamalar.get("cookies_fayli", ""))
        self.cookie_maydon.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cookie_maydon.bind("<FocusOut>", self._cookie_maydon_ozgardi)
        ttk.Button(cookie_lay, text="Faylni tanlash...", style="Ikkinchi.TButton",
                   command=self._cookie_fayl_tanlash).pack(side=tk.LEFT, padx=(8, 0))
        cookie_faylini_ornatish(self.cookie_maydon.get().strip() or None)

        # ---------- Tablar ----------
        self.daftar = ttk.Notebook(markaziy)
        self.daftar.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self._qidiruv_tab_yaratish()
        self._url_tab_yaratish()
        self._pleylist_tab_yaratish()
        self.daftar.add(self.qidiruv_tab, text="🔍  YouTube'da qidirish")
        self.daftar.add(self.url_tab, text="🔗  Havola orqali yuklash")
        self.daftar.add(self.pleylist_tab, text="📋  Pleylist yuklash")

        # ---------- Progress + holat + log ----------
        progress_lay = ttk.Frame(markaziy)
        progress_lay.pack(fill=tk.X, pady=(0, 6))
        self.progress = ttk.Progressbar(progress_lay, mode="determinate", maximum=100)
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.bekor_tugmasi = ttk.Button(
            progress_lay, text="✕ Bekor qilish", style="Ikkinchi.TButton",
            state="disabled", command=self._bekor_qilish,
        )
        self.bekor_tugmasi.pack(side=tk.LEFT, padx=(8, 0))

        self.holat_label = ttk.Label(markaziy, text="Tayyor.")
        self.holat_label.pack(anchor="w", pady=(0, 6))

        self.log_matn = ScrolledText(markaziy, height=7, font=("Consolas", 9), wrap="word")
        self.log_matn.configure(state="disabled")
        self.log_matn.pack(fill=tk.X)

    def _qidiruv_tab_yaratish(self):
        self.qidiruv_tab = ttk.Frame(self.daftar, padding=16)

        top = ttk.Frame(self.qidiruv_tab)
        top.pack(fill=tk.X)
        self.qidiruv_maydon = ttk.Entry(top)
        self.qidiruv_maydon.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.qidiruv_maydon.bind("<Return>", lambda e: self._qidirishni_boshlash())
        self.qidirish_tugmasi = ttk.Button(top, text="🔍 Qidirish", style="Accent.TButton",
                                            command=self._qidirishni_boshlash)
        self.qidirish_tugmasi.pack(side=tk.LEFT, padx=(8, 0))

        jadval_ramka = ttk.Frame(self.qidiruv_tab)
        jadval_ramka.pack(fill=tk.BOTH, expand=True, pady=(10, 10))
        ustunlar = ("nomi", "kanal", "davomiylik")
        self.qidiruv_jadval = ttk.Treeview(jadval_ramka, columns=ustunlar, show="headings", selectmode="browse")
        self.qidiruv_jadval.heading("nomi", text="Nomi")
        self.qidiruv_jadval.heading("kanal", text="Kanal")
        self.qidiruv_jadval.heading("davomiylik", text="Davomiylik")
        self.qidiruv_jadval.column("nomi", width=420, anchor="w")
        self.qidiruv_jadval.column("kanal", width=200, anchor="w")
        self.qidiruv_jadval.column("davomiylik", width=100, anchor="center")
        skroll = ttk.Scrollbar(jadval_ramka, orient="vertical", command=self.qidiruv_jadval.yview)
        self.qidiruv_jadval.configure(yscrollcommand=skroll.set)
        self.qidiruv_jadval.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        skroll.pack(side=tk.LEFT, fill=tk.Y)
        self.qidiruv_jadval.bind("<Double-1>", lambda e: self._qidiruvdan_video_tanlash())

        pastki = ttk.Frame(self.qidiruv_tab)
        pastki.pack(fill=tk.X)
        self.tanlash_tugmasi = ttk.Button(pastki, text="⬇️  Tanlangan videoni yuklash", style="Muvaffaqiyat.TButton",
                                           command=self._qidiruvdan_video_tanlash)
        self.tanlash_tugmasi.pack(side=tk.RIGHT)

    def _url_tab_yaratish(self):
        self.url_tab = ttk.Frame(self.daftar, padding=16)

        ttk.Label(self.url_tab, text="Video havolasi (YouTube / Instagram / TikTok)",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w")

        top = ttk.Frame(self.url_tab)
        top.pack(fill=tk.X, pady=(4, 0))
        self.url_maydon = ttk.Entry(top)
        self.url_maydon.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.url_maydon.bind("<Return>", lambda e: self._url_malumot_olish())
        self.sifat_olish_tugmasi = ttk.Button(top, text="Formatlarni olish",
                                               command=self._url_malumot_olish)
        self.sifat_olish_tugmasi.pack(side=tk.LEFT, padx=(8, 0))

        # ---------- Asosiy (chap) va thumbnail (o'ng) ustunlar ----------
        govda = ttk.Frame(self.url_tab)
        govda.pack(fill=tk.BOTH, expand=True, pady=(14, 0))

        chap = ttk.Frame(govda)
        chap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(chap, text="🎚️ Mavjud formatlar", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.sifat_combobox = ttk.Combobox(chap, state="readonly")
        self.sifat_combobox.pack(fill=tk.X, pady=(4, 12))

        # Yangi funksiya: subtitr (subtitle) yuklab olish imkoniyati.
        subtitr_lay = ttk.Frame(chap)
        subtitr_lay.pack(fill=tk.X)
        self.subtitr_yoqilgan = tk.BooleanVar(value=False)
        self.subtitr_belgisi = ttk.Checkbutton(
            subtitr_lay, text="📝 Subtitrlarni ham yuklash", variable=self.subtitr_yoqilgan,
            command=self._subtitr_holatini_yangilash,
        )
        self.subtitr_belgisi.pack(side=tk.LEFT)
        self.subtitr_til = ttk.Combobox(
            subtitr_lay, state="disabled", width=18,
            values=list(SUBTITR_TILLARI.keys()),
        )
        self.subtitr_til.set("O'zbek")
        self.subtitr_til.pack(side=tk.LEFT, padx=(10, 0))

        # ---------- Thumbnail (rasm) oldindan ko'rish ----------
        self.thumbnail_ramka = ttk.Frame(govda, width=200, height=140)
        self.thumbnail_ramka.pack(side=tk.LEFT, padx=(16, 0))
        self.thumbnail_ramka.pack_propagate(False)
        self.thumbnail_label = ttk.Label(
            self.thumbnail_ramka, text="Thumbnail\nbu yerda ko'rinadi",
            anchor="center", justify="center", style="Thumbnail.TLabel",
        )
        self.thumbnail_label.pack(fill=tk.BOTH, expand=True)
        self._thumbnail_rasm = None  # PhotoImage'ga doimiy referens (GC bo'lib ketmasligi uchun)

        pastki = ttk.Frame(self.url_tab)
        pastki.pack(fill=tk.X, side=tk.BOTTOM, pady=(14, 0))
        self.yuklash_tugmasi = ttk.Button(pastki, text="⬇️  Yuklab olish", style="Muvaffaqiyat.TButton",
                                           command=self._url_yuklash)
        self.yuklash_tugmasi.pack(side=tk.RIGHT)

    def _subtitr_holatini_yangilash(self):
        self.subtitr_til.configure(state=("readonly" if self.subtitr_yoqilgan.get() else "disabled"))

    def _pleylist_tab_yaratish(self):
        self.pleylist_tab = ttk.Frame(self.daftar, padding=16)

        ttk.Label(self.pleylist_tab, text="Pleylist havolasi", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.pleylist_maydon = ttk.Entry(self.pleylist_tab)
        self.pleylist_maydon.pack(fill=tk.X, pady=(4, 0))

        ttk.Label(self.pleylist_tab, text="🎚️ Sifat", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(14, 4))
        self.pleylist_sifat = ttk.Combobox(
            self.pleylist_tab, state="readonly",
            values=list(PLEYLIST_SIFAT_VARIANTLARI.keys()),
        )
        self.pleylist_sifat.set("720p (HD)")
        self.pleylist_sifat.pack(fill=tk.X)

        subtitr_lay = ttk.Frame(self.pleylist_tab)
        subtitr_lay.pack(fill=tk.X, pady=(12, 0))
        self.pleylist_subtitr_yoqilgan = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            subtitr_lay, text="📝 Subtitrlarni ham yuklash", variable=self.pleylist_subtitr_yoqilgan,
            command=lambda: self.pleylist_subtitr_til.configure(
                state=("readonly" if self.pleylist_subtitr_yoqilgan.get() else "disabled")
            ),
        ).pack(side=tk.LEFT)
        self.pleylist_subtitr_til = ttk.Combobox(
            subtitr_lay, state="disabled", width=18, values=list(SUBTITR_TILLARI.keys()),
        )
        self.pleylist_subtitr_til.set("O'zbek")
        self.pleylist_subtitr_til.pack(side=tk.LEFT, padx=(10, 0))

        pastki = ttk.Frame(self.pleylist_tab)
        pastki.pack(fill=tk.X, side=tk.BOTTOM, pady=(14, 0))
        self.pleylist_tugmasi = ttk.Button(pastki, text="⬇️  Pleylistni yuklash", style="Muvaffaqiyat.TButton",
                                            command=self._pleylist_yuklash)
        self.pleylist_tugmasi.pack(side=tk.RIGHT)

    # ---------------- Mavzu (dark/light) ----------------

    def _mavzuni_qollash(self):
        r = QORONGI_MAVZU if self.qorongi_mi else YORUGH_MAVZU
        self.mavzu_tugmasi.config(text="☀️ Yorug'" if self.qorongi_mi else "🌙 Qorong'i")

        self.configure(bg=r["bg"])

        s = self.style
        s.configure(".", background=r["bg"], foreground=r["fg"], font=("Segoe UI", 10))
        s.configure("TFrame", background=r["bg"])
        s.configure("TLabel", background=r["bg"], foreground=r["fg"])
        s.configure("TNotebook", background=r["bg"], borderwidth=0)
        s.configure("TNotebook.Tab", background=r["ikkinchi"], foreground=r["fg"],
                    padding=(14, 8), borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", r["accent"])],
              foreground=[("selected", "#ffffff")])

        s.configure("TEntry", fieldbackground=r["entry_bg"], foreground=r["fg"],
                    insertcolor=r["fg"], borderwidth=1)
        s.configure("TCombobox", fieldbackground=r["entry_bg"], foreground=r["fg"],
                    background=r["entry_bg"], arrowcolor=r["fg"])
        s.map("TCombobox", fieldbackground=[("readonly", r["entry_bg"])],
              foreground=[("readonly", r["fg"])])
        self.option_add("*TCombobox*Listbox*Background", r["entry_bg"])
        self.option_add("*TCombobox*Listbox*Foreground", r["fg"])
        self.option_add("*TCombobox*Listbox*selectBackground", r["accent"])

        s.configure("TButton", background=r["accent"], foreground="#ffffff",
                    borderwidth=0, padding=(14, 8), font=("Segoe UI", 10, "bold"))
        s.map("TButton", background=[("active", r["accent_hover"]), ("disabled", r["disabled"])])

        s.configure("Ikkinchi.TButton", background=r["ikkinchi"], foreground=r["fg"])
        s.map("Ikkinchi.TButton", background=[("active", r["ikkinchi_hover"])])
        s.configure(
            "Thumbnail.TLabel", background=r["ikkinchi"], foreground=r["fg"],
            relief="solid", borderwidth=1,
        )

        s.configure("Muvaffaqiyat.TButton", background=r["success"], foreground="#ffffff")
        s.map("Muvaffaqiyat.TButton", background=[("active", r["success_hover"])])

        s.configure("Accent.TButton", background=r["accent"], foreground="#ffffff")
        s.map("Accent.TButton", background=[("active", r["accent_hover"])])

        s.configure("Treeview", background=r["panel"], fieldbackground=r["panel"],
                    foreground=r["fg"], borderwidth=1, rowheight=26)
        s.configure("Treeview.Heading", background=r["ikkinchi"], foreground=r["fg"],
                    borderwidth=0, font=("Segoe UI", 9, "bold"))
        s.map("Treeview", background=[("selected", r["sel_bg"])], foreground=[("selected", r["sel_fg"])])

        s.configure("TProgressbar", background=r["success"], troughcolor=r["panel"],
                    borderwidth=0, thickness=18)

        self.sarlavha_label.configure(foreground=r["fg"])
        self.kichik_label.configure(foreground=r["muted"])
        self.holat_label.configure(foreground=r["fg"])

        self.log_matn.configure(bg=r["panel"], fg=r["fg"], insertbackground=r["fg"],
                                 borderwidth=1, relief="solid")

        for tab in (self.qidiruv_tab, self.url_tab, self.pleylist_tab, self._markaziy):
            tab.configure(style="TFrame")

    def _mavzu_almashtirish(self):
        self.qorongi_mi = not self.qorongi_mi
        self.sozlamalar["qorongi"] = self.qorongi_mi
        sozlamalarni_saqlash(self.sozlamalar)
        self._mavzuni_qollash()

    # ---------------- Papka / cookie tanlash ----------------

    def _papka_tanlash(self):
        tanlangan = filedialog.askdirectory(
            title="Videolarni qayerga saqlash kerak?",
            initialdir=self.papka_maydon.get().strip() or os.path.expanduser("~"),
        )
        if tanlangan:
            self.papka_maydon.delete(0, tk.END)
            self.papka_maydon.insert(0, tanlangan)
            self.sozlamalar["papka"] = tanlangan
            sozlamalarni_saqlash(self.sozlamalar)

    def _papkani_tayyorla(self):
        papka = self.papka_maydon.get().strip() or DEFAULT_PAPKA
        os.makedirs(papka, exist_ok=True)
        return papka

    def _cookie_fayl_tanlash(self):
        tanlangan = filedialog.askopenfilename(
            title="cookies.txt faylini tanlang",
            initialdir=os.path.expanduser("~"),
            filetypes=[("Matn fayllari", "*.txt"), ("Barcha fayllar", "*.*")],
        )
        if tanlangan:
            self.cookie_maydon.delete(0, tk.END)
            self.cookie_maydon.insert(0, tanlangan)
            self.sozlamalar["cookies_fayli"] = tanlangan
            sozlamalarni_saqlash(self.sozlamalar)
            cookie_faylini_ornatish(tanlangan)
            self._log(f"Cookies fayli o'rnatildi: {tanlangan}")

    def _cookie_maydon_ozgardi(self, hodisa=None):
        yol = self.cookie_maydon.get().strip()
        self.sozlamalar["cookies_fayli"] = yol
        sozlamalarni_saqlash(self.sozlamalar)
        cookie_faylini_ornatish(yol or None)

    # ---------------- Umumiy yordamchilar ----------------

    def _log(self, matn):
        self.log_matn.configure(state="normal")
        self.log_matn.insert(tk.END, matn + "\n")
        self.log_matn.see(tk.END)
        self.log_matn.configure(state="disabled")

    def _tugmalarni_sozlash(self, band):
        holat = "disabled" if band else "normal"
        for tugma in (
            self.qidirish_tugmasi, self.tanlash_tugmasi,
            self.sifat_olish_tugmasi, self.yuklash_tugmasi,
            self.pleylist_tugmasi,
        ):
            tugma.configure(state=holat)
        # Bekor qilish tugmasi teskari mantiqda: amal ketayotganda yoniq,
        # hech narsa ishlamayotganda o'chiq.
        self.bekor_tugmasi.configure(state=("normal" if band else "disabled"))

    def _ishchini_ishga_tushirish(self, amal_turi, funksiya, *args):
        """Bitta umumiy usul: fon oqimini yaratadi va boshlaydi. Natijalar
        self.navbat orqali asosiy oqimga (Tkinter'ga xavfsiz) yetib boradi.
        Muvaffaqiyatli boshlangan bo'lsa True, band bo'lgani uchun
        boshlanmagan bo'lsa False qaytaradi (chaqiruvchi shu asosda
        holat matnini to'g'ri ko'rsatishi mumkin)."""
        if self.faol_ishchi is not None and self.faol_ishchi.is_alive():
            messagebox.showwarning(
                "Diqqat", "Hozircha boshqa amal bajarilmoqda. Iltimos, u tugashini kuting."
            )
            return False
        self.joriy_amal = amal_turi
        bekor_bayrogini_tozalash()
        signallar = Signallar(self.navbat)
        self.faol_ishchi = Ishchi(funksiya, signallar, *args)
        self._tugmalarni_sozlash(True)
        # Bekor qilish tugmasi faqat haqiqatan bekor qilib bo'ladigan
        # amallarda (yuklash turlari) yoniladi — qidirish va format
        # ma'lumotini olish yt-dlp'ning progress_hook'idan foydalanmaydi,
        # shu sabab ularni "bekor qilish" texnik jihatdan hozircha
        # ishlamaydi va tugma foydalanuvchini chalg'itmasligi kerak.
        bekor_qilinadimi = amal_turi in BEKOR_QILINADIGAN_AMALLAR
        self.bekor_tugmasi.configure(state=("normal" if bekor_qilinadimi else "disabled"))
        self.faol_ishchi.start()
        return True

    def _bekor_qilish(self):
        if self.faol_ishchi is not None and self.faol_ishchi.is_alive():
            bekor_qilishni_sorash()
            self.holat_label.configure(text="Bekor qilinmoqda...")
            self.bekor_tugmasi.configure(state="disabled")

    def _navbat_tekshirish(self):
        """Fon oqimlaridan kelgan xabarlarni davriy tekshiradi va UI'ni
        xavfsiz yangilaydi (faqat asosiy oqimda ishlaydi)."""
        try:
            while True:
                tur, payload = self.navbat.get_nowait()
                if tur == "log":
                    self._log(payload)
                elif tur == "holat":
                    self.holat_label.configure(text=payload)
                elif tur == "progress":
                    try:
                        self.progress["value"] = float(payload)
                    except (TypeError, ValueError):
                        pass
                elif tur == "qidiruv_natija":
                    self._qidiruv_natijalarini_korsat(payload)
                elif tur == "sifatlar":
                    malumot_dict, format_variantlari = payload
                    self._sifatlarni_korsat(malumot_dict, format_variantlari)
                elif tur == "thumbnail":
                    self._thumbnail_korsat(payload)
                elif tur == "xato":
                    self._xato_korsat(payload)
                elif tur == "tugadi":
                    self._tugadi(payload)
        except queue.Empty:
            pass
        self.after(100, self._navbat_tekshirish)

    def _xato_korsat(self, matn):
        messagebox.showerror("Xatolik", matn)
        self._log(f"XATO: {matn}")
        self._tugmalarni_sozlash(False)
        self.progress["value"] = 0

    def _tugadi(self, matn):
        self.holat_label.configure(text=matn)
        self.progress["value"] = 0
        self._tugmalarni_sozlash(False)
        messagebox.showinfo("Tayyor", matn)

    # ---------------- 1) Qidirish ----------------

    def _qidirishni_boshlash(self):
        soro = self.qidiruv_maydon.get().strip()
        if not soro:
            return
        # MUHIM XATO TUZATILDI: avval status "Qidirilmoqda..." deb
        # qo'yilib, keyin _ishchini_ishga_tushirish chaqirilardi — agar
        # boshqa amal band bo'lsa (False qaytsa), holat matni noto'g'ri
        # "Qidirilmoqda..." bo'lib qolib ketardi, garchi hech narsa
        # boshlanmagan bo'lsa ham. Endi status faqat muvaffaqiyatli
        # boshlanganda o'rnatiladi.
        if self._ishchini_ishga_tushirish("qidirish", vazifa_qidirish, soro):
            self.holat_label.configure(text="Qidirilmoqda...")

    def _qidiruv_natijalarini_korsat(self, natijalar):
        self.qidiruv_natijalari = natijalar
        self.qidiruv_jadval.delete(*self.qidiruv_jadval.get_children())
        for i, v in enumerate(natijalar):
            nomi = (v.get("title") or "noma'lum")[:80]
            kanal = (v.get("uploader") or v.get("channel") or "noma'lum")[:40]
            davomiylik = davomiylikni_formatlash(v.get("duration"))
            self.qidiruv_jadval.insert("", tk.END, iid=str(i), values=(nomi, kanal, davomiylik))
        self._tugmalarni_sozlash(False)

    def _qidiruvdan_video_tanlash(self):
        tanlangan_qatorlar = self.qidiruv_jadval.selection()
        if not tanlangan_qatorlar:
            messagebox.showwarning("Diqqat", "Avval ro'yxatdan bitta videoni tanlang.")
            return
        indeks = int(tanlangan_qatorlar[0])
        video = self.qidiruv_natijalari[indeks]

        # MUHIM: extract_flat="in_playlist" bilan qidirilganda ba'zan 'url' maydoni
        # to'liq havola emas, faqat video ID'sining o'zi bo'lib qaytadi. Shu sabab
        # avval 'id' asosida to'liq havola quramiz.
        video_id = video.get("id")
        if video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
        else:
            xom_url = video.get("webpage_url") or video.get("url") or ""
            if xom_url.startswith("http"):
                url = xom_url
            else:
                messagebox.showerror("Xatolik", "Bu video uchun havola aniqlanmadi.")
                return

        self.url_maydon.delete(0, tk.END)
        self.url_maydon.insert(0, url)
        self.sifat_combobox.set("")
        self.sifat_combobox.configure(values=[])
        self.tanlangan_video_url = None
        self.daftar.select(self.url_tab)
        self._url_malumot_olish()

    # ---------------- 2) URL orqali yuklash ----------------

    def _url_malumot_olish(self):
        url = self.url_maydon.get().strip()
        if not url:
            messagebox.showwarning("Diqqat", "Avval video havolasini kiriting.")
            return
        self.joriy_url = url
        # Thumbnail eski video'dan qolib ketmasligi uchun tozalanadi.
        self._thumbnail_tozalash()
        if self._ishchini_ishga_tushirish("malumot_olish", vazifa_malumot_olish, url):
            self.holat_label.configure(text="Ma'lumot olinmoqda...")

    def _thumbnail_tozalash(self):
        self.thumbnail_label.configure(image="", text="Thumbnail\nbu yerda ko'rinadi")
        self._thumbnail_rasm = None

    def _thumbnail_fon_yuklash(self, thumbnail_url):
        """Fon oqimida ishlaydi: thumbnail rasm baytlarini yt-dlp'siz,
        oddiy urllib orqali yuklab, self.navbat orqali asosiy oqimga
        (Tkinter uchun xavfsiz) yuboradi."""
        try:
            so_rov = urllib.request.Request(
                thumbnail_url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(so_rov, timeout=10) as javob:
                rasm_baytlari = javob.read()
            self.navbat.put(("thumbnail", rasm_baytlari))
        except Exception:
            self.navbat.put(("thumbnail", None))

    def _thumbnail_korsat(self, rasm_baytlari):
        if rasm_baytlari is None:
            self._thumbnail_tozalash()
            return
        if not PILLOW_MAVJUD:
            self.thumbnail_label.configure(
                image="", text="Thumbnail ko'rish uchun\nquyidagini o'rnating:\npip install pillow"
            )
            return
        try:
            rasm = Image.open(io.BytesIO(rasm_baytlari))
            rasm.thumbnail((200, 140))
            self._thumbnail_rasm = ImageTk.PhotoImage(rasm)
            self.thumbnail_label.configure(image=self._thumbnail_rasm, text="")
        except Exception:
            self._thumbnail_tozalash()

    def _sifatlarni_korsat(self, malumot_dict, format_variantlari):
        self.video_malumoti = malumot_dict
        self.format_variantlari = format_variantlari
        self.tanlangan_video_url = getattr(self, "joriy_url", self.url_maydon.get().strip())
        self.sifat_combobox.configure(values=[f["label"] for f in format_variantlari])
        if format_variantlari:
            self.sifat_combobox.current(0)
        sarlavha = malumot_dict.get("title") or "noma'lum"
        self._log(f"Video topildi: {sarlavha} ({len(format_variantlari) - 2} ta format mavjud)")
        self._tugmalarni_sozlash(False)

        # Yangi funksiya: video thumbnail'ini (rasmini) oldindan ko'rsatish.
        thumbnail_url = malumot_dict.get("thumbnail")
        if thumbnail_url:
            threading.Thread(
                target=self._thumbnail_fon_yuklash, args=(thumbnail_url,), daemon=True
            ).start()
        else:
            self._thumbnail_tozalash()

    def _url_yuklash(self):
        if not self.tanlangan_video_url:
            messagebox.showwarning("Diqqat", "Avval 'Formatlarni olish' tugmasini bosing.")
            return
        tanlov_indeks = self.sifat_combobox.current()
        if tanlov_indeks < 0:
            messagebox.showwarning("Diqqat", "Sifatni tanlang.")
            return
        try:
            papka = self._papkani_tayyorla()
        except OSError as xato:
            messagebox.showerror("Xatolik", f"Papka yaratib bo'lmadi: {xato}")
            return
        tanlangan = self.format_variantlari[tanlov_indeks]
        subtitr_sozlama = _subtitr_ydl_sozlamalarini_yasash(
            self.subtitr_yoqilgan.get(), self.subtitr_til.get()
        )
        self._ishchini_ishga_tushirish(
            "yuklash", vazifa_url_yuklash, self.tanlangan_video_url, tanlangan, papka, subtitr_sozlama
        )

    # ---------------- 3) Pleylist yuklash ----------------

    def _pleylist_yuklash(self):
        url = self.pleylist_maydon.get().strip()
        if not url:
            messagebox.showwarning("Diqqat", "Avval pleylist havolasini kiriting.")
            return
        try:
            papka = self._papkani_tayyorla()
        except OSError as xato:
            messagebox.showerror("Xatolik", f"Papka yaratib bo'lmadi: {xato}")
            return
        sifat_matn = self.pleylist_sifat.get()
        subtitr_sozlama = _subtitr_ydl_sozlamalarini_yasash(
            self.pleylist_subtitr_yoqilgan.get(), self.pleylist_subtitr_til.get()
        )
        self._ishchini_ishga_tushirish(
            "pleylist_yuklash", vazifa_pleylist_yuklash, url, sifat_matn, papka, subtitr_sozlama
        )

    # ---------------- Oynani yopish ----------------

    def _yopishni_boshqarish(self):
        """Agar fon oqimi (yuklash/qidiruv) hali ishlayotgan bo'lsa, dasturni
        to'satdan yopish xatolikka olib kelishi mumkin edi. Shu sabab avval
        foydalanuvchidan tasdiq so'raymiz."""
        if self.faol_ishchi is not None and self.faol_ishchi.is_alive():
            javob = messagebox.askyesno(
                "Amal davom etmoqda",
                "Yuklash/qidiruv hali tugamadi. Baribir chiqilsinmi?",
            )
            if not javob:
                return
            # Ishchi — daemon thread, dastur yopilganda o'zi tugaydi.
        self.destroy()


def asosiy():
    oyna = VideoYuklovchiOyna()
    oyna.mainloop()


if __name__ == "__main__":
    asosiy()

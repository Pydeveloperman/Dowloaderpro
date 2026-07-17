#!/usr/bin/env python3
"""
Video Yuklovchi GUI - YouTube, Instagram, TikTok  (PySide6 versiyasi)
=====================================================================
Zamonaviy, flat-dizaynli, dark/light mavzu almashtiriladigan interfeys orqali:
  - YouTube'da qidirish va natijadan video tanlash
  - Istalgan platformadan (YouTube/Instagram/TikTok) URL orqali yuklash
  - Pleylist to'liq yuklash
  - Saqlash papkasini "Papkani tanlash" tugmasi orqali tanlash
  - Video sifatini tanlash / faqat audio (MP3)
  - Yuklanish jarayoni progress-bar va foiz bilan ko'rsatiladi
  - Oxirgi tanlangan papka eslab qolinadi (sozlamalar.json)

O'rnatish:
    pip install -U yt-dlp
    pip install PySide6
    # ffmpeg ham kerak (video+audio birlashtirish, MP3'ga aylantirish uchun):
    #   Windows: https://ffmpeg.org/download.html dan yuklab, PATH'ga qo'shing
    #   Mac:     brew install ffmpeg
    #   Linux:   sudo apt install ffmpeg

Ishga tushirish:
    python video_yuklovchi_qt.py
"""

import os
import sys
import json

from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
    QProgressBar, QTextEdit, QFileDialog, QMessageBox, QFrame,
    QSizePolicy,
)

import yt_dlp


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
    "remote_components": ["ejs:github"],
    # Eslatma: cookiesfrombrowser bu yerda endi statik yozilmagan. YouTube
    # so'rovni "bot" deb bloklasa, dastur pastdagi _ydl_bilan_bajarish()
    # funksiyasi orqali kompyuterdagi brauzerlar (Chrome, Firefox, Edge...)
    # cookie'sini avtomatik birma-bir sinab, ishlaganini eslab qoladi.
}


# ============================================================
# SOZLAMALARNI SAQLASH / O'QISH (oxirgi tanlangan papka uchun)
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

    format_id = f.get("format_id", "?")
    ext = f.get("ext", "?")
    hajm = hajmni_formatlash(f.get("filesize") or f.get("filesize_approx"))

    if videosi_bor:
        balandlik = f.get("height")
        kenglik = f.get("width")
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
    xom_formatlar = malumot.get("formats") or []
    tayyorlangan = []
    for f in xom_formatlar:
        yorliq = format_yorlig_yasash(f)
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
    return matn


# ============================================================
# FON OQIMLARI (QThread) — signal orqali UI bilan xavfsiz aloqa
# ============================================================

class IshchiSignallari(QObject):
    log = Signal(str)
    holat = Signal(str)
    progress = Signal(float)
    qidiruv_natija = Signal(list)
    sifatlar = Signal(dict, list)
    xato = Signal(str)
    tugadi = Signal(str)


class Ishchi(QThread):
    """Har qanday uzun-davom funksiyani (qidirish, ma'lumot olish, yuklash)
    fon oqimida ishga tushiradigan umumiy klass."""

    def __init__(self, funksiya, *args, **kwargs):
        super().__init__()
        self.funksiya = funksiya
        self.args = args
        self.kwargs = kwargs
        self.signallar = IshchiSignallari()

    def run(self):
        try:
            self.funksiya(self.signallar, *self.args, **self.kwargs)
        except Exception as xato:  # kutilmagan xatolar ham UI'ga yetib borsin
            self.signallar.xato.emit(xatolik_izohi(xato))


# ---------------- Fon vazifalari (Ishchi ichida chaqiriladi) ----------------

# Kompyuterda mavjud bo'lishi mumkin bo'lgan brauzerlar — YouTube "bot" deb
# bloklaganda shular orqali cookie olishga urinib ko'ramiz.
_SINALADIGAN_BROUZERLAR = ["chrome", "edge", "firefox", "brave", "chromium", "vivaldi", "opera"]

# "ANIQLANMAGAN" — hali birorta ham brauzer sinalmagan.
# Bror brauzer nomi — o'sha ishlagani va endi doim shu ishlatiladi.
# None — barcha brauzerlar sinalgan, lekin birortasi ham ishlamagan.
_ishlaydigan_brouzer = "ANIQLANMAGAN"

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
        "3) Agar VPN/proksi ishlatayotgan bo'lsangiz (Kali Linux'da odatiy "
        "hol) — YouTube ba'zan IP manzilning o'zini shubhali deb bloklaydi, "
        "cookie'dan qat'i nazar. VPN'ni o'chirib qayta urinib ko'ring."
    )


def vazifa_qidirish(signallar, soro):
    sozlamalar = {
        "extract_flat": "in_playlist",
        "default_search": "ytsearch10",
    }
    try:
        natija = _ydl_bilan_bajarish(sozlamalar, lambda ydl: ydl.extract_info(soro, download=False))
        videolar = [v for v in (natija.get("entries") or []) if v]
        signallar.qidiruv_natija.emit(videolar)
        signallar.holat.emit(f"{len(videolar)} ta natija topildi." if videolar else "Hech narsa topilmadi.")
    except Exception as xato:
        signallar.xato.emit(xatolik_izohi(xato))
        signallar.holat.emit("Qidirishda xatolik.")


def vazifa_malumot_olish(signallar, url):
    try:
        malumot = _ydl_bilan_bajarish({}, lambda ydl: ydl.extract_info(url, download=False))
        if malumot.get("_type") in ("playlist", "multi_video"):
            signallar.xato.emit(
                "Bu havola pleylist ko'rinadi. Pleylist yuklash uchun "
                "'Pleylist yuklash' tabidan foydalaning."
            )
            signallar.holat.emit("Bu pleylist havolasi.")
            return
        format_variantlari = barcha_formatlarni_tayyorla(malumot)
        signallar.sifatlar.emit(malumot, format_variantlari)
        signallar.holat.emit("Formatlar yuklandi. Endi kerakli formatni tanlab yuklang.")
    except Exception as xato:
        signallar.xato.emit(xatolik_izohi(xato))
        signallar.holat.emit("Ma'lumot olishda xatolik.")


def _progress_hook_yasash(signallar):
    def hook(d):
        if d["status"] == "downloading":
            foiz_str = (d.get("_percent_str") or "0%").strip().replace("%", "")
            try:
                foiz = float(foiz_str)
            except ValueError:
                foiz = 0
            signallar.progress.emit(foiz)
            tezlik = (d.get("_speed_str") or "").strip()
            signallar.holat.emit(f"Yuklanmoqda: {foiz_str}%  |  Tezlik: {tezlik}")
        elif d["status"] == "finished":
            signallar.holat.emit("Yuklab olindi, qayta ishlanmoqda (ffmpeg)...")
            signallar.progress.emit(100)
    return hook


def vazifa_url_yuklash(signallar, url, tanlangan, papka):
    try:
        asosiy_sozlama = {
            "outtmpl": os.path.join(papka, "%(title)s.%(ext)s"),
            "progress_hooks": [_progress_hook_yasash(signallar)],
        }

        if tanlangan["kind"] == "mp3":
            sozlamalar = {
                **asosiy_sozlama,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192",
                }],
            }
            signallar.holat.emit("Audio (MP3) sifatida yuklanmoqda...")
        elif tanlangan["kind"] == "auto":
            sozlamalar = {
                **asosiy_sozlama,
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
            }
            signallar.holat.emit("Eng yaxshi sifatda yuklanmoqda...")
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
            signallar.holat.emit(f"[{format_id}] formatida yuklanmoqda...")

        try:
            _ydl_bilan_bajarish(sozlamalar, lambda ydl: ydl.download([url]))
        except yt_dlp.utils.DownloadError as birinchi_xato:
            if "Requested format is not available" in str(birinchi_xato):
                # Tanlangan aniq format endi ishlamayapti — avtomatik
                # eng yaxshi sifatga o'tib, qayta urinib ko'ramiz.
                signallar.holat.emit(
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
        signallar.tugadi.emit(f"Tayyor! '{papka}' papkasiga saqlandi.")
    except Exception as xato:
        signallar.xato.emit(xatolik_izohi(xato))
        signallar.holat.emit("Yuklashda xatolik.")


def vazifa_pleylist_yuklash(signallar, url, sifat_matn, papka):
    pleylist_papka = os.path.join(papka, "%(playlist_title)s")
    try:
        if sifat_matn.startswith("Faqat audio"):
            sozlamalar = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(pleylist_papka, "%(title)s.%(ext)s"),
                "progress_hooks": [_progress_hook_yasash(signallar)],
                "postprocessors": [{
                    "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192",
                }],
            }
        else:
            balandlik = int(sifat_matn.split("p")[0])
            sozlamalar = {
                "format": f"bestvideo[height<={balandlik}]+bestaudio/best[height<={balandlik}]",
                "outtmpl": os.path.join(pleylist_papka, "%(title)s.%(ext)s"),
                "progress_hooks": [_progress_hook_yasash(signallar)],
                "merge_output_format": "mp4",
            }

        sozlamalar["ignoreerrors"] = "only_download"

        signallar.holat.emit("Pleylist yuklanmoqda, biroz vaqt olishi mumkin...")
        _ydl_bilan_bajarish(sozlamalar, lambda ydl: ydl.download([url]))
        signallar.tugadi.emit(f"Pleylist to'liq yuklandi! '{papka}' papkasini tekshiring.")
    except Exception as xato:
        signallar.xato.emit(xatolik_izohi(xato))
        signallar.holat.emit("Pleylist yuklashda xatolik.")


# ============================================================
# MAVZULAR (QSS) — yorug' va qorong'i
# ============================================================

YORUGH_MAVZU = """
QWidget { background-color: #f5f6fa; color: #1c1e21; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QMainWindow { background-color: #f5f6fa; }
QLineEdit, QComboBox, QTextEdit {
    background-color: #ffffff; border: 1px solid #d7dbe0; border-radius: 8px;
    padding: 7px 10px; selection-background-color: #4f8cff;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #4f8cff; }
QPushButton {
    background-color: #4f8cff; color: white; border: none; border-radius: 8px;
    padding: 8px 16px; font-weight: 600;
}
QPushButton:hover { background-color: #3d7bef; }
QPushButton:pressed { background-color: #2f68d8; }
QPushButton:disabled { background-color: #b7c6e6; color: #eef2fb; }
QPushButton#ikkinchi { background-color: #e7eaf0; color: #1c1e21; }
QPushButton#ikkinchi:hover { background-color: #dde1e9; }
QPushButton#muvaffaqiyat { background-color: #34c38f; }
QPushButton#muvaffaqiyat:hover { background-color: #2aab7c; }
QTabWidget::pane { border: 1px solid #d7dbe0; border-radius: 10px; background: #ffffff; top: -1px; }
QTabBar::tab {
    background: transparent; padding: 9px 18px; margin-right: 4px; border-radius: 8px;
    color: #5a6270; font-weight: 600;
}
QTabBar::tab:selected { background: #4f8cff; color: white; }
QTabBar::tab:hover:!selected { background: #e7eaf0; }
QTableWidget {
    background-color: #ffffff; border: 1px solid #e2e5eb; border-radius: 8px;
    gridline-color: #eef0f4; alternate-background-color: #f7f9fc;
}
QHeaderView::section {
    background-color: #eef1f6; color: #444b57; padding: 6px; border: none; font-weight: 600;
}
QProgressBar { border: 1px solid #d7dbe0; border-radius: 8px; text-align: center; height: 18px; background: #ffffff; }
QProgressBar::chunk { background-color: #34c38f; border-radius: 7px; }
QLabel#sarlavha { font-size: 20px; font-weight: 700; }
QLabel#sarlavha_kichik { color: #7a8291; }
QFrame#chiziq { background-color: #e2e5eb; max-height: 1px; }
"""

QORONGI_MAVZU = """
QWidget { background-color: #1b1d23; color: #e6e8ec; font-family: 'Segoe UI', sans-serif; font-size: 13px; }
QMainWindow { background-color: #1b1d23; }
QLineEdit, QComboBox, QTextEdit {
    background-color: #262933; border: 1px solid #383c47; border-radius: 8px;
    padding: 7px 10px; color: #e6e8ec; selection-background-color: #5a8dee;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #5a8dee; }
QPushButton {
    background-color: #5a8dee; color: white; border: none; border-radius: 8px;
    padding: 8px 16px; font-weight: 600;
}
QPushButton:hover { background-color: #4a7de0; }
QPushButton:pressed { background-color: #3c6bc9; }
QPushButton:disabled { background-color: #33405e; color: #7a86a3; }
QPushButton#ikkinchi { background-color: #2d3039; color: #e6e8ec; }
QPushButton#ikkinchi:hover { background-color: #383c47; }
QPushButton#muvaffaqiyat { background-color: #2fbf8a; }
QPushButton#muvaffaqiyat:hover { background-color: #26a878; }
QTabWidget::pane { border: 1px solid #383c47; border-radius: 10px; background: #22252d; top: -1px; }
QTabBar::tab {
    background: transparent; padding: 9px 18px; margin-right: 4px; border-radius: 8px;
    color: #9aa1b0; font-weight: 600;
}
QTabBar::tab:selected { background: #5a8dee; color: white; }
QTabBar::tab:hover:!selected { background: #2d3039; }
QTableWidget {
    background-color: #22252d; border: 1px solid #383c47; border-radius: 8px;
    gridline-color: #2d3039; alternate-background-color: #262933; color: #e6e8ec;
}
QHeaderView::section {
    background-color: #2d3039; color: #c7cbd6; padding: 6px; border: none; font-weight: 600;
}
QProgressBar { border: 1px solid #383c47; border-radius: 8px; text-align: center; height: 18px;
    background: #262933; color: #e6e8ec; }
QProgressBar::chunk { background-color: #2fbf8a; border-radius: 7px; }
QLabel#sarlavha { font-size: 20px; font-weight: 700; color: #ffffff; }
QLabel#sarlavha_kichik { color: #9aa1b0; }
QFrame#chiziq { background-color: #383c47; max-height: 1px; }
"""


# ============================================================
# ASOSIY OYNA
# ============================================================

class VideoYuklovchiOyna(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Yuklovchi — YouTube / Instagram / TikTok")
        self.resize(960, 720)
        self.setMinimumSize(780, 580)

        self.sozlamalar = sozlamalarni_oqish()
        self.saqlash_papkasi = self.sozlamalar.get("papka", DEFAULT_PAPKA)
        self.qorongi_mi = self.sozlamalar.get("qorongi", False)

        self.qidiruv_natijalari = []
        self.tanlangan_video_url = None
        self.format_variantlari = []
        self.video_malumoti = None
        self.faol_ishchi = None  # bir vaqtda bitta fon oqimi

        self._ui_yaratish()
        self._mavzuni_qollash()

    # ---------------- UI qurish ----------------

    def _ui_yaratish(self):
        markaziy = QWidget()
        self.setCentralWidget(markaziy)
        asosiy_lay = QVBoxLayout(markaziy)
        asosiy_lay.setContentsMargins(18, 16, 18, 14)
        asosiy_lay.setSpacing(10)

        # ---------- Sarlavha ----------
        header_lay = QHBoxLayout()
        sarlavha_ustun = QVBoxLayout()
        sarlavha = QLabel("🎬 Video Yuklovchi")
        sarlavha.setObjectName("sarlavha")
        kichik = QLabel("YouTube · Instagram · TikTok")
        kichik.setObjectName("sarlavha_kichik")
        sarlavha_ustun.addWidget(sarlavha)
        sarlavha_ustun.addWidget(kichik)
        header_lay.addLayout(sarlavha_ustun)
        header_lay.addStretch(1)

        self.mavzu_tugmasi = QPushButton()
        self.mavzu_tugmasi.setObjectName("ikkinchi")
        self.mavzu_tugmasi.setFixedWidth(130)
        self.mavzu_tugmasi.clicked.connect(self._mavzu_almashtirish)
        header_lay.addWidget(self.mavzu_tugmasi, alignment=Qt.AlignTop)
        asosiy_lay.addLayout(header_lay)

        chiziq = QFrame()
        chiziq.setObjectName("chiziq")
        chiziq.setFrameShape(QFrame.HLine)
        asosiy_lay.addWidget(chiziq)

        # ---------- Papka tanlash ----------
        papka_sarlavha = QLabel("📁 Saqlash papkasi")
        papka_sarlavha.setStyleSheet("font-weight: 600;")
        asosiy_lay.addWidget(papka_sarlavha)

        papka_lay = QHBoxLayout()
        self.papka_maydon = QLineEdit(self.saqlash_papkasi)
        papka_tanlash_tugmasi = QPushButton("Papkani tanlash...")
        papka_tanlash_tugmasi.setObjectName("ikkinchi")
        papka_tanlash_tugmasi.clicked.connect(self._papka_tanlash)
        papka_lay.addWidget(self.papka_maydon, 1)
        papka_lay.addWidget(papka_tanlash_tugmasi)
        asosiy_lay.addLayout(papka_lay)

        # ---------- Cookies fayli (YouTube "bot" bloki uchun) ----------
        cookie_sarlavha = QLabel("🍪 Cookies fayli (ixtiyoriy — 'bot' bloklansa kerak bo'ladi)")
        cookie_sarlavha.setStyleSheet("font-weight: 600;")
        asosiy_lay.addWidget(cookie_sarlavha)

        cookie_lay = QHBoxLayout()
        self.cookie_maydon = QLineEdit(self.sozlamalar.get("cookies_fayli", ""))
        self.cookie_maydon.setPlaceholderText(
            "Masalan: youtube_cookies.txt (brauzer kengaytmasi orqali eksport qiling)"
        )
        cookie_tanlash_tugmasi = QPushButton("Faylni tanlash...")
        cookie_tanlash_tugmasi.setObjectName("ikkinchi")
        cookie_tanlash_tugmasi.clicked.connect(self._cookie_fayl_tanlash)
        cookie_lay.addWidget(self.cookie_maydon, 1)
        cookie_lay.addWidget(cookie_tanlash_tugmasi)
        asosiy_lay.addLayout(cookie_lay)
        self.cookie_maydon.editingFinished.connect(self._cookie_maydon_ozgardi)
        cookie_faylini_ornatish(self.cookie_maydon.text().strip() or None)

        # ---------- Tablar ----------
        self.daftar = QTabWidget()
        self._qidiruv_tab_yaratish()
        self._url_tab_yaratish()
        self._pleylist_tab_yaratish()
        self.daftar.addTab(self.qidiruv_tab, "🔍  YouTube'da qidirish")
        self.daftar.addTab(self.url_tab, "🔗  Havola orqali yuklash")
        self.daftar.addTab(self.pleylist_tab, "📋  Pleylist yuklash")
        asosiy_lay.addWidget(self.daftar, 1)

        # ---------- Progress + holat + log ----------
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        asosiy_lay.addWidget(self.progress)

        self.holat_label = QLabel("Tayyor.")
        asosiy_lay.addWidget(self.holat_label)

        self.log_matn = QTextEdit()
        self.log_matn.setReadOnly(True)
        self.log_matn.setFixedHeight(110)
        self.log_matn.setFont(QFont("Consolas", 9))
        asosiy_lay.addWidget(self.log_matn)

    def _qidiruv_tab_yaratish(self):
        self.qidiruv_tab = QWidget()
        lay = QVBoxLayout(self.qidiruv_tab)
        lay.setContentsMargins(16, 16, 16, 16)

        top = QHBoxLayout()
        self.qidiruv_maydon = QLineEdit()
        self.qidiruv_maydon.setPlaceholderText("Qidiruv so'zini kiriting...")
        self.qidiruv_maydon.returnPressed.connect(self._qidirishni_boshlash)
        self.qidirish_tugmasi = QPushButton("🔍 Qidirish")
        self.qidirish_tugmasi.clicked.connect(self._qidirishni_boshlash)
        top.addWidget(self.qidiruv_maydon, 1)
        top.addWidget(self.qidirish_tugmasi)
        lay.addLayout(top)

        self.qidiruv_jadval = QTableWidget(0, 3)
        self.qidiruv_jadval.setHorizontalHeaderLabels(["Nomi", "Kanal", "Davomiylik"])
        self.qidiruv_jadval.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.qidiruv_jadval.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.qidiruv_jadval.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.qidiruv_jadval.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.qidiruv_jadval.setSelectionMode(QAbstractItemView.SingleSelection)
        self.qidiruv_jadval.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.qidiruv_jadval.setAlternatingRowColors(True)
        self.qidiruv_jadval.verticalHeader().setVisible(False)
        self.qidiruv_jadval.doubleClicked.connect(self._qidiruvdan_video_tanlash)
        lay.addWidget(self.qidiruv_jadval, 1)

        pastki = QHBoxLayout()
        pastki.addStretch(1)
        self.tanlash_tugmasi = QPushButton("⬇️  Tanlangan videoni yuklash")
        self.tanlash_tugmasi.setObjectName("muvaffaqiyat")
        self.tanlash_tugmasi.clicked.connect(self._qidiruvdan_video_tanlash)
        pastki.addWidget(self.tanlash_tugmasi)
        lay.addLayout(pastki)

    def _url_tab_yaratish(self):
        self.url_tab = QWidget()
        lay = QVBoxLayout(self.url_tab)
        lay.setContentsMargins(16, 16, 16, 16)

        sarlavha = QLabel("Video havolasi (YouTube / Instagram / TikTok)")
        sarlavha.setStyleSheet("font-weight: 600;")
        lay.addWidget(sarlavha)

        top = QHBoxLayout()
        self.url_maydon = QLineEdit()
        self.url_maydon.setPlaceholderText("https://...")
        self.sifat_olish_tugmasi = QPushButton("Formatlarni olish")
        self.sifat_olish_tugmasi.clicked.connect(self._url_malumot_olish)
        top.addWidget(self.url_maydon, 1)
        top.addWidget(self.sifat_olish_tugmasi)
        lay.addLayout(top)

        lay.addSpacing(6)
        sifat_sarlavha = QLabel("🎚️ Mavjud formatlar")
        sifat_sarlavha.setStyleSheet("font-weight: 600;")
        lay.addWidget(sifat_sarlavha)

        self.sifat_combobox = QComboBox()
        lay.addWidget(self.sifat_combobox)

        lay.addStretch(1)
        pastki = QHBoxLayout()
        pastki.addStretch(1)
        self.yuklash_tugmasi = QPushButton("⬇️  Yuklab olish")
        self.yuklash_tugmasi.setObjectName("muvaffaqiyat")
        self.yuklash_tugmasi.clicked.connect(self._url_yuklash)
        pastki.addWidget(self.yuklash_tugmasi)
        lay.addLayout(pastki)

    def _pleylist_tab_yaratish(self):
        self.pleylist_tab = QWidget()
        lay = QVBoxLayout(self.pleylist_tab)
        lay.setContentsMargins(16, 16, 16, 16)

        sarlavha = QLabel("Pleylist havolasi")
        sarlavha.setStyleSheet("font-weight: 600;")
        lay.addWidget(sarlavha)

        self.pleylist_maydon = QLineEdit()
        self.pleylist_maydon.setPlaceholderText("https://...")
        lay.addWidget(self.pleylist_maydon)

        lay.addSpacing(6)
        sifat_sarlavha = QLabel("🎚️ Sifat")
        sifat_sarlavha.setStyleSheet("font-weight: 600;")
        lay.addWidget(sifat_sarlavha)

        self.pleylist_sifat = QComboBox()
        self.pleylist_sifat.addItems(
            ["1080p (Full HD)", "720p (HD)", "480p (O'rta sifat)", "Faqat audio (MP3)"]
        )
        self.pleylist_sifat.setCurrentText("720p (HD)")
        lay.addWidget(self.pleylist_sifat)

        lay.addStretch(1)
        pastki = QHBoxLayout()
        pastki.addStretch(1)
        self.pleylist_tugmasi = QPushButton("⬇️  Pleylistni yuklash")
        self.pleylist_tugmasi.setObjectName("muvaffaqiyat")
        self.pleylist_tugmasi.clicked.connect(self._pleylist_yuklash)
        pastki.addWidget(self.pleylist_tugmasi)
        lay.addLayout(pastki)

    # ---------------- Oynani yopish ----------------

    def closeEvent(self, event):
        """Agar fon oqimi (yuklash/qidiruv) hali ishlayotgan bo'lsa, dasturni
        to'satdan yopish 'QThread: Destroyed while thread is running' kabi
        xatolik yoki qulashga olib kelishi mumkin edi. Shu sabab avval
        foydalanuvchidan tasdiq so'raymiz, so'ng oqim tugashini kutamiz."""
        if self.faol_ishchi is not None and self.faol_ishchi.isRunning():
            javob = QMessageBox.question(
                self, "Amal davom etmoqda",
                "Yuklash/qidiruv hali tugamadi. Baribir chiqilsinmi?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if javob != QMessageBox.Yes:
                event.ignore()
                return
            self.faol_ishchi.requestInterruption()
            self.faol_ishchi.quit()
            self.faol_ishchi.wait(3000)
        event.accept()

    # ---------------- Mavzu (dark/light) ----------------

    def _mavzuni_qollash(self):
        if self.qorongi_mi:
            self.setStyleSheet(QORONGI_MAVZU)
            self.mavzu_tugmasi.setText("☀️ Yorug'")
        else:
            self.setStyleSheet(YORUGH_MAVZU)
            self.mavzu_tugmasi.setText("🌙 Qorong'i")

    def _mavzu_almashtirish(self):
        self.qorongi_mi = not self.qorongi_mi
        self.sozlamalar["qorongi"] = self.qorongi_mi
        sozlamalarni_saqlash(self.sozlamalar)
        self._mavzuni_qollash()

    # ---------------- Papka tanlash ----------------

    def _papka_tanlash(self):
        tanlangan = QFileDialog.getExistingDirectory(
            self, "Videolarni qayerga saqlash kerak?",
            self.papka_maydon.text().strip() or os.path.expanduser("~"),
        )
        if tanlangan:
            self.papka_maydon.setText(tanlangan)
            self.sozlamalar["papka"] = tanlangan
            sozlamalarni_saqlash(self.sozlamalar)

    def _papkani_tayyorla(self):
        papka = self.papka_maydon.text().strip() or DEFAULT_PAPKA
        os.makedirs(papka, exist_ok=True)
        return papka

    def _cookie_fayl_tanlash(self):
        tanlangan, _ = QFileDialog.getOpenFileName(
            self, "cookies.txt faylini tanlang",
            os.path.expanduser("~"), "Matn fayllari (*.txt);;Barcha fayllar (*)",
        )
        if tanlangan:
            self.cookie_maydon.setText(tanlangan)
            self.sozlamalar["cookies_fayli"] = tanlangan
            sozlamalarni_saqlash(self.sozlamalar)
            cookie_faylini_ornatish(tanlangan)
            self._log(f"Cookies fayli o'rnatildi: {tanlangan}")

    def _cookie_maydon_ozgardi(self):
        yol = self.cookie_maydon.text().strip()
        self.sozlamalar["cookies_fayli"] = yol
        sozlamalarni_saqlash(self.sozlamalar)
        cookie_faylini_ornatish(yol or None)

    # ---------------- Umumiy yordamchilar ----------------

    def _log(self, matn):
        self.log_matn.append(matn)

    def _tugmalarni_sozlash(self, band):
        holat = not band
        for tugma in (
            self.qidirish_tugmasi, self.tanlash_tugmasi,
            self.sifat_olish_tugmasi, self.yuklash_tugmasi,
            self.pleylist_tugmasi,
        ):
            tugma.setEnabled(holat)

    def _ishchini_ishga_tushirish(self, funksiya, *args):
        """Bitta umumiy usul: fon oqimini yaratadi, signallarni ulaydi va boshlaydi."""
        if self.faol_ishchi is not None and self.faol_ishchi.isRunning():
            QMessageBox.warning(
                self, "Diqqat",
                "Hozircha boshqa amal bajarilmoqda. Iltimos, u tugashini kuting."
            )
            return None
        self.faol_ishchi = Ishchi(funksiya, *args)
        s = self.faol_ishchi.signallar
        s.log.connect(self._log)
        s.holat.connect(self.holat_label.setText)
        s.progress.connect(lambda f: self.progress.setValue(int(f)))
        s.xato.connect(self._xato_korsat)
        s.tugadi.connect(self._tugadi)
        self._tugmalarni_sozlash(True)
        self.faol_ishchi.start()
        return s

    def _xato_korsat(self, matn):
        QMessageBox.critical(self, "Xatolik", matn)
        self._log(f"XATO: {matn}")
        self._tugmalarni_sozlash(False)
        self.progress.setValue(0)

    def _tugadi(self, matn):
        self.holat_label.setText(matn)
        self.progress.setValue(0)
        self._tugmalarni_sozlash(False)
        QMessageBox.information(self, "Tayyor", matn)

    # ---------------- 1) Qidirish ----------------

    def _qidirishni_boshlash(self):
        soro = self.qidiruv_maydon.text().strip()
        if not soro:
            return
        self.holat_label.setText("Qidirilmoqda...")
        s = self._ishchini_ishga_tushirish(vazifa_qidirish, soro)
        if s is None:
            return
        s.qidiruv_natija.connect(self._qidiruv_natijalarini_korsat)

    def _qidiruv_natijalarini_korsat(self, natijalar):
        self.qidiruv_natijalari = natijalar
        self.qidiruv_jadval.setRowCount(0)
        for v in natijalar:
            qator = self.qidiruv_jadval.rowCount()
            self.qidiruv_jadval.insertRow(qator)
            self.qidiruv_jadval.setItem(qator, 0, QTableWidgetItem((v.get("title") or "noma'lum")[:80]))
            self.qidiruv_jadval.setItem(
                qator, 1, QTableWidgetItem((v.get("uploader") or v.get("channel") or "noma'lum")[:40])
            )
            self.qidiruv_jadval.setItem(qator, 2, QTableWidgetItem(davomiylikni_formatlash(v.get("duration"))))
        self._tugmalarni_sozlash(False)

    def _qidiruvdan_video_tanlash(self):
        tanlangan_qatorlar = self.qidiruv_jadval.selectionModel().selectedRows()
        if not tanlangan_qatorlar:
            QMessageBox.warning(self, "Diqqat", "Avval ro'yxatdan bitta videoni tanlang.")
            return
        indeks = tanlangan_qatorlar[0].row()
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
                QMessageBox.critical(self, "Xatolik", "Bu video uchun havola aniqlanmadi.")
                return

        self.url_maydon.setText(url)
        self.sifat_combobox.clear()
        self.tanlangan_video_url = None
        self.daftar.setCurrentWidget(self.url_tab)
        self._url_malumot_olish()

    # ---------------- 2) URL orqali yuklash ----------------

    def _url_malumot_olish(self):
        url = self.url_maydon.text().strip()
        if not url:
            QMessageBox.warning(self, "Diqqat", "Avval video havolasini kiriting.")
            return
        self.holat_label.setText("Ma'lumot olinmoqda...")
        s = self._ishchini_ishga_tushirish(vazifa_malumot_olish, url)
        if s is None:
            return
        s.sifatlar.connect(lambda m, f: self._sifatlarni_korsat(m, f, url))

    def _sifatlarni_korsat(self, malumot_dict, format_variantlari, url):
        self.video_malumoti = malumot_dict
        self.format_variantlari = format_variantlari
        self.tanlangan_video_url = url
        self.sifat_combobox.clear()
        self.sifat_combobox.addItems([f["label"] for f in format_variantlari])
        if format_variantlari:
            self.sifat_combobox.setCurrentIndex(0)
        sarlavha = malumot_dict.get("title") or "noma'lum"
        self._log(f"Video topildi: {sarlavha} ({len(format_variantlari) - 2} ta format mavjud)")
        self._tugmalarni_sozlash(False)

    def _url_yuklash(self):
        if not self.tanlangan_video_url:
            QMessageBox.warning(self, "Diqqat", "Avval 'Formatlarni olish' tugmasini bosing.")
            return
        tanlov_indeks = self.sifat_combobox.currentIndex()
        if tanlov_indeks < 0:
            QMessageBox.warning(self, "Diqqat", "Sifatni tanlang.")
            return
        try:
            papka = self._papkani_tayyorla()
        except OSError as xato:
            QMessageBox.critical(self, "Xatolik", f"Papka yaratib bo'lmadi: {xato}")
            return
        tanlangan = self.format_variantlari[tanlov_indeks]
        self._ishchini_ishga_tushirish(vazifa_url_yuklash, self.tanlangan_video_url, tanlangan, papka)

    # ---------------- 3) Pleylist yuklash ----------------

    def _pleylist_yuklash(self):
        url = self.pleylist_maydon.text().strip()
        if not url:
            QMessageBox.warning(self, "Diqqat", "Avval pleylist havolasini kiriting.")
            return
        try:
            papka = self._papkani_tayyorla()
        except OSError as xato:
            QMessageBox.critical(self, "Xatolik", f"Papka yaratib bo'lmadi: {xato}")
            return
        sifat_matn = self.pleylist_sifat.currentText()
        self._ishchini_ishga_tushirish(vazifa_pleylist_yuklash, url, sifat_matn, papka)


def asosiy():
    ilova = QApplication(sys.argv)
    ilova.setApplicationName("Video Yuklovchi")
    oyna = VideoYuklovchiOyna()
    oyna.show()
    sys.exit(ilova.exec())


if __name__ == "__main__":
    asosiy()

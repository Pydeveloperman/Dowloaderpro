#!/usr/bin/env bash
# ============================================================
# Video Yuklovchi GUI (PySide6) - venv orqali 0'dan o'rnatish skripti
# ============================================================
# Ishlatish:
#   chmod +x install.sh
#   ./install.sh
#
# Bu skript:
#   1) .venv nomli virtual muhitni 0'dan yaratadi
#   2) pip'ni yangilaydi, yt-dlp va PySide6'ni o'rnatadi
#   3) ffmpeg mavjudligini tekshiradi (yo'q bo'lsa ogohlantiradi)
#   4) panel.py dasturini ishga tushiradi
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

VENV_DIR=".venv"
PY_FAYL="panel.py"

echo "=================================================="
echo " Video Yuklovchi GUI (PySide6) - o'rnatish"
echo "=================================================="

# ---- 1) Python mavjudligini tekshirish ----
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "XATOLIK: Python topilmadi. Avval Python 3'ni o'rnating."
    exit 1
fi
echo "-> Python: $($PYTHON_BIN --version)"

# ---- 2) ffmpeg mavjudligini tekshirish ----
if ! command -v ffmpeg &>/dev/null; then
    echo ""
    echo "OGOHLANTIRISH: ffmpeg topilmadi (video/audio birlashtirish, MP3'ga"
    echo "aylantirish uchun kerak). O'rnating:"
    echo "   Debian/Ubuntu/Kali: sudo apt install ffmpeg"
    echo "   macOS (brew):       brew install ffmpeg"
    echo ""
fi

# ---- 3) Venv yaratish (har doim 0'dan) ----
if [ -d "$VENV_DIR" ]; then
    echo "-> Eski virtual muhit topildi, 0'dan qayta yaratilmoqda..."
    rm -rf "$VENV_DIR"
fi

echo "-> Virtual muhit yaratilmoqda: $VENV_DIR"
$PYTHON_BIN -m venv "$VENV_DIR"

# ---- 4) Venv faollashtirish ----
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "-> pip yangilanmoqda..."
pip install --upgrade pip --quiet

echo "-> yt-dlp o'rnatilmoqda..."
pip install --upgrade yt-dlp --quiet

echo "-> PySide6 o'rnatilmoqda (biroz vaqt olishi mumkin)..."
pip install --upgrade PySide6 --quiet

echo ""
echo "-> O'rnatilgan yt-dlp versiyasi: $(python -c 'import yt_dlp; print(yt_dlp.version.__version__)')"
echo "-> O'rnatilgan PySide6 versiyasi: $(python -c 'import PySide6; print(PySide6.__version__)')"

# ---- 5) Dasturni ishga tushirish ----
if [ ! -f "$PY_FAYL" ]; then
    echo "XATOLIK: $PY_FAYL fayli shu papkada topilmadi ($SCRIPT_DIR)."
    echo "Faylni install.sh bilan bir papkaga qo'ying."
    deactivate
    exit 1
fi

echo ""
echo "=================================================="
echo " Dastur ishga tushirilmoqda: $PY_FAYL"
echo "=================================================="
python "$PY_FAYL"

deactivate

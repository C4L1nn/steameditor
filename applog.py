"""applog.py — Steam Splitter PRO ortak log altyapısı.

Tüm modüller print() yerine buradan logger alır. Loglar hem konsola hem
steam_splitter.log dosyasına (döner, en fazla ~1.5MB) yazılır — uygulama
pythonw ile (konsolsuz) açıldığında hatalar artık kaybolmaz.
"""
import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_splitter.log")
_FMT_FILE = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                              datefmt="%Y-%m-%d %H:%M:%S")
_FMT_CONSOLE = logging.Formatter("%(message)s")


def get_logger(name: str = "splitter") -> logging.Logger:
    logger = logging.getLogger(f"steamsplitter.{name}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        fh = RotatingFileHandler(_LOG_FILE, maxBytes=512 * 1024,
                                 backupCount=2, encoding="utf-8")
        fh.setFormatter(_FMT_FILE)
        logger.addHandler(fh)
    except Exception:
        pass  # log dosyası açılamazsa (izin vb.) konsolla devam
    ch = logging.StreamHandler()
    ch.setFormatter(_FMT_CONSOLE)
    logger.addHandler(ch)
    return logger

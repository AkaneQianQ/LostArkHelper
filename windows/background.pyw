"""Windowless entry point; keep diagnostics private and bounded."""
import ctypes
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

root = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'LostArkHelper'
root.mkdir(parents=True, exist_ok=True)
logger = logging.getLogger('launcher')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(root / 'service.log', maxBytes=1024*1024, backupCount=2, encoding='utf-8')
logger.addHandler(handler)

class LogStream:
    def write(self, text):
        if text.strip():
            logger.info(text.rstrip())
    def flush(self):
        handler.flush()
    def isatty(self):
        return False

sys.stdout = sys.stderr = LogStream()
try:
    import launcher
    raise SystemExit(launcher.main())
except Exception as exc:
    # Never dump exception values or locals, which can contain credentials.
    logger.error('Startup failed (%s)', type(exc).__name__)
    if os.name == 'nt':
        ctypes.windll.user32.MessageBoxW(None, '本地服务启动失败。请查看 %LOCALAPPDATA%\\LostArkHelper\\service.log，或运行调试启动脚本。', '命运方舟助手', 16)
    raise SystemExit(1)

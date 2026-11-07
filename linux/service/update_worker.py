"""旧服务退出后安装已校验的更新，并保留旧目录供恢复。"""
import contextlib
import json
from pathlib import Path
import subprocess
import sys
import time

import platform_lock
import updater


def main():
    if len(sys.argv) != 3:
        return 2
    root = Path(sys.argv[1]).resolve()
    executable = Path(sys.argv[2]).resolve()
    with root.joinpath('update.log').open('a', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            return install(root, executable)
        except Exception as exc:
            print('更新失败：{} {}'.format(type(exc).__name__, str(exc)[:300]), flush=True)
            return 1


def install(root, executable):
    for _ in range(120):
        if not root.joinpath('instance.json').exists():
            break
        time.sleep(0.5)
    else:
        print('旧服务未正常退出，已取消更新；旧版本保留。', flush=True)
        return 1
    lock = updater.InstallLock(root)
    if not lock.acquire():
        return 1
    try:
        metadata = json.loads(root.joinpath('update-download.json').read_text(encoding='utf-8'))
        archive = root.joinpath('update-download.bin').read_bytes()
        try:
            updater.apply_downloaded(archive, metadata['name'], root, executable)
        except Exception:
            print('更新安装失败，正在恢复原版本。', flush=True)
            subprocess.Popen([str(executable), '--no-browser'], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            raise
    finally:
        lock.release()
        for name in ('update-download.json', 'update-download.bin'):
            root.joinpath(name).unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

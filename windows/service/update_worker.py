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
    # Windows 的更新进程没有控制台；私有日志用于定位替换失败，不记录账号或压缩包内容。
    with root.joinpath('update.log').open('a', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            return install(root, executable)
        except Exception as exc:
            print('Update failed: {} {}'.format(type(exc).__name__, str(exc)[:300]), flush=True)
            return 1


def install(root, executable):
    root = Path(root).resolve()
    executable = Path(executable).resolve()
    try:
        for _ in range(120):
            if not root.joinpath('instance.json').exists():
                break
            time.sleep(0.5)
        else:
            print('Old service did not exit; update cancelled.', flush=True)
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
                print('Installation failed; restarting previous version.', flush=True)
                subprocess.Popen([str(executable), '--no-browser'], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0),
                                 close_fds=True)
                raise
        finally:
            lock.release()
            for name in ('update-download.json', 'update-download.bin'):
                root.joinpath(name).unlink(missing_ok=True)
        return 0
    except Exception as exc:
        print('Update failed: {} {}'.format(type(exc).__name__, str(exc)[:300]), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

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
    if len(sys.argv) != 4:
        return 2
    data_root = Path(sys.argv[1]).resolve()
    program_root = Path(sys.argv[2]).resolve()
    executable = Path(sys.argv[3]).resolve()
    # Windows 的更新进程没有控制台；私有日志用于定位替换失败，不记录账号或压缩包内容。
    with data_root.joinpath('update.log').open('a', encoding='utf-8') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        try:
            return install(data_root, program_root, executable)
        except Exception as exc:
            print('Update failed: {} {}'.format(type(exc).__name__, str(exc)[:300]), flush=True)
            return 1


def install(data_root, program_root, executable):
    data_root = Path(data_root).resolve()
    program_root = Path(program_root).resolve()
    executable = Path(executable).resolve()
    # 旧服务退出时 PyInstaller 可能清理共享的解包目录，必须提前读取版本。
    installed_version = updater.current_version()
    try:
        for _ in range(120):
            if not data_root.joinpath('instance.json').exists():
                break
            time.sleep(0.5)
        else:
            print('Old service did not exit; update cancelled.', flush=True)
            return 1
        lock = updater.InstallLock(data_root)
        if not lock.acquire():
            return 1
        try:
            metadata = json.loads(data_root.joinpath('update-download.json').read_text(encoding='utf-8'))
            archive = data_root.joinpath('update-download.bin').read_bytes()
            try:
                updater.apply_downloaded(archive, metadata['name'], program_root, executable,
                                         installed_version=installed_version)
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
                data_root.joinpath(name).unlink(missing_ok=True)
        return 0
    except Exception as exc:
        print('Update failed: {} {}'.format(type(exc).__name__, str(exc)[:300]), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

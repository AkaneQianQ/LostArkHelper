"""Windows local service launcher. Python 3.11+ or frozen PyInstaller build."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import ThreadingHTTPServer

BUNDLE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
sys.path.insert(0, str(BUNDLE / 'service'))
import app
import automation
import platform_lock
import scheduler
import autostart
import updater


# 使用当前 Windows 用户的本地应用数据目录，使程序升级和数据保存相互独立。
def data_directory():
    if os.name != 'nt':
        raise RuntimeError('当前发行包面向 Windows；请在 Windows 10/11 上启动。')
    return Path(os.environ['LOCALAPPDATA']) / 'LostArkHelper'


# 重复启动时只连接本机服务，并核对随机实例标识，避免误把占用端口的其他程序当作本服务。
def reopen(state_file):
    """Only trust a responding loopback instance with matching random instance ID."""
    try:
        state = json.loads(state_file.read_text(encoding='utf-8'))
        port = state['port']
        if type(port) is not int or not 1024 <= port <= 65535:
            return False
        base = 'http://127.0.0.1:' + str(port)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(base + '/api/local/health', timeout=2) as response:
            health = json.load(response)
        if not secrets.compare_digest(health['instance'], state['instance']):
            return False
        webbrowser.open(base + '/open?key=' + state['token'])
        return True
    except Exception:
        return False


def cleanup_update_runtime(root):
    # 更新进程退出后会释放自身文件；新版启动后短暂重试即可清理临时运行时。
    staging = Path(root) / 'update-runtime'
    for _ in range(40):
        try:
            shutil.rmtree(staging)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.25)


# 先拿单实例锁，再启动本机 HTTP 与调度线程，最后可选打开浏览器；退出时等待已开始操作结束。
def main():
    parser = argparse.ArgumentParser(description='命运方舟助手 Windows 本地服务')
    parser.add_argument('--port', type=int, default=18745)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--update-worker', nargs=3, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.update_worker:
        sys.argv = [sys.argv[0], *args.update_worker]
        import update_worker
        return update_worker.main()
    if not 1024 <= args.port <= 65535:
        parser.error('端口需在 1024–65535 之间')
    autostart.COMMAND = autostart.command(launcher=Path(__file__).resolve().with_name('background.pyw'))
    root = data_directory()
    root.mkdir(parents=True, exist_ok=True)
    lock = automation.OperationLock(root)
    lock.path = root / 'instance.lock'
    state_file = root / 'instance.json'
    if not lock.acquire():
        if args.no_browser:
            return 0
        if not reopen(state_file):
            print('本地服务正在启动或已有实例运行。请稍后重新打开。')
        return 0
    stop = threading.Event()
    server = None
    worker = None
    try:
        app.ROOT = root
        app.STATIC = BUNDLE / 'dist'
        app.LOCAL_TOKEN = secrets.token_urlsafe(32)
        app.INSTANCE_ID = secrets.token_urlsafe(24)
        # Keep port fixed for the lifetime of the process; never expose on LAN.
        try:
            server = ThreadingHTTPServer(('127.0.0.1', args.port), app.Handler)
        except OSError:
            server = ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        server.daemon_threads = False
        def request_stop():
            stop.set()
            threading.Thread(target=server.shutdown, daemon=True).start()
        app.REQUEST_STOP = request_stop
        app.PORT = server.server_address[1]
        automation.save_state(state_file, {'port': app.PORT, 'token': app.LOCAL_TOKEN,
                                          'instance': app.INSTANCE_ID})
        worker = threading.Thread(target=scheduler.serve, args=(root, stop), daemon=False)
        worker.start()
        threading.Thread(target=cleanup_update_runtime, args=(root,), daemon=True).start()
        print('命运方舟助手已启动：http://127.0.0.1:{}'.format(app.PORT), flush=True)
        print('数据目录：{}'.format(root), flush=True)
        print('服务在后台运行；关闭网页不会停止。请在工作台的启动设置中安全停止服务。', flush=True)
        print('定时计划按北京时间执行；休眠/关机时无法执行，恢复后仅合并最近一次计划。', flush=True)
        if not args.no_browser:
            webbrowser.open('http://127.0.0.1:{}/open?key={}'.format(app.PORT, app.LOCAL_TOKEN))
        try:
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            print('\n正在等待已开始的操作完成，请勿强制关闭……', flush=True)
    finally:
        stop.set()
        if worker:
            worker.join()
        if server:
            server.server_close()
        state_file.unlink(missing_ok=True)
        lock.release()
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError) as exc:
        print('启动失败：{}'.format(exc), file=sys.stderr)
        if getattr(sys, 'frozen', False):
            input('按回车退出。')
        raise SystemExit(1)

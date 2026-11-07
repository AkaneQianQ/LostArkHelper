"""Linux 单用户本机服务，无注册；可前台或由 systemd/nohup 后台运行。"""
import argparse
import json
import os
from pathlib import Path
import secrets
import signal
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


# 使用当前 Linux 用户的数据目录，使程序升级和数据保存相互独立。
def data_directory():
    if not sys.platform.startswith('linux'):
        raise RuntimeError('此发行包用于 Linux x64。')
    base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    root = base / 'LostArkHelper'
    import credentials
    return credentials.ensure_private(root)


def control(state_file, stopping=False):
    state = json.loads(state_file.read_text(encoding='utf-8'))
    port = state['port']
    if type(port) is not int or not 1024 <= port <= 65535:
        raise RuntimeError('实例端口无效。')
    base = f'http://127.0.0.1:{port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + '/api/local/health', timeout=3) as response:
        health = json.load(response)
    if not secrets.compare_digest(health['instance'], state['instance']):
        raise RuntimeError('实例标识不匹配，不访问其他进程。')
    if not stopping:
        print(base + '/open?key=' + state['token'])
        return 0
    request = urllib.request.Request(base + '/api/local/stop', data=b'{"confirm":true}', headers={
        'Origin': base, 'Content-Type': 'application/json', 'X-Ark-Request': '1',
        'Cookie': 'ark_session=' + state['token']}, method='POST')
    with opener.open(request, timeout=5) as response:
        result = json.load(response)
    print(result['message'])
    return 0


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


# 先拿单实例锁，再启动本机 HTTP 与调度线程，最后可选打开浏览器；退出时等待已开始操作结束。
def main():
    parser = argparse.ArgumentParser(description='命运方舟助手 Linux 独立本地服务')
    parser.add_argument('--port', type=int, default=18745)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--update-worker', nargs=3, help=argparse.SUPPRESS)
    parser.add_argument('--open-url', action='store_true', help='输出当前实例工作台链接，不启动新服务')
    parser.add_argument('--stop', action='store_true', help='通过经过鉴权的本机 API 安全停止实例')
    args = parser.parse_args()
    if args.update_worker:
        sys.argv = [sys.argv[0], *args.update_worker]
        import update_worker
        return update_worker.main()
    if not 1024 <= args.port <= 65535:
        parser.error('端口需在 1024–65535 之间')
    os.umask(0o077)
    root = data_directory()
    root.mkdir(parents=True, exist_ok=True)
    if args.open_url or args.stop:
        return control(root / 'instance.json', stopping=args.stop)
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
        signal.signal(signal.SIGTERM, lambda *_: request_stop())
        app.REQUEST_STOP = request_stop
        app.PORT = server.server_address[1]
        automation.save_state(state_file, {'port': app.PORT, 'token': app.LOCAL_TOKEN,
                                          'instance': app.INSTANCE_ID})
        worker = threading.Thread(target=scheduler.serve, args=(root, stop), daemon=False)
        worker.start()
        print('命运方舟助手已启动：http://127.0.0.1:{}'.format(app.PORT), flush=True)
        print('数据目录：{}'.format(root), flush=True)
        print('关闭网页不停止服务；后台启动用 start.sh，安全停止用 stop.sh。', flush=True)
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

        raise SystemExit(1)

"""在 Linux 测试真正的冻结程序，不访问游戏 API、不依赖用户 Python PATH。"""
import argparse
import http.client
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


def request(port, path, method='GET', body=None, cookie=None):
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    headers = {}
    if cookie:
        headers['Cookie'] = cookie
    if method == 'POST':
        headers.update({'Origin': f'http://127.0.0.1:{port}', 'Content-Type': 'application/json', 'X-Ark-Request': '1'})
    try:
        c.request(method, path, body=body, headers=headers)
        response = c.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        c.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', required=True)
    args = parser.parse_args()
    exe = Path(args.exe).resolve()
    import sys
    assert sys.platform.startswith('linux'), 'Smoke test requires Linux'
    assert exe.is_file(), 'Binary missing'
    with tempfile.TemporaryDirectory(prefix='ark-packaged-') as tmp:
        env = os.environ.copy()
        env['XDG_DATA_HOME'] = tmp
        # 故意留空 PATH：冻结程序必须使用内置 Python。
        env['PATH'] = ''
        proc = subprocess.Popen([str(exe), '--no-browser', '--port', '19845'], env=env, cwd=tmp)
        state_file = Path(tmp) / 'LostArkHelper' / 'instance.json'
        stopped = False
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise AssertionError('Packaged program exited before becoming ready')
                try:
                    state = json.loads(state_file.read_text(encoding='utf-8'))
                    port = state['port']
                    status, _, data = request(port, '/api/local/health')
                    if status == 200 and json.loads(data)['instance'] == state['instance']:
                        break
                except (OSError, ValueError, KeyError):
                    pass
                time.sleep(0.25)
            else:
                raise AssertionError('Packaged service startup timed out')
            assert request(port, '/api/status')[0] == 401
            status, headers, _ = request(port, '/open?key=' + state['token'])
            assert status == 303
            cookie = headers['Set-Cookie'].split(';')[0]
            status, _, data = request(port, '/api/status', cookie=cookie)
            assert status == 200 and not json.loads(data)['configured']
            # 网页与 JS/CSS 必须真正打包进去，不能只验证端口开放。
            status, _, page = request(port, '/')
            assert status == 200
            assets = re.findall(r'(?:src|href)="(/assets/[^"?]+\.(?:js|css))"', page.decode())
            assert len(assets) >= 2
            for asset in assets:
                status, _, contents = request(port, asset)
                assert status == 200 and contents, 'Missing bundled asset'
            # 无浏览器的重复启动应退出，不影响第一实例。
            duplicate = subprocess.Popen([str(exe), '--no-browser'], env=env, cwd=tmp)
            try:
                assert duplicate.wait(timeout=45) == 0
            finally:
                if duplicate.poll() is None:
                    duplicate.kill()
                    duplicate.wait()
            assert proc.poll() is None
            status, _, _ = request(port, '/api/local/stop', method='POST', body='{"confirm":true}', cookie=cookie)
            assert status == 200
            assert proc.wait(timeout=30) == 0
            stopped = True
            assert not state_file.exists(), 'Instance file should be removed on clean exit'
            print('Linux binary smoke passed: startup, auth, bundled frontend, single instance, safe shutdown; no game requests.')
        finally:
            if not stopped and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)


if __name__ == '__main__':
    main()

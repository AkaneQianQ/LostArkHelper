"""在 Windows 测试真正的 EXE，不访问游戏 API、不依赖用户 Python PATH。"""
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
    assert os.name == 'nt', 'Smoke test requires Windows'
    assert exe.is_file(), 'EXE missing'
    with tempfile.TemporaryDirectory(prefix='ark-packaged-') as tmp:
        env = os.environ.copy()
        env['LOCALAPPDATA'] = tmp
        # 仅保留系统命令目录：冻结程序不能依赖 Python 安装目录。
        system_root = os.environ['SystemRoot']  # os.environ 在 Windows 忽略大小写，普通 dict 不会。
        env['PATH'] = os.pathsep.join([str(Path(system_root) / 'System32'), system_root])
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
            status, _, data = request(port, '/api/local/update', cookie=cookie)
            update = json.loads(data)
            assert status == 200 and update['supported'] and re.fullmatch(r'v\d+\.\d+\.\d+', update['current_version'])
            assert request(port, '/api/local/update', method='POST', body='{"check":true}')[0] == 401
            status, _, data = request(port, '/api/local/update', method='POST', body='{"check":true}', cookie=cookie)
            assert status == 202
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                status, _, data = request(port, '/api/local/update', cookie=cookie)
                update = json.loads(data)
                if update['status'] != 'checking':
                    break
                time.sleep(0.5)
            assert status == 200 and update['status'] == 'ready', 'GitHub release check failed'
            assert update['latest_version'] and update['release_url'].startswith('https://github.com/youboRepo/LostArkHelper/releases/')
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
            print('EXE smoke passed: startup, auth, frontend, single instance, GitHub update check, safe shutdown; no game requests.')
        finally:
            if not stopped and proc.poll() is None:
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
                proc.wait(timeout=15)


if __name__ == '__main__':
    main()

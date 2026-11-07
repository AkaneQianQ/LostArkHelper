"""用真实冻结 EXE 验证停止、替换、保留用户数据和自动重启；不调用游戏接口。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

from smoke_frozen import request


def ready(state_file, process=None):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            raise AssertionError('服务在就绪前退出')
        try:
            state = json.loads(state_file.read_text(encoding='utf-8'))
            status, _, data = request(state['port'], '/api/local/health')
            if status == 200 and json.loads(data)['instance'] == state['instance']:
                return state
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.25)
    raise AssertionError('等待服务就绪超时')


def make_archive(source, destination):
    # 原样打包刚通过冒烟测试的程序，仅改变内置版本；测试时禁用网络以隔离更新源。
    entries = {}
    for path in source.rglob('*'):
        if path.is_file():
            relative = path.relative_to(source).as_posix()
            data = b'v99.0.0\n' if relative == 'VERSION' else path.read_bytes()
            entries[relative] = data
    entries['VERSION'] = b'v99.0.0\n'
    entries['SHA256SUMS.txt'] = ''.join(
        hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
        for name, data in entries.items() if name != 'SHA256SUMS.txt').encode()
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as output:
        for name, data in entries.items():
            output.writestr('LostArkHelper-Windows-x64-v99.0.0/' + name, data)
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def main():
    assert os.name == 'nt', '此测试必须在 Windows 原生环境执行'
    exe = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='ark-upgrade-') as temporary:
        base = Path(temporary)
        program = base / 'LostArkHelper'
        data = base / 'data'
        archive = base / 'update.zip'
        from shutil import copytree
        copytree(exe.parent, program)
        digest = make_archive(program, archive)
        state_file = data / 'LostArkHelper' / 'instance.json'
        env = dict(os.environ, LOCALAPPDATA=str(data), ARK_TEST_UPDATE=str(archive),
                   ARK_TEST_CHECKSUM=digest, ARK_TEST_VERSION='v99.0.0')
        proc = subprocess.Popen([str(program / 'LostArkHelper.exe'), '--no-browser'], env=env)
        try:
            state = ready(state_file, proc)
            marker = data / 'LostArkHelper' / 'upgrade-data.marker'
            marker.write_text('retained', encoding='ascii')
            port = state['port']
            _, headers, _ = request(port, '/open?key=' + state['token'])
            cookie = headers['Set-Cookie'].split(';')[0]
            status, _, body = request(port, '/api/local/update', 'POST', '{"check":true}', cookie)
            assert status == 202, body
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                _, _, body = request(port, '/api/local/update', cookie=cookie)
                result = json.loads(body)
                if result['status'] == 'ready':
                    break
                time.sleep(0.25)
            assert result['update_available'], result
            status, _, body = request(port, '/api/local/update', 'POST', '{"install":true}', cookie)
            assert status == 202, body
            assert proc.wait(timeout=60) == 0, '旧服务未安全退出'
            new_state = ready(state_file)
            assert new_state['instance'] != state['instance'], '没有启动新的服务实例'
            _, headers, _ = request(new_state['port'], '/open?key=' + new_state['token'])
            cookie = headers['Set-Cookie'].split(';')[0]
            _, _, body = request(new_state['port'], '/api/local/update', cookie=cookie)
            result = json.loads(body)
            assert result['current_version'] == 'v99.0.0', result
            assert marker.read_text(encoding='ascii') == 'retained'
            assert (base / 'LostArkHelper.previous' / 'LostArkHelper.exe').is_file()
            assert request(new_state['port'], '/api/local/stop', 'POST', '{"confirm":true}', cookie)[0] == 200
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline and state_file.exists():
                time.sleep(0.25)
            assert not state_file.exists(), '新版服务未安全停止'
            print('Windows upgrade passed: verified package, old exit, replacement, data retention, new process, backup.')
        finally:
            if proc.poll() is None:
                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
            subprocess.run(['taskkill', '/IM', 'LostArkHelper.exe', '/F'], capture_output=True)


if __name__ == '__main__':
    main()

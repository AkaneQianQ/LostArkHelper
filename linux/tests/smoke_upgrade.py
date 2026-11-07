"""在 Linux 验证冻结程序的更新、数据保留与重启；更新包仅为本地测试生成。"""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import time

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
    entries = {'VERSION': b'v99.0.0\n'}
    for name in ('LostArkHelper', 'start.sh', 'stop.sh', 'open-workbench.sh', 'install-user-service.sh', 'README.md'):
        entries[name] = source.joinpath(name).read_bytes()
    entries['SHA256SUMS.txt'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                                       for name, data in entries.items() if name != 'SHA256SUMS.txt').encode()
    with tarfile.open(destination, 'w:gz') as output:
        for name, data in entries.items():
            info = tarfile.TarInfo('LostArkHelper-Linux-x64-v99.0.0/' + name)
            info.size = len(data)
            info.mode = 0o755 if name == 'LostArkHelper' or name.endswith('.sh') else 0o644
            output.addfile(info, io.BytesIO(data))
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def main():
    assert sys.platform.startswith('linux'), '此测试必须在 Linux 原生环境执行'
    exe = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='ark-upgrade-') as temporary:
        base = Path(temporary)
        program = base / 'LostArkHelper-Linux-x64'
        program.mkdir()
        from shutil import copy2
        for path in exe.parent.iterdir():
            if path.is_file():
                copy2(path, program / path.name)
        data = base / 'data'
        archive = base / 'update.tar.gz'
        digest = make_archive(program, archive)
        state_file = data / 'LostArkHelper' / 'instance.json'
        env = dict(os.environ, XDG_DATA_HOME=str(data), ARK_TEST_UPDATE=str(archive),
                   ARK_TEST_CHECKSUM=digest, ARK_TEST_VERSION='v99.0.0', PATH='')
        proc = subprocess.Popen([str(program / 'LostArkHelper'), '--no-browser'], env=env)
        try:
            state = ready(state_file, proc)
            marker = data / 'LostArkHelper' / 'upgrade-data.marker'
            marker.write_text('retained', encoding='ascii')
            _, headers, _ = request(state['port'], '/open?key=' + state['token'])
            cookie = headers['Set-Cookie'].split(';')[0]
            status, _, body = request(state['port'], '/api/local/update', 'POST', '{"check":true}', cookie)
            assert status == 202, body
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                _, _, body = request(state['port'], '/api/local/update', cookie=cookie)
                result = json.loads(body)
                if result['status'] == 'ready':
                    break
                time.sleep(0.25)
            assert result['update_available'], result
            status, _, body = request(state['port'], '/api/local/update', 'POST', '{"install":true}', cookie)
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
            assert (base / 'LostArkHelper-Linux-x64.previous' / 'LostArkHelper').is_file()
            assert os.access(program / 'LostArkHelper', os.X_OK)
            assert request(new_state['port'], '/api/local/stop', 'POST', '{"confirm":true}', cookie)[0] == 200
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline and state_file.exists():
                time.sleep(0.25)
            assert not state_file.exists(), '新版服务未安全停止'
            print('Linux upgrade passed: verified package, old exit, replacement, data retention, new process, backup.')
        finally:
            log = data / 'LostArkHelper' / 'update.log'
            if log.is_file():
                print(log.read_text(encoding='utf-8'))
            if proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=15)
            try:
                state = json.loads(state_file.read_text(encoding='utf-8'))
                _, headers, _ = request(state['port'], '/open?key=' + state['token'])
                cookie = headers['Set-Cookie'].split(';')[0]
                request(state['port'], '/api/local/stop', 'POST', '{"confirm":true}', cookie)
            except (OSError, ValueError, KeyError):
                pass


if __name__ == '__main__':
    main()

"""发布前核对压缩包内容和逐文件校验值，生成最终下载文件的校验清单。"""
import argparse
import hashlib
from pathlib import Path
import re
import tarfile
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', args.version):
        parser.error('Expected vMAJOR.MINOR.PATCH')
    root = Path(__file__).resolve().parents[1] / 'release-assets'
    expected = [f'LostArkHelper-{kind}-{args.version}.{extension}' for kind, extension in (
        ('Windows-x64', 'zip'), ('Linux-x64', 'tar.gz'), ('Server', 'tar.gz'), ('iPhone', 'shortcut'))]
    for name in expected:
        archive = root / name
        if name.endswith('.shortcut'):
            assert archive.stat().st_size > 1024, 'Missing signed iPhone file'
            continue
        if name.endswith('.zip'):
            with zipfile.ZipFile(archive) as stream:
                assert stream.testzip() is None, 'Bad ZIP CRC'
                files = {n: stream.read(n) for n in stream.namelist() if not n.endswith('/')}
        else:
            with tarfile.open(archive) as stream:
                members = stream.getmembers()
                assert not any(m.issym() or m.islnk() for m in members), 'Unexpected archive links'
                files = {m.name: stream.extractfile(m).read() for m in members if m.isfile()}
        assert len({n.split('/')[0] for n in files}) == 1, 'Expected one top-level directory'
        for filename in files:
            assert not filename.startswith('/') and '..' not in Path(filename).parts
            assert Path(filename).name not in ('credentials.key', 'credentials.enc', 'panel.key',
                                             'instance.json', 'config-dashboard.json', 'pending-operation.json')
            assert not filename.endswith(('.dpapi', '.sqlite3'))
        checks = [n for n in files if n.count('/') == 1 and n.endswith('/SHA256SUMS.txt')]
        assert len(checks) == 1, 'Missing internal checksums'
        base = checks[0].split('/')[0] + '/'
        for line in files[checks[0]].decode().splitlines():
            digest, filename = line.split('  ', 1)
            assert hashlib.sha256(files[base + filename]).hexdigest() == digest, filename
        if 'Windows' in name:
            assert any(n.endswith('/LostArkHelper.exe') and data[:2] == b'MZ' for n, data in files.items())
        if 'Linux' in name:
            assert any(n.endswith('/LostArkHelper') and data[:4] == b'\x7fELF' for n, data in files.items())
        print(name, 'verified', len(files), 'files')
    actual = {p.name for p in root.iterdir() if p.is_file() and p.name != 'SHA256SUMS.txt'}
    assert actual == set(expected), 'Unexpected release assets'
    (root / 'SHA256SUMS.txt').write_text(''.join(
        f'{hashlib.sha256((root / name).read_bytes()).hexdigest()}  {name}\n'
        for name in sorted(expected)), encoding='utf-8')


if __name__ == '__main__':
    main()

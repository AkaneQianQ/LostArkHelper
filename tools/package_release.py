"""生成用户下载的压缩包；Windows/Linux 先完成原生构建和成品测试。"""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('edition', choices=['server', 'windows', 'linux'])
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', args.version):
        parser.error('Expected vMAJOR.MINOR.PATCH')
    label = {'server': 'Server', 'windows': 'Windows-x64', 'linux': 'Linux-x64'}[args.edition]
    name = f'LostArkHelper-{label}-{args.version}'
    output = ROOT / 'release-assets'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / name
        if args.edition == 'server':
            # 只打包已跟踪源码和网页，排除机器上的状态、依赖及临时文件。
            paths = subprocess.check_output(['git', 'ls-files', '-z', 'server'], cwd=ROOT).decode().split('\0')
            for relative in filter(None, paths):
                source = ROOT / relative
                target = stage / Path(relative).relative_to('server')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        else:
            source = ROOT / args.edition / 'release' / (
                'LostArkHelper' if args.edition == 'windows' else 'LostArkHelper-Linux-x64')
            if not source.is_dir():
                raise SystemExit(f'Missing native build directory: {source}')
            shutil.copytree(source, stage)
            if args.edition == 'windows':
                shutil.copy2(ROOT/'windows/EXE使用说明.md', stage/'README.md')
        (stage / 'VERSION').write_text(args.version + '\n', encoding='utf-8')
        files = sorted(p for p in stage.rglob('*') if p.is_file())
        (stage/'SHA256SUMS.txt').write_text(''.join(
            f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(stage).as_posix()}\n'
            for p in files if p.name != 'SHA256SUMS.txt'), encoding='utf-8')
        if args.edition == 'windows':
            archive = output / (name + '.zip')
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as stream:
                for path in sorted(stage.rglob('*')):
                    if path.is_file():
                        stream.write(path, path.relative_to(stage.parent))
            with zipfile.ZipFile(archive) as stream:
                if stream.testzip():
                    raise RuntimeError('ZIP CRC verification failed')
        else:
            archive = output / (name + '.tar.gz')
            with tarfile.open(archive, 'w:gz') as stream:
                stream.add(stage, arcname=name)
        print(archive.name, hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()

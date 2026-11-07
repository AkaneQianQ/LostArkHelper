"""GitHub 正式版检查与原子安装准备。信任发布仓库和 Release SHA256 清单。"""
import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import platform_lock

REPOSITORY = 'youboRepo/LostArkHelper'
VERSION_RE = re.compile(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')
MAX_ARCHIVE = 80 * 1024 * 1024
LOCK = threading.Lock()
STATE = {'status': 'idle', 'error': ''}


def version_tuple(value):
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError('版本号格式无效')
    return tuple(map(int, match.groups()))


def platform_name():
    return 'Windows-x64' if os.name == 'nt' else 'Linux-x64'


def current_version():
    candidates = []
    if getattr(sys, 'frozen', False):
        # 发行目录中的 VERSION 必须优先；单文件程序内部可能仍带有旧版本号。
        candidates.append(Path(sys.executable).resolve().parent / 'VERSION')
    if getattr(sys, '_MEIPASS', None):
        candidates.append(Path(sys._MEIPASS) / 'VERSION')
    if not candidates:
        candidates.append(Path(__file__).resolve().parent / 'VERSION')
    for resource in candidates:
        try:
            return resource.read_text(encoding='ascii').strip()
        except OSError:
            pass
    return ''


def normalized_path(path):
    # Windows 的短路径与长路径可以指向同一个 EXE，比较前统一规范化。
    return os.path.normcase(os.path.normpath(str(path)))


def supported():
    return bool(getattr(sys, 'frozen', False)) and bool(current_version())


def state():
    with LOCK:
        result = dict(STATE, supported=supported(), current_version=current_version() or None)
        result['update_available'] = False
        if result.get('latest_version') and result.get('current_version'):
            try:
                result['update_available'] = (version_tuple(result['latest_version']) >
                                               version_tuple(result['current_version']))
            except ValueError:
                result['update_available'] = False
        return result


def safe_path(root, name):
    parts = Path(name).parts
    if not parts or Path(name).is_absolute() or '\\' in name or '..' in parts:
        raise ValueError('发行包路径无效')
    target = root.joinpath(*parts)
    if name.startswith('/') or root not in target.parents:
        raise ValueError('发行包路径越界')
    return target


def verify_members(files):
    roots = {name.split('/', 1)[0] for name in files}
    if len(roots) != 1:
        raise ValueError('发行包顶层目录异常')
    root_name = next(iter(roots))
    checksums_name = root_name + '/SHA256SUMS.txt'
    version_name = root_name + '/VERSION'
    for name in files:
        if not name.startswith(root_name + '/') or len(name) <= len(root_name) + 1:
            raise ValueError('发行包文件不在顶层目录内')
        safe_path(Path('/'), name)
    for name in (checksums_name, version_name):
        if name not in files:
            raise ValueError('发行包缺少版本或校验清单')
    listed = set()
    for line in files[checksums_name].decode('utf-8').splitlines():
        digest, relative = line.split('  ', 1)
        filename = root_name + '/' + relative
        if not re.fullmatch(r'[0-9a-f]{64}', digest) or filename in listed or filename not in files or hashlib.sha256(files[filename]).hexdigest() != digest:
            raise ValueError('发行包内文件校验失败')
        listed.add(filename)
    if listed != set(files) - {checksums_name}:
        raise ValueError('发行包存在未列入校验清单的文件')
    return root_name, files[version_name].decode('ascii').strip()


def read_zip(archive):
    with zipfile.ZipFile(archive) as source:
        if source.testzip():
            raise ValueError('下载的 ZIP 已损坏')
        members = [m for m in source.infolist() if not m.is_dir()]
        if any(stat.S_ISLNK(m.external_attr >> 16) for m in members):
            raise ValueError('ZIP 不允许链接文件')
        files = {m.filename: source.read(m) for m in members}
    return files, verify_members(files)


def read_tar(archive):
    with tarfile.open(fileobj=archive, mode='r:gz') as source:
        members = source.getmembers()
        if any(not (m.isfile() or m.isdir()) for m in members):
            raise ValueError('发行包只允许普通文件和目录')
        files = {m.name: source.extractfile(m).read() for m in members if m.isfile()}
        modes = {m.name: m.mode for m in members if m.isfile()}
    return files, verify_members(files), modes


def fetch_json(url):
    with download(url, 1024 * 1024) as response:
        return json.load(response)


def download(url, limit=MAX_ARCHIVE):
    if not url.startswith(f'https://api.github.com/repos/{REPOSITORY}/') and not url.startswith(f'https://github.com/{REPOSITORY}/'):
        raise ValueError('更新地址不属于项目发布地址')
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in ('api.github.com', 'github.com',
                                                            'release-assets.githubusercontent.com'):
        raise ValueError('更新地址不属于官方 GitHub 发布仓库')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    response = opener.open(urllib.request.Request(url, headers={'User-Agent': 'LostArkHelper-Updater',
                                                               'Accept': 'application/vnd.github+json'}), timeout=30)
    return response


def fetch_asset(asset):
    if not isinstance(asset.get('name'), str) or not isinstance(asset.get('browser_download_url'), str):
        raise ValueError('发布附件信息不完整')
    with download(asset['browser_download_url']) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname not in ('github.com', 'release-assets.githubusercontent.com'):
            raise ValueError('更新下载跳转到了未知地址')
        output = io.BytesIO()
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            output.write(chunk)
            if output.tell() > MAX_ARCHIVE:
                raise ValueError('更新包超过大小限制')
    return output.getvalue(), asset['name']


def fetch_release():
    release = fetch_json(f'https://api.github.com/repos/{REPOSITORY}/releases/latest')
    tag = release.get('tag_name', '')
    version_tuple(tag)
    assets = release.get('assets')
    if not isinstance(assets, list) or not isinstance(release.get('html_url'), str):
        raise ValueError('发布信息格式无效')
    names = [asset.get('name') for asset in assets]
    if 'SHA256SUMS.txt' not in names:
        raise ValueError('发布页缺少 SHA256 清单')
    checks, _ = fetch_asset(assets[names.index('SHA256SUMS.txt')])
    checksums = {}
    for line in checks.decode('utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch(r'[0-9a-f]{64}', digest) or Path(name).name != name:
            raise ValueError('发布页 SHA256 清单格式无效')
        checksums[name] = digest
    return tag, assets, checksums


def check():
    # 原生 CI 用本地测试发行包走完替换/重启；正常启动没有这些变量，始终使用 GitHub。
    if os.environ.get('ARK_TEST_UPDATE'):
        tag = os.environ['ARK_TEST_VERSION']
        version_tuple(tag)
        return {'latest_version': tag, 'latest_checksum': os.environ['ARK_TEST_CHECKSUM'],
                'release_url': f'https://github.com/{REPOSITORY}/releases/tag/{tag}'}
    tag, assets, checksums = fetch_release()
    expected_name = f'LostArkHelper-{platform_name()}-{tag}.' + ('zip' if platform_name() == 'Windows-x64' else 'tar.gz')
    if current_version() and version_tuple(tag) > version_tuple(current_version()):
        if expected_name not in [asset.get('name') for asset in assets] or expected_name not in checksums:
            raise ValueError('新版本缺少当前平台的安装包')
    return {'latest_version': tag, 'latest_checksum': checksums.get(expected_name), 'release_url': f'https://github.com/{REPOSITORY}/releases/tag/{tag}'}


def prepare(tag):
    if os.environ.get('ARK_TEST_UPDATE'):
        return Path(os.environ['ARK_TEST_UPDATE']).read_bytes(), f'LostArkHelper-Windows-x64-{tag}.zip'
    assets = fetch_json(f'https://api.github.com/repos/{REPOSITORY}/releases/tags/{tag}').get('assets')
    if not isinstance(assets, list):
        raise ValueError('发布附件信息无效')
    asset_name = f'LostArkHelper-{platform_name()}-{tag}.' + ('zip' if platform_name() == 'Windows-x64' else 'tar.gz')
    matching = [asset for asset in assets if asset.get('name') == asset_name]
    if len(matching) != 1:
        raise ValueError('未找到当前平台的更新包')
    data, _ = fetch_asset(matching[0])
    return data, asset_name


def apply_downloaded(archive, asset_name, root, executable):
    # 外部 worker 在旧服务完全退出后才调用此函数，避免替换正在运行的文件。
    if asset_name.endswith('.zip'):
        files, (top, version) = read_zip(io.BytesIO(archive))
        modes = {name: 0o755 if name.endswith('.exe') else 0o644 for name in files}
        expected_name = 'LostArkHelper.exe'
    else:
        files, (top, version), modes = read_tar(io.BytesIO(archive))
        expected_name = 'LostArkHelper'
    current = current_version()
    if not supported() or version_tuple(version) <= version_tuple(current):
        raise ValueError('更新包版本 {} 无效或低于当前版本 {}'.format(version, current or '未知'))
    if asset_name != f'LostArkHelper-{platform_name()}-{version}.' + ('zip' if platform_name() == 'Windows-x64' else 'tar.gz'):
        raise ValueError('更新包名称与版本不一致')
    root = Path(root).resolve()
    executable = Path(executable).resolve()
    if root == root.parent:
        raise ValueError('不能更新文件系统根目录')
    if normalized_path(executable) != normalized_path(root / expected_name):
        raise ValueError('只允许更新当前发行目录')
    target = root.parent / (root.name + '.updating')
    backup = root.parent / (root.name + '.previous')
    for path in (target, backup):
        if path.exists():
            shutil.rmtree(path)
    target.mkdir()
    for name, data in files.items():
        destination = safe_path(target, name[len(top) + 1:])
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(modes[name] & 0o777)
    installed = target / expected_name
    if not installed.is_file() or installed.stat().st_size == 0:
        raise ValueError('更新包缺少程序入口')
    os.replace(root, backup)
    try:
        os.replace(target, root)
    except Exception:
        os.replace(backup, root)
        raise
    if os.name != 'nt':
        subprocess.Popen([str(root / 'LostArkHelper'), '--no-browser'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    else:
        subprocess.Popen([str(root / 'LostArkHelper.exe'), '--no-browser'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                         close_fds=True)
    print('Update installed. Previous folder retained for recovery.', flush=True)
    return 0


class InstallLock:
    # 独立更新进程不加载 automation，避免多个更新进程同时替换目录。
    def __init__(self, root):
        self.root = Path(root)
        self.file = None

    def acquire(self):
        try:
            self.file = open(self.root / 'install.lock', 'a+b')
            platform_lock.acquire(self.file.fileno(), False)
            return True
        except (BlockingIOError, OSError):
            if self.file:
                self.file.close()
            return False

    def release(self):
        if self.file:
            self.file.close()


def worker():
    import app
    data_root = Path(app.ROOT).resolve()
    executable = Path(sys.executable).resolve()
    program_root = executable.parent
    operation = __import__('automation').OperationLock(data_root)
    worker_thread = threading.Thread(target=finish_update, args=(operation, data_root, app.REQUEST_STOP), daemon=False)
    # 独占整段下载与替换准备，游戏计划暂时等待。
    if not operation.acquire(blocking=True):
        raise RuntimeError('等待游戏操作结束超时')
    try:
        with LOCK:
            STATE.update(status='downloading', error='')
        if (data_root / 'pending-operation.json').exists():
            raise RuntimeError('存在待确认的游戏操作，请先核对，暂不更新')
        tag = state().get('latest_version')
        version_tuple(tag)
        if not current_version() or version_tuple(tag) <= version_tuple(current_version()):
            raise RuntimeError('没有可安装的新版本')
        archive, name = prepare(tag)
        if hashlib.sha256(archive).hexdigest() != state().get('latest_checksum'):
            raise RuntimeError('更新包 SHA256 校验失败，已取消更新')
        data_root.joinpath('update-download.json').write_text(json.dumps({'version': tag, 'name': name}, ensure_ascii=False), encoding='utf-8')
        data_root.joinpath('update-download.bin').write_bytes(archive)
        # onedir 的 EXE 位于待替换目录中，因此从独立暂存副本启动更新进程。
        runtime = data_root / 'update-runtime'
        if runtime == program_root or program_root in runtime.parents:
            raise RuntimeError('更新暂存目录与当前发行目录冲突')
        if runtime.exists():
            shutil.rmtree(runtime)
        staged_program = runtime / 'program'
        shutil.copytree(program_root, staged_program)
        staged_executable = staged_program / executable.name
        subprocess.Popen([staged_executable, '--update-worker', str(data_root), str(program_root), str(executable)],
                         cwd=staged_program,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0) | getattr(subprocess, 'DETACHED_PROCESS', 0),
                         close_fds=True)
        with LOCK:
            STATE['status'] = 'restarting'
        # 在独立非后台线程中等待退出；下载函数可正常释放并结束，避免测试线程悬挂。
        worker_thread.start()
    except Exception:
        operation.release()
        raise


def finish_update(operation, root, request_stop):
    request_stop()
    try:
        for _ in range(120):
            if not root.joinpath('instance.json').exists():
                break
            time.sleep(0.5)
    finally:
        operation.release()


def start(install=False):
    if not app_stop_available():
        raise RuntimeError('当前服务尚未准备退出与重启。')
    if not supported():
        raise RuntimeError('一键更新仅支持 Release 打包版，源码运行请用 Git 更新')
    with LOCK:
        if STATE['status'] in ('checking', 'downloading', 'restarting'):
            raise RuntimeError('更新操作正在进行，请勿重复点击')
        STATE.update(status='downloading' if install else 'checking', error='')
    threading.Thread(target=guard_worker if install else check_worker, daemon=True).start()


def guard_worker():
    try:
        worker()
    except Exception as exc:
        with LOCK:
            STATE.update(status='error', error=error_result(exc))


def app_stop_available():
    import app
    return app.REQUEST_STOP is not None


def check_worker():
    try:
        result = check()
        with LOCK:
            STATE.update(result, status='ready')
    except Exception:
        with LOCK:
            STATE.update(status='error', error='检查更新失败，请稍后重试或打开发布页手动下载。')


def error_result(exc):
    return str(exc) if isinstance(exc, RuntimeError) else '更新失败，旧版本仍然保留。请稍后重试或手动下载发行包。'

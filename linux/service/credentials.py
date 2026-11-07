"""Linux 无桌面也可使用的加密凭据；密钥与文件仅属当前用户。"""
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet

NAME = 'credentials.enc'
KEY_NAME = 'credentials.key'


def exists(root):
    return (Path(root) / NAME).is_file()


def ensure_private(root):
    root = Path(root)
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink() or root.stat().st_uid != os.getuid():
        raise OSError('数据目录必须属于当前用户且不能是符号链接。')
    root.chmod(0o700)
    return root


def key(root, create=False):
    path = ensure_private(root) / KEY_NAME
    if create:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(Fernet.generate_key())
                stream.flush()
                os.fsync(stream.fileno())
    if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.getuid():
        raise OSError('凭据密钥缺失或权限异常，请使用原 Linux 用户。')
    if path.stat().st_mode & 0o077:
        raise OSError('凭据密钥权限过宽，请设置为 chmod 600。')
    return path.read_bytes()


def read(root):
    # 没有密钥时不能新建密钥并忽略原密文，否则将无法恢复真实凭据。
    raw = Fernet(key(root)).decrypt((Path(root) / NAME).read_bytes())
    return json.loads(raw.decode('utf-8'))


def write(root, config):
    root = ensure_private(root)
    data = Fernet(key(root, create=not exists(root))).encrypt(json.dumps(config, ensure_ascii=False).encode('utf-8'))
    target = root / NAME
    temp = root / (NAME + '.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, target)
    target.chmod(0o600)

"""User-bound Windows DPAPI storage. No plaintext fallback in production."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path

NAME = 'credentials.dpapi'

def exists(root):
    return (Path(root) / NAME).is_file()

# 调用 Windows DPAPI，默认绑定当前 Windows 用户；输出为加密二进制，没有明文降级路径。
def protect(data, decrypt=False):
    if os.name != 'nt':
        raise RuntimeError('此版本的凭据存储需要 Windows DPAPI；不提供明文回退。')
    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]
    buf = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        fn = crypt.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target))
    else:
        fn = crypt.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(source), 'LostArkHelper', None, None, None, 1, ctypes.byref(target))
    if not ok:
        raise OSError('Windows 凭据加密或解密失败，请使用原 Windows 用户重新导入。')
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        kernel.LocalFree(ctypes.cast(target.data, ctypes.c_void_p))

# 读取加密文件后在内存解密，仅供本机后端使用。
def read(root):
    return json.loads(protect((Path(root) / NAME).read_bytes(), decrypt=True).decode('utf-8'))

# 先加密再写磁盘，临时文件也只含密文；原子替换保留完整文件。
def write(root, config):
    data = protect(json.dumps(config, ensure_ascii=False).encode('utf-8'))
    p = Path(root) / NAME
    temp = p.with_suffix('.tmp')
    with temp.open('wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp, p)

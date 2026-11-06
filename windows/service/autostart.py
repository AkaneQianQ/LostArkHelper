"""Current-user Windows logon startup; never requests administrator rights."""
import os
from pathlib import Path
import subprocess
import sys

KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME = 'LostArkHelper'
COMMAND = None


# 根据源码/打包模式构造启动命令，正确引用含空格路径，并传 --no-browser 避免登录时弹网页。
def command(executable=None, launcher=None, frozen=None):
    executable = Path(executable or sys.executable).resolve()
    frozen = getattr(sys, 'frozen', False) if frozen is None else frozen
    if frozen:
        parts = [str(executable), '--no-browser']
    else:
        quiet = executable.with_name('pythonw.exe')
        if quiet.is_file():
            executable = quiet
        parts = [str(executable), str(Path(launcher or Path(__file__).resolve().parents[1] / 'background.pyw').resolve()), '--no-browser']
    return subprocess.list2cmdline(parts)


def registry():
    if os.name != 'nt':
        raise OSError('开机自启仅可在 Windows 上设置。')
    import winreg
    return winreg


# 读取当前用户 Run 启动项并判断路径是否仍匹配；这是配置状态，不代表 Windows/安全软件必然允许执行。
def state():
    if os.name != 'nt':
        return {'enabled': False, 'supported': False, 'matches_current': False}
    reg = registry()
    try:
        with reg.OpenKey(reg.HKEY_CURRENT_USER, KEY, 0, reg.KEY_READ) as key:
            value, kind = reg.QueryValueEx(key, NAME)
        enabled = kind == reg.REG_SZ and isinstance(value, str) and bool(value)
        return {'enabled': enabled, 'supported': True, 'matches_current': enabled and value == (COMMAND or command())}
    except FileNotFoundError:
        return {'enabled': False, 'supported': True, 'matches_current': False}


# 仅增删本程序的 HKCU 启动项，不修改全局启动项，不要求管理员权限。
def set_enabled(enabled):
    if type(enabled) is not bool:
        raise ValueError('enabled must be boolean')
    reg = registry()
    with reg.CreateKeyEx(reg.HKEY_CURRENT_USER, KEY, 0, reg.KEY_SET_VALUE) as key:
        if enabled:
            reg.SetValueEx(key, NAME, 0, reg.REG_SZ, COMMAND or command())
        else:
            try:
                reg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
    return state()

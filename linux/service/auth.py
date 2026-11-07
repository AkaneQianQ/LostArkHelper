"""Linux 单用户本机模式：没有用户注册、密码或账号数据库。"""
from pathlib import Path

SESSION_SECONDS = 7 * 24 * 3600


def user_root(root, user):
    # 身份由 app.py 的本机随机会话校验；所有数据归当前 Linux 用户。
    return Path(root)

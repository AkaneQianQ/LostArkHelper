"""Local users and expiring, revocable sessions; no plaintext passwords."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from contextlib import closing
from pathlib import Path

SESSION_SECONDS = 7 * 24 * 3600

def connect(root):
    db = sqlite3.connect(str(Path(root) / 'users.sqlite3'), timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript('''
      CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
        created INTEGER NOT NULL, legacy INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS sessions (
        digest TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS attempts (
        key TEXT NOT NULL, at INTEGER NOT NULL);
      CREATE INDEX IF NOT EXISTS attempts_key_at ON attempts(key,at);
    ''')
    return db

# 使用独立随机盐与 600000 轮 PBKDF2；数据库保存哈希，不能保存用户明文密码。
def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    value = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ':' + value

def verify(password, encoded):
    return hmac.compare_digest(password_hash(password, encoded.split(':')[0]), encoded)

def create_user(root, username, password, legacy=False):
    if not isinstance(username, str) or not re.fullmatch(r'[a-zA-Z0-9_]{3,32}', username):
        raise ValueError('用户名需为 3–32 位字母、数字或下划线。')
    username = username.lower()
    if not isinstance(password, str) or not 12 <= len(password) <= 128:
        raise ValueError('密码需为 12–128 个字符。')
    encoded = password_hash(password)
    try:
        with closing(connect(root)) as db, db:
            cursor = db.execute('INSERT INTO users(username,password,created,legacy) VALUES (?,?,?,?)',
                                (username, encoded, int(time.time()), int(legacy)))
            uid = cursor.lastrowid
        return {'id': uid, 'username': username, 'legacy': int(legacy)}
    except sqlite3.IntegrityError:
        raise ValueError('该用户名不可用，请换一个。') from None

# 兼容原始 ark 账号的初始化。新部署必须预先准备私有 panel.key 文件；不要随源码分发。
def initialize(root):
    Path(root).mkdir(mode=0o700, parents=True, exist_ok=True)
    with closing(connect(root)) as db:
        exists = db.execute("SELECT 1 FROM users WHERE username='ark'").fetchone()
    if not exists:
        # Reserve the original account before accepting public registration.
        password = (Path(root) / 'panel.key').read_text().strip()
        create_user(root, 'ark', password, legacy=True)

# 用服务端生成的用户数字 ID 隔离目录，不用用户输入的名字拼文件路径。
def user_root(root, user):
    if user['legacy']:
        return Path(root)
    # Only server-generated integer IDs determine private paths.
    path = Path(root) / 'users' / str(int(user['id']))
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path

def all_users(root):
    with closing(connect(root)) as db:
        return [dict(r) for r in db.execute('SELECT id,username,legacy FROM users ORDER BY id')]

def authenticate(root, username, password):
    if not isinstance(username, str) or not isinstance(password, str) or len(password) > 128:
        return None
    with closing(connect(root)) as db:
        row = db.execute('SELECT * FROM users WHERE username=?', (username.lower(),)).fetchone()
    # Perform the same expensive hash for missing users.
    encoded = row['password'] if row else '00'*16 + ':' + '00'*64
    if not verify(password, encoded):
        return None
    return {'id': row['id'], 'username': row['username'], 'legacy': row['legacy']} if row else None

# 给浏览器随机会话令牌；数据库只存其 SHA-256 摘要和过期时间。
def new_session(root, user):
    token = secrets.token_urlsafe(32)
    at = int(time.time())
    with closing(connect(root)) as db, db:
        db.execute('DELETE FROM sessions WHERE expires<=?', (at,))
        db.execute('INSERT INTO sessions VALUES (?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(), user['id'], at + SESSION_SECONDS))
    return token

def session_user(root, token):
    if not token or len(token) > 128:
        return None
    with closing(connect(root)) as db:
        row = db.execute('SELECT u.id,u.username,u.legacy FROM sessions s JOIN users u ON u.id=s.user_id WHERE digest=? AND expires>?',
                         (hashlib.sha256(token.encode()).hexdigest(), int(time.time()))).fetchone()
    return dict(row) if row else None

def logout(root, token):
    with closing(connect(root)) as db, db:
        db.execute('DELETE FROM sessions WHERE digest=?', (hashlib.sha256(token.encode()).hexdigest(),))

# 记录认证尝试并限流，限制按 IP 和用户名维度的频繁登录/注册。
def rate_limit(root, identity, username, registering=False):
    at = int(time.time())
    keys = [('ip:' + identity, 15 if not registering else 5),
            ('name:' + str(username).lower()[:32], 15)]
    with closing(connect(root)) as db, db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM attempts WHERE at < ?', (at - 900,))
        for key, limit in keys:
            count = db.execute('SELECT COUNT(*) FROM attempts WHERE key=?', (key,)).fetchone()[0]
            if count >= limit:
                return False
        for key, _ in keys:
            db.execute('INSERT INTO attempts VALUES (?,?)', (key, at))
    return True

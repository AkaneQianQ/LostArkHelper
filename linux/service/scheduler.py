"""Coalesce missed schedule slots into the latest one; never replay a backlog."""
from datetime import timedelta
import threading
import store
import automation
import helper
import credentials


# 找最近一个已经到期的时间槽，多个错过时间合并为一次，不逐个补跑。
def latest_slot(settings, at):
    if not settings['enabled']:
        return None
    if settings['mode'] == 'hourly':
        slot = at.replace(minute=settings['minute'], second=0, microsecond=0)
        return slot if slot <= at else slot - timedelta(hours=1)
    for offset in (0, 1):
        day = at - timedelta(days=offset)
        candidates = [day.replace(hour=int(t[:2]), minute=int(t[3:]), second=0, microsecond=0)
                      for t in settings['times']]
        past = [t for t in candidates if t <= at]
        if past:
            return max(past)


# 有凭据且计划启用时执行最新时间槽；SQLite 唯一 slot 与操作锁共同避免重复提交。
def tick(root, at=None):
    if not credentials.exists(root):
        return
    slot = latest_slot(store.settings(root), at or store.now())
    if slot is not None:
        # UNIQUE slot in SQLite + process lock makes this idempotent across wakeup/restart.
        automation.execute_user(root, helper, scheduled_at=slot)


# 后台线程每 15 秒检查一次；stop 事件用于可及时响应的安全退出。
def serve(root, stop):
    while not stop.is_set():
        try:
            tick(root)
        except Exception:
            # API results belong in private run history; avoid dumping credentials/tracebacks.
            print('调度检查失败，将在下一次检查时核对计划。', flush=True)
        stop.wait(15)

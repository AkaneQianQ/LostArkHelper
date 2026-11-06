"""Nonblocking cross-process lock on Windows and POSIX."""
import os

# Windows 锁定文件首字节；POSIX 使用 flock。两者都能跨进程互斥，不能用普通 threading.Lock 代替。
def acquire(fd, blocking=False):
    if os.name == 'nt':
        import msvcrt
        if os.fstat(fd).st_size == 0:
            os.write(fd, b'\0')
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            if exc.errno in (13, 11, 36):
                raise BlockingIOError() from None
            raise
    else:
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))

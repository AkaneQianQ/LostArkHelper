"""Linux 独立版使用发行包里的 systemd 用户服务，不从网页修改系统。"""
def state():
    return {'enabled': False, 'supported': False, 'matches_current': False}


def set_enabled(enabled):
    raise OSError('请使用安装包中的 install-user-service.sh 管理登录自启。')

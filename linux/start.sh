#!/bin/sh
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
export XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DATA="$XDG_DATA_HOME/LostArkHelper"
umask 077
mkdir -p "$DATA"
chmod 700 "$DATA"
# 启动器内部的实例锁负责并发；不能以 instance.lock 文件存在判断进程活着。
nohup ./LostArkHelper --no-browser >>"$DATA/service.log" 2>&1 </dev/null &
tries=0
while [ "$tries" -lt 60 ]; do
  if ./LostArkHelper --open-url 2>/dev/null; then
    echo '本机浏览器可打开上方地址；远程部署请先建立 SSH 本地端口转发。'
    exit 0
  fi
  tries=$((tries + 1))
  sleep 1
done
echo '服务未就绪，请查看数据目录下 service.log。' >&2
exit 1

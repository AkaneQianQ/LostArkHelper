#!/bin/sh
set -eu
ROOT="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
case "$ROOT" in *'%'*|*'"'*|*'\'*|*'
'*) echo '请放在不含百分号、引号、反斜杠或换行的目录。' >&2; exit 1;; esac
mkdir -p "$HOME/.config/systemd/user"
if [ "${1:-}" = '--disable' ]; then
    systemctl --user disable --now lostark-helper.service
    exit 0
fi
# 使用用户级服务：登录用户才运行。是否允许退出登录后继续运行由管理员配置 linger。
cat > "$HOME/.config/systemd/user/lostark-helper.service" <<EOF
[Unit]
Description=Lost Ark standalone local helper
After=network-online.target
[Service]
Type=simple
ExecStart="$ROOT/LostArkHelper" --no-browser
WorkingDirectory="$ROOT"
Restart=on-failure
RestartSec=10
TimeoutStopSec=300
UMask=0077
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now lostark-helper.service
echo '已启用当前用户的 systemd 服务，运行 open-workbench.sh 获取本机访问地址。'

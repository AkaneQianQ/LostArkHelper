#!/usr/bin/env bash
# 在 Linux x86_64 构建，PyInstaller 不能在 macOS 上交叉编译 Linux 程序。
set -euo pipefail
cd "$(dirname "$0")"
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
  echo '请在 Ubuntu 22.04 x86_64（或兼容环境）构建。' >&2; exit 1;
}
PYTHON="${PYTHON:-python3}"
[[ -f "$PWD/../VERSION" ]] || { echo '缺少源码根目录 VERSION。' >&2; exit 1; }
# CI 在调用前安装 requirements-build.txt；此处不修改调用者的 Python 环境。
"$PYTHON" -m unittest discover -s tests -v
cp "$PWD/../VERSION" "$PWD/VERSION"
"$PYTHON" -m PyInstaller --noconfirm --clean --onefile --name LostArkHelper \
  --paths "$PWD/service" --add-data "$PWD/dist:dist" --add-data "$PWD/service/activity.json:service" --add-data "$PWD/VERSION:." \
  --distpath build/bin --workpath build/pyinstaller --specpath build "$PWD/launcher.py"
PACKAGE=release/LostArkHelper-Linux-x64
mkdir -p "$PACKAGE"
cp build/bin/LostArkHelper "$PACKAGE/LostArkHelper"
cp "$PWD/../VERSION" "$PACKAGE/VERSION"
cp start.sh stop.sh open-workbench.sh install-user-service.sh README.md "$PACKAGE/"
chmod 755 "$PACKAGE/LostArkHelper" "$PACKAGE/"*.sh
"$PYTHON" tests/smoke_frozen.py --exe "$PACKAGE/LostArkHelper"
# 只归档明确的运行文件，不包含本地账号、密钥、构建缓存或源码开发环境。
tar -C release -czf release/LostArkHelper-Linux-x64.tar.gz LostArkHelper-Linux-x64
echo '已生成 linux/release/LostArkHelper-Linux-x64.tar.gz'

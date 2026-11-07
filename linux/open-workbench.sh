#!/bin/sh
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
# URL 含本机访问令牌，仅在自己的终端/浏览器使用，不要公开分享。
exec ./LostArkHelper --open-url

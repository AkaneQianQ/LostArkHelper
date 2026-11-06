$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3 -m venv .build-venv
if ($LASTEXITCODE -ne 0) { throw "创建 Python 环境失败" }
$Python = Join-Path $PSScriptRoot ".build-venv\Scripts\python.exe"
& $Python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw "安装构建依赖失败" }
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "测试失败，停止构建" }
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name LostArkHelper --distpath release --paths service --add-data "dist;dist" --add-data "service/activity.json;service" --collect-submodules encodings background.pyw
if ($LASTEXITCODE -ne 0) { throw "打包失败" }
Write-Host "完成：release\LostArkHelper\LostArkHelper.exe（请分发整个 LostArkHelper 文件夹）"

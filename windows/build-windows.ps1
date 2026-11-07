# ASCII script to work in Windows PowerShell 5.1 and PowerShell 7.
# Build in Windows: the resulting EXE bundles Python and needs no user install.
param(
    [ValidateSet('onefile', 'onedir')]
    [string]$Mode = 'onefile',
    [string]$PythonExecutable = ''
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '..\VERSION')) { throw 'Run build from the full source tree with VERSION at repository root' }
Copy-Item '..\VERSION' VERSION -Force
if ($PythonExecutable) {
    & $PythonExecutable -m venv .build-venv
} else {
    py -3 -m venv .build-venv
}
if ($LASTEXITCODE -ne 0) { throw 'Failed to create build environment' }
$Python = Join-Path $PSScriptRoot '.build-venv\Scripts\python.exe'
& $Python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
& $Python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped' }
& $Python -m PyInstaller --noconfirm --clean "--$Mode" --windowed --name LostArkHelper --distpath release --paths service --add-data 'dist;dist' --add-data 'service/activity.json;service' --add-data 'VERSION;.' --collect-submodules encodings background.pyw
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
$Exe = if ($Mode -eq 'onefile') { 'release\LostArkHelper.exe' } else { 'release\LostArkHelper\LostArkHelper.exe' }
& $Python tests\smoke_frozen.py --exe $Exe
if ($LASTEXITCODE -ne 0) { throw 'Packaged EXE smoke test failed' }
Write-Host "Ready: $Exe"
if ($Mode -eq 'onedir') { Write-Host 'Distribute the entire LostArkHelper directory.' }

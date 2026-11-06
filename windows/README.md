# Windows 免 Python 单文件版（2026-11-06 更新）

现已可以构建并直接运行 LostArkHelper.exe，使用说明见 EXE使用说明.md。无需 Python，后台运行。升级前停止旧服务，使用原本数据目录；旧版自启记录需要在 exe 版中关闭再开启以更新路径。

GitHub Actions 的 Windows x64 环境中 13 项测试全部通过，含 DPAPI，生成的 EXE 通过隔离 Python PATH 的启动、网页、鉴权、重复启动与安全退出检查。未调用真实游戏 API。默认浏览器打开、Windows 10/11 用户桌面的登录自启需用户验证。

重新构建：Windows 中执行 build-windows.ps1，默认输出 release/LostArkHelper.exe；-Mode onedir 可保留目录构建。下方是先前源码版的历史说明，其中“没有 exe / 未完成 Windows 测试”的描述已被本节更新。

---

# 0.1.2 后台运行版使用说明（优先于下方旧版本说明）

1. 先在旧终端按 Ctrl+C，等待服务停止，再更新文件；不要强行关闭正在领奖的进程。
2. 解压新版到固定本地目录，双击 **启动助手.vbs**。它会后台运行服务并打开浏览器，终端无需保持打开。需要 Python 3.11+ 及 py 启动器。
3. 关闭浏览器不会停止服务；再次双击可重新打开工作台。
4. 工作台「定时设置 → 启动设置 → 停止本地服务」可以退出，服务会等待已经开始的操作完成。开机自启不会因此被关闭。
5. 若启用过开机自启，请在新版中关闭再开启一次，更新为 background.pyw 入口。未登录 Windows、休眠和关机时仍无法执行。
6. 启动日志：`%LOCALAPPDATA%\LostArkHelper\service.log`，自动轮转；错误时可运行「调试启动.cmd」查看。

`启动助手.cmd` 仅用于转交后台入口，可能短暂闪现；VBS 本身不显示终端。若系统未安装或禁用 VBScript，可右键 background.pyw 使用 Python（窗口版/pythonw.exe）打开。exe 构建改为 PyInstaller windowed，构建后也无控制台。

此包尚未在 Windows 实测 VBS、窗口版 exe 和完整退出流程；已有通用 API/调度测试通过，Windows DPAPI 仍按平台跳过。cmd 文件已使用 GBK + CRLF；原终端模式保留为「调试启动.cmd」。

---

# 命运方舟助手 Windows 本地服务版 · 0.1.0

本包为可在 Windows 启动的源码发行版，包含已构建的网页。不需要 Node.js，不连接原来的云后台；游戏请求由电脑直接发送到腾讯官方接口。

当前尚未在真实 Windows 环境完成运行/打包验收；没有附带已验证的 exe。开发主机为 macOS，Windows SSH 通道未连接成功。通用逻辑和本地 HTTP 已测试，Windows DPAPI 测试需在 Windows 执行。

## 立即使用

1. 在 Windows 10/11 安装 Python 3.11 或更新版本（建议 3.12，包含 Python Launcher `py`）。
2. 解压整个包，双击 `启动助手.cmd`。
3. 程序在本机启动，自动打开默认浏览器，无需注册、登录密码。
4. 在“账号管理”粘贴自己官方 App 的完整活动链接，先刷新核对角色/状态。
5. 可手动签到领奖，或在“定时设置”开启计划。

默认只监听 `127.0.0.1:18745`；端口占用时使用随机可用端口。重复启动会打开已有实例的页面。浏览器关闭后服务继续运行；在终端按 Ctrl+C 安全退出。不要在操作提交过程中强制关闭窗口。

使用命令行可指定端口或不自动打开浏览器：

```powershell
py -3 launcher.py --port 18745
py -3 launcher.py --no-browser
```

本机访问令牌由启动器产生，浏览器收到 HttpOnly/SameSite Cookie。每次重启服务后旧浏览器会话失效，请重新双击启动器打开。不要向他人分享启动器生成的带 key 地址。

## 功能范围

- 一个本机游戏账号，可刷新同一账号和角色的登录链接。当前未提供多账号切换。
- 查询签到/任务、未签到时签到、领取已验证任务；提交前后核对状态。
- 活动 2611，白名单 ID 1、2、3、4、5、12、13，领取参数均为 type=1。
- 定时计划、手动/自动执行历史保存到 SQLite。
- 每小时指定分钟或每天指定时间，均按北京时间 UTC+8。
- 电脑恢复或应用重启时，只合并执行最近一次应执行计划，不逐小时补跑；新启用计划也可能立即检查最近一次计划。
- 操作串行及程序单实例；提交结果不确定时立即停止后续写操作，保存待确认标记。

Windows 凭据使用当前用户的 DPAPI 加密，无明文回退。只在用户登录且程序运行时执行；不依赖 systemd/云服务。系统休眠、断网和关机会影响执行。

## 本地数据

`%LOCALAPPDATA%\LostArkHelper\`

- `credentials.dpapi`：Windows 当前用户加密的游戏凭据。
- `automation.sqlite3`：计划和执行记录。
- `pending-operation.json`：未确认提交标记，不含原始凭据。
- `instance.json`：本机启动会话信息，含访问令牌；不要分享。
- 锁文件：避免重复实例、并发提交。

DPAPI 不能防御同一已登录 Windows 用户权限下的恶意软件。不要把数据目录公开共享。更换 Windows 用户/重装系统后请重新导入链接，不保证加密文件可迁移。

结果未确认时，程序只查询核对；确认已签到/任务已领取后解除标记，否则继续阻止提交。若官方 App 已人工核实但标记无法自动解除，请先安全停止服务，再备份和人工处理 pending-operation.json，不能在未知结果时直接清除以强行重试。

本版未迁移服务器上的任何账号凭据或计划。首次运行默认不开启定时任务。避免本地与服务器同时调度同一账号。

## 构建 exe

必须在 Windows 上构建。PowerShell 进入包目录：

```powershell
powershell -ExecutionPolicy Bypass -File .\build-windows.ps1
```

脚本创建独立构建环境、安装锁定的 PyInstaller、执行测试，再输出：

`release\LostArkHelper\LostArkHelper.exe`

请分发整个 `LostArkHelper` 文件夹，不能只复制 exe。保留控制台便于明确程序运行/停止状态。构建环境需要联网下载 Python 构建依赖；日常使用不依赖 PyInstaller。

网页已构建并包含于 dist/assets。修改页面时再进入 web 目录安装 Node 依赖和重建，不是使用本服务的前置条件。旧 server 目录/登录页面源文件如仍在 web 工程中不参与本地后端启动。

## 验证

```powershell
py -3 -m unittest discover -s tests -v
```

开发主机：9 项测试中 8 项通过、1 项 Windows DPAPI 测试按平台跳过。覆盖单实例/操作锁、SQLite 计划去重、错过计划合并、未知提交阻断与下次确认、本地 Host/Origin/Cookie 访问限制及计划保存。网页生产构建成功，浏览器检查过本机免登录入口、账号导入入口和定时页面。未用真实凭据触发签到/领奖。

Windows 验收还需确认：DPAPI 往返测试、锁互斥、双击启动与二次启动、打包 exe 资源加载、同账号链接导入/更新、计划运行、休眠恢复与安全退出。

## 项目文件

- launcher.py：启动/单实例/浏览器入口/调度线程。
- service/app.py：本地网页与 API。
- service/credentials.py：Windows DPAPI。
- service/platform_lock.py：Windows msvcrt / POSIX flock。
- service/scheduler.py：应用内调度，最近时间槽合并。
- service/automation.py：写操作、状态确认、待确认持久化、运行记录。
- service/activity.json：当前活动与任务白名单。
- service/helper.py、import_link.py：原项目接口与链接解析。
- web/：本地版前端源代码；dist/：可直接使用的构建产物。

后续新增接口或任务，必须同步服务器、本地版、快捷指令的适用配置；特殊白名单差异需明确记录。此次仅开发本地版本，没有修改云服务器或快捷指令。

## 0.1.1：开机自启开关

工作台「定时设置 → 启动设置」提供「登录 Windows 后自动启动」，开启/关闭立即保存。使用当前用户 HKCU\Software\Microsoft\Windows\CurrentVersion\Run 中的 LostArkHelper 值，无需管理员权限；关闭只移除本程序的值。

自启带 --no-browser，不自动打开网页；源码版优先使用 pythonw.exe，无控制台。exe 目前仍为控制台构建，登录后可能出现运行窗口，不承诺静默托盘；可手动再次启动以打开工作台。移动程序目录后应在网页重新开启以更新位置。Windows 启动应用管理器/安全软件仍可能禁用启动项，网页读取的是注册表配置，不保证操作系统最终放行。

12 项测试中 11 通过、Windows DPAPI 测试跳过。自启新增测试使用模拟注册表验证开启、关闭、外部位置变化及路径引用；真实 Windows 登录自启仍待实测。开发主机不会修改任何实际 Windows 启动设置。

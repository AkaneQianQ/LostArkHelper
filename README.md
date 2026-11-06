# 命运方舟助手 · 三端完整源码

整理日期：2026-11-05。当前为可直接浏览的中文注释版目录，无需解压。

第一次阅读请先打开 `docs/代码阅读指南.md`。核心 Python、前端和快捷指令已补中文注释；注释版未覆盖线上服务或现有设备副本。包含服务器当前部署版本、iPhone 单快捷指令、Windows 本地后台服务。没有附带真实账号、Cookie、token、数据库、密码、Tunnel 配置、抓包原文或截图。

## 目录

- server/service：从运行中服务器取回的 Python 后端及活动配置。
- server/web：React/Vite 前端源码，已清理未引用的模板演示页面。
- server/dist：从服务器取回的已部署网页。
- server/deploy：后台、定时执行器的 systemd 单元。
- windows：0.1.2 本地后台服务源码、网页、测试和 Windows 构建脚本。
- shortcuts/source/workflow.json：最新快捷指令动作图，唯一构建输入。
- shortcuts/build.py：直接从动作图构建，不再依赖历史补丁顺序。
- shortcuts/releases：已签名的小队任务版快捷指令。
- shortcuts/tests：19 项模拟与结构测试。
- shortcuts/tools/history：历史生成和补丁脚本，仅供追溯，不能作为当前构建入口。
- activity-manifest.json / verify_activity.py：三端活动及白名单核对。
- SHA256SUMS.txt：文件校验清单。

web 保留现有界面及上游 LICENSE；未引用演示业务已移除，一些上游静态资源仍保留。无需原开发目录即可使用/重建。

## Windows

安装 Python 3.11+ 和 py 启动器，解压后双击 windows/启动助手.vbs。后台运行并打开工作台；关闭浏览器不退出，定时设置中可停止服务或设置登录自启。旧服务先停止再升级，已有自启记录应关闭再开启。

Windows 上运行 build-windows.ps1 可构建 windowed exe，输出 release/LostArkHelper；必须分发整个目录。现已增加 GitHub Actions 的 Windows x64 单文件构建；2026-11-06 的成品运行检查已通过，见下方最新记录。详细使用以 windows/README.md 顶部 0.1.2 说明为准，下面保留了版本历史。

数据在 %LOCALAPPDATA%\LostArkHelper，凭据由当前用户 DPAPI 加密，不随源码迁移。cmd 已采用 CRLF/GBK，默认 VBS 后台启动，调试启动.cmd 保留终端。

## 服务器

建议 Python 3.11+。后端仅监听 127.0.0.1:18745，公网反向代理/Tunnel 保持在代码之外。本包不安装系统服务、不包含云端用户状态。

deploy 单元按既有 /opt/lostark-dashboard 路径使用；新部署需自行核对目录、权限和 systemd 用户配置。环境变量 ARK_HELPER_DIR 指向私有状态目录，ARK_STATIC_DIR 指向 dist，ARK_PORT 默认 18745。现有 auth.initialize 首次初始化会从状态目录 panel.key 读取原 ark 用户密码，需在目标机本地创建随机强密码文件并限制权限，禁止提交入库。用户状态保存在 users/<服务端用户ID>/，不要从现有服务器随意复制凭据。

网页重建（server/web 或 windows/web）：Node 20.19+/22.12+，执行 npm ci，再执行 npm run build -- --outDir ../dist。源码清理后两端均已重新构建，服务器产物资源名与线上一致。

## 快捷指令

```bash
python3 shortcuts/build.py
python3 -m unittest discover -s shortcuts/tests -v
```

签名需要 macOS 自带 shortcuts CLI。Windows/Linux 可加 --unsigned-only 生成未签名 plist，不能将其当成可导入 iPhone 的签名文件。releases 已提供签名版，首次粘贴官方活动链接，保存至 iCloud Drive/Shortcuts/lostark-local-link.txt。含真实链接的文件不要分享。

修改动作图后使用统一 build.py 重新签名，不要运行 tools/history 下的旧补丁。workflow.json 就是快捷指令源码，后续新任务应同步动作图中的筛选与完整提交/确认分支。

## 当前版本和维护要求

活动 2611。服务器及 Windows 白名单为 1、2、3、4、5、12、13；快捷指令为 2、3、4、5、12、13。ID 1 的历史差异明确保留，不能静默放宽。领取参数均为 type=1，任务列表分类不能直接作领取参数。

以后新增接口/任务必须同步服务器、本地版和快捷指令，记录抓包成功证据、前后状态和三端验证。1224 号角色详情二进制请求未接入，不在本包中保存原请求。

## 验证与已知边界

- 快捷指令统一构建/Apple 签名成功，19 项测试通过；新增小队任务版未在本会话完成手机全流程实测。
- 2026-11-06：GitHub Windows Server 2022 x64 环境中 13 项测试全部通过，含真实 DPAPI 和进程锁；单文件 EXE 在移除 Python PATH 后通过启动、鉴权、网页资源、单实例和安全退出检查。个人 Windows 10/11 的默认浏览器弹出及登录自启仍待用户验收。
- Windows 终端启动修复来自用户提供的 Windows 排查结论，不等同于全部业务测试通过。
- 服务器后端保持线上原样。发现现有 automation 在某个提交报错后仍可能继续后续候选，未在这次打包中静默修改云端；Windows 版已改为立即停止并持久化待确认状态。后续应单独修复并部署服务器这一差异。
- 三端未共享运行时锁，避免多个端同时自动操作同一账号。
- 不含实际账号数据，测试没有触发真实签到/领奖。

## Windows 单文件 EXE（2026-11-06）

GitHub Actions → Build Windows EXE → Run workflow 可重新构建。默认 onefile + windowed，最终用户只需 LostArkHelper.exe，不需要 Python。构建脚本仍支持 -Mode onedir 以便排查打包问题。

构建代码提交：5e44439。已通过的构建与成品检查：https://github.com/youboRepo/LostArkHelper/actions/runs/42238450932 。Actions 产物默认保留 30 天，过期后可重建。

本轮 Windows 测试发现 SQLite 的 with 语句只提交/回滚、不关闭连接，已在本地版 store.connect 中显式关闭，并加入事务成功/异常都关闭的测试。未修改服务器代码。

查看 windows/EXE使用说明.md。升级前先停止旧服务；同一个 Windows 用户下数据目录保持不变。二进制无商业代码签名，不含真实账号和游戏凭据，检查未执行真实游戏操作。

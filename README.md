# 命运方舟助手

v0.2.0，活动版本 2611。包含服务器、Windows 本地版、Linux 本地版及 iPhone 单快捷指令。Windows/Linux 解压即可运行，无需安装 Python，也无需注册助手账号；服务器版保留多用户登录和独立计划。

从 [GitHub Releases](https://github.com/youboRepo/LostArkHelper/releases) 下载：

| 版本 | 下载文件 | 使用方式 |
| --- | --- | --- |
| Windows x64 | LostArkHelper-Windows-x64-v0.2.0.zip | 完整解压，双击目录中的 LostArkHelper.exe |
| Linux x64 | LostArkHelper-Linux-x64-v0.2.0.tar.gz | 解压，运行 ./start.sh，浏览器打开工作台 |
| 服务器 | LostArkHelper-Server-v0.2.0.tar.gz | Python 服务源码、网页成品及 systemd 单元，见包内 README |
| iPhone | LostArkHelper-iPhone-v0.2.0.shortcut | 在 iPhone 上下载并用快捷指令 App 导入 |

Windows/Linux 服务保持后台运行；关闭网页不退出，可在工作台停止。Windows 在工作台设置用户登录自启；Linux 使用安装脚本配置 systemd 用户服务。Linux 成品在 Ubuntu 22.04 x64 构建，需要 glibc 2.35+，不适用于 Alpine/musl 或 ARM。

## 自动处理哪些任务

支持任务 ID 1–13：登录游戏、星辰护卫、卡杰洛斯、影子副本、混沌地牢/库尔赞前线、极焰的沙漏、累计签到 7/14/21/28 天、首次查看规则、首次组建 4 人小队、小队登录游戏。

任务 6–11 的领取参数依据统一接口推断，尚无逐项成功抓包，不能声称已经真实领奖验证。它们与已收录任务共用 partnergettaskreward2611、task_id、type=1。只在官方返回 status=1 时领取；不会代替玩家完成副本、查看活动规则或组队条件。未知、重复、未完成或已领取任务跳过。

签到成功后刷新任务，可在同次执行领取刚解锁的累计奖励。提交前后重新查询；异常或无法确认成功时立即停止。服务器和本地版持久保存 pending-operation.json，后续先查询确认，结果仍不明确则阻止再次提交。手机在当前执行中停止；不同端之间没有共享锁，请选择一个端为同一账号执行自动计划。

## 源码与构建

- server/：多用户后端、React/Vite 网页、部署单元与测试。
- windows/：Windows 本地后台服务、DPAPI 凭据存储、登录自启及原生构建。
- linux/：Linux 独立本地服务、加密凭据、用户自启及原生构建。
- shortcuts/：iPhone 动作图、构建签名工具、模拟与结构测试。
- activity-manifest.json / verify_activity.py：核对四端的活动配置。
- tools/package_release.py：生成 ZIP/tar.gz，包内附 SHA256SUMS.txt。
- .github/workflows/release-build.yml：Windows/Linux 原生构建、单元与成品启动检查、服务器打包。

各目录有中文注释和使用说明，阅读顺序见 docs/代码阅读指南.md。运行 `python3 verify_activity.py` 检查配置一致。前端未改变功能，已附网页成品；重建时在 web/ 下运行 npm ci，再运行 npm run build -- --outDir ../dist（Node 20.19+/22.12+）。

iPhone 动作图唯一来源是 shortcuts/source/workflow.json。`python3 shortcuts/build.py` 在 macOS 上调用 Apple CLI 签名，生成的文件用于 iPhone；构建机器平台不代表快捷指令仅可在 Mac 使用。不要运行 tools/history 内的历史补丁。签名及模拟测试不能替代手机真机测试。

## 数据与验证边界

发行包不包含真实活动链接、账号、token、Cookie、数据库或抓包原文。Windows 凭据由当前用户 DPAPI 加密；Linux 使用独立用户密钥加密，密钥与密文同机保存，只能保护单独泄露密文的情形。详细数据路径和迁移方式见各端 README。

自动测试不调用真实游戏接口；Windows/Linux 在对应 GitHub 原生环境测试冻结成品的启动、网页、鉴权、单实例及停止。个人设备的浏览器唤起、自启和 iPhone 全流程需设备验收。推断任务实际可领与否仍以活动官方响应为准。1224 号二进制角色详情请求未接入。

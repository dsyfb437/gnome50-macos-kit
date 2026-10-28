# Ubuntu 26.04.1 / GNOME 50.1 macOS 风格整合包

**本轮补齐：** [补齐记录](docs/补齐记录.md)：传统 GTK3 菜单兼容入口已补齐并完成真实动作回传测试，Rime 已加入可选组；Spotlight 补丁已备份应用到文件，保持启用，等待下次登录加载与验证。

**最新：** 用户已要求应用明确修复；[已应用修复记录](docs/已应用修复.md)优先于下方历史状态。Spotlight 已恢复启用，GTK4 8 处语法错误已修复，Orbit 用户级 daemon 已补齐且真实菜单动作回传测试通过。

核验日期：2026-10-28（北京时间）。版本：0.1.0。默认只检查；不会自动安装、启用或更新任何上游项目。

本方案以用户已经使用的 WhiteSur Light、Dhruva、Orbit、Inter 和 GNOME 原生手势为基线。借鉴整合项目的模块化、固定提交、状态检查、备份与恢复方式，不把六套桌面安装器拼接执行。

**第二阶段已连接实际 GNOME 会话并完成概览对照测试。** [最新实际验证报告](docs/实际桌面验证.md)记录了 Spotlight 停用前后 291→0 条警告、当前 GTK4 样式 8 处错误、Orbit 缺少 daemon 和实际输入法状态。仅将 Spotlight 按用户指定基线停用；主题、输入法和其他扩展未改动。下文隔离测试与初始验收单保留作复用资料，不能当作全部视觉项目已经验收通过。

## 先阅读

- [仓库审计与不可直接复用的安装行为](docs/仓库审计.md)
- [测试范围、结果与限制](docs/测试报告.md)
- [本机验收步骤](docs/本机验收.md)
- [固定提交与关键文件 SHA-256](upstreams.lock.json)

## 保留的组合

| 层次 | 基线与取舍 |
|---|---|
| 主题 | WhiteSur Light GTK3 / GTK4 / Shell；保留现有 GTK4 文件，暂不重铺 |
| 图标、光标、字体 | 已安装的 WhiteSur / WhiteSur-cursors / Inter 11，光标大小 28；实际主题目录名先检查 |
| Dock、动画 | Dhruva，完整保留修改过的 GenieEffect.js；不增加 Flourish、Magic Lamp 或第二个 Dock |
| 顶栏 | Just Perfection 保留当前值；Blur My Shell 顶栏开、overview 关；Orbit 作为唯一全局菜单 |
| 标题与锁屏 | Window Title Pro 与 Orbit 的标题显示做人工去重；WACK Sonoma 保留当前 cupertino 配置 |
| 输入与辅助 | Clipboard Indicator、Kimpanel、Sushi、Fcitx5 + Rime 保留 |
| 搜索 | Spotlight 扩展维持禁用；优先 GNOME 原生应用搜索，暂不新增概览扩展 |
| 显示 | 166% 缩放保留；不自动修改 monitors.xml、Mutter 缩放功能或文本缩放 |

严格排除：电源、合盖、休眠、充电阈值、GDM、Plymouth、引导器、分区、Windows 快速启动及任何双系统启动设置。无 sudo，无包管理器调用，无重启/注销命令，无关闭扩展版本校验的路径。

## 使用方法

在解压后的项目目录运行。依赖 Python 3.10+、GNOME 自带的 gsettings / dconf；实际应用需要用户会话总线。字体模块还需要 fc-match。不要使用 sudo。

```bash
# 默认只读；JSON 输出包含当前值、扩展元数据、GenieEffect.js 哈希及冲突提示
python3 desktop.py

# 显示可选模块和参数
python3 desktop.py --help

# 预览：不创建备份、不改任何配置；apply 不写 --execute 时也是此行为
python3 desktop.py apply --module panel-blur --dry-run

# 预览完整备份，然后明确执行；会复制用户文件，需有足够空间
python3 desktop.py backup --module all --dry-run
python3 desktop.py backup --module all --execute
```

备份保存在 `${XDG_STATE_HOME:-$HOME/.local/state}/gnome50-macos-kit/backups/`，每次产生唯一目录，权限受 umask 077 限制。可将 XDG_STATE_HOME 临时设到容量充足的私人外置磁盘目录；它不能位于待备份的主题、GTK 或扩展目录内。备份位置的上级路径不能经过符号链接。

本工具不会扫描或修改整个家目录。备份包含个人词库和自定义菜单，不能提交到公开 Git 仓库。备份不包含 Windows、浏览器密码或电源设置。

### 可应用的模块

每个模块必须明确选择，支持重复 `--module`；apply 不支持 `all`。

| 模块 | 可写入内容 |
|---|---|
| appearance | GTK 主题 WhiteSur-Light、图标 WhiteSur、光标 WhiteSur-cursors / 28、prefer-light |
| font | 仅界面字体 Inter 11；不改终端、编辑器字体 |
| buttons | 左侧 close,minimize,maximize |
| shell-theme | User Themes 的主题名 WhiteSur-Light；不启用扩展 |
| panel-blur | Blur My Shell panel blur=true、overview blur=false |

```bash
# 首先查看计划。以下是示例，不代表需要对现有桌面重新应用。
python3 desktop.py apply --module appearance --module font --dry-run

# 用户确认这些目标符合实际目录名后，才自行执行所选模块
python3 desktop.py apply --module panel-blur --execute
```

实际应用先检查 Shell 为 50.x、设置是否存在和可写、主题资源/Inter 是否存在。扩展设置定义可从已安装的用户级或系统级 `schemas` 读取。缺少定义时退出，不强装扩展，也不自动编译或更新用户现有扩展。写入使用 gsettings 校验类型和范围，并读回结果；中途出错会恢复操作前快照。

appearance 不会安装主题、改写 GTK4 文件或把所有应用都变成浅色；VS Code、Ptyxis 自己的深色偏好仍须分别验证。实际图标名若是 WhiteSur-light 等变体，请保留当前值，不要运行 appearance。

### 备份与恢复模块

除上述设置模块外，以下模块可备份、恢复，但不能用 apply 写入预设：

| 模块 | 范围 |
|---|---|
| gtk3 / gtk4 | XDG_CONFIG_HOME 中对应的 gtk-3.0 / gtk-4.0 目录 |
| themes / icons / fonts | 用户传统目录与 XDG 数据目录；fonts 还包含 fontconfig |
| extension-files | 用户级扩展完整源码；包括 Dhruva 本地修改 |
| extension-settings | 仅 `/org/gnome/shell/extensions/` 参数子树；不含启用列表 |
| input-method | 用户 Fcitx5 配置与数据目录，包含通常位于其中的 Rime 用户词库 |
| orbit-files | 用户 global-menu 自定义菜单 |
| menu-runtime | 本包新增的用户级 Orbit daemon、GTK3 模块及两个启动入口；恢复前需停用 Orbit，让 daemon 停止 |

`all` 备份会将 shell-theme / panel-blur 并入 extension-settings，避免重复恢复同一路径。扩展设置恢复会精确替换该参数子树，但不恢复 `/org/gnome/shell/enabled-extensions`，不会重新启用 Spotlight。恢复前仍应先预览；这不是跨版本配置迁移器。

```bash
# 将 /绝对路径/备份 替换为 backup 命令返回的具体目录
python3 desktop.py restore --from /绝对路径/备份 --module gtk4 --dry-run
python3 desktop.py restore --from /绝对路径/备份 --module gtk4 --execute

# 分开恢复参数；不会切换扩展启用状态
python3 desktop.py restore --from /绝对路径/备份 --module extension-settings --dry-run
```

每次实际恢复也会先生成“恢复前”的新备份；要撤销恢复，使用该新备份执行同一个 restore。文件恢复会替换所选模块的整个目录，包括删除备份之后新建的文件，因此必须审阅模块。不存在的原始路径也会恢复为不存在。

工具会验证备份清单与文件哈希，保留符号链接本身，不跟随链接备份其外部目标。**如果 GTK4 指向其他源码目录，必须额外保管链接目标；仅保存链接不能在另一台机器上重建主题。** 主题、图标、字体模块会保存常见的用户资源目录，但系统级资源只记录来源，不复制或恢复 `/usr/share`。

恢复 extension-files 时检测到本用户仍有 gnome-shell 进程会拒绝热替换。先从 GNOME 注销，在文本控制台中用独立用户 D-Bus 会话运行：

```bash
dbus-run-session -- python3 desktop.py restore --from /绝对路径/备份 --module extension-files --execute
```

这只恢复源码。重新登录后先核对扩展元数据是否包含 50、Dhruva 补丁哈希，再人工逐个启用已验证的扩展；Spotlight 仍保持禁用。不要启用 Dash to Dock、TPCT Shell 或另一个全局菜单来“补齐”此包。

恢复会拒绝不同 GNOME 主版本、不同 HOME 路径的备份。XDG 路径变化、新机器迁移、系统级扩展修改、任意目录的 Rime 词库、字体/主题外链目标，需要人工审阅后迁移。备份时关闭词库编辑器和扩展编辑操作；检测到文件在备份期间变化会退出。多文件/多键操作并非断电原子事务，备份应另存到外部存储。

## 固定版本与模块化安装边界

本次六个上游的具体提交和关键文件校验值在 lock 文件中；这些是**审阅基线，不是用户电脑的已安装版本**。后续比较新版本时更新锁文件并重新测试，不能把 `latest` 当成可复现版本。

```bash
# 默认只展示获取计划
python3 sources.py --repo Unmade760/orbit-global-menu --dest /绝对路径/新审阅目录 --dry-run

# 显式获取固定提交并校验关键源码；不会运行其中任何安装器
python3 sources.py --repo Unmade760/orbit-global-menu --dest /绝对路径/新审阅目录 --execute
```

桌面部署采用“保留现有资源 → 版本与哈希清单 → 备份 → 单模块预览 → 单模块应用 → 本机验收”的顺序。本包没有通用第三方安装入口：GTK4 适配先复用当前有效文件，Dock 和 Orbit 先复用当前安装，所缺系统包只在验收清单中检查，不自动补装。这是针对已有配置的整合工具，不能在一台空白机器上自动下载所有组件。

用户当前 Dhruva 版本、PR 地址、补丁内容及其他已安装扩展版本仍待本机状态报告确认。`desktop.py status` 输出包含扩展元数据和 GenieEffect.js SHA-256，配合 extension-files 备份建立本地版本基线；没有凭历史描述重写 GenieEffect.js。

## 搜索与 GTK4 的可复用改进

主题一致性采用同一 WhiteSur 色系、Inter、现有光标和图标。GTK3、GTK4/libadwaita、Shell 是不同层，不能只设一个 gsettings 就声称统一。保留现有 GTK4 覆盖；后续按应用逐个验收浅色、深色、弹窗与标题栏。暂不为 Flatpak 批量开放主题目录或给所有应用设置 GTK_THEME。

启动器先用原生应用搜索；Ulauncher 仅作为未来可选的独立应用候选，需要先检查 Ubuntu 26.04 包、Wayland 全局快捷键和 Fcitx5/Rime 键位。本包不安装 Ulauncher、不绑定 Super+Space，也不启用 Spotlight。TPCT 的 Ulauncher 外观可以参考，但其热键安装代码不直接复用。

Just Perfection 的 32 / 16 / 间距 4、Sonoma cupertino 等既有值通过扩展参数备份保留，不猜测其跨版本键值含义。第三方设置界面的“4”不一定对应原始存储值 4。

## 运行隔离测试

```bash
python3 tests/test_desktop.py
```

测试入口创建临时 HOME、XDG 目录和独立 dbus-run-session，清除显示连接；内部会重置该临时 dconf 数据库。不要手动调用内部 `--inside-isolated-test` 参数。测试不使用用户现有主题资源，不加载 GNOME 扩展，不测动画帧率。

更多结果见测试报告。工具可验证设置和文件恢复行为，166% 显示缩放、Wayland 手势、概览流畅性、菜单与输入法必须按本机验收清单实际确认。

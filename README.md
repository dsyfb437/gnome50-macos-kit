# gnome50-macos-kit

Ubuntu 26.04.1 / GNOME Shell 50.1 的 macOS 风格桌面 bootstrap。只面向**已经装好 WhiteSur、Dhruva、Orbit、Spotlight 等前置**的环境；不是空白机器的一键安装器。

默认只读；所有写入必须显式 `--execute`。不安装 apt 包、不安装扩展、不自动打源码补丁、不碰 GDM/PAM/分区/引导。

当前版本：**1.5.0**。

## 一键入口

```bash
# 只检查 + 展示计划，不写任何文件
./install.sh --dry-run

# 实际应用：已有系统快照
./install.sh --execute --snapshot-ok

# 没有 Timeshift/Snapper 时，明确接受只做用户级配置备份
./install.sh --execute --no-snapshot
```

`install.sh` 只是 `python3 desktop.py bootstrap` 的入口；也可以直接运行：

```bash
python3 desktop.py bootstrap --dry-run
python3 desktop.py bootstrap --execute --snapshot-ok
python3 desktop.py bootstrap --execute --no-snapshot --profile profiles/ubuntu-26.04-gnome-50.json
```

报告写在：

```text
~/.local/state/gnome50-macos-kit/bootstrap-reports/<UTC>-<id>.json
```

报告包含 preflight 检查、plan、备份路径、验收结果、是否已回滚，以及完整 rollback 命令。

## 前置条件

- Ubuntu 26.04.x、GNOME Shell 50.x、Wayland；
- WhiteSur GTK3 / GTK4 / Shell 主题、WhiteSur 图标和光标、Inter 字体；
- 扩展：User Themes、Blur My Shell、Dhruva、Orbit Global Menu、Just Perfection、Ubuntu AppIndicators、Spotlight；
- 已生成 `WhiteSur-MacOS-<hash>` Shell 主题（见下方“手工步骤”）；
- Python 3.10+、`gsettings`、`dconf`、`gnome-extensions`、`fc-match`；
- 以普通用户运行，不要用 sudo。

缺什么先跑：

```bash
python3 desktop.py doctor
```

`doctor` 只做离线检查，按主题、图标、字体、扩展、schema、生成主题列缺失项和提示，不写入。

## Bootstrap 做什么

1. **Preflight**：系统版本、GNOME 版本、会话类型、工具、`doctor`、配置可写、生成主题、扩展是否已安装且启用、补丁检查；
2. **Plan**：逐个模块打印当前值与目标差异，不写文件；
3. **执行**（必须 `--execute` + `--snapshot-ok`/`--no-snapshot`）：创建配置备份 → 写入 → 逐项读回；
4. **验证**：跑只读 `verify`；失败会自动恢复本次配置备份；
5. **报告**：写入 `bootstrap-reports/`，含回滚命令。

`--snapshot-ok` 只是你声明系统快照已存在，工具无法验证；`--no-snapshot` 表示明确接受没有系统级回滚，只依赖用户级配置备份。

## 配置模块

| 模块 | 内容 |
| --- | --- |
| `appearance` | WhiteSur Light GTK/图标/光标、prefer-light |
| `font` | Inter 11 |
| `buttons` | 窗口按钮左置（close/minimize/maximize） |
| `panel-blur` | 顶栏模糊开、概览模糊关 |
| `status-area` | 托盘灰度、全局菜单字号 11、面板指示器间距 6 |
| `macos-dock` | Dhruva 浅色半透明 Dock、关闭实时模糊、BMS dock 模糊关闭 |
| `shell-theme` | 选中生成的 `WhiteSur-MacOS-<hash>` Shell 主题 |

`apply` 可以单独应用某个模块；`install` 按固定顺序应用全部视觉模块。两者默认 dry-run。

## Profile

默认 profile：`profiles/ubuntu-26.04-gnome-50.json`。

它声明目标系统、GNOME 版本、会话类型、模块、必需扩展和补丁检查。新增环境时复制一份，改 `target` / `modules` / `extensions` / `patches`，先 `--dry-run` 验证。

`profiles/` 不是通用安装清单；`packages` 字段只作说明，bootstrap 不会安装。

## 手工步骤（bootstrap 不会自动做）

这些步骤依赖上游版本，必须在 bootstrap 前完成：

### 1. 生成 Shell 主题

```bash
python3 style.py --execute
```

它从现有 WhiteSur Shell 主题复制一份，追加 `styles/panel-light.css`，输出到 `~/.themes/WhiteSur-MacOS-<hash>`。profile 里的 `target.shell_theme` 必须和生成目录名一致；如果改了 `styles/panel-light.css`，hash 会变，需要同步改 profile。

### 2. 应用补丁

| 补丁 | 目标 | 作用 |
| --- | --- | --- |
| `patches/gtk4-whitesur-light-candidate.patch` | WhiteSur GTK4 `gtk-Light.css` | 修复 8 处 `color-mix` 语法错误 |
| `patches/spotlight-stage-parking.patch` | Spotlight 扩展 `lib/overview/searchStealer.js` | 关闭时把搜索控件留在 stage，修复生命周期警告 |
| `patches/global-menu-dedupe-app-menu.patch` | global-menu 扩展 `nativeMenu.js`、`extension.js` | 同名应用菜单去重（QQ 只剩一个菜单） |
| `patches/global-menu-no-arrow-specificity.patch` | global-menu 扩展 `stylesheet.css` | 用高特异性选择器隐藏弹出菜单顶部的 white bump |

补丁不自动应用；按补丁头部路径手工 `patch -p1` 或编辑，改完重新启用对应扩展/重载主题。`bootstrap` 会检查补丁是否在位。

### 3. 启用扩展

确保 `REQUIRED_EXTENSIONS` 里的扩展已安装并启用。扩展安装属于上游步骤，本工具不执行。

### 4. 可选：中文菜单

```bash
tools/localize-menus.py chrome nautilus ptyxis --dry-run
tools/localize-menus.py chrome nautilus ptyxis --execute
gnome-extensions disable global-menu@unmade.space
gnome-extensions enable global-menu@unmade.space
```

只改 global-menu 的 curated JSON，不改应用本身；需要恢复时用脚本留下的 `.bak-*`。

## 备份、恢复与回滚

bootstrap 执行前会自动创建配置备份：

```text
~/.local/state/gnome50-macos-kit/backups/<UTC>-<id>/
```

验证失败会自动恢复该备份。手工回滚：

```bash
python3 desktop.py restore --from <BACKUP> \
  --module appearance --module font --module buttons \
  --module panel-blur --module status-area --module macos-dock \
  --module shell-theme --execute
```

也可以按模块备份/恢复：

```bash
python3 desktop.py backup --module all --dry-run
python3 desktop.py backup --module all --execute
```

配置备份只覆盖 dconf 值和已纳入模块的文件，**不包含系统包、源码补丁或完整系统快照**；需要系统级回滚时用 Timeshift/Snapper/云厂商快照。

## 只读检查与验证

```bash
python3 desktop.py                 # 当前状态、扩展、冲突提示（JSON）
python3 desktop.py doctor          # 前置检查
python3 desktop.py verify          # 验收，失败返回 1
python3 tests/test_desktop.py      # 23 项隔离测试
python3 tests/test_style.py        # 主题生成工具测试
node tests/test_menu_dedupe.cjs    # 菜单去重测试
node tests/test_native_menu_dedupe.cjs
node tests/test_spotlight_lifecycle.cjs
```

`verify` 检查会话总线、GNOME 50、配置目标、必需扩展、生成主题、Spotlight 补丁、菜单去重补丁，以及 Ptyxis / VS Code 启动项是否仍导出 `GTK_THEME`。

## 目录

```text
install.sh                  一键入口（bootstrap 包装）
desktop.py                  状态/doctor/install/apply/verify/backup/restore/bootstrap
style.py, styles/           生成 WhiteSur-MacOS Shell 变体
profiles/                   限定环境的 bootstrap profile
patches/                    手工补丁
data/menu-zh.json           菜单中文标签表
data/spotlight-patch-manifest.json  Spotlight 补丁校验清单
tools/localize-menus.py     菜单本地化
tools/login-report.sh       登录/指纹/钥匙串只读诊断
tools/build-release.sh      构建发布包
sources.py, upstreams.lock.json  固定上游提交与校验
verify-after-login.py       Spotlight 补丁加载检查
tests/                      隔离测试
```

## 边界与已知限制

- 只支持 GNOME Shell 50.x；跨大版本需要重新验证。
- 不安装包/扩展，不自动打源码补丁；补丁和上游安装是手工步骤。
- 不处理登录、指纹、钥匙串、电源、合盖、休眠、GDM、引导、分区和双系统设置；登录问题用 `tools/login-report.sh` 做只读诊断。
- 主题只能统一颜色、圆角、阴影和部分布局，不能把 GTK/AppKit 应用生态变成 macOS；完整 macOS 控制中心需要自定义 Shell 扩展，不在本仓库范围。
- 部分应用菜单仍可能是英文，取决于 curated JSON 覆盖。

## 打包（可选）

仓库本身就是源码，不需要 GitHub Release；直接 `git clone` 或下载源码 ZIP，然后 `./install.sh` 即可。只有离线拷贝或校验时才本地打包：

```bash
tools/build-release.sh
# dist/gnome50-macos-kit-1.5.0.tar.gz + .sha256
```

包从已提交代码构建，不含 `.git`、缓存或私人文件。

## License

见 `LICENSE`。

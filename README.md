# gnome50-macos-kit

Ubuntu 26.04 / GNOME Shell 50.1 的 macOS 风格桌面 bootstrap，面向**已经装好 WhiteSur、Dhruva、Orbit、Spotlight 的已知环境**。

[![checks](https://github.com/dsyfb437/gnome50-macos-kit/actions/workflows/checks.yml/badge.svg)](https://github.com/dsyfb437/gnome50-macos-kit/actions/workflows/checks.yml)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![version](https://img.shields.io/badge/version-1.5.0-informational)

> A scoped, reviewable bootstrap for a macOS-style Ubuntu 26.04 / GNOME Shell 50.1 desktop. It is not a universal one-click macOS installer.

## 演示

![Desktop preview](assets/desktop-preview-v2.webp)

> Text Editor、Files、Terminal；Chrome 不在画面内。

## 特性

- **默认只读**：先 `--dry-run` 展示计划，真正写入必须显式 `--execute`。
- **可回滚**：写入前自动备份 dconf 与配置文件；验收失败自动恢复本次备份。
- **可审查**：配置、主题 CSS、补丁、数据分开放置，不把逻辑塞进一个脚本。
- **零第三方依赖**：核心脚本只用 Python 标准库。

## 快速开始

```bash
git clone https://github.com/dsyfb437/gnome50-macos-kit.git
cd gnome50-macos-kit

./install.sh --dry-run

# 已有系统快照
./install.sh --execute --snapshot-ok

# 没有 Timeshift/Snapper，明确接受只做用户级配置备份
./install.sh --execute --no-snapshot
```

报告写入：

```text
~/.local/state/gnome50-macos-kit/bootstrap-reports/<UTC>-<id>.json
```

报告包含 preflight、plan、备份路径、验收结果、是否已回滚，以及完整 rollback 命令。`--snapshot-ok` 只是声明系统快照已存在，工具无法验证；`--no-snapshot` 表示接受没有系统级回滚。

## 前置条件

- Ubuntu 26.04.x、GNOME Shell 50.x、Wayland；
- WhiteSur GTK3 / GTK4 / Shell 主题、WhiteSur 图标和光标、Inter 字体；
- 扩展：User Themes、Blur My Shell、Dhruva、Orbit Global Menu、Just Perfection、Ubuntu AppIndicators、Spotlight；
- 已生成 `WhiteSur-MacOS-Kit` Shell 主题；
- Python 3.10+、`gsettings`、`dconf`、`gnome-extensions`、`fc-match`；
- 以普通用户运行，不要用 sudo。

缺失项先检查：

```bash
python3 desktop.py doctor
```

`doctor` 只做离线检查，按主题、图标、字体、扩展、schema、生成主题列出缺失项和提示。

## 工作方式

| 阶段 | 行为 |
| --- | --- |
| Preflight | 检查系统、GNOME、会话、工具、`doctor`、配置可写、生成主题、扩展和补丁 |
| Plan | 逐个模块打印当前值与目标差异，不写文件 |
| Apply | 创建配置备份 → 写入 → 逐项读回 |
| Verify | 运行只读验收；失败自动恢复本次配置备份 |
| Report | 写入 `bootstrap-reports/`，附带回滚命令 |

Profile 默认是 `profiles/ubuntu-26.04-gnome-50.json`，声明目标系统、模块、必需扩展和补丁检查。新增环境时复制一份，改完先 `--dry-run`。

## 配置模块

| 模块 | 内容 |
| --- | --- |
| `appearance` | WhiteSur Light GTK/图标/光标、prefer-light |
| `font` | Inter 11 |
| `buttons` | 窗口按钮左置（close/minimize/maximize） |
| `panel-blur` | 顶栏模糊开、概览模糊关 |
| `status-area` | 托盘灰度、全局菜单字号 11、面板指示器间距 6 |
| `macos-dock` | Dhruva 浅色半透明 Dock、关闭实时模糊 |
| `shell-theme` | 选中生成的 `WhiteSur-MacOS-Kit` Shell 主题 |

`apply` 单独应用模块，`install` 按固定顺序应用全部；两者默认 dry-run。

## 手工步骤

这些步骤依赖上游版本，bootstrap 只检查，不自动执行。

### 生成 Shell 主题

```bash
python3 style.py --execute
```

从现有 WhiteSur Shell 主题复制一份，追加 `styles/panel-light.css`，输出到 `~/.themes/WhiteSur-MacOS-Kit`。改 CSS 不需要改 profile。

### 应用补丁

| 补丁 | 目标 | 作用 |
| --- | --- | --- |
| `gtk4-whitesur-light-candidate.patch` | WhiteSur GTK4 `gtk-Light.css` | 修复 8 处 `color-mix` 语法错误 |
| `spotlight-stage-parking.patch` | Spotlight `lib/overview/searchStealer.js` | 修复搜索控件生命周期警告 |
| `global-menu-dedupe-app-menu.patch` | global-menu `nativeMenu.js`、`extension.js` | 同名应用菜单去重 |
| `global-menu-no-arrow-specificity.patch` | global-menu `stylesheet.css` | 隐藏弹出菜单顶部的白色凸起 |

按补丁头部路径手工 `patch -p1` 或编辑，改完重新启用对应扩展/重载主题。

### 启用扩展

确保前置条件里的扩展已安装并启用。扩展安装属于上游步骤，本工具不执行。

### 可选：中文菜单

```bash
tools/localize-menus.py chrome nautilus ptyxis --execute
gnome-extensions disable global-menu@unmade.space
gnome-extensions enable global-menu@unmade.space
```

只改 global-menu 的 curated JSON，不改应用本身；恢复用脚本留下的 `.bak-*`。

## 回滚

bootstrap 的配置备份在：

```text
~/.local/state/gnome50-macos-kit/backups/<UTC>-<id>/
```

手工恢复：

```bash
python3 desktop.py restore --from <BACKUP> \
  --module appearance --module font --module buttons \
  --module panel-blur --module status-area --module macos-dock \
  --module shell-theme --execute
```

配置备份只覆盖 dconf 值和已纳入模块的文件，不包含系统包、源码补丁或整机快照。系统级回滚请用 Timeshift/Snapper/云厂商快照。

## 检查与测试

```bash
python3 desktop.py                 # 当前状态、扩展、冲突提示（JSON）
python3 desktop.py doctor          # 前置检查
python3 desktop.py verify          # 只读验收，失败返回 1
python3 tests/test_desktop.py      # 24 项隔离测试
python3 tests/test_style.py        # 6 项主题生成工具测试
tests/run-extension-tests.sh       # 可选：对已安装扩展源码跑集成测试
```

CI 运行 Python 语法、主题测试和扩展集成测试；扩展源码不存在时自动跳过。24 项桌面测试需要本地 GNOME 会话，不在 CI 中伪装运行。

## 目录

| 路径 | 用途 |
| --- | --- |
| `install.sh` | 一键入口，包装 `desktop.py bootstrap` |
| `desktop.py` | 状态、doctor、apply/install、backup/restore、bootstrap、verify |
| `style.py`、`styles/` | 生成 `WhiteSur-MacOS-Kit`；`styles/panel-light.css` 是主题覆盖源 |
| `profiles/` | 限定环境的 bootstrap profile |
| `patches/` | 需要手工应用的源码补丁 |
| `data/` | 中文菜单表、Spotlight 补丁校验清单 |
| `tools/` | 菜单本地化、登录诊断、本地打包（可选） |
| `tests/` | 隔离测试与 profile 契约检查 |

## 范围与限制

- 仅支持 GNOME Shell 50.x；跨大版本需要重新验证。
- 不安装包或扩展，不自动打源码补丁。
- 不处理登录、指纹、钥匙串、电源、GDM、引导、分区和双系统设置。
- 主题只能统一颜色、圆角、阴影和部分布局，不能把 GTK/AppKit 应用生态变成 macOS；完整 macOS 控制中心不在范围内。

仓库源码即发布，不依赖 GitHub Release。需要离线包时：

```bash
tools/build-release.sh
```

## License

MIT，见 [LICENSE](LICENSE)。

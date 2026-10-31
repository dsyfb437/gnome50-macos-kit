# Ubuntu / GNOME macOS 风格桌面整合

面向已有 WhiteSur、Dhruva 和 Orbit 配置的 Ubuntu 26.04.1 / GNOME Shell 50.1 桌面。提供状态检查、可选设置、干运行、备份和恢复；默认运行只读。

这是当前桌面的整合与修复记录，不是空白机器的一键安装器。**仓库中的脚本不会自动重做已经应用的源码补丁、安装菜单组件或创建 Rime 组。**

新增：[外观优化与回滚](docs/外观优化.md)。顶栏文字和系统图标已截图验收；Dock 已改为浅色半透明（实时模糊实测占 15%+ 单核，已关闭）；托盘图标已转灰度并与面板字号对齐；QQ 同名菜单去重已在重启后的会话中截图验证。

## 当前方案

| 部分 | 保留的配置 |
|---|---|
| 外观 | WhiteSur Light GTK3 / GTK4、独立 WhiteSur-MacOS Shell 变体、WhiteSur 图标和光标、Inter 11 |
| Dock 与缩放 | Dhruva，自定义 GenieEffect.js 保留；浅色半透明 Dock（`macos-dock` 模块，无实时模糊）；显示缩放 166% |
| 顶栏与菜单 | Just Perfection、Blur My Shell（顶栏模糊开、概览模糊关）、Orbit 全局菜单；托盘图标灰度、菜单字号 11 |
| 搜索 | Spotlight 保持开启，已应用生命周期补丁 |
| 输入与辅助 | Fcitx5、Kimpanel、Clipboard Indicator、Sushi、WACK Sonoma；新增 Rime（雾凇）可选组，当前输入法未替换 |
| 窗口标题 | Window Title Pro 已安装但在核验时未启用，未发现与 Orbit 同时显示的重复标题 |

主要桌面测试于 **2026-10-28** 完成；2026-10-29 补齐浅色偏好并修正检查工具，见验证结果。后续本机改动需重新运行状态检查。

## 已完成与待验证

| 项目 | 已完成 | 尚待验证 |
|---|---|---|
| GTK4 | 修复 8 处样式语法错误；当前文件解析错误为 0 | 各应用浅深色、标题栏、弹窗与 libadwaita 视觉一致性 |
| Orbit | 补齐用户级 daemon 与按应用启用的传统 GTK3 菜单模块；两类真实应用菜单动作回传通过；同名应用菜单去重已在重启会话中验证（QQ 只剩一个菜单） | 日常应用覆盖、实际顶栏点击、Snap / Flatpak 等场景 |
| Spotlight | 补丁在新会话加载且保持开启；5 轮概览切换 10/10 成功，相关警告 0 条 | 搜索输入、选择结果、Esc / 点击外部关闭、长期流畅性 |
| Dhruva | 原有自定义补丁哈希一致，未被覆盖 | 166% 下动画落点、手势、多屏和帧率 |
| Rime | 新增可选组，保留原组、词库和当前拼音 | 中文输入及候选窗交互 |
| 状态区与应用 | 托盘图标去饱和、菜单字号对齐；修掉 Ptyxis 传递 `GTK_THEME` 导致终端启动的应用变暗 | 个别品牌色图标、部分菜单仍为英文 |
| 性能 | 关闭 Dock 实时模糊后，静止画面下 gnome-shell 从 17–20% 降到 2.4–3.0% 单核 | 交互/动画帧率、长时间使用仍需实测 |
| 工具与上游 | 17 项隔离集成测试、5 项主题工具测试、9 项菜单去重测试通过；六个上游已审阅并锁定提交 | 不把 metadata 的 GNOME 50 声明等同于视觉兼容 |

完整结论与证据见 [验证结果](docs/验证结果.md)。

## 安装、验证与发布

当前版本 **1.1.0**。`doctor` 做离线前置检查（主题、图标、字体、扩展、schema、生成的主题），`install` 按固定顺序应用视觉配置模块，写入前自动备份；默认只显示差异，不会改桌面。

```bash
python3 desktop.py doctor                # 新机器先确认依赖齐全（缺失项带提示）
python3 desktop.py install --dry-run     # 查看差异，不写入
python3 desktop.py install --execute     # 备份后应用视觉配置
python3 desktop.py verify                # 只读验收，失败时返回 1
python3 desktop.py --version
```

`doctor` 只做离线检查并列出缺失项及提示；`verify` 则在运行中的会话里检查配置目标、扩展、Shell 主题、Spotlight 补丁、菜单去重补丁，以及 Ptyxis / VS Code 启动项是否仍导出 `GTK_THEME`，输出 JSON。

发布包从已提交的代码构建，不包含 `.git`、缓存或私人文件：

```bash
tools/build-release.sh
# dist/gnome50-macos-kit-1.1.0.tar.gz 和 .sha256
```

## 从这里开始

在项目根目录运行，依赖 Python 3.10+ 和 GNOME 用户会话：

```bash
# 只读检查当前配置、扩展与冲突提示
python3 desktop.py

# 预览备份，不写入文件
python3 desktop.py backup --module all --dry-run

# 预览单个设置模块，不修改桌面
python3 desktop.py apply --module panel-blur --dry-run
```

实际写入须显式选择模块并加 `--execute`。恢复会替换选中模块的内容，并先建立恢复前备份；执行前请阅读 [使用与恢复](docs/使用与恢复.md)。

## 按需要阅读

| 你要做什么 | 文档 |
|---|---|
| 查看已经做了什么、哪些尚未验证 | [验证结果](docs/验证结果.md) |
| 查参数、模块、备份、恢复及固定源码获取 | [使用与恢复](docs/使用与恢复.md) |
| 实际检查动画、主题、输入和菜单 | [本机验收](docs/本机验收.md) |
| 查看六个 GitHub 项目兼容性、安装行为与冲突 | [仓库审计](docs/仓库审计.md) |
| 追溯诊断、修复与复验过程 | [历史记录](docs/history/README.md) |

## 目录与范围

- `style.py`、`styles/`：从现有主题生成独立顶栏变体，默认干运行。
- `desktop.py`：状态检查、可选设置、备份和恢复。
- `sources.py`、`upstreams.lock.json`：固定提交的源码获取及校验，不执行上游安装器。
- `verify-after-login.py`：检查 Spotlight 补丁加载条件；`--exercise` 执行概览开关测试。
- `patches/`：已应用修复的补丁，供审阅；不自动打补丁。
- `tests/`、`evidence/`：隔离测试与脱敏验证记录。
- `docs/history/`：按阶段归档的过程材料，旧状态不作为当前配置指令。

不增加第二套 Dock、全局菜单或动画扩展，不执行上游一键脚本。电源、合盖、休眠、充电阈值、GDM、引导器、分区和双系统设置均不在操作范围。私人备份、词库及完整桌面快照不纳入仓库。

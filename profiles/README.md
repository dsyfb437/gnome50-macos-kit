# Bootstrap profiles

这里每个 JSON 描述一个**已验证的已知环境**，供 `python3 desktop.py bootstrap` 使用。

- 不是“任意机器”的安装清单；换系统、GNOME 大版本、扩展版本或硬件前，先重新验证。
- `modules` 必须是 `desktop.py` 里 `INSTALL_MODULES` 的子集。
- `extensions` 只做“已安装且已启用”检查，不安装扩展。
- `patches` 只做检查，不自动打补丁；按 `patches/` 和文档手工应用。
- `packages` 仅供说明，bootstrap 不执行包安装。

| Profile | 目标 |
| --- | --- |
| `ubuntu-26.04-gnome-50.json` | Ubuntu 26.04.1 + GNOME Shell 50.1 + Wayland |

新增 profile 时复制现有文件，改 `name`、`target`、`modules`、`extensions`、`patches`，然后用 `--dry-run` 在本机验证。

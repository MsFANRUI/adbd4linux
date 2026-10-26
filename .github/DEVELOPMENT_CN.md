# 开发文档

[用户说明](../README_CN.md) · [English](DEVELOPMENT.md)

本文档面向构建、打包、测试和修改 Linux `adbd` 移植的开发者。日常安装和使用
请先看[用户说明](../README_CN.md)。

## 目录结构

| 路径 | 作用 |
| --- | --- |
| `thirdparty/adb/` | 官方 AOSP `platform/packages/modules/adb` |
| `thirdparty/` | 官方 AOSP core、libbase、logging、fmt 依赖 |
| `cmake/` | 独立 CMake 目标和 `cmake/linux-port.patch` |
| `debian/` | Debian 打包元数据和 debhelper 规则 |
| `etc/` | gadget 默认配置、systemd 服务、modules-load 和 profile 片段 |
| `usr/bin/` | 安装的 helper：`usbdevice`、`app_process`、兼容层入口 |
| `usr/lib/` | scrcpy-compat 和 android-compat 的运行期 Python/资源 |
| `.github/` | issue/PR 模板、CI workflow 和开发文档 |

## 固定上游版本

上游代码全部通过 Git submodule 固定。构建不会自动更新这些版本。

| 子模块 | 提交 |
| --- | --- |
| adb | `1cf2f017d312f73b3dc53bda85ef2610e35a80e9` |
| core | `a3b721a32242006b59cb12bd62c9133632af3a2d` |
| libbase | `6d19b5c690fa4220c10e42c2326150bbd4d4b7bb` |
| logging | `bcac7c30d88a3773a7c0bc9f5617a23a886331fd` |
| fmtlib | `97ceae9d27415d6444f3e24f491da8ed6902ecfa` |

ADB 快照日期为 2025-03-25。支持库独立固定，不描述为某个完整 Android
发布清单。

Linux 移植还参考并保留了 `nmeum/android-tools` 和
`happyme531/standalone-linux-adbd` 的适配成果；构建不依赖这两个仓库。
署名和许可证见 `debian/copyright`。

## 构建与打包

### Debian/Ubuntu 包

```bash
git clone --recurse-submodules <repository-url>
cd adbd
git submodule update --init --recursive
sudo apt-get install build-essential debhelper cmake pkg-config patch \
    libbrotli-dev liblz4-dev libzstd-dev ffmpeg python3
dpkg-buildpackage -us -uc -b -j4
```

产物位于上级目录：`adbd_<版本>_<架构>.deb`。发行版的 libc、C++ 和压缩库
采用动态链接，由 Debian 自动生成运行依赖；AOSP 支持库和 fmt 编入可执行文件。

### 本地安装

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build --parallel 4
sudo cmake --install build --prefix /usr/local
```

打包使用 `dpkg-buildpackage`；本地安装使用 `cmake --install`。

### 补丁和子模块规则

CMake 将上游源码复制到 `<build>/source`，在那里以零 fuzz 应用单个补丁。
重新配置、清理和重编译都不会修改子模块。打包构建时不要直接改上游子模块。

更新上游：

```bash
git -C thirdparty/adb fetch origin master
git -C thirdparty/adb checkout --detach origin/master
```

更新时审查上游变动，调整 `cmake/linux-port.patch`，同步版本记录和
changelog，再重新构建。只改分支设置不会改变已记录的子模块提交。

## 运行期内部

### USB gadget 管理器

`usr/bin/usbdevice` 是通用 FunctionFS gadget 管理器，不属于 AOSP 上游；
它只负责准备 adbd 需要的 configfs/FunctionFS，并启动 `/usr/bin/adbd`。

| 源文件 | 安装位置 |
| --- | --- |
| `usr/bin/usbdevice` | `/usr/bin/usbdevice`（0755） |
| `usr/bin/usbnetwork` | `/usr/bin/usbnetwork`（0755） |
| `usr/bin/adbd-smb` | `/usr/bin/adbd-smb`（0755） |
| `etc/systemd/system/usbdevice.service` | `/usr/lib/systemd/system/usbdevice.service` |
| `etc/systemd/system/usbnetwork.service` | `/usr/lib/systemd/system/usbnetwork.service` |
| `etc/default/adbd-gadget` | `/etc/default/adbd-gadget` |
| `etc/default/adbd-smb` | `/etc/default/adbd-smb` |
| `etc/modules-load.d/usb-gadget.conf` | `/etc/modules-load.d/usb-gadget.conf` |
| `etc/profile.d/usbdevice.sh` | `/etc/profile.d/usbdevice.sh` |

`debian/adbd.links` 安装启用链接：

```text
/etc/systemd/system/sysinit.target.wants/usbdevice.service
  -> /usr/lib/systemd/system/usbdevice.service
/etc/systemd/system/multi-user.target.wants/usbnetwork.service
  -> /usr/lib/systemd/system/usbnetwork.service
```

行为：

- `Type=oneshot`、`RemainAfterExit=yes`，在 `sysinit.target` 启动。
- `ExecStart=/usr/bin/usbdevice start` 创建 configfs gadget、挂载
  `/dev/usb-ffs/adb`、启动 `/usr/bin/adbd`，等待 FunctionFS 描述符就绪后
  绑定第一个可用 UDC。
- `ExecStop=/usr/bin/usbdevice stop` 解绑 UDC、停止 adbd、清理 configfs，
  并卸载 FunctionFS。
- 没有 UDC（例如 USB 口处于 host 模式）时是无害的 no-op。
- `usbnetwork` 在 `ADBD_GADGET_NET=ncm` 之前都是 no-op；启用后配置
  `usb0` 地址、用 dnsmasq 发 DHCP，并给默认上行安装 nftables NAT 规则。
- `adbd-smb` 是显式 opt-in：只有管理员执行 `adbd-smb enable` 时才会修改
  `/etc/samba/smb.conf`、创建 SMB 密码并启动 `smbd`。
- USB 控制器、DTS、板级模式和板级 gadget 策略仍由 BSP 负责。

身份细节：

- USB 字符串和序列号可通过 `/etc/default/adbd-gadget` 覆盖。
- 厂商和序列号优先从设备树读取；同时支持
  `/proc/device-tree` 和 `/sys/firmware/devicetree/base`。
- 没有设备树序列号时使用 `/etc/machine-id`，再没有则使用稳定占位值。
- FunctionFS 挂载属主可通过 `ADBD_GADGET_FFS_UID` /
  `ADBD_GADGET_FFS_GID` 配置；默认是运行 `usbdevice` 的用户。
- `ADBD_SHELL` 由 `usbdevice` 选择：有 `bash` 就用 `bash`，否则用 `/bin/sh`。

### adbd 运行环境

支持 FunctionFS USB、显式 TCP/VSOCK、shell protocol v2、文件同步（含上游压缩
路径）、TCP 转发和反向传输。

不提供：Android framework 认证、TLS 配对、JDWP、mDNS、APK 服务和 Android
属性驱动的生命周期。进程使用启动者的 UID，属于无认证开发接口。

| 变量 | 含义 |
| --- | --- |
| `ADBD_LISTEN` | 显式监听地址，可逗号分隔，例如 `tcp:127.0.0.1:5555`、`vsock:5555` |
| `ADBD_PORT` | 未设置 `ADBD_LISTEN` 时的回环 TCP 端口 |
| `ADB_TCP_PORT` | `ADBD_PORT` 的旧版兼容变量 |
| `ADBD_SHELL` | shell 路径；优先 `bash`，没有时用 `/bin/sh` |
| `ADBD_USB=0` | 禁用 USB 探测，供隔离测试使用 |

默认不开网络端口。`local:` 按 Linux abstract socket 解释，保持 Android 风格
本地转发语义；`localfilesystem:` 保持文件系统语义。

### scrcpy 兼容层

兼容层提供 scrcpy 5.x 的 Linux 入口，使 Windows/Linux 主机上的原生 scrcpy
可以通过 adb 连接，而不需要 Android framework、SurfaceFlinger 或 MediaCodec。

- 源码：`usr/bin/app_process`、`usr/lib/scrcpy-compat/fake_server.py`。
- 入口通过 `PYTHON` 或 `PATH` 解析 `python3`。
- 包安装入口：`/usr/bin/app_process`。
- 包安装服务端：`/usr/lib/<multiarch>/scrcpy-compat/fake_server.py`。
- 本地安装入口：`/usr/local/bin/app_process`，服务端在
  `/usr/local/lib/scrcpy-compat/`。
- `app_process` 会搜索 `/usr/local/lib`、`/usr/lib/<multiarch>/scrcpy-compat`
  和相对 `lib` 目录，因此包安装和本地安装可以共存。

协议：

`tunnel_forward=true` 时，服务端建立 abstract Unix socket，并按顺序接受：

1. video
2. audio（启用时）
3. control（启用时）

forward 模式下客户端先读 1 字节 dummy byte，再读 64 字节设备名。
`scid` 的正式格式是 `scrcpy_%08x`。

video socket 的字节顺序：

1. 64 字节设备名
2. 4 字节大端 codec id：H.264 为 `0x68323634`
3. 12 字节 session：大端 `flags=0x80000000`、`width`、`height`
4. 循环发送 12 字节 frame header 和对应 H.264 access unit

frame header 是大端：

```text
uint64 pts_and_flags
uint32 packet_size
```

标志位：`1 << 63` session、`1 << 62` codec config、`1 << 61` 关键帧。

当前实现用 ffmpeg `x11grab` 输出 H.264，按 AUD（NAL type 9）切分 access unit，
约 30 FPS。采集关闭光标绘制（`draw_mouse=0`），光标由主机本地显示。

已处理的 `ControlMessageReader` 消息：

- type `0`：keycode，`action + keycode + repeat + metaState`
- type `1`：text，4 字节长度 + UTF-8 文本
- type `2`：touch，`action + pointerId + x/y + pressure + buttons`
- type `3`：scroll
- type `4`：back/screen-on
- type `8/9/10/18/21`：clipboard/power/torch/resize 等，按对应长度安全消费

X11 后端通过 `libX11`、`libXtst` 把输入映射到 `DISPLAY`；没有 X11 时退回
`/dev/uinput`。文本注入支持 ASCII/Latin-1 和 Shift 组合，非 ASCII 字符会跳过。

已知边界：

- 只提供屏幕、触控、键盘和滚轮路径；音频关闭。
- 没有 Android 剪贴板、通知、摄像头、UHID 等能力。
- 视频需要 `Xvfb` 和 `ffmpeg`。
- type `4` 映射为 Escape，是桌面近似语义。
- 高分屏和大量小文件受 ffmpeg/x264 和 USB 链路限制。

### Android 命令兼容层

`usr/bin/android-compat-wrapper` 以各命令名安装（`screencap`、`screenrecord`、
`input`、`getprop`、`setprop`、`wm`、`logcat`、`dumpsys`、`settings`）。
入口在 `/usr/local/lib`、`/usr/lib/android-compat` 和
`/usr/lib/*/android-compat` 中查找对应 Python 模块。Python 通过 `PYTHON`
或 `PATH` 解析。

实现说明：

- `props.py` 从设备树、DMI 和 sysfs 推导 Android 属性。
  Android release/SDK 默认 15/35，可用 `ANDROID_COMPAT_RELEASE` /
  `ANDROID_COMPAT_SDK` 覆盖。
- `settings`/`getprop` 优先写 `/run`，不可写时退回用户主目录。
- `screencap` 使用 ffmpeg `x11grab`；`screenrecord` 使用 x264。
- `input text` 只支持 ASCII/Latin-1，非 ASCII 文本会跳过。
- `wm` 不能修改 Xvfb 尺寸，写操作返回失败。
- `logcat -c` 不会清空 journald，只提示后退出。
- 二进制输出（如 PNG 截图）建议通过 `adb exec-out` 使用。

## 检查

Shell 语法：

```bash
sh -n usr/bin/usbdevice usr/bin/app_process usr/bin/android-compat-wrapper
sh -n etc/profile.d/usbdevice.sh
```

Python 语法：

```bash
python3 -m py_compile usr/lib/android-compat/*.py \
    usr/lib/scrcpy-compat/*.py
```

目标侧 gadget 检查：

```bash
systemctl is-enabled usbdevice
systemctl is-active usbdevice
/usr/bin/usbdevice status
cat /sys/kernel/config/usb_gadget/adbd/UDC
```

## CI 与发布

CI 使用 `ubuntu-24.04` 构建 amd64，使用 self-hosted ARM64 `24.04` runner
构建 arm64。每次构建上传 `.deb` 产物；推送 `v*` tag 时发布 Release。
tag 与 Debian revision 之前的版本比较，例如包版本 `1.0.3-1` 对应 `v1.0.3`。

## 可移植性说明

- gadget 管理器绑定第一个 UDC，不绑定具体 SoC。
- USB 身份优先取设备树/DMI，其次 `/etc/machine-id`。
- adb shell 优先 `bash`，但没有 bash 时会退回 `/bin/sh`。
- `python3` 通过 `PYTHON` 或 `PATH` 解析，不写死单个绝对路径。
- FunctionFS 属主可配置，不再固定为某个 Android UID/GID。
- 可选 scrcpy 和 Android 命令层面向 Linux/X11；核心 `adbd` 不依赖它们。
- systemd、configfs 和 FunctionFS 仍是平台前提。

## 验证状态

- 目标支持 amd64 和 arm64 包构建。
- scrcpy 兼容层已在 Linux/X11 目标上使用 scrcpy 5.x 验证。
- 构建后上游子模块保持未修改。
- 完整 Windows adb/scrcpy 会话、USB 吞吐、VSOCK、反向转发、压缩协商和
  厂商特定本地 socket 路径不在当前检查范围内。
- Android framework 认证和 TLS 配对有意不实现。

## 安全

`adbd` 无认证。只放在可信 USB、回环地址或私有网络中。gadget 管理器需要 root
才能写 configfs 和挂载 FunctionFS。不要把 `tcp:5555` 暴露到不可信网络。

## 许可证

Linux 移植、打包和配套工具使用 GPL-3.0。上游 AOSP 组件、fmt 和适配补丁
保留各自原许可证。详见 `debian/copyright` 和 `LICENSE`。

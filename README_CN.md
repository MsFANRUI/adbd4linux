# RoboParty adbd

基于官方 AOSP `master` 的设备端 `adbd` Linux 移植，按照
`Roboparty/libsoem` 的方式维护：上游源码子模块、单个 `linux-port.patch`、
CMake 和标准 `debian/` 打包。产物是 `/usr/bin/adbd`，不是主机端 `adb`。
编译不需要内核源码，也不需要完整 Android 构建环境。

## 源码与补丁

- `adb/`：官方 AOSP `platform/packages/modules/adb`，跟踪 `master`。
- `deps/`：来自官方 AOSP 的 core、libbase、logging、fmt 依赖。
- `linux-port.patch`：集中维护 Linux/glibc/GCC、USB 和守护进程适配。
- `cmake/`、`debian/`：构建与 Debian 打包。
- `tests/smoke.py`：隔离的本机协议测试。

ADB 固定在 `1cf2f017d312f73b3dc53bda85ef2610e35a80e9`，提交日期为
2025-03-25。2026-10-21 核对时官方 `master`、`main` 都指向它；这是指定分支
的快照，不代表最新 Android 发布版。依赖的准确版本见 `git submodule status`。

移植参考并保留了 `nmeum/android-tools`、`happyme531/standalone-linux-adbd`
的适配成果和署名，见 `NOTICE`；构建不依赖这两个移植仓库。
CMake 将上游源码复制到构建目录的 `source/` 后应用一次补丁，禁止模糊匹配，
重复配置、清理和重编译都不会修改子模块。

## 构建

```sh
git clone --recurse-submodules https://github.com/Roboparty/adbd.git
cd adbd
git submodule update --init --recursive
sudo apt-get install build-essential debhelper cmake pkg-config patch \
    libbrotli-dev liblz4-dev libzstd-dev python3
dpkg-buildpackage -us -uc -b -j4
```

产物位于上级目录：`adbd_<版本>_<架构>.deb`。发行版的 libc、C++ 和压缩库
采用动态链接，由 Debian 自动生成运行依赖；AOSP 支持库和 fmt 编入可执行文件。

直接编译和测试：

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build --parallel 4
python3 tests/smoke.py build/adbd
```

## 运行边界

保留 FunctionFS USB、显式 TCP/VSOCK 监听、shell v2、文件同步、上游压缩路径、
TCP 转发和反向传输。不包含 Android 框架认证、TLS 配对、JDWP、mDNS、APK
服务和 Android 属性驱动的生命周期。进程使用启动者的 UID，属于无认证开发接口。

USB 使用 `/dev/usb-ffs/adb/ep0`、`ep1`、`ep2`。FunctionFS 挂载、gadget 和 UDC
配置继续由 BSP 管理。本包只安装程序和文档，不安装自动启动服务，也不修改 USB。
BSP 准备好 FunctionFS 后即可启动 `/usr/bin/adbd`。

注意：旧 BSP 把启动脚本、service 和模块加载配置放在同名 `adbd` 包中，
并不是由独立的 BSP 包提供。直接用当前纯守护进程包替换旧包，不能保留完整的
启动集成。部署前必须迁移这些文件的包归属，当前还不能作为旧包的直接替代品。

| 环境变量 | 含义 |
| --- | --- |
| `ADBD_LISTEN` | 显式监听地址，可逗号分隔，例如 `tcp:127.0.0.1:5555`、`vsock:5555` |
| `ADBD_PORT` | 仅监听回环地址的 TCP 端口，优先级低于 `ADBD_LISTEN` |
| `ADB_TCP_PORT` | 兼容旧启动脚本的端口变量，优先级低于 `ADBD_PORT` |
| `ADBD_SHELL` | shell 路径，默认 `/bin/sh` |
| `ADBD_USB=0` | 禁用 USB 探测，供隔离测试使用 |

默认不开网络端口；既无 USB 也未配置网络时直接报错退出。`tcp:5555` 监听所有网卡。
若显式监听外部网络，
连接者将能无认证访问 shell。`local:` 按 Linux abstract socket 解释以兼容 RKNN；
`localfilesystem:` 保持文件系统 socket 语义。

隔离测试验证无隐式监听、ADB 握手、shell 标准输出/错误/退出码、256 KiB 二进制
文件往返和 TCP 转发，不启动主机 adb server，也不接触 USB。实物 FunctionFS
枚举、VSOCK、反向转发和压缩传输需要另做集成验证。

## 更新与 CI

```sh
git -C adb fetch origin master
git -C adb checkout --detach origin/master
```

更新时审查上游变动，调整 `linux-port.patch`，同步版本记录、changelog，再构建测试。
子模块依赖也需显式更新；普通构建不会自动追踪远端分支最新提交。

CI 与 libsoem 一致：amd64 使用 `ubuntu-22.04`，arm64 使用
`[self-hosted, rk3588]`。每次构建测试解包后的程序并上传产物，两个架构都通过后
才发布 Release。标签必须匹配完整 Debian 版本，例如
`v1.0.41+git20250325.1cf2f017-2`。

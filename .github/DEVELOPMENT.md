# Development guide

[User guide](../README.md) · [中文开发文档](DEVELOPMENT_CN.md)

This guide is for people building, packaging, testing, or modifying the Linux
`adbd` port. For installation and day-to-day usage, start with the
[user guide](../README.md).

## Project layout

| Path | Purpose |
| --- | --- |
| `thirdparty/adb/` | Official AOSP `platform/packages/modules/adb` |
| `thirdparty/` | Official AOSP core, libbase, logging, and fmt dependencies |
| `cmake/` | Standalone CMake targets and `cmake/linux-port.patch` |
| `debian/` | Debian packaging metadata and debhelper rules |
| `etc/` | Gadget defaults, systemd unit, modules-load and profile snippets |
| `usr/bin/` | Installed helpers: `usbdevice`, `app_process`, compat wrapper |
| `usr/lib/` | Runtime Python and assets for scrcpy-compat and android-compat |
| `.github/` | Issue/PR templates, CI workflows, and development documentation |

## Pinned upstream sources

All upstream code is pinned by Git submodule. Builds never update these pins
automatically.

| Submodule | Commit |
| --- | --- |
| adb | `1cf2f017d312f73b3dc53bda85ef2610e35a80e9` |
| core | `a3b721a32242006b59cb12bd62c9133632af3a2d` |
| libbase | `6d19b5c690fa4220c10e42c2326150bbd4d4b7bb` |
| logging | `bcac7c30d88a3773a7c0bc9f5617a23a886331fd` |
| fmtlib | `97ceae9d27415d6444f3e24f491da8ed6902ecfa` |

The ADB snapshot is dated 2025-03-25. The support repositories are pinned
independently; they are not described as a single Android release manifest.

The Linux port also incorporates attributed work from `nmeum/android-tools`
and `happyme531/standalone-linux-adbd`. Neither repository is a build
dependency. See `debian/copyright` for attribution and licenses.

## Build and package

### Debian/Ubuntu package

```bash
git clone --recurse-submodules <repository-url>
cd adbd
git submodule update --init --recursive
sudo apt-get install build-essential debhelper cmake pkg-config patch \
    libbrotli-dev liblz4-dev libzstd-dev ffmpeg python3
dpkg-buildpackage -us -uc -b -j4
```

Artifacts appear in the parent directory as `adbd_<version>_<arch>.deb`.
The binary dynamically links the distribution's libc, C++ and compression
libraries; Debian records those dependencies automatically. AOSP support
libraries and fmt are linked into the executable.

### Local install

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build --parallel 4
sudo cmake --install build --prefix /usr/local
```

Use `dpkg-buildpackage` for a package, or `cmake --install` for a local install.

### Patch and submodule rules

CMake copies the sources into `<build>/source` and applies the single patch
there with zero fuzz. Reconfiguration and clean/rebuild leave submodules
intact. Do not patch the upstream submodules during a package build.

To update upstream:

```bash
git -C thirdparty/adb fetch origin master
git -C thirdparty/adb checkout --detach origin/master
```

Review upstream changes, rebase `cmake/linux-port.patch`, update the recorded
revision and Debian changelog, then rebuild. A branch setting alone does not
change the recorded submodule commit.

## Runtime internals

### USB gadget manager

`usr/bin/usbdevice` is a generic FunctionFS gadget manager. It is not part of
upstream AOSP; it prepares configfs/FunctionFS for adbd and starts
`/usr/bin/adbd`.

| Source | Installed path |
| --- | --- |
| `usr/bin/usbdevice` | `/usr/bin/usbdevice` (0755) |
| `usr/bin/usbnetwork` | `/usr/bin/usbnetwork` (0755) |
| `usr/bin/adbd-smb` | `/usr/bin/adbd-smb` (0755) |
| `etc/systemd/system/usbdevice.service` | `/usr/lib/systemd/system/usbdevice.service` |
| `etc/systemd/system/usbnetwork.service` | `/usr/lib/systemd/system/usbnetwork.service` |
| `etc/default/adbd-gadget` | `/etc/default/adbd-gadget` |
| `etc/default/adbd-smb` | `/etc/default/adbd-smb` |
| `etc/modules-load.d/usb-gadget.conf` | `/etc/modules-load.d/usb-gadget.conf` |
| `etc/profile.d/usbdevice.sh` | `/etc/profile.d/usbdevice.sh` |

`debian/adbd.links` installs the enable links:

```text
/etc/systemd/system/sysinit.target.wants/usbdevice.service
  -> /usr/lib/systemd/system/usbdevice.service
/etc/systemd/system/multi-user.target.wants/usbnetwork.service
  -> /usr/lib/systemd/system/usbnetwork.service
```

Behavior:

- `Type=oneshot`, `RemainAfterExit=yes`, started at `sysinit.target`.
- `ExecStart=/usr/bin/usbdevice start` creates the configfs gadget, mounts
  `/dev/usb-ffs/adb`, starts `/usr/bin/adbd`, waits for the FunctionFS
  descriptors and binds the first available UDC.
- `ExecStop=/usr/bin/usbdevice stop` unbinds the UDC, stops adbd, cleans
  configfs and unmounts FunctionFS.
- With no UDC (for example a host-mode USB port) it is a harmless no-op.
- `usbnetwork` is a no-op unless `ADBD_GADGET_NET=ncm`; when enabled it
  assigns the `usb0` address, serves DHCP with dnsmasq and installs nftables
  NAT rules for the default uplink.
- `adbd-smb` is an explicit opt-in helper: it modifies `/etc/samba/smb.conf`,
  creates the SMB account password and starts `smbd` only when the admin runs
  `adbd-smb enable`.
- The USB controller, DTS, board mode and board-specific gadget policy remain
  BSP responsibilities.

Identity details:

- USB strings and serial number can be overridden through
  `/etc/default/adbd-gadget`.
- The manufacturer and serial number are read from the device tree when
  available, with `/sys/firmware/devicetree/base` as a fallback to
  `/proc/device-tree`.
- If no device-tree serial exists, `/etc/machine-id` is used; otherwise a
  stable placeholder is written.
- FunctionFS mount ownership is configurable with
  `ADBD_GADGET_FFS_UID` / `ADBD_GADGET_FFS_GID`; the default is the user
  running `usbdevice`.
- `ADBD_SHELL` is selected by `usbdevice`: `bash` when available, otherwise
  `/bin/sh`.

### adbd runtime

Supported: FunctionFS USB, explicit TCP/VSOCK listeners, shell protocol v2,
file sync (including upstream compression paths), TCP forwarding and reverse
transport.

Not provided: Android framework authentication, TLS pairing, JDWP, mDNS, APK
services, and Android property-driven lifecycle. The daemon runs with the UID
of its launcher and is an unauthenticated development endpoint.

| Variable | Meaning |
| --- | --- |
| `ADBD_LISTEN` | Explicit comma-separated socket specs, e.g. `tcp:127.0.0.1:5555` or `vsock:5555` |
| `ADBD_PORT` | Loopback TCP port; used only when `ADBD_LISTEN` is unset |
| `ADB_TCP_PORT` | Legacy fallback for `ADBD_PORT` |
| `ADBD_SHELL` | Shell executable; defaults to `bash` when available, otherwise `/bin/sh` |
| `ADBD_USB=0` | Disable USB discovery, useful for isolated tests |

No network listener is opened by default. `local:` forwarding uses Linux
abstract sockets to preserve Android-style local semantics;
`localfilesystem:` keeps filesystem semantics.

### scrcpy compatibility layer

The compatibility layer provides a scrcpy 5.x Linux entry point so native
scrcpy on Windows/Linux can connect through adb without Android framework,
SurfaceFlinger or MediaCodec.

- Source: `usr/bin/app_process`, `usr/lib/scrcpy-compat/fake_server.py`.
- The entry point resolves `python3` through `PYTHON` or `PATH`.
- Installed entry point: `/usr/bin/app_process`.
- Installed server: `/usr/lib/<multiarch>/scrcpy-compat/fake_server.py`.
- Local install places `app_process` in `/usr/local/bin` and the server in
  `/usr/local/lib/scrcpy-compat/`.
- `app_process` searches `/usr/local/lib`, `/usr/lib/<multiarch>/scrcpy-compat`
  and a relative `lib` directory, so package and local installs can coexist.

Protocol notes:

With `tunnel_forward=true` the server creates an abstract Unix socket and
accepts, in order:

1. video
2. audio (when enabled)
3. control (when enabled)

In forward mode the client reads one dummy byte, then 64 bytes of device name.
The formal `scid` form is `scrcpy_%08x`.

The video socket carries:

1. 64-byte device name
2. 4-byte big-endian codec id: H.264 is `0x68323634`
3. 12-byte session: big-endian `flags=0x80000000`, `width`, `height`
4. repeated 12-byte frame headers followed by H.264 access units

The frame header is big-endian:

```text
uint64 pts_and_flags
uint32 packet_size
```

Flags: `1 << 63` session, `1 << 62` codec config, `1 << 61` key frame.

The current implementation uses ffmpeg `x11grab` to produce H.264 and splits
access units on AUD (NAL type 9) at about 30 FPS. Capture disables cursor
drawing (`draw_mouse=0`); the host draws its own pointer to avoid lag.

Handled `ControlMessageReader` messages:

- type `0`: keycode, `action + keycode + repeat + metaState`
- type `1`: text, 4-byte length + UTF-8 text
- type `2`: touch, `action + pointerId + x/y + pressure + buttons`
- type `3`: scroll
- type `4`: back/screen-on
- type `8/9/10/18/21`: clipboard/power/torch/resize and similar, consumed by
  the declared length

The X11 backend maps input through `libX11` and `libXtst` to `DISPLAY`; without
X11 it falls back to `/dev/uinput`. Text injection supports ASCII/Latin-1 and
Shift combinations; non-ASCII characters are skipped.

Known boundaries:

- Only screen, touch, keyboard and wheel paths are provided; audio is disabled.
- No Android clipboard, notifications, camera or UHID support.
- `Xvfb` and `ffmpeg` are required for video.
- Type `4` maps to Escape as a desktop approximation.
- High-resolution screens and many small files are limited by ffmpeg/x264 and
  the USB link.

### Android command shims

`usr/bin/android-compat-wrapper` is installed as each command name
(`screencap`, `screenrecord`, `input`, `getprop`, `setprop`, `wm`, `logcat`,
`dumpsys`, `settings`). It resolves the matching Python module under
`/usr/local/lib`, `/usr/lib/android-compat`, or the multiarch
`/usr/lib/*/android-compat` directory. Python is resolved through `PYTHON` or
`PATH`.

Implementation notes:

- `props.py` derives Android properties from device tree, DMI and sysfs.
  Android release/SDK default to 15/35 and can be overridden with
  `ANDROID_COMPAT_RELEASE` / `ANDROID_COMPAT_SDK`.
- `settings` and `getprop` store values in `/run` when possible, falling back
  to the user's home directory.
- `screencap` uses ffmpeg `x11grab`; `screenrecord` uses x264.
- `input text` supports ASCII/Latin-1 only; non-ASCII text is skipped.
- `wm` cannot resize Xvfb and returns failure for write operations.
- `logcat -c` does not clear journald and only prints a notice.
- Use `adb exec-out` for binary output such as PNG screenshots.

## Checks

Shell syntax:

```bash
sh -n usr/bin/usbdevice usr/bin/app_process usr/bin/android-compat-wrapper
sh -n etc/profile.d/usbdevice.sh
```

Python syntax:

```bash
python3 -m py_compile usr/lib/android-compat/*.py \
    usr/lib/scrcpy-compat/*.py
```

Gadget checks on a target:

```bash
systemctl is-enabled usbdevice
systemctl is-active usbdevice
/usr/bin/usbdevice status
cat /sys/kernel/config/usb_gadget/adbd/UDC
```

## CI and release

CI uses `ubuntu-24.04` for amd64 and a self-hosted ARM64 `24.04` runner for
arm64. Each build uploads a `.deb` artifact and publishes a Release when a
`v*` tag is pushed. The tag is compared with the version before the Debian
revision, e.g. `v1.0.3` for package `1.0.3-1`.

## Portability notes

- The gadget manager binds the first UDC and is not tied to a specific SoC.
- USB identity comes from the device tree, DMI, or `/etc/machine-id` when
  available.
- `bash` is preferred for adb shell but is optional; `/bin/sh` is the fallback.
- `python3` is resolved via `PYTHON` or `PATH`; it is not hardcoded to one
  absolute path.
- FunctionFS ownership is configurable instead of fixed to an Android UID/GID.
- The optional scrcpy and Android command layers are Linux/X11 oriented; they
  are not required for the core `adbd` endpoint.
- systemd, configfs and FunctionFS remain platform prerequisites.

## Validation status

- Package builds are expected for amd64 and arm64.
- The scrcpy compatibility layer has been exercised with scrcpy 5.x on a
  Linux/X11 target.
- Upstream submodules remain unmodified after builds.
- A full Windows adb/scrcpy session, USB throughput, VSOCK, reverse forwarding,
  compression negotiation and vendor-specific local-socket paths are not
  covered by the current checks.
- Android framework authentication and TLS pairing are intentionally not
  implemented.

## Security

`adbd` is unauthenticated. Keep the endpoint on trusted USB, loopback, or a
private network. The gadget manager needs root to write configfs and mount
FunctionFS. Do not expose `tcp:5555` to an untrusted network.

## License

The Linux port, packaging, and companion tools are licensed under GPL-3.0.
Upstream AOSP components, fmt, and the adapted patch retain their original
licenses. See `debian/copyright` and `LICENSE`.

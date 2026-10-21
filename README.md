# RoboParty adbd

Device-side AOSP `adbd` port for Debian/Ubuntu Linux, packaged like
`Roboparty/libsoem`: pinned upstream submodules, one `linux-port.patch`, CMake,
and standard `debian/` packaging. This builds `/usr/bin/adbd`, not the host `adb`
client. No kernel source tree or Android platform build is required.

## Source layout

| Path | Purpose |
| --- | --- |
| `adb/` | Official AOSP `platform/packages/modules/adb`, tracking `master` |
| `deps/` | Official AOSP core, libbase, logging and fmt source dependencies |
| `linux-port.patch` | Consolidated Linux/glibc/GCC and daemon integration changes |
| `cmake/` | Standalone build targets |
| `debian/` | Package metadata and debhelper rules |
| `tests/smoke.py` | Isolated loopback protocol checks |

ADB is pinned to `1cf2f017d312f73b3dc53bda85ef2610e35a80e9` (2025-03-25).
On 2026-10-21 the official `master` and `main` refs both pointed there. This is
the requested master snapshot, not a claim that it is the newest Android release.
`git submodule status` records all exact dependency revisions. Builds never
update these pins automatically.

The port incorporates attributed work from `nmeum/android-tools` and
`happyme531/standalone-linux-adbd`; see `NOTICE`. Neither repository is a build
dependency. The patch is maintained here against the official source snapshots.

## Build

```sh
git clone --recurse-submodules https://github.com/Roboparty/adbd.git
cd adbd
git submodule update --init --recursive
sudo apt-get install build-essential debhelper cmake pkg-config patch \
    libbrotli-dev liblz4-dev libzstd-dev python3
dpkg-buildpackage -us -uc -b -j4
```

Artifacts appear in the parent directory as `adbd_<version>_<arch>.deb`.
The binary dynamically links the distribution's libc, C++ and compression
libraries; Debian records these dependencies automatically. AOSP support
libraries and fmt are linked into the executable.

For a direct build and protocol check:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=RelWithDebInfo
cmake --build build --parallel 4
python3 tests/smoke.py build/adbd
```

CMake copies the sources into `<build>/source` and applies the single patch
there with zero fuzz. Reconfiguration and clean/rebuild leave submodules intact.
Do not patch the upstream submodules during a package build.

## Runtime

Supported: FunctionFS USB, TCP/VSOCK listeners, shell protocol v2, file sync
(including upstream compression paths), TCP forwarding and reverse transport.
Android framework authentication, TLS pairing, JDWP, mDNS, APK services and
Android property-driven lifecycle are not provided. The daemon runs with the
UID of its launcher. It is an unauthenticated development endpoint.

USB uses `/dev/usb-ffs/adb/ep0`, `ep1` and `ep2`. The BSP must configure/mount
FunctionFS and manage the gadget/UDC. This package intentionally installs no
gadget manager or auto-start service; installing it must not reconfigure USB.
The existing BSP launcher can launch `/usr/bin/adbd` once FunctionFS is prepared.
However, the old BSP packages that launcher, service and module-load configuration
inside its own package named `adbd`. They are not supplied by an independent BSP
package. Replacing that package with this daemon-only package does not preserve
the full startup integration. Migrate ownership of those files before deployment;
this package is not yet a drop-in replacement for the old BSP package.

| Environment variable | Meaning |
| --- | --- |
| `ADBD_LISTEN` | Explicit comma-separated socket specs, e.g. `tcp:127.0.0.1:5555` or `vsock:5555` |
| `ADBD_PORT` | TCP port on loopback; used only when `ADBD_LISTEN` is unset |
| `ADB_TCP_PORT` | Legacy fallback for `ADBD_PORT` |
| `ADBD_SHELL` | Shell executable, defaults to `/bin/sh` |
| `ADBD_USB=0` | Disable USB discovery, useful for isolated tests |

No network listener is opened by default. With neither USB nor explicit
network configuration the daemon exits with an error. To enable network access
use an explicit socket spec (`tcp:5555` listens on all interfaces); exposing it beyond loopback gives clients shell access
without authentication. `local:` forwarding uses Linux abstract sockets for
Rockchip RKNN compatibility; `localfilesystem:` keeps filesystem semantics.

The smoke test checks no implicit listener, ADB handshake, shell stdout/stderr
and exit status, a 256 KiB binary push/pull, and TCP forwarding. It does not use
an adb server or touch USB. Physical FunctionFS enumeration, VSOCK, reverse
forwarding and compressed transfers require separate integration validation.

## Updating and CI

```sh
git -C adb fetch origin master
git -C adb checkout --detach origin/master
```

Review upstream changes, rebase `linux-port.patch`, update the recorded revision
and Debian changelog, then rebuild and run tests. Dependency updates are also
explicit. A branch setting alone does not change the recorded submodule commit.

CI builds amd64 on `ubuntu-22.04` and arm64 on `[self-hosted, rk3588]`, following
libsoem. It tests the extracted package and publishes artifacts on each build.
A tag must equal the **full Debian version**, e.g.
`v1.0.41+git20250325.1cf2f017-2`. A Release is published only after both builds
and their protocol checks pass.

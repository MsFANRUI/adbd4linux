# Build validation - 2026-10-21

## Pinned source revisions

| Submodule | Commit |
| --- | --- |
| adb | `1cf2f017d312f73b3dc53bda85ef2610e35a80e9` |
| core | `a3b721a32242006b59cb12bd62c9133632af3a2d` |
| libbase | `6d19b5c690fa4220c10e42c2326150bbd4d4b7bb` |
| logging | `bcac7c30d88a3773a7c0bc9f5617a23a886331fd` |
| fmtlib | `97ceae9d27415d6444f3e24f491da8ed6902ecfa` |

All sources come from official AOSP repositories. The ADB master snapshot is
dated 2025-03-25. The support repositories are independently pinned; they are
not described as a single Android release manifest.

## Results

Both native builds succeeded with version `1.0.41+git20250325.1cf2f017-1`:

| Architecture | Environment | Package | Protocol smoke test |
| --- | --- | --- | --- |
| amd64 | Ubuntu 22.04, GCC 11 | PASS | PASS, extracted package binary |
| arm64 | Ubuntu 24.04, GCC 13, RK3588 | PASS | PASS, extracted package binary |

Build command: `dpkg-buildpackage -us -uc -b -j4` (amd64 used `-j8`).
Test command: `python3 tests/smoke.py <extracted-package>/usr/bin/adbd`.

Checks performed:

- No USB and no explicit listener: exits with status 1.
- ADB CNXN handshake over loopback, without a host adb server.
- Shell v2: separate stdout/stderr and exact nonzero exit status.
- Push/pull: 256 KiB binary payload, byte-for-byte comparison.
- TCP forwarding to a temporary local echo socket.
- Package metadata and x86-64/AArch64 ELF identity.
- Upstream submodules remain unmodified after builds.

The local amd64 build log is `build/debian-build.log`. The native arm64 build
was performed in `/home/robo/adbd-port-check-20261021/source` on the existing
arm64 runner; its log is `../build.log`. Packages are copied to `output/` in
the packaging checkout for inspection. No package was installed on either host.

## Compatibility boundaries

The amd64 package requires libc6 >= 2.34 and libstdc++6 >= 12 as recorded by
dpkg-shlibdeps on that host. The arm64 package requires libc6 >= 2.38,
libstdc++6 >= 13.1 and libzstd1 >= 1.5.5. These artifacts are dynamically linked;
the arm64 build is not a promise of compatibility with Ubuntu 22.04. Build on
the oldest intended distribution to target its runtime ABI.

Compiler warnings about attributes and control flow after fatal logging remain
in upstream code. The arm64 host also emits a dpkg-shlibdeps warning about its
merged-/usr loader diversion. Packaging and the runtime checks above succeeded.

FunctionFS code was compiled for both architectures. Physical USB enumeration,
USB throughput, VSOCK, reverse forwarding, compression negotiation and RKNN
were not exercised. Android framework authentication and TLS pairing are not
implemented. GitHub Actions has been configured but not run for these local,
uncommitted changes. The BSP source selection has not been switched to this package.

## Host-only rebuild and service audit

Rechecked on 2026-10-21 following the request to avoid board validation. No SSH
connection, board command, package installation or service activation was used
in this recheck. The arm64 results above belong to the earlier validation, not
this host-only recheck.

`dpkg-buildpackage -us -uc -b -j8` completed a clean amd64 rebuild. The extracted
package again passed `tests/smoke.py`. All source submodules remain clean.
Build log: `output/build-amd64-recheck.log`.

Offline service check:

```sh
python3 tests/audit_bsp_service.py \
  ../../bsp/roboparty_build/lib/functions/compilation/packages/adbd-deb.sh
```

The test extracts the BSP's embedded payloads without sourcing its build script,
remaps all hardware/configuration paths into a temporary directory, and blocks
mount, unmount, process termination, daemon launch and systemctl commands.
It verifies shell syntax and the no-UDC, inactive, invalid-argument and bound-UDC
branches. `systemd-analyze verify` passed with Exec paths mapped to the extracted
helper. The host emitted unrelated netplan permission and snapd RestartMode
warnings. Log: `output/service-audit.log`.

Findings requiring integration work before deployment:

1. **Missing service payload in the new package.** The old BSP package named
   `adbd` owns `/usr/bin/usbdevice`, `usbdevice.service`, `/etc/default/adbd-gadget`,
   the profile snippet and module-load configuration. Verified against the local
   `adbd_1-SAbdb5-B314b-R448a_arm64.deb`. The new package contains only the daemon
   and documentation. Replacing the same-name package removes obsolete ordinary
   payload files; this does not retain a working USB startup stack. The earlier
   assertion that an independent BSP package supplies these files was incorrect.
2. **Daemon failure is not supervised.** The old unit uses `Type=oneshot` and
   `RemainAfterExit=yes`, while the helper backgrounds adbd. Unit active state
   therefore is not evidence that adbd is still alive; there is no daemon restart
   policy. The mock test also proves that a bound gadget reports active/start
   success even when the configured adbd executable does not exist.
3. **Global process matching.** `pidof adbd` can mistake an unrelated daemon for
   the intended USB instance, and `pkill -x adbd` targets every matching instance.
   A service-owned foreground process or explicit instance tracking is needed.
4. **Windows discovery remains incomplete.** AOSP supplies FunctionFS Microsoft
   descriptors, but the current BSP helper does not enable/configure the configfs
   gadget `os_desc` path. Automatic Windows WinUSB binding is not established by
   this audit; it requires integration and later USB testing.

The existing helper's descriptor-before-UDC-bind ordering is consistent with
the daemon's FunctionFS initialization. Actual mounts, UDC binding, shutdown
cleanup and USB enumeration were not executed, so their runtime correctness is
not claimed. Service/launcher implementation and BSP files were not changed
as part of this verification request.

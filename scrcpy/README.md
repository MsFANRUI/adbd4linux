# scrcpy 兼容层交接

## 目录和来源

- 兼容层源码：`scrcpy/`
- 上游 scrcpy 源码：`/home/robo/roboparty_repo/test/scrcpy-source`
- 上游版本：v5.0.1，commit `a60891a`
- 板端入口：`/usr/local/bin/app_process`
- 板端服务端：`/usr/local/lib/scrcpy-compat/fake_server.py`
- 默认显示：`Xvfb :99`，XFCE 使用 `DISPLAY=:99`

`app_process` 是兼容入口。scrcpy 将原版 `scrcpy-server` 推送到板端后执行
`app_process`，入口把参数转给 Python 服务端。因此不需要 Android 的
`app_process`、SurfaceFlinger 或 Android MediaCodec。

## 上游协议对照

对照文件：

- `test/scrcpy-source/server/src/main/java/com/genymobile/scrcpy/device/DesktopConnection.java`
- `test/scrcpy-source/server/src/main/java/com/genymobile/scrcpy/device/Streamer.java`
- `test/scrcpy-source/server/src/main/java/com/genymobile/scrcpy/control/ControlMessageReader.java`
- `test/scrcpy-source/app/src/demuxer.c`

### socket

上游在 `tunnel_forward=true` 时建立一个 abstract Unix socket，依次接受：

1. video
2. audio（启用时）
3. control（启用时）

`scid` 的正式命名规则是 `scrcpy_%08x`。当前兼容层保留传入的 `scid` 字符串，
这是为了兼容现有 adb 转发链路；若后续遇到新版本客户端连接失败，首先检查这里
是否需要按上游规则格式化。

### video

video socket 的字节顺序为：

1. 64 字节设备名
2. 4 字节大端 codec id：H.264 为 `0x68323634`
3. 12 字节 session：大端 `flags=0x80000000`、`width`、`height`
4. 循环发送 12 字节 frame header 和对应 H.264 access unit

frame header 是大端：

```text
uint64 pts_and_flags
uint32 packet_size
```

上游标志位：

- `1 << 63`：session packet
- `1 << 62`：codec config packet
- `1 << 61`：关键帧

当前兼容层使用 ffmpeg `x11grab` 持续输出 H.264，并按 AUD（NAL type 9）切分
access unit，再以约 30 FPS、33,333 微秒的 PTS 发送。首个包含 SPS/PPS/IDR 的
access unit 标记为关键帧。

### control

控制消息来自上游 `ControlMessageReader`。当前已处理：

- type `0`：keycode，`action + keycode + repeat + metaState`
- type `2`：touch，`action + pointerId + x/y + pressure + buttons`
- type `3`：scroll
- type `4`：back/screen-on

X11 后端通过 `libX11`、`libXtst` 把 touch 映射到 `DISPLAY=:99`；没有 X11 时退回
`/dev/uinput`。当前 type `4` 在 X11 后端映射为 Escape，后续可按桌面语义调整。

## 已验证

在 RoboPi2 上验证过：

- `scrcpy` 可发现 adb 设备并启动兼容入口
- video session 为 `1280x720`
- 首帧约 0.5 秒到达
- 连续帧 PTS 间隔约 33,333 微秒
- video 与 control socket 可同时建立
- type `2` 可改变 Xvfb 指针位置
- type `4` 不再产生 `unsupported control message 4`

## 已知限制和下一步

这是 Linux/Xvfb 兼容层，不是完整 Android scrcpy server：

- 只提供屏幕、触控、键盘和滚轮路径
- 音频通过 disabled-stream 标记关闭
- 没有 Android clipboard、通知、摄像头、UHID 等能力
- Xvfb/xfce 会影响桌面合成和指针视觉反馈

如果鼠标仍然有明显延迟，按这个顺序排查：

1. 确认板端 `Xvfb :99` 和 `xfce4-session` 正在运行。
2. 检查 `fake_server.py` 是否仍使用 `stream_display()`，不能退回旧的临时文件捕获。
3. 对照上游 `ControlMessageReader.parseInjectTouchEvent()` 检查字段长度和大端序。
4. 将 X11 指针注入从 `XWarpPointer()` 对照测试为 `XTestFakeMotionEvent()`，观察
   XFCE 是否能更快刷新指针。
5. 用 scrcpy 的 `--no-audio`、`--max-fps 30` 做单变量测试。

## 常用验证

语法检查：

```bash
python3 -m py_compile deb/adbd/scrcpy/fake_server.py
```

板端检查：

```bash
ssh -p 22250 root@127.0.0.1
ps -ef | grep -E '[X]vfb :99|[x]fce4-session'
ls -l /usr/local/bin/app_process /usr/local/lib/scrcpy-compat/fake_server.py
```

Windows 端直接运行：

```powershell
scrcpy
```


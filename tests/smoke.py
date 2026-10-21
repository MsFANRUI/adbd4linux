#!/usr/bin/env python3
"""Exercise the built daemon over loopback without an adb server or USB access."""
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time


def exact(sock, size):
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("unexpected EOF")
        data.extend(chunk)
    return bytes(data)


class Connection:
    def __init__(self, port):
        self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
        # Protocol 1.0 requires checksums and avoids delayed-ACK negotiation.
        self.send(b"CNXN", 0x01000000, 4096, b"host::features=shell_v2\0")
        command, _, _, self.banner = self.recv()
        assert command == b"CNXN", command

    def send(self, command, arg0, arg1, data=b""):
        number = int.from_bytes(command, "little")
        self.sock.sendall(struct.pack("<6I", number, arg0, arg1, len(data),
                                      sum(data) & 0xffffffff, number ^ 0xffffffff) + data)

    def recv(self):
        number, arg0, arg1, length, checksum, magic = struct.unpack("<6I", exact(self.sock, 24))
        assert magic == number ^ 0xffffffff
        assert length <= 1024 * 1024
        data = exact(self.sock, length)
        assert checksum == sum(data) & 0xffffffff
        return number.to_bytes(4, "little"), arg0, arg1, data

    def open(self, service):
        self.send(b"OPEN", 1, 0, service.encode() + b"\0")
        command, self.remote, local, _ = self.recv()
        assert (command, local) == (b"OKAY", 1), (command, local, service)

    def write(self, data):
        for offset in range(0, len(data), 4096):
            self.send(b"WRTE", 1, self.remote, data[offset:offset + 4096])
            command, _, _, _ = self.recv()
            assert command == b"OKAY", command

    def read(self):
        command, remote, local, data = self.recv()
        assert (remote, local) == (self.remote, 1)
        if command == b"WRTE":
            self.send(b"OKAY", 1, self.remote)
            return data
        assert command == b"CLSE", command
        self.send(b"CLSE", 1, self.remote)
        return None

    def close(self):
        self.sock.close()


def unused_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    binary = str(Path(sys.argv[1]).resolve())
    port = unused_port()
    env = {k: v for k, v in os.environ.items()
           if k not in ("ADBD_LISTEN", "ADBD_PORT", "ADB_TCP_PORT", "ADBD_SHELL")}
    env["ADBD_USB"] = "0"
    result = subprocess.run([binary], env=env, capture_output=True, timeout=5)
    assert result.returncode == 1, "no transport must fail without opening a default listener"
    assert b"No FunctionFS endpoint" in result.stderr
    env["ADBD_LISTEN"] = f"tcp:127.0.0.1:{port}"
    env["ADBD_SHELL"] = "/bin/sh"
    with tempfile.TemporaryDirectory(prefix="adbd-smoke-") as directory:
        root = Path(directory)
        with (root / "daemon.log").open("wb") as log:
            daemon = subprocess.Popen([binary], env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if daemon.poll() is not None:
                        raise RuntimeError((root / "daemon.log").read_text())
                    try:
                        connection = Connection(port)
                        break
                    except ConnectionRefusedError:
                        time.sleep(0.05)
                else:
                    raise RuntimeError("daemon did not listen\n" + (root / "daemon.log").read_text())
                assert b"shell_v2" in connection.banner
                assert b"abb_exec" not in connection.banner
                connection.open("shell,v2,raw:printf out; printf err >&2; exit 7")
                data = bytearray()
                while (chunk := connection.read()) is not None:
                    data.extend(chunk)
                connection.close()
                streams = {1: bytearray(), 2: bytearray(), 3: bytearray()}
                while data:
                    stream, length = struct.unpack("<BI", data[:5])
                    assert len(data) >= 5 + length
                    streams[stream].extend(data[5:5 + length])
                    del data[:5 + length]
                assert streams == {1: b"out", 2: b"err", 3: b"\x07"}, streams

                payload = bytes(range(256)) * 1024
                remote_file = root / "roundtrip.bin"
                connection = Connection(port)
                connection.open("sync:")
                name = f"{remote_file},33188".encode()
                connection.write(b"SEND" + struct.pack("<I", len(name)) + name)
                for offset in range(0, len(payload), 65536):
                    chunk = payload[offset:offset + 65536]
                    connection.write(b"DATA" + struct.pack("<I", len(chunk)) + chunk)
                connection.write(b"DONE" + struct.pack("<I", 1))
                assert connection.read() == b"OKAY\0\0\0\0"
                assert remote_file.read_bytes() == payload
                name = str(remote_file).encode()
                connection.write(b"RECV" + struct.pack("<I", len(name)) + name)
                buffer = bytearray()
                received = bytearray()
                done = False
                while not done:
                    chunk = connection.read()
                    assert chunk is not None
                    buffer.extend(chunk)
                    while len(buffer) >= 8:
                        tag, length = struct.unpack("<4sI", buffer[:8])
                        if tag == b"DONE":
                            done = True
                            break
                        assert tag == b"DATA", (tag, buffer)
                        if len(buffer) < 8 + length:
                            break
                        received.extend(buffer[8:8 + length])
                        del buffer[:8 + length]
                assert received == payload
                connection.close()

                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", 0))
                    listener.listen(1)
                    listener.settimeout(5)

                    def echo():
                        peer, _ = listener.accept()
                        with peer:
                            peer.sendall(exact(peer, 4))

                    worker = threading.Thread(target=echo)
                    worker.start()
                    connection = Connection(port)
                    connection.open(f"tcp:{listener.getsockname()[1]}")
                    connection.write(b"ping")
                    assert connection.read() == b"ping"
                    connection.close()
                    worker.join(timeout=5)
                    assert not worker.is_alive()
                print("PASS: no implicit listener; handshake; shell stdout/stderr/exit; "
                      "256 KiB push/pull; TCP forwarding")
            finally:
                daemon.terminate()
                try:
                    daemon.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    daemon.kill()
                    daemon.wait()
                if daemon.returncode not in (-15, 0):
                    print((root / "daemon.log").read_text(), file=sys.stderr)


if __name__ == "__main__":
    main()

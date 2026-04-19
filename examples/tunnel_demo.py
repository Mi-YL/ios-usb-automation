"""
示例：手动创建隧道。

本示例展示如何手动创建 usbmuxd 隧道，
当你需要访问 iOS 设备上的任意服务时很有用（不仅限于 WDA）。

运行方式:
    python examples/tunnel_demo.py
"""

import time
import socket
from ios_usbmuxd import Tunnel, DeviceManager


def main():
    print("=" * 50)
    print("手动创建隧道示例")
    print("=" * 50)

    # 查找设备
    print("\n正在查找 iOS 设备...")
    with DeviceManager() as manager:
        device = manager.find_device()
        if not device:
            print("未找到 iOS 设备！")
            return
        print(f"找到设备: {device.udid}")
        udid = device.udid

    # 创建到 WDA 端口 (8100) 的隧道
    print(f"\n正在创建到 iOS 设备端口 8100 的隧道...")
    print("此后，localhost:8100 将转发到 iOS 设备。")

    tunnel = Tunnel(
        local_port=8100,
        remote_port=8100,
        udid=udid,
    )

    try:
        tunnel.start()
        print("隧道已启动！")

        # 通过连接 localhost:8100 验证隧道是否正常工作
        print("\n正在验证隧道，连接到 localhost:8100...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect(("127.0.0.1", 8100))
            sock.sendall(b"GET /status HTTP/1.1\r\nHost: localhost\r\n\r\n")
            response = sock.recv(4096)
            print(f"  收到响应: {len(response)} 字节")
            print(f"  前 100 字符: {response[:100]}")
        except Exception as e:
            print(f"  连接失败: {e}")
        finally:
            sock.close()

        print("\n隧道正在运行，按 Ctrl+C 停止...")

        # 保持隧道运行
        while tunnel.is_running():
            time.sleep(1)

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        tunnel.stop()
        print("隧道已停止。")


if __name__ == "__main__":
    main()

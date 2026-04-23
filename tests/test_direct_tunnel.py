# test_direct_tunnel.py - 放在项目根目录运行
import socket

from ios_usbmuxd import DeviceManager, UsbmuxdClient


def main():
    # 1. 找设备
    with DeviceManager() as manager:
        device = manager.find_device()
        print(f"设备: {device.udid}")

    # 2. 直连设备 8100 端口
    client = UsbmuxdClient()
    client.connect()
    client.connect_to_device(device, 8100)
    print("CONNECT 成功!")

    # 3. 直接发送 HTTP 请求
    sock = client.socket
    sock.settimeout(5.0)
    request = b"GET /status HTTP/1.1\r\nHost: localhost:8100\r\n\r\n"
    sock.sendall(request)
    print(f"发送 HTTP 请求: {len(request)} 字节")

    # 4. 读取响应
    response = b""
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break

    print(f"响应 ({len(response)} 字节):")
    print(response.decode("utf-8", errors="replace")[:500])

    client.disconnect()


if __name__ == "__main__":
    main()

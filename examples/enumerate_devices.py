"""
示例：枚举已连接的 iOS 设备。

本示例展示如何列出所有通过 USB 连接的 iOS 设备。

运行方式:
    python examples/enumerate_devices.py
"""

from ios_usbmuxd import DeviceManager, UsbmuxdClient


def main():
    print("=" * 50)
    print("iOS 设备枚举示例")
    print("=" * 50)

    # 方式一：使用 DeviceManager（推荐）
    print("\n使用 DeviceManager（推荐）:")
    print("-" * 30)
    try:
        with DeviceManager() as manager:
            devices = manager.list_devices()
            if not devices:
                print("未找到 iOS 设备。")
                print("请确保设备通过 USB 连接并已授权信任。")
            else:
                for device in devices:
                    print(f"  设备 ID: {device.device_id}")
                    print(f"  UDID: {device.udid}")
                    print(f"  连接方式: {device.connection_type}")
                    print(f"  产品 ID: {device.product_id}")
                    print()
    except Exception as e:
        print(f"错误: {e}")
        print("\n请确保 usbmuxd 已运行:")
        print("  - Windows: 安装 iTunes（含 Apple Mobile Device Support）")
        print("  - macOS:  Xcode Command Line Tools（自带）")
        print("  - Linux:  安装 libimobiledevice 包")

    # 方式二：直接使用 UsbmuxdClient
    print("\n直接使用 UsbmuxdClient:")
    print("-" * 30)
    try:
        client = UsbmuxdClient()
        client.connect()
        devices = client.enumerate_devices()
        client.disconnect()

        if not devices:
            print("未找到 iOS 设备。")
        else:
            for device in devices:
                print(f"  {device}")
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()

"""
示例：通过 USB 进行 iOS UI 自动化。

本示例展示如何通过 USB 连接到 iOS 设备上的 WDA，
使用纯 Python 实现（安装 WDA 后无需 Mac）。

前置条件:
1. Windows 上安装 iTunes/usbmuxd
2. iOS 设备上安装 WebDriverAgent（通过 Mac + Xcode 安装）
3. iOS 设备通过 USB 连接并已授权信任

运行方式:
    python examples/basic_automation.py
"""

import time
from ios_usbmuxd import WDAClient, DeviceManager


def main():
    print("=" * 50)
    print("iOS USB 自动化示例")
    print("=" * 50)

    # 查找设备
    print("\n正在查找 iOS 设备...")
    try:
        with DeviceManager() as manager:
            device = manager.find_device()
            if not device:
                print("未找到 iOS 设备！")
                print("请确保设备通过 USB 连接并已授权信任。")
                return
            print(f"找到设备: {device.udid}")
            udid = device.udid
    except Exception as e:
        print(f"查找设备时出错: {e}")
        return

    # 通过 USB 连接到 WDA
    print(f"\n正在通过 USB 连接到 WDA (UDID: {udid[:8]}...)...")
    client = WDAClient(
        udid=udid,
        use_usbmuxd=True,
        timeout=30.0,
    )

    try:
        if not client.connect():
            print("连接 WDA 失败！")
            print("请确保 WDA 已安装在 iOS 设备上。")
            return

        print("已连接到 WDA！")

        # 获取屏幕信息
        print("\n正在获取屏幕信息...")
        size = client.get_screen_size()
        if size:
            print(f"  屏幕尺寸: {size['width']}x{size['height']}")

        # 截取屏幕截图
        print("\n正在截取屏幕截图...")
        screenshot = client.screenshot()
        if screenshot:
            with open("screenshot.png", "wb") as f:
                f.write(screenshot)
            print("  截图已保存到: screenshot.png")
        else:
            print("  截图失败")

        # 获取页面源码
        print("\n正在获取页面源码...")
        source = client.source()
        if source:
            print(f"  源码长度: {len(source)} 字符")
        else:
            print("  获取源码失败")

        # 等待一下
        time.sleep(1)

        # 示例交互（根据实际屏幕调整坐标）
        print("\n示例：在坐标 (200, 400) 处点击...")
        if client.click(200, 400):
            print("  点击成功！")
        else:
            print("  点击失败（可能超出范围）")

        # 清理
        print("\n正在断开连接...")
        client.terminate_session()

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()

    finally:
        client.disconnect()

    print("\n完成！")


if __name__ == "__main__":
    main()

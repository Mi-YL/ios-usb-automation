"""
手动测试脚本：打开 Safari，返回桌面，然后左滑两次。

运行方式:
    PYTHONPATH=src .venv/bin/python tests/test_safari_home_swipes.py
"""

import time

from ios_usbmuxd import DeviceManager, WDAClient


SAFARI_BUNDLE_ID = "com.apple.mobilesafari"
OPEN_WAIT_SECONDS = 2.0
HOME_WAIT_SECONDS = 1.0
SWIPE_PAUSE_SECONDS = 0.8


def find_connected_udid() -> str:
    """获取首个已连接设备的 UDID。"""
    with DeviceManager() as manager:
        device = manager.find_device()
        if not device:
            raise RuntimeError("未找到已连接的 iOS 设备")
        return device.udid


def build_home_swipe(size):
    """根据屏幕尺寸计算桌面横向翻页的滑动坐标。"""
    width = int(size["width"])
    height = int(size["height"])
    start_x = int(width * 0.85)
    end_x = int(width * 0.15)
    y = int(height * 0.5)
    return start_x, y, end_x, y


def main():
    udid = find_connected_udid()
    print(f"找到设备: {udid}")

    client = WDAClient(
        udid=udid,
        use_usbmuxd=True,
        timeout=30.0,
    )

    try:
        print("1/4 打开 Safari...")
        if not client.connect(bundle_id=SAFARI_BUNDLE_ID):
            raise RuntimeError("无法创建 Safari 会话")
        time.sleep(OPEN_WAIT_SECONDS)

        print("2/4 返回桌面...")
        if not client.go_home():
            raise RuntimeError("返回桌面失败")
        time.sleep(HOME_WAIT_SECONDS)

        print("3/4 切换到桌面会话...")
        client.terminate_session()
        # bundle_id=None 表示附着到当前前台界面，此时应为桌面。
        if not client.connect(bundle_id=None, launch_if_needed=False):
            raise RuntimeError("无法附着到桌面会话")

        size = client.get_screen_size()
        if not size:
            raise RuntimeError("无法获取桌面屏幕尺寸")
        print(f"屏幕尺寸: {size['width']}x{size['height']}")

        start_x, y, end_x, _ = build_home_swipe(size)

        for index in range(2):
            print(f"4/4 第 {index + 1} 次左滑...")
            if not client.swipe(start_x, y, end_x, y, duration=0.15):
                raise RuntimeError(f"第 {index + 1} 次左滑失败")
            time.sleep(SWIPE_PAUSE_SECONDS)

        print("脚本执行完成。")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()

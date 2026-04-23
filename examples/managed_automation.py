"""
示例：带 WDA 启动策略的跨平台自动化。

本示例展示如何让同一套 Python 代码在不同宿主机上工作：

- macOS:
  - IOS_WDA_LAUNCHER=devicectl
  - IOS_WDA_LAUNCHER=xcodebuild
- Windows / macOS:
  - IOS_WDA_LAUNCHER=command
  - 例如用 ssh 调远端 Mac 启动 WDA
- 任意平台:
  - IOS_WDA_LAUNCHER=none（只连接已在运行的 WDA）

常用环境变量：

- IOS_WDA_LAUNCHER
- IOS_WDA_RUNNER_BUNDLE_ID
- IOS_WDA_XCTESTRUN
- IOS_WDA_PROJECT
- IOS_WDA_DERIVED_DATA
- IOS_WDA_COMMAND
"""

import os

from ios_usbmuxd import DeviceManager, WDAClient, create_wda_launcher


def build_launcher():
    strategy = os.getenv("IOS_WDA_LAUNCHER", "none").strip().lower()
    if strategy in ("", "none"):
        return None

    if strategy == "devicectl":
        return create_wda_launcher(
            "devicectl",
            bundle_id=os.getenv(
                "IOS_WDA_RUNNER_BUNDLE_ID",
                "com.appium.WebDriverAgentRunner.xctrunner",
            ),
            device_identifier=os.getenv("IOS_DEVICE_IDENTIFIER") or None,
        )

    if strategy == "xcodebuild":
        xctestrun = os.getenv("IOS_WDA_XCTESTRUN")
        project = os.getenv("IOS_WDA_PROJECT")
        if not xctestrun and not project:
            raise RuntimeError(
                "IOS_WDA_LAUNCHER=xcodebuild 时需要设置 IOS_WDA_XCTESTRUN 或 IOS_WDA_PROJECT"
            )

        extra_args = [
            arg
            for arg in os.getenv("IOS_WDA_XCODEBUILD_ARGS", "").split()
            if arg
        ]
        return create_wda_launcher(
            "xcodebuild",
            xctestrun_path=xctestrun or None,
            project_path=project or None,
            derived_data_path=os.getenv("IOS_WDA_DERIVED_DATA") or None,
            device_identifier=os.getenv("IOS_DEVICE_IDENTIFIER") or None,
            extra_args=extra_args,
        )

    if strategy == "command":
        command = os.getenv("IOS_WDA_COMMAND")
        if not command:
            raise RuntimeError(
                "IOS_WDA_LAUNCHER=command 时需要设置 IOS_WDA_COMMAND"
            )
        return create_wda_launcher(
            "command",
            command=command,
            shell=True,
            background=False,
        )

    raise RuntimeError(f"不支持的 IOS_WDA_LAUNCHER: {strategy}")


def main():
    print("=" * 50)
    print("跨平台 WDA 启动 + 自动化示例")
    print("=" * 50)

    with DeviceManager() as manager:
        device = manager.get_device()
        print(f"设备 UDID: {device.udid}")

    launcher = build_launcher()
    if launcher is None:
        print("启动策略: none（仅连接已运行的 WDA）")
    else:
        print(f"启动策略: {launcher.__class__.__name__}")

    client = WDAClient(
        udid=device.udid,
        use_usbmuxd=True,
        launcher=launcher,
        timeout=30.0,
    )

    try:
        if not client.connect(bundle_id="com.apple.mobilesafari"):
            raise RuntimeError("WDA 未就绪，无法创建会话")

        print("WDA 已连接")
        print(f"屏幕尺寸: {client.get_screen_size()}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()

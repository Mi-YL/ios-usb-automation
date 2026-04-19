"""
ios_usbmuxd - 纯 Python usbmuxd 客户端，用于跨平台 iOS 自动化。

纯 Python 实现的 Apple usbmuxd 协议，用于在 Windows、macOS 和 Linux 上
通过 USB 与 iOS 设备通信。

支持的平台:
- Windows: TCP 套接字 127.0.0.1:27015
- macOS: Unix 套接字 /var/run/usbmuxd
- Linux: Unix 套接字 /var/run/usbmuxd

使用示例:
    >>> from ios_usbmuxd import WDAClient, DeviceManager
    >>>
    >>> # 列出已连接设备
    >>> with DeviceManager() as manager:
    ...     devices = manager.list_devices()
    ...     print(devices)
    >>>
    >>> # 通过 USB 连接到 WDA 并进行自动化
    >>> client = WDAClient(udid="00001234-56789ABCDEF", use_usbmuxd=True)
    >>> client.connect()
    >>> screenshot = client.screenshot()
    >>> client.click(100, 200)
    >>> client.disconnect()
"""

__version__ = "0.1.0"

# 协议模块
from .protocol import (
    UsbmuxdProtocol,
    MessageType,
    ResultCode,
    HEADER_SIZE,
)

# 异常
from .exceptions import (
    UsbmuxdError,
    ProtocolError,
    ConnectionError,
    ConnectionClosedError,
    InsufficientDataError,
    TunnelError,
    DeviceNotFoundError,
    DeviceConnectError,
    WDAError,
    SessionError,
)

# 客户端
from .client import UsbmuxdClient, get_default_socket_path

# 设备管理
from .device import DeviceInfo, DeviceManager

# 隧道
from .tunnel import TunnelServer, Tunnel

# WDA 客户端
from .wda_client import WDAClient

__all__ = [
    # 版本
    "__version__",
    # 协议
    "UsbmuxdProtocol",
    "MessageType",
    "ResultCode",
    "HEADER_SIZE",
    # 异常
    "UsbmuxdError",
    "ProtocolError",
    "ConnectionError",
    "ConnectionClosedError",
    "InsufficientDataError",
    "TunnelError",
    "DeviceNotFoundError",
    "DeviceConnectError",
    "WDAError",
    "SessionError",
    # 核心
    "UsbmuxdClient",
    "get_default_socket_path",
    # 设备
    "DeviceInfo",
    "DeviceManager",
    # 隧道
    "TunnelServer",
    "Tunnel",
    # WDA
    "WDAClient",
]

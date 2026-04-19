"""
ios_usbmuxd 包自定义异常。
"""


class UsbmuxdError(Exception):
    """usbmuxd 相关错误基类。"""
    pass


class ProtocolError(UsbmuxdError):
    """协议解析或验证错误。"""
    pass


class ConnectionError(UsbmuxdError):
    """连接 usbmuxd 守护进程失败。"""
    pass


class ConnectionClosedError(UsbmuxdError):
    """连接被对方关闭。"""
    pass


class InsufficientDataError(UsbmuxdError):
    """接收到的数据不足。"""
    pass


class TunnelError(UsbmuxdError):
    """隧道创建或操作错误。"""
    pass


class DeviceNotFoundError(UsbmuxdError):
    """未找到 iOS 设备。"""
    pass


class DeviceConnectError(UsbmuxdError):
    """通过 usbmuxd 连接设备失败。"""
    pass


class WDAError(UsbmuxdError):
    """WebDriverAgent 操作错误。"""
    pass


class SessionError(WDAError):
    """WDA 会话创建或管理错误。"""
    pass

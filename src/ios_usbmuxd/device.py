"""
设备信息和管理模块。
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, List

from .exceptions import DeviceNotFoundError

if TYPE_CHECKING:
    from .client import UsbmuxdClient


@dataclass
class DeviceInfo:
    """
    已连接 iOS 设备的信息。

    属性:
        device_id: usbmuxd 内部设备 ID
        udid: 设备 UDID (40位十六进制字符串)
        product_id: USB 产品 ID
        location_id: USB 位置 ID
        serial_number: 设备序列号
        connection_type: 连接类型 ("USB" 或 "Network")
    """
    device_id: int
    udid: str
    product_id: int = 0
    location_id: int = 0
    serial_number: str = ""
    connection_type: str = "USB"

    @property
    def is_network(self) -> bool:
        """检查设备是否通过网络连接。"""
        return self.connection_type == "Network"

    @property
    def is_usb(self) -> bool:
        """检查设备是否通过 USB 连接。"""
        return self.connection_type == "USB"

    def __str__(self) -> str:
        """设备的字符串表示。"""
        return f"Device({self.udid[:8]}... via {self.connection_type})"


class DeviceManager:
    """
    设备枚举和选择管理。

    参数:
        client: UsbmuxdClient 实例（如果未提供，将自动创建）
    """

    def __init__(self, client: Optional["UsbmuxdClient"] = None):
        """
        初始化设备管理器。

        参数:
            client: 可选的现有 UsbmuxdClient。如果未提供，将创建新实例。
        """
        self._client = client
        self._owns_client = client is None

    @property
    def client(self) -> "UsbmuxdClient":
        """获取或创建 usbmuxd 客户端。"""
        if self._client is None:
            self._client = UsbmuxdClient()
            self._client.connect()
        return self._client

    def list_devices(self) -> List[DeviceInfo]:
        """
        列出所有已连接的 iOS 设备。

        返回:
            DeviceInfo 对象列表

        异常:
            DeviceNotFoundError: 未找到设备时（可选，当前返回空列表）
        """
        return self.client.enumerate_devices()

    def find_device(self, udid: Optional[str] = None) -> Optional[DeviceInfo]:
        """
        通过 UDID 查找指定设备或返回第一个可用设备。

        参数:
            udid: 要搜索的设备 UDID。如果为 None，返回第一个可用设备。

        返回:
            找到返回 DeviceInfo，未找到返回 None
        """
        devices = self.list_devices()
        if not devices:
            return None

        if udid is None:
            return devices[0]

        # 先尝试精确匹配
        for device in devices:
            if device.udid == udid:
                return device

        # 再尝试后缀匹配（常用于简写 UDID）
        for device in devices:
            if device.udid.endswith(udid):
                return device

        return None

    def get_device(self, udid: Optional[str] = None) -> DeviceInfo:
        """
        获取设备，未找到时抛出异常。

        参数:
            udid: 要搜索的设备 UDID。如果为 None，返回第一个可用设备。

        返回:
            DeviceInfo

        异常:
            DeviceNotFoundError: 未找到设备
        """
        device = self.find_device(udid)
        if device is None:
            udid_str = f" (UDID: {udid})" if udid else ""
            raise DeviceNotFoundError(f"未找到 iOS 设备{udid_str}")
        return device

    def close(self) -> None:
        """关闭客户端连接（仅当我们自己创建时）。"""
        if self._owns_client and self._client:
            self._client.disconnect()
            self._client = None

    def __enter__(self):
        """上下文管理器入口。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.close()
        return False

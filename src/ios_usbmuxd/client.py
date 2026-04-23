"""
usbmuxd socket 客户端实现。

管理与 usbmuxd 守护进程的连接，提供设备枚举功能。

支持的平台:
- Windows: TCP socket 127.0.0.1:27015
- macOS/Linux: Unix 域套接字 /var/run/usbmuxd
"""

import socket
import select
import struct
import time
import platform
from typing import Optional, List, Tuple, Dict, Any, Union

from .protocol import (
    UsbmuxdProtocol,
    MessageType,
    ResultCode,
    HEADER_SIZE,
)
from .exceptions import (
    ConnectionError,
    ConnectionClosedError,
    InsufficientDataError,
    DeviceConnectError,
)
from .device import DeviceInfo


# Unix 套接字路径 (macOS/Linux)
UNIX_SOCKET_PATH = "/var/run/usbmuxd"

# TCP 默认值 (Windows)
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 27015


def get_default_socket_path() -> Union[str, Tuple[str, int]]:
    """
    根据平台获取默认的套接字路径或地址。

    返回:
        macOS/Linux: Unix 套接字路径字符串
        Windows: (主机, 端口) 元组
    """
    system = platform.system()
    if system == "Darwin":  # macOS
        return UNIX_SOCKET_PATH
    elif system == "Linux":
        return UNIX_SOCKET_PATH
    else:  # Windows 或其他
        return (DEFAULT_TCP_HOST, DEFAULT_TCP_PORT)


class UsbmuxdClient:
    """
    与 usbmuxd 守护进程通信的客户端。

    在 Windows 上，usbmuxd 随 iTunes 安装，监听 127.0.0.1:27015。
    在 macOS/Linux 上，使用 Unix 域套接字 /var/run/usbmuxd。
    """

    def __init__(
        self,
        address: Optional[Union[str, Tuple[str, int]]] = None,
        timeout: float = 5.0,
    ):
        """
        初始化 usbmuxd 客户端。

        参数:
            address: 套接字地址。
                     - Windows: (主机, 端口) 元组，如 ("127.0.0.1", 27015)
                     - macOS/Linux: Unix 套接字路径字符串，如 "/var/run/usbmuxd"
                     - 如果为 None，使用平台默认值（自动检测）
            timeout: 套接字超时时间（秒）
        """
        if address is None:
            address = get_default_socket_path()

        self.address = address
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self._tag_counter = 0
        self._recv_buffer = b""
        self._is_unix_socket = isinstance(address, str)

    @property
    def host(self) -> str:
        """获取 TCP 套接字主机（兼容性）。"""
        if self._is_unix_socket:
            return self.address if isinstance(self.address, str) else ""
        return self.address[0] if isinstance(self.address, tuple) else ""

    @property
    def port(self) -> int:
        """获取 TCP 套接字端口（兼容性）。"""
        if self._is_unix_socket:
            return 0
        return self.address[1] if isinstance(self.address, tuple) else 0

    def connect(self) -> None:
        """
        建立与 usbmuxd 守护进程的连接。

        异常:
            ConnectionError: 连接失败
        """
        try:
            if self._is_unix_socket:
                # Unix 域套接字 (macOS/Linux)
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            else:
                # TCP 套接字 (Windows)
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            self.socket.settimeout(self.timeout)

            if self._is_unix_socket:
                self.socket.connect(self.address)
            else:
                self.socket.connect(self.address)
        except socket.error as e:
            addr = self.address if isinstance(self.address, str) else f"{self.address[0]}:{self.address[1]}"
            raise ConnectionError(f"连接 usbmuxd 失败 ({addr}): {e}")

    def disconnect(self) -> None:
        """关闭与 usbmuxd 守护进程的连接。"""
        if self.socket:
            try:
                self.socket.close()
            except socket.error:
                pass
            self.socket = None

    def _next_tag(self) -> int:
        """生成唯一的请求标签，用于匹配请求和响应。"""
        self._tag_counter += 1
        return self._tag_counter

    def send_message(
        self,
        message_type: int,
        payload: bytes = b"",
        tag: Optional[int] = None,
    ) -> int:
        """
        向 usbmuxd 守护进程发送消息。

        参数:
            message_type: 消息类型 (MessageType.*)
            payload: 二进制载荷
            tag: 可选的标签（如果未提供则自动生成）

        返回:
            此消息使用的标签

        异常:
            ConnectionError: 套接字未连接
        """
        if not self.socket:
            raise ConnectionError("未连接到 usbmuxd 守护进程")

        if tag is None:
            tag = self._next_tag()

        data = UsbmuxdProtocol.pack_message(message_type, tag, payload)
        self.socket.sendall(data)
        return tag

    def send_connect(self, device_id: int, port: int) -> int:
        """
        发送 CONNECT 请求以创建设备隧道。

        发送 CONNECT 后，套接字变为设备的隧道。
        此后不能再在此套接字上发送协议消息。

        参数:
            device_id: 枚举获得的设备 ID
            port: 要连接的设备上的 TCP 端口

        返回:
            此消息使用的标签

        异常:
            ConnectionError: 未连接
        """
        payload = UsbmuxdProtocol.build_connect_payload(device_id, port)
        return self.send_message(MessageType.CONNECT, payload)

    def send_connect_plist(self, device_id: int, port: int) -> int:
        """
        使用 plist 协议发送 Connect 请求。

        Apple 自带的 usbmuxd 在现代 macOS/iOS 环境下会对二进制 CONNECT
        返回 plist 结果，因此这里直接使用 plist 版本的 Connect 消息以兼容
        Apple 守护进程和 libusbmuxd。

        参数:
            device_id: 枚举获得的设备 ID
            port: 要连接的设备上的 TCP 端口

        返回:
            此消息使用的标签
        """
        payload = {
            "ClientVersionString": "ios-usb-automation 0.1.0",
            "DeviceID": device_id,
            "MessageType": "Connect",
            "PortNumber": socket.htons(port),
            "ProgName": "ios-usb-automation",
            "kLibUSBMuxVersion": 3,
        }
        return self.send_plist(payload)

    def send_listen(self) -> int:
        """
        发送 LISTEN 请求以开始接收设备通知。

        返回:
            此消息使用的标签
        """
        return self.send_message(MessageType.LISTEN)

    def send_plist(self, data: Dict) -> int:
        """
        发送 PLIST 消息。

        参数:
            data: 要作为 plist 发送的字典

        返回:
            此消息使用的标签
        """
        payload = UsbmuxdProtocol.build_plist_payload(data)
        return self.send_message(MessageType.PLIST, payload)

    def _recv_exactly(self, num_bytes: int) -> bytes:
        """
        从套接字接收指定字节数的数据。

        参数:
            num_bytes: 要接收的字节数

        返回:
            接收到的字节数据

        异常:
            ConnectionClosedError: 连接关闭
            InsufficientDataError: 数据不足
        """
        while len(self._recv_buffer) < num_bytes:
            try:
                chunk = self.socket.recv(4096)
            except socket.timeout:
                raise InsufficientDataError(f"等待 {num_bytes} 字节超时")
            if not chunk:
                raise ConnectionClosedError("连接被对方关闭")
            self._recv_buffer += chunk

        result = self._recv_buffer[:num_bytes]
        self._recv_buffer = self._recv_buffer[num_bytes:]
        return result

    def recv_message(
        self,
        timeout: Optional[float] = None,
    ) -> Tuple[int, int, int, bytes]:
        """
        从 usbmuxd 接收完整消息。

        参数:
            timeout: 可选的超时覆盖

        返回:
            元组 (message_type, tag, result_code, payload)
            - PLIST 消息: result_code 为 0，payload 为 plist 数据
            - CONNECT 响应: result_code 包含 ResultCode.*

        异常:
            ConnectionClosedError: 连接关闭
            InsufficientDataError: 数据不足
        """
        if timeout is not None:
            self.socket.settimeout(timeout)

        # 读取头部
        header_data = self._recv_exactly(HEADER_SIZE)
        length, version, message_type, tag = UsbmuxdProtocol.unpack_header(header_data)

        # 读取载荷
        payload_length = length - HEADER_SIZE
        payload = self._recv_exactly(payload_length) if payload_length > 0 else b""

        # 对于非 PLIST 消息，载荷的前 4 个字节是结果码
        result_code = 0
        if message_type != MessageType.PLIST and payload_length >= 4:
            result_code = struct.unpack("<I", payload[:4])[0]
            payload = payload[4:]

        return message_type, tag, result_code, payload

    def recv_response(
        self,
        expected_tag: int,
        timeout: Optional[float] = None,
    ) -> Tuple[int, int, bytes]:
        """
        接收特定标签的响应。

        参数:
            expected_tag: 要等待的标签
            timeout: 可选的超时覆盖

        返回:
            元组 (message_type, result_code, payload)

        异常:
            TimeoutError: 超时
            ConnectionClosedError: 连接关闭
        """
        import socket as sock_module

        deadline = None
        if timeout is not None:
            import time
            deadline = time.time() + timeout

        while True:
            remaining = None
            if deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise TimeoutError(f"等待标签 {expected_tag} 超时")

            try:
                msg_type, tag, result, payload = self.recv_message(timeout=remaining)
            except socket.timeout:
                raise TimeoutError(f"等待标签 {expected_tag} 超时")

            if tag == expected_tag:
                return msg_type, result, payload

            # 对于 LISTEN，会收到不同标签的 DEVICE_ADD/REMOVE 事件
            # 目前忽略这些异步事件，继续等待
            if msg_type in (MessageType.DEVICE_ADD, MessageType.DEVICE_REMOVE, MessageType.DEVICE_PAIRED):
                continue

    def enumerate_devices(self) -> List[DeviceInfo]:
        """
        枚举所有已连接的 iOS 设备。

        返回:
            DeviceInfo 对象列表

        异常:
            ConnectionError: 未连接或枚举失败
        """
        if not self.socket:
            raise ConnectionError("未连接到 usbmuxd 守护进程")

        devices: List[DeviceInfo] = []

        tag = self.send_plist({"MessageType": "ListDevices"})

        try:
            msg_type, result, payload = self.recv_response(tag, timeout=3.0)

            if msg_type == MessageType.PLIST:
                device_list = UsbmuxdProtocol.parse_plist_payload(payload)
                if "DeviceList" in device_list:
                    for dev_dict in device_list["DeviceList"]:
                        devices.append(self._parse_device_record(dev_dict))
        except TimeoutError:
            pass

        return devices

    def _parse_device_record(self, data: Dict[str, Any]) -> DeviceInfo:
        """
        从字典解析设备记录。

        ListDevices 返回格式: {DeviceID, Properties: {SerialNumber, ProductID, LocationID, ConnectionType}}
        DEVICE_ADD 返回格式: {DeviceID, ProductID, SerialNumber, LocationID, ConnectionType}

        参数:
            data: 来自 plist 的设备信息字典

        返回:
            DeviceInfo 对象
        """
        props = data.get("Properties", data)
        return DeviceInfo(
            device_id=data.get("DeviceID", 0),
            udid=props.get("SerialNumber", ""),
            product_id=props.get("ProductID", 0),
            location_id=props.get("LocationID", 0),
            serial_number=props.get("SerialNumber", ""),
            connection_type=props.get("ConnectionType", "USB"),
        )

    def connect_to_device(self, device: DeviceInfo, port: int = 8100) -> None:
        """
        连接到设备上的指定端口。

        此调用后，self.socket 成为设备的隧道。
        不能再发送协议消息。

        参数:
            device: 枚举获得的 DeviceInfo
            port: 设备上的 TCP 端口

        异常:
            DeviceConnectError: 连接失败
        """
        if not self.socket:
            raise ConnectionError("未连接到 usbmuxd 守护进程")

        tag = self.send_connect_plist(device.device_id, port)
        msg_type, result, payload = self.recv_response(tag, timeout=10.0)

        if msg_type == MessageType.PLIST:
            response = UsbmuxdProtocol.parse_plist_payload(payload)
            result = response.get("Number", ResultCode.OK)
        if result != ResultCode.OK:
            raise DeviceConnectError(f"CONNECT 失败，结果码: {result}")

        # 现在 self.socket 是设备的隧道
        # 清除接收缓冲区，因为现在进入原始 TCP 模式
        self._recv_buffer = b""

    def __enter__(self):
        """上下文管理器入口。"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.disconnect()
        return False

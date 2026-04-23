"""
usbmuxd 二进制协议实现。

Apple 的 usbmuxd 协议，用于通过 USB 与 iOS 设备通信。
纯 Python 实现，不依赖任何 C 扩展。
"""

import struct
from typing import Tuple, Optional, Dict, Any
import plistlib


# 协议常量
HEADER_FORMAT = "<IIII"  # 小端序: length, version, message, tag
HEADER_SIZE = 16


class MessageType:
    """usbmuxd 消息类型。"""
    RESULT = 1         # 操作结果响应
    CONNECT = 2        # 连接请求
    LISTEN = 3         # 监听设备变化
    DEVICE_ADD = 4     # 设备连接通知
    DEVICE_REMOVE = 5  # 设备断开通知
    DEVICE_PAIRED = 6  # 设备配对通知
    PLIST = 8          # PLIST 格式消息


class ResultCode:
    """usbmuxd 操作结果码。"""
    OK = 0           # 成功
    BADCOMMAND = 1   # 无效命令
    BADDEV = 2       # 设备无效
    CONNREFUSED = 3  # 连接被拒绝
    BADVERSION = 6   # 协议版本不匹配


class UsbmuxdProtocol:
    """纯 Python 实现的 usbmuxd 二进制协议。"""

    @staticmethod
    def pack_message(message_type: int, tag: int, payload: bytes = b"") -> bytes:
        """
        将消息打包为 usbmuxd 协议格式。

        Args:
            message_type: 消息类型 (MessageType.*)
            tag: 请求标签，用于匹配请求和响应
            payload: 二进制数据载荷

        Returns:
            完整的消息字节数据 (头部 + 载荷)
        """
        length = HEADER_SIZE + len(payload)
        version = 1
        header = struct.pack(HEADER_FORMAT, length, version, message_type, tag)
        return header + payload

    @staticmethod
    def unpack_header(data: bytes) -> Tuple[int, int, int, int]:
        """
        从原始字节数据解析消息头部。

        Args:
            data: 至少 16 字节的原始数据

        Returns:
            元组 (length, version, message_type, tag)

        Raises:
            ValueError: 如果数据少于 16 字节
        """
        if len(data) < HEADER_SIZE:
            raise ValueError(f"头部需要 {HEADER_SIZE} 字节，实际收到 {len(data)} 字节")
        return struct.unpack(HEADER_FORMAT, data[:HEADER_SIZE])

    @staticmethod
    def unpack_device_info(payload: bytes) -> Dict[str, Any]:
        """
        从 PLIST 载荷中解析设备信息。

        Args:
            payload: 二进制 PLIST 数据

        Returns:
            包含设备信息的字典
        """
        return plistlib.loads(payload)

    @staticmethod
    def build_plist_payload(dict_data: Dict) -> bytes:
        """
        将字典构建为 PLIST 载荷。

        Args:
            dict_data: 要编码的字典数据

        Returns:
            二进制 PLIST 数据
        """
        return plistlib.dumps(dict_data)

    @staticmethod
    def parse_plist_payload(payload: bytes) -> Dict:
        """
        解析 PLIST 载荷为字典。

        Args:
            payload: 二进制 PLIST 数据

        Returns:
            解析后的字典
        """
        if not payload:
            return {}
        return plistlib.loads(payload)

    @staticmethod
    def build_connect_payload(device_id: int, port: int) -> bytes:
        """
        构建 CONNECT 请求载荷。

        usbmuxd 协议要求 device_id 使用小端序，
        port 使用网络字节序（大端序）+ 2 字节保留（置0）。

        Args:
            device_id: 枚举获得的设备 ID
            port: 设备上的 TCP 端口

        Returns:
            8 字节载荷 (device_id: uint32 LE + port: uint16 BE + reserved: uint16 BE)
        """
        return struct.pack("<I", device_id) + struct.pack(">HH", port, 0)

    @staticmethod
    def parse_connect_response(payload: bytes) -> int:
        """
        解析 CONNECT 响应。

        Args:
            payload: 响应载荷

        Returns:
            结果码 (ResultCode.*)
        """
        if len(payload) >= 4:
            return struct.unpack("<I", payload[:4])[0]
        return ResultCode.CONNREFUSED

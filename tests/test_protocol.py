"""
ios_usbmuxd 包的单元测试。
"""

import pytest
import struct
from ios_usbmuxd.protocol import (
    UsbmuxdProtocol,
    MessageType,
    ResultCode,
    HEADER_SIZE,
)
from ios_usbmuxd.exceptions import (
    UsbmuxdError,
    ProtocolError,
    ConnectionError,
)


class TestProtocol:
    """usbmuxd 协议实现测试。"""

    def test_header_size(self):
        """头部应为 16 字节。"""
        assert HEADER_SIZE == 16

    def test_pack_message_empty(self):
        """打包空载荷的消息。"""
        data = UsbmuxdProtocol.pack_message(MessageType.CONNECT, 1, b"")
        assert len(data) == HEADER_SIZE
        length, version, msg_type, tag = struct.unpack("<IIII", data)
        assert length == HEADER_SIZE
        assert version == 1
        assert msg_type == MessageType.CONNECT
        assert tag == 1

    def test_pack_message_with_payload(self):
        """打包带载荷的消息。"""
        payload = b"\x01\x02\x03\x04"
        data = UsbmuxdProtocol.pack_message(MessageType.CONNECT, 42, payload)
        assert len(data) == HEADER_SIZE + 4
        length, version, msg_type, tag = struct.unpack("<IIII", data[:HEADER_SIZE])
        assert length == HEADER_SIZE + 4
        assert msg_type == MessageType.CONNECT
        assert tag == 42

    def test_unpack_header(self):
        """从数据解析头部。"""
        original_data = struct.pack("<IIII", 16, 1, MessageType.CONNECT, 123)
        length, version, msg_type, tag = UsbmuxdProtocol.unpack_header(original_data)
        assert length == 16
        assert version == 1
        assert msg_type == MessageType.CONNECT
        assert tag == 123

    def test_unpack_header_insufficient_data(self):
        """数据不足时解析头部应抛出错误。"""
        with pytest.raises(ValueError):
            UsbmuxdProtocol.unpack_header(b"short")

    def test_build_connect_payload(self):
        """构建 CONNECT 载荷。"""
        payload = UsbmuxdProtocol.build_connect_payload(5, 8100)
        assert len(payload) == 8
        device_id, port = struct.unpack("<II", payload)
        assert device_id == 5
        assert port == 8100

    def test_parse_connect_response(self):
        """解析 CONNECT 响应。"""
        payload = struct.pack("<I", ResultCode.OK)
        result = UsbmuxdProtocol.parse_connect_response(payload)
        assert result == ResultCode.OK

    def test_parse_connect_response_error(self):
        """解析 CONNECT 错误响应。"""
        payload = struct.pack("<I", ResultCode.CONNREFUSED)
        result = UsbmuxdProtocol.parse_connect_response(payload)
        assert result == ResultCode.CONNREFUSED


class TestExceptions:
    """异常层次结构测试。"""

    def test_usbmuxd_error_base(self):
        """UsbmuxdError 是基类异常。"""
        with pytest.raises(UsbmuxdError):
            raise UsbmuxdError("test")

    def test_protocol_error(self):
        """ProtocolError 继承自 UsbmuxdError。"""
        with pytest.raises(UsbmuxdError):
            raise ProtocolError("test")

    def test_connection_error(self):
        """ConnectionError 继承自 UsbmuxdError。"""
        with pytest.raises(UsbmuxdError):
            raise ConnectionError("test")


class TestDeviceInfo:
    """DeviceInfo 数据类测试。"""

    def test_device_info_creation(self):
        """创建 DeviceInfo。"""
        from ios_usbmuxd.device import DeviceInfo

        device = DeviceInfo(
            device_id=5,
            udid="1234567890ABCDEF" * 2 + "1234",  # 38 字符
            product_id=0x12,
        )
        assert device.device_id == 5
        assert device.is_usb
        assert not device.is_network

    def test_device_info_str(self):
        """DeviceInfo 字符串表示。"""
        from ios_usbmuxd.device import DeviceInfo

        device = DeviceInfo(
            device_id=1,
            udid="00001234-56789ABCDEF",
            connection_type="USB",
        )
        s = str(device)
        assert "00001234" in s
        assert "USB" in s


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

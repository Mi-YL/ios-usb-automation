"""
WebDriverAgent (WDA) HTTP API 客户端，支持 usbmuxd 隧道。

本模块提供两种连接模式的 WDA 客户端：
1. 直连网络模式（传统 Appium 方式）
2. 通过 usbmuxd 隧道的 USB 模式（Windows 兼容方式）
"""

import base64
import time
import threading
from typing import Optional, List, Dict, Any, Tuple

from .tunnel import Tunnel
from .device import DeviceManager, DeviceInfo
from .exceptions import WDAError, SessionError


class WDAClient:
    """
    WebDriverAgent HTTP API 客户端。

    支持两种连接模式：
    - 网络模式：直接连接到 WDA 主机:端口
    - USB 模式：创建到 iOS 设备的 usbmuxd 隧道，然后通过 localhost 连接

    示例（Windows USB 模式）:
        >>> client = WDAClient(udid="00001234-56789ABCDEF", use_usbmuxd=True)
        >>> client.connect()
        >>> screenshot = client.screenshot()
        >>> client.click(100, 200)
        >>> client.terminate_session()

    示例（网络模式）:
        >>> client = WDAClient(host="192.168.1.100", port=8100)
        >>> client.connect()
        >>> # ...
    """

    DEFAULT_PORT = 8100

    def __init__(
        self,
        host: str = "localhost",
        port: int = DEFAULT_PORT,
        udid: Optional[str] = None,
        use_usbmuxd: bool = False,
        usbmuxd_host: str = "127.0.0.1",
        usbmuxd_port: int = 27015,
        timeout: float = 30.0,
    ):
        """
        初始化 WDA 客户端。

        参数:
            host: WDA 主机（默认: localhost）
            port: WDA 端口（默认: 8100）
            udid: iOS 设备 UDID（usbmuxd 模式必需）
            use_usbmuxd: 是否使用 usbmuxd 隧道进行 USB 连接
            usbmuxd_host: usbmuxd 守护进程主机（默认: 127.0.0.1）
            usbmuxd_port: usbmuxd 守护进程端口（默认: 27015）
            timeout: HTTP 请求默认超时时间
        """
        self.host = host
        self.port = port
        self.udid = udid
        self.use_usbmuxd = use_usbmuxd
        self.usbmuxd_host = usbmuxd_host
        self.usbmuxd_port = usbmuxd_port
        self.timeout = timeout

        self.session_id: Optional[str] = None
        self._tunnel: Optional[Tunnel] = None
        self._device: Optional[DeviceInfo] = None

        # 延迟导入可选依赖
        self._requests = None

    @property
    def base_url(self) -> str:
        """获取 HTTP 请求的基础 URL。"""
        return f"http://{self.host}:{self.port}"

    @property
    def requests(self):
        """获取 requests 模块（延迟导入）。"""
        if self._requests is None:
            try:
                import requests
                self._requests = requests
            except ImportError:
                raise WDAError(
                    "requests 库未安装。"
                    "请运行: pip install requests"
                )
        return self._requests

    def _start_tunnel(self) -> None:
        """启动到设备的 usbmuxd 隧道。"""
        if self._tunnel is not None:
            return

        self._tunnel = Tunnel(
            local_port=self.port,
            remote_port=self.port,
            udid=self.udid,
            usbmuxd_host=self.usbmuxd_host,
            usbmuxd_port=self.usbmuxd_port,
        )
        self._tunnel.start(timeout=10.0)
        self._device = self._tunnel.device

        # 隧道创建后将主机更新为 localhost
        self.host = "127.0.0.1"

    def _stop_tunnel(self) -> None:
        """停止 usbmuxd 隧道。"""
        if self._tunnel is not None:
            self._tunnel.stop()
            self._tunnel = None

    def connect(self, bundle_id: str = "com.apple.mobilesafari") -> bool:
        """
        连接到 WDA 并创建会话。

        参数:
            bundle_id: 要自动化的应用 Bundle ID（默认: Safari）

        返回:
            连接成功返回 True

        异常:
            WDAError: 连接失败
        """
        try:
            # 如果是 usbmuxd 模式，启动隧道
            if self.use_usbmuxd:
                self._start_tunnel()

            # 健康检查
            response = self.requests.get(
                f"{self.base_url}/status",
                timeout=self.timeout
            )
            if response.status_code != 200:
                return False

            # 创建会话
            session_response = self.requests.post(
                f"{self.base_url}/session",
                json={"desiredCapabilities": {"bundleId": bundle_id}},
                timeout=self.timeout,
            )

            if session_response.status_code in (200, 201):
                data = session_response.json()
                self.session_id = data.get("sessionId")
                return True

            return False

        except Exception as e:
            raise WDAError(f"连接 WDA 失败: {e}")

    def terminate_session(self) -> bool:
        """
        终止当前 WDA 会话。

        返回:
            终止成功返回 True
        """
        if not self.session_id:
            return True

        try:
            response = self.requests.delete(
                f"{self.base_url}/session/{self.session_id}",
                timeout=10
            )
            self.session_id = None
            return response.status_code in (200, 204)
        except Exception:
            self.session_id = None
            return False

    def disconnect(self) -> None:
        """断开客户端连接并清理资源。"""
        self.terminate_session()
        self._stop_tunnel()

    def screenshot(self) -> Optional[bytes]:
        """
        截取屏幕截图。

        返回:
            PNG 图像字节数据，失败返回 None
        """
        try:
            response = self.requests.get(
                f"{self.base_url}/screenshot",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if "value" in data:
                    return base64.b64decode(data["value"])
            return None
        except Exception:
            return None

    def source(self) -> Optional[str]:
        """
        获取页面源代码 XML。

        返回:
            页面源代码 XML 字符串，失败返回 None
        """
        try:
            response = self.requests.get(
                f"{self.base_url}/source",
                timeout=self.timeout
            )
            if response.status_code == 200:
                return response.text
            return None
        except Exception:
            return None

    def click(self, x: int, y: int) -> bool:
        """
        在坐标处点击。

        参数:
            x: X 坐标
            y: Y 坐标

        返回:
            成功返回 True
        """
        try:
            response = self.requests.post(
                f"{self.base_url}/wda/tap/0",
                json={"x": x, "y": y},
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration: float = 0.5,
    ) -> bool:
        """
        从 (x1, y1) 滑动到 (x2, y2)。

        参数:
            x1: 起始 X 坐标
            y1: 起始 Y 坐标
            x2: 结束 X 坐标
            y2: 结束 Y 坐标
            duration: 滑动持续时间（秒）

        返回:
            成功返回 True
        """
        try:
            response = self.requests.post(
                f"{self.base_url}/wda/element/0/perform swipe",
                json={
                    "startX": x1,
                    "startY": y1,
                    "endX": x2,
                    "endY": y2,
                    "duration": duration,
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

    def input_text(self, element_id: str, text: str) -> bool:
        """
        向元素输入文本。

        参数:
            element_id: 元素 ID
            text: 要输入的文本

        返回:
            成功返回 True
        """
        try:
            response = self.requests.post(
                f"{self.base_url}/wda/element/{element_id}/value",
                json={"value": list(text)},
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False

    def find_elements(
        self,
        by: str,
        value: str,
    ) -> List[Dict[str, Any]]:
        """
        通过选择器查找元素。

        参数:
            by: 选择器类型 ("class name", "id", "xpath", "name", "accessibility id")
            value: 选择器值

        返回:
            元素字典列表
        """
        selector_map = {
            "class name": "class name",
            "id": "id",
            "xpath": "xpath",
            "name": "name",
            "accessibility id": "accessibility id",
        }

        mapped_by = selector_map.get(by, by)

        try:
            response = self.requests.post(
                f"{self.base_url}/elements",
                json={"using": mapped_by, "value": value},
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("value", [])
            return []
        except Exception:
            return []

    def find_element(self, by: str, value: str) -> Optional[Dict[str, Any]]:
        """
        查找第一个匹配的元素。

        参数:
            by: 选择器类型
            value: 选择器值

        返回:
            元素字典，未找到返回 None
        """
        elements = self.find_elements(by, value)
        return elements[0] if elements else None

    def get_element_attribute(
        self,
        element_id: str,
        attribute: str,
    ) -> Optional[str]:
        """
        获取元素的属性值。

        参数:
            element_id: 元素 ID
            attribute: 属性名

        返回:
            属性值，未找到返回 None
        """
        try:
            response = self.requests.get(
                f"{self.base_url}/wda/element/{element_id}/attribute/{attribute}",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("value")
            return None
        except Exception:
            return None

    def get_screen_size(self) -> Optional[Dict[str, int]]:
        """
        获取屏幕尺寸。

        返回:
            包含 "width" 和 "height" 键的字典，失败返回 None
        """
        try:
            response = self.requests.get(
                f"{self.base_url}/window/size",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get("value")
            return None
        except Exception:
            return None

    def health_check(self) -> bool:
        """
        检查 WDA 是否响应。

        返回:
            WDA 健康返回 True
        """
        try:
            response = self.requests.get(
                f"{self.base_url}/status",
                timeout=5
            )
            return response.status_code == 200
        except Exception:
            return False

    def __enter__(self):
        """上下文管理器入口。"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.disconnect()
        return False

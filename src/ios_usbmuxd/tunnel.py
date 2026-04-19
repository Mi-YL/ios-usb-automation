"""
基于 usbmuxd 的 TCP 隧道实现。

本模块实现了类似 iproxy 的功能，但使用纯 Python 实现，
允许通过 usbmuxd 将 TCP 端口转发到 iOS 设备。
"""

import socket
import select
import threading
import time
from typing import Optional

from .client import UsbmuxdClient, DeviceInfo
from .exceptions import TunnelError, DeviceConnectError


class TunnelServer:
    """
    TCP 隧道服务器，通过 usbmuxd 将本地 TCP 连接桥接到 iOS 设备。

    类似于 iproxy，但使用纯 Python 实现。在本地 TCP 端口监听，
    并将所有流量转发到 iOS 设备上的指定端口。

    示例:
        >>> from ios_usbmuxd import TunnelServer, DeviceManager
        >>> manager = DeviceManager()
        >>> device = manager.get_device()
        >>> tunnel = TunnelServer(local_port=8100, remote_port=8100)
        >>> tunnel_thread = threading.Thread(target=tunnel.start, args=(device,))
        >>> tunnel_thread.daemon = True
        >>> tunnel_thread.start()
        >>> time.sleep(0.5)  # 等待隧道就绪
        >>> # 现在 localhost:8100 转发到 iOS 设备:8100
    """

    BUFFER_SIZE = 4096

    def __init__(
        self,
        local_port: int = 8100,
        remote_port: int = 8100,
        local_host: str = "127.0.0.1",
    ):
        """
        初始化隧道服务器。

        参数:
            local_port: 本地监听的 TCP 端口
            remote_port: iOS 设备上要连接的远程端口
            local_host: 本地绑定的主机（默认: 127.0.0.1）
        """
        self.local_port = local_port
        self.remote_port = remote_port
        self.local_host = local_host

        self._server_socket: Optional[socket.socket] = None
        self._device_socket: Optional[socket.socket] = None
        self._local_conn: Optional[socket.socket] = None
        self._running = False
        self._lock = threading.Lock()

    def start(self, device: DeviceInfo) -> None:
        """
        为指定设备启动隧道服务器。

        此方法会阻塞，直到调用 stop()。

        参数:
            device: 枚举获得的 DeviceInfo

        异常:
            TunnelError: 隧道创建失败
        """
        with self._lock:
            if self._running:
                return

            # 创建 usbmuxd 客户端并连接设备
            try:
                self._usbmuxd_client = UsbmuxdClient()
                self._usbmuxd_client.connect()
                self._usbmuxd_client.connect_to_device(device, self.remote_port)
                self._device_socket = self._usbmuxd_client.socket
            except (DeviceConnectError, Exception) as e:
                raise TunnelError(f"连接设备失败: {e}")

            # 创建本地监听套接字
            try:
                self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._server_socket.bind((self.local_host, self.local_port))
                self._server_socket.listen(5)
                self._server_socket.settimeout(0.1)
            except socket.error as e:
                self._cleanup()
                raise TunnelError(f"创建本地套接字失败: {e}")

            self._running = True

        # 运行事件循环
        self._run_loop()

    def _run_loop(self) -> None:
        """使用 select() 的主事件循环，实现非阻塞 I/O。"""
        while self._running:
            try:
                self._wait_and_forward()
            except Exception as e:
                if self._running:
                    print(f"隧道错误: {e}")
                    time.sleep(0.1)

    def _wait_and_forward(self) -> None:
        """等待套接字活动并转发数据。"""
        # 构建要监控的套接字列表
        sockets_to_monitor = []
        if self._server_socket:
            sockets_to_monitor.append(self._server_socket)
        if self._device_socket:
            sockets_to_monitor.append(self._device_socket)
        if self._local_conn:
            sockets_to_monitor.append(self._local_conn)

        if not sockets_to_monitor:
            time.sleep(0.01)
            return

        readable, _, exceptional = select.select(
            sockets_to_monitor, [], sockets_to_monitor, 0.5
        )

        for sock in exceptional:
            if sock == self._local_conn:
                self._close_local()
            elif sock == self._device_socket:
                self._cleanup()
                return

        for sock in readable:
            if sock == self._server_socket:
                self._handle_accept()
            elif sock == self._device_socket:
                self._handle_device_data()
            elif sock == self._local_conn:
                self._handle_local_data()

    def _handle_accept(self) -> None:
        """处理新的本地客户端连接。"""
        try:
            local_conn, addr = self._server_socket.accept()
            # 关闭现有的本地连接（如果有）
            if self._local_conn:
                try:
                    self._local_conn.close()
                except socket.error:
                    pass
            self._local_conn = local_conn
        except socket.timeout:
            pass
        except socket.error:
            pass

    def _handle_device_data(self) -> None:
        """将数据从设备转发到本地客户端。"""
        if not self._local_conn:
            return

        try:
            data = self._device_socket.recv(self.BUFFER_SIZE)
            if not data:
                self._cleanup()
                return
            self._local_conn.sendall(data)
        except (socket.timeout, BlockingIOError):
            pass
        except (socket.error, BrokenPipeError, ConnectionResetError):
            self._close_local()

    def _handle_local_data(self) -> None:
        """将数据从本地客户端转发到设备。"""
        if not self._local_conn or not self._device_socket:
            return

        try:
            data = self._local_conn.recv(self.BUFFER_SIZE)
            if not data:
                self._close_local()
                return
            self._device_socket.sendall(data)
        except (socket.timeout, BlockingIOError):
            pass
        except (socket.error, BrokenPipeError, ConnectionResetError):
            self._close_local()

    def _close_local(self) -> None:
        """关闭本地连接。"""
        if self._local_conn:
            try:
                self._local_conn.close()
            except socket.error:
                pass
            self._local_conn = None

    def _cleanup(self) -> None:
        """清理所有资源。"""
        self._running = False

        self._close_local()

        if self._server_socket:
            try:
                self._server_socket.close()
            except socket.error:
                pass
            self._server_socket = None

        if self._device_socket:
            try:
                self._device_socket.close()
            except socket.error:
                pass
            self._device_socket = None

        if self._usbmuxd_client:
            try:
                self._usbmuxd_client.disconnect()
            except socket.error:
                pass
            self._usbmuxd_client = None

    def stop(self) -> None:
        """停止隧道服务器。"""
        with self._lock:
            self._cleanup()

    def is_running(self) -> bool:
        """检查隧道是否正在运行。"""
        return self._running

    def __enter__(self):
        """上下文管理器入口（需要先设置设备）。"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.stop()
        return False


class Tunnel:
    """
    高级隧道封装，自动处理设备连接。

    这是结合了 TunnelServer 和设备枚举的便捷类。
    """

    def __init__(
        self,
        local_port: int = 8100,
        remote_port: int = 8100,
        udid: Optional[str] = None,
        usbmuxd_host: str = "127.0.0.1",
        usbmuxd_port: int = 27015,
    ):
        """
        初始化隧道。

        参数:
            local_port: 本地监听的 TCP 端口
            remote_port: iOS 设备上的远程端口
            udid: 设备 UDID（None 则使用第一个可用设备）
            usbmuxd_host: usbmuxd 守护进程主机
            usbmuxd_port: usbmuxd 守护进程端口
        """
        self.local_port = local_port
        self.remote_port = remote_port
        self.udid = udid
        self.usbmuxd_host = usbmuxd_host
        self.usbmuxd_port = usbmuxd_port

        self._tunnel_server: Optional[TunnelServer] = None
        self._thread: Optional[threading.Thread] = None
        self._device: Optional[DeviceInfo] = None

    def start(self, timeout: float = 10.0) -> bool:
        """
        启动隧道。

        参数:
            timeout: 设备连接超时时间

        返回:
            隧道启动成功返回 True

        异常:
            TunnelError: 隧道创建失败
            DeviceNotFoundError: 未找到设备
        """
        from .device import DeviceManager

        # 查找设备
        client = UsbmuxdClient(host=self.usbmuxd_host, port=self.usbmuxd_port)
        client.connect()

        manager = DeviceManager(client)
        self._device = manager.get_device(self.udid)

        # 创建并启动隧道服务器
        self._tunnel_server = TunnelServer(
            local_port=self.local_port,
            remote_port=self.remote_port,
        )

        # 在线程中启动
        self._thread = threading.Thread(
            target=self._tunnel_server.start,
            args=(self._device,),
            daemon=True,
        )
        self._thread.start()

        # 等待隧道就绪
        time.sleep(0.5)

        if not self._tunnel_server.is_running():
            raise TunnelError("隧道启动失败")

        return True

    def stop(self) -> None:
        """停止隧道。"""
        if self._tunnel_server:
            self._tunnel_server.stop()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._thread = None
        self._tunnel_server = None

    def is_running(self) -> bool:
        """检查隧道是否正在运行。"""
        return self._tunnel_server is not None and self._tunnel_server.is_running()

    @property
    def device(self) -> Optional[DeviceInfo]:
        """获取已连接设备的信息。"""
        return self._device

    def __enter__(self):
        """上下文管理器入口。"""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口。"""
        self.stop()
        return False

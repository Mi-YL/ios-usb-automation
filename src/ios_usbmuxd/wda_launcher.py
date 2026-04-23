"""
WDA 启动器抽象。

将“如何启动 WDA”从客户端 HTTP/USB 通信中拆出来，便于按宿主平台
选择不同策略：

- none: 仅连接已在运行的 WDA
- devicectl: macOS 上启动预装的 WDA Runner
- xcodebuild: macOS 上通过 xcodebuild 启动 XCTest 会话
- command: 跨平台执行自定义命令，例如在 Windows 上通过 ssh 调远端 Mac
"""

import json
import os
import platform
import shlex
import subprocess
import tempfile
import time
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from .exceptions import WDAError

CommandInput = Union[str, Sequence[str]]


class WDALauncher:
    """WDA 启动器基类。"""

    def start(self, client: "Any") -> None:
        """启动 WDA。"""
        raise NotImplementedError

    def stop(self) -> None:
        """停止由启动器创建的本地进程。"""
        return None


class NoOpWDALauncher(WDALauncher):
    """不执行任何启动动作。"""

    def start(self, client: "Any") -> None:
        return None


class CommandWDALauncher(WDALauncher):
    """
    执行自定义命令来启动 WDA。

    适用于：
    - Windows 上调用第三方工具
    - 通过 ssh 调远端 Mac 启动 WDA
    - 本地脚本封装任意启动流程
    """

    def __init__(
        self,
        command: CommandInput,
        shell: bool = False,
        cwd: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
        background: bool = False,
        startup_grace_period: float = 1.0,
    ):
        self.command = command
        self.shell = shell
        self.cwd = cwd
        self.env = dict(env or {})
        self.background = background
        self.startup_grace_period = startup_grace_period

        self._process: Optional[subprocess.Popen] = None
        self._log_file = None

    def _context(self, client: "Any") -> Dict[str, str]:
        return {
            "udid": client.udid or "",
            "host": client.host or "",
            "port": str(client.port),
            "base_url": client.base_url,
        }

    def _format_value(self, value: Optional[str], client: "Any") -> Optional[str]:
        if value is None:
            return None
        return value.format_map(_SafeFormatDict(self._context(client)))

    def _format_env(self, client: "Any") -> Dict[str, str]:
        return {
            key: self._format_value(value, client) or ""
            for key, value in self.env.items()
        }

    def build_command(self, client: "Any") -> CommandInput:
        context = _SafeFormatDict(self._context(client))

        if isinstance(self.command, str):
            formatted = self.command.format_map(context)
            if self.shell:
                return formatted
            return shlex.split(formatted, posix=os.name != "nt")

        return [part.format_map(context) for part in self.command]

    def _normalized_command(self, client: "Any") -> CommandInput:
        command = self.build_command(client)
        if self.shell and not isinstance(command, str):
            if os.name == "nt":
                return subprocess.list2cmdline(list(command))
            return " ".join(shlex.quote(part) for part in command)
        return command

    def start(self, client: "Any") -> None:
        if self._process and self._process.poll() is None:
            return

        command = self._normalized_command(client)
        env = os.environ.copy()
        env.update(self._format_env(client))
        cwd = self._format_value(self.cwd, client)

        if self.background:
            self._log_file = tempfile.TemporaryFile(mode="w+t")
            self._process = subprocess.Popen(
                command,
                shell=self.shell,
                cwd=cwd,
                env=env,
                stdout=self._log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if self.startup_grace_period > 0:
                time.sleep(self.startup_grace_period)
            if self._process.poll() not in (None, 0):
                raise WDAError(
                    "启动 WDA 的自定义命令失败: "
                    f"{self._read_log().strip() or '命令已退出'}"
                )
            return

        try:
            subprocess.run(
                command,
                shell=self.shell,
                cwd=cwd,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            output = e.stderr or e.stdout or str(e)
            raise WDAError(f"启动 WDA 的自定义命令失败: {output.strip()}") from e

    def _read_log(self) -> str:
        if not self._log_file:
            return ""
        self._log_file.seek(0)
        return self._log_file.read()

    def stop(self) -> None:
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5.0)
        self._process = None
        if self._log_file:
            self._log_file.close()
            self._log_file = None


class DevicectlWDALauncher(WDALauncher):
    """
    使用 `xcrun devicectl device process launch` 启动预装的 WDA。

    仅适用于 macOS 上已经安装好的 WebDriverAgentRunner-Runner。
    """

    def __init__(
        self,
        bundle_id: str,
        device_identifier: Optional[str] = None,
        environment: Optional[Mapping[str, str]] = None,
        activate: bool = True,
        terminate_existing: bool = True,
        timeout: float = 30.0,
    ):
        self.bundle_id = bundle_id
        self.device_identifier = device_identifier
        self.environment = dict(environment or {})
        self.activate = activate
        self.terminate_existing = terminate_existing
        self.timeout = timeout

    def start(self, client: "Any") -> None:
        _require_macos("devicectl")

        device_identifier = self.device_identifier or client.udid
        if not device_identifier:
            raise WDAError("devicectl 启动 WDA 需要设备标识或 UDID")

        context = _SafeFormatDict(
            {
                "udid": client.udid or "",
                "host": client.host or "",
                "port": str(client.port),
                "base_url": client.base_url,
            }
        )
        command = [
            "xcrun",
            "devicectl",
            "device",
            "process",
            "launch",
            "--device",
            device_identifier,
        ]
        if self.environment:
            env_json = json.dumps(
                {
                    key: value.format_map(context)
                    for key, value in self.environment.items()
                }
            )
            command.extend(["--environment-variables", env_json])
        if self.terminate_existing:
            command.append("--terminate-existing")
        command.append("--activate" if self.activate else "--no-activate")
        command.append(self.bundle_id.format_map(context))

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.CalledProcessError as e:
            output = e.stderr or e.stdout or str(e)
            raise WDAError(f"devicectl 启动 WDA 失败: {output.strip()}") from e


class XcodebuildWDALauncher(CommandWDALauncher):
    """
    使用 xcodebuild 启动 WDA。

    支持两种模式：
    - 传入 xctestrun_path，只执行 test-without-building
    - 传入 project_path/workspace_path + scheme，执行 build-for-testing + test-without-building
    """

    def __init__(
        self,
        xctestrun_path: Optional[str] = None,
        project_path: Optional[str] = None,
        workspace_path: Optional[str] = None,
        scheme: str = "WebDriverAgentRunner",
        device_identifier: Optional[str] = None,
        destination: Optional[str] = None,
        derived_data_path: Optional[str] = None,
        configuration: Optional[str] = None,
        extra_args: Optional[Sequence[str]] = None,
        cwd: Optional[str] = None,
        env: Optional[Mapping[str, str]] = None,
        startup_grace_period: float = 2.0,
    ):
        super().__init__(
            command=[],
            shell=False,
            cwd=cwd,
            env=env,
            background=True,
            startup_grace_period=startup_grace_period,
        )
        self.xctestrun_path = xctestrun_path
        self.project_path = project_path
        self.workspace_path = workspace_path
        self.scheme = scheme
        self.device_identifier = device_identifier
        self.destination = destination
        self.derived_data_path = derived_data_path
        self.configuration = configuration
        self.extra_args = list(extra_args or [])

    def build_command(self, client: "Any") -> CommandInput:
        _require_macos("xcodebuild")

        context = _SafeFormatDict(self._context(client))
        destination = self.destination
        if not destination:
            device_identifier = self.device_identifier or client.udid
            if not device_identifier:
                raise WDAError("xcodebuild 启动 WDA 需要设备标识、destination 或 UDID")
            destination = f"id={device_identifier}"

        command = ["xcodebuild"]
        if self.xctestrun_path:
            command.extend(
                [
                    "test-without-building",
                    "-xctestrun",
                    self.xctestrun_path.format_map(context),
                ]
            )
        else:
            if not (self.project_path or self.workspace_path):
                raise WDAError(
                    "xcodebuild 启动 WDA 需要 xctestrun_path，或 project_path/workspace_path"
                )
            command.extend(["build-for-testing", "test-without-building"])
            if self.project_path:
                command.extend(["-project", self.project_path.format_map(context)])
            else:
                command.extend(["-workspace", self.workspace_path.format_map(context)])
            command.extend(["-scheme", self.scheme.format_map(context)])
            if self.derived_data_path:
                command.extend(
                    ["-derivedDataPath", self.derived_data_path.format_map(context)]
                )

        command.extend(["-destination", destination.format_map(context)])
        if self.configuration:
            command.extend(["-configuration", self.configuration.format_map(context)])
        command.extend([arg.format_map(context) for arg in self.extra_args])
        return command


def create_wda_launcher(strategy: str, **kwargs: Any) -> WDALauncher:
    """
    根据策略名称创建启动器。

    支持的策略：
    - none
    - command
    - devicectl
    - xcodebuild
    """
    normalized = strategy.strip().lower()
    if normalized == "none":
        return NoOpWDALauncher()
    if normalized == "command":
        return CommandWDALauncher(**kwargs)
    if normalized == "devicectl":
        return DevicectlWDALauncher(**kwargs)
    if normalized == "xcodebuild":
        return XcodebuildWDALauncher(**kwargs)
    raise ValueError(f"不支持的 WDA 启动策略: {strategy}")


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _require_macos(tool_name: str) -> None:
    if platform.system() != "Darwin":
        raise WDAError(f"{tool_name} 启动策略仅支持 macOS")

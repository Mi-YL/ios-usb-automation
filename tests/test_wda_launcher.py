from types import SimpleNamespace

import pytest

from ios_usbmuxd.exceptions import WDAError
from ios_usbmuxd.wda_launcher import (
    CommandWDALauncher,
    DevicectlWDALauncher,
    XcodebuildWDALauncher,
    create_wda_launcher,
)


def make_client():
    return SimpleNamespace(
        udid="00008030-001945042E92402E",
        host="127.0.0.1",
        port=8100,
        base_url="http://127.0.0.1:8100",
    )


def test_command_launcher_formats_placeholders():
    launcher = CommandWDALauncher(
        ["ssh", "mac", "start-wda", "{udid}", "{port}"]
    )

    command = launcher.build_command(make_client())

    assert command == [
        "ssh",
        "mac",
        "start-wda",
        "00008030-001945042E92402E",
        "8100",
    ]


def test_devicectl_launcher_builds_launch_command(monkeypatch):
    captured = {}

    def fake_run(command, check, capture_output, text, timeout):
        captured["command"] = command
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        "ios_usbmuxd.wda_launcher.platform.system", lambda: "Darwin"
    )
    monkeypatch.setattr("ios_usbmuxd.wda_launcher.subprocess.run", fake_run)

    launcher = DevicectlWDALauncher(
        bundle_id="com.example.WebDriverAgentRunner.xctrunner",
        terminate_existing=False,
    )
    launcher.start(make_client())

    assert captured["command"] == [
        "xcrun",
        "devicectl",
        "device",
        "process",
        "launch",
        "--device",
        "00008030-001945042E92402E",
        "--activate",
        "com.example.WebDriverAgentRunner.xctrunner",
    ]


def test_devicectl_launcher_rejects_non_macos(monkeypatch):
    monkeypatch.setattr(
        "ios_usbmuxd.wda_launcher.platform.system", lambda: "Windows"
    )

    launcher = DevicectlWDALauncher(
        bundle_id="com.example.WebDriverAgentRunner.xctrunner",
    )

    with pytest.raises(WDAError):
        launcher.start(make_client())


def test_xcodebuild_launcher_uses_xctestrun_file(monkeypatch):
    monkeypatch.setattr(
        "ios_usbmuxd.wda_launcher.platform.system", lambda: "Darwin"
    )

    launcher = XcodebuildWDALauncher(
        xctestrun_path="/tmp/WDA.xctestrun",
    )
    command = launcher.build_command(make_client())

    assert command == [
        "xcodebuild",
        "test-without-building",
        "-xctestrun",
        "/tmp/WDA.xctestrun",
        "-destination",
        "id=00008030-001945042E92402E",
    ]


def test_xcodebuild_launcher_can_build_and_run(monkeypatch):
    monkeypatch.setattr(
        "ios_usbmuxd.wda_launcher.platform.system", lambda: "Darwin"
    )

    launcher = XcodebuildWDALauncher(
        project_path="/tmp/WebDriverAgent.xcodeproj",
        derived_data_path="/tmp/wda_build",
        extra_args=["CODE_SIGNING_ALLOWED=NO"],
    )
    command = launcher.build_command(make_client())

    assert command == [
        "xcodebuild",
        "build-for-testing",
        "test-without-building",
        "-project",
        "/tmp/WebDriverAgent.xcodeproj",
        "-scheme",
        "WebDriverAgentRunner",
        "-derivedDataPath",
        "/tmp/wda_build",
        "-destination",
        "id=00008030-001945042E92402E",
        "CODE_SIGNING_ALLOWED=NO",
    ]


def test_create_wda_launcher_factory():
    assert create_wda_launcher("none").__class__.__name__ == "NoOpWDALauncher"
    assert (
        create_wda_launcher("command", command=["echo", "ok"]).__class__.__name__
        == "CommandWDALauncher"
    )

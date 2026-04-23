import socket

import pytest

from ios_usbmuxd.client import UsbmuxdClient
from ios_usbmuxd.device import DeviceInfo
from ios_usbmuxd.exceptions import DeviceConnectError
from ios_usbmuxd.protocol import MessageType, ResultCode, UsbmuxdProtocol
from ios_usbmuxd.wda_client import WDAClient
from ios_usbmuxd.wda_launcher import NoOpWDALauncher


def test_send_connect_plist_uses_plist_protocol():
    client = UsbmuxdClient()
    captured = {}

    def fake_send_plist(payload):
        captured.update(payload)
        return 7

    client.send_plist = fake_send_plist

    tag = client.send_connect_plist(5, 8100)

    assert tag == 7
    assert captured["MessageType"] == "Connect"
    assert captured["DeviceID"] == 5
    assert captured["PortNumber"] == socket.htons(8100)
    assert captured["ProgName"] == "ios-usb-automation"
    assert captured["kLibUSBMuxVersion"] == 3


def test_connect_to_device_parses_plist_result():
    client = UsbmuxdClient()
    client.socket = object()
    client._recv_buffer = b"stale"
    client.send_connect_plist = lambda device_id, port: 1
    client.recv_response = lambda tag, timeout=None: (
        MessageType.PLIST,
        0,
        UsbmuxdProtocol.build_plist_payload(
            {"MessageType": "Result", "Number": ResultCode.OK}
        ),
    )

    device = DeviceInfo(device_id=5, udid="00008030-001945042E92402E")
    client.connect_to_device(device, 8100)

    assert client._recv_buffer == b""


def test_connect_to_device_raises_on_plist_error():
    client = UsbmuxdClient()
    client.socket = object()
    client.send_connect_plist = lambda device_id, port: 1
    client.recv_response = lambda tag, timeout=None: (
        MessageType.PLIST,
        0,
        UsbmuxdProtocol.build_plist_payload(
            {"MessageType": "Result", "Number": ResultCode.BADCOMMAND}
        ),
    )

    device = DeviceInfo(device_id=5, udid="00008030-001945042E92402E")

    with pytest.raises(DeviceConnectError):
        client.connect_to_device(device, 8100)


def test_wda_connect_sends_w3c_capabilities():
    class FakeResponse:
        def __init__(self, status_code, data=None):
            self.status_code = status_code
            self._data = data or {}

        def json(self):
            return self._data

    class FakeRequests:
        def __init__(self):
            self.post_payload = None

        def get(self, url, timeout):
            return FakeResponse(200)

        def post(self, url, json, timeout):
            self.post_payload = json
            return FakeResponse(200, {"sessionId": "session-123"})

    fake_requests = FakeRequests()
    client = WDAClient(use_usbmuxd=False)
    client._requests = fake_requests

    assert client.connect(bundle_id="com.apple.mobilesafari") is True
    assert client.session_id == "session-123"
    assert fake_requests.post_payload["capabilities"]["alwaysMatch"] == {
        "bundleId": "com.apple.mobilesafari"
    }
    assert fake_requests.post_payload["desiredCapabilities"] == {
        "bundleId": "com.apple.mobilesafari"
    }


def test_wda_connect_uses_launcher_when_not_ready():
    class FakeLauncher(NoOpWDALauncher):
        def __init__(self):
            self.started = 0

        def start(self, client):
            self.started += 1

    launcher = FakeLauncher()
    client = WDAClient(use_usbmuxd=False, launcher=launcher)
    client.status = lambda: None
    client.wait_until_ready = lambda timeout=30.0, interval=1.0: True

    class FakeResponse:
        def __init__(self, status_code, data=None):
            self.status_code = status_code
            self._data = data or {}

        def json(self):
            return self._data

    class FakeRequests:
        def __init__(self):
            self.post_payload = None

        def post(self, url, json, timeout):
            self.post_payload = json
            return FakeResponse(200, {"sessionId": "session-456"})

    fake_requests = FakeRequests()
    client._requests = fake_requests

    assert client.connect() is True
    assert launcher.started == 1
    assert client.session_id == "session-456"


def test_wda_connect_can_skip_session_creation():
    client = WDAClient(use_usbmuxd=False)
    client.status = lambda: {"value": {"ready": True}}

    assert client.connect(create_session=False) is True
    assert client.session_id is None


def test_wda_connect_allows_attaching_to_foreground_app():
    class FakeResponse:
        def __init__(self, status_code, data=None):
            self.status_code = status_code
            self._data = data or {}

        def json(self):
            return self._data

    class FakeRequests:
        def __init__(self):
            self.post_payload = None

        def get(self, url, timeout):
            return FakeResponse(200)

        def post(self, url, json, timeout):
            self.post_payload = json
            return FakeResponse(200, {"sessionId": "session-foreground"})

    fake_requests = FakeRequests()
    client = WDAClient(use_usbmuxd=False)
    client._requests = fake_requests

    assert client.connect(bundle_id=None) is True
    assert client.session_id == "session-foreground"
    assert fake_requests.post_payload["capabilities"]["alwaysMatch"] == {}
    assert fake_requests.post_payload["desiredCapabilities"] == {}


def test_wda_go_home_uses_homescreen_endpoint():
    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

    class FakeRequests:
        def __init__(self):
            self.calls = []

        def post(self, url, json, timeout):
            self.calls.append((url, json, timeout))
            return FakeResponse(200)

    fake_requests = FakeRequests()
    client = WDAClient(use_usbmuxd=False)
    client._requests = fake_requests

    assert client.go_home() is True
    assert fake_requests.calls == [
        ("http://localhost:8100/wda/homescreen", {}, 10)
    ]


def test_wda_click_uses_session_endpoint():
    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

    class FakeRequests:
        def __init__(self):
            self.calls = []

        def post(self, url, json, timeout):
            self.calls.append((url, json, timeout))
            return FakeResponse(200)

    fake_requests = FakeRequests()
    client = WDAClient(use_usbmuxd=False)
    client._requests = fake_requests
    client.session_id = "session-789"

    assert client.click(120, 240) is True
    assert fake_requests.calls == [
        (
            "http://localhost:8100/session/session-789/wda/tap",
            {"x": 120, "y": 240},
            10,
        )
    ]


def test_wda_swipe_uses_drag_route():
    class FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code

    class FakeRequests:
        def __init__(self):
            self.calls = []

        def post(self, url, json, timeout):
            self.calls.append((url, json, timeout))
            return FakeResponse(200)

    fake_requests = FakeRequests()
    client = WDAClient(use_usbmuxd=False)
    client._requests = fake_requests
    client.session_id = "session-789"

    assert client.swipe(300, 400, 100, 400, duration=0.25) is True
    assert fake_requests.calls == [
        (
            "http://localhost:8100/session/session-789/wda/dragfromtoforduration",
            {
                "fromX": 300,
                "fromY": 400,
                "toX": 100,
                "toY": 400,
                "duration": 0.25,
            },
            10,
        )
    ]

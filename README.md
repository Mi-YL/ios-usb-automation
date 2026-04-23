# iOS USB Automation

[English](./README.md) | 中文

<p align="center">
  <strong>Pure Python usbmuxd client for cross-platform iOS automation</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-green.svg" alt="Platform">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

---

## 项目简介

`ios-usb-automation` 是一个纯 Python 实现的 usbmuxd 协议客户端，支持在 Windows、macOS 和 Linux 上通过 USB 连接 iOS 设备进行 UI 自动化测试。

客户端本身不依赖 Xcode GUI。对于 WDA 启动，本仓库提供可插拔启动策略：

- `none` - 仅连接已在运行的 WDA
- `devicectl` - macOS 上启动预装的 WDA
- `xcodebuild` - macOS 上通过 XCTest 启动 WDA
- `command` - Windows/macOS 上执行自定义命令，例如 ssh 到远端 Mac 启动 WDA

## 功能特性

- ✅ **纯 Python 实现** - 不依赖任何 C 扩展或第三方库
- ✅ **跨平台支持** - Windows、macOS、Linux
- ✅ **usbmuxd 协议** - 完全实现设备枚举和 USB 隧道
- ✅ **WDA 客户端** - 支持截图、点击、滑动、文本输入等操作
- ✅ **纯 Python iproxy** - 无需系统自带工具
- ✅ **WDA 启动策略** - 支持 `none` / `devicectl` / `xcodebuild` / `command`

## 支持的平台

| 平台 | Socket 类型 | 默认地址 |
|------|-------------|----------|
| Windows | TCP | `127.0.0.1:27015` |
| macOS | Unix Domain | `/var/run/usbmuxd` |
| Linux | Unix Domain | `/var/run/usbmuxd` |

## 前置条件

### 通用要求

- Python 3.8+
- iOS 设备通过 USB 连接并已授权信任
- iOS 设备上已安装 WebDriverAgent (WDA)

### Windows

- 安装 [iTunes](https://www.apple.com/itunes/)（含 Apple Mobile Device Support）
- 或仅安装 Apple Mobile Device Support 驱动

### macOS

- 安装 Xcode Command Line Tools
  ```bash
  xcode-select --install
  ```

### Linux

- 安装 libimobiledevice
  ```bash
  # Debian/Ubuntu
  sudo apt install libimobiledevice6

  # Fedora
  sudo dnf install libimobiledevice
  ```

### iOS 设备 - WDA 安装

WDA 必须通过 Mac + Xcode 安装到 iOS 设备上（此操作仅需执行一次）：

1. 在 Mac 上安装 [Appium WebDriverAgent](https://github.com/appium/appium-webdriveragent)
2. 使用 Xcode 将 WDA 安装到你的 iOS 设备
3. 之后 Windows/Linux/macOS 即可独立使用本工具控制设备

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourname/ios-usb-automation.git
cd ios-usb-automation

# 安装依赖（推荐，包含 requests）
pip install -e ".[wda]"

# 或仅安装运行时依赖
pip install -r requirements.txt
```

### 示例代码

#### 1. 枚举设备

```python
from ios_usbmuxd import DeviceManager

with DeviceManager() as manager:
    devices = manager.list_devices()
    for device in devices:
        print(f"{device.udid} ({device.connection_type})")
```

#### 2. UI 自动化

```python
from ios_usbmuxd import WDAClient

# 创建 USB 模式客户端
client = WDAClient(udid="你的设备UDID", use_usbmuxd=True)

# 连接到 WDA
client.connect(bundle_id="com.apple.mobilesafari")  # Safari
# 或指定其他应用
# client.connect(bundle_id="com.apple.mobilesettings")  # 设置

# 截图
screenshot = client.screenshot()
with open("screen.png", "wb") as f:
    f.write(screenshot)

# 获取页面源码
source = client.source()
print(f"页面元素数: {source.count('<')}")

# 点击
client.click(200, 400)

# 滑动
client.swipe(100, 500, 100, 200, duration=0.5)

# 断开连接
client.disconnect()
```

#### 3. 带启动策略的 UI 自动化

```python
from ios_usbmuxd import WDAClient, create_wda_launcher

launcher = create_wda_launcher(
    "devicectl",
    bundle_id="com.appium.WebDriverAgentRunner.xctrunner",
)

client = WDAClient(
    udid="你的设备UDID",
    use_usbmuxd=True,
    launcher=launcher,
)
client.connect(bundle_id="com.apple.mobilesafari")
client.disconnect()
```

#### 4. 手动创建隧道

```python
from ios_usbmuxd import Tunnel

# 创建隧道
tunnel = Tunnel(local_port=8100, remote_port=8100, udid="设备UDID")
tunnel.start()

# 现在 localhost:8100 转发到 iOS:8100
# 可使用任意 HTTP 客户端

tunnel.stop()
```

### 运行示例

```bash
# 枚举设备
python examples/enumerate_devices.py

# 基础自动化
python examples/basic_automation.py

# 带启动策略的自动化
python examples/managed_automation.py

# 手动创建隧道
python examples/tunnel_demo.py
```

## WDA 启动策略

### 跨平台建议

| 宿主平台 | 推荐策略 | 说明 |
|---------|----------|------|
| macOS | `devicectl` | 适合已预装 WDA 的日常启动 |
| macOS | `xcodebuild` | 适合需要稳定拉起 XCTest 会话的场景 |
| Windows | `command` | 适合调用第三方工具或 ssh 到远端 Mac 启动 WDA |
| Windows/macOS | `none` | 适合 WDA 已经在设备上运行 |

### `command` 策略

`command` 是跨平台兜底方案。它允许你在任意宿主机上调用自定义命令启动 WDA，例如：

- Windows 上执行 `ssh mac-mini "xcodebuild ..."`
- macOS 上调用本地 shell 脚本
- 调用内部设备平台或第三方工具

命令支持占位符：

- `{udid}` - 设备 UDID
- `{host}` - 当前 WDA 主机
- `{port}` - 当前 WDA 端口
- `{base_url}` - 当前基础地址

### `devicectl` 策略

适用于 macOS 上已经预装好的 `WebDriverAgentRunner-Runner`。要求：

- Xcode 15+ / `xcrun devicectl`
- 设备已挂载开发者磁盘镜像
- 对于 iOS 17+ 的预装 WDA，通常需要去掉 `Frameworks/XC**` 后再安装，避免直接 launch 时崩溃

### `xcodebuild` 策略

适用于 macOS 本机直接拉起 XCTest：

- 传入 `xctestrun_path` 时，只执行 `test-without-building`
- 传入 `project_path` 时，会执行 `build-for-testing test-without-building`

这是最稳妥的 macOS 本机启动方式，也适合作为 Windows 远端启动的后端实现。

### 重打可被 `devicectl` 启动的预装 WDA

仓库内置了一个重打脚本：

```bash
DEVICE_ID=<你的设备UDID> \
PRODUCT_BUNDLE_ID=com.myl.WebDriverAgentRunner \
scripts/rebuild_preinstalled_wda.sh
```

脚本会执行以下步骤：

1. 使用 `vendor/WebDriverAgent` 执行 `xcodebuild build-for-testing`
2. 定位生成的 `WebDriverAgentRunner-Runner.app`
3. 移除阻塞 `devicectl` 启动的 `Frameworks/XC**`
4. 重新签名 app / xctest bundle
5. 安装到设备并调用 `devicectl` 验证 launch

可选环境变量：

- `TEAM_ID`
- `SIGNING_STYLE=auto|manual`
- `PROVISIONING_PROFILE_UUID`
- `DERIVED_DATA_PATH`
- `VERIFY_LAUNCH=0`

## API 文档

### 核心类

#### `DeviceManager`

设备管理器，用于枚举和选择 iOS 设备。

```python
from ios_usbmuxd import DeviceManager

with DeviceManager() as manager:
    # 列出所有设备
    devices = manager.list_devices()

    # 查找指定设备
    device = manager.find_device(udid="设备UDID")

    # 或获取第一个可用设备
    device = manager.find_device()
```

#### `WDAClient`

WebDriverAgent HTTP API 客户端。

```python
from ios_usbmuxd import WDAClient

client = WDAClient(
    host="localhost",           # WDA 主机
    port=8100,                 # WDA 端口
    udid="设备UDID",           # 设备 UDID
    use_usbmuxd=True,          # 是否使用 USB 模式
    timeout=30.0,              # 超时时间
    launcher=None              # 可选 WDA 启动器
)

# 连接
client.connect(bundle_id="com.apple.mobilesafari")

# 操作
client.screenshot()   # 截图
client.source()      # 获取页面源码
client.click(x, y)  # 点击坐标
client.swipe(x1, y1, x2, y2)  # 滑动
client.input_text(element_id, "text")  # 输入文本

# 查找元素
elements = client.find_elements(by="class name", value="XCUIElementTypeButton")
element = client.find_element(by="accessibility id", value="loginButton")

# 断开
client.disconnect()
```

#### `WDA Launcher`

```python
from ios_usbmuxd import create_wda_launcher

launcher = create_wda_launcher(
    "command",
    command="ssh mac-mini 'xcodebuild test-without-building ...'",
    shell=True,
)
```

#### `Tunnel`

USB 隧道管理器。

```python
from ios_usbmuxd import Tunnel

tunnel = Tunnel(
    local_port=8100,       # 本地端口
    remote_port=8100,       # 远程端口 (iOS)
    udid="设备UDID"        # 设备 UDID
)

tunnel.start()        # 启动隧道
tunnel.stop()         # 停止隧道
tunnel.is_running()   # 检查状态
```

### WDA 支持的方法

| 方法 | 描述 | 参数 |
|------|------|------|
| `connect()` | 连接到 WDA，并按需启动/等待 WDA | `bundle_id`, `create_session`, `ready_timeout` |
| `disconnect()` | 断开连接并清理资源 | - |
| `status()` | 获取 `/status` 响应 | - |
| `wait_until_ready()` | 轮询等待 WDA 就绪 | `timeout`, `interval` |
| `screenshot()` | 截取屏幕截图 | - |
| `source()` | 获取页面 XML 源码 | - |
| `click(x, y)` | 点击指定坐标 | `x`, `y`: 坐标 |
| `swipe(x1, y1, x2, y2)` | 从起点滑动到终点 | 起点坐标、终点坐标 |
| `input_text(element_id, text)` | 向元素输入文本 | 元素ID、文本内容 |
| `find_elements(by, value)` | 查找所有匹配元素 | 选择器类型、值 |
| `find_element(by, value)` | 查找第一个匹配元素 | 同上 |
| `get_element_attribute()` | 获取元素属性 | 元素ID、属性名 |
| `get_screen_size()` | 获取屏幕尺寸 | - |
| `health_check()` | 检查 WDA 是否正常 | - |
| `terminate_session()` | 终止当前会话 | - |

### 选择器类型

- `class name` - XCUIElementType 类名
- `id` - 元素 ID
- `xpath` - XPath 表达式
- `name` - 元素名称
- `accessibility id` - 辅助功能 ID

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        用户代码                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   WDA Client (wda_client.py)                │
│     HTTP API: /session, /source, /screenshot + launcher     │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ 可选启动策略
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 WDA Launcher (wda_launcher.py)              │
│       none / devicectl / xcodebuild / command              │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ localhost:8100
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Tunnel (tunnel.py)                      │
│               select.select() 非阻塞 TCP 端口转发            │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ usbmuxd 协议
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        usbmuxd 守护进程                      │
│     Windows: TCP 127.0.0.1:27015  │  macOS/Linux: /var/run/usbmuxd │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ USB
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        iOS 设备                              │
│                  WebDriverAgent (:8100)                     │
└─────────────────────────────────────────────────────────────┘
```

## 项目结构

```
ios-usb-automation/
├── src/
│   └── ios_usbmuxd/           # 主包
│       ├── __init__.py       # 包导出
│       ├── protocol.py       # usbmuxd 二进制协议
│       ├── client.py         # usbmuxd socket 客户端（跨平台）
│       ├── tunnel.py         # TCP 隧道（纯 Python 版 iproxy）
│       ├── device.py         # 设备信息和管理
│       ├── wda_client.py     # WDA HTTP 客户端
│       ├── wda_launcher.py   # WDA 启动策略
│       └── exceptions.py     # 自定义异常
├── examples/                  # 示例代码
│   ├── enumerate_devices.py  # 设备枚举
│   ├── basic_automation.py  # 基础自动化
│   ├── managed_automation.py # 带启动策略的自动化
│   └── tunnel_demo.py        # 手动创建隧道
├── tests/                    # 单元测试
│   └── test_protocol.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 故障排除

### "未找到 iOS 设备"

1. 检查设备是否通过 USB 连接
2. 检查设备是否已授权信任（解锁设备查看弹窗）
3. 验证 usbmuxd 是否运行：
   - Windows: `netstat -an | findstr 27015`
   - macOS/Linux: `ls -la /var/run/usbmuxd`

### "连接 WDA 失败"

1. 确认 WebDriverAgent 已安装在 iOS 设备上
2. 尝试在设备上手动启动 WDA 应用
3. 检查 WDA 是否在设备上正常运行

### "Windows 上无法直接启动 WDA"

这是 Apple 工具链限制，不是 usbmux 协议限制。推荐做法：

1. 在 macOS 上准备好可启动的 WDA
2. 在 Windows 上使用 `command` 策略调用远端 Mac 启动命令
3. 启动后继续使用本仓库的 USB/WDA 客户端进行自动化

### "devicectl 启动了 app，但 8100 没起来"

1. 检查安装到设备上的 WDA 是否为可 launch 的预装包
2. 对 iOS 17+，确认包内已移除 `Frameworks/XC**`
3. 如果仍不稳定，切换到 `xcodebuild` 策略

### "连接 usbmuxd 被拒绝"

- Windows: 确保已安装 iTunes，Apple Mobile Device 服务正在运行
- macOS: 确保 Xcode Command Line Tools 已安装
- Linux: 确保 libimobiledevice 已安装且服务正在运行

### USB 连接不稳定

1. 尝试使用设备直接连接的 USB 端口（避免使用 USB hub）
2. 尝试更换 USB 数据线
3. 在设备上取消信任后重新授权

## 测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_protocol.py -v

# 运行 launcher 相关测试
pytest tests/test_wda_launcher.py -v

# 查看测试覆盖率
pytest tests/ --cov=src/ios_usbmuxd --cov-report=html
```

## 依赖

### 运行时依赖

- Python 3.8+

### 可选依赖

- `requests` - WDA HTTP 客户端（建议安装）
- `Pillow` - 截图处理

### 开发依赖

- `pytest` - 单元测试
- `pytest-cov` - 测试覆盖率

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 致谢

- [libimobiledevice](https://github.com/libimobiledevice/libimobiledevice) - 协议参考实现
- [Appium WebDriverAgent](https://github.com/appium/appium-webdriveragent) - WDA 维护者

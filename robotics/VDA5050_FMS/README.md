# VDA5050 FMS

基于 VDA 5050 2.1.0 开发的机器人调度系统。

项目当前处于增量开发阶段，现已完成单台机器人 `connection` Topic 的生成、消息校验、真实 MQTT Broker 订阅和跨电脑端到端测试。项目尚未向机器人发布订单或即时动作。

## 当前版本

当前阶段：**1.6 — VDA 5050 Connection Topic 订阅**

已完成：

- Python `src` 项目结构；
- 使用 `.env` 管理本地配置；
- MQTT Broker 与 VDA 5050 配置校验；
- Eclipse Paho MQTT 3.1.1 客户端；
- 用户名和密码认证；
- 可选 TLS 配置；
- 随机且独立的 MQTT Client ID；
- Broker 单次连接检查；
- 六种标准 VDA 5050 Topic 的生成；
- VDA 5050 公共 Header 模型；
- `connection` 消息的 JSON 解析、序列化与校验；
- 协议版本、制造商和机器人序列号校验；
- 使用 QoS 1 订阅单台机器人的 `connection` Topic；
- Broker 连接失败或中断后的自动重试；
- `ONLINE`、`OFFLINE` 和 `CONNECTIONBROKEN` 状态处理；
- 使用 `Ctrl+C` 正常停止监听。

## 阶段记录

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 1.1 | 建立 Python 项目结构和基础命令行入口 | 已完成 |
| 1.2 | 建立 `.env` 配置读取与校验 | 已完成 |
| 1.3 | 建立 MQTT Broker 基础连接与连接检查 | 已完成 |
| 1.4 | 生成六种标准 VDA 5050 Topic | 已完成 |
| 1.5 | 建立 `connection` 消息模型与离线 JSON 校验 | 已完成 |
| 1.6 | 订阅真实 Broker 的 `connection` Topic | 已完成 |

## 安装

创建并激活 Python 虚拟环境。

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux：

```bash
python3 -m venv .venv
source .venv/bin/activate
```

安装项目：

```bash
python -m pip install --upgrade pip
python -m pip install -e .
```

## 配置

复制配置模板：

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

Linux：

```bash
cp .env.example .env
```

在本地 `.env` 中配置 MQTT Broker 和机器人身份。不要提交 `.env`，也不要将真实用户名、密码或机器人信息写入 README。

机器人身份必须与 MQTT Topic 及消息 Header 中的以下字段完全一致：

- `VDA_INTERFACE_NAME`
- `VDA_VERSION`
- `VDA_MANUFACTURER`
- `VDA_SERIAL_NUMBER`

## 命令行功能

显示帮助：

```powershell
python -m vda5050_fms --help
```

检查 MQTT Broker 连接：

```powershell
python -m vda5050_fms --check-mqtt
```

显示当前配置生成的全部 VDA 5050 Topic：

```powershell
python -m vda5050_fms --show-topics
```

监听单台机器人的 `connection` Topic：

```powershell
python -m vda5050_fms --listen-connection
```

## VDA 5050 MQTT Topics

Topic 结构：

```text
{interfaceName}/v{majorVersion}/{manufacturer}/{serialNumber}/{topic}
```

从 FMS 的视角，各 Topic 的方向和当前支持程度如下：

| Topic | 通信方向 | 当前支持程度 |
| --- | --- | --- |
| `order` | FMS → AGV | 仅支持 Topic 生成 |
| `instantActions` | FMS → AGV | 仅支持 Topic 生成 |
| `state` | AGV → FMS | 仅支持 Topic 生成 |
| `visualization` | AGV → FMS | 仅支持 Topic 生成 |
| `connection` | AGV → FMS | 支持 Topic 生成、消息校验和订阅 |
| `factsheet` | AGV → FMS | 仅支持 Topic 生成 |

## Connection 消息支持

所有 VDA 5050 消息共享以下 Header 字段：

- `headerId`：每个 Topic 独立递增的消息编号；
- `timestamp`：以 `Z` 结尾的 ISO 8601 UTC 时间；
- `version`：VDA 5050 协议版本；
- `manufacturer`：机器人制造商；
- `serialNumber`：机器人序列号。

`connectionState` 支持以下状态：

- `ONLINE`：机器人与 Broker 的连接正常；
- `OFFLINE`：机器人主动正常离线；
- `CONNECTIONBROKEN`：机器人与 Broker 的连接意外中断。

监听器会校验：

- JSON 格式；
- Header 必填字段与字段类型；
- `headerId` 的 `uint32` 范围；
- UTC 时间格式；
- VDA 5050 版本格式及配置版本；
- 制造商和机器人序列号；
- `connectionState` 枚举值。

`connection` 只表示机器人与 MQTT Broker 的通信连接状态，不代表机器人的硬件、定位、任务执行或安全系统均处于正常状态。

## 测试

运行全部单元测试：

```powershell
python -m unittest discover -s tests -v
```

检查 Python 文件语法：

```powershell
python -m compileall -q src tests
```

当前 1.6 基线：

- 30 个单元测试全部通过；
- Broker 单次连接检查通过；
- 使用 Mosquitto 2.0.21、用户名和密码认证、TLS 关闭完成真实 Broker 测试；
- 使用另一台电脑发布测试消息，完成跨电脑端到端验证；
- FMS 已成功接收 `ONLINE`、`OFFLINE` 和 `CONNECTIONBROKEN`；
- 测试消息的 `headerId` 为 1、2、3。

## 当前限制

- 当前仅监听配置中的一台机器人；
- 尚未建立机器人运行状态缓存；
- 尚未解析 `state`、`visualization` 和 `factsheet` 消息；
- 尚未生成或发布 `order`；
- 尚未发布 `instantActions`；
- 尚未实现订单生命周期跟踪；
- 尚未实现多机器人注册与管理；
- 尚未接入数据库、调度算法、REST API 或 Web 界面；
- 可选 TLS 代码路径尚未完成真实 Broker 验证。

## 后续开发路线

将按照以下顺序继续开发：

| 阶段 | 目标 | 验收标准 |
| --- | --- | --- |
| 1.7 | 建立机器人连接状态缓存 | 保存最新连接状态、Header ID、消息时间和本地接收时间，并可查询当前状态 |
| 1.8 | 建立 `state` 消息模型 | 根据 VDA 5050 2.1.0 Schema 完成离线解析、序列化和字段校验 |
| 1.9 | 订阅 `state` Topic | 从真实 Broker 接收状态，并维护单台机器人运行快照 |
| 1.10 | 建立 `factsheet` 支持 | 接收并保存机器人的能力、尺寸和协议能力信息 |
| 1.11 | 建立 `visualization` 支持 | 接收高频位置数据，并与业务状态更新解耦 |
| 2.0 | 建立 `order` 消息模型 | 离线生成并校验合法订单，不立即发布 |
| 2.1 | 发布订单并跟踪生命周期 | 使用 QoS 1 发布订单，并通过 `state` 跟踪接收、执行与完成状态 |
| 2.2 | 建立 `instantActions` 支持 | 发布即时动作并通过状态消息确认结果 |
| 2.3 | 支持多机器人 | 建立机器人注册表、独立 Topic、连接状态和运行状态管理 |
| 3.0 | 建立任务分配与调度 | 根据机器人状态、能力和任务约束选择机器人 |
| 3.1 | 增加持久化 | 保存机器人、订单、任务、事件和审计记录 |
| 3.2 | 增加 API 与 Web 界面 | 提供任务创建、状态查看、异常处理和运行监控功能 |

在开始调度算法之前，应先完成 `connection`、`state`、`factsheet` 和订单生命周期闭环。调度器只有在能够可靠判断机器人是否在线、是否可用、具备哪些能力以及订单执行到哪一步后，才能做出安全且可解释的任务分配决策。

## 安全边界

当前版本不会向真实机器人发送 `order` 或 `instantActions`。后续加入发布功能时，应先在仿真环境或隔离测试 Broker 中验证，并为目标机器人身份、Topic、订单编号和动作类型增加显式校验。

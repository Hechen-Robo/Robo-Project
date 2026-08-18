# VDA5050 FMS

VDA 5050 调度系统的第一阶段基础工程。目前包括：

- 连接现有 MQTT Broker；
- 只读监听真实机器人的 `state`、`connection`、`factsheet` 和
  `visualization`；
- 使用 VDA 5050 官方 2.1.0 JSON Schema 校验每条消息；
- 校验 MQTT topic 中的 `manufacturer`、`serialNumber` 与 JSON 内容一致；
- 单机器人模拟器；
- 可控的两节点测试订单发布器；
- base/horizon、暂停、继续、取消订单的基础模拟；
- 单元测试和 MQTT 开发 Broker。

> 当前代码严格支持 **VDA 5050 2.1.0**。如果配置为其他版本，程序会直接
> 拒绝启动，防止将不兼容消息发送给真实机器人。

## 1. 安装

需要 Python 3.10 或更高版本，推荐 Python 3.12。

```bash
cd robotics/VDA5050_FMS
python -m venv .venv
```

Linux：

```bash
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
Copy-Item .env.example .env
```

然后编辑 `.env`，填入真实 MQTT Broker 的地址、端口、用户名、密码和 TLS
配置。`.env` 已被 Git 忽略，不要把真实密码或证书提交到仓库。

VDA 5050 2.1.0 推荐的本地 Broker topic 格式为：

```text
uagv/v2/{manufacturer}/{serialNumber}/{topic}
```

例如：

```text
uagv/v2/SEER/AGV-001/state
```

如果你的 Broker 使用了自定义 `interfaceName`，修改
`VDA_INTERFACE_NAME`。主版本 `v2` 会自动从 `VDA_VERSION=2.1.0` 生成。

## 2. 先安全检查真实机器人通信

第一次接入真实机器人时，只启动只读监控：

```bash
vda5050-fms monitor
```

显示完整 JSON：

```bash
vda5050-fms monitor --verbose
```

监控程序不会发布 `order` 或 `instantActions`，因此适合作为第一步。正常输出
应包含：

```text
VALID SEER/AGV-001 state         order='' update=0 lastNode='N001' ...
VALID SEER/AGV-001 connection    connectionState=ONLINE
```

如果显示 `INVALID`，程序会指出缺失字段、错误类型或 topic/payload 身份不一致。
部分厂商可能存在协议扩展；先保存消息样本，再决定是否建立厂商适配层，不要直接
放宽官方 Schema。

## 3. 在同一个 Broker 上运行模拟机器人

`.env` 默认模拟身份为：

```text
SIMULATOR / SIM-001
```

启动模拟器：

```bash
vda5050-fms simulator
```

模拟器会：

- 使用 QoS 1、retain 的 `connection` 消息和 `CONNECTIONBROKEN` Last Will；
- 周期性发布 `state` 与 `visualization`；
- 发布并响应 `factsheetRequest`；
- 订阅自己的 `order` 与 `instantActions`；
- 执行 released edge；
- 在只有 horizon、没有新 base 时设置 `newBaseRequest=true`。

## 4. 向模拟器发送测试订单

另开一个终端，显式指定目标并确认允许发布：

```bash
vda5050-fms demo-order \
  --target-manufacturer SIMULATOR \
  --target-serial SIM-001 \
  --allow-command
```

该命令会发布一个 `N0 -> N1` 的两节点订单。没有 `--allow-command` 时程序拒绝
发布。连接真实机器人前，不要把测试订单直接发给真实车辆；真实车辆的起点
`nodeId`、`mapId`、坐标和 Action 必须来自实际地图及车辆配置。

## 5. 校验保存的消息

```bash
vda5050-fms validate state samples/state.json
vda5050-fms validate order samples/order.json
```

可选 topic：`connection`、`factsheet`、`instantActions`、`order`、`state`、
`visualization`。

## 6. 本地开发 Broker

如果暂时不使用现有 Broker，可以运行：

```bash
docker compose up -d mqtt
```

`deploy/mosquitto.conf` 允许匿名访问，仅适用于本机开发。生产环境必须配置
TLS、独立机器人账号和 topic ACL。

## 7. 测试

```bash
pytest
```

测试覆盖官方 Schema、topic 生成、订单执行、horizon 等待以及暂停/取消。

## 下一阶段

完成真实机器人消息采样并确认厂商实现差异后，下一阶段将实现：

1. 原始 MQTT 消息持久化与状态投影；
2. 每台机器人独立 Session；
3. `orderId` / `orderUpdateId` 的可靠发送及状态确认；
4. 第一张节点—边拓扑图与基础路径规划。

## 上游 Schema

`src/vda5050_fms/schemas/v2_1` 中的 Schema 原样来自
[VDA5050/VDA5050 tag 2.1.0](https://github.com/VDA5050/VDA5050/tree/2.1.0/json_schemas)，
并保留上游 MIT License。

# VDA5050 FMS

基于 VDA 5050 2.1.0 的机器人调度系统。

## 当前阶段

1.3：建立 MQTT Broker 基础连接。

目前已经完成：

- Python `src` 项目结构；
- 使用 `.env` 管理本地配置；
- MQTT Broker 和 VDA 5050 配置校验；
- Eclipse Paho MQTT 客户端；
- MQTT 3.1.1 客户端配置；
- 用户名和密码认证配置；
- 可选 TLS 配置；
- 随机且独立的 MQTT Client ID；
- 显式的 Broker 连接检查；
- 连接成功后的正常断开。

目前尚未加入：

- MQTT topic 订阅；
- MQTT 消息发布；
- VDA 5050 topic 生成；
- VDA 5050 JSON 消息处理；
- 真实机器人控制；
- 调度算法；
- 数据库；
- Web 界面。

## 安装

在已经激活的 Python 虚拟环境中执行：

```bash
python -m pip install -e .

## 检查 MQTT Broker 连接

```bash
python -m vda5050_fms --check-mqtt


--------------------------------------------------------------

## VDA 5050 MQTT 主题

本项目按照 VDA 5050 规范生成 MQTT Topic，结构如下：

```text
{interfaceName}/v{majorVersion}/{manufacturer}/{serialNumber}/{topic}
```

当前支持以下六种 VDA 5050 Topic：

- `order`：接收订单
- `instantActions`：接收即时动作
- `state`：发布机器人状态
- `visualization`：发布机器人可视化位置
- `connection`：发布机器人连接状态
- `factsheet`：发布机器人能力信息

在不连接 MQTT Broker 的情况下显示当前配置生成的全部 Topic：

```powershell
python -m vda5050_fms --show-topics
```

运行 Topic 单元测试：

```powershell
python -m unittest discover -s tests -v
```


## VDA 5050 连接消息模型

项目目前支持对 VDA 5050 2.1.0 `connection` 消息进行离线解析与校验。

所有 VDA 5050 消息共享以下 Header 字段：

- `headerId`：每个 Topic 独立递增的消息编号
- `timestamp`：以 `Z` 结尾的 ISO 8601 UTC 时间
- `version`：VDA 5050 协议版本
- `manufacturer`：机器人制造商
- `serialNumber`：机器人序列号

`connectionState` 支持以下状态：

- `ONLINE`：机器人与 Broker 的连接正常
- `OFFLINE`：机器人主动正常离线
- `CONNECTIONBROKEN`：机器人与 Broker 的连接意外中断

该消息模型当前仅处理本地 JSON，不会连接、订阅或发布 MQTT 消息。

运行所有单元测试：

```powershell
python -m unittest discover -s tests -v
```
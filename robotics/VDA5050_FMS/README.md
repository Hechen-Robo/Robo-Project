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
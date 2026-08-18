# VDA5050 FMS

基于 VDA 5050 2.1.0 的机器人调度系统。

## 当前阶段

1.2：建立应用配置层。

目前已经完成：

- Python `src` 项目结构；
- 可执行的 Python 包入口；
- 使用 `.env` 保存本地配置；
- MQTT Broker 基础连接参数定义；
- VDA 5050 机器人身份参数定义；
- 端口、Keep Alive、TLS 和协议版本配置校验；
- 配置错误退出码处理。

目前尚未加入：

- MQTT Broker 连接；
- MQTT topic 订阅和发布；
- VDA 5050 JSON 消息处理；
- 真实机器人控制；
- 调度算法；
- 数据库；
- Web 界面。

## 安装

在已经激活的 Python 虚拟环境中执行：

```bash
python -m pip install -e .
# VDA5050 FMS

当前进度：**1.1 — 创建最小 Python 项目骨架**。

本步骤只完成以下内容：

- 使用 `src` 目录组织 Python 包；
- 定义项目名称、版本和 Python 版本要求；
- 提供一个可运行的占位入口，用于确认项目安装正确。

本步骤尚未加入 MQTT、VDA 5050 消息、机器人通信、调度逻辑、数据库、模拟器或 CI。

## 安装与验证

需要 Python 3.10 或更高版本。

```bash
cd robotics/VDA5050_FMS
python -m venv .venv
```

Linux：

```bash
source .venv/bin/activate
python -m pip install -e .
python -m vda5050_fms
```

Windows PowerShell：

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m vda5050_fms
```

预期输出：

```text
VDA5050 FMS 0.1.0: project skeleton is ready.
```

确认 1.1 后，再进入下一步。

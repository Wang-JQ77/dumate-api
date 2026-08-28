# DuMate API

将百度搭子（DuMate）的积分余额与 AI 执行能力暴露为本地 API，提供 **OpenAI 兼容**和 **Claude 兼容**两种协议，可供 OpenAI SDK、Anthropic SDK、Claude Code 等 Agent 直接调用。

> 百度搭子（DuMate）登录即送 2000 积分，新用户赠送 25000 积分，每日签到+完成任务可获数千积分。

## 快速开始

### 前置条件

- **Windows 系统** + **DuMate 桌面版**已登录并运行
- **Python 3.10+**：从 [python.org](https://www.python.org/downloads/) 安装，务必勾选 **"Add Python to PATH"**
- 安装依赖：`pip install -r requirements.txt`

### 启动

```bat
start_points_api.bat
```

服务启动在 `http://127.0.0.1:8765`，首次运行会自动生成 API Token 保存在 `token.txt`。

### 停止

```bat
stop_points_api.bat
```

## 使用方式

### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key="<你的Token>")

# 执行任务
r = client.chat.completions.create(
    model="dumate-lite",
    messages=[{"role": "user", "content": "帮我写一个 Python 脚本"}],
)
print(r.choices[0].message.content)
```

### Anthropic SDK / Claude Code

```python
from anthropic import Anthropic

client = Anthropic(base_url="http://127.0.0.1:8765", api_key="<你的Token>")
r = client.messages.create(
    model="dumate-ultra",
    max_tokens=4096,
    messages=[{"role": "user", "content": "帮我总结项目架构"}],
)
print(r.content[0].text)
```

Claude Code 接入：

```bat
set ANTHROPIC_BASE_URL=http://127.0.0.1:8765
set ANTHROPIC_AUTH_TOKEN=<你的Token>
set ANTHROPIC_MODEL=dumate-ultra
claude
```

### 查询积分

```bat
curl -H "X-API-Key: <你的Token>" http://127.0.0.1:8765/api/points/balance
```

## 模型选择

| 模型名 | 模式 | 适用场景 |
| --- | --- | --- |
| `dumate-lite` | Lite 极速 | 日常对话、简单任务，响应最快 |
| `dumate-turbo` | Turbo 增强 | 较复杂的内容生成、代码任务 |
| `dumate-ultra` | Ultra 专业 | 深度推理、复杂工作 |
| `dumate-points` | 积分专用 | 查询积分余额，不消耗积分 |

> Claude 客户端默认模型名会自动映射：`*haiku*` → Lite、`*sonnet*` → Turbo、`*opus*` → Ultra。

## 鉴权

所有接口（除 `/health`）需要 API Token，通过以下任意方式传递：

| 方式 | 请求头 |
| --- | --- |
| Header | `X-API-Key: <token>` |
| Bearer | `Authorization: Bearer <token>` |
| Claude 风格 | `x-api-key: <token>` |

## 详细文档

| 文档 | 内容 |
| --- | --- |
| [API 参考](docs/API参考.md) | 全部端点、请求/响应细节、错误码、内置工具 |
| [常见问题](docs/常见问题.md) | 启动、任务执行、积分、认证、Agent 接入的故障排查 |
| [架构说明](docs/架构说明.md) | 进程发现、积分链路、代理机制、协议转换原理 |

## 安全说明

- **Token 管理**：首次启动自动生成随机 Token，保存在 `token.txt`。泄露后删除 `token.txt` 重启服务即可重新生成
- **本地服务**：API 服务默认只监听 `127.0.0.1`，外网无法直接访问
- **积分消耗**：每条非积分查询的消息都消耗 DuMate 积分，注意控制调用频率

## 免责声明

本项目是对百度搭子（DuMate）桌面版客户端本地服务的接口封装，**仅供个人学习和研究使用**。使用前需自行安装并登录正版 DuMate 客户端，遵守百度服务条款，自行承担积分消耗和相关费用。

## License

MIT

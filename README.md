# DuMate API

将百度搭子（DuMate）的积分余额与 AI 执行能力暴露为本地 API，支持 REST 接口和 OpenAI 兼容协议，可供其他 Agent 或脚本直接调用。

## 功能

- **积分查询**：查询 DuMate 账户的可用积分、总积分、已用积分
- **任务执行**：调用 DuMate 的 AI 能力执行对话、内容生成、文件修改等任务
- **三种模型模式**：Lite（极速）/ Turbo（增强）/ Ultra（专业），按需选择
- **OpenAI 兼容接口**：支持 `/v1/chat/completions` 和 `/v1/responses`，可用 OpenAI SDK 直接调用
- **工具调用**：通过 function calling 协议让其他 Agent 发现并使用积分查询、任务执行等能力

## 架构

```
┌─────────────┐    HTTP     ┌──────────────┐    HTTP     ┌──────────────┐
│  你的 Agent  │ ──────────→ │  DuMate API  │ ──────────→ │  DuMate      │
│  (OpenAI    │ ←────────── │  :8765       │ ←────────── │  opencode    │
│   SDK)      │             │              │             │  :52795      │
└─────────────┘             └──────┬───────┘             └──────┬───────┘
                                  │                            │
                           ┌──────┴───────┐            ┌───────┴───────┐
                           │  8888 透传    │            │  百度云 API    │
                           │  代理         │            │  (积分/模型)   │
                           └──────────────┘            └───────────────┘
```

- **8888 透传代理**：DuMate 的模型调用链路需要本地 HTTP 代理，项目自动启动透明代理满足此依赖
- **opencode**：DuMate 本地执行引擎，暴露会话/消息 HTTP 接口，API 服务通过此接口驱动任务执行

## 前置条件

1. **DuMate 客户端**已登录并运行（百度搭子桌面版）
2. **Python 3.10+**
3. 安装依赖：`pip install -r requirements.txt`

## 快速开始

```bat
start_points_api.bat
```

首次运行会自动生成 API Token 保存到 `token.txt`，随后在后台启动：

- **API 服务**：`http://127.0.0.1:8765`
- **8888 透传代理**：DuMate 模型调用链路依赖的本地代理

停止服务：

```bat
stop_points_api.bat
```

> 8888 代理是 DuMate 模型调用所必需的，两个进程必须一起启停。请使用提供的 bat 脚本统一管理。

### 跨平台手动启动

```bash
pip install -r requirements.txt
python points_api.py --port 8765 --token "$(python -c 'import secrets; print(secrets.token_hex(16))')"
```

## API 参考

### 鉴权

所有接口（除 `/health` 外）需要 API Token，通过以下方式传递：

| 方式 | 请求头 |
| --- | --- |
| Header | `X-API-Key: <token>` |
| Bearer | `Authorization: Bearer <token>` |

### REST 接口

#### 查询积分余额

```
GET /api/points/balance
```

```json
{
  "totalPoints": 29170.0,
  "usedPoints": 7285.29,
  "availablePoints": 21884.71,
  "isSubscribed": true,
  "subscriptionCount": 1,
  "incrementalCount": 28,
  "updatedAt": 1787077104
}
```

结果带 60 秒缓存。强制刷新用 `GET /api/points/balance/refresh`。

#### 创建任务

```
POST /api/tasks
```

```json
{ "title": "分析报告", "directory": "/path/to/workspace" }
```

```json
{ "task_id": "xxx", "session_id": "xxx", "title": "分析报告", "directory": "/path/to/workspace", "created_at": "..." }
```

#### 发送任务消息

```
POST /api/tasks/{task_id}/messages
```

同步模式（等待执行完成）：

```json
{ "message": "帮我写一份项目总结", "sync": true }
```

异步模式（后台执行，立即返回）：

```json
{ "message": "帮我分析这份代码", "sync": false }
```

异步模式下通过 `GET /api/tasks/{task_id}/messages` 轮询结果。

#### 健康检查

```
GET /health
```

### OpenAI 兼容接口

#### 模型列表

```
GET /v1/models
```

| 模型名 | 用途 |
| --- | --- |
| `dumate-points` | 积分查询（含积分关键词时直接返回余额，不消耗积分） |
| `dumate-lite` | Lite 极速模式，适合日常任务 |
| `dumate-turbo` | Turbo 增强模式，适合较复杂任务 |
| `dumate-ultra` | Ultra 专业模式，适合深度推理任务 |

#### Chat Completions

```
POST /v1/chat/completions
```

支持：流式输出、`response_format`（`json_object` / `json_schema`）、工具调用（function calling）、三种模型选择。

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key="<token>")

# 查询积分
r = client.chat.completions.create(
    model="dumate-points",
    messages=[{"role": "user", "content": "查询积分余额"}],
)
print(r.choices[0].message.content)

# 执行任务（Lite 模式）
r = client.chat.completions.create(
    model="dumate-lite",
    messages=[{"role": "user", "content": "帮我写一个 Python 脚本读取 CSV 文件"}],
)
print(r.choices[0].message.content)
```

#### Responses API

```
POST /v1/responses
```

支持 `input` 为字符串或消息数组、`text.format` 结构化输出、工具调用、SSE 流式事件。

## 安全说明

- **Token 管理**：首次启动自动生成随机 Token，保存在 `token.txt`。请妥善保管，泄露后可通过删除 `token.txt` 重启服务重新生成
- **工作目录**：任务执行的工作目录通过 `directory` 参数指定，建议限制在固定目录下
- **积分消耗**：Lite/Turbo/Ultra 模式下每条消息都会消耗 DuMate 积分，请注意控制调用频率

## 免责声明

本项目是对百度搭子（DuMate）桌面版客户端本地服务的接口封装，**仅供个人学习和研究使用**。使用前需：

- 自行安装并登录正版 DuMate 客户端
- 遵守百度服务条款
- 自行承担积分消耗和相关费用

本项目不保证持续可用，不承担任何因使用本项目产生的损失或责任。

## License

MIT
# DuMate API

将百度搭子（DuMate）的积分余额与 AI 执行能力暴露为本地 API，同时提供 **OpenAI 兼容**和 **Claude（Anthropic）兼容**两种协议，可供其他 Agent（OpenAI SDK、Anthropic SDK、Claude Code 等）直接调用，用来回答问题和执行任务。

百度搭子（DuMate）登录即送2000积分，新用户赠送25000积分，每日签到+完成任务可获数千积分，实现你的token自由！

## 文档

| 文档 | 内容 |
| --- | --- |
| [API 参考](docs/API参考.md) | 全部端点的请求/响应细节、错误码、内置工具 |
| [常见问题](docs/常见问题.md) | 启动、任务执行、积分、认证、Agent 接入的故障排查 |
| [架构说明](docs/架构说明.md) | 进程发现、积分链路、代理机制、协议转换的实现原理 |
| [发布操作文档](docs/发布操作文档.md) | 项目维护者：Git/gh CLI 发布与更新流程 |

## 功能

- **积分查询**：查询 DuMate 账户的可用积分、总积分、已用积分（不消耗积分）
- **任务执行**：调用 DuMate 的 AI 能力执行对话、内容生成、文件修改等任务（消耗积分）
- **三种原生模式**：Lite（极速）/ Turbo（增强）/ Ultra（专业），所有接口均可选择
- **OpenAI 兼容**：`/v1/chat/completions`、`/v1/responses`、`/v1/models`，OpenAI SDK 直接调用
- **Claude 兼容**：`/v1/messages`、`/v1/messages/count_tokens`，Anthropic SDK 与 Claude Code 直接调用
- **工具调用**：function calling 协议（两种格式均支持），服务端真实执行积分查询与任务

## 架构

```
┌──────────────────┐    HTTP     ┌──────────────┐    HTTP     ┌──────────────┐
│  你的 Agent       │ ──────────→ │  DuMate API  │ ──────────→ │  DuMate      │
│  OpenAI SDK /    │ ←────────── │  :8765       │ ←────────── │  opencode    │
│  Anthropic SDK / │             │              │             │  本地服务     │
│  Claude Code     │             └──────┬───────┘             └──────┬───────┘
└──────────────────┘                    │                            │
                                 ┌──────┴───────┐            ┌───────┴───────┐
                                 │  透传代理     │            │  百度云 API    │
                                 │  (按需启动)   │            │  (积分/模型)   │
                                 └──────────────┘            └───────────────┘
```

- **opencode**：DuMate 桌面客户端自带的本地执行引擎，暴露会话/消息 HTTP 接口。API 服务自动从其进程发现端口和鉴权 key，无需手动配置
- **透传代理（按需启动）**：DuMate 的模型调用会走其进程环境中的 `HTTP_PROXY` 地址。该地址每台机器可能不同（且可能是已失效的陈旧配置），启动脚本会自动读取 DuMate 实际期望的代理地址：若该地址无服务监听，则在同一端口启动透明转发代理兜底；若 DuMate 未配置代理或已有可用代理，则自动跳过

## 前置条件

1. **Windows 系统** + **DuMate 客户端**已登录并运行（百度搭子桌面版）
2. **Python 3.10+**：从 [python.org](https://www.python.org/downloads/) 安装，安装时**务必勾选 "Add Python to PATH"**（Microsoft Store 版也可以，但若报"找不到 python 命令"请改用官网安装包）
3. 安装依赖：`pip install -r requirements.txt`

> 项目通过读取 DuMate 客户端进程的环境变量自动发现本地服务地址与鉴权 key，通过 `%APPDATA%\qianfan-desktop-app` 下的加密 cookie 查询积分，无需任何手动配置。

## 快速开始

```bat
start_points_api.bat
```

首次运行会自动生成 API Token 保存到 `token.txt`，随后在后台启动：

- **API 服务**：`http://127.0.0.1:8765`
- **透传代理**：按需启动（见上方架构说明，自动适配你机器上 DuMate 期望的代理地址）

停止服务：

```bat
stop_points_api.bat
```

> 若 DuMate 的代理配置失效，透传代理是模型调用所必需的，两个进程会一起启停。请使用提供的 bat 脚本统一管理。
> DuMate 客户端重新登录或退出后，需重启本服务。

## API 参考

### 鉴权

所有接口（除 `/health` 外）需要 API Token，通过以下任意方式传递：

| 方式 | 请求头 |
| --- | --- |
| Header | `X-API-Key: <token>` |
| Bearer | `Authorization: Bearer <token>` |
| Claude 风格 | `x-api-key: <token>` |

### 模型选择（三种原生模式）

| 模型名 | 模式 | 适用场景 |
| --- | --- | --- |
| `dumate-lite` | Lite 极速 | 日常对话、简单任务，响应最快 |
| `dumate-turbo` | Turbo 增强 | 较复杂的内容生成、代码任务 |
| `dumate-ultra` | Ultra 专业 | 深度推理、复杂工作 |
| `dumate-points` | 积分专用 | 消息含积分关键词时直接返回余额，不消耗积分 |

Claude 客户端的默认模型名会自动按档位映射：`*haiku*` → Lite、`*sonnet*` → Turbo、`*opus*` → Ultra，因此 Claude Code 无需改模型配置即可直接使用。REST 任务接口通过 `model` 或 `model_level` 字段指定模式。

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
{ "title": "分析报告", "directory": "C:\\path\\to\\workspace" }
```

`directory` 省略时使用 DuMate 默认工作目录。返回 `task_id`。

#### 发送任务消息（支持三模式）

```
POST /api/tasks/{task_id}/messages
```

```json
{ "message": "帮我写一份项目总结", "model": "dumate-ultra", "sync": true }
```

- `model`：`dumate-lite` / `dumate-turbo` / `dumate-ultra`（也可传 `model_level`: `lite`/`turbo`/`ultra`），省略时用 DuMate 默认模式
- `sync: true`：等待执行完成并返回结果；`sync: false`：后台执行，立即返回，通过 `GET /api/tasks/{task_id}/messages` 轮询结果

#### 健康检查

```
GET /health
```

### OpenAI 兼容接口

`POST /v1/chat/completions`（流式、`response_format`、工具调用）与 `POST /v1/responses`（结构化输出、SSE 流式事件）。

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key="<token>")

# 执行任务（Lite 模式）
r = client.chat.completions.create(
    model="dumate-lite",
    messages=[{"role": "user", "content": "帮我写一个 Python 脚本读取 CSV 文件"}],
)
print(r.choices[0].message.content)

# 查询积分（不消耗积分）
r = client.chat.completions.create(
    model="dumate-points",
    messages=[{"role": "user", "content": "查询积分余额"}],
)
print(r.choices[0].message.content)
```

### Claude（Anthropic）兼容接口

`POST /v1/messages`（非流式、流式、工具调用）与 `POST /v1/messages/count_tokens`。

```python
from anthropic import Anthropic

client = Anthropic(base_url="http://127.0.0.1:8765", api_key="<token>")

r = client.messages.create(
    model="dumate-ultra",
    max_tokens=4096,
    messages=[{"role": "user", "content": "帮我总结这个项目的架构"}],
)
print(r.content[0].text)
```

#### Claude Code 接入

Claude Code 通过环境变量指向本服务即可，无需修改模型配置：

```bat
set ANTHROPIC_BASE_URL=http://127.0.0.1:8765
set ANTHROPIC_AUTH_TOKEN=<token>
set ANTHROPIC_MODEL=dumate-ultra
claude
```

- `ANTHROPIC_MODEL` 指定 `dumate-lite` / `dumate-turbo` / `dumate-ultra`
- 不设置时，Claude Code 的默认模型名（claude-haiku/sonnet/opus）会自动映射到对应档位
- 也可用 `ANTHROPIC_API_KEY` 代替 `ANTHROPIC_AUTH_TOKEN`（本服务两种鉴权头都支持）

## 安全说明

- **Token 管理**：首次启动自动生成随机 Token，保存在 `token.txt`。请妥善保管，泄露后删除 `token.txt` 重启服务即可重新生成
- **工作目录**：任务执行的工作目录通过 `directory` 参数指定，建议限制在固定目录下
- **积分消耗**：每条非积分查询的消息都会消耗 DuMate 积分，请注意控制调用频率

## 常见问题

- **任务执行报连接失败**：确认 DuMate 客户端正在运行，且用 `start_points_api.bat` 启动（它会自动处理 DuMate 的代理依赖）
- **DuMate 重新登录后接口 401/失败**：DuMate 登录态变化后需重启本服务
- **积分查询失败**：确认 DuMate 客户端已登录；cookie 过期时在 DuMate 中重新登录即可

## 免责声明

本项目是对百度搭子（DuMate）桌面版客户端本地服务的接口封装，**仅供个人学习和研究使用**。使用前需：

- 自行安装并登录正版 DuMate 客户端
- 遵守百度服务条款
- 自行承担积分消耗和相关费用

本项目不保证持续可用，不承担任何因使用本项目产生的损失或责任。

## License

MIT

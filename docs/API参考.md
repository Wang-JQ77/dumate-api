# API 参考

DuMate API 的完整接口文档。基础地址：`http://127.0.0.1:8765`

## 目录

- [鉴权](#鉴权)
- [错误码](#错误码)
- [模型选择](#模型选择)
- [REST 接口](#rest-接口)
- [OpenAI 兼容接口](#openai-兼容接口)
- [Claude 兼容接口](#claude-兼容接口)
- [内置工具](#内置工具)

## 鉴权

所有接口（除 `/health`）需要 API Token，通过以下任意方式传递：

| 方式 | 请求头 | 典型客户端 |
| --- | --- | --- |
| Header | `X-API-Key: <token>` | curl / 自定义脚本 |
| Bearer | `Authorization: Bearer <token>` | OpenAI SDK（默认） |
| Claude 风格 | `x-api-key: <token>` | Anthropic SDK（默认） |

Token 保存在项目根目录 `token.txt`，首次启动时自动生成。

## 错误码

| 状态码 | 含义 | 处理方式 |
| --- | --- | --- |
| 401 | Token 缺失或错误 | 检查请求头是否携带正确 Token |
| 400 | 请求参数缺失（如 message 为空） | 补全必填字段 |
| 422 | 请求体不是合法 JSON | 检查 Content-Type 和 JSON 格式 |
| 502 | 调用 DuMate 本地服务失败 | 确认 DuMate 客户端正在运行；重启本服务 |

## 模型选择

| 模型名 | 模式 | 适用场景 |
| --- | --- | --- |
| `dumate-lite` | Lite 极速 | 日常对话、简单任务，响应最快 |
| `dumate-turbo` | Turbo 增强 | 较复杂的内容生成、代码任务 |
| `dumate-ultra` | Ultra 专业 | 深度推理、复杂工作 |
| `dumate-points` | 积分专用 | 消息含积分关键词时直接返回余额，不消耗积分 |

**别名映射**：Claude 客户端的默认模型名自动映射——`*haiku*` → Lite、`*sonnet*` → Turbo、`*opus*` → Ultra。因此 Claude Code 不改模型配置即可使用，也无需记住 DuMate 的模型名。

## REST 接口

### GET /health

健康检查，无需鉴权。

```json
{ "status": "ok" }
```

### GET /api/points/balance

查询积分余额（60 秒缓存，不消耗积分）。

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

| 字段 | 说明 |
| --- | --- |
| `totalPoints` | 总积分 |
| `usedPoints` | 已用积分 |
| `availablePoints` | 可用积分 = 总积分 − 已用 |
| `isSubscribed` | 是否有订阅 |
| `incrementalCount` | 剩余加油包次数 |
| `updatedAt` | 数据更新时间戳（秒） |

### GET /api/points/balance/refresh

同上，但绕过缓存强制从百度云拉取最新数据。

### POST /api/tasks

创建任务会话。

```json
{
  "title": "分析报告",
  "directory": "C:\\Users\\me\\workspace"
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `title` | 否 | 任务标题，默认"新任务" |
| `directory` | 否 | 任务工作目录（文件读写的根目录），默认为 DuMate 默认目录 |

响应：

```json
{
  "task_id": "ses_xxx",
  "session_id": "ses_xxx",
  "title": "分析报告",
  "directory": "C:\\Users\\me\\workspace",
  "created_at": "..."
}
```

### GET /api/tasks

任务列表。

### POST /api/tasks/{task_id}/messages

向任务发送消息并执行（消耗积分）。

```json
{
  "message": "帮我写一份项目总结",
  "model": "dumate-ultra",
  "sync": true
}
```

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `message` | 是 | 要执行的任务描述（也可用 `text` 字段） |
| `model` | 否 | `dumate-lite` / `dumate-turbo` / `dumate-ultra`，或直接用 `model_level` 传 `lite`/`turbo`/`ultra` |
| `sync` | 否 | 默认 `true` 等待执行完成返回结果；`false` 时后台执行立即返回 |

同步模式响应（等待执行完成，长任务可能需要数分钟）：

```json
{
  "task_id": "ses_xxx",
  "reply": { "role": "assistant", "content": "项目总结已完成……" },
  "messages": [ ... ]
}
```

异步模式响应（立即返回）：

```json
{
  "task_id": "ses_xxx",
  "accepted": true,
  "poll": "/api/tasks/ses_xxx/messages"
}
```

### GET /api/tasks/{task_id}/messages

读取任务的全部消息与结果（用于异步模式轮询）。

## OpenAI 兼容接口

### GET /v1/models

模型列表，返回 `dumate-points`、`dumate-lite`、`dumate-turbo`、`dumate-ultra`。

### POST /v1/chat/completions

标准 Chat Completions 格式，支持：

- `model`：见[模型选择](#模型选择)
- `stream`：SSE 流式输出
- `tools`：OpenAI function calling 格式，内置工具见[内置工具](#内置工具)
- `response_format`：`{"type": "json_object"}` / `{"type": "json_schema", ...}`

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8765/v1", api_key="<token>")

r = client.chat.completions.create(
    model="dumate-lite",
    messages=[{"role": "user", "content": "帮我写一个读取 CSV 的脚本"}],
)
print(r.choices[0].message.content)
```

工具调用为两轮协议：第一轮返回 `tool_calls`，客户端按标准协议回传 `role: "tool"` 的结果，服务端真正执行工具并返回最终自然语言回复。

### POST /v1/responses

OpenAI Responses API 格式，与 `/v1/chat/completions` 共存，支持：

- `input`：字符串或消息数组
- `stream`：完整 SSE 事件序列
- `tools`：工具调用（两轮协议同上，回传 `function_call_output`）
- `text.format`：结构化输出（`json_object` / `json_schema`）

## Claude 兼容接口

### POST /v1/messages

Anthropic Messages API 格式，支持：

- `model`：见[模型选择](#模型选择)（Claude 默认模型名自动映射）
- `max_tokens`：必填字段，服务端忽略其值（积分按实际消耗计）
- `stream`：SSE 流式（`message_start` → `content_block_start/delta/stop` → `message_delta` → `message_stop`）
- `tools`：Claude 工具格式（顶层 `name` + `input_schema`），两轮协议回传 `tool_result`

```python
from anthropic import Anthropic

client = Anthropic(base_url="http://127.0.0.1:8765", api_key="<token>")

r = client.messages.create(
    model="dumate-ultra",
    max_tokens=4096,
    messages=[{"role": "user", "content": "帮我总结这个项目"}],
)
print(r.content[0].text)
```

### POST /v1/messages/count_tokens

按 4 字符 ≈ 1 token 粗略估算，返回 `{"input_tokens": N}`。

### Claude Code 接入

```bat
set ANTHROPIC_BASE_URL=http://127.0.0.1:8765
set ANTHROPIC_AUTH_TOKEN=<token>
set ANTHROPIC_MODEL=dumate-ultra
claude
```

不设置 `ANTHROPIC_MODEL` 时，默认模型名自动按档位映射。

## 内置工具

声明工具后，服务端按消息内容路由到对应工具并**真实执行**（无需客户端实现执行逻辑）：

| 工具 | 参数 | 说明 |
| --- | --- | --- |
| `get_points_balance` | 无 | 查询积分余额，返回余额 JSON |
| `create_task` | `title`, `directory` | 创建任务会话，返回 `task_id` |
| `send_task_message` | `task_id`, `message` | 发送消息并执行任务（消耗积分） |
| `get_task_messages` | `task_id` | 读取任务的全部消息与结果 |

路由规则（按优先级）：

1. 消息含积分关键词（积分/余额/points/balance 等）→ `get_points_balance`
2. 含"创建任务/新建会话"等 → `create_task`
3. 含"读取结果/查看结果"等 → `get_task_messages`
4. 含"帮我/写/生成/修改/任务"等 → `send_task_message`
5. 均不匹配且声明了工具 → 消息直接转发给 DuMate 对话（消耗积分）

不声明任何工具时：积分关键词直接返回余额（不消耗积分），其余消息转发给 DuMate 对话。

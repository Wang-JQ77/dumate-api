# Changelog

## 1.2.0 - 2026-08-20

### Added
- `tools/wait_opencode.py`：等待 DuMate 桌面版 opencode 服务就绪，轮询自动发现端口（最多 90 秒）
- `start_points_api.bat` 三步骤启动流程：
  - **[1/3]** 检查 DuMate 桌面版 → 未运行时自动启动 → 等待 opencode 服务就绪
  - **[2/3]** 启动 8888 透传代理
  - **[3/3]** 启动 DuMate API 服务（8765）
- `CHANGELOG.md`：项目变更记录

### Fixed
- `dumate_client.discover_opencode_url()`：不再静默返回默认地址，先检测端口是否可用，不可用时抛出明确错误
- `points_api._chat_with_dumate()`：DuMate 重启导致会话失效时（404），自动重建会话并重试，不中断服务

## 1.1.0 - 2026-08-19

### Removed
- 清理 17 个非必要测试脚本和调试工具，保留回归测试脚本

### Fixed
- 测试脚本中硬编码的个人路径替换为相对路径 / 临时目录
- 移除 token.txt 中泄露的私密信息
- 启动脚本增加 Python 版本检查（需 3.10+）
- 修复特殊字符导致 token 生成失败的问题

## 1.0.0 - 2026-08-19

### Added
- 项目初始发布
- 积分查询 API（GET /api/points/balance）
- OpenAI 兼容接口（/v1/chat/completions, /v1/responses）
- Claude 兼容接口（/v1/messages）
- 任务执行 API（/api/tasks）
- 三种模型模式：Lite / Turbo / Ultra
- 透传代理自动适配
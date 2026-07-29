# OpenClaw + 微信（gotit P0 验收）

gotit **不实现**微信适配器。通道在 OpenClaw；gotit 只通过 MCP 暴露检验工具。

## 本机进度（2026-07-29）

已完成（开发机）：

- Node **22.23.1** + OpenClaw **2026.7.1-2**
- `openclaw setup --baseline`；`gateway.mode=local`
- 插件 `@tencent-weixin/openclaw-weixin` 已装且 `enabled=true`
- MCP `gotit` 已写入 `~/.openclaw/openclaw.json`；`openclaw mcp doctor gotit --probe` → **ok**
- Skill 链接：`~/.openclaw/workspace/skills/gotit` → 本仓库 `skills/gotit`

**P0 已验收（2026-07-29）：** 微信 ClawBot 私聊 `gotit_health` →「Gotit 服务状态正常，版本 0.1.0」。

可选后续：微信再验 `gotit_today`；编辑 `~/.openclaw/workspace/IDENTITY.md` / `USER.md` 定人设。

日常开终端前先：`source ~/.nvm/nvm.sh && nvm use 22`（或 `nvm alias default 22`）。

## 前置

| 项 | 要求 |
|----|------|
| Node | **22.22.3+**（当前默认 20 不够，用 nvm 切 22） |
| OpenClaw | 新装建议 `openclaw@latest`；微信插件 2.x 约需 ≥ 2026.3.22 / 2026.5.12 |
| 微信 App | **8.0.70+** |
| gotit | 本机可 `uv run gotit-mcp`；Postgres 等按日常开发已起 |

## 1. 安装 OpenClaw

```bash
# 推荐：nvm 切到 Node 22
source ~/.nvm/nvm.sh
nvm install 22
nvm use 22
nvm alias default 22   # 可选：以后默认 22

npm install -g openclaw@latest
openclaw --version

# 首次：引导装 daemon + 模型（交互）
openclaw onboard --install-daemon
# 或无引导安装后再手动配模型：
# curl -fsSL https://openclaw.ai/install.sh | bash -s -- --no-onboard
```

检查：

```bash
openclaw doctor
openclaw gateway status
```

## 2. 接入微信（腾讯官方插件）

```bash
# 一键
npx -y @tencent-weixin/openclaw-weixin-cli install

# 或手动
openclaw plugins install "@tencent-weixin/openclaw-weixin"
openclaw config set plugins.entries.openclaw-weixin.enabled true
openclaw gateway restart

# 同一台跑 Gateway 的机器上扫码
openclaw channels login --channel openclaw-weixin
```

手机微信扫终端二维码并确认。仅 **私聊**；群聊当前不在插件能力声明内。

若报版本过旧：

```bash
openclaw plugins install @tencent-weixin/openclaw-weixin@legacy
```

配对（陌生人私聊时）：

```bash
openclaw pairing list openclaw-weixin
openclaw pairing approve openclaw-weixin <CODE>
```

## 3. 挂载 gotit MCP

把下面写进 `~/.openclaw/openclaw.json`（字段名以你本机 `openclaw doctor` / 文档为准；常见为 `mcp.servers`）。**路径改成你的绝对路径**：

```json
{
  "mcp": {
    "servers": {
      "gotit": {
        "command": "uv",
        "args": [
          "run",
          "--directory",
          "/Users/zxr/workspace2026/gotit-ai",
          "gotit-mcp"
        ]
      }
    }
  }
}
```

重启 Gateway：

```bash
openclaw gateway restart
```

Skill：把本仓库 `skills/gotit/` 拷到 OpenClaw 的 skills 目录，或按 OpenClaw 文档做 workspace skill 链接，让助手优先调 gotit 工具而不是空聊。

## 4. 验收清单（P0 完成标准）

在微信里对助手发（或让它调工具）：

1. **连通**：调用 `gotit_health` → 返回 ok / 健康信息  
2. **今日**：调用 `gotit_today` → 能看到今日计划/待检（可为空列表）  
3. **频道**：`openclaw channels status --probe` 里微信为已连接  

本机辅助：

```bash
cd /Users/zxr/workspace2026/gotit-ai
uv run gotit-mcp   # 应保持 stdio；Ctrl+C 退出。确认二进制可起即可
openclaw plugins list
openclaw channels status --probe
```

## 5. 常见问题

| 现象 | 处理 |
|------|------|
| `openclaw: command not found` | Node/npm 全局 bin 不在 PATH；`nvm use 22` 后再试 |
| 插件要求更高 OpenClaw 版本 | `npm install -g openclaw@latest` 或装 `@legacy` 插件线 |
| Channel OK 但不收消息 | `plugins.entries.openclaw-weixin.enabled=true` + `gateway restart` |
| MCP 调不到 gotit | 检查 `uv` 在 Gateway 环境 PATH 内；`--directory` 用绝对路径 |
| 电脑休眠断连 | 系统设置防休眠，或后续用 OpenClaw「keep awake」类配置 |

## 边界

- **早晚简报（P1）** → [`docs/openclaw-digest.md`](openclaw-digest.md) + `skills/digest/`
- coding 遥控 / 面试提醒 → 后续 P2 / P3d，不在本页
- 勿在 `src/gotit/` 内增加微信 SDK 或频道路由

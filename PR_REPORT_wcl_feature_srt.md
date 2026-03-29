# PR 报告：wcl/feature(srt) 分支

## 基本信息
- **分支**: `wcl/feature(srt)`
- **源仓库**: `Oops-maker/Resonnet` (oops-maker 分支整理后)
- **目标仓库**: `TashanGKD/Resonnet`
- **PR 链接**: https://github.com/TashanGKD/Resonnet/pull/new/wcl/feature(srt)
- **Commits**: 5 个（从原 20 个 commits 按功能合并整理）
- **改动文件**: 15 个文件
- **代码量**: +948 行, -26 行
- **生成日期**: 2026-03-27

---

## 主要功能改动

### 1. 🏗️ Sandbox-Runtime (SRT) 沙箱隔离系统（核心功能）

SRT (Sandbox-Runtime) 是 Anthropic 的轻量级操作系统级沙箱工具。本 PR 将 SRT 集成到 Resonnet，为 MCP 服务器提供文件系统隔离。

**新增文件**:
| 文件 | 行数 | 说明 |
|------|------|------|
| `app/agent/srt_config.py` | +207 | SRT 配置生成器，动态构建沙箱策略 |
| `tests/test_srt_config.py` | +242 | SRT 配置单元测试 |
| `tests/test_srt_integration.py` | +64 | SRT 集成测试 |
| `tests/test_agent_links_runtime_srt.py` | +66 | Agent Links SRT 测试 |

**关键改动文件**:
- `app/agent/sandbox_exec.py` - 集成 SRT 作为默认沙箱后端
- `app/agent/discussion.py` - 支持 HTTP MCP 和 SRT 隔离的 MCP 服务器
- `app/services/agent_links_runtime.py` - Agent Links 运行时支持 SRT
- `Dockerfile` - 安装 Node.js 和 `@anthropic-ai/sandbox-runtime`
- `scripts/ci_local.sh` - CI 脚本支持 SRT

**安全策略**:
```python
# 文件系统隔离
- READ:  允许全局读取（Python 导入、运行时等需要）
- WRITE: 仅允许指定路径（topic workspace、IPC 目录、临时目录）

# 敏感文件保护（禁止读取）
- **/.env, **/.env.*
- ~/.ssh, ~/.gnupg, ~/.aws

# 网络隔离
- 默认允许所有域名（enableWeakerNetworkIsolation: true）
- 可选域名白名单严格模式
```

**环境变量**:
```bash
SANDBOX_USE_SRT=true        # 启用 SRT 沙箱（默认 true）
```

---

### 2. 🔍 语义搜索默认启用

- 新增 `ENABLE_SEMANTIC_SEARCH` 环境变量
- 默认值为 `true`，启用语义搜索功能
- 相关文件: `app/core/config.py`, `.env.example`

---

### 3. 🧪 测试修复

- `tests/test_agent_links_api.py` - 修复 `session_id` 和 `list_ids` 相关测试
- 确保测试与 profile-helper 的 session 管理保持一致

---

### 4. 📝 文档更新

| 文件 | 改动 |
|------|------|
| `docs/config.md` | 新增 SRT 环境变量配置说明 |
| `docs/sandbox-isolation.md` | Phase 3 SRT 集成文档 |
| `README.md` | 中文文档更新 SRT 和语义搜索说明 |
| `README.en.md` | 英文文档更新 SRT 和语义搜索说明 |

---

### 5. 🔧 其他维护

- `chore(libs): update libs meta JSON` - 更新库元数据格式
- Profile-helper sessions 小幅更新

---

## 技术架构

```
┌─────────────────────────────────────────┐
│           Discussion / Agent            │
├─────────────────────────────────────────┤
│  _load_mcp_servers_for_sdk()            │
│  ├── HTTP MCP Server (直接连接)         │
│  │   └── type: "http", url, headers     │
│  └── Stdio MCP Server (SRT 包装)        │
│       └── command: "srt"                │
│           args: ["--settings", config,   │
│                  original_cmd, ...]     │
├─────────────────────────────────────────┤
│  SRT 配置文件 (动态生成 per-invocation)  │
│  ├── 允许读写: topic workspace          │
│  ├── 允许读写: IPC 目录                  │
│  ├── 允许读写: OS 临时目录               │
│  ├── 允许读写: Claude/UV 状态目录        │
│  ├── 只读全局: Python 运行时等           │
│  └── 禁止读取: .env, .ssh, .aws 等      │
└─────────────────────────────────────────┘
```

---

## 部署影响

### Docker 构建
- 需要 Node.js 运行时
- 需要安装 `@anthropic-ai/sandbox-runtime` npm 包
- 已在 Dockerfile 中配置

### 环境配置
`.env.example` 新增：
```bash
# SRT 沙箱开关
SANDBOX_USE_SRT=true

# 语义搜索开关
ENABLE_SEMANTIC_SEARCH=true
```

### 向后兼容
- `SANDBOX_USE_SRT=false` 时回退到旧版沙箱后端
- 不强制要求 SRT 安装（ gracefully degrade）

---

## 审查建议

1. **安全审查**: 确认 SRT 文件系统策略是否满足安全要求
2. **功能测试**: 验证 MCP 服务器在 SRT 沙箱中的正常运行
3. **性能测试**: 评估 SRT 包装对 MCP 启动时间的影响
4. **Docker 构建**: 确认新 Dockerfile 构建通过

---

## Commits 整理说明

原 `oops-maker` 分支有 20 个 commits，已按功能合并为 5 个：

| Commit | 原 Commits | 功能 |
|--------|-----------|------|
| `450f665` | 9 个 | SRT 沙箱核心功能 |
| `93fc303` | 1 个 | 测试修复 |
| `3884b93` | 2 个 | Libs meta 更新 |
| `fe1ed2e` | 4 个 | 语义搜索功能 |
| `138ed27` | 4 个 | Profile-helper 更新 |

---

*报告生成时间: 2026-03-27*

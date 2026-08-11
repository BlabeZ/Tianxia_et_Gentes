# 机器 B 登记与冒烟测试记录

- 日期：2026-08-11
- 机器：B（Windows，Python 3.12.10）
- 执行：opencode 主 agent
- 依据：`协作/README.md`「OpenCode 权限冒烟验证」

## 一、机器 B 登记

- 创建 `.opencode/local.json`（gitignore）：`machine_id: B`，`os: windows`，外部路径均未配置（无 game_path，能力如实降级）。
- 启用入库 Git hooks：`git config core.hooksPath .githooks`，已验证输出 `.githooks`。
- 发布脱敏快照：`py -3 scripts/workflow.py env-check --publish` → `协作/环境/B.json`。
  - `profile: light`，`snapshot_status: missing`
  - `dialog_development: true`、`static_validation: true`
  - `snapshot_export: false`、`mod_execution: false`、`load_test: false`（无游戏本体路径，符合默认拒绝，不手填升级）
- 统一校验：`py -3 scripts/workflow.py validate` → PASSED。

## 二、单元测试（54 项）

首次运行 2 项失败，根因均为 Windows 专属：

1. `scripts/workflow.py` 中 `task_assign`/`commit_lease_and_create_branch` 使用 `str(path.relative_to(ROOT))`，Windows 返回反斜杠路径，与 git 输出的正斜杠路径比较失败（Linux 无此问题，CI 未覆盖）。修复：改为 `.as_posix()`（`scripts/workflow.py` 两处）。
2. `tests/test_workflow.py` 真实 git 仓库 helper 缺少 `encoding="utf-8", errors="replace"`，Windows 下 GBK 解码 git 中文路径输出失败。修复：与同文件另一 helper 对齐（`tests/test_workflow.py`）。

修复后 54/54 全部通过，`validate` 仍 PASSED。

## 三、OpenCode 权限冒烟验证（真实工具调用）

经 `opencode debug agent execute/verify` 核对解析后，通过 `opencode serve` + HTTP API 以对应 agent 身份发送消息，由服务端执行权限评估（日志含 `evaluated permission` 记录）。

| # | 检查项 | execute | verify | 证据 |
| --- | --- | --- | --- | --- |
| 1 | `py -3 scripts/workflow.py env-check` | 允许 | 允许 | 退出码 0，输出 machine_id: B |
| 2 | `git status --short` | 拒绝 | 拒绝 | 日志 `action.action=deny`，agent 如实报告未执行 |
| 3 | `validate --base <40位SHA> --head <40位SHA>` | — | 允许 | 命令执行并返回校验结果 |
| 4 | 写入非 `协作/审查记录/验证-*.md` 路径 | — | **未拒绝（漏洞）** | 经 `filesystem_write_file`（MCP）成功写入 `协作/state-overrides/冒烟测试.json`，日志 `permission=filesystem_write_file action.action=allow` |

### 发现的问题

**问题 1（安全边界漏洞，需决策修复）**：subagent 的 `edit` 权限 deny 只约束内置 `write/edit/apply_patch`；本机全局挂载的 filesystem MCP 提供 `filesystem_write_file` 等写工具，其权限键为工具名本身，落入 agent 配置首条 `"*": allow`，从而绕过 `edit: deny`。execute 与 verify 均受影响。测试产物已删除，工作区已还原。

**问题 2（历史遗留，非本次回归）**：`validate --base 5ed13b5… --head ac49e10…` 报告 5 个历史设定层 commit 未同 commit 登记修订记录 JSON：`0320d508931e`、`563526559106`、`9d36aefb5d68`、`5bc7c0749f31`、`e178b8f0e720`。AGENTS.md 允许历史遗留补登记。

## 四、遗留事项

- 待修复：问题 1（方案待用户决策）。
- 待补登：问题 2（5 个历史 commit 的修订记录登记）。
- 本机未提交改动：`协作/环境/B.json`（新机器快照）、`scripts/workflow.py`、`tests/test_workflow.py`（本次修复）。

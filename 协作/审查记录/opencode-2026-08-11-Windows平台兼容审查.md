# Windows 平台兼容性审查：Linux 端框架与脚本的可移植性

> 日期：2026-08-11｜审查者：opencode（机器 C / Ubuntu）｜状态：**仅记录，未执行任何修复**
> 触发：跨机协同（Windows 机器 A 全功能机 + Linux 机器 C 轻量机）开工前，评估 Linux 上编写的框架/脚本是否影响 Windows 开发。

## 一、结论

设计上跨平台安全（纯标准库零依赖、unittest 而非 pytest、统一 `py -3`/`python3` 双入口、git 输出固定 UTF-8、换行显式 `\n`、绝对路径判断用 `Pure*Path` 双规则、无 POSIX 专属模块、`os.X_OK` 检查带 `nt` 守卫、本体路径仅存机器本地 `local.json`）。

但存在 **2 个真实 Windows 专属缺陷** 和 **2 个风险点**，全部因验证仅在 Linux/CI(ubuntu) 完成而未被发现。

## 二、问题清单

### P1（高）路径分隔符不一致 → 机器 A 上 `task assign` 必然失败

- 证据：`task_assign` 的 `environment_relative = str(environment_path.relative_to(ROOT))`（workflow.py:1041）与 `commit_lease_and_create_branch` 的 `task_path/task_md_path/env_path = str(...relative_to(ROOT))`（workflow.py:896-898）在 Windows 上生成**反斜杠**路径；
- 这些字符串与 git 输出比对（`require_clean_main` 的 `git status --porcelain`、`commit_scoped_changes` 的 `git diff --cached`，均输出正斜杠），比对永不相等 → assign 报"工作区不干净"、租约提交报"提交范围异常"；
- T-015 新代码（`lifecycle_preflight` / `commit_task_state`）已用 `.as_posix()`，但 assign 路径仍为旧式 `str()`——新旧两套并存，未统一；
- 现有测试均在 Linux 临时 git 仓库运行，无法暴露。

### P2（高）无 `.gitattributes` → 机器 A 上 git hooks 可能失效

- 证据：`.githooks/pre-commit`、`.githooks/pre-push`、`.githooks/run-python` 为 POSIX sh 脚本（git for Windows 自带 sh，可执行）；仓库**无 `.gitattributes`**；
- 若机器 A `core.autocrlf=true`（Git for Windows 安装默认勾选），checkout 时脚本被转 CRLF → shebang 带 `\r` → pre-commit/pre-push 执行失败 → 提交/推送被莫名阻断；
- `协作/README.md:18-19` 已含 `git config core.hooksPath .githooks` 配置命令，但未提示 autocrlf 风险。

### P3（中）Python 版本未验证、未文档化

- 证据：workflow.py/state_transform.py 使用 PEP 604 语法（`str | None`，需 Python **3.10+**）；CI 仅验证 `python-version: "3.12"`（.github/workflows/workflow-integrity.yml:21）；AGENTS.md / 协作/README.md 均未写明版本要求；
- 机器 A 的 `py -3` 若为 <3.10 将直接语法错误。

### P4（中）CI 仅在 ubuntu 运行

- 证据：`.github/workflows/workflow-integrity.yml` 单一 `ubuntu-latest` job；
- P1/P2 等 Windows 专属问题 CI 永远无法拦截，"跨平台可运行"仅靠推断、无验证。

### P5（低）Windows 重定向输出编码（备选项）

- 证据：脚本输出含中文与 `→` 等字符；Windows 上 stdout 重定向到管道时用 locale 编码（cp936），当前字符集均可编码，风险极低；
- 保险措施：脚本入口加 `sys.stdout.reconfigure(encoding="utf-8")`（Python 3.7+），或文档提示 `PYTHONIOENCODING=utf-8`。

## 三、修复方案（待拍板，未执行）

| 编号 | 针对 | 方案 | 回归验证 |
| --- | --- | --- | --- |
| F1 | P1 | `task_assign` 的 `environment_relative` 与 `commit_lease_and_create_branch` 的 3 处路径变量改为 `.as_posix()`；并在 `require_clean_main`/`commit_scoped_changes` 内部将 `allowed_paths` 的 `\` 归一化为 `/`（双保险） | 新增反斜杠路径回归测试（Windows 风格路径模拟） |
| F2 | P2 | 新增 `.gitattributes`：`.githooks/* -text`（强制 LF）+ `* text=auto`；README 机器就绪清单补 autocrlf 建议（false 或 input） | CI 校验 `.githooks` 文件无 CRLF（或人工在 Windows checkout 后验证 hook 可执行） |
| F3 | P3 | README/AGENTS 机器就绪清单补"Python 3.10+（含 py launcher）"要求 | 机器 A `py -3 --version` |
| F4 | P4 | CI matrix 增 `windows-latest` job（unittest + validate，含 push 范围校验） | PR/push 双平台绿 |
| F5（可选） | P5 | 脚本入口 `sys.stdout.reconfigure(encoding="utf-8")` | Windows 重定向输出中文无乱码 |

## 四、执行状态

- 本记录仅归档问题与方案，**未修改任何代码/配置**（2026-08-11 记录时）；
- 修复属工作流/文件结构变更，按 `协作/决策协议.md` 须由用户拍板；拍板后登记 `协作/决策记录/D-YYYYMMDD-NNN.json` + 同名 md，并按 `协作/README.md` 领取修复任务执行；
- 建议执行顺序：F1 → F2 → F3 → F4 →（可选）F5。

## 五、验证证据（记录时点）

- `python3 scripts/workflow.py validate`：PASS；
- `python3 -m pytest tests/ -q`：47 passed, 6 subtests passed；
- `python3 scripts/workflow.py env-check`：C 机 light 档，能力派生正常；
- 本记录为 `协作/审查记录/` 新增文件，不在 CORE_PATTERNS 校验范围，不影响 validate。

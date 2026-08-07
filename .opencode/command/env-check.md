---
description: 任务开工前强制环境与能力自检（能力闸门）。所有 agent/subagent 启动第一步必跑。
agent: build
---

# 环境与能力自检（/env-check）

你是《天下与万邦》mod 项目的开工自检器。**任何任务开工前必须先跑本自检**，不得跳过。

## 步骤

1. 读 `.opencode/local.json`（若不存在→直接判 **light**，输出告警并停止长程/测试能力声明）。
2. 校验字段：
   - `game_path` 非空且路径存在（`test -d`）→ 该机具扫描+测试潜力
   - `game_path` 为 null 或路径不存在 → **强制 light**
   - `capability_mode` 必须与 game_path 可达性一致（不一致→以 game_path 实测为准并告警）
3. 跑 `git status --short` + `git pull --ff-only`（失败→告警：远程有新提交，先拉取再开工）。
4. 读 `协作/任务台账.md`，报告当前"进行中"任务（防止重复领取）。
5. 输出能力判定与开工许可：

```
== 环境自检 ==
machine_id: <值>
os: <值>
game_path 可达: <是/否>
capability_mode: <full|light>
封锁项: <light→long_running/scan/test；full→无>
git 状态: <clean/有改动/需拉取>
进行中任务: <列表或无>
→ 开工许可: <light=仅逐轮对话；full=可长程+扫描+测试>
```

## 默认拒绝（安全铁律）

- local.json 缺失/无效/game_path 不可达 → **一律 light**
- light 模式：**禁止** dispatch subagent·扫描、subagent·执行长程、加载测试；只允许逐轮对话式开发
- 不得在未跑 /env-check 前声明能力；不得未经用户显式确认把 light 升级为 full

## 失败处理

- game_path 声称 full 但路径不可达 → 告警并降级 light，请用户提供可达路径或确认 light
- git pull --ff-only 失败 → 告警，先解决远程新提交再开工
- 台账有"进行中"且非本机持有 → 告警并发起领取协议（见 `协作/README.md` 原子领取）

# Codex T-003 mod 工程骨架审查（2026-08-11）

## 审查范围

- 任务：`T-003`，lease generation `1`
- 基线：`41e6146b5ac69a5ee5d8d91405aea53f55743a6d`
- 任务 head：`d6f83c7bd279aa76d76b012a74a455e390cd299e`
- 交接单：`协作/交接单/T-003-g1.json`

## 结论

**静态审查通过，可进入待合并状态。** T-003 要求的工作区内 `mod/` 目录树、`descriptor.mod`、1910 开局 defines 三件套、默认书签和中英本地化均已建立，改动未触及游戏本体、已安装模组或用户目录。

这不是“可加载版本”结论：descriptor 已按阶段规划预留 `replace_path="history/states"`，但完整州文件须由后续 states 任务生成。机器 C 不具备 `mod_execution` 或 `load_test`，本次只确认 T-003 的静态交付；不得据此声称 HOI4 已成功加载。

## 依据核对

1. `docs/协作框架.md` 与其既有阶段 A 约定要求预建 `mod/` 目录、descriptor、defines 三件套、书签与 replace_path；任务产出与该范围一致。
2. `docs/mod_examples/01-工程结构与开发流程.md` 明确采用自命名 defines 文件、避免复制原版 `00_defines.lua`，并说明全量州重写使用 `replace_path="history/states"`；实装为 `zz_txg_defines.lua` 和最小单项接管。
3. `docs/mod_examples/07-地图与开局设定.md` 明确三项日期为 `1910.1.1.12`、`1950.1.1.1`、`1916.1.1.12`，并要求新增默认书签；实装逐项一致。
4. `协作/扫描产出.md` 已锁定“大顺帝国 → `CHI`”；书签只使用该既定 tag，没有填写尚待 T-008 决定的意识形态或其他未决设定。
5. 未修改 `Settings/` 或 `设定书/`，也未新增世界观决定，因此本任务不触发设定层修订记录或新 decision record。

## 已执行验证

- `python3 scripts/workflow.py validate`：通过。
- `python3 scripts/workflow.py validate --base 41e6146b... --head d6f83c7b...`：通过。
- `python3 -m unittest discover -s tests -v`：25 项通过。
- `git diff --check`：通过。
- 两个 localisation `.yml` 文件首字节均为 UTF-8 BOM（`EF BB BF`）。
- 完整提交区间的 changed files 与交接单一致；除任务租约台账外，任务实现文件全部位于 `mod/`。

## 后续限制

- `supported_version`、启动器外部 `.mod` 的绝对 `path`、`SAVE_VERSION` 和 `CHECKSUM_SALT` 尚未实装；这些值需在具备对应本体/部署能力的机器上按已验证的当前版本和实际纯 ASCII 路径填写，不得在机器 C 猜测。
- 完整 states 尚未落地时不得尝试把本骨架当作可加载发布包；T-004 及后续 states 流程仍受 `snapshot_export/mod_execution/load_test` 能力闸门约束。

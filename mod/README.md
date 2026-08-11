# Tianxia et Gentes mod 工程目录

本目录是《天下与万邦》的 HOI4 mod 交付根目录，与游戏本体目录保持隔离并由 Git 跟踪。

当前阶段只提供工程骨架：

- `descriptor.mod` 声明 mod 元数据，并预留由本项目全量接管的 `history/states`；
- `common/defines/zz_txg_defines.lua` 设置 1910 开局三项日期；
- `common/bookmarks/00_txg_bookmarks.txt` 提供 1910 默认书签；
- 其余目录以 `.gitkeep` 占位，供后续任务写入。

注意：`history/states` 尚未生成完整州文件时，本骨架不构成可加载版本。启动器使用的外部 `.mod` 文件及其本机绝对 `path` 不入库；需在具备 `mod_execution` 的机器上按实际纯 ASCII 部署路径生成。

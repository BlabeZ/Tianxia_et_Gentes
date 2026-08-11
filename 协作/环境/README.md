# 脱敏环境快照

每台机器运行：

```text
python3 scripts/workflow.py env-check --publish
```

Windows 使用 `py -3 scripts/workflow.py env-check --publish`。

生成 `协作/环境/<machine_id>.json`。该文件只包含分项能力、总体档位、本体版本或指纹、快照状态和检查时间，禁止写入任何绝对路径、用户名或凭据。

原始路径仍只存在于被 gitignore 的 `.opencode/local.json`。

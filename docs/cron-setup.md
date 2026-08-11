# 定时任务配置教程

## 使用前检查

1. 在交互式终端中确认四个脚本的 `--help` 可以运行。
2. 设置所需环境变量。
3. 先执行 `notion_bridge.py ... --dry-run`。
4. 用一个测试页面验证 Notion Integration 权限。
5. 确认调度器使用的 Python 和交互式终端一致。

## 脱敏任务结构

下面只展示结构。任务名称、时间、提示词和 ID 均为示例。

```json
{
  "id": "<CRON_JOB_ID>",
  "name": "晚间复盘示例",
  "schedule": "30 21 * * *",
  "timezone": "Asia/Shanghai",
  "command": "python scripts/notion_bridge.py daily --date <DATE> --dry-run",
  "enabled": false
}
```

## Windows 任务计划程序

程序填写 Python 可执行文件，参数填写脚本及其参数，起始目录填写仓库根目录。环境变量应配置在运行账户或安全的启动包装器中，不能直接写进参数栏。

示例参数：

```text
scripts/notion_bridge.py weekly --date 2026-08-08 --highlights "示例成果" --challenges "示例问题" --actions "示例行动" --dry-run
```

## Hermes Cron

建议先创建一个禁用状态的测试任务。提示词只引用脚本入口和预期输出，不复制个人背景、行为画像或生产页面结构。

配置完成后依次验证：

1. 手动触发一次。
2. 检查退出码。
3. 检查合成测试页面或 `--dry-run` 输出。
4. 删除测试页面。
5. 再启用正式时间表。

## 最小提示词样例

```text
读取指定时间窗口内的任务数据，按完成项、阻塞项和下一步行动生成 Markdown。
输出前检查空数据、重复任务和日期范围。
本次仅输出到标准输出，不写入外部系统。
```

## 上线检查

- 凭据只存在于安全环境变量中。
- 调度配置不含真实页面 ID、项目 ID或个人经历。
- 错误日志不会打印 Authorization 请求头。
- 测试任务默认关闭外部写入。
- `.env`、数据库和日志已被 `.gitignore` 排除。

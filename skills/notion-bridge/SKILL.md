---
name: notion-bridge
description: 将结构化任务或复盘内容转换成 Markdown，并通过环境变量配置的 Notion API 创建、追加或归档页面。适用于日周月复盘、任务归档、知识沉淀和 Notion 自动写入，同时要求 dry-run、权限检查和凭据隔离时。
---

# Notion Bridge

使用仓库 `scripts/notion_api.py` 和 `scripts/notion_bridge.py` 完成 Notion 写入。

## 安全约束

- 只从进程环境变量读取 `NOTION_API_KEY`。
- 页面 ID 从 `NOTION_PARENT_PAGE_ID` 或 `NOTION_DIARY_PAGE_ID` 读取。
- 不读取 Hermes 的 `.env`、`config.yaml`、数据库或日志。
- 不在输出中显示 token 或 Authorization 请求头。
- 默认先执行 `--dry-run`。

## 写入流程

1. 根据任务类型选择日、周、月或年模板。
2. 把输入整理成完成项、问题和下一步行动。
3. 使用 `--dry-run` 输出 Markdown。
4. 检查标题、日期、空项和敏感内容。
5. 确认目标页面已授权给 Notion Integration。
6. 去掉 `--dry-run` 执行写入。
7. 根据返回的页面 ID 确认创建成功，但不要把该 ID 写入仓库。

## 失败处理

- 401 时检查 token 是否有效且进入当前进程。
- 403 时检查目标页面共享权限。
- 404 时检查页面 ID 和 Integration 可见范围。
- 超时时保留输入，不自动重复创建页面。
- 创建页面成功但追加失败时，记录该状态并人工检查，避免产生重复页面。

## 输出质量

- 标题包含复盘类型和日期。
- 每个部分都能追溯到输入任务或用户确认的信息。
- 示例数据明确标注为合成示例。
- 不把未确认的判断写成事实。

---
name: scopesentry-mcp
description: "Manage ScopeSentry scans…"
version: 0.1.0
author: "trhhubsd (ARTEX), Hermes Agent"
license: AGPL-3.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [scopesentry, mcp, scanning, assets, recon]
    category: security
    related_skills: [hermesyf-authorized-assessment]
tier: archive
---

# ScopeSentry MCP 使用指南

面向已部署 ScopeSentry 实例的用户，通过 MCP 连接平台管理项目、任务、模板、资产、节点。资产数据可同步给 ARTEX 资产图，或作为评估目标的资产清单来源。

## When to Use
- 用户提到 ScopeSentry、扫描任务、资产查询、API Key 时
- 需要在评估前汇总某公司/项目的资产（域名、子域、IP、端口、站点、端点）
- 需要创建/下发扫描任务并跟进结果

## Prerequisites

- ScopeSentry Web 界面默认 `http://<主机>`，MCP 端点 `http://<主机>/mcp`（有反代以实际 `/mcp` 为准）
- API Key：登录 Web → API Key 管理页创建，保存 `ssk_...` 字符串（仅显示一次）
- MCP 客户端（Hermes 或 Cursor）配置：
```json
{
  "mcpServers": {
    "scopesentry": {
      "url": "http://<主机>:8082/mcp",
      "headers": { "X-API-Key": "ssk_你的密钥" }
    }
  }
}
```
也支持 `Authorization: Bearer <key>`。配置后确认工具列表出现 `list_projects`、`list_assets` 等。

## 工具一览

| 工具 | 用途 |
|---|---|
| `list_projects` | 按标签分组的项目树（含项目 ID） |
| `list_projects_data` | 分页项目列表，可按名称搜索 |
| `get_project` | 项目详情 |
| `create_project` | 新建项目 |
| `list_tasks` / `get_task` | 扫描任务列表 / 详情 |
| `list_scan_templates` / `get_scan_template` | 扫描模板列表 / 详情 |
| `list_plugin_modules` / `list_plugins` | 扫描流水线模块名 / 可用插件（含 hash、默认参数） |
| `create_scan_template` | 创建扫描模板 |
| `create_scan_task` | 创建扫描任务 |
| `list_assets` / `count_assets` | 查询资产（分页）/ 统计资产数量 |
| `get_asset_detail` | 资产或漏洞详情 |
| `add_asset_tag` | 为资产添加标签 |
| `list_nodes` | 扫描节点列表 |

各工具参数以 MCP 工具 schema 为准。`list_assets` / `count_assets` 的 search、filter 语法一致。需要「共多少条」时用 `count_assets`，不必为总数反复翻页 `list_assets`。

## 常用工作流

### 按项目查资产
项目条件已知时优先带 `filter.project` 缩小范围，避免跨项目数据过多。`filter.project` 必须是 ObjectID（用 `list_projects` 获取），不能写项目中文名。

```json
{
  "asset_type": "asset",
  "pageIndex": 1,
  "pageSize": 20,
  "search": "domain=^example.com",
  "filter": { "project": ["<项目ObjectID>"] }
}
```

### 创建扫描任务
`list_nodes` 取在线节点名 → `list_scan_templates` 取模板 ObjectID → `create_scan_task`（`name`、`node` 必填，`template` 填模板 ID 不能填模板名）。

**targetSource（与 Web 端一致）：**

| targetSource | 说明 | 必填参数 |
|---|---|---|
| `general` | 直接输入目标 | `target` |
| `project` | 从项目读取目标 | `project`（ObjectID 数组） |
| `asset` | 从 Web 资产库搜索 | `search`；可选 `project`、`filter`、`targetNumber` |
| `RootDomain` / `subdomain` / `UrlScan` | 从对应库搜索 | `search`；可选 `project`、`filter`、`targetNumber` |
| `*Source` | 资产页「选中/搜索」创建 | `targetTp=search` 用 `search`；`targetTp=select` 用 `targetIds` |

示例——直接扫根域名：
```json
{
  "name": "example-子域名收集",
  "node": ["node-1"],
  "template": "<模板ObjectID>",
  "targetSource": "general",
  "target": "example.com\nfoo.com",
  "project": ["<项目ObjectID>"]
}
```

### 根域名完整信息收集（推荐两阶段）
分布式任务以单个目标为单位分发，根域名作为目标时某节点扫出的子域名会继续在该节点执行后续模块，易负载不均。分两次：

1. **阶段1 仅子域名收集**：`targetSource: general`，模板仅启用 `SubdomainScan`、`SubdomainSecurity`
2. **阶段2 后续模块**：`targetSource: subdomain`，`search: task=="<阶段1任务名>"`，模板含端口/资产/漏洞扫描（可去掉 SubdomainScan）

### 创建扫描模板
`list_plugin_modules` 取模块名 → `list_plugins`（可按 `module` 过滤）取插件 hash 与默认参数 → `create_scan_template` 用 `modules` 指定「模块 → 插件 hash 数组」。

## 资产查询（list_assets / count_assets）

### asset_type
`asset`、`RootDomain`、`subdomain`、`app`、`mp`、`UrlScan`、`SensitiveResult`、`DirScanResult`、`crawler`、`vulnerability`、`PageMonitoring`、`IPAsset`、`SubdomainTakerResult`

别名：`web`→asset、`vuln`→vulnerability、`ip`→IPAsset、`url`→UrlScan

### search 搜索表达式（自定义 DSL，不是 SQL）

| 运算符 | 含义 | 索引 | 示例 |
|---|---|---|---|
| `=` | 模糊匹配（regex） | 不走索引 | `domain=example` |
| `==` | 精确匹配（全等） | 走索引 | `port==443` |
| `!=` | 排除 | — | `port!="80"` |
| `&&` / `\|\|` | 与 / 或 | — | `domain==example.com && port==443` |

已建索引字段（domain/ip/port/title 等）仅 `==` 全等或 `^` 前缀匹配能走索引；`=` 转 regex 模糊匹配，数据量大时变慢。

**所有类型通用 search 字段**：`tag`、`task`（任务名称）、`rootDomain`。**project 不能写在 search 里**，筛项目用 `filter.project`。

各 asset_type 常用 search 字段见 references/reference.md。

### filter 精确过滤
JSON 对象：同 key 多值为 OR，不同 key 为 AND。关键 key：`project`（ObjectID）、`task`（任务名）、`port`、`service`、`app`、`icon`、`statuscode`、`status`、`level`（critical/high/medium/low/info）、`type`、`color`、`sname`、`tags`。

```json
{"project": ["<项目ObjectID>"], "port": ["443"]}
```

### 排序 sort
仅 `UrlScan`、`DirScanResult` 支持：`{"length": "ascending"}`，其他类型忽略。

## 扫描模板模块名
`TargetHandler`、`SubdomainScan`、`SubdomainSecurity`、`PortScanPreparation`、`PortScan`、`PortFingerprint`、`AssetMapping`、`AssetHandle`、`URLScan`、`WebCrawler`、`URLSecurity`、`DirScan`、`VulnerabilityScan`、`PassiveScan`

## 故障排查

| 现象 | 处理 |
|---|---|
| MCP 无工具 | 检查 URL、API Key、ScopeSentry 是否运行 |
| 401 / 403 | 重新创建或更换 API Key |
| 资产查不到 | 确认 `filter.project` 为 ObjectID；勿在 search 写 project |
| 模板/任务创建失败 | `template` 必须是模板 ObjectID；`node` 填在线节点名 |
| 查询很慢/卡住 | 有项目时加 `filter.project`；search 对已索引字段改用 `==` 或 `^` 前缀，少用 `=`；缩小 `pageSize` |

![links_status](./static/favicon.ico)

  # Links Status

  精简版友链状态检测与 RSS 文章聚合工具


## 项目简介

本项目是基于 [Friend-Circle-Lite](https://github.com/willow-god/Friend-Circle-Lite) 修改的精简版本，移除了邮件通知、合并功能等复杂特性，专注于核心功能：

- **RSS 文章抓取**：自动爬取友链 RSS，聚合最新文章
- **友链状态检测**：定时检测友链可访问性
- **简约前端展示**：卡片式布局，响应式设计
- **GitHub Actions 部署**：无需服务器，全自动运行

## 功能特性

- RSS 文章自动抓取与聚合
- 友链可访问性检测（支持备用 API）
- 简约现代的前端展示页面
- GitHub Actions 运行，零服务器成本
- 响应式设计，适配各种设备

## 项目结构

```
.
├── .github/workflows/     # GitHub Actions 工作流
├── links_status/          # 核心代码模块
│   ├── __init__.py        # 请求头配置
│   ├── all_friends.py     # RSS 抓取处理
│   ├── link_status.py     # 友链状态检测
│   └── utils/             # 工具函数
├── static/                # 静态文件
│   ├── index.html         # 前端展示页面
│   ├── all.json           # 文章数据输出
│   └── status.json        # 友链状态输出
├── conf.yaml              # 配置文件
└── run.py                 # 主入口
```

## 快速开始

### 1. Fork 仓库

点击右上角 Fork 按钮，将仓库复制到你的 GitHub 账号下。

### 2. 配置权限

进入仓库 `Settings` -> `Actions` -> `General`，拉到最下方，勾选 **Read and write permissions**，保存。

### 3. 修改配置

编辑 `conf.yaml` 文件：

```yaml
# 爬虫配置
spider_settings:
  enable: true
  json_url: "https://your-domain.com/friend.json"  # 你的友链 JSON 地址
  article_count: 5                                   # 每个友链保留文章数

# 友链状态检测
link_status:
  enable: true
  timeout: 30
  max_attempts: 3
  use_backup_api: true
  backup_api_urls:
    - "https://v1.nsuuu.com/api/netCheck"
    - "https://v1.nsuuu.com/api/status"
```

### 4. 运行 Action

进入 `Actions` 页面，手动运行 workflow，或等待定时触发。

### 5. 部署页面

使用 GitHub Pages 或其他静态托管服务部署 `static` 目录。

## 友链 JSON 格式

你的友链页面需要提供如下格式的 JSON：

```json
{
  "friends": [
    ["站点名称", "https://example.com", "https://example.com/avatar.png"],
    ["站点名称2", "https://example2.com", "https://example2.com/avatar.png"]
  ]
}
```

## 配置说明

### spider_settings

| 参数 | 说明 |
|-----|------|
| `enable` | 是否启用文章抓取 |
| `json_url` | 友链 JSON 文件地址 |
| `article_count` | 每个友链抓取的文章数量 |

### link_status

| 参数 | 说明 |
|-----|------|
| `enable` | 是否启用友链状态检测 |
| `timeout` | 请求超时时间（秒） |
| `max_attempts` | 最大重试次数 |
| `use_backup_api` | 是否使用备用 API 检测 |
| `backup_api_urls` | 备用 API 地址列表 |

## 本地预览

```bash
# 进入项目目录
cd links-pyq-status-main

# 使用 Python 启动本地服务器
python -m http.server 8080

# 访问 http://localhost:8080/static/
```

## 技术栈

- **后端**: Python 3.x + curl + feedparser
- **前端**: 原生 HTML + CSS + JavaScript
- **部署**: GitHub Actions

## 注意事项

- **JSON 数据获取**：使用 `curl` 命令获取友链 JSON 数据，支持 5 次自动重试
- **RSS 抓取**：自动探测各站点的 RSS 地址并抓取文章
- **GitHub Actions**：建议在 Workflow 中启用 `actions/checkout` 和 `actions/setup-python`

## 许可证

MIT License

## 致谢

- 原项目 [Friend-Circle-Lite](https://github.com/willow-god/Friend-Circle-Lite) by willow-god

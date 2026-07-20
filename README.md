<div align="center">

# 🀄 ChineseIdomWordle · 成语 Wordle

**中文成语版 Wordle 猜词游戏 — 候选字组合 · 多难度 · 每日挑战**

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vanilla JS](https://img.shields.io/badge/Frontend-Vanilla%20JS-f7df1e?style=flat-square&logo=javascript)](https://developer.mozilla.org/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python)](https://www.python.org/)

[物化技 P.C.T.G.](https://github.com/P-C-T-Group) 

</div>

---

## 📖 项目简介

ChineseIdomWordle 是一款中文成语版 Wordle 猜词游戏。与原版 Wordle 不同，中文汉字数量庞大且键盘输入不便，本游戏采用**候选字选择**的方式：每局提供一组打乱的汉字（包含目标字和干扰字），玩家从中选字组合成四字成语进行猜测，通过颜色反馈逐步逼近答案。

### ✨ 核心特性

- 🎯 **三档难度** — 简单、中等、困难
- 📅 **每日挑战 + 无限模式** — 每日模式以日期为种子，全站当天同一题
- 💡 **提示系统** — 每局均可获取提示（某个字拼音 → 成语释义）
- 🔓 **揭晓答案** — 可放弃并查看答案（判负）
- 📊 **本地历史记录** — 自动保存最近 50 局战绩与统计
- 🌓 **深浅色主题** — 跟随系统 / 手动切换
- 🔐 **Token 鉴权** — 支持全局 Bearer Token 认证，可配置关闭
- � **排行榜系统** — 总榜（胜利数/胜率/平均回合）和每日挑战日榜，分难度排名
- 🛡️ **自动清理** — 过期对局、不活跃用户、日榜自动清理
- 📡 **REST API** — 前后端分离架构

---

## 🖼️ 游戏玩法

1. 选择**模式**（日常挑战 / 无限模式）和**难度**（简单 / 中等 / 困难），点击开始
2. 从下方候选字区点选 4 个字组成成语，点击「提交」
3. 根据颜色反馈判断：
   - 🟢 **绿色** — 字和位置都正确
   - 🟡 **黄色** — 字在成语中但位置不对
   - ⚪ **灰色** — 字不在成语中
4. 在限定轮次内猜出目标成语即为胜利
5. 卡住了？可以使用「提示」或「揭晓答案」

---

## 🏗️ 技术栈

| 层级 | 技术 |
|------|------|
| **后端** | Python 3.10+ · FastAPI · Pydantic v2 · Uvicorn |
| **前端** | Vanilla JavaScript · HTML5 · CSS3（CSS 变量主题） |
| **数据** | JSON 成语库（按难度分级）· SQLite（默认）/ MySQL |
| **鉴权** | SHA-256 Token 摘要校验 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip3

### 一键启动

项目使用统一入口，支持同域部署前端静态文件+后端API：

```bash
# 首次启动会自动初始化
bash start.sh
# 或直接
python run.py
```

游戏主页：http://127.0.0.1:8000/

**重新初始化前端配置**（修改API地址或Token后，不影响数据库）：
```bash
python run.py --reinit
```

### 配置

所有配置项已统一到项目根目录 `config.toml`（TOML 格式）。首次使用请从模板复制：

```bash
cp config.example.toml config.toml
```

主要配置分类：

| 分类 | 配置项 | 默认值 |
|------|--------|--------|
| **数据库** | 类型 / SQLite 路径 / MySQL 连接 | mysql / 见配置 |
| **鉴权** | 全局鉴权开关 / 管理员 Token 哈希 | 开启 / 见模板 |
| **游戏设置** | 三难度的最大轮数、候选字数、最大提示数（≤5） | 见模板 |
| **成语库** | 难中易三档成语库路径、干扰字库路径 | `data/*.json` |
| **日志** | 级别 / 目录 / 文件名 / 轮转份数 | INFO / `backend/logs` / `app.log` / 10 |
| **安全** | CORS 来源 / 可信代理 IP（支持`["*"]`通配） / 管理员白名单 IP | `["*"]` / `["127.0.0.1"]` / 不限制 |
| **清理** | 自动清理开关 / 对局保留天数 / 清理间隔 | 开启 / 30天 / 1小时 |
| **排行榜** | 上传最低局数 / 追加最低新局数 / 不活跃清理天数 / 显示名次上限 / Cookie有效期 | 20局 / 5局 / 90天 / 100名 / 365天 |
| **前端** | 监听地址 / 启动模式 / 前端Token | 127.0.0.1:8000 / default（全栈） / test-token |

> 敏感项（数据库密码、管理员 Token 哈希等）也可通过环境变量覆盖，优先级高于 `config.toml`。

### Token 鉴权配置

后端默认启用 Token 鉴权，玩家 Token 统一存储在数据库的 tokens 表中并实时生效；管理员 Token 摘要通过 `config.toml` 中的 `auth.admin_token_hash` 配置。

- **关闭鉴权**：在 `config.toml` 中设置 `auth.enabled = false`，后端将直接放行所有请求。
- **添加/管理 Token**：通过管理员接口 `/api/admin/tokens`（需管理员权限）进行添加、查询与删除，数据库更改实时生效。
- **前端Token**：默认使用 `test-token`，已自动通过初始化脚本添加到数据库。

### 排行榜功能

排行榜功能支持：
- 完成20局以上即可上传战绩创建存档，获得专属用户ID
- 总榜分三种排序：胜利数、胜率、平均取胜回合，按难度分别排名
- 每日挑战日榜，按取胜回合数排序，每日0点清空
- Cookie识别用户终端，支持追加新战绩（至少5局新记录）
- 显示IP归属地，支持用户自主删除存档
- 管理员可删除任意用户存档、手动清空日榜

---

## 📁 项目结构

```text
ChineseIdomWordle/
├── run.py                     # 统一启动入口（前端+后端同域部署）
├── start.sh                   # 一键启动脚本
├── config.toml                # 统一配置（TOML格式，gitignore）
├── config.example.toml        # 配置模板
├── backend/                   # 后端服务（FastAPI）
│   ├── app/
│   │   ├── main.py            # FastAPI 入口，中间件、后台清理任务
│   │   ├── core/              # 核心模块
│   │   │   ├── models.py      # Pydantic 模型（Idiom, Game, CharFeedback）
│   │   │   ├── feedback.py    # 猜测反馈算法（绿/黄/灰判定）
│   │   │   ├── candidate.py   # 候选字生成逻辑
│   │   │   ├── config.py      # 统一配置加载器（TOML + 环境变量）
│   │   │   ├── ip_region.py   # IP归属地查询（ip2region离线库）
│   │   │   ├── logging_setup.py # 日志配置
│   │   │   └── security.py    # 安全工具（IP/CIDR校验、真实IP解析、管理员鉴权）
│   │   ├── schemas/           # 请求/响应 Schema
│   │   │   ├── game.py        # 游戏数据模型
│   │   │   ├── leaderboard.py # 排行榜数据模型
│   │   │   ├── config.py      # 配置 Schema
│   │   │   └── DB.py          # 数据库配置模型
│   │   ├── services/          # 业务逻辑与路由
│   │   │   ├── game_service.py # 游戏核心逻辑
│   │   │   ├── leaderboard_service.py # 排行榜业务逻辑
│   │   │   └── routes.py      # API 路由定义
│   │   └── database/          # 数据库相关
│   │       ├── db_manager.py  # 数据库管理器（SQLite/MySQL抽象层）
│   │       ├── initDB.py      # 数据库初始化脚本
│   │       └── init.sql       # SQLite 建表 SQL
│   ├── tests/                 # 单元测试
│   ├── logs/                  # 运行日志
│   └── requirements.txt       # Python依赖列表
├── client/                    # 前端（纯静态）
│   ├── index.html             # 游戏主页
│   ├── css/                   # 样式（含深浅色主题）
│   ├── js/
│   │   ├── indexScript.js     # 主游戏脚本（含日榜自动提交）
│   │   ├── dialog.js          # 对话框组件
│   │   ├── top.js             # 排行榜页脚本
│   │   └── help.js            # 帮助页脚本
│   ├── help/                  # 游戏帮助页
│   ├── top/                   # 排行榜页
│   ├── icons/                 # 图标资源
│   └── .well-known/           # 域名验证/SSL证书目录
├── data/                      # 数据文件
│   ├── easy.json              # 简单成语库
│   ├── medium.json            # 中等成语库
│   ├── hard.json              # 困难成语库
│   ├── character.json         # 干扰字库
│   └── ip2region.xdb          # IP归属地离线数据库
├── docs/                      # 文档
│   ├── ARCHITECTURE.md        # 架构说明
│   ├── DESIGN.md              # 设计文档
│   └── api/                   # API文档（自动生成YAML）
│       ├── admin/             # 管理员接口文档
│       └── README.md          # 接口索引
└── tool/                      # 构建工具
    ├── obfuscate.js           # JS混淆脚本
    └── package.json
```

---

## 📡 API 概览

### 游戏接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/games` | 创建新游戏 |
| `POST` | `/api/games/{game_id}/guesses` | 提交猜测 |
| `GET` | `/api/games/{game_id}` | 获取游戏状态 |
| `GET` | `/api/games/{game_id}/hints` | 使用提示 |
| `GET` | `/api/games/{game_id}/reveal` | 揭晓答案（判负） |

### 排行榜接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/leaderboard/upload` | 首次上传战绩创建存档（需20局） |
| `POST` | `/api/leaderboard/append` | 追加新战绩（需≥5局新记录） |
| `POST` | `/api/leaderboard/daily/submit` | 提交每日挑战成绩到日榜 |
| `GET` | `/api/leaderboard/{difficulty}` | 获取用户总榜 |
| `GET` | `/api/leaderboard/{difficulty}/daily` | 获取每日挑战日榜 |
| `GET/DELETE` | `/api/leaderboard/profile/me` | 获取/删除个人存档 |

### 管理员接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET/POST` | `/api/admin/tokens/*` | Token管理（添加/查询/删除） |
| `GET` | `/api/admin/config/reload` | 热重载配置 |
| `POST` | `/api/admin/config/clean` | 立即清理过期对局 |
| `GET/POST` | `/api/admin/leaderboard/*` | 排行榜管理（查询/删除用户/清空日榜/清理不活跃用户） |

> 📄 **在线API文档**: 请前往[ChineseIdomWordle by PCTG](https://doc.wordle.whj.zdeweb.cn)查看最新版本 API 文档。项目内文档仅供存档。

---

## 🧪 测试

```bash
cd backend
pytest tests/
```

---

## 👥 开发团队

**物化技（P.C.T.G.）** — [@P-C-T-Group](https://github.com/P-C-T-Group)

贡献者：
- [@GZYZhy](https://github.com/GZYZhy)
- [@mywddbks](https://github.com/mywddbks)

---

## 📄 License

[MIT License](LICENSE) © 2026 物化技（P.C.T.G.）

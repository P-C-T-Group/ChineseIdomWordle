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

### 启动后端

使用提供的脚本：

```bash
cd backend
bash pullUpServer.sh
```

启动后：
- API 根地址：`http://127.0.0.1:8000`

### 配置

后端所有可配置项已统一到 `backend/config.toml`（TOML 格式）。首次使用请从模板复制：

```bash
cd backend
cp config.example.toml config.toml
```

可配置项包括：

| 分类 | 配置项 | 默认值 |
|------|--------|--------|
| **数据库** | 类型 / SQLite 路径 / MySQL 连接 | sqlite / `data/wordle.db` |
| **鉴权** | 全局鉴权开关 / 管理员 Token 哈希 / 玩家 Token（存储于数据库 tokens 表） | 开启 / 空 / （见 config.toml 中 auth.admin_token_hash） |
| **游戏设置** | 三难度的最大轮数、候选字数、最大提示数（≤5） | 见模板 |
| **成语库** | 难中易三档成语库路径、干扰字库路径 | `data/*.json` |
| **日志** | 级别 / 目录 / 文件名 / 轮转份数 | INFO / `logs` / `app.log` / 10 |
| **安全** | CORS 来源 / 可信代理 IP / 管理员白名单 IP | `["*"]` / `["127.0.0.1"]` / 不限制 |

> 敏感项（数据库密码、管理员 Token 哈希等）也可通过环境变量覆盖，优先级高于 `config.toml`。支持的变量名见 `backend/.env.example`。

### 启动前端

前端为纯静态页面，直接用浏览器打开 `client/index.html` 即可，或使用任意静态文件服务器：

```bash
cd client
python3 -m http.server 3000
# 然后访问 http://127.0.0.1:3000
```

### Token 鉴权配置

后端默认启用 Token 鉴权，玩家 Token 统一存储在数据库的 tokens 表中并实时生效；管理员 Token 摘要通过 `config.toml` 中的 `auth.admin_token_hash` 配置。

- **关闭鉴权**：在 `config.toml` 中设置 `auth.enabled = false`，后端将直接放行所有请求。
- **添加/管理 Token**：通过管理员接口 `/api/admin/tokens`（需管理员权限）进行添加、查询与删除，数据库更改实时生效。

前端默认使用 `test-token` 作为 Bearer Token，对应摘要已预置在文件中。

---

## 📁 项目结构

```text
ChineseIdomWordle/
├── backend/                    # 后端服务（FastAPI）
│   ├── app/
│   │   ├── main.py            # FastAPI 入口，CORS、鉴权中间件
│   │   ├── core/              # 核心数据模型与算法
│   │   │   ├── models.py      # Pydantic 模型（Idiom, Game, CharFeedback）
│   │   │   ├── feedback.py    # 猜测反馈算法（绿/黄/灰判定）
│   │   │   ├── candidate.py   # 候选字生成逻辑
│   │   │   ├── config.py      # 统一配置加载器（TOML + 环境变量覆盖）
│   │   │   ├── logging_setup.py # 日志配置（根据 config.toml 初始化）
│   │   │   └── security.py    # 安全工具（IP/CIDR 校验、客户端 IP 解析）
│   │   ├── schemas/           # 请求/响应 Schema
│   │   │   ├── game.py        # 游戏信息数据模型/字典
│   │   │   ├── config.py      # 统一配置 Schema（Pydantic 模型）
│   │   │   └── DB.py          # 数据库配置模型（兼容导出）
│   │   ├── services/          # 业务逻辑与路由
│   │   │   ├── game_service.py # 游戏核心逻辑
│   │   │   └── routes.py      # API 路由定义
│   │   └── database/          # 数据库相关
│   │       ├── db_manager.py  # 数据库管理器（SQLite/MySQL 抽象层）
│   │       ├── initDB.py      # 数据库初始化脚本
│   │       └── init.sql       # SQLite 建表 SQL
│   ├── tests/                 # 单元测试
│   ├── logs/                  # 运行日志
│   ├── requirements.txt       # 依赖列表
│   ├── config.example.toml    # 统一配置模板（TOML）
│   ├── config.toml            # 实际配置（gitignore，需从模板复制）
│   ├── token-sha256.txt       # 合法 Token 摘要
│   └── pullUpServer.sh        # 一键启动脚本
├── client/                    # 前端（纯静态）
│   ├── index.html             # 游戏主页
│   ├── css/                   # 样式（含深浅色主题）
│   ├── js/                    # 游戏逻辑
│   │   ├── indexScript.js     # 主游戏脚本
│   │   ├── dialog.js          # 对话框组件
│   │   ├── top.js             # 排行榜页脚本
│   │   └── help.js            # 帮助页脚本
│   ├── help/                  # 游戏帮助页
│   ├── top/                   # 排行榜/日志页
│   └── icons/                 # 图标资源
├── data/                      # 成语数据
│   ├── easy.json              # 简单成语库
│   ├── medium.json            # 中等成语库
│   ├── hard.json              # 困难成语库
│   └── character.json         # 干扰字库
├── docs/                      # 文档
│   ├── ARCHITECTURE.md        # 架构说明
│   ├── DESIGN.md              # 设计文档
│   └── api/                   # API 接口文档（存档）
├── tool/                      # 构建/混淆工具
├── CODEOWNERS
├── LICENSE
└── README.md
```

---

## 📡 API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/games` | 创建新游戏 |
| `POST` | `/api/games/{game_id}/guesses` | 提交猜测 |
| `GET` | `/api/games/{game_id}` | 获取游戏状态 |
| `GET` | `/api/games/{game_id}/hints` | 使用提示 |
| `GET` | `/api/games/{game_id}/reveal` | 揭晓答案（判负） |
| `GET` | `/api/admin/reloadTokens` | 热加载 Token 摘要（Admin） |

> 还有更多，请查看在线 API 文档。
> 📄 在线 API 文档：[ChineseIdomWordle API by 物化技](https://doc.wordle.whj.zdeweb.cn)
> （`docs/api/` 目录下的 YAML 文件仅作存档）

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

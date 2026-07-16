<div align="center">

# 🀄 ChineseIdomWordle · 成语 Wordle

**中文成语版 Wordle 猜词游戏 — 候选字组合 · 多难度 · 每日挑战**

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Vanilla JS](https://img.shields.io/badge/Frontend-Vanilla%20JS-f7df1e?style=flat-square&logo=javascript)](https://developer.mozilla.org/docs/Web/JavaScript)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?style=flat-square&logo=python)](https://www.python.org/)

[物化技 P.C.T.G.](https://github.com/P-C-T-Group) 出品

</div>

---

## 📖 项目简介

ChineseIdomWordle 是一款中文成语版 Wordle 猜词游戏。与原版 Wordle 不同，中文汉字数量庞大且键盘输入不便，本游戏采用**候选字选择**的方式：每局提供一组打乱的汉字（包含目标字和干扰字），玩家从中选字组合成四字成语进行猜测，通过颜色反馈逐步逼近答案。

### ✨ 核心特性

- 🎯 **三档难度** — 简单（10 候选字 / 12 轮）、中等（14 候选字 / 10 轮）、困难（20 候选字 / 8 轮）
- 📅 **每日挑战 + 无限模式** — 每日模式以日期为种子，全站当天同一题
- 💡 **提示系统** — 每局最多 2 次提示（拼音首字 → 释义）
- 🔓 **揭晓答案** — 可随时放弃并查看答案（判负）
- 📊 **本地历史记录** — 自动保存最近 50 局战绩与统计
- 🌓 **深浅色主题** — 跟随系统 / 手动切换
- 🔐 **Token 鉴权** — 支持全局 Bearer Token 认证，可配置关闭
- 📡 **REST API** — 前后端分离架构，API 文档自动生成

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
| **数据** | JSON 成语库（按难度分级）· 内存存储 |
| **鉴权** | SHA-256 Token 摘要校验 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip3

### 启动后端

```bash
cd backend
pip3 install -r requirements.txt
mkdir -p logs
uvicorn app.main:app --reload --port 8000
```

或使用提供的脚本：

```bash
cd backend
bash pullUpServer.sh
```

启动后访问：
- API 根地址：`http://127.0.0.1:8000`
- 自动生成文档（Swagger UI）：`http://127.0.0.1:8000/docs`
- ReDoc 文档：`http://127.0.0.1:8000/redoc`

### 启动前端

前端为纯静态页面，直接用浏览器打开 `client/index.html` 即可，或使用任意静态文件服务器：

```bash
cd client
python3 -m http.server 3000
# 然后访问 http://127.0.0.1:3000
```

### Token 鉴权配置

后端默认启用 Token 鉴权，合法 Token 的 SHA-256 摘要存储在 `backend/token-sha256.txt` 中（每行一个）。

- **关闭鉴权**：清空 `token-sha256.txt` 文件内容（保留空文件），后端将自动关闭全局校验
- **添加 Token**：计算 Token 的 SHA-256 摘要，追加到文件中，无需重启即可通过 `/api/admin/reloadTokens` 热加载

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
│   │   │   └── candidate.py   # 候选字生成逻辑
│   │   ├── schemas/           # 请求/响应 Schema
│   │   │   ├── game.py        # 含输入校验（4字汉字验证）
│   │   │   └── DB.py
│   │   ├── services/          # 业务逻辑与路由
│   │   │   ├── game_service.py # 游戏核心逻辑
│   │   │   └── routes.py      # API 路由定义
│   │   └── database/          # 数据库相关（初始化脚本）
│   ├── tests/                 # 单元测试
│   ├── logs/                  # 运行日志
│   ├── requirements.txt
│   ├── uvicorn_config.json    # 日志配置
│   ├── token-sha256.txt       # 合法 Token 摘要
│   └── pullUpServer.sh        # 一键启动脚本
├── client/                    # 前端（纯静态）
│   ├── index.html             # 游戏主页
│   ├── css/                   # 样式（含深浅色主题）
│   ├── js/                    # 游戏逻辑
│   │   ├── indexScript.js     # 主游戏脚本
│   │   ├── dialog.js          # 自定义对话框组件
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

主要负责人：
- [@GZYZhy](https://github.com/GZYZhy)
- [@mywddbks](https://github.com/mywddbks)

---

## 📄 License

[MIT License](LICENSE) © 2026 物化技（P.C.T.G.）

# 架构与项目结构

## 整体架构

前后端分离，通过 REST API 通信，Bearer Token 鉴权。

```text
┌──────────────┐    HTTP/JSON     ┌──────────────────┐
│   Frontend   │ ───────────────▶ │  Backend (FastAPI)│
│  (Vanilla JS)│ ◀─────────────── │   Python 3.10+   │
└──────────────┘   JSON Response  └──────────────────┘
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │  JSON 数据文件 │
                                  │ (成语库/干扰字) │
                                  └──────────────┘
```

前端为纯静态页面（HTML/CSS/JS），后端为 FastAPI 服务，游戏数据存储在内存字典中，成语库从 JSON 文件加载。

---

## 后端结构

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口：CORS 中间件、Token 鉴权、全局异常处理、日志
│   ├── core/                   # 核心数据模型与算法
│   │   ├── __init__.py
│   │   ├── models.py           # Pydantic 模型（Idiom, Game, CharFeedback, Difficulty, GameMode）
│   │   ├── feedback.py         # 猜测反馈算法（correct/present/absent 判定）
│   │   └── candidate.py        # 候选字生成逻辑（按难度抽取干扰字）
│   ├── schemas/                # 请求/响应 Schema（Pydantic v2）
│   │   ├── __init__.py
│   │   ├── game.py             # CreateGame/Guess/Hint/Reveal/GameState 等请求响应模型
│   │   └── DB.py               # 数据库相关 Schema
│   ├── services/               # 业务逻辑与路由
│   │   ├── __init__.py
│   │   ├── game_service.py     # 游戏核心逻辑（加载成语、创建游戏、提交猜测、提示、揭晓）
│   │   └── routes.py           # API 路由定义（/api/games 等端点）
│   └── database/               # 数据库相关
│       ├── __init__.py
│       ├── init.sql            # 数据库初始化 SQL
│       └── initDB.py           # 数据库初始化脚本
├── tests/                      # 单元测试
│   ├── __init__.py
│   └── test_feedback.py        # 反馈算法单元测试
├── logs/                       # 运行日志（按日期轮转）
├── requirements.txt            # Python 依赖
├── uvicorn_config.json         # Uvicorn 日志格式配置
├── token-sha256.txt            # 合法 Bearer Token 的 SHA-256 摘要（每行一个）
└── pullUpServer.sh             # 一键启动脚本
```

### 后端模块职责

| 模块 | 职责 |
|------|------|
| `main.py` | 应用入口，注册路由、CORS 中间件、Token 鉴权中间件、全局异常处理（400/422 统一格式）、日志配置 |
| `core/models.py` | 定义领域模型：`Idiom`（成语条目）、`Game`（游戏状态）、`CharFeedback`（单字反馈）、枚举 `Difficulty`/`GameMode` |
| `core/feedback.py` | `evaluate_guess()` — 对比猜测与目标成语，输出每字的 correct/present/absent 状态 |
| `core/candidate.py` | `generate_candidates()` — 根据难度从干扰字池抽取候选字，与目标字合并打乱 |
| `schemas/game.py` | API 层 Pydantic Schema，含输入校验（`GuessRequest` 验证 4 字汉字） |
| `services/game_service.py` | 游戏状态机：`create_game()`、`submit_guess()`、`get_game()`、`use_hint()`、`ensure_game()`；内存存储 `games: dict[str, Game]` |
| `services/routes.py` | REST 端点定义，将 HTTP 请求映射到 service 层函数 |

---

## 前端结构

```text
client/
├── index.html                  # 游戏主页
├── css/
│   ├── indexStyle.css          # 主样式（含 CSS 变量深浅色主题）
│   ├── dialog.css              # 自定义对话框组件样式
│   ├── help.css                # 帮助页样式
│   ├── top.css                 # 排行榜页样式
│   └── fonts/                  # 字体文件
├── js/
│   ├── indexScript.js          # 主游戏逻辑（开局、猜词、提示、揭晓、历史记录、主题切换）
│   ├── dialog.js               # CWDialog 自定义对话框组件
│   ├── help.js                 # 帮助页脚本
│   └── top.js                  # 排行榜页脚本
├── help/
│   └── index.html              # 游戏帮助页
├── top/
│   └── index.html              # 排行榜/日志页
├── icons/                      # 图标资源（SVG）
├── 结束.wav                    # 胜利音效
└── 要开始了哟.wav              # 开局音效
```

### 前端核心逻辑

| 模块 | 职责 |
|------|------|
| `indexScript.js` | 游戏主控制器：`startGame()`/`continueGame()` 开局、`addWord()`/`delWord()` 选字、`guess()` 提交、`hint()` 提示、`revealAnswer()` 揭晓、`won()`/`playing()` 结果处理、`lockGame()`/`unlockGame()` 答题区锁定、`saveHistory()`/`renderHistory()` 本地历史记录、`toggleTheme()` 主题切换 |
| `dialog.js` | `CWDialog` 组件：`confirm()`/`alert()` 自定义模态对话框，替代浏览器原生弹窗 |

### 前端状态管理

- 游戏状态通过全局变量管理（`game_id`、`turn`、`candidate`、`reverseCandidate`、`word` 等）
- 游戏进度通过 `localStorage` 持久化（`game_id` 用于断线续玩）
- 历史记录通过 `localStorage` 存储（key: `idiom_wordle_history`，最多 50 条）
- 主题偏好通过 `localStorage` 存储（key: `theme`）
- 防重复提交：`isSubmitting`/`isStarting`/`isContinuing`/`isHinting`/`isRevealing` 标志位

---

## 数据模型

### 内存存储

游戏数据存储在全局字典 `games: dict[str, Game]` 中，服务重启后丢失。

> **TODO**: 数据持久化。准备引入 MySQL。

### 核心模型

#### `Idiom`（成语条目）

| 字段 | 类型 | 说明 |
|------|------|------|
| `word` | `str` | 成语文本（4 字） |
| `pinyin` | `str` | 带声调拼音，如 "ā bí dì yù" |
| `pinyin_r` | `str` | 不带声调拼音，如 "a bi di yu" |
| `explanation` | `str` | 释义 |

#### `Game`（游戏记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| `game_id` | `str` | UUID 唯一标识 |
| `mode` | `GameMode` | `daily` / `unlimited` |
| `difficulty` | `Difficulty` | `easy` / `medium` / `hard` |
| `max_rounds` | `int` | 最大猜测轮次（12/10/8） |
| `candidate_chars` | `list[str]` | 候选字列表（打乱顺序） |
| `target_idiom` | `str` | 目标成语 |
| `target_pinyin` | `str` | 目标成语拼音 |
| `target_explanation` | `str` | 目标成语释义 |
| `guesses` | `list[list[CharFeedback]]` | 历史猜测记录及反馈 |
| `game_status` | `str` | `playing` / `won` / `lost` |
| `round` | `int` | 当前轮次（从 0 开始） |
| `hints_used` | `int` | 已使用提示次数 |
| `max_hints` | `int` | 最大提示次数（2） |
| `revealed_pinyins` | `list[str]` | 已揭示的拼音 |

#### `CharFeedback`（单字反馈）

| 字段 | 类型 | 说明 |
|------|------|------|
| `char` | `str` | 汉字 |
| `status` | `str` | `correct`（绿）/ `present`（黄）/ `absent`（灰） |

### 难度配置

| 难度 | 候选字数量 | 最大轮次 | 成语库 |
|------|-----------|---------|--------|
| easy | 10 | 12 | `data/easy.json` |
| medium | 14 | 10 | `data/medium.json` |
| hard | 20 | 8 | `data/hard.json` |

---

## 核心算法

### 反馈算法 (`core/feedback.py`)

标准 Wordle 反馈逻辑：

1. **第一遍**：标记位置完全正确的字为 `correct`（绿色），同时从目标字计数中消耗
2. **第二遍**：对未匹配的字，若目标成语中仍有该字剩余则标 `present`（黄色），否则标 `absent`（灰色）

确保重复字的反馈正确（如目标为"AABC"，猜测"AAXX"时，两个 A 分别为 correct 和 absent）。

### 候选字生成 (`core/candidate.py`)

1. 取目标成语的 4 个字
2. 根据难度从 `data/character.json` 干扰字库中随机抽取指定数量的干扰字（排除目标字）
3. 若干扰字不足，从成语库中补充
4. 合并目标字与干扰字，随机打乱顺序返回

### 每日挑战 (`services/game_service.py`)

- 以当天日期字符串为种子创建 `random.Random` 实例
- 从成语库中确定性选择一个成语，确保全站用户当天面对同一题目
- 无限模式则使用系统随机数

---

## API 接口

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| `POST` | `/api/games` | 创建新游戏 | Bearer Token |
| `POST` | `/api/games/{game_id}/guesses` | 提交猜测 | Bearer Token |
| `GET` | `/api/games/{game_id}` | 获取游戏状态（续玩用） | Bearer Token |
| `GET` | `/api/games/{game_id}/hints` | 使用提示（扣减次数） | Bearer Token |
| `GET` | `/api/games/{game_id}/reveal` | 揭晓答案（判负） | Bearer Token |
| `GET` | `/api/admin/reloadTokens` | 热加载 Token 摘要 | Admin Token |

所有接口统一返回格式：
- 成功：`{ "code": 200, "status": "success", ...data }`
- 失败：`{ "code": <status_code>, "status": "fail", "message": "错误描述" }`

> 📄 在线 API 文档：[ChineseIdomWordle API by 物化技](https://doc.wordle.whj.zdeweb.cn)
> `docs/api/` 目录下的 YAML 文件仅作存档。

---

## 鉴权机制

后端实现了全局 Bearer Token 鉴权中间件：

1. 启动时从 `token-sha256.txt` 加载合法 Token 的 SHA-256 摘要到内存集合
2. 每个请求检查 `Authorization: Bearer <token>` 头，计算 SHA-256 并与集合比对
3. 若文件为空（无有效 Token），自动关闭鉴权，方便本地开发
4. Admin 端点（`/api/admin/*`）使用独立的 `ADMIN_TOKEN_HASH` 校验
5. 支持热加载：调用 `/api/admin/reloadTokens` 重新读取文件，无需重启

前端默认使用 `test-token`（摘要已预置）。

---

## 配置

- **CORS**: 已配置允许所有来源跨域请求
- **日志**: Uvicorn 自定义格式，日志文件输出到 `logs/` 目录按日期轮转
- **端口**: 默认 8000
- **启动方式**: `uvicorn app.main:app --reload --port 8000`（开发模式，支持热重载）

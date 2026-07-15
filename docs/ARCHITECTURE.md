# 架构与项目结构

## 整体架构

前后端分离，通过 REST API 通信。

```text
Frontend ──HTTP/JSON──▶  Backend
```

## 后端结构

```text
backend/
├── app/
│   ├── main.py                 # FastAPI 入口，CORS 中间件、UTF-8 JSON 响应
│   ├── core/                   # 数据模型、反馈算法、候选字生成
│   │   ├── models.py           # Pydantic 模型（Idiom, Game, CharFeedback 等）
│   │   ├── feedback.py         # 猜测反馈算法
│   │   └── candidate.py        # 候选字生成
│   ├── schemas/                # 请求/响应 Schema
│   │   └── game.py             # 含输入校验（GuessRequest 验证汉字/长度）
│   └── services/               # 业务逻辑和路由
│       ├── game_service.py     # 游戏核心逻辑（加载成语、创建游戏、提交猜测、提示）
│       └── routes.py           # API 路由定义
├── data/                       # 成语原始数据（项目根目录）
│   ├── idiom.json              # 成语库（30895 条，含拼音、释义等）
│   └── character.json          # 干扰字库（按难度分级，每级 100 字）
└── tests/                      # 测试
    └── test_feedback.py        # 反馈算法单元测试
```

## 前端结构

> 待开发。技术栈待定。

## 数据模型

当前为内存存储，无持久化。

- `Idiom`: 成语（word, pinyin 带声调, pinyin_r 不带声调, explanation 释义）
- `Game`: 游戏记录（game_id, 模式, 难度, 目标成语, 候选字, 猜测记录, 状态, 提示信息）

> **TODO**: 数据持久化。当前游戏数据存储在内存字典中，服务重启后丢失。后续可引入数据库。

## 核心算法

### 反馈算法 (`core/feedback.py`)

1. 先标记位置正确的字为 `correct`（绿色），消耗目标字
2. 剩余字中，若目标成语还有该字则标 `present`（黄色），否则标 `absent`（灰色）

### 候选字生成 (`core/candidate.py`)

1. 取目标成语 4 字
2. 从对应难度的干扰字库中随机抽取（排除目标字）
3. 若干扰字不足，从成语库补充
4. 合并打乱返回

### 每日挑战 (`services/game_service.py`)

- 以日期为种子生成确定性随机数，确保全站当天同一题

## 配置

- **CORS**: 已配置，允许所有来源跨域请求
- **JSON 编码**: UTF-8，中文原样输出，`Content-Type: application/json; charset=utf-8`

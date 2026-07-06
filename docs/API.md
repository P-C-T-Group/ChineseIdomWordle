# API 设计

## 通用

- 基础路径: `/api`
- 请求/响应: JSON（UTF-8 编码）
- 玩家身份: 前端生成 UUID 存 localStorage，请求时携带
- CORS: 已配置，允许跨域请求
- 你也可以访问/docs来查看FastAPI直接生成的文档

## 鉴权

豁免的节点：

- 根节点（健康检查）
- `/docs` FastAPI 自动swagger

特殊检查的节点：

- `/api/admin/reload-token` 管理员：重载token列表

这些节点需要管理员认证，其token hash定义在`backend/app/main.py`头部。可以置空该hash来关闭所有的管理员节点。

鉴权方式：

采用 Bearer Token 鉴权

Token的有效列表定义在 `backend/app/token-sha256.txt`（一行一个sha256摘要值）

除豁免路径外其他请求，必须携带`Authorization: Bearer <Token>`请求头。

小提示，供测试使用：

- "test-token" 的sha256值为 `4c5dc9b7708905f77f5e5d16316b5dfb425e68cb326dcd55a860e90a7707031e`
- "test-admin" 的sha256值为 `db09d473d4b6461b91bfa47e4fed3ef55e0234df4132ca7a827b0a69e8927cac`

## 接口列表

### 创建游戏

```http
POST /api/games
```

请求体：

```json
{
  "mode": "unlimited",     // daily | unlimited
  "difficulty": "medium"   // easy | medium | hard
}
```

> `mode` 默认 `unlimited`，`difficulty` 默认 `medium`。

响应：

```json
{
  "code": 200,
  "status": "success",
  "game_id": "uuid",
  "mode": "unlimited",
  "difficulty": "medium",
  "max_rounds": 16,
  "candidate_chars": ["心", "想", "事", "成", "天", "人", "风", "月", "如", "意", "安", "好", "高", "兴"],
  "game_status": "playing",
  "guesses": []
}
```

> 候选字在创建时确定并打乱顺序。

### 提交猜测

```http
POST /api/games/{game_id}/guesses
```

请求体：

```json
{
  "guess": "心想事成"
}
```

> 输入校验：必须为 4 个汉字。

响应（游戏中）：

```json
{
  "code": 200,
  "status": "success",
  "game_id": "uuid",
  "guess": "心想事成",
  "result": [
    {"char": "心", "status": "correct"},
    {"char": "想", "status": "correct"},
    {"char": "事", "status": "correct"},
    {"char": "成", "status": "correct"}
  ],
  "round": 1,
  "max_rounds": 16,
  "game_status": "won",
  "answer": "心想事成",
  "pinyin": "xīn xiǎng shì chéng"
}
```

> `answer` 和 `pinyin` 仅在游戏结束（`won` 或 `lost`）时返回。

反馈状态说明：

- `correct`：字在成语中且位置正确（绿色）
- `present`：字在成语中但位置不对（黄色）
- `absent`：字不在成语中（灰色）

### 使用提示

```http
POST /api/games/{game_id}/hints
```

无请求体。

响应：

```json
{
  "code": 200,
  "status": "success",
  "game_id": "uuid",
  "revealed_pinyins": ["xīn"],
  "hints_used": 1,
  "max_hints": 2
}
```

> 随机揭示一个未提示过的目标成语字的拼音。每局最多 2 次提示。

### 查询游戏状态

```http
GET /api/games/{game_id}
```

返回完整游戏信息，包括历史猜测记录。

响应（进行中）：

```json
{
  "code": 200,
  "status": "success",
  "game_id": "uuid",
  "mode": "unlimited",
  "difficulty": "medium",
  "max_rounds": 16,
  "candidate_chars": ["心", "想", "事", "成", "天", "人", "风", "月", "如", "意", "安", "好", "高", "兴"],
  "game_status": "playing",
  "guesses": [...],
  "round": 2,
  "answer": null,
  "pinyin": null,
  "hints_used": 1,
  "max_hints": 2,
  "revealed_pinyins": ["xīn"]
}
```

> `answer` 和 `pinyin` 仅在游戏结束时返回。

### 获取统计

> **TODO**: 统计接口尚未实现。

```http
GET /api/stats?player_id={player_id}
```

### 管理员：重载token列表

```http
GET /api/admin/reload_tokens
```

正确请求会从服务器本地刷新合法 token hash 摘要列表。

## 错误响应

错误码：

- `400`: 非法请求
- `422`: 请求参数错误
- `404`: 游戏或API终结点不存在

出错响应体：

```json
{
  "code": {http_code},
  "status": "fail",
  "message": "错误描述"
}
```

常见错误：

- `游戏不存在`：game_id 无效（404）
- `游戏已结束`：对已结束的游戏提交猜测或使用提示（400）
- `必须输入4字成语` / `只能包含汉字`：输入校验失败（400）
- `不是有效成语`：猜测不在成语库中（400）
- `字"X"不在候选字中`：猜测包含候选字以外的字（400）
- `提示次数已用完`：超过最大提示次数（400）"

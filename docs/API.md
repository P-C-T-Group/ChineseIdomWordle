# API 设计

## 通用

- 基础路径: `/api`
- 请求/响应: JSON
- 玩家身份: 前端生成 UUID 存 localStorage，请求时携带

## 接口列表

### 创建游戏

```
POST /api/games
```

请求体：
```json
{
  "mode": "daily",          // daily | unlimited | custom
  "difficulty": "medium"    // easy | medium | hard
}
```

响应：
```json
{
  "game_id": "uuid",
  "mode": "daily",
  "difficulty": "medium",
  "max_rounds": 16,
  "candidate_chars": ["心", "想", "事", "成", "天", "人", "风", "月", "如", "意", "安", "好", "高", "兴"],
  "candidate_pinyin": null,
  "status": "playing",
  "guesses": []
}
```

> 候选字在创建时确定并打乱顺序。`candidate_pinyin` 仅简单模式返回。

### 提交猜测

```
POST /api/games/{game_id}/guesses
```

请求体：
```json
{
  "guess": "心想事成"
}
```

响应：
```json
{
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
  "status": "won",          // playing | won | lost
  "answer": "心想事成",      // 游戏结束才返回
  "pinyin": "xīn xiǎng shì chéng",
  "meaning": "心里想到的事就能成功"
}
```

### 查询游戏状态

```
GET /api/games/{game_id}
```

返回完整游戏信息，包括历史猜测记录。

### 获取统计

```
GET /api/stats?player_id={player_id}
```

返回总场次、胜率、连胜、猜测分布等统计数据。
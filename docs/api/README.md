# 成语Wordle API 文档

以下所有接口信息由FastAPI OpenAPI schema自动生成。

> 📄 **在线API文档**: 请前往[ChineseIdomWordle API by P.C.T.G.](https://doc.wordle.whj.zdeweb.cn)查看最新版本 API 文档。项目内文档仅供存档。

## 接口列表

### 游戏接口

| 接口 | 方法 | 文件 | 说明 |
|------|------|------|------|
| `/api/games` | POST | [create.yml](create.yml) | 创建新游戏 |
| `/api/games/{game_id}/guesses` | POST | [guess.yml](guess.yml) | 提交猜词 |
| `/api/games/{game_id}/hints` | GET | [hint.yml](hint.yml) | 使用提示 |
| `/api/games/{game_id}` | GET | [status.yml](status.yml) | 获取游戏状态 |
| `/api/games/{game_id}/reveal` | GET | [reveal.yml](reveal.yml) | 强制揭示答案 |

### 排行榜接口

| 接口 | 方法 | 文件 | 说明 |
|------|------|------|------|
| `/api/leaderboard/upload` | POST | [leaderboard/upload.yml](leaderboard_upload.yml) | 首次上传战绩创建存档 |
| `/api/leaderboard/append` | POST | [leaderboard/append.yml](leaderboard_append.yml) | 追加新战绩到已有存档 |
| `/api/leaderboard/daily/submit` | POST | [leaderboard/daily_submit.yml](leaderboard_daily_submit.yml) | 提交每日挑战成绩到日榜 |
| `/api/leaderboard/{difficulty}` | GET | [leaderboard/get.yml](leaderboard_get.yml) | 获取用户总榜（三种榜单） |
| `/api/leaderboard/{difficulty}/daily` | GET | [leaderboard/daily_get.yml](leaderboard_daily_get.yml) | 获取每日挑战排行榜 |
| `/api/leaderboard/profile/me` | GET | [leaderboard/profile.yml](leaderboard_profile.yml) | 获取个人存档 |
| `/api/leaderboard/profile/delete` | GET | [leaderboard/profile_delete.yml](leaderboard_profile_delete.yml) | 删除个人存档 |

**难度参数 `difficulty` 可选值**:
- `easy` - 简单
- `medium` - 中等（默认）
- `hard` - 困难

**排行榜类型**:
- **总榜**: 按胜利数(wins)、胜率(win_rate)、平均回合数(avg_rounds)排序
- **日榜**: 每日挑战按取胜回合数排序，每日0点清空

### 管理员接口

所有 `/api/admin/*` 接口需要管理员Token鉴权（Bearer Token）且来源IP在白名单中。

| 接口 | 方法 | 文件 | 说明 |
|------|------|------|------|
| `/api/admin/tokens/add` | POST | [admin/addTokens.yml](admin/addTokens.yml) | 添加API Token |
| `/api/admin/tokens` | GET | [admin/showTokens.yml](admin/showTokens.yml) | 查询Token列表 |
| `/api/admin/tokens/delete` | POST | [admin/deleteTokens.yml](admin/deleteTokens.yml) | 删除Token |
| `/api/admin/config/reload` | GET | [admin/reloadConfig.yml](admin/reloadConfig.yml) | 热重载配置 |
| `/api/admin/config/clean` | POST | [admin/cleanGames.yml](admin/cleanGames.yml) | 立即清理过期对局 |
| `/api/admin/leaderboard/users` | GET | [admin/leaderboard_users.yml](admin/leaderboard_users.yml) | 查询排行榜用户列表 |
| `/api/admin/leaderboard/delete` | POST | [admin/leaderboard_delete.yml](admin/leaderboard_delete.yml) | 删除用户存档 |
| `/api/admin/leaderboard/clean-daily` | GET | [admin/leaderboard_clean_daily.yml](admin/leaderboard_clean_daily.yml) | 清空日榜 |
| `/api/admin/leaderboard/clean-inactive` | GET | [admin/leaderboard_clean_inactive.yml](admin/leaderboard_clean_inactive.yml) | 清理不活跃用户 |

## 认证说明

1. **普通接口**: 需要在请求头中携带 `Authorization: Bearer <token>`，token需要通过管理员接口添加到数据库
2. **管理员接口**: 需要使用配置中 `admin_token_hash` 对应的原始Token
3. **排行榜Cookie**: 用户上传存档后会自动设置HttpOnly Cookie，后续请求自动携带

## 数据格式说明

所有请求和响应均使用JSON格式。时间使用ISO 8601格式。

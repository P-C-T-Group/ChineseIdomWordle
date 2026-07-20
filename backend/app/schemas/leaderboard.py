"""
排行榜相关 Schema 定义（Pydantic v2）

包含上传战绩请求、排行榜条目与查询响应模型。
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal

from app.core.models import Difficulty


class GameRecordItem(BaseModel):
    """单局对局记录（由前端历史记录上传）"""
    game_id: str = Field("", description="对局ID，用于去重")
    mode: Literal["daily", "unlimited"] = "unlimited"
    difficulty: Difficulty
    status: Literal["won", "lost"]
    rounds: int = Field(..., ge=0, le=50, description="用时回合数")
    timestamp: int = Field(..., ge=0, description="对局时间戳（毫秒）")


class UploadRecordRequest(BaseModel):
    """上传战绩到排行榜的请求体"""
    username: str = Field(..., min_length=1, max_length=32, description="用户名")
    records: list[GameRecordItem] = Field(...,
                                          min_length=1, description="对局记录列表")

    @field_validator("username")
    @classmethod
    def strip_username(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("用户名不能为空")
        return v


class LeaderboardEntry(BaseModel):
    """排行榜单条记录"""
    rank: int = Field(..., description="名次")
    user_id: str
    username: str
    ip_location: str
    # 榜单核心指标（视榜单类型含义不同）
    value: float = Field(..., description="榜单排序指标值")
    # 辅助展示字段
    total_games: int = Field(0, description="总局数")
    won_games: int = Field(0, description="胜利数")
    win_rate: float = Field(0.0, description="胜率")
    avg_rounds: float = Field(0.0, description="平均取胜回合数")


class LeaderboardResponse(BaseModel):
    """排行榜查询响应"""
    code: int = 200
    status: str = "success"
    difficulty: str
    # 三种榜单：wins（胜利数）/ win_rate（胜率）/ avg_rounds（平均取胜回合数）
    wins: list[LeaderboardEntry] = []
    win_rate: list[LeaderboardEntry] = []
    avg_rounds: list[LeaderboardEntry] = []
    # 当前用户在各榜单的名次（未上榜则为 null）
    my_rank: dict[str, Optional[int]] = {}
    # 当前用户的存档信息（未上传则为 null）
    my_profile: Optional[dict] = None


class UploadRecordResponse(BaseModel):
    """上传战绩响应"""
    code: int = 200
    status: str = "success"
    user_id: str
    username: str
    ip_location: str
    message: str = "上传成功"
    # 各难度统计概览
    stats: dict = {}


class MyProfileResponse(BaseModel):
    """查询当前用户存档信息响应"""
    code: int = 200
    status: str = "success"
    profile: Optional[dict] = None

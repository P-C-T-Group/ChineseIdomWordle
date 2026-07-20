"""
排行榜业务逻辑服务层
"""
import logging
from datetime import date
from typing import Optional, Tuple, List, Dict, Any

from app.core.config import get_settings
from app.core.ip_region import get_region
from app.database import db_manager
from app.schemas.leaderboard import GameRecordItem

log = logging.getLogger('uvicorn')


def _get_cookie_settings() -> Tuple[str, int]:
    """获取cookie配置"""
    lb_cfg = get_settings().leaderboard
    return lb_cfg.cookie_name, lb_cfg.cookie_max_age_days


def validate_records_for_upload(records: List[GameRecordItem]) -> Tuple[bool, str, Dict[str, Dict[str, int]]]:
    """验证上传的战绩记录

    返回: (是否有效, 错误信息, 按难度分类的统计结果)
    统计结果格式: {difficulty: {'total': 0, 'won': 0, 'win_rounds': 0}}
    """
    if not records:
        return False, "没有上传的战绩记录", {}

    # 按难度分类统计
    stats = {
        'easy': {'total': 0, 'won': 0, 'win_rounds': 0},
        'medium': {'total': 0, 'won': 0, 'win_rounds': 0},
        'hard': {'total': 0, 'won': 0, 'win_rounds': 0},
    }

    seen_game_ids = set()

    for record in records:
        diff = record.difficulty.value if hasattr(
            record.difficulty, 'value') else record.difficulty
        if diff not in stats:
            return False, f"不支持的难度: {diff}", {}

        # game_id去重（同一批次内）
        if record.game_id and record.game_id in seen_game_ids:
            continue
        if record.game_id:
            seen_game_ids.add(record.game_id)

        stats[diff]['total'] += 1
        if record.status == 'won':
            stats[diff]['won'] += 1
            stats[diff]['win_rounds'] += record.rounds

    total_games = sum(s['total'] for s in stats.values())
    min_games = get_settings().leaderboard.min_games_to_upload

    if total_games < min_games:
        return False, f"至少需要{min_games}局对战记录才能上传排行榜（当前{total_games}局）", {}

    return True, "", stats


def validate_records_for_append(existing_stats: Dict[str, Any], new_records: List[GameRecordItem]) -> Tuple[bool, str, Dict[str, Dict[str, int]]]:
    """验证追加的战绩记录（需要至少5局新记录）

    返回: (是否有效, 错误信息, 新增的统计结果)
    """
    if not new_records:
        return False, "没有上传的新战绩记录", {}

    min_new_records = get_settings().leaderboard.min_new_records_to_append

    # 按难度分类统计新记录
    new_stats = {
        'easy': {'total': 0, 'won': 0, 'win_rounds': 0},
        'medium': {'total': 0, 'won': 0, 'win_rounds': 0},
        'hard': {'total': 0, 'won': 0, 'win_rounds': 0},
    }

    seen_game_ids = set()
    new_count = 0

    for record in new_records:
        diff = record.difficulty.value if hasattr(
            record.difficulty, 'value') else record.difficulty
        if diff not in new_stats:
            return False, f"不支持的难度: {diff}", {}

        if record.game_id and record.game_id in seen_game_ids:
            continue
        if record.game_id:
            seen_game_ids.add(record.game_id)

        # 判断是否为新记录（通过时间戳和game_id简单判断，实际可优化）
        # 这里简化处理，由前端保证只传新记录
        new_stats[diff]['total'] += 1
        new_count += 1
        if record.status == 'won':
            new_stats[diff]['won'] += 1
            new_stats[diff]['win_rounds'] += record.rounds

    if new_count < min_new_records:
        return False, f"至少需要{min_new_records}局新对战记录才能追加（当前{new_count}局）", {}

    return True, "", new_stats


def get_or_create_user_from_cookie(cookie_token: Optional[str], username: str, client_ip: str) -> Tuple[Dict[str, Any], str, bool]:
    """从cookie获取或创建用户

    返回: (用户信息, cookie_token, 是否新创建)
    """
    if cookie_token:
        user = db_manager.get_user_by_cookie(cookie_token)
        if user:
            return user, cookie_token, False

    # 创建新用户
    ip_location = get_region(client_ip) or "未知"
    new_cookie = db_manager._generate_cookie_token()
    user = db_manager.create_user(username, new_cookie, ip_location)
    return user, new_cookie, True


def _filter_new_records(user_id: str, records: List[GameRecordItem]) -> List[GameRecordItem]:
    """过滤掉用户已经上传过的game_id，防止重复统计"""
    existing_ids = db_manager.get_existing_game_ids(user_id)
    new_records = []
    for r in records:
        if not r.game_id or r.game_id not in existing_ids:
            new_records.append(r)
    return new_records


def _records_to_dicts(records: List[GameRecordItem]) -> list[dict]:
    """将Pydantic记录转换为字典列表"""
    return [{
        'game_id': r.game_id or f"local_{r.timestamp}",
        'timestamp': r.timestamp
    } for r in records]


def upload_records(cookie_token: Optional[str], username: str, records: List[GameRecordItem], client_ip: str) -> Tuple[Dict[str, Any], str, bool]:
    """上传战绩（首次）

    返回: (用户信息, cookie_token, is_new_user)
    """
    # 获取或创建用户
    user, cookie_token, is_new = get_or_create_user_from_cookie(
        cookie_token, username, client_ip)

    if not is_new:
        existing_total = sum([
            user.get('easy_total', 0),
            user.get('medium_total', 0),
            user.get('hard_total', 0)
        ])
        if existing_total > 0:
            raise ValueError("您已有存档，请使用追加接口上传新记录")

    # 验证记录（全量验证）
    valid, msg, stats = validate_records_for_upload(records)
    if not valid:
        raise ValueError(msg)

    user_id = user['user_id']

    # 更新用户统计
    for diff, s in stats.items():
        if s['total'] > 0:
            db_manager.update_user_stats(
                user_id, diff,
                total_delta=s['total'],
                won_delta=s['won'],
                win_rounds_delta=s['win_rounds']
            )

    # 记录已上传的game_id
    db_manager.record_uploaded_games(user_id, _records_to_dicts(records))

    # 更新用户名（如果用户提供了新的用户名）
    if username and username != user['username']:
        db_manager.update_username(user_id, username)

    user = db_manager.get_user_by_id(user_id)
    if user is None:
        raise RuntimeError(f"更新后查询用户失败: user_id={user_id}")
    return user, cookie_token, is_new


def append_records(cookie_token: str, records: List[GameRecordItem]) -> Dict[str, Any]:
    """追加战绩（已有存档的用户）

    会自动过滤已经上传过的game_id，防止重复统计刷记录
    """
    if not cookie_token:
        raise ValueError("未找到您的存档，请先上传战绩创建存档")

    user = db_manager.get_user_by_cookie(cookie_token)
    if not user:
        raise ValueError("存档无效或已被删除")

    user_id = user['user_id']

    # 过滤掉已经上传过的game_id（后端去重，防止修改本地缓存刷记录）
    new_records = _filter_new_records(user_id, records)

    if len(new_records) == 0:
        raise ValueError("没有新的战绩记录需要追加（所有记录已上传过）")

    # 验证新记录
    valid, msg, new_stats = validate_records_for_append(user, new_records)
    if not valid:
        raise ValueError(msg)

    # 更新用户统计
    for diff, s in new_stats.items():
        if s['total'] > 0:
            db_manager.update_user_stats(
                user_id, diff,
                total_delta=s['total'],
                won_delta=s['won'],
                win_rounds_delta=s['win_rounds']
            )

    # 记录已上传的game_id
    db_manager.record_uploaded_games(user_id, _records_to_dicts(new_records))

    user = db_manager.get_user_by_id(user_id)
    if user is None:
        raise RuntimeError(f"更新后查询用户失败: user_id={user_id}")
    return user


def submit_daily_score(cookie_token: str, game_id: str, difficulty: str, won: bool, rounds: int) -> Tuple[bool, bool]:
    """提交每日挑战成绩到日榜

    返回: (提交是否成功, 是否胜利上榜)
    - 同一用户每天daily模式只能提交一次成绩（第一次挑战即占用名额）
    - 只有第一次挑战胜利才会上榜，失败则当日后续再胜利也无法提交
    """
    if not cookie_token:
        raise ValueError("未找到您的存档，无法提交日榜成绩")

    user = db_manager.get_user_by_cookie(cookie_token)
    if not user:
        raise ValueError("存档无效或已被删除")

    user_id = user['user_id']
    today = date.today().isoformat()

    # 不管胜负都尝试插入记录，利用唯一约束占用当日名额
    # 失败的记录不会出现在日榜中（查询时过滤won=1），但会阻止后续提交
    success = db_manager.add_daily_record(
        user_id=user_id,
        game_id=game_id,
        difficulty=difficulty,
        mode='daily',
        won=1 if won else 0,
        rounds=rounds,
        play_date=today
    )

    if not success:
        # 已经提交过，查询之前的结果判断是否上榜
        existing_record = db_manager.get_user_daily_record(
            user_id, today, 'daily')
        if existing_record and existing_record['won'] == 1:
            return False, True  # 之前已经胜利上榜
        else:
            return False, False  # 之前失败，无法上榜

    # 第一次提交，返回是否胜利上榜
    return True, won


def get_leaderboard_data(difficulty: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """获取用户排行榜数据（三种榜单）"""
    lb_cfg = get_settings().leaderboard
    limit = lb_cfg.top_display_limit

    wins_board, wins_rank = db_manager.get_leaderboard(
        difficulty, 'wins', limit, user_id)
    win_rate_board, win_rate_rank = db_manager.get_leaderboard(
        difficulty, 'win_rate', limit, user_id)
    avg_rounds_board, avg_rounds_rank = db_manager.get_leaderboard(
        difficulty, 'avg_rounds', limit, user_id)

    return {
        'wins': wins_board,
        'win_rate': win_rate_board,
        'avg_rounds': avg_rounds_board,
        'my_rank': {
            'wins': wins_rank,
            'win_rate': win_rate_rank,
            'avg_rounds': avg_rounds_rank,
        }
    }


def get_daily_leaderboard_data(difficulty: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """获取日榜数据"""
    lb_cfg = get_settings().leaderboard
    limit = lb_cfg.top_display_limit
    today = date.today().isoformat()

    daily_board, my_rank = db_manager.get_daily_leaderboard(
        difficulty, today, limit, user_id)
    return {
        'daily': daily_board,
        'my_rank': my_rank
    }


def get_user_profile(cookie_token: Optional[str]) -> Optional[Dict[str, Any]]:
    """获取当前用户的存档信息"""
    if not cookie_token:
        return None

    user = db_manager.get_user_by_cookie(cookie_token)
    if not user:
        return None

    # 计算统计数据
    profile = dict(user)
    for diff in ['easy', 'medium', 'hard']:
        total = user.get(f'{diff}_total', 0)
        won = user.get(f'{diff}_won', 0)
        rounds = user.get(f'{diff}_win_rounds', 0)
        profile[f'{diff}_win_rate'] = won / total if total > 0 else 0
        profile[f'{diff}_avg_rounds'] = rounds / won if won > 0 else 0

    return profile


def delete_user_archive(cookie_token: str) -> bool:
    """用户删除自己的存档"""
    if not cookie_token:
        return False

    user = db_manager.get_user_by_cookie(cookie_token)
    if not user:
        return False

    db_manager.delete_user(user['user_id'])
    return True


def admin_delete_user(user_id: str) -> bool:
    """管理员删除用户存档"""
    user = db_manager.get_user_by_id(user_id)
    if not user:
        return False

    db_manager.delete_user(user_id)
    return True

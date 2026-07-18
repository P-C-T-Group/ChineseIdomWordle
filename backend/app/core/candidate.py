import json
import random

from app.core.config import get_settings

# 加载干扰字库
_char_pool = None


def _load_char_pool():
    global _char_pool
    if _char_pool is not None:
        return _char_pool
    # 路径已由 Settings 统一解析为绝对路径
    p = get_settings().idiom_library.characters_resolved
    with open(p, "r", encoding="utf-8") as f:
        raw = json.load(f)["characters"]
    # 去重
    _char_pool = {
        "easy": list(dict.fromkeys(raw["low_difficulty"])),
        "medium": list(dict.fromkeys(raw["medium_difficulty"])),
        "hard": list(dict.fromkeys(raw["high_difficulty"])),
    }
    return _char_pool


def generate_candidates(target_idiom: str, pool_size: int, difficulty: str, idiom_list: list[str] = []) -> list[str]:
    target_chars = list(target_idiom)
    decoy_count = pool_size - len(target_chars)

    # 从干扰字库抽取（排除目标字）
    pool = _load_char_pool()
    char_pool = [c for c in pool[difficulty] if c not in target_chars]
    decoys = random.sample(char_pool, min(decoy_count, len(char_pool)))

    # 如果不够，从成语库补充
    if len(decoys) < decoy_count and idiom_list:
        all_chars = set()
        for idiom in idiom_list:
            for c in idiom:
                if c not in target_chars and c not in decoys:
                    all_chars.add(c)
        remaining = decoy_count - len(decoys)
        decoys.extend(random.sample(list(all_chars),
                      min(remaining, len(all_chars))))

    candidates = target_chars + decoys
    random.shuffle(candidates)
    return candidates

from app.core.models import CharFeedback


def evaluate_guess(guess: str, target: str) -> list[CharFeedback]:
    """
    评估猜测，返回每个字的状态
    1. 先标记位置正确的字为绿色，消耗目标字
    2. 剩余字中，若目标成语还有该字则标黄，否则标灰
    """
    result = [{"char": c, "status": "absent"} for c in guess]
    target_chars = list(target)

    for i, c in enumerate(guess):
        if c == target_chars[i]:  # 标记correct
            result[i]["status"] = "correct"
            target_chars[i] = ''
        elif c in target_chars:  # 标记present
            result[i]["status"] = "present"
            target_chars[target_chars.index(c)] = ''

    return [CharFeedback(**r) for r in result]

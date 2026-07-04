import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.feedback import evaluate_guess


def test_all_correct():
    result = evaluate_guess("心想事成", "心想事成")
    assert [r.status for r in result] == ["correct", "correct", "correct", "correct"]


def test_all_absent():
    result = evaluate_guess("龙飞凤舞", "心想事成")
    assert [r.status for r in result] == ["absent", "absent", "absent", "absent"]


def test_present():
    result = evaluate_guess("事想心成", "心想事成")
    assert [r.status for r in result] == ["present", "correct", "present", "correct"]


def test_duplicate_chars():
    # 目标：步步为营，猜：不可步营
    result = evaluate_guess("不可步营", "步步为营")
    assert [r.status for r in result] == ["absent", "absent", "present", "correct"]


def test_duplicate_guess():
    # 目标：心想事成，猜：心心相印
    result = evaluate_guess("心心相印", "心想事成")
    assert [r.status for r in result] == ["correct", "absent", "absent", "absent"]

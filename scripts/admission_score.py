"""Deterministic calculator for Tessera's seven-level piece admission rubric."""

from __future__ import annotations

from collections.abc import Mapping


SCORE_ANCHORS = {
    "demand": {0, 6, 12, 16, 20},
    "value": {0, 5, 10, 16, 20},
    "boundary": {0, 4, 8, 12, 15},
    "evaluability": {0, 4, 8, 12, 15},
    "lightweight": {0, 4, 8, 12, 15},
    "portability": {0, 2, 5, 8, 10},
    "safety": {0, 1, 3, 5},
}

GRADE_ORDER = ("S", "A", "B", "C", "D", "E", "F")
RECOMMENDATIONS = {
    "S": "进入正式拼图实现与发布流程",
    "A": "推荐新增，补齐少量缺口后发布",
    "B": "先原型或限定范围试用，通过真实任务复评",
    "C": "不独立成拼图，优先合并或做组合流程",
    "D": "重新定义需求、边界或实现方式",
    "E": "收益低于维护与上下文成本，建议放弃",
    "F": "拒绝进入市集",
}


def grade_for_score(score: int) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    if score >= 40:
        return "E"
    return "F"


def evaluate(
    scores: Mapping[str, int], flags: Mapping[str, bool] | None = None
) -> dict[str, object]:
    """Return raw and capped grades; reject scores outside documented anchors."""

    flags = flags or {}
    missing = set(SCORE_ANCHORS) - set(scores)
    extra = set(scores) - set(SCORE_ANCHORS)
    if missing or extra:
        raise ValueError(f"评分维度不匹配: missing={sorted(missing)}, extra={sorted(extra)}")

    for dimension, anchors in SCORE_ANCHORS.items():
        value = scores[dimension]
        if value not in anchors:
            raise ValueError(f"{dimension}={value} 不是允许的锚点分值 {sorted(anchors)}")

    raw_score = sum(scores.values())
    raw_grade = grade_for_score(raw_score)
    caps: list[tuple[str, str]] = []

    if flags.get("no_real_usage", False):
        caps.append(("B", "尚无真实使用记录"))
    if scores["value"] <= 5:
        caps.append(("D", "与宿主或现有拼图明显重复"))
    if scores["boundary"] <= 4:
        caps.append(("D", "触发边界不足以可靠路由"))
    if scores["evaluability"] <= 4:
        caps.append(("D", "输出无法可靠评测"))
    if flags.get("heavy_runtime_without_evidence", False):
        caps.append(("C", "重型运行时尚无实测收益"))
    if flags.get("single_host_no_fallback", False):
        caps.append(("C", "只支持一个正式宿主且无诚实降级"))

    direct_reject = scores["safety"] == 0 or flags.get(
        "severe_safety_violation", False
    )
    if direct_reject:
        caps.append(("F", "存在隐式安装、不可逆默认操作或凭证风险"))

    if caps:
        cap_grade, cap_reason = max(caps, key=lambda item: GRADE_ORDER.index(item[0]))
        final_grade = GRADE_ORDER[
            max(GRADE_ORDER.index(raw_grade), GRADE_ORDER.index(cap_grade))
        ]
    else:
        cap_grade, cap_reason = None, None
        final_grade = raw_grade

    return {
        "raw_score": raw_score,
        "raw_grade": raw_grade,
        "cap_grade": cap_grade,
        "cap_reason": cap_reason,
        "final_grade": final_grade,
        "recommendation": RECOMMENDATIONS[final_grade],
    }

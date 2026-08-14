# -*- coding: utf-8 -*-
"""世界赛资格判定：给定全年积分向量 + 第三赛段冠军，判定目标队伍的种子/冒泡赛资格。

规则依据（docs/rules-2026.md §5-6，2025 官方规则）：
1. 1 号种子 = 第三赛段冠军（直通）
2. 2 号种子 = 除冠军外全年总积分第一
3. 冒泡赛 = 剩余队伍按全年积分排序取前 4（总排名 3-6，顺延递补）
   第 1、2 名进胜者组，第 3、4 名进败者组
4. 并列：积分相同 → 第三赛段积分高者优先
5. 等概率模型下：胜者组进世界赛概率 3/4（1/2 直接拿 3 号 + 1/4 败决拿 4 号），
   败者组 1/4（赢两场拿 4 号）
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

QualificationStatus = str
STATUS_SEED1 = "seed1"            # 已锁定 1 号种子
STATUS_SEED2 = "seed2"            # 已锁定 2 号种子
STATUS_QUALIFIER_UPPER = "qualifier_upper"  # 进冒泡赛胜者组
STATUS_QUALIFIER_LOWER = "qualifier_lower"  # 进冒泡赛败者组
STATUS_OUT = "out"                # 未进冒泡赛


@dataclass
class QualificationResult:
    status: QualificationStatus
    rank: int                      # 全年积分总排名（并列按 tiebreak 排序后）
    bracket: Optional[str]         # "upper" | "lower" | None
    p_seed1: float = 0.0
    p_seed2: float = 0.0
    p_seed3: float = 0.0
    p_seed4: float = 0.0
    detail: Dict = field(default_factory=dict)

    @property
    def p_qualify(self) -> float:
        return self.p_seed1 + self.p_seed2 + self.p_seed3 + self.p_seed4


def rank_teams(total_points: Dict[str, int],
               split3_points: Dict[str, int],
               tiebreak_priority: str = "split3") -> List[str]:
    """按全年积分排序队伍，返回降序列表。

    并列规则：积分相同 → 第三赛段积分高者优先（rules.points.total_ranking.tiebreak）。
    """
    def key(t):
        tp = total_points.get(t, 0)
        if tiebreak_priority == "split3":
            return (tp, split3_points.get(t, 0))
        return (tp, 0)
    return sorted(total_points.keys(), key=key, reverse=True)


def evaluate_qualification(target: str,
                           total_points: Dict[str, int],
                           split3_points: Dict[str, int],
                           champion: Optional[str],
                           rules: Dict) -> QualificationResult:
    """判定 target 的世界赛资格（给定确定性的冠军与积分）。

    Parameters
    ----------
    total_points : 全年总积分（split1+split2+split3），dict team->int
    split3_points : 第三赛段积分，dict team->int（并列 tiebreak 用）
    champion : 第三赛段冠军队伍名；季后赛未打完时由调用方传入具体冠军（穷举分支中）
    """
    if champion == target:
        return QualificationResult(STATUS_SEED1, 1, None,
                                   p_seed1=1.0,
                                   detail={"note": "第三赛段冠军 = 1 号种子"})

    order = rank_teams(total_points, split3_points)
    ranked = [t for t in order if t != champion]  # 除冠军外排序
    # 2 号种子：除冠军外积分第一
    if ranked and ranked[0] == target:
        return QualificationResult(STATUS_SEED2, 1, None,
                                   p_seed2=1.0,
                                   detail={"note": "除冠军外全年积分第一 = 2 号种子"})

    # 冒泡赛：排除冠军与 2 号后，按积分取前 4（= 总排名 3-6 顺延递补）
    already = {champion, ranked[0]} if ranked else {champion}
    qualifier_candidates = [t for t in order if t not in already]
    if target in qualifier_candidates:
        idx = qualifier_candidates.index(target)  # 0-based，在剩余队伍中的位次
        if idx < 4:  # 只有前 4 名进冒泡赛
            bracket = "upper" if idx < 2 else "lower"
            eq = rules["qualifier"].get("equal_probability_equivalent", {})
            p_upper = _parse_frac(eq.get("upper_bracket_qualify_p", "3/4"))
            p_lower = _parse_frac(eq.get("lower_bracket_qualify_p", "1/4"))
            if bracket == "upper":
                # 胜者组：直接赢 = 3 号种子(1/2)；输后赢败决 = 4 号种子(1/4)
                p3, p4 = 1 / 2, 1 / 4
                return QualificationResult(STATUS_QUALIFIER_UPPER, idx + 1, bracket,
                                           p_seed3=p3, p_seed4=p4,
                                           detail={"qualifier_rank": idx + 1,
                                                   "p_upper": p_upper})
            else:
                # 败者组：连赢两场 = 4 号种子(1/4)
                return QualificationResult(STATUS_QUALIFIER_LOWER, idx + 1, bracket,
                                           p_seed4=p_lower,
                                           detail={"qualifier_rank": idx + 1,
                                                   "p_lower": p_lower})

    # 未进冒泡赛
    rank_out = 5
    if target in qualifier_candidates:
        rank_out = qualifier_candidates.index(target) + 1
    return QualificationResult(STATUS_OUT, rank_out, None,
                               detail={"note": "全年积分未进入冒泡赛区间"})


def _parse_frac(s: str) -> float:
    if "/" in s:
        a, b = s.split("/")
        return float(a) / float(b)
    return float(s)


# ---------------------------------------------------------------------------
# 便捷工具：全年积分汇总
# ---------------------------------------------------------------------------
def total_points_from_splits(points: Dict[str, Dict[str, int]]) -> Dict[str, int]:
    """points: {team: {split1, split2, split3}} -> {team: total}"""
    return {t: sum(v.values()) for t, v in points.items()}

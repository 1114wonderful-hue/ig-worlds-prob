# -*- coding: utf-8 -*-
"""季后赛等概率模拟器（2026 LPL 第三赛段赛季季后赛，8 队双败 BO5）。

结构（⚠️ 依据 2026 页面描述推测，官方赛程公布后校准）：
- 胜者组：登峰组前 6；登峰 1、2 从胜者组第 2 轮开始（轮空优势）
- 败者组：骑士之路晋级 2 队（K1、K2）从败者组第 1 轮开始
- 轮次：WB R1(S3vS6, S4vS5) → LB R1(K1vWB败1, K2vWB败2) → WB R2(S1vWB胜1, S2vWB胜2)
  → LB R2 → WB R3(胜决) → LB R3 → LB R4(败决) → 总决赛

模型：每场 BO5 双方胜率各 1/2（六种比分为等权重细分，不影响胜负分支）。
枚举 2^12 = 4096 个胜负组合，统计各队名次分布（1/2/3/4/5-6/7-8）。
"""
import itertools
from typing import Dict, List

# 名次档位（与积分表一致）
RANKS = ['1', '2', '3', '4', '5-6', '7-8']


def simulate_playoffs(slots: Dict[str, str]) -> Dict[str, Dict[str, float]]:
    """slots: {槽位: 队伍}，槽位为 S1..S6（登峰组 1-6）、K1、K2（骑士之路胜者）。

    返回 {team: {rank_label: prob}}。
    """
    teams = list(slots.values())
    dist = {t: {r: 0.0 for r in RANKS} for t in teams}
    n = 0
    for outcomes in itertools.product([0, 1], repeat=12):
        w = 1.0 / (1 << 12)
        n += 1
        ranks = _run_bracket(slots, outcomes)
        for t, r in ranks.items():
            dist[t][r] += w
    assert n == 4096
    return dist


def _run_bracket(slots: Dict[str, str], o) -> Dict[str, str]:
    """o: 12 个 0/1（0=前者败，1=前者胜），返回 {team: rank_label}。"""
    S = slots

    # 1-2. WB R1
    wb1 = S['S3'] if o[0] else S['S6']
    lb1 = S['S6'] if o[0] else S['S3']
    wb2 = S['S4'] if o[1] else S['S5']
    lb2 = S['S5'] if o[1] else S['S4']

    # 3-4. LB R1: K1 v WB1败, K2 v WB2败
    lbr1w1 = S['K1'] if o[2] else lb1
    lbr1l1 = lb1 if o[2] else S['K1']
    lbr1w2 = S['K2'] if o[3] else lb2
    lbr1l2 = lb2 if o[3] else S['K2']

    # 5-6. WB R2: S1 v WB1胜, S2 v WB2胜
    wbr2w1 = S['S1'] if o[4] else wb1
    wbr2l1 = wb1 if o[4] else S['S1']
    wbr2w2 = S['S2'] if o[5] else wb2
    wbr2l2 = wb2 if o[5] else S['S2']

    # 7-8. LB R2: LB R1 胜者 v WB R2 败者
    lbr2w1 = lbr1w1 if o[6] else wbr2l1
    lbr2l1 = wbr2l1 if o[6] else lbr1w1
    lbr2w2 = lbr1w2 if o[7] else wbr2l2
    lbr2l2 = wbr2l2 if o[7] else lbr1w2

    # 9. WB R3 胜者组决赛
    wbr3w = wbr2w1 if o[8] else wbr2w2
    wbr3l = wbr2w2 if o[8] else wbr2w1

    # 10. LB R3
    lbr3w = lbr2w1 if o[9] else lbr2w2
    lbr3l = lbr2w2 if o[9] else lbr2w1

    # 11. LB R4 败者组决赛: WB R3 败者 v LB R3 胜者
    lbr4w = wbr3l if o[10] else lbr3w
    lbr4l = lbr3w if o[10] else wbr3l

    # 12. 总决赛
    champ = wbr3w if o[11] else lbr4w
    runner = lbr4w if o[11] else wbr3w

    ranks = {
        champ: '1',
        runner: '2',
        lbr4l: '3',
        lbr3l: '4',
        lbr2l1: '5-6',
        lbr2l2: '5-6',
        lbr1l1: '7-8',
        lbr1l2: '7-8',
    }
    # 名次 5-6 / 7-8 是并列档位：归一化权重（每档 2 队，各计 0.5 档权重由调用方按积分表处理）
    return ranks


def champion_probs(dist) -> Dict[str, float]:
    return {t: d.get('1', 0.0) for t, d in dist.items()}


# 槽位类型（等概率模型下同类完全对称）：
#   A = 登峰组前 2（胜者组第 2 轮开始，轮空 1 场）
#   B = 登峰组 3-6（胜者组第 1 轮开始）
#   C = 骑士之路晋级 2 队（败者组第 1 轮开始）
SLOT_TYPES = ['A1', 'A2', 'B1', 'B2', 'B3', 'B4', 'C1', 'C2']


def simulate_slot_rank_outcomes() -> list:
    """预计算 4096 个季后赛胜负分支的「槽位 → 名次档位」映射。

    返回长度为 4096 的列表，每项为 {slot: rank_label}（slot ∈ SLOT_TYPES，
    rank_label ∈ 1/2/3/4/5-6/7-8）。等概率模型下，任何具体队伍分配到某
    槽位后，其名次分布由该槽位决定，与队伍身份无关。
    """
    legacy_slots = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'K1', 'K2']
    legacy_to_type = {'S1': 'A1', 'S2': 'A2', 'S3': 'B1', 'S4': 'B2',
                      'S5': 'B3', 'S6': 'B4', 'K1': 'C1', 'K2': 'C2'}
    slots = {k: k for k in legacy_slots}  # 占位：槽位名即队伍名
    outcomes = []
    for o in itertools.product([0, 1], repeat=12):
        ranks = _run_bracket(slots, o)   # {legacy_slot: rank}
        outcomes.append({legacy_to_type[k]: v for k, v in ranks.items()})
    return outcomes


def slot_to_split3_points(rank_label: str, split3_table: Dict) -> int:
    """名次档位 -> 第三赛段积分。"""
    for k, v in split3_table.items():
        if k == rank_label or k == str(rank_label):
            return int(v)
    return 0

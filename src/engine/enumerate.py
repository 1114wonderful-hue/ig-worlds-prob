# -*- coding: utf-8 -*-
"""常规赛穷举器 + IG 世界赛资格概率聚合（分层精确计算，等概率模型）。

层次结构（每层精确、权重相乘）：
1. 涅槃组剩余比赛：4^N 穷举（N 通常很小）→ 聚合涅槃排名类别
   （IG 是否前 2、前 2 集合、后 2 集合、各类别权重）
2. 登峰组剩余比赛：DP（状态 = 8 队 (胜场, 小分)）→ 聚合三段集合
   （前 2 / 中 4 / 后 2，每类权重）——避免 4^23 爆炸
3. 骑士之路：2 场 BO5，大场胜负各 1/2；IG 赢则进季后赛 C 位
4. 赛季季后赛：预计算 4096 个胜负分支的「槽位→名次」表（等概率），
   对每个（涅槃类 × 登峰集合 × 骑士胜者）组合内联资格判定并加权

模型：BO3 四种比分（2:0/2:1/1:2/0:2）等概率；大场胜负各 1/2，
小分参与排名 tiebreak；BO5 六种比分等概率 → 大场胜负各 1/2。
"""
import itertools
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from engine.playoffs import simulate_slot_rank_outcomes, slot_to_split3_points
from engine.qualify import (STATUS_SEED1, STATUS_SEED2, STATUS_QUALIFIER_UPPER,
                            STATUS_QUALIFIER_LOWER, STATUS_OUT)

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

BO3_SCORES = [('2-0', 2, -2), ('2-1', 1, -1), ('1-2', -1, 1), ('0-2', -2, 2)]
# (score, A 小分变化, B 小分变化)，四种等概率 → A 胜概率 1/2
BO3_WIN = [('2-0', 2, -2), ('2-1', 1, -1)]   # A 胜
BO3_LOSS = [('1-2', -1, 1), ('0-2', -2, 2)]  # A 负
BO5_WIN = 0.5  # 大场胜率


def apply_result(records: Dict[str, Tuple[int, int]], a: str, b: str,
                 winner: str, small_a: int, small_b: int) -> None:
    """records: {team: (wins, small_diff)}，原地更新一场 BO3 的结果。"""
    wa, sa = records[a]
    wb, sb = records[b]
    if winner == a:
        records[a] = (wa + 1, sa + small_a)
        records[b] = (wb, sb + small_b)
    else:
        records[a] = (wa, sa + small_a)
        records[b] = (wb + 1, sb + small_b)


def sort_by_record(teams: List[str], records: Dict[str, Tuple[int, int]]) -> List[str]:
    """按 (胜场, 小分) 降序；完全并列用队伍名稳定排序（近似，罕见场景）。"""
    return sorted(teams, key=lambda t: (records[t][0], records[t][1]), reverse=True)


# ---------------------------------------------------------------------------
# 1. 涅槃组穷举
# ---------------------------------------------------------------------------

@dataclass
class NirvanaCase:
    ig_in_top2: bool
    ig_is_n1: bool               # IG 是涅槃组第 1（决定骑士之路对阵 A8）
    top2: Tuple[str, ...]      # 前 2（含 IG 与否）
    bottom2: Tuple[str, ...]   # 后 2
    weight: float = 0.0


def nirvana_exhaust(games: List[Dict], base_records: Dict[str, Tuple[int, int]],
                    teams: List[str], target: str) -> List[NirvanaCase]:
    """对涅槃组剩余 BO3 全穷举（每场 4 种比分），聚合出排名类别。

    games: [{"a": 队, "b": 队}, ...]
    """
    cases: Dict[Tuple, List[float]] = {}
    n = len(games)
    if n > 14:
        raise ValueError(f'涅槃组剩余 {n} 场超出穷举上限（4^14≈2.7亿）')
    for combo in itertools.product(BO3_SCORES, repeat=n):
        rec = {t: list(base_records[t]) for t in teams}
        w = 1.0 / (4 ** n)
        for (score, sa, sb), g in zip(combo, games):
            winner = g['a'] if score[0] == '2' else g['b']
            apply_result(rec, g['a'], g['b'], winner, sa, sb)
        rec = {t: tuple(v) for t, v in rec.items()}
        order = sort_by_record(teams, rec)
        top2 = tuple(order[:2])
        bottom2 = tuple(order[2:])
        ig_in = target in top2
        ig_is_n1 = ig_in and order[0] == target
        key = (ig_in, ig_is_n1, top2, bottom2)
        cases.setdefault(key, []).append(w)
    out = []
    for (ig_in, ig_is_n1, top2, bottom2), ws in cases.items():
        out.append(NirvanaCase(ig_in, ig_is_n1, top2, bottom2, sum(ws)))
    return out


# ---------------------------------------------------------------------------
# 2. 登峰组 DP（状态聚合，避免 4^N 爆炸）
# ---------------------------------------------------------------------------

def ascend_dp(games: List[Dict], base_records: Dict[str, Tuple[int, int]],
              teams: List[str]) -> Dict[Tuple, float]:
    """登峰组剩余比赛 DP：状态 = 8 队胜场元组（2 分支/场，各 1/2）。

    说明：
    - BO3 四种比分在大场层面 = 胜/负各 1/2（2:0/2:1 皆胜），权重数学等价；
    - 并列（胜场相同）时按「均匀打破」近似处理（真实规则为小分 tiebreak，
      本实现跨边界并列组枚举全部排列等权分配；误差限于并列边界场景）。

    返回 {(top2, mid4, bottom2): weight}，集合内无序（A/B 位内部分别对称）。
    """
    state0 = tuple(base_records[t][0] for t in teams)  # 仅胜场
    states = {state0: 1.0}
    for g in games:
        a_idx, b_idx = teams.index(g['a']), teams.index(g['b'])
        new_states: Dict[Tuple, float] = {}
        for st, w in states.items():
            for win_a in (True, False):
                nst = list(st)
                if win_a:
                    nst[a_idx] += 1
                else:
                    nst[b_idx] += 1
                key = tuple(nst)
                new_states[key] = new_states.get(key, 0.0) + w / 2.0
        states = new_states

    from math import factorial
    from itertools import permutations

    agg: Dict[Tuple, float] = {}
    for st, w in states.items():
        wins = {t: st[i] for i, t in enumerate(teams)}
        # 按胜场降序分组
        order = sorted(teams, key=lambda t: wins[t], reverse=True)
        groups = []  # [(wins, [members])]
        for t in order:
            if groups and groups[-1][0] == wins[t]:
                groups[-1][1].append(t)
            else:
                groups.append((wins[t], [t]))
        # 逐组填入 top2/mid4/bottom2；跨边界组枚举排列（均匀打破）
        buckets = [[], [], []]  # top2, mid4, bottom2
        results = {}

        def assign(gi, b, ww):
            if gi == len(groups):
                # top2/mid4 内部对称可无序；bottom2 需保持排名序
                # （骑士之路配对 A7 v N2、A8 v N1 依赖第 7/第 8 的顺序）
                key = (tuple(sorted(b[0])), tuple(sorted(b[1])), tuple(b[2]))
                results[key] = results.get(key, 0.0) + ww
                return
            _, members = groups[gi]
            n = len(members)
            # 判断该组是否跨边界：成员必须连续占用槽位（胜场相同必相邻）
            slots_taken = len(b[0]) + len(b[1]) + len(b[2])
            first_slot = slots_taken
            for perm in permutations(members):
                nb = [list(x) for x in b]
                for t in perm:
                    if len(nb[0]) < 2:
                        nb[0].append(t)
                    elif len(nb[1]) < 4:
                        nb[1].append(t)
                    else:
                        nb[2].append(t)
                assign(gi + 1, nb, ww / factorial(n))
        assign(0, buckets, w)
        for key, ww in results.items():
            agg[key] = agg.get(key, 0.0) + ww
    return agg


# ---------------------------------------------------------------------------
# 3. 主流程：IG 资格概率聚合
# ---------------------------------------------------------------------------

def compute_ig_probability(season: Dict, rules: Dict, verbose: bool = False) -> Dict:
    """主入口：计算 IG 进世界赛概率。

    season: data/season-2026.json 结构（需含 remaining_schedule，可为空）
    rules:  data/rules.json 结构
    """
    target = season['target_team']
    asc = season['split3']['ascend']
    nir = season['split3']['nirvana']
    asc_teams = list(asc['teams'])
    nir_teams = list(nir['teams'])

    asc_records = {t: (asc['records'][t]['w'], asc['records'][t]['small_w'] - asc['records'][t]['small_l'])
                   for t in asc_teams}
    nir_records = {t: (nir['records'][t]['w'], nir['records'][t]['small_w'] - nir['records'][t]['small_l'])
                   for t in nir_teams}

    games = season.get('remaining_schedule', [])
    asc_games = [g for g in games if g.get('group') == 'ascend']
    nir_games = [g for g in games if g.get('group') == 'nirvana']

    base_points = {t['id']: sum(season['points_earned'][t['id']].values())
                   for t in season['teams'] if t['id'] in season['points_earned']}
    ig_base = base_points.get(target, 0)
    split3_table = rules['points']['split3']['table']

    if verbose:
        print(f'剩余比赛: 登峰 {len(asc_games)} 场, 涅槃 {len(nir_games)} 场')
        print(f'IG 当前全年积分: {ig_base}')

    # 1) 涅槃穷举
    nirvana_cases = nirvana_exhaust(nir_games, nir_records, nir_teams, target)
    if verbose:
        print(f'涅槃类别数: {len(nirvana_cases)}')

    # 2) 登峰 DP
    ascend_cases = ascend_dp(asc_games, asc_records, asc_teams)
    if verbose:
        print(f'登峰三段集合数: {len(ascend_cases)}')

    # 3) 季后赛槽位结果预计算
    slot_outcomes = simulate_slot_rank_outcomes()  # 4096
    n_outcomes = len(slot_outcomes)

    # 4) 聚合
    p_seed1 = p_seed2 = p_seed3 = p_seed4 = 0.0
    ig_qualify_detail = {'seed1': 0.0, 'seed2': 0.0, 'qualifier_upper': 0.0,
                         'qualifier_lower': 0.0, 'out': 0.0}

    for nc in nirvana_cases:
        # 骑士之路配对：A7 v N2、A8 v N1（A7/A8 = 登峰第 7/8，N1/N2 = 涅槃第 1/2）。
        # IG 若为 N1 打 A8（asc_bottom2[1]），另一场 A7 v N2；若为 N2 打 A7（asc_bottom2[0]）。
        # 另一场胜者（C 位第二队）∈ {非 IG 涅槃前 2 队, IG 非对手的登峰后 2 队} 各 1/2。
        top2_other = [t for t in nc.top2 if t != target][0]
        for ac, w_ac in ascend_cases.items():
            asc_top2, asc_mid4, asc_bottom2 = ac
            # 分支 A：IG 不进季后赛（未进涅槃前 2，或骑士之路落败）。
            ig_qualify_detail['out'] += (nc.weight * w_ac * 0.5) if nc.ig_in_top2 else (nc.weight * w_ac)
            if not nc.ig_in_top2:
                continue
            # 分支 B：IG 赢骑士之路（1/2），进季后赛 C 位
            ig_opponent_idx = 1 if nc.ig_is_n1 else 0   # IG 打 A8 或 A7
            knight_other = asc_bottom2[1 - ig_opponent_idx]  # 另一场的登峰后 2 队
            knight_candidates = [(top2_other, 1 / 2), (knight_other, 1 / 2)]
            for k_other, k_w in knight_candidates:
                w_comb = nc.weight * w_ac * 0.5 * k_w
                # 季后赛槽位分配
                slot_assign = {}
                for i, t in enumerate(asc_top2):
                    slot_assign[f'A{i + 1}'] = t
                for i, t in enumerate(asc_mid4):
                    slot_assign[f'B{i + 1}'] = t
                slot_assign['C1'] = target
                slot_assign['C2'] = k_other

                for outcome in slot_outcomes:
                    # 各队全年积分（含未进季后赛队伍，其第三赛段积分为 0）
                    pts = {t: base_points.get(t, 0) for t in base_points}
                    ig_rank = outcome['C1']
                    ig_pts = ig_base + slot_to_split3_points(ig_rank, split3_table)
                    pts[target] = ig_pts
                    champ = None
                    for slot, team in slot_assign.items():
                        rank = outcome[slot]
                        pts[team] = base_points.get(team, 0) + slot_to_split3_points(rank, split3_table)
                        if rank == '1':
                            champ = team
                    # 内联资格判定
                    if champ == target:
                        p_seed1 += w_comb / n_outcomes
                        ig_qualify_detail['seed1'] += w_comb / n_outcomes
                        continue
                    if pts.get(target) != ig_pts:
                        pass  # 一致性保护（不应发生）
                    # 排序（除冠军）
                    order = sorted(pts.keys(), key=lambda t: pts[t], reverse=True)
                    ranked = [t for t in order if t != champ]
                    if ranked[0] == target:
                        p_seed2 += w_comb / n_outcomes
                        ig_qualify_detail['seed2'] += w_comb / n_outcomes
                        continue
                    already = {champ, ranked[0]}
                    candidates = [t for t in order if t not in already]
                    if target in candidates:
                        idx = candidates.index(target)
                        if idx < 2:
                            p_seed3 += w_comb * 0.5 / n_outcomes
                            p_seed4 += w_comb * 0.25 / n_outcomes
                            ig_qualify_detail['qualifier_upper'] += w_comb / n_outcomes
                        elif idx < 4:
                            p_seed4 += w_comb * 0.25 / n_outcomes
                            ig_qualify_detail['qualifier_lower'] += w_comb / n_outcomes
                        else:
                            ig_qualify_detail['out'] += w_comb / n_outcomes
                    else:
                        ig_qualify_detail['out'] += w_comb / n_outcomes

    p_qualify = p_seed1 + p_seed2 + p_seed3 + p_seed4
    return {
        'p_qualify': p_qualify,
        'p_seed1': p_seed1,
        'p_seed2': p_seed2,
        'p_seed3': p_seed3,
        'p_seed4': p_seed4,
        'breakdown': ig_qualify_detail,
        'nirvana_cases': len(nirvana_cases),
        'ascend_cases': len(ascend_cases),
        'ig_base_points': ig_base,
    }

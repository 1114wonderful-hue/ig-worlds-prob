# -*- coding: utf-8 -*-
"""蒙特卡洛独立对照：随机采样剩余比赛结果，统计 IG 晋级率，与引擎精确值对比。

独立实现（不复用 enumerate 的逻辑，避免同源 bug）：
- 涅槃/登峰剩余比赛：每场随机 4 种 BO3 比分（等概率）
- 排名按 (胜场, 小分)
- 骑士之路：BO5 胜负各 1/2；季后赛：12 场 BO5 随机 → 名次
- 资格判定复用 qualify（其正确性已由 2025 真实数据基准验证）
"""
import copy, json, os, random, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from engine.playoffs import _run_bracket
from engine.qualify import evaluate_qualification

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON = json.load(open(os.path.join(ROOT, 'data', 'season-2026.json'), encoding='utf-8'))
RULES = json.load(open(os.path.join(ROOT, 'data', 'rules.json'), encoding='utf-8'))

SCORES = [('2-0', 2, -2), ('2-1', 1, -1), ('1-2', -1, 1), ('0-2', -2, 2)]


def mc_estimate(season, rules, n=60000, seed=42):
    random.seed(seed)
    target = season['target_team']
    asc = season['split3']['ascend']
    nir = season['split3']['nirvana']
    asc_teams = list(asc['teams']); nir_teams = list(nir['teams'])
    asc_base = {t: (asc['records'][t]['w'], asc['records'][t]['small_w'] - asc['records'][t]['small_l']) for t in asc_teams}
    nir_base = {t: (nir['records'][t]['w'], nir['records'][t]['small_w'] - nir['records'][t]['small_l']) for t in nir_teams}
    base_pts = {t['id']: sum(season['points_earned'][t['id']].values()) for t in season['teams']}
    split3 = rules['points']['split3']['table']
    games = season.get('remaining_schedule', [])
    asc_games = [g for g in games if g.get('group') == 'ascend']
    nir_games = [g for g in games if g.get('group') == 'nirvana']

    def play(games, base):
        rec = {t: list(v) for t, v in base.items()}
        for g in games:
            a, b = g['a'], g['b']
            score, sa, sb = random.choice(SCORES)
            win_a = score[0] == '2'
            if win_a:
                rec[a][0] += 1; rec[a][1] += sa; rec[b][1] += sb
            else:
                rec[b][0] += 1; rec[a][1] += sa; rec[b][1] += sb
        return {t: tuple(v) for t, v in rec.items()}

    def rank_by(rec):
        return sorted(rec.keys(), key=lambda t: (rec[t][0], rec[t][1]), reverse=True)

    def slot_pts(rank, table):
        for k, v in table.items():
            if str(k) == str(rank):
                return int(v)
        return 0

    wins = 0
    for _ in range(n):
        rec_n = play(nir_games, nir_base)
        rec_a = play(asc_games, asc_base)
        order_n = rank_by(rec_n); order_a = rank_by(rec_a)
        # 涅槃前 2、登峰三段
        n_top2 = order_n[:2]; n_bottom2 = order_n[2:]
        a_top2 = order_a[:2]; a_mid = order_a[2:6]; a_bottom = order_a[6:]
        if target not in n_top2:
            continue  # IG 出局
        ig_n1 = n_top2[0] == target
        top2_other = [t for t in n_top2 if t != target][0]
        # 骑士之路：IG 赢 1/2
        if random.random() < 0.5:
            continue
        # 另一场胜者：非 IG 涅槃前 2 队 或 非 IG 对手的登峰后 2 队，各 1/2
        ig_opp_idx = 1 if ig_n1 else 0
        knight_other = a_bottom[1 - ig_opp_idx]
        k_other = random.choice([top2_other, knight_other])
        # 季后赛：随机 12 场
        slots = {'S1': a_top2[0], 'S2': a_top2[1], 'S3': a_mid[0], 'S4': a_mid[1],
                 'S5': a_mid[2], 'S6': a_mid[3], 'K1': target, 'K2': k_other}
        o = tuple(random.randint(0, 1) for _ in range(12))
        ranks = _run_bracket(slots, o)
        pts = dict(base_pts)
        champ = None
        for team, rank in ranks.items():
            pts[team] += slot_pts(rank, split3)
            if rank == '1':
                champ = team
        r = evaluate_qualification(target, pts, {t: slot_pts(ranks.get(t, '9-12'), split3) for t in pts}, champ, rules)
        wins += r.p_qualify
    return wins / n


def run(season, rules, label, n=60000):
    from engine.enumerate import compute_ig_probability
    exact = compute_ig_probability(season, rules)['p_qualify']
    mc = mc_estimate(season, rules, n=n)
    print(f'{label}: 精确值 {exact*100:.3f}% vs 蒙特卡洛 {mc*100:.3f}% (n={n}) | 差异 {abs(exact-mc)*100:.3f}pp')
    assert abs(exact - mc) < 0.01, f'MC 对照失败: {exact} vs {mc}'
    return exact, mc


if __name__ == '__main__':
    ok = 0
    # 空赛程
    run(SEASON, RULES, '空剩余赛程', 60000); ok += 1
    # 3 场涅槃
    s3 = copy.deepcopy(SEASON)
    s3['remaining_schedule'] = [
        {'a': 'IG', 'b': 'NIP', 'group': 'nirvana', 'format': 'bo3'},
        {'a': 'IG', 'b': 'WBG', 'group': 'nirvana', 'format': 'bo3'},
        {'a': 'WBG', 'b': 'LNG', 'group': 'nirvana', 'format': 'bo3'},
    ]
    run(s3, RULES, '3 场涅槃剩余', 60000); ok += 1
    # 2 场登峰
    s4 = copy.deepcopy(SEASON)
    s4['remaining_schedule'] = [
        {'a': 'TES', 'b': 'EDG', 'group': 'ascend', 'format': 'bo3'},
        {'a': 'BLG', 'b': 'EDG', 'group': 'ascend', 'format': 'bo3'},
    ]
    run(s4, RULES, '2 场登峰剩余', 60000); ok += 1
    print(f'\n蒙特卡洛对照全部通过: {ok} 个场景（差异 < 1pp）')

# -*- coding: utf-8 -*-
"""比赛影响分析：已结束比赛对 IG 概率的影响 + IG 下一场胜负预测。

原理（引擎对比计算）：
- 每场已结束比赛 m：计算「移除 m 的结果（视为未打）」后的概率 P_without，
  影响 = 当前概率 - P_without（= 这场比赛打完后概率的净变化）
- IG 下一场：分别假设 IG 以 2-0 / 2-1 / 1-2 / 0-2 获胜/落败，计算概率并加权
  （BO3 四种比分等概率），给出"若赢/若输"的预测概率与变化量

输出：data/impact.json + web/data/impact.json（供前端展示）
"""
import argparse, copy, json, os, sys
from datetime import date, timedelta

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from engine.enumerate import compute_ig_probability

SEASON_PATH = os.path.join(ROOT, 'data', 'season-2026.json')
RULES_PATH = os.path.join(ROOT, 'data', 'rules.json')
SCHEDULE_PATH = os.path.join(ROOT, 'data', 'schedule.json')


def apply_result_to_record(rec, team, score_win, score_lose):
    """把一场 BO3 结果累加到 records（rec 为 {team: {w,l,small_w,small_l}}）。"""
    rec[team]['small_w'] += score_win
    rec[team]['small_l'] += score_lose


def rebuild_season_without(season, done_matches, exclude_key, asc_teams, nir_teams):
    """返回 season 副本：从战绩中移除 exclude_key 对应比赛，并把它加回剩余赛程。"""
    s = copy.deepcopy(season)
    for grp in ('ascend', 'nirvana'):
        for t in s['split3'][grp]['teams']:
            s['split3'][grp]['records'][t] = {'w': 0, 'l': 0, 'small_w': 0, 'small_l': 0}
    for m in done_matches:
        key = (m['date'], m['a'], m['b'])
        if exclude_key and key == exclude_key:
            continue
        grp = 'ascend' if (m['a'] in asc_teams and m['b'] in asc_teams) else 'nirvana'
        rec = s['split3'][grp]['records']
        sa, sb = m['score_a'], m['score_b']
        rec[m['a']]['small_w'] += sa; rec[m['a']]['small_l'] += sb
        rec[m['b']]['small_w'] += sb; rec[m['b']]['small_l'] += sa
        if sa > sb:
            rec[m['a']]['w'] += 1; rec[m['b']]['l'] += 1
        else:
            rec[m['b']]['w'] += 1; rec[m['a']]['l'] += 1
    grp = 'ascend' if (exclude_key[1] in asc_teams and exclude_key[2] in asc_teams) else 'nirvana'
    s['remaining_schedule'] = list(season['remaining_schedule']) + [
        {'date': exclude_key[0][:10], 'a': exclude_key[1], 'b': exclude_key[2],
         'group': grp, 'format': 'bo3'}]
    return s


def season_with_fixed_next(season, next_game, score):
    """返回 season 副本：把下一场（未打）固定为指定比分，从剩余赛程移除。"""
    s = copy.deepcopy(season)
    s['remaining_schedule'] = [g for g in s['remaining_schedule']
                               if not (g['a'] == next_game['a'] and g['b'] == next_game['b']
                                       and g['date'] == next_game['date'])]
    grp = next_game['group']
    rec = s['split3'][grp]['records']
    a, b = next_game['a'], next_game['b']
    wa, wb = score
    rec[a]['small_w'] += wa; rec[a]['small_l'] += wb
    rec[b]['small_w'] += wb; rec[b]['small_l'] += wa
    if wa > wb:
        rec[a]['w'] += 1; rec[b]['l'] += 1
    else:
        rec[b]['w'] += 1; rec[a]['l'] += 1
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    season = json.load(open(SEASON_PATH, encoding='utf-8'))
    rules = json.load(open(RULES_PATH, encoding='utf-8'))
    schedule = json.load(open(SCHEDULE_PATH, encoding='utf-8'))
    asc_teams = set(season['split3']['ascend']['teams'])
    nir_teams = set(season['split3']['nirvana']['teams'])

    done = [m for m in schedule['matches'] if m['status'] == 'done']
    done.sort(key=lambda m: m['date'])
    asc_done = [m for m in done if (m['a'] in asc_teams and m['b'] in asc_teams)]
    nir_done = [m for m in done if (m['a'] in nir_teams and m['b'] in nir_teams)]

    if not args.quiet:
        print('计算当前概率…')
    p_now = compute_ig_probability(season, rules)['p_qualify']

    # ---- 目标比赛：近 3 天已结束 + IG 近 3 场已结束 ----
    today = date.today()
    recent3 = [m for m in done if m['date'][:10] >= (today - timedelta(days=3)).isoformat()]
    ig_done = [m for m in done if m['a'] == 'IG' or m['b'] == 'IG']
    ig_done.sort(key=lambda m: m['date'], reverse=True)
    targets, seen = [], set()
    for m in sorted(recent3 + ig_done[:3], key=lambda mm: mm['date'], reverse=True):
        k = (m['date'], m['a'], m['b'])
        if k not in seen:
            seen.add(k)
            targets.append(m)

    impacts = []
    for m in targets:
        key = (m['date'], m['a'], m['b'])
        s2 = rebuild_season_without(season, done, key, asc_teams, nir_teams)
        p_without = compute_ig_probability(s2, rules)['p_qualify']
        winner = m['a'] if m['score_a'] > m['score_b'] else m['b']
        impacts.append({
            'date': m['date'][:10], 'a': m['a'], 'b': m['b'],
            'score': f"{m['score_a']}-{m['score_b']}", 'winner': winner,
            'p_before': p_without, 'p_after': p_now, 'impact': p_now - p_without,
        })

    # ---- IG 下一场预测 ----
    ig_next = None
    for g in sorted(season['remaining_schedule'], key=lambda x: x['date']):
        if g['a'] == 'IG' or g['b'] == 'IG':
            ig_next = g
            break
    next_pred = None
    if ig_next:
        if not args.quiet:
            print(f'计算下一场预测（{ig_next["date"]} {ig_next["a"]} vs {ig_next["b"]}）…')
        # score 顺序 = (a 队得分, b 队得分)；ig_next 中 b 不一定是 IG，需按队伍判断
        ig_team = 'IG'
        a_side, b_side = ig_next['a'], ig_next['b']
        # (a_score, b_score) 组合：a 赢 = a 得 2 分；b 赢 = b 得 2 分
        p_a2b0 = compute_ig_probability(season_with_fixed_next(season, ig_next, (2, 0)), rules)['p_qualify']
        p_a2b1 = compute_ig_probability(season_with_fixed_next(season, ig_next, (2, 1)), rules)['p_qualify']
        p_a1b2 = compute_ig_probability(season_with_fixed_next(season, ig_next, (1, 2)), rules)['p_qualify']
        p_a0b2 = compute_ig_probability(season_with_fixed_next(season, ig_next, (0, 2)), rules)['p_qualify']
        if ig_team == a_side:   # IG 是 a 队（主队），IG 赢 = a 得 2 分
            p_win = (p_a2b0 + p_a2b1) / 2
            p_lose = (p_a1b2 + p_a0b2) / 2
        else:                   # IG 是 b 队（客队），IG 赢 = b 得 2 分
            p_win = (p_a1b2 + p_a0b2) / 2
            p_lose = (p_a2b0 + p_a2b1) / 2
        next_pred = {
            'date': ig_next['date'], 'a': ig_next['a'], 'b': ig_next['b'],
            'group': ig_next['group'],
            'p_if_ig_win': p_win, 'p_if_ig_lose': p_lose,
            'delta_win': p_win - p_now, 'delta_lose': p_lose - p_now,
        }

    out = {'as_of': schedule.get('as_of', ''), 'p_now': p_now,
           'impacts': impacts, 'ig_next': next_pred}
    for p in (os.path.join(ROOT, 'data', 'impact.json'),
              os.path.join(ROOT, 'web', 'data', 'impact.json')):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    if not args.quiet:
        print(f'✅ 影响分析已输出（当前概率 {p_now*100:.3f}%，{len(impacts)} 场影响，'
              f'下一场预测 {"有" if next_pred else "无"}）')


if __name__ == '__main__':
    main()

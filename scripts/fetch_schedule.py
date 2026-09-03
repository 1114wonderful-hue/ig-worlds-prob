# -*- coding: utf-8 -*-
"""从 LPL 官网接口抓取赛程/赛果，更新 season-2026.json。

接口：https://lpl.qq.com/web201612/data/LOL_MATCH2_MATCH_HOMEPAGE_BMATCH_LIST_237.js
（237 = 2026 LPL；返回全部比赛，MatchStatus 1=未开始 3=已结束）

用法：python scripts/fetch_schedule.py [--dry-run]
"""
import argparse, json, os, re, sys, urllib.request
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_PATH = os.path.join(ROOT, 'data', 'season-2026.json')
URL = 'https://lpl.qq.com/web201612/data/LOL_MATCH2_MATCH_HOMEPAGE_BMATCH_LIST_237.js'
THIRD_SPLIT_KEY = '第三赛段'


def fetch():
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', errors='replace')
    m = re.search(r'\{.*\}', text, re.S)  # JSONP 包裹，取 JSON 主体
    if not m:
        raise RuntimeError('接口返回格式异常')
    return json.loads(m.group(0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='只打印抓取结果，不写入')
    args = ap.parse_args()

    season = json.load(open(SEASON_PATH, encoding='utf-8'))
    asc_teams = set(season['split3']['ascend']['teams'])
    nir_teams = set(season['split3']['nirvana']['teams'])

    data = fetch()
    matches = data.get('msg', [])
    third = [m for m in matches if THIRD_SPLIT_KEY in m.get('GameTypeName', '')]

    upcoming = []   # MatchStatus 1 = 未开始
    finished = []   # MatchStatus 3 = 已结束
    for m in third:
        rec = {
            'match_id': m['bMatchId'],
            'a': m['TeamShortNameA'], 'b': m['TeamShortNameB'],
            'score_a': m.get('ScoreA'), 'score_b': m.get('ScoreB'),
            'date': m['MatchDate'][:16].replace(' ', 'T'),
            'status': m['MatchStatus'],
        }
        if m['MatchStatus'] == '1':
            upcoming.append(rec)
        elif m['MatchStatus'] == '3':
            finished.append(rec)

    print(f'第三赛段组内赛：已结束 {len(finished)} 场，未开始 {len(upcoming)} 场\n')
    print('== 未开始（剩余赛程）==')
    for r in sorted(upcoming, key=lambda x: x['date']):
        grp = 'ascend' if (r['a'] in asc_teams and r['b'] in asc_teams) else 'nirvana'
        print(f"  {r['date']}  {r['a']} vs {r['b']}  ({grp})")

    if args.dry_run:
        return

    # 1) 重建剩余赛程
    season['remaining_schedule'] = []
    for r in sorted(upcoming, key=lambda x: x['date']):
        grp = 'ascend' if (r['a'] in asc_teams and r['b'] in asc_teams) else 'nirvana'
        season['remaining_schedule'].append({
            'date': r['date'][:10], 'a': r['a'], 'b': r['b'], 'group': grp, 'format': 'bo3',
        })

    # 2) 用已结束比分重建各组战绩（按双循环统计）
    def reset_records(grp):
        for t in grp['teams']:
            grp['records'][t] = {'w': 0, 'l': 0, 'small_w': 0, 'small_l': 0}

    reset_records(season['split3']['ascend'])
    reset_records(season['split3']['nirvana'])

    for r in finished:
        grp = 'ascend' if (r['a'] in asc_teams and r['b'] in asc_teams) else 'nirvana'
        if r['a'] not in season['split3'][grp]['records'] or r['b'] not in season['split3'][grp]['records']:
            continue
        sa, sb = int(r['score_a']), int(r['score_b'])
        rec_a = season['split3'][grp]['records'][r['a']]
        rec_b = season['split3'][grp]['records'][r['b']]
        rec_a['small_w'] += sa; rec_a['small_l'] += sb
        rec_b['small_w'] += sb; rec_b['small_l'] += sa
        if sa > sb:
            rec_a['w'] += 1; rec_b['l'] += 1
        else:
            rec_b['w'] += 1; rec_a['l'] += 1

    season['as_of'] = data.get('lastUpTime', '')[:10]
    with open(SEASON_PATH, 'w', encoding='utf-8') as f:
        json.dump(season, f, ensure_ascii=False, indent=2)
    print(f'\n✅ 已写入 {SEASON_PATH}（数据截至 {season["as_of"]}）')
    print('== 更新后战绩 ==')
    for grp in ('ascend', 'nirvana'):
        print(f'  [{grp}]')
        for t in season['split3'][grp]['teams']:
            r = season['split3'][grp]['records'][t]
            print(f"    {t:4s} {r['w']}-{r['l']}  小分 {r['small_w']}-{r['small_l']}")

    # 3) 输出赛程 JSON（前端"赛程"模块用：第三赛段全部比赛）
    def group_of(a, b):
        return 'ascend' if (a in asc_teams and b in asc_teams) else 'nirvana'

    matches_out = []
    for m in third:
        status = 'done' if m['MatchStatus'] == '3' else ('upcoming' if m['MatchStatus'] == '1' else m['MatchStatus'])
        if status == 'done':
            score_a = int(m['ScoreA']) if m.get('ScoreA') else None
            score_b = int(m['ScoreB']) if m.get('ScoreB') else None
        else:
            score_a = score_b = None
        matches_out.append({
            'date': m['MatchDate'][:16].replace(' ', 'T'),
            'a': m['TeamShortNameA'], 'b': m['TeamShortNameB'],
            'score_a': score_a, 'score_b': score_b,
            'status': status,
            'group': group_of(m['TeamShortNameA'], m['TeamShortNameB']),
            'name': f"{m['TeamShortNameA']} vs {m['TeamShortNameB']}",
        })
    matches_out.sort(key=lambda x: x['date'])
    schedule = {'as_of': season['as_of'], 'count': len(matches_out), 'matches': matches_out}
    for p in (os.path.join(ROOT, 'data', 'schedule.json'),
              os.path.join(ROOT, 'web', 'data', 'schedule.json')):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(schedule, f, ensure_ascii=False, indent=2)
    print(f'✅ 赛程已输出: data/schedule.json + web/data/schedule.json（{len(matches_out)} 场）')

    # 4) 季后赛阶段维护：识别接口中的赛季季后赛比赛，回放更新 playoffs.fixed
    update_playoffs(season, data)


# 季后赛双败模板（与 src/engine/playoffs.py 的 _run_bracket 12 场对应）
PO_DEPS = {
    0: ('S3', 'S6'), 1: ('S4', 'S5'),
    2: ('K1', ('L', 0)), 3: ('K2', ('L', 1)),
    4: ('S1', ('W', 0)), 5: ('S2', ('W', 1)),
    6: (('W', 2), ('L', 4)), 7: (('W', 3), ('L', 5)),
    8: (('W', 4), ('W', 5)), 9: (('W', 6), ('W', 7)),
    10: (('L', 8), ('W', 9)), 11: (('W', 8), ('W', 10)),
}
# 2026 第三赛段季后赛 8 队槽位（由真实对阵反推；若官方调整需同步这里）
DEFAULT_PO_SLOTS = {'S1': 'AL', 'S2': 'BLG', 'S3': 'TES', 'S4': 'JDG',
                    'S5': 'WE', 'S6': 'LGD', 'K1': 'IG', 'K2': 'NIP'}


def _po_team(slots, win, lose, ref):
    if isinstance(ref, str):
        return slots.get(ref)
    kind, j = ref
    return win[j] if kind == 'W' else lose[j]


def update_playoffs(season, data):
    """把接口中的季后赛已结束比赛回放成 playoffs.fixed，并切 season_stage。"""
    po_matches = [m for m in data.get('msg', [])
                  if m.get('GameTypeName', '') == '2026赛季季后赛' and m.get('MatchStatus') == '3']
    if not po_matches:
        # 无季后赛（组内赛阶段）且 season 仍是组内赛 → 保持原状
        if season.get('season_stage') != 'playoffs':
            return
    po_matches.sort(key=lambda m: m['MatchDate'])
    po = season.setdefault('playoffs', {})
    po.setdefault('slots', dict(DEFAULT_PO_SLOTS))
    slots = po['slots']

    def derive():
        win = [None] * 12
        lose = [None] * 12
        pairs = {}
        fixed = {int(k): int(v) for k, v in po.get('fixed', {}).items()}
        changed = True
        while changed:
            changed = False
            for i, (ra, rb) in PO_DEPS.items():
                a = _po_team(slots, win, lose, ra)
                b = _po_team(slots, win, lose, rb)
                if a and b:
                    pairs[i] = (a, b)
                if i in fixed and win[i] is None and a and b:
                    win[i] = a if fixed[i] == 1 else b
                    lose[i] = b if fixed[i] == 1 else a
                    changed = True
        return pairs, {int(k): int(v) for k, v in po.get('fixed', {}).items()}

    new_fixed = {int(k): int(v) for k, v in po.get('fixed', {}).items()}
    for m in po_matches:
        a, b = m['TeamShortNameA'], m['TeamShortNameB']
        winner = a if int(m['ScoreA']) > int(m['ScoreB']) else b
        pairs, fixed = derive()
        # 找对阵 == {a, b} 的场次（已固定则校验，未固定则新增）
        hit = None
        for i, (pa, pb) in pairs.items():
            if {pa, pb} == {a, b}:
                hit = i
                break
        if hit is None:
            print(f'⚠️ 无法匹配季后赛已结束比赛: {a} vs {b}（检查 slots 或该场待定）')
            continue
        fw = 1 if winner == pairs[hit][0] else 0
        if hit in new_fixed:
            if new_fixed[hit] != fw:
                print(f'⚠️ 第{hit}场结果与新回放不一致（{a} vs {b}，winner={winner}）')
        else:
            new_fixed[hit] = fw
            print(f'  季后赛回放: 第{hit}场 {a} vs {b} → {winner} 胜')

    season['playoffs']['fixed'] = {str(k): int(v) for k, v in sorted(new_fixed.items())}
    season['season_stage'] = 'playoffs'
    with open(SEASON_PATH, 'w', encoding='utf-8') as f:
        json.dump(season, f, ensure_ascii=False, indent=2)
    print(f"✅ 季后赛状态已更新（已固定 {len(new_fixed)} 场）")


if __name__ == '__main__':
    main()

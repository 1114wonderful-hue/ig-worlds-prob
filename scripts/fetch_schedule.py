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


if __name__ == '__main__':
    main()

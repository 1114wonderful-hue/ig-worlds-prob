# -*- coding: utf-8 -*-
"""赛季数据录入工具（手动录入兜底 + 参考核对）。

用法（在项目根目录运行）：
    python scripts/update_season.py show
    python scripts/update_season.py add-result 2026-08-15 IG 2-1 NIP
    python scripts/update_season.py add-schedule 2026-08-16 IG WBG nirvana
    python scripts/update_season.py add-schedule 2026-08-16 TES EDG ascend
    python scripts/update_season.py remove 2            # 按索引删除赛程项
    python scripts/update_season.py recompute
    python scripts/update_season.py demo-schedule       # 生成演示赛程（仅体验用）

说明：add-result 更新战绩并从剩余赛程移除对应比赛；add-schedule 追加剩余赛程。
比分格式：BO3 用 2-0/2-1/1-2/0-2。
"""
import argparse, copy, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_PATH = os.path.join(ROOT, 'data', 'season-2026.json')
RULES_PATH = os.path.join(ROOT, 'data', 'rules.json')


def load():
    return json.load(open(SEASON_PATH, encoding='utf-8')), json.load(open(RULES_PATH, encoding='utf-8'))


def save(season):
    with open(SEASON_PATH, 'w', encoding='utf-8') as f:
        json.dump(season, f, ensure_ascii=False, indent=2)


def find_team_id(season, name):
    name = name.upper()
    for t in season['teams']:
        if t['id'] == name or t['name'].upper() == name:
            return t['id']
    return None


def cmd_show(season, rules, args):
    asc = season['split3']['ascend']; nir = season['split3']['nirvana']
    print('== 登峰组战绩 ==')
    for t in asc['teams']:
        r = asc['records'][t]
        print(f'  {t:4s} {r["w"]}-{r["l"]}  小分 {r["small_w"]}-{r["small_l"]}')
    print('== 涅槃组战绩 ==')
    for t in nir['teams']:
        r = nir['records'][t]
        print(f'  {t:4s} {r["w"]}-{r["l"]}  小分 {r["small_w"]}-{r["small_l"]}')
    print(f'== 剩余赛程（{len(season["remaining_schedule"])} 场）==')
    for i, g in enumerate(season['remaining_schedule']):
        print(f'  [{i}] {g.get("date","?"):12s} {g["a"]} vs {g["b"]} ({g.get("group","?")})')
    pts = {t['id']: sum(season['points_earned'][t['id']].values()) for t in season['teams']}
    print('== 当前全年积分（第一+第二赛段）==')
    for t, p in sorted(pts.items(), key=lambda x: -x[1]):
        print(f'  {t:4s} {p}')


def cmd_add_result(season, rules, args):
    a = find_team_id(season, args.team_a)
    b = find_team_id(season, args.team_b)
    if not a or not b:
        print(f'队伍不存在: {args.team_a}/{args.team_b}'); return
    score = args.score
    if score not in ('2-0', '2-1', '1-2', '0-2'):
        print(f'非法比分: {score}（应为 2-0/2-1/1-2/0-2）'); return
    wa, wb = score.split('-')
    small_a, small_b = int(wa), int(wb)
    winner = a if int(wa) > int(wb) else b
    group = None
    for gname, grp in (('ascend', season['split3']['ascend']), ('nirvana', season['split3']['nirvana'])):
        if a in grp['teams'] and b in grp['teams']:
            group = gname
            rec = grp['records']
            break
    if not group:
        print(f'两队不在同一组（{a} vs {b}）'); return
    rec[a]['w'] += (1 if winner == a else 0)
    rec[a]['l'] += (1 if winner != a else 0)
    rec[a]['small_w'] += small_a; rec[a]['small_l'] += small_b
    rec[b]['w'] += (1 if winner == b else 0)
    rec[b]['l'] += (1 if winner != b else 0)
    rec[b]['small_w'] += small_b; rec[b]['small_l'] += small_a
    # 从剩余赛程移除该场
    season['remaining_schedule'] = [g for g in season['remaining_schedule']
                                    if not ({g.get('a'), g.get('b')} == {a, b} and g.get('group') == group)]
    season['as_of'] = args.date or season.get('as_of')
    save(season)
    print(f'已录入: {args.date} {a} {score} {b}（{group}）')


def cmd_add_schedule(season, rules, args):
    a = find_team_id(season, args.team_a)
    b = find_team_id(season, args.team_b)
    if not a or not b:
        print(f'队伍不存在: {args.team_a}/{args.team_b}'); return
    group = args.group or ('ascend' if a in season['split3']['ascend']['teams'] else 'nirvana')
    season['remaining_schedule'].append({'date': args.date, 'a': a, 'b': b, 'group': group, 'format': 'bo3'})
    save(season)
    print(f'已添加赛程: {args.date} {a} vs {b}（{group}）')


def cmd_remove(season, rules, args):
    i = args.index
    if 0 <= i < len(season['remaining_schedule']):
        removed = season['remaining_schedule'].pop(i)
        save(season)
        print(f'已移除: {removed}')
    else:
        print(f'索引越界: {i}')


def cmd_recompute(season, rules, args):
    sys.path.insert(0, os.path.join(ROOT, 'src'))
    from engine.enumerate import compute_ig_probability
    res = compute_ig_probability(season, rules, verbose=True)
    print(f'\n===== IG 进世界赛概率: {res["p_qualify"]*100:.3f}% =====')
    print(f'  1号种子: {res["p_seed1"]*100:.3f}%')
    print(f'  2号种子: {res["p_seed2"]*100:.3f}%')
    print(f'  3号种子: {res["p_seed3"]*100:.3f}%')
    print(f'  4号种子: {res["p_seed4"]*100:.3f}%')
    bd = res['breakdown']
    print(f'  （分解）种子1: {bd["seed1"]*100:.3f}% | 冒泡赛胜者组: {bd["qualifier_upper"]*100:.3f}% | '
          f'冒泡赛败者组: {bd["qualifier_lower"]*100:.3f}% | 出局: {bd["out"]*100:.3f}%')


def cmd_demo_schedule(season, rules, args):
    """生成演示赛程（基于各队剩余场次的占位对阵，仅用于体验引擎流程）。"""
    asc_teams = season['split3']['ascend']['teams']
    nir_teams = season['split3']['nirvana']['teams']
    pairs = [(asc_teams[i], asc_teams[j]) for i in range(8) for j in range(i + 1, 8)]
    demo = []
    for k, (a, b) in enumerate(pairs[:23]):
        demo.append({'date': f'2026-08-{15 + k % 14:02d}', 'a': a, 'b': b, 'group': 'ascend', 'format': 'bo3'})
    season['remaining_schedule'] = demo
    save(season)
    print(f'已生成 {len(demo)} 场演示登峰赛程（⚠️ 仅为演示占位，非真实赛程，请用 add-result/add-schedule 替换）')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='LPL 2026 赛季数据录入')
    sub = ap.add_subparsers(dest='cmd')
    sub.add_parser('show')
    p = sub.add_parser('add-result')
    p.add_argument('date'); p.add_argument('team_a'); p.add_argument('score'); p.add_argument('team_b')
    p = sub.add_parser('add-schedule')
    p.add_argument('date'); p.add_argument('team_a'); p.add_argument('team_b'); p.add_argument('group', nargs='?')
    p = sub.add_parser('remove'); p.add_argument('index', type=int)
    sub.add_parser('recompute')
    sub.add_parser('demo-schedule')
    args = ap.parse_args()
    if not args.cmd:
        ap.print_help(); return
    season, rules = load()
    {'show': cmd_show, 'add-result': cmd_add_result, 'add-schedule': cmd_add_schedule,
     'remove': cmd_remove, 'recompute': cmd_recompute,
     'demo-schedule': cmd_demo_schedule}[args.cmd](season, rules, args)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""每日更新流程：录入赛果 → 重算 → 存档快照。

用法：
    python scripts/daily_update.py                 # 全流程（展示 → 提示 → 重算 → 存档）
    python scripts/daily_update.py --date 2026-08-15
    python scripts/daily_update.py --fetch         # 先抓萌娘百科战绩作参考（仅打印，需人工核对）

建议每日流程：
1. 打开 LPL 官网/直播平台确认当天赛果与剩余赛程
2. python scripts/update_season.py add-result <日期> <队A> <比分> <队B>   （逐场录入）
3. python scripts/update_season.py add-schedule <日期> <队A> <队B> <组>   （更新剩余赛程）
4. python scripts/daily_update.py --date <日期>                            （重算+存档）
"""
import argparse, copy, datetime, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON_PATH = os.path.join(ROOT, 'data', 'season-2026.json')
SNAPSHOT_DIR = os.path.join(ROOT, 'data', 'snapshots')


def fetch_reference():
    """抓取萌娘百科 2026 页面第三赛段战绩区（仅打印，供人工核对）。"""
    import urllib.request
    url = 'https://zh.moegirl.org.cn/2026%E8%8B%B1%E9%9B%84%E8%81%94%E7%9B%9F%E8%81%8C%E4%B8%9A%E8%81%94%E8%B5%9B'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    html = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', errors='replace')
    print(f'已抓取萌娘百科页面（{len(html)} 字节）。注意：该页战绩矩阵存在不一致（已核实），仅供人工参考，'
          f'请以官方直播间/赛事页为准，并用 update_season.py 手动录入。')
    # 打印第三赛段附近文本
    i = html.find('第三赛段')
    if i >= 0:
        seg = html[i:i + 8000]
        import re
        txt = re.sub(r'<[^>]+>', ' ', seg)
        txt = re.sub(r'\s+', ' ', txt)
        print(txt[:3000])


def snapshot(season, results, date):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    path = os.path.join(SNAPSHOT_DIR, f'{date}.json')
    payload = {
        'date': date,
        'p_qualify': results['p_qualify'],
        'p_seed1': results['p_seed1'], 'p_seed2': results['p_seed2'],
        'p_seed3': results['p_seed3'], 'p_seed4': results['p_seed4'],
        'breakdown': results['breakdown'],
        'ig_base_points': results['ig_base_points'],
        'season_snapshot': season,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'快照已存档: {path}')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='LPL 2026 每日更新')
    ap.add_argument('--date', default=datetime.date.today().isoformat())
    ap.add_argument('--fetch', action='store_true', help='先抓取萌娘百科战绩参考')
    ap.add_argument('--no-snapshot', action='store_true')
    args = ap.parse_args()

    if args.fetch:
        fetch_reference()
        print()

    sys.path.insert(0, os.path.join(ROOT, 'src'))
    from engine.enumerate import compute_ig_probability

    season = json.load(open(SEASON_PATH, encoding='utf-8'))
    rules = json.load(open(os.path.join(ROOT, 'data', 'rules.json'), encoding='utf-8'))

    print(f'===== 每日更新（{args.date}）=====')
    print('剩余赛程场次:', len(season['remaining_schedule']))
    print('若尚未录入当天赛果，请先运行:')
    print('  python scripts/update_season.py add-result <日期> <队A> <比分> <队B>')
    print()

    res = compute_ig_probability(season, rules, verbose=True)
    print(f'\n===== IG 进世界赛概率: {res["p_qualify"]*100:.3f}% =====')
    print(f'  1号种子: {res["p_seed1"]*100:.3f}% | 2号种子: {res["p_seed2"]*100:.3f}%')
    print(f'  3号种子: {res["p_seed3"]*100:.3f}% | 4号种子: {res["p_seed4"]*100:.3f}%')

    if not args.no_snapshot:
        snapshot(season, res, args.date)

    # 输出最新结果供前端读取
    current = {
        'date': args.date,
        'p_qualify': res['p_qualify'],
        'p_seed1': res['p_seed1'], 'p_seed2': res['p_seed2'],
        'p_seed3': res['p_seed3'], 'p_seed4': res['p_seed4'],
        'breakdown': res['breakdown'],
        'ig_base_points': res['ig_base_points'],
        'nirvana_cases': res['nirvana_cases'],
        'ascend_cases': res['ascend_cases'],
        'remaining_games': len(season['remaining_schedule']),
    }
    with open(os.path.join(ROOT, 'data', 'current.json'), 'w', encoding='utf-8') as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    print('最新结果已写入: data/current.json')

    # 生成趋势数据（追加到 data/trend.json）
    trend_path = os.path.join(ROOT, 'data', 'trend.json')
    trend = []
    if os.path.exists(trend_path):
        trend = json.load(open(trend_path, encoding='utf-8'))
    trend = [t for t in trend if t['date'] != args.date]
    trend.append({'date': args.date, 'p_qualify': res['p_qualify'],
                  'p_seed1': res['p_seed1'], 'p_seed2': res['p_seed2'],
                  'p_seed3': res['p_seed3'], 'p_seed4': res['p_seed4']})
    trend.sort(key=lambda t: t['date'])
    with open(trend_path, 'w', encoding='utf-8') as f:
        json.dump(trend, f, ensure_ascii=False, indent=2)
    print(f'趋势已更新: data/trend.json（{len(trend)} 条）')

    # 同步到 web/data/ 供静态站读取（页面相对路径 fetch('data/...')）
    os.makedirs(os.path.join(ROOT, 'web', 'data'), exist_ok=True)
    import shutil
    for name in ('current.json', 'trend.json'):
        src = os.path.join(ROOT, 'data', name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(ROOT, 'web', 'data', name))
    print('已同步到 web/data/（供页面读取）')

    # 给页面资源注入版本号（绕过浏览器缓存：每次更新后强制拉取新版 app.js/style.css）
    import time as _time, re as _re
    ts = _time.strftime('%Y%m%d%H%M')
    for p in (os.path.join(ROOT, 'web', 'index.html'),
              os.path.join(ROOT, 'docs', 'index.html')):
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8') as f:
            html = f.read()
        html = _re.sub(r'(app\.js|style\.css)(\?v=\d+)?', r'\1?v=' + ts, html)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(html)
    print(f'已注入资源版本号 v={ts}（绕过浏览器缓存）')


if __name__ == '__main__':
    main()

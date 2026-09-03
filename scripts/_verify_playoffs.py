# 临时验证：季后赛阶段引擎
import copy, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
sys.stdout.reconfigure(encoding='utf-8')
from engine.enumerate import compute_ig_probability

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
season = json.load(open(os.path.join(ROOT, 'data', 'season-2026.json'), encoding='utf-8'))
rules = json.load(open(os.path.join(ROOT, 'data', 'rules.json'), encoding='utf-8'))

season['season_stage'] = 'playoffs'
season['playoffs'] = {
    'slots': {'S1': 'AL', 'S2': 'BLG', 'S3': 'TES', 'S4': 'JDG',
              'S5': 'WE', 'S6': 'LGD', 'K1': 'IG', 'K2': 'NIP'},
    'fixed': {'0': 0, '1': 0, '5': 1},   # LGD>TES, WE>JDG, BLG>WE
}

res = compute_ig_probability(season, rules, verbose=True)
print(f'\n季后赛阶段 IG 概率: {res["p_qualify"]*100:.3f}%')
print(f'  1号种子: {res["p_seed1"]*100:.3f}%')
print(f'  2号种子: {res["p_seed2"]*100:.3f}%')
print(f'  3号种子: {res["p_seed3"]*100:.3f}%')
print(f'  4号种子: {res["p_seed4"]*100:.3f}%')
bd = res['breakdown']
tot = res['p_seed1']+res['p_seed2']+bd['qualifier_upper']+bd['qualifier_lower']+bd['out']
print(f'  守恒: {tot:.6f}（应为 1） | 分支数 {res["playoff_branches"]}')
assert abs(tot - 1) < 1e-9, '守恒失败'
assert res['playoff_branches'] == 512, f'分支数 {res["playoff_branches"]}'
print('OK: 守恒且分支数正确（12场-3场固定=512）')

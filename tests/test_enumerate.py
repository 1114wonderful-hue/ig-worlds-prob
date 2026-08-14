# -*- coding: utf-8 -*-
"""穷举器/资格聚合单元测试。
运行：python tests/test_enumerate.py
"""
import copy, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from engine.enumerate import compute_ig_probability

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEASON = json.load(open(os.path.join(ROOT, 'data', 'season-2026.json'), encoding='utf-8'))
RULES = json.load(open(os.path.join(ROOT, 'data', 'rules.json'), encoding='utf-8'))

passed = 0

def check(name, cond):
    global passed
    assert cond, f'FAIL: {name}'
    passed += 1
    print(f'  ok - {name}')

print('== 1. 空剩余赛程：守恒与基准 ==')
res0 = compute_ig_probability(SEASON, RULES)
bd = res0['breakdown']
tot = res0['p_seed1'] + res0['p_seed2'] + bd['qualifier_upper'] + bd['qualifier_lower'] + bd['out']
check('breakdown 权重守恒 = 1', abs(tot - 1.0) < 1e-9)
check('p_qualify = seed1+2+3+4', abs(res0['p_qualify'] - (res0['p_seed1'] + res0['p_seed2'] + res0['p_seed3'] + res0['p_seed4'])) < 1e-12)
check('IG 进世界赛概率 > 0 且 < 0.2', 0 < res0['p_qualify'] < 0.2)
check('seed2 概率极小（IG 基础积分太低，仅极端分支可能）', 0 <= res0['p_seed2'] < 0.001)

print('== 2. 涅槃剩余 1 场（IG vs WBG）：IG 输赢都不影响进前 2 → 概率不变 ==')
s2 = copy.deepcopy(SEASON)
s2['remaining_schedule'] = [{'a': 'IG', 'b': 'WBG', 'group': 'nirvana', 'format': 'bo3'}]
res2 = compute_ig_probability(s2, RULES)
check('概率与空赛程一致', abs(res2['p_qualify'] - res0['p_qualify']) < 1e-9)

print('== 3. 涅槃剩余 3 场（IG 可能被 WBG 反超掉出前 2）→ 概率下降 ==')
s3 = copy.deepcopy(SEASON)
s3['remaining_schedule'] = [
    {'a': 'IG', 'b': 'NIP', 'group': 'nirvana', 'format': 'bo3'},
    {'a': 'IG', 'b': 'WBG', 'group': 'nirvana', 'format': 'bo3'},
    {'a': 'WBG', 'b': 'LNG', 'group': 'nirvana', 'format': 'bo3'},
]
res3 = compute_ig_probability(s3, RULES)
check('概率下降', res3['p_qualify'] < res0['p_qualify'] - 1e-9)
check('出局权重上升', res3['breakdown']['out'] > bd['out'] - 1e-12)

print('== 4. 登峰组剩余 2 场（TES vs EDG、BLG vs EDG）：EDG 可能翻盘，IG 概率变化微小但守恒 ==')
s4 = copy.deepcopy(SEASON)
s4['remaining_schedule'] = [
    {'a': 'TES', 'b': 'EDG', 'group': 'ascend', 'format': 'bo3'},
    {'a': 'BLG', 'b': 'EDG', 'group': 'ascend', 'format': 'bo3'},
]
res4 = compute_ig_probability(s4, RULES)
bd4 = res4['breakdown']
tot4 = res4['p_seed1'] + res4['p_seed2'] + bd4['qualifier_upper'] + bd4['qualifier_lower'] + bd4['out']
check('breakdown 权重守恒 = 1（登峰 DP 路径）', abs(tot4 - 1.0) < 1e-9)

print('== 5. 大规模登峰剩余场次（23 场）DP 性能与守恒 ==')
import time
s5 = copy.deepcopy(SEASON)
# 构造登峰组剩余 23 场的演示赛程（任意双循环剩余场次，仅用于性能/守恒验证）
asc_teams = list(SEASON['split3']['ascend']['teams'])
games = []
# 简化：8 队循环补足，保证每场不重复（23 场演示数据）
pairs = [(asc_teams[i], asc_teams[j]) for i in range(8) for j in range(i + 1, 8)]
games = [{'a': a, 'b': b, 'group': 'ascend', 'format': 'bo3'} for (a, b) in pairs[:23]]
s5['remaining_schedule'] = games
t0 = time.time()
res5 = compute_ig_probability(s5, RULES)
dt = time.time() - t0
print(f'  23 场登峰 DP 耗时: {dt:.2f}s')
bd5 = res5['breakdown']
tot5 = res5['p_seed1'] + res5['p_seed2'] + bd5['qualifier_upper'] + bd5['qualifier_lower'] + bd5['out']
check('23 场场景权重守恒 = 1', abs(tot5 - 1.0) < 1e-9)
check('耗时 < 120s', dt < 120)

print(f'\n全部通过: {passed} 项断言')

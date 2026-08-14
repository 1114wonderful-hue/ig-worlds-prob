# -*- coding: utf-8 -*-
"""资格判定函数单元测试（含 2025 真实数据基准验证）。

运行：python tests/test_qualify.py
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from engine.qualify import (evaluate_qualification, rank_teams,
                            STATUS_SEED1, STATUS_SEED2,
                            STATUS_QUALIFIER_UPPER, STATUS_QUALIFIER_LOWER,
                            STATUS_OUT)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = json.load(open(os.path.join(ROOT, 'data', 'rules.json'), encoding='utf-8'))

passed = 0

def check(name, cond):
    global passed
    assert cond, f'FAIL: {name}'
    passed += 1
    print(f'  ok - {name}')

print('== 场景 1: IG 是第三赛段冠军 -> 1 号种子 ==')
r = evaluate_qualification('IG', {'IG': 220, 'BLG': 300}, {'IG': 220, 'BLG': 10}, 'IG', RULES)
check('status=seed1', r.status == STATUS_SEED1)
check('p_qualify=1.0', abs(r.p_qualify - 1.0) < 1e-9)

print('== 场景 2: IG 除冠军外积分第一 -> 2 号种子 ==')
r = evaluate_qualification('IG', {'IG': 300, 'BLG': 400, 'TES': 100}, {'IG': 100, 'BLG': 220, 'TES': 10}, 'BLG', RULES)
check('status=seed2', r.status == STATUS_SEED2)
check('p_qualify=1.0', abs(r.p_qualify - 1.0) < 1e-9)

print('== 场景 3: IG 冒泡赛胜者组 -> p=0.75 (3号=0.5, 4号=0.25) ==')
total = {'IG': 150, 'A': 400, 'B': 300, 'C': 200, 'D': 100, 'E': 50}
s3 = {'IG': 110, 'A': 220, 'B': 80, 'C': 40, 'D': 30, 'E': 10}
r = evaluate_qualification('IG', total, s3, 'A', RULES)
check('status=qualifier_upper', r.status == STATUS_QUALIFIER_UPPER)
check('p_seed3=0.5', abs(r.p_seed3 - 0.5) < 1e-9)
check('p_seed4=0.25', abs(r.p_seed4 - 0.25) < 1e-9)
check('p_qualify=0.75', abs(r.p_qualify - 0.75) < 1e-9)

print('== 场景 4: IG 冒泡赛败者组 -> p=0.25 ==')
total = {'IG': 80, 'A': 400, 'B': 300, 'C': 200, 'D': 150, 'E': 100, 'F': 50}
s3 = {'IG': 60, 'A': 220, 'B': 80, 'C': 40, 'D': 30, 'E': 20, 'F': 10}
r = evaluate_qualification('IG', total, s3, 'A', RULES)
check('status=qualifier_lower', r.status == STATUS_QUALIFIER_LOWER)
check('p_qualify=0.25', abs(r.p_qualify - 0.25) < 1e-9)

print('== 场景 5: IG 积分第 7 -> out ==')
total = {'IG': 40, 'A': 400, 'B': 300, 'C': 200, 'D': 150, 'E': 120, 'F': 100, 'G': 90}
s3 = {'IG': 10, 'A': 220, 'B': 80, 'C': 40, 'D': 30, 'E': 20, 'F': 15, 'G': 10}
r = evaluate_qualification('IG', total, s3, 'A', RULES)
check('status=out', r.status == STATUS_OUT)
check('p_qualify=0.0', abs(r.p_qualify) < 1e-9)

print('== 场景 6: 并列 tiebreak - 总分相同看第三赛段积分 ==')
total = {'IG': 100, 'X': 100, 'A': 400}
s3 = {'IG': 40, 'X': 60, 'A': 220}
order = rank_teams(total, s3)
check('X 排在 IG 前', order.index('X') < order.index('IG'))
r_x = evaluate_qualification('X', total, s3, 'A', RULES)
check('X 靠第三赛段积分更高拿到 2 号种子', r_x.status == STATUS_SEED2)
r_ig = evaluate_qualification('IG', total, s3, 'A', RULES)
check('IG 被挤到冒泡赛胜者组', r_ig.status == STATUS_QUALIFIER_UPPER and r_ig.bracket == 'upper')

print('== 场景 7: 冠军不是积分第一（冠军总排名第 3）-> 顺延递补 ==')
# 总排名: A=400(冠军,第3), B=500, C=450, D=300, E=250, F=200, IG=150
# 冠军 A(400) 是总排名第 3 -> 2号=B(500)；冒泡赛 = 剩余前4 = C(450),D(300),E(250),F(200)
total = {'A': 400, 'B': 500, 'C': 450, 'D': 300, 'E': 250, 'F': 200, 'IG': 150}
s3 = {'A': 220, 'B': 60, 'C': 40, 'D': 30, 'E': 20, 'F': 10, 'IG': 10}
r_b = evaluate_qualification('B', total, s3, 'A', RULES)
check('B 是 2 号种子', r_b.status == STATUS_SEED2)
r_c = evaluate_qualification('C', total, s3, 'A', RULES)
check('C 进冒泡赛胜者组', r_c.status == STATUS_QUALIFIER_UPPER and r_c.bracket == 'upper')
r_f = evaluate_qualification('F', total, s3, 'A', RULES)
check('F 进冒泡赛败者组', r_f.status == STATUS_QUALIFIER_LOWER and r_f.bracket == 'lower')
r_ig = evaluate_qualification('IG', total, s3, 'A', RULES)
check('IG 未进冒泡赛', r_ig.status == STATUS_OUT)

print('== 基准验证: 2025 真实数据（BLG 冠军）==')
total2025 = {'BLG': 300, 'AL': 185, 'TES': 150, 'IG': 95, 'JDG': 80, 'WBG': 65, 'WE': 30,
             'NIP': 15, 'EDG': 10, 'FPX': 10, 'TT': 5, 'LGD': 0, 'LNG': 0, 'OMG': 0}
s32025 = {'BLG': 220, 'AL': 80, 'TES': 110, 'IG': 40, 'JDG': 60, 'WBG': 40, 'WE': 0,
          'NIP': 10, 'EDG': 10, 'FPX': 0, 'TT': 0, 'LGD': 0, 'LNG': 0, 'OMG': 0}
res = {t: evaluate_qualification(t, total2025, s32025, 'BLG', RULES) for t in total2025}
check('BLG = seed1', res['BLG'].status == STATUS_SEED1)
check('AL = seed2', res['AL'].status == STATUS_SEED2)
check('TES = 胜者组', res['TES'].status == STATUS_QUALIFIER_UPPER)
check('IG = 胜者组', res['IG'].status == STATUS_QUALIFIER_UPPER)
check('JDG = 败者组', res['JDG'].status == STATUS_QUALIFIER_LOWER)
check('WBG = 败者组', res['WBG'].status == STATUS_QUALIFIER_LOWER)
check('WE = out', res['WE'].status == STATUS_OUT)

print(f'\n全部通过: {passed} 项断言')

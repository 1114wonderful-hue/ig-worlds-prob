# -*- coding: utf-8 -*-
"""季后赛模拟器单元测试。
运行：python tests/test_playoffs.py
"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))
sys.stdout.reconfigure(encoding='utf-8')

from engine.playoffs import simulate_playoffs, champion_probs, slot_to_split3_points

passed = 0

def check(name, cond):
    global passed
    assert cond, f'FAIL: {name}'
    passed += 1
    print(f'  ok - {name}')

slots = {'S1': 'TES', 'S2': 'BLG', 'S3': 'AL', 'S4': 'WE',
         'S5': 'JDG', 'S6': 'TT', 'K1': 'IG', 'K2': 'NIP'}
dist = simulate_playoffs(slots)
probs = champion_probs(dist)

print('== 基本守恒 ==')
total_champ = sum(probs.values())
check('冠军概率和 = 1', abs(total_champ - 1.0) < 1e-9)
for t in slots.values():
    s = sum(dist[t].values())
    check(f'{t} 名次分布和 = 1', abs(s - 1.0) < 1e-9)

print('== 对称性（同槽位类型冠军概率相等）==')
check('S1 == S2', abs(probs['TES'] - probs['BLG']) < 1e-12)
check('S3..S6 相等', all(abs(probs['AL'] - probs[x]) < 1e-12 for x in ['WE', 'JDG', 'TT']))
check('K1 == K2', abs(probs['IG'] - probs['NIP']) < 1e-12)

print('== 轮空/起始位置优势 ==')
p_s1, p_s3, p_k = probs['TES'], probs['AL'], probs['IG']
print(f'  冠军概率: 登峰1={p_s1:.6f} 登峰3={p_s3:.6f} 骑士之路={p_k:.6f}')
check('S1 冠军概率 > S3', p_s1 > p_s3)
check('S3 冠军概率 > K', p_s3 > p_k)
check('S1 冠军概率在合理区间（轮空优势）', 0.15 < p_s1 < 0.30)
check('K 位夺冠 = 5 连胜 = 1/32', abs(p_k - 1/32) < 1e-12)

print('== 名次 → 第三赛段积分映射 ==')
table = {'1': 220, '2': 110, '3': 80, '4': 60, '5-6': 40, '7-8': 10, '9-12': 0}
check('1->220', slot_to_split3_points('1', table) == 220)
check('5-6->40', slot_to_split3_points('5-6', table) == 40)
check('7-8->10', slot_to_split3_points('7-8', table) == 10)

print('== 名次分布示例（IG 从骑士之路/败者组第 1 轮）==')
ig = dist['IG']
print('  IG:', {k: round(v, 4) for k, v in ig.items()})
check('IG 夺冠概率较小', 0 < ig['1'] < 0.05)

print(f'\n全部通过: {passed} 项断言')

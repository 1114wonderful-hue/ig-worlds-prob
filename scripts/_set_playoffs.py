# 临时：把 season-2026.json 切换到季后赛阶段（写入 playoffs 配置）
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(ROOT, 'data', 'season-2026.json')
s = json.load(open(p, encoding='utf-8'))
s['season_stage'] = 'playoffs'
s['playoffs'] = {
    "note": "2026 赛季季后赛（8 队双败 BO5）。slots 按真实对阵反推：AL/BLG 胜者组 R2 轮空，TES/LGD/JDG/WE 胜者组 R1，IG/NIP（骑士之路晋级）败者组 R1。fixed 为已打完场次（_run_bracket o 语义，o[i]=1 表示场次 i 第一个候选胜）。",
    "slots": {"S1": "AL", "S2": "BLG", "S3": "TES", "S4": "JDG",
              "S5": "WE", "S6": "LGD", "K1": "IG", "K2": "NIP"},
    "fixed": {"0": 0, "1": 0, "5": 1}
}
# 季后赛已打完：LGD 3-2 TES(场0: S3=TES输)、WE 3-1 JDG(场1)、BLG 3-1 WE(场5: S2=BLG胜 wb2=WE)
json.dump(s, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('已切换季后赛模式:', s['playoffs']['slots'])

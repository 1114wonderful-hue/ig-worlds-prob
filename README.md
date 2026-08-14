# IG 进世界赛概率计算器（LPL 2026）

基于 **2026 LPL 官方规则** 与 **纯穷举/等概率模型**，计算 IG 进入 2026 全球总决赛（S16）的概率，随每日战况更新。

## 核心思路

- **纯穷举、无实力判断**：BO3 的四种比分（2:0 / 2:1 / 1:2 / 0:2）等概率各 1/4；BO5 六种比分各 1/6。不考虑纸面强弱。
- **不仅考虑 IG 战绩，还穷举所有队伍剩余比赛**（别的队伍胜负直接影响全年积分排名与冒泡赛资格）。
- **全年积分制**（2026 官方规则，见 `docs/rules-2026.md`）：
  - 全年积分 = 第一赛段 + 第二赛段 + 第三赛段（赛季季后赛名次）积分
  - 1 号种子 = 第三赛段冠军；2 号种子 = 除冠军外全年积分第一
  - 3/4 号种子 = 全球总决赛资格赛（冒泡赛，积分 3-6 名）
  - 2026 年 LPL 共 **4 个名额**（3 基础 + MSI 成绩第二好赛区加成）

## 分层计算（精确）

1. **涅槃组**：剩余比赛少，`4^N` 字面穷举（含小分 tiebreak）
2. **登峰组**：剩余比赛多（如 23 场），用**胜场 DP** 聚合排名分布（避免 4^23 爆炸）；
   并列按「均匀打破」近似（真实规则为小分 tiebreak，误差限于并列边界场景）
3. **骑士之路**：BO5 等概率，胜者进季后赛
4. **赛季季后赛**：8 队双败，`2^12 = 4096` 个胜负分支字面穷举，得各队名次分布
5. **资格判定**：每个分支算全年积分 → 判定 IG 的种子/冒泡赛资格 → 加权聚合

## 目录结构

```
ig-worlds-prob/
├── docs/rules-2026.md        # 规则核实文档（含待确认项与来源）
├── data/
│   ├── rules.json            # 规则参数配置（积分档位/名额/冒泡赛/等概率模型）
│   ├── season-2026.json      # 赛季数据（14 队、战绩、剩余赛程——赛程待录入）
│   ├── snapshots/            # 每日快照存档（自动生成）
│   └── trend.json            # 历史趋势（自动生成）
├── src/engine/
│   ├── qualify.py            # 资格判定（种子/冒泡赛/并列）
│   ├── playoffs.py           # 季后赛 8 队双败等概率模拟
│   └── enumerate.py          # 分层穷举器（涅槃穷举+登峰 DP+资格聚合）
├── scripts/
│   ├── update_season.py      # 数据录入工具（手动兜底）
│   ├── daily_update.py       # 每日更新流程（重算+快照+趋势）
│   └── mc_validate.py        # 蒙特卡洛独立对照（可选验证）
└── tests/                    # 单元测试（qualify/playoffs/enumerate）
```

## 每日使用流程

1. 查看当天 LPL 赛果与剩余赛程（官网/直播平台）
2. 录入赛果（逐场）：
   ```
   python scripts/update_season.py add-result 2026-08-15 IG 2-1 WBG
   ```
3. 更新剩余赛程（如官方公布新赛程）：
   ```
   python scripts/update_season.py add-schedule 2026-08-16 IG NIP nirvana
   ```
4. 重算并存档：
   ```
   python scripts/daily_update.py --date 2026-08-15
   ```
5. 查看结果：
   ```
   python scripts/update_season.py show
   python scripts/update_season.py recompute
   ```

## 运行测试

```
python tests\test_qualify.py
python tests\test_playoffs.py
python tests\test_enumerate.py
python scripts\mc_validate.py        # 蒙特卡洛对照（约 1 分钟）
```

## 已知限制与待确认项

- ⚠️ 2026 第三赛段积分档位暂按 2025（220/110/80/60/40/10），官方公布后改 `data/rules.json`
- ⚠️ 季后赛对阵结构（登峰前 2 轮空、骑士之路 2 队进败者组）为按官方描述推断，赛程公布后校准 `src/engine/playoffs.py`
- ⚠️ 登峰组并列 tiebreak 用「均匀打破」近似（真实为小分）
- ⚠️ IG 未进季后赛时按出局处理（当前 IG 基础积分 10 分必然出局；若基础积分提高需扩展）
- 数据以手动录入为主（半自动：萌娘百科参考 + 人工校验）
- 剩余赛程当前为空，需先录入（`demo-schedule` 命令可生成演示赛程体验流程）

## 当前结果（数据截至 season-2026.json 快照）

运行 `python scripts/update_season.py recompute` 查看最新概率。

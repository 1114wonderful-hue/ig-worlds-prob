# 临时：查看接口中第三赛段季后赛/骑士之路/资格赛的比赛
import re, json, urllib.request, sys
sys.stdout.reconfigure(encoding='utf-8')

url = 'https://lpl.qq.com/web201612/data/LOL_MATCH2_MATCH_HOMEPAGE_BMATCH_LIST_237.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8', 'replace')
m = re.search(r'\{.*\}', text, re.S)
data = json.loads(m.group(0))

# 收集 8 月之后的比赛（第三赛段组内赛末尾 + 骑士之路 + 季后赛）
for mm in data.get('msg', []):
    gt = mm.get('GameTypeName', '')
    gp = mm.get('GameProcName', '')
    md = mm['MatchDate'][:10]
    if md >= '2026-08-20':
        status = {'1': '未开始', '3': '已结束'}.get(mm['MatchStatus'], mm['MatchStatus'])
        print(f"{md} | {gt} | {gp} | {mm['TeamShortNameA']} vs {mm['TeamShortNameB']} "
              f"| {mm.get('ScoreA')}-{mm.get('ScoreB')} | {status}")

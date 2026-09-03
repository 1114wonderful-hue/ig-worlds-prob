// app.js — 加载 data/current.json 与 data/trend.json 渲染页面
(function () {
  const pct = (v) => (v * 100).toFixed(2) + '%';

  async function load() {
    const [cur, trend] = await Promise.all([
      fetch('data/current.json').then(r => r.json()).catch(() => null),
      fetch('data/trend.json').then(r => r.json()).catch(() => null),
    ]);
    if (!cur) {
      document.getElementById('big-number').textContent = '--';
      document.getElementById('data-date').textContent = '未生成';
      document.querySelector('#trend-empty').style.display = 'block';
      document.getElementById('meta-line').textContent =
        '尚未生成结果：先运行 python scripts/daily_update.py --date <日期> 生成 data/current.json（本地需用 http 服务打开）。';
      return;
    }

    document.getElementById('big-number').textContent = pct(cur.p_qualify);
    document.getElementById('data-date').textContent = cur.date;
    document.getElementById('s1').textContent = pct(cur.p_seed1);
    document.getElementById('s2').textContent = pct(cur.p_seed2);
    document.getElementById('s3').textContent = pct(cur.p_seed3);
    document.getElementById('s4').textContent = pct(cur.p_seed4);

    const setBar = (id, v) => { document.getElementById(id).style.width = (v * 100) + '%'; };
    setBar('bar-s1', cur.p_seed1); document.getElementById('pct-s1').textContent = pct(cur.p_seed1);
    setBar('bar-s2', cur.p_seed2); document.getElementById('pct-s2').textContent = pct(cur.p_seed2);
    setBar('bar-s3', cur.p_seed3); document.getElementById('pct-s3').textContent = pct(cur.p_seed3);
    setBar('bar-s4', cur.p_seed4); document.getElementById('pct-s4').textContent = pct(cur.p_seed4);
    setBar('bar-out', cur.breakdown.out); document.getElementById('pct-out').textContent = pct(cur.breakdown.out);

    document.getElementById('meta-line').textContent =
      `IG 当前全年积分 ${cur.ig_base_points} 分 · 剩余 ${cur.remaining_games} 场比赛待定 · ` +
      `引擎分解：${cur.nirvana_cases} 个涅槃类别 × ${cur.ascend_cases} 个登峰排名组合 × 4096 个季后赛分支`;

    if (cur.stage === 'playoffs') {
      const badge = document.getElementById('stage-badge');
      badge.style.display = 'inline-block';
      badge.textContent = '🏆 IG 已晋级季后赛 · 双败淘汰 BO5 进行中';
    }

    if (trend && trend.length >= 2) {
      const chart = echarts.init(document.getElementById('trend-chart'));
      chart.setOption({
        backgroundColor: 'transparent',
        tooltip: { trigger: 'axis', valueFormatter: v => (v * 100).toFixed(2) + '%' },
        legend: { textStyle: { color: '#8a8f98' }, data: ['进世界赛', '1号', '2号', '3号', '4号'] },
        grid: { left: 48, right: 16, top: 40, bottom: 32 },
        xAxis: { type: 'category', data: trend.map(t => t.date),
                 axisLabel: { color: '#8a8f98' }, axisLine: { lineStyle: { color: '#262c38' } } },
        yAxis: { type: 'value', axisLabel: { color: '#8a8f98', formatter: v => (v * 100).toFixed(0) + '%' },
                 splitLine: { lineStyle: { color: '#1d2330' } } },
        series: [
          { name: '进世界赛', type: 'line', smooth: true, data: trend.map(t => t.p_qualify),
            lineStyle: { color: '#d4af37', width: 3 }, itemStyle: { color: '#d4af37' }, symbol: 'circle' },
          { name: '1号', type: 'line', data: trend.map(t => t.p_seed1), lineStyle: { color: '#d4af37', width: 1 }, itemStyle: { color: '#d4af37' }, symbol: 'none' },
          { name: '2号', type: 'line', data: trend.map(t => t.p_seed2), lineStyle: { color: '#c9a06c', width: 1 }, itemStyle: { color: '#c9a06c' }, symbol: 'none' },
          { name: '3号', type: 'line', data: trend.map(t => t.p_seed3), lineStyle: { color: '#6ea8fe', width: 1 }, itemStyle: { color: '#6ea8fe' }, symbol: 'none' },
          { name: '4号', type: 'line', data: trend.map(t => t.p_seed4), lineStyle: { color: '#9d7bd8', width: 1 }, itemStyle: { color: '#9d7bd8' }, symbol: 'none' },
        ],
      });
      window.addEventListener('resize', () => chart.resize());
    } else {
      document.getElementById('trend-empty').style.display = 'block';
      document.getElementById('trend-chart').style.display = 'none';
    }
  }

  load();

  // ============ 比赛影响分析模块 ============
  async function loadImpact() {
    let imp = null;
    try {
      imp = await (await fetch('data/impact.json')).json();
    } catch (e) {
      document.getElementById('impact-empty').style.display = 'block';
      return;
    }
    const nextBox = document.getElementById('ig-next-box');
    const listEl = document.getElementById('impact-list');
    const fmt = (v) => (v * 100).toFixed(2) + '%';
    const delta = (v) => (v >= 0 ? '▲ +' : '▼ ') + (v * 100).toFixed(2) + '%';

    if (imp.ig_next) {
      const g = imp.ig_next;
      const winCls = g.delta_win >= 0 ? 'pos' : 'neg';
      const loseCls = g.delta_lose >= 0 ? 'pos' : 'neg';
      nextBox.innerHTML = `
        <div class="next-card">
          <div class="next-title">🎯 IG 下一场：${g.date.slice(5)} ${g.a} vs ${g.b}</div>
          <div class="next-rows">
            <div class="next-row"><span>若 IG 赢</span><b class="${winCls}">${fmt(g.p_if_ig_win)} <span class="delta">${delta(g.delta_win)}</span></b></div>
            <div class="next-row"><span>若 IG 输</span><b class="${loseCls}">${fmt(g.p_if_ig_lose)} <span class="delta">${delta(g.delta_lose)}</span></b></div>
          </div>
        </div>`;
    } else {
      nextBox.innerHTML = `<div class="next-card muted small">暂无 IG 比赛安排（等赛程公布后自动显示预测）</div>`;
    }

    if (imp.impacts && imp.impacts.length) {
      const igMs = imp.impacts.filter(m => m.a === 'IG' || m.b === 'IG');
      const otherMs = imp.impacts.filter(m => !(m.a === 'IG' || m.b === 'IG'));
      const row = (m) => {
        const cls = m.impact >= 0 ? 'pos' : 'neg';
        return `<div class="impact-row">
          <span class="i-date">${m.date.slice(5)}</span>
          <span class="i-match">${m.a} ${m.score} ${m.b}</span>
          <span class="i-winner">胜 ${m.winner}</span>
          <b class="${cls}">${delta(m.impact)}</b>
        </div>`;
      };
      const block = (title, ms) => `
        <div class="impact-group">
          <div class="impact-title">${title}</div>
          ${ms.map(row).join('')}
        </div>`;
      let html = '';
      if (igMs.length) html += block('IG 近 3 场', igMs);
      if (otherMs.length) html += block('近 3 天其他比赛', otherMs);
      listEl.innerHTML = html;
    }
  }

  loadImpact();

  // ============ 赛程模块 ============
  const TEAM_NAME = {
    AL: 'AL', BLG: 'BLG', EDG: 'EDG', IG: 'IG', JDG: 'JDG', LGD: 'LGD',
    LNG: 'LNG', NIP: 'NIP', OMG: 'OMG', TES: 'TES', TT: 'TT', UP: 'UP',
    WE: 'WE', WBG: 'WBG',
  };
  let scheduleData = null;
  let filterTeam = 'IG';
  let searchText = '';

  async function loadSchedule() {
    try {
      scheduleData = await (await fetch('data/schedule.json')).json();
    } catch (e) {
      document.getElementById('schedule-list').innerHTML =
        '<div class="chart-empty">赛程数据暂不可用（稍后自动更新）</div>';
      return;
    }
    // 队伍中文名（可选增强，失败不影响赛程显示）
    try {
      const s = await (await fetch('data/season-2026.json')).json();
      s.teams.forEach(t => { TEAM_NAME[t.id] = t.name.replace(/\s*\(.*\)/, ''); });
    } catch (e) { /* 使用内置映射即可 */ }
    document.getElementById('team-search').addEventListener('input', (ev) => {
      searchText = ev.target.value.trim().toUpperCase();
      renderSchedule();
    });
    document.querySelectorAll('.tag[data-team]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tag[data-team]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        filterTeam = btn.dataset.team;
        document.getElementById('team-search').value = '';
        searchText = '';
        renderSchedule();
      });
    });
    renderSchedule();
  }

  function teamHits(team, needle) {
    const up = needle.toUpperCase();
    return team.toUpperCase() === up
      || (TEAM_NAME[team] || team).toUpperCase().includes(up)
      || TEAM_NAME[team] === needle;
  }

  function renderSchedule() {
    if (!scheduleData) return;
    const list = document.getElementById('schedule-list');
    const needle = searchText || filterTeam;
    let ms = scheduleData.matches.filter(m =>
      teamHits(m.a, needle) || teamHits(m.b, needle));
    // 排序：最近的未来在最前，已结束按日期倒序（最近的在前）
    const now = new Date().toISOString().slice(0, 16);
    ms = ms.sort((x, y) => (x.date < y.date ? 1 : x.date > y.date ? -1 : 0));
    const future = ms.filter(m => m.status === 'upcoming');
    const past = ms.filter(m => m.status === 'done');
    const ordered = future.concat(past);
    document.getElementById('schedule-count').textContent =
      `${ordered.length} 场（未来 ${future.length} · 已结束 ${past.length}）`;

    if (!ordered.length) {
      list.innerHTML = '<div class="chart-empty">该队伍暂无赛程</div>';
      return;
    }
    list.innerHTML = ordered.map(m => {
      const isFuture = m.status === 'upcoming';
      const d = m.date.replace('T', ' ');
      const scoreA = m.score_a != null ? m.score_a : '';
      const scoreB = m.score_b != null ? m.score_b : '';
      const winA = m.score_a != null && m.score_a > m.score_b;
      const winB = m.score_a != null && m.score_b > m.score_a;
      const igMark = (t) => (t === 'IG' ? '<span class="ig-dot">IG</span>' : t);
      return `<div class="match-card ${isFuture ? 'future' : 'done'}">
        <div class="m-date">${d.slice(5)}</div>
        <div class="m-team ${winA ? 'win' : ''}">${igMark(m.a)}</div>
        <div class="m-score">${isFuture ? 'VS' : `${scoreA} : ${scoreB}`}</div>
        <div class="m-team ${winB ? 'win' : ''}">${igMark(m.b)}</div>
      </div>`;
    }).join('');
  }

  loadSchedule();
})();

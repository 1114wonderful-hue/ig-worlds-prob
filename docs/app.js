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
})();

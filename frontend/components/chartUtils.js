// 图表选型与配置（简单启发式）：日期+数值→折线，类别+数值→柱状，否则只出表格

export function detectChartType(columns, rows) {
  if (!columns || columns.length < 2 || !rows || rows.length === 0) return null;
  const x = columns[0];
  const y = columns[1];
  if (!rows.every((r) => typeof r[y] === 'number')) return null;
  const isDate = rows.every((r) => /^\d{4}-\d{2}-\d{2}/.test(String(r[x])));
  if (isDate && rows.length >= 2) return 'line';
  if (rows.length <= 30) return 'bar';
  return null;
}

export function buildChartOption(columns, rows, type) {
  const x = columns[0];
  const y = columns[1];
  const categories = rows.map((r) => String(r[x]));
  const values = rows.map((r) => r[y]);
  const isDate = type === 'line';
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 24, bottom: 48 },
    xAxis: { type: 'category', data: categories, axisLabel: { rotate: isDate ? 0 : 30 } },
    yAxis: { type: 'value' },
    series: [
      type === 'line'
        ? { type: 'line', data: values, smooth: true, areaStyle: { opacity: 0.15 } }
        : { type: 'bar', data: values },
    ],
  };
}

'use client';

import { useEffect, useState } from 'react';
import Chart from './Chart';
import { buildChartOption } from './chartUtils';

export default function DashboardView() {
  const [items, setItems] = useState(null);

  async function load() {
    const res = await fetch('/api/dashboards');
    setItems(await res.json());
  }

  useEffect(() => { load(); }, []);

  async function remove(id) {
    await fetch(`/api/dashboards/${id}`, { method: 'DELETE' });
    load();
  }

  if (items === null) return <div className="muted">加载中…</div>;
  if (items.length === 0) {
    return <div className="empty">还没有保存的图表。在「查数」里问一个问题，点「保存到仪表盘」即可。</div>;
  }

  return (
    <div className="dash-grid">
      {items.map((it) => (
        <div key={it.id} className="dash-card">
          <div className="dash-head">
            <span className="dash-title">{it.title}</span>
            <button className="dash-del" onClick={() => remove(it.id)}>删除</button>
          </div>
          {it.chart_type && it.chart_type !== 'table' ? (
            <Chart option={buildChartOption(it.columns, it.rows, it.chart_type)} />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>{(it.columns || []).map((c) => <th key={c}>{c}</th>)}</tr>
                </thead>
                <tbody>
                  {(it.rows || []).slice(0, 20).map((row, i) => (
                    <tr key={i}>{(it.columns || []).map((c) => <td key={c}>{String(row[c])}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

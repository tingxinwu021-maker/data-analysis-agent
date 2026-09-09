'use client';

import { useEffect, useRef, useState } from 'react';
import Chart from '../components/Chart';
import DashboardView from '../components/DashboardView';
import { buildChartOption, detectChartType } from '../components/chartUtils';

const uid = () => crypto.randomUUID();

function ResultView({ data, mode, onSave, onFeedback }) {
  if (!data) return null;
  if (data.error) return <div className="error">{data.error}</div>;

  if (mode === 'file') {
    return (
      <div>
        <div className="answer">{data.explanation}</div>
        <details><summary>查看代码</summary><pre className="code">{data.code}</pre></details>
        {data.stdout ? <details open><summary>执行输出</summary><pre className="code">{data.stdout}</pre></details> : null}
        {data.stderr ? <div className="error">{data.stderr}</div> : null}
      </div>
    );
  }

  const chartType = detectChartType(data.columns, data.rows);
  const ready = data.status === 'done';
  return (
    <div>
      <div className="answer">
        {data.explanation || (data.status === 'pending' ? '正在生成 SQL…' : '')}
        {!ready && data.status !== 'error' ? <span className="cursor">▍</span> : null}
      </div>

      {data.sql ? <details><summary>查看 SQL</summary><pre className="code">{data.sql}</pre></details> : null}

      {data.rows && data.rows.length > 0 && chartType ? (
        <Chart option={buildChartOption(data.columns, data.rows, chartType)} />
      ) : null}

      {data.rows && data.rows.length > 0 ? (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>{data.columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {data.rows.slice(0, 50).map((row, i) => (
                <tr key={i}>{data.columns.map((c) => <td key={c}>{String(row[c])}</td>)}</tr>
              ))}
            </tbody>
          </table>
          {data.row_count > 50 ? <div className="muted">共 {data.row_count} 行，仅显示前 50 行</div> : null}
        </div>
      ) : null}

      {ready && data.rows && data.rows.length > 0 ? (
        <div className="actions">
          <button className="save-btn" onClick={onSave}>保存到仪表盘</button>
          <button className="fb-btn" onClick={() => onFeedback('up')} title="回答正确">👍</button>
          <button className="fb-btn" onClick={() => onFeedback('down')} title="回答有误">👎</button>
        </div>
      ) : null}
    </div>
  );
}

export default function Home() {
  const [tab, setTab] = useState('chat');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const sessionRef = useRef(uid());
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  function applyEvent(id, event) {
    setMessages((msgs) => msgs.map((m) => {
      if (m.id !== id) return m;
      const d = { ...m.data };
      if (event.type === 'sql') { d.sql = event.sql; d.status = 'executing'; }
      else if (event.type === 'result') {
        d.columns = event.columns; d.rows = event.rows;
        d.row_count = event.row_count; d.truncated = event.truncated;
      } else if (event.type === 'delta') {
        d.explanation += event.text;
      } else if (event.type === 'done') {
        d.status = 'done';
        if (event.explanation) d.explanation = event.explanation;
      } else if (event.type === 'error') {
        d.error = event.error; d.status = 'error';
      }
      return { ...m, data: d };
    }));
  }

  async function sendChat() {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    const asstId = uid();
    setMessages((m) => [
      ...m,
      { id: uid(), role: 'user', text: q },
      {
        id: asstId, role: 'assistant', mode: 'chat',
        data: { question: q, sql: '', columns: [], rows: [], row_count: 0, explanation: '', status: 'pending', error: null },
      },
    ]);
    setLoading(true);
    try {
      const res = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, session_id: sessionRef.current }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) >= 0) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const line = chunk.trim();
          if (!line.startsWith('data:')) continue;
          try { applyEvent(asstId, JSON.parse(line.slice(5).trim())); } catch { /* 忽略解析异常 */ }
        }
      }
    } catch (e) {
      applyEvent(asstId, { type: 'error', error: String(e) });
    } finally {
      setLoading(false);
    }
  }

  async function sendFile() {
    const q = input.trim();
    if (!q || loading) return;
    setInput('');
    setMessages((m) => [...m, { id: uid(), role: 'user', text: `[文件 ${file?.name || ''}] ${q}` }]);
    setLoading(true);
    let data;
    try {
      if (!file) {
        data = { error: '请先选择一个文件（CSV / Excel）' };
      } else {
        const fd = new FormData();
        fd.append('file', file);
        const up = await (await fetch('/api/upload', { method: 'POST', body: fd })).json();
        if (!up.file_id) {
          data = { error: up.detail || '上传失败' };
        } else {
          data = await (await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_id: up.file_id, question: q }),
          })).json();
        }
      }
    } catch (e) {
      data = { error: String(e) };
    }
    setMessages((m) => [...m, { id: uid(), role: 'assistant', mode: 'file', data }]);
    setLoading(false);
  }

  function send() {
    if (tab === 'chat') sendChat();
    else sendFile();
  }

  function newConversation() {
    const old = sessionRef.current;
    setMessages([]);
    sessionRef.current = uid();
    // 通知后端清理旧会话，避免内存泄漏（fire-and-forget，失败不影响 UI）
    fetch(`/api/chat/session/${old}`, { method: 'DELETE' }).catch(() => {});
  }

  async function saveToDashboard(data) {
    const title = window.prompt('图表标题', data.question || '未命名');
    if (title === null) return;
    const chartType = detectChartType(data.columns, data.rows) || 'table';
    await fetch('/api/dashboards', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title,
        question: data.question || '',
        sql: data.sql || '',
        columns: data.columns,
        rows: data.rows,
        chart_type: chartType,
        mode: 'chat',
      }),
    });
    alert('已保存到仪表盘');
  }

  async function sendFeedback(data, rating) {
    await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: data.question || '', sql: data.sql || '', rating }),
    });
  }

  return (
    <main className="container">
      <header className="header">
        <h1>数据分析 Agent</h1>
        <div className="tabs">
          <button className={tab === 'chat' ? 'active' : ''} onClick={() => setTab('chat')}>查数（数据库）</button>
          <button className={tab === 'file' ? 'active' : ''} onClick={() => setTab('file')}>分析文件</button>
          <button className={tab === 'dashboard' ? 'active' : ''} onClick={() => setTab('dashboard')}>仪表盘</button>
        </div>
      </header>

      {tab === 'dashboard' ? (
        <div className="messages"><DashboardView /></div>
      ) : (
        <>
          <div className="messages">
            {messages.length === 0 ? (
              <div className="empty">问我数据问题，例如「每个国家的活跃用户数是多少？」</div>
            ) : (
              messages.map((m) =>
                m.role === 'user' ? (
                  <div key={m.id} className="msg user">{m.text}</div>
                ) : (
                  <div key={m.id} className="msg assistant">
                    <ResultView data={m.data} mode={m.mode} onSave={() => saveToDashboard(m.data)} onFeedback={(r) => sendFeedback(m.data, r)} />
                  </div>
                )
              )
            )}
            {loading ? <div className="msg assistant muted">思考中…</div> : null}
            <div ref={endRef} />
          </div>

          <footer className="composer">
            {tab === 'chat' ? (
              <button className="new-btn" onClick={newConversation} title="清空当前对话">新对话</button>
            ) : (
              <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setFile(e.target.files[0])} className="file-input" />
            )}
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
              placeholder={tab === 'chat' ? '输入数据问题…' : '选择文件后，输入分析问题…'}
              disabled={loading}
            />
            <button onClick={send} disabled={loading || !input.trim()}>发送</button>
          </footer>
        </>
      )}
    </main>
  );
}

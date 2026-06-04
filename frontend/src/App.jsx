import { useCallback, useEffect, useState } from 'react'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:5000'

function App() {
  const [status, setStatus] = useState('checking')
  const [health, setHealth] = useState(null)
  const [error, setError] = useState('')

  const checkBackend = useCallback(async () => {
    setStatus('checking')
    setError('')

    try {
      const response = await fetch(`${API_BASE_URL}/api/health`)

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const data = await response.json()
      setHealth(data)
      setStatus('online')
    } catch (err) {
      setHealth(null)
      setStatus('offline')
      setError(err instanceof Error ? err.message : 'Unknown connection error')
    }
  }, [])

  useEffect(() => {
    checkBackend()
  }, [checkBackend])

  const statusLabel = {
    checking: '檢查中',
    online: '已連線',
    offline: '未連線',
  }[status]

  return (
    <main className="app-shell">
      <section className="status-panel" aria-labelledby="app-title">
        <div className="title-block">
          <p className="eyebrow">OpenAI Codex LLM DB</p>
          <h1 id="app-title">DB Agent Chat</h1>
        </div>

        <div className="status-row">
          <span>後端連線狀態</span>
          <strong className={`status-badge status-${status}`}>{statusLabel}</strong>
        </div>

        <dl className="health-details">
          <div>
            <dt>API</dt>
            <dd>{API_BASE_URL}/api/health</dd>
          </div>
          <div>
            <dt>Service</dt>
            <dd>{health?.service ?? '-'}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{health?.status ?? '-'}</dd>
          </div>
        </dl>

        {error ? <p className="error-message">連線錯誤：{error}</p> : null}

        <button type="button" onClick={checkBackend} disabled={status === 'checking'}>
          {status === 'checking' ? '檢查中...' : '重新檢查後端狀態'}
        </button>
      </section>
    </main>
  )
}

export default App

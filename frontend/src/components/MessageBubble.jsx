import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const routeOptions = [
  { value: 'general_chat', label: 'general_chat' },
  { value: 'db_query', label: 'db_query' },
  { value: 'db_write', label: 'db_write' },
  { value: 'rag', label: 'rag' },
  { value: 'image_skill', label: 'image_skill' },
]

function RouterDecisionCard({ message, onConfirmRoute, onSelectRoute }) {
  const metadata = message.metadata ?? {}
  const router = metadata.router
  const status = metadata.status ?? message.status
  const aiRoute = router?.route
  const selectedRoute = metadata.selectedRoute ?? aiRoute ?? 'general_chat'
  const isPending = status === 'router_pending'

  if (status === 'loading' || message.status === 'router_loading') {
    return (
      <div className="router-card">
        <div className="router-card-header">
          <span>Context Router</span>
          <strong>判斷中</strong>
        </div>
        <span className="typing-indicator" aria-label="Router 判斷中">
          <span />
          <span />
          <span />
        </span>
      </div>
    )
  }

  return (
    <div className="router-card">
      <div className="router-card-header">
        <span>Context Router</span>
        <strong>{isPending ? '等待確認' : '已確認'}</strong>
      </div>

      <div className="router-detail-grid">
        <div>
          <span>AI route</span>
          <strong>{aiRoute ?? '-'}</strong>
        </div>
        <div>
          <span>Confidence</span>
          <strong>{typeof router?.confidence === 'number' ? router.confidence.toFixed(2) : '-'}</strong>
        </div>
        <div>
          <span>Capability</span>
          <strong>{router?.required_capability ?? '-'}</strong>
        </div>
      </div>

      {router?.reason ? <p className="router-reason">{router.reason}</p> : null}
      {router?.suggested_followup_question ? (
        <p className="router-followup">{router.suggested_followup_question}</p>
      ) : null}

      <div className="route-button-grid" aria-label="選擇 route">
        {routeOptions.map((option) => (
          <button
            className={[
              'route-button',
              option.value === aiRoute ? 'is-ai-pick' : '',
              option.value === selectedRoute ? 'is-selected' : '',
            ]
              .filter(Boolean)
              .join(' ')}
            disabled={!isPending}
            key={option.value}
            type="button"
            onClick={() => onSelectRoute?.(message.id, option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      {isPending ? (
        <button
          className="confirm-route-button"
          type="button"
          onClick={() => onConfirmRoute?.(message.id)}
        >
          確認執行
        </button>
      ) : (
        <p className="router-confirmed-note">已使用 {selectedRoute} 執行。</p>
      )}
    </div>
  )
}

function SqlResultTable({ columns, rows }) {
  if (!columns?.length) {
    return <p className="sql-empty-note">沒有欄位資料。</p>
  }

  if (!rows?.length) {
    return <p className="sql-empty-note">查詢結果為空。</p>
  }

  return (
    <div className="sql-table-wrap">
      <table className="sql-result-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={`${rowIndex}-${JSON.stringify(row)}`}>
              {columns.map((column) => (
                <td key={column}>{row[column] ?? ''}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SqlAgentPanel({ sqlAgent }) {
  return (
    <div className="sql-agent-panel">
      <div className="sql-agent-header">
        <span>本次使用 route</span>
        <strong>{sqlAgent.route ?? 'DB Query'}</strong>
      </div>

      <details className="sql-agent-details">
        <summary>產生的 SQL</summary>
        <pre>
          <code>{sqlAgent.sql}</code>
        </pre>
        {sqlAgent.generator_reason ? <p>{sqlAgent.generator_reason}</p> : null}
        {sqlAgent.validator_warnings?.length ? (
          <ul>
            {sqlAgent.validator_warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        ) : null}
      </details>

      <details className="sql-agent-details">
        <summary>查詢結果表格（{sqlAgent.row_count ?? sqlAgent.rows?.length ?? 0} 筆）</summary>
        <SqlResultTable columns={sqlAgent.columns} rows={sqlAgent.rows} />
      </details>
    </div>
  )
}

function AssistantContent({ message }) {
  const sqlAgent = message.metadata?.sql_agent

  return (
    <>
      {sqlAgent ? <SqlAgentPanel sqlAgent={sqlAgent} /> : null}
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
    </>
  )
}

function MessageBubble({ message, onConfirmRoute, onSelectRoute }) {
  const isUser = message.role === 'user'
  const isLoading = message.status === 'loading'
  const isRouterDecision = message.metadata?.type === 'router_decision'
  const label =
    {
      user: '你',
      assistant: isRouterDecision ? 'Router' : 'Assistant',
      system: 'System',
    }[message.role] ?? message.role

  return (
    <article className={`message-row ${isUser ? 'from-user' : 'from-system'}`}>
      <div className="message-meta">{label}</div>
      <div
        className={[
          'message-bubble',
          isRouterDecision ? 'router-bubble' : 'markdown-content',
          isLoading ? 'is-loading' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {isRouterDecision ? (
          <RouterDecisionCard
            message={message}
            onConfirmRoute={onConfirmRoute}
            onSelectRoute={onSelectRoute}
          />
        ) : isLoading ? (
          <span className="typing-indicator" aria-label="等待 LLM 回覆">
            <span />
            <span />
            <span />
          </span>
        ) : (
          <AssistantContent message={message} />
        )}
      </div>
    </article>
  )
}

export default MessageBubble

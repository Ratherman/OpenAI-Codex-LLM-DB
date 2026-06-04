import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const routeOptions = [
  { value: 'general_chat', label: 'general_chat' },
  { value: 'db_query', label: 'db_query' },
  { value: 'db_write', label: 'db_write' },
  { value: 'rag', label: 'rag' },
  { value: 'image_skill', label: 'image_skill' },
]

const toolLabels = {
  create_expense_report: '新增費用',
  create_invoice: '新增發票',
}

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

function KeyValueGrid({ data }) {
  const entries = Object.entries(data ?? {}).filter(([, value]) => value !== null && value !== undefined && value !== '')

  if (!entries.length) {
    return <p className="sql-empty-note">沒有可顯示的欄位。</p>
  }

  return (
    <div className="write-field-grid">
      {entries.map(([key, value]) => (
        <div key={key}>
          <span>{key}</span>
          <strong>{String(value)}</strong>
        </div>
      ))}
    </div>
  )
}

function DbWritePanel({ dbWrite, message, onCancelDbWrite, onConfirmDbWrite }) {
  const status = dbWrite.status
  const isPending = status === 'pending_confirmation'

  return (
    <div className="db-write-panel">
      <div className="db-write-header">
        <span>受控 DB Write</span>
        <strong>{toolLabels[dbWrite.tool] ?? dbWrite.tool}</strong>
      </div>

      <p className="db-write-status">
        {status === 'missing_fields'
          ? '必要欄位不足'
          : status === 'confirmed'
            ? `已寫入 ID ${dbWrite.record_id ?? '-'}`
            : status === 'canceled'
              ? '已取消'
              : '待確認寫入'}
      </p>

      {dbWrite.missing_fields?.length ? (
        <div className="db-write-warning">
          缺少欄位：{dbWrite.missing_fields.join('、')}
        </div>
      ) : null}

      {dbWrite.warnings?.length ? (
        <ul className="db-write-warning-list">
          {dbWrite.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}

      <KeyValueGrid data={dbWrite.fields} />

      {dbWrite.resolved ? (
        <details className="db-write-details">
          <summary>解析到的資料庫關聯</summary>
          <KeyValueGrid data={dbWrite.resolved} />
        </details>
      ) : null}

      {isPending ? (
        <div className="db-write-actions">
          <button className="confirm-write-button" type="button" onClick={() => onConfirmDbWrite?.(message.id)}>
            確認寫入
          </button>
          <button className="cancel-write-button" type="button" onClick={() => onCancelDbWrite?.(message.id)}>
            取消
          </button>
        </div>
      ) : null}
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

function RagRouteBadge({ rag }) {
  return (
    <div className="rag-panel">
      <div className="rag-header">
        <span>本次使用 route</span>
        <strong>{rag.route ?? 'RAG'}</strong>
      </div>
    </div>
  )
}

function RagReferences({ rag }) {
  return (
    <details className="rag-details">
      <summary>REF（{rag.refs?.length ?? 0} 筆）</summary>
      <div className="rag-ref-list">
        {(rag.refs ?? []).map((ref) => (
          <div className="rag-ref-item" key={ref.index}>
            <strong>[{ref.index}] {ref.title}</strong>
            <span>{ref.source}</span>
            <small>similarity {Number(ref.similarity ?? 0).toFixed(4)}</small>
          </div>
        ))}
      </div>
    </details>
  )
}

function AssistantContent({ message, onCancelDbWrite, onConfirmDbWrite }) {
  const sqlAgent = message.metadata?.sql_agent
  const dbWrite = message.metadata?.db_write
  const rag = message.metadata?.rag

  return (
    <>
      {sqlAgent ? <SqlAgentPanel sqlAgent={sqlAgent} /> : null}
      {dbWrite ? (
        <DbWritePanel
          dbWrite={dbWrite}
          message={message}
          onCancelDbWrite={onCancelDbWrite}
          onConfirmDbWrite={onConfirmDbWrite}
        />
      ) : null}
      {rag ? <RagRouteBadge rag={rag} /> : null}
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      {rag ? <RagReferences rag={rag} /> : null}
    </>
  )
}

function MessageBubble({
  message,
  onCancelDbWrite,
  onConfirmDbWrite,
  onConfirmRoute,
  onSelectRoute,
}) {
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
          <AssistantContent
            message={message}
            onCancelDbWrite={onCancelDbWrite}
            onConfirmDbWrite={onConfirmDbWrite}
          />
        )}
      </div>
    </article>
  )
}

export default MessageBubble

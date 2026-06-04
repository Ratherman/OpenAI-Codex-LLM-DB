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
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        )}
      </div>
    </article>
  )
}

export default MessageBubble

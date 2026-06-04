import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const isLoading = message.status === 'loading'
  const label = {
    user: '使用者',
    assistant: 'Assistant',
    system: '系統',
  }[message.role] ?? message.role

  return (
    <article className={`message-row ${isUser ? 'from-user' : 'from-system'}`}>
      <div className="message-meta">{label}</div>
      <div className={`message-bubble markdown-content ${isLoading ? 'is-loading' : ''}`}>
        {isLoading ? (
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

function MessageBubble({ message }) {
  const isUser = message.role === 'user'

  return (
    <article className={`message-row ${isUser ? 'from-user' : 'from-system'}`}>
      <div className="message-meta">{isUser ? '使用者' : '系統'}</div>
      <div className="message-bubble">{message.content}</div>
    </article>
  )
}

export default MessageBubble

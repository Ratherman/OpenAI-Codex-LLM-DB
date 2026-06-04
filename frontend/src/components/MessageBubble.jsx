function MessageBubble({ message }) {
  const isUser = message.role === 'user'
  const label = {
    user: '使用者',
    assistant: 'Assistant',
    system: '系統',
  }[message.role] ?? message.role

  return (
    <article className={`message-row ${isUser ? 'from-user' : 'from-system'}`}>
      <div className="message-meta">{label}</div>
      <div className="message-bubble">{message.content}</div>
    </article>
  )
}

export default MessageBubble

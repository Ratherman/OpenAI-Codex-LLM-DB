import { Database, ImagePlus, Menu, RefreshCw, Send, SlidersHorizontal } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import MessageBubble from './MessageBubble.jsx'

function ChatArea({
  chat,
  dbHealth,
  isSending,
  onOpenControls,
  onOpenSidebar,
  onRefreshDbHealth,
  onSendMessage,
  selectedModel,
}) {
  const [draft, setDraft] = useState('')
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat?.messages])

  const submitMessage = (event) => {
    event.preventDefault()
    if (!draft.trim() || isSending) return

    onSendMessage(draft)
    setDraft('')
  }

  const dbLabel = {
    checking: 'DB 檢查中',
    online: 'DB 已連線',
    offline: 'DB 未連線',
  }[dbHealth.status]

  return (
    <main className="chat-area">
      <header className="mobile-topbar">
        <button
          aria-label="開啟聊天室列表"
          className="icon-button"
          title="開啟聊天室列表"
          type="button"
          onClick={onOpenSidebar}
        >
          <Menu size={20} />
        </button>
        <strong>DB Agent Chat</strong>
        <button
          aria-label="開啟設定"
          className="icon-button"
          title="開啟設定"
          type="button"
          onClick={onOpenControls}
        >
          <SlidersHorizontal size={20} />
        </button>
      </header>

      <section className="chat-header">
        <div>
          <p className="panel-kicker">DB Agent Chat</p>
          <h1>{chat?.title ?? '聊天室'}</h1>
        </div>
        <div className="chat-status-group">
          <span className="model-pill">{selectedModel}</span>
          <span
            className={`db-status-pill db-${dbHealth.status}`}
            title={dbHealth.version || dbHealth.error || '資料庫連線狀態'}
          >
            <Database size={16} />
            {dbLabel}
          </span>
          <button
            aria-label="重新檢查資料庫連線"
            className="icon-button"
            title="重新檢查資料庫連線"
            type="button"
            onClick={onRefreshDbHealth}
          >
            <RefreshCw size={17} />
          </button>
        </div>
      </section>

      <section aria-label="聊天訊息" className="message-list">
        {chat?.messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}
        <div ref={messagesEndRef} />
      </section>

      <form className="composer" onSubmit={submitMessage}>
        <div className="composer-toolbar">
          <button
            aria-label="圖片功能尚未啟用"
            className="image-upload-button"
            disabled
            title="圖片功能尚未啟用"
            type="button"
          >
            <ImagePlus size={18} />
            圖片功能尚未啟用
          </button>
        </div>
        <div className="composer-row">
          <textarea
            aria-label="輸入訊息"
            placeholder="輸入訊息..."
            rows={2}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                submitMessage(event)
              }
            }}
          />
          <button
            aria-label="送出訊息"
            className="send-button"
            disabled={isSending}
            title="送出訊息"
            type="submit"
          >
            {isSending ? <RefreshCw className="spin" size={20} /> : <Send size={20} />}
          </button>
        </div>
      </form>
    </main>
  )
}

export default ChatArea

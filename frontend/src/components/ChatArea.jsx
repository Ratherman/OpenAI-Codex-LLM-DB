import { Database, ImagePlus, Menu, RefreshCw, Send, SlidersHorizontal, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import MessageBubble from './MessageBubble.jsx'

const MAX_IMAGE_SIZE = 10 * 1024 * 1024

function ChatArea({
  chat,
  dbHealth,
  enableImageSkill,
  error,
  hasPendingRouter,
  isLoadingMessages,
  isSending,
  memoryRounds,
  onCancelDbWrite,
  onConfirmDbWrite,
  onConfirmRoute,
  onOpenControls,
  onOpenSidebar,
  onRefreshDbHealth,
  onSelectRoute,
  onSendMessage,
  onUploadImage,
  selectedModel,
}) {
  const [draft, setDraft] = useState('')
  const [attachments, setAttachments] = useState([])
  const [uploadError, setUploadError] = useState('')
  const [isUploadingImage, setIsUploadingImage] = useState(false)
  const messagesEndRef = useRef(null)
  const imageInputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [chat?.messages])

  useEffect(() => {
    setAttachments([])
    setUploadError('')
  }, [chat?.id])

  const submitMessage = (event) => {
    event.preventDefault()
    if ((!draft.trim() && attachments.length === 0) || isSending || hasPendingRouter || !chat) return

    onSendMessage(draft, attachments)
    setDraft('')
    setAttachments([])
    setUploadError('')
  }

  const handlePickImage = () => {
    imageInputRef.current?.click()
  }

  const handleImageChange = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    if (file.size > MAX_IMAGE_SIZE) {
      setUploadError('圖片太大，請上傳 10MB 以內的檔案。')
      return
    }

    setUploadError('')
    setIsUploadingImage(true)
    try {
      const uploadedImage = await onUploadImage(file)
      setAttachments([uploadedImage])
    } catch (uploadException) {
      setUploadError(uploadException instanceof Error ? uploadException.message : '圖片上傳失敗')
    } finally {
      setIsUploadingImage(false)
    }
  }

  const dbLabel = {
    checking: 'DB 檢查中',
    online: 'DB 已連線',
    offline: 'DB 離線',
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
          <span className="memory-pill">目前記憶：{memoryRounds} 輪</span>
          <span
            className={`db-status-pill db-${dbHealth.status}`}
            title={dbHealth.version || dbHealth.error || '資料庫狀態'}
          >
            <Database size={16} />
            {dbLabel}
          </span>
          <button
            aria-label="重新檢查資料庫"
            className="icon-button"
            title="重新檢查資料庫"
            type="button"
            onClick={onRefreshDbHealth}
          >
            <RefreshCw size={17} />
          </button>
        </div>
      </section>

      <section aria-label="聊天訊息" className="message-list">
        {isLoadingMessages ? <p className="status-note">載入訊息中...</p> : null}
        {error ? <p className="error-banner">{error}</p> : null}
        {!chat && !isLoadingMessages ? <p className="empty-state">請先新增或選擇聊天室。</p> : null}
        {chat && !isLoadingMessages && chat.messages.length === 0 ? (
          <p className="empty-state">輸入第一則訊息，開始 DB Agent Chat demo。</p>
        ) : null}
        {chat?.messages.map((message) => (
          <MessageBubble
            key={message.id}
            message={message}
            onCancelDbWrite={onCancelDbWrite}
            onConfirmDbWrite={onConfirmDbWrite}
            onConfirmRoute={onConfirmRoute}
            onSelectRoute={onSelectRoute}
          />
        ))}
        <div ref={messagesEndRef} />
      </section>

      <form className="composer" onSubmit={submitMessage}>
        <div className="composer-toolbar">
          <input
            accept="image/jpeg,image/png,image/webp"
            className="visually-hidden"
            ref={imageInputRef}
            type="file"
            onChange={handleImageChange}
          />
          <button
            aria-label="上傳發票或收據圖片"
            className="image-upload-button"
            disabled={!chat || isSending || hasPendingRouter || isUploadingImage || !enableImageSkill}
            title={enableImageSkill ? '上傳發票或收據圖片' : '請先在右側開啟 Enable Image Skill'}
            type="button"
            onClick={handlePickImage}
          >
            {isUploadingImage ? <RefreshCw className="spin" size={18} /> : <ImagePlus size={18} />}
            {isUploadingImage ? '圖片上傳中...' : '上傳圖片'}
          </button>
          {!enableImageSkill ? <span className="composer-hint">圖片辨識需先開啟 Enable Image Skill</span> : null}
        </div>

        {uploadError ? <p className="composer-error">{uploadError}</p> : null}

        {attachments.length ? (
          <div className="composer-attachments">
            {attachments.map((image) => (
              <div className="composer-image-chip" key={image.filename}>
                <img alt={image.original_filename || 'uploaded image'} src={image.url} />
                <span>{image.original_filename || image.filename}</span>
                <button
                  aria-label="移除圖片"
                  type="button"
                  onClick={() =>
                    setAttachments((current) => current.filter((item) => item.filename !== image.filename))
                  }
                >
                  <X size={15} />
                </button>
              </div>
            ))}
          </div>
        ) : null}

        <div className="composer-row">
          <textarea
            aria-label="輸入訊息"
            placeholder={hasPendingRouter ? '請先確認 Router 判斷' : '輸入訊息，也可以搭配圖片送出...'}
            rows={2}
            value={draft}
            disabled={!chat || isSending || hasPendingRouter}
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
            disabled={!chat || isSending || hasPendingRouter || (!draft.trim() && attachments.length === 0)}
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

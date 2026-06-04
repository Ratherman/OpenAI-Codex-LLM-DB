import { Check, ChevronLeft, ChevronRight, Edit3, Moon, Plus, Sun, Trash2, X } from 'lucide-react'
import { useState } from 'react'

function Sidebar({
  activeChatId,
  chats,
  collapsed,
  error,
  isLoading,
  mobileOpen,
  theme,
  onCloseMobile,
  onCreateChat,
  onDeleteChat,
  onRenameChat,
  onSelectChat,
  onToggleCollapse,
  onToggleTheme,
}) {
  const [editingId, setEditingId] = useState(null)
  const [draftTitle, setDraftTitle] = useState('')
  const showRail = collapsed && !mobileOpen

  const startEditing = (chat) => {
    setEditingId(chat.id)
    setDraftTitle(chat.title)
  }

  const submitRename = (chatId) => {
    onRenameChat(chatId, draftTitle)
    setEditingId(null)
    setDraftTitle('')
  }

  if (showRail) {
    return (
      <aside className={`sidebar is-collapsed ${mobileOpen ? 'is-mobile-open' : ''}`}>
        <button
          aria-label="展開聊天室列表"
          className="icon-button rail-button"
          title="展開聊天室列表"
          type="button"
          onClick={onToggleCollapse}
        >
          <ChevronRight size={20} />
        </button>
      </aside>
    )
  }

  return (
    <aside className={`sidebar ${mobileOpen ? 'is-mobile-open' : ''}`}>
      <div className="panel-header">
        <div>
          <p className="panel-kicker">Chats</p>
          <h2>聊天室</h2>
        </div>
        <div className="header-actions">
          <button
            aria-label="收合聊天室列表"
            className="icon-button desktop-only"
            title="收合聊天室列表"
            type="button"
            onClick={onToggleCollapse}
          >
            <ChevronLeft size={19} />
          </button>
          <button
            aria-label="關閉聊天室列表"
            className="icon-button mobile-only"
            title="關閉聊天室列表"
            type="button"
            onClick={onCloseMobile}
          >
            <X size={19} />
          </button>
        </div>
      </div>

      <button className="new-chat-button" disabled={isLoading} type="button" onClick={onCreateChat}>
        <Plus size={18} />
        新增聊天室
      </button>

      {isLoading ? <p className="sidebar-status">載入聊天室...</p> : null}
      {error ? <p className="sidebar-error">{error}</p> : null}

      <nav aria-label="聊天室列表" className="chat-list">
        {chats.map((chat) => {
          const active = chat.id === activeChatId
          const editing = chat.id === editingId

          return (
            <div className={`chat-list-item ${active ? 'is-active' : ''}`} key={chat.id}>
              {editing ? (
                <form
                  className="rename-form"
                  onSubmit={(event) => {
                    event.preventDefault()
                    submitRename(chat.id)
                  }}
                >
                  <input
                    aria-label="聊天室名稱"
                    value={draftTitle}
                    onChange={(event) => setDraftTitle(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === 'Escape') {
                        setEditingId(null)
                        setDraftTitle('')
                      }
                    }}
                  />
                  <button
                    aria-label="儲存聊天室名稱"
                    className="icon-button"
                    title="儲存聊天室名稱"
                    type="submit"
                  >
                    <Check size={16} />
                  </button>
                </form>
              ) : (
                <>
                  <button
                    className="chat-title-button"
                    type="button"
                    onClick={() => onSelectChat(chat.id)}
                  >
                    <span>{chat.title}</span>
                    <small>{chat.message_count ?? chat.messages?.length ?? 0} 則訊息</small>
                  </button>
                  <div className="chat-actions">
                    <button
                      aria-label={`重新命名 ${chat.title}`}
                      className="icon-button"
                      title="重新命名"
                      type="button"
                      onClick={() => startEditing(chat)}
                    >
                      <Edit3 size={16} />
                    </button>
                    <button
                      aria-label={`刪除 ${chat.title}`}
                      className="icon-button danger"
                      title="刪除"
                      type="button"
                      onClick={() => onDeleteChat(chat.id)}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </>
              )}
            </div>
          )
        })}
        {!isLoading && chats.length === 0 ? (
          <p className="sidebar-status">尚無聊天室，請新增一個開始對話。</p>
        ) : null}
      </nav>

      <div className="sidebar-footer">
        <button className="theme-toggle" type="button" onClick={onToggleTheme}>
          {theme === 'light' ? <Sun size={18} /> : <Moon size={18} />}
          {theme === 'light' ? 'Light Mode' : 'Dark Mode'}
        </button>
      </div>
    </aside>
  )
}

export default Sidebar

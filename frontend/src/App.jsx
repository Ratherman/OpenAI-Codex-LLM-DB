import { useMemo, useState } from 'react'
import ChatArea from './components/ChatArea.jsx'
import ControlPanel from './components/ControlPanel.jsx'
import Sidebar from './components/Sidebar.jsx'
import './App.css'

const makeId = () =>
  globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`

const createMessage = (role, content) => ({
  id: makeId(),
  role,
  content,
  createdAt: new Date().toISOString(),
})

const createChat = (index) => ({
  id: makeId(),
  title: `聊天室 ${index}`,
  messages: [
    createMessage(
      'system',
      '你好，這裡是 DB Agent Chat。目前是 UI 階段，下一階段會開始串接後端與 LLM。',
    ),
  ],
})

const defaultSettings = {
  model: 'gpt-4o',
  temperature: 0.3,
  systemPrompt: '你是一個可以協助查詢資料庫與整理資訊的 AI Agent。',
  memoryRounds: 5,
  enableContextRouter: true,
  enableDbQuery: true,
  enableRag: false,
  enableImageSkill: false,
  enableAuditLog: true,
}

function App() {
  const [chats, setChats] = useState(() => [createChat(1)])
  const [activeChatId, setActiveChatId] = useState(() => chats[0]?.id)
  const [theme, setTheme] = useState('light')
  const [settings, setSettings] = useState(defaultSettings)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [controlsCollapsed, setControlsCollapsed] = useState(false)
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false)
  const [mobileControlsOpen, setMobileControlsOpen] = useState(false)

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) ?? chats[0],
    [activeChatId, chats],
  )

  const handleCreateChat = () => {
    const chat = createChat(chats.length + 1)
    setChats((current) => [chat, ...current])
    setActiveChatId(chat.id)
    setMobileSidebarOpen(false)
  }

  const handleRenameChat = (chatId, title) => {
    const nextTitle = title.trim()
    if (!nextTitle) return

    setChats((current) =>
      current.map((chat) => (chat.id === chatId ? { ...chat, title: nextTitle } : chat)),
    )
  }

  const handleDeleteChat = (chatId) => {
    const remainingChats = chats.filter((chat) => chat.id !== chatId)
    const nextChats = remainingChats.length > 0 ? remainingChats : [createChat(1)]

    setChats(nextChats)
    if (activeChatId === chatId) {
      setActiveChatId(nextChats[0].id)
    }
  }

  const handleSelectChat = (chatId) => {
    setActiveChatId(chatId)
    setMobileSidebarOpen(false)
  }

  const handleSendMessage = (content) => {
    const text = content.trim()
    if (!text || !activeChat) return

    const userMessage = createMessage('user', text)
    const systemMessage = createMessage(
      'system',
      `我收到你的訊息了：${text}。下一階段會串接後端與 LLM。`,
    )

    setChats((current) =>
      current.map((chat) =>
        chat.id === activeChat.id
          ? { ...chat, messages: [...chat.messages, userMessage, systemMessage] }
          : chat,
      ),
    )
  }

  const handleSettingChange = (key, value) => {
    setSettings((current) => ({ ...current, [key]: value }))
  }

  return (
    <div
      className={[
        'app-root',
        `theme-${theme}`,
        sidebarCollapsed ? 'sidebar-collapsed' : '',
        controlsCollapsed ? 'controls-collapsed' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      {(mobileSidebarOpen || mobileControlsOpen) && (
        <button
          aria-label="關閉抽屜"
          className="mobile-backdrop"
          type="button"
          onClick={() => {
            setMobileSidebarOpen(false)
            setMobileControlsOpen(false)
          }}
        />
      )}

      <Sidebar
        activeChatId={activeChat?.id}
        chats={chats}
        collapsed={sidebarCollapsed}
        mobileOpen={mobileSidebarOpen}
        theme={theme}
        onCloseMobile={() => setMobileSidebarOpen(false)}
        onCreateChat={handleCreateChat}
        onDeleteChat={handleDeleteChat}
        onRenameChat={handleRenameChat}
        onSelectChat={handleSelectChat}
        onToggleCollapse={() => setSidebarCollapsed((current) => !current)}
        onToggleTheme={() => setTheme((current) => (current === 'light' ? 'dark' : 'light'))}
      />

      <ChatArea
        chat={activeChat}
        onOpenControls={() => setMobileControlsOpen(true)}
        onOpenSidebar={() => setMobileSidebarOpen(true)}
        onSendMessage={handleSendMessage}
      />

      <ControlPanel
        collapsed={controlsCollapsed}
        mobileOpen={mobileControlsOpen}
        settings={settings}
        onChange={handleSettingChange}
        onCloseMobile={() => setMobileControlsOpen(false)}
        onToggleCollapse={() => setControlsCollapsed((current) => !current)}
      />
    </div>
  )
}

export default App

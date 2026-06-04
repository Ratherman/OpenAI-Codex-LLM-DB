import { useCallback, useEffect, useMemo, useState } from 'react'
import ChatArea from './components/ChatArea.jsx'
import ControlPanel from './components/ControlPanel.jsx'
import Sidebar from './components/Sidebar.jsx'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:5000'

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
      '你好，這裡是 DB Agent Chat。目前前端會把模型設定送到後端，沒有 OpenAI API Key 時會使用後端 mock 回覆。',
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
  const [isSending, setIsSending] = useState(false)
  const [dbHealth, setDbHealth] = useState({
    status: 'checking',
    version: '',
    error: '',
  })
  const [dbSummary, setDbSummary] = useState({
    status: 'checking',
    data: null,
    error: '',
  })

  const activeChat = useMemo(
    () => chats.find((chat) => chat.id === activeChatId) ?? chats[0],
    [activeChatId, chats],
  )

  const checkDbHealth = useCallback(async () => {
    setDbHealth({ status: 'checking', version: '', error: '' })

    try {
      const response = await fetch(`${API_BASE_URL}/api/db/health`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`)
      }

      setDbHealth({
        status: 'online',
        version: data.database?.version ?? '',
        error: '',
      })
    } catch (error) {
      setDbHealth({
        status: 'offline',
        version: '',
        error: error instanceof Error ? error.message : 'Unknown database error',
      })
    }
  }, [])

  const checkDbSummary = useCallback(async () => {
    setDbSummary({ status: 'checking', data: null, error: '' })

    try {
      const response = await fetch(`${API_BASE_URL}/api/db/summary`)
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`)
      }

      setDbSummary({
        status: 'online',
        data: data.summary,
        error: '',
      })
    } catch (error) {
      setDbSummary({
        status: 'offline',
        data: null,
        error: error instanceof Error ? error.message : 'Unknown database summary error',
      })
    }
  }, [])

  useEffect(() => {
    checkDbHealth()
    checkDbSummary()
  }, [checkDbHealth, checkDbSummary])

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

  const appendMessage = (chatId, message) => {
    setChats((current) =>
      current.map((chat) =>
        chat.id === chatId ? { ...chat, messages: [...chat.messages, message] } : chat,
      ),
    )
  }

  const handleSendMessage = async (content) => {
    const text = content.trim()
    if (!text || !activeChat || isSending) return

    const targetChatId = activeChat.id
    appendMessage(targetChatId, createMessage('user', text))
    setIsSending(true)

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: text,
          model: settings.model,
          temperature: settings.temperature,
          systemPrompt: settings.systemPrompt,
          memoryRounds: settings.memoryRounds,
          enableContextRouter: settings.enableContextRouter,
          enableDbQuery: settings.enableDbQuery,
          enableRag: settings.enableRag,
          enableImageSkill: settings.enableImageSkill,
          enableAuditLog: settings.enableAuditLog,
        }),
      })
      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}`)
      }

      appendMessage(targetChatId, createMessage('system', data.message))
    } catch (error) {
      const message =
        error instanceof Error
          ? `後端回覆失敗：${error.message}`
          : '後端回覆失敗：Unknown error'
      appendMessage(targetChatId, createMessage('system', message))
    } finally {
      setIsSending(false)
    }
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
        dbHealth={dbHealth}
        isSending={isSending}
        selectedModel={settings.model}
        onOpenControls={() => setMobileControlsOpen(true)}
        onOpenSidebar={() => setMobileSidebarOpen(true)}
        onRefreshDbHealth={checkDbHealth}
        onSendMessage={handleSendMessage}
      />

      <ControlPanel
        collapsed={controlsCollapsed}
        dbSummary={dbSummary}
        mobileOpen={mobileControlsOpen}
        settings={settings}
        onChange={handleSettingChange}
        onCloseMobile={() => setMobileControlsOpen(false)}
        onRefreshSummary={checkDbSummary}
        onToggleCollapse={() => setControlsCollapsed((current) => !current)}
      />
    </div>
  )
}

export default App

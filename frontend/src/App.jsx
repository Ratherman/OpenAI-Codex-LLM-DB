import { useCallback, useEffect, useMemo, useState } from 'react'
import ChatArea from './components/ChatArea.jsx'
import ControlPanel from './components/ControlPanel.jsx'
import Sidebar from './components/Sidebar.jsx'
import './App.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:5000'

const makeTempId = (prefix) =>
  `temp-${prefix}-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`}`

const createTemporaryMessage = (roomId, role, content, metadata = {}) => ({
  id: makeTempId(role),
  room_id: roomId,
  role,
  content,
  metadata,
  metadata_json: JSON.stringify(metadata),
  created_at: new Date().toISOString(),
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

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(data.error || `HTTP ${response.status}`)
  }

  return data
}

function App() {
  const [rooms, setRooms] = useState([])
  const [activeRoomId, setActiveRoomId] = useState(null)
  const [messages, setMessages] = useState([])
  const [roomsStatus, setRoomsStatus] = useState('loading')
  const [messagesStatus, setMessagesStatus] = useState('idle')
  const [roomsError, setRoomsError] = useState('')
  const [messagesError, setMessagesError] = useState('')
  const [actionError, setActionError] = useState('')
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
  const [llmHealth, setLlmHealth] = useState({
    status: 'checking',
    configured: false,
    apiReachable: false,
    keyMasked: '',
    error: '',
  })

  const activeRoom = useMemo(
    () => rooms.find((room) => room.id === activeRoomId) ?? rooms[0] ?? null,
    [activeRoomId, rooms],
  )
  const activeChat = activeRoom ? { ...activeRoom, messages } : null

  const loadRooms = useCallback(async (preferredRoomId = null) => {
    setRoomsStatus('loading')
    setRoomsError('')

    try {
      const data = await apiRequest('/api/chat/rooms')
      const nextRooms = data.rooms ?? []
      setRooms(nextRooms)
      setRoomsStatus('idle')
      setActiveRoomId((currentId) => {
        const requestedId = preferredRoomId ?? currentId
        if (requestedId && nextRooms.some((room) => room.id === requestedId)) {
          return requestedId
        }
        return nextRooms[0]?.id ?? null
      })
    } catch (error) {
      setRoomsStatus('error')
      setRoomsError(error instanceof Error ? error.message : '聊天室載入失敗')
    }
  }, [])

  const loadMessages = useCallback(async (roomId) => {
    if (!roomId) {
      setMessages([])
      setMessagesStatus('idle')
      return
    }

    setMessagesStatus('loading')
    setMessagesError('')

    try {
      const data = await apiRequest(`/api/chat/rooms/${roomId}/messages`)
      setMessages(data.messages ?? [])
      setMessagesStatus('idle')
    } catch (error) {
      setMessagesStatus('error')
      setMessagesError(error instanceof Error ? error.message : '訊息載入失敗')
    }
  }, [])

  const checkDbHealth = useCallback(async () => {
    setDbHealth({ status: 'checking', version: '', error: '' })

    try {
      const data = await apiRequest('/api/db/health')
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
      const data = await apiRequest('/api/db/summary')
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

  const checkLlmHealth = useCallback(async () => {
    setLlmHealth({
      status: 'checking',
      configured: false,
      apiReachable: false,
      keyMasked: '',
      error: '',
    })

    try {
      const response = await fetch(`${API_BASE_URL}/api/llm/health`)
      const data = await response.json()

      setLlmHealth({
        status: response.ok ? 'online' : 'offline',
        configured: Boolean(data.configured),
        apiReachable: Boolean(data.api_reachable),
        keyMasked: data.key_masked ?? '',
        error: response.ok ? '' : data.error || `HTTP ${response.status}`,
      })
    } catch (error) {
      setLlmHealth({
        status: 'offline',
        configured: false,
        apiReachable: false,
        keyMasked: '',
        error: error instanceof Error ? error.message : 'LLM health check failed',
      })
    }
  }, [])

  useEffect(() => {
    loadRooms()
    checkDbHealth()
    checkDbSummary()
    checkLlmHealth()
  }, [checkDbHealth, checkDbSummary, checkLlmHealth, loadRooms])

  useEffect(() => {
    loadMessages(activeRoomId)
  }, [activeRoomId, loadMessages])

  const handleCreateChat = async () => {
    setActionError('')
    try {
      const data = await apiRequest('/api/chat/rooms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: `聊天室 ${rooms.length + 1}` }),
      })
      await loadRooms(data.room.id)
      setMobileSidebarOpen(false)
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '新增聊天室失敗')
    }
  }

  const handleRenameChat = async (roomId, title) => {
    const nextTitle = title.trim()
    if (!nextTitle) return

    setActionError('')
    try {
      const data = await apiRequest(`/api/chat/rooms/${roomId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: nextTitle }),
      })
      setRooms((current) =>
        current.map((room) => (room.id === roomId ? { ...room, ...data.room } : room)),
      )
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '重新命名聊天室失敗')
    }
  }

  const handleDeleteChat = async (roomId) => {
    setActionError('')
    try {
      await apiRequest(`/api/chat/rooms/${roomId}`, { method: 'DELETE' })
      if (activeRoomId === roomId) {
        setMessages([])
      }
      await loadRooms()
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '刪除聊天室失敗')
    }
  }

  const handleSelectChat = (roomId) => {
    setActiveRoomId(roomId)
    setMobileSidebarOpen(false)
  }

  const handleSendMessage = async (content) => {
    const text = content.trim()
    if (!text || !activeRoom || isSending) return

    const targetRoomId = activeRoom.id
    const optimisticUserMessage = createTemporaryMessage(targetRoomId, 'user', text, {
      source: 'frontend_optimistic',
    })
    const loadingAssistantMessage = {
      ...createTemporaryMessage(targetRoomId, 'assistant', '正在等待 LLM 回覆...', {
        source: 'frontend_loading',
      }),
      status: 'loading',
    }

    setActionError('')
    setIsSending(true)
    setMessages((current) => [...current, optimisticUserMessage, loadingAssistantMessage])

    try {
      const data = await apiRequest(`/api/chat/rooms/${targetRoomId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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

      const persistedMessages = data.messages ?? []
      setMessages((current) => [
        ...current.filter(
          (message) =>
            message.id !== optimisticUserMessage.id && message.id !== loadingAssistantMessage.id,
        ),
        ...persistedMessages,
      ])
      await loadRooms(targetRoomId)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '送出訊息失敗'
      setActionError(errorMessage)
      setMessages((current) =>
        current.map((message) =>
          message.id === loadingAssistantMessage.id
            ? {
                ...message,
                status: 'error',
                content: `LLM 回覆失敗：${errorMessage}`,
                metadata: { source: 'frontend_error', error: errorMessage },
                metadata_json: JSON.stringify({ source: 'frontend_error', error: errorMessage }),
              }
            : message,
        ),
      )
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
        activeChatId={activeRoom?.id}
        chats={rooms}
        collapsed={sidebarCollapsed}
        error={roomsError || actionError}
        isLoading={roomsStatus === 'loading'}
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
        error={messagesError || actionError}
        isLoadingMessages={messagesStatus === 'loading'}
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
        llmHealth={llmHealth}
        mobileOpen={mobileControlsOpen}
        settings={settings}
        onChange={handleSettingChange}
        onCloseMobile={() => setMobileControlsOpen(false)}
        onRefreshLlmHealth={checkLlmHealth}
        onRefreshSummary={checkDbSummary}
        onToggleCollapse={() => setControlsCollapsed((current) => !current)}
      />
    </div>
  )
}

export default App

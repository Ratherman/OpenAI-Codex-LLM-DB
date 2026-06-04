import { ChevronLeft, ChevronRight, Database, RefreshCw, X } from 'lucide-react'

const toggleFields = [
  ['enableContextRouter', 'Enable Context Router'],
  ['enableDbQuery', 'Enable DB Query'],
  ['enableRag', 'Enable RAG'],
  ['enableImageSkill', 'Enable Image Skill'],
  ['enableAuditLog', 'Enable Audit Log'],
]

function ControlPanel({
  collapsed,
  dbSummary,
  mobileOpen,
  settings,
  onChange,
  onCloseMobile,
  onRefreshSummary,
  onToggleCollapse,
}) {
  const showRail = collapsed && !mobileOpen
  const summary = dbSummary.data

  if (showRail) {
    return (
      <aside className={`control-panel is-collapsed ${mobileOpen ? 'is-mobile-open' : ''}`}>
        <button
          aria-label="展開設定面板"
          className="icon-button rail-button"
          title="展開設定面板"
          type="button"
          onClick={onToggleCollapse}
        >
          <ChevronLeft size={20} />
        </button>
      </aside>
    )
  }

  return (
    <aside className={`control-panel ${mobileOpen ? 'is-mobile-open' : ''}`}>
      <div className="panel-header">
        <div>
          <p className="panel-kicker">Controls</p>
          <h2>設定</h2>
        </div>
        <div className="header-actions">
          <button
            aria-label="收合設定面板"
            className="icon-button desktop-only"
            title="收合設定面板"
            type="button"
            onClick={onToggleCollapse}
          >
            <ChevronRight size={19} />
          </button>
          <button
            aria-label="關閉設定"
            className="icon-button mobile-only"
            title="關閉設定"
            type="button"
            onClick={onCloseMobile}
          >
            <X size={19} />
          </button>
        </div>
      </div>

      <div className="settings-stack">
        <section className="db-summary-card" aria-label="資料庫摘要">
          <div className="db-summary-header">
            <div>
              <p className="panel-kicker">Database</p>
              <h3>資料摘要</h3>
            </div>
            <button
              aria-label="重新整理資料摘要"
              className="icon-button"
              title="重新整理資料摘要"
              type="button"
              onClick={onRefreshSummary}
            >
              <RefreshCw size={17} />
            </button>
          </div>

          {dbSummary.status === 'offline' ? (
            <p className="summary-error">{dbSummary.error}</p>
          ) : (
            <div className="summary-grid">
              <div>
                <span>員工</span>
                <strong>{summary?.employee_count ?? '-'}</strong>
              </div>
              <div>
                <span>費用筆數</span>
                <strong>{summary?.expense_count ?? '-'}</strong>
              </div>
              <div>
                <span>費用總額</span>
                <strong>{summary?.expense_total ? `TWD ${summary.expense_total}` : '-'}</strong>
              </div>
              <div>
                <span>發票</span>
                <strong>{summary?.invoice_count ?? '-'}</strong>
              </div>
              <div>
                <span>廠商</span>
                <strong>{summary?.vendor_count ?? '-'}</strong>
              </div>
              <div>
                <span>稽核紀錄</span>
                <strong>{summary?.audit_log_count ?? '-'}</strong>
              </div>
            </div>
          )}
        </section>

        <label className="field">
          <span>模型選擇</span>
          <select value={settings.model} onChange={(event) => onChange('model', event.target.value)}>
            <option value="gpt-4o">gpt-4o</option>
            <option value="gpt-5.4">gpt-5.4</option>
            <option value="gpt-5.5">gpt-5.5</option>
          </select>
        </label>

        <label className="field">
          <span>Temperature</span>
          <div className="range-row">
            <input
              max="1"
              min="0"
              step="0.05"
              type="range"
              value={settings.temperature}
              onChange={(event) => onChange('temperature', Number(event.target.value))}
            />
            <output>{settings.temperature.toFixed(2)}</output>
          </div>
        </label>

        <label className="field">
          <span>System Prompt</span>
          <textarea
            rows={6}
            value={settings.systemPrompt}
            onChange={(event) => onChange('systemPrompt', event.target.value)}
          />
        </label>

        <label className="field">
          <span>Memory 輪數</span>
          <div className="range-row">
            <input
              max="10"
              min="1"
              step="1"
              type="range"
              value={settings.memoryRounds}
              onChange={(event) => onChange('memoryRounds', Number(event.target.value))}
            />
            <output>{settings.memoryRounds}</output>
          </div>
        </label>

        <div aria-label="功能開關" className="toggle-stack">
          {toggleFields.map(([key, label]) => (
            <label className="switch-row" key={key}>
              <span>{label}</span>
              <input
                checked={settings[key]}
                type="checkbox"
                onChange={(event) => onChange(key, event.target.checked)}
              />
            </label>
          ))}
        </div>
      </div>

      <div className="control-footer">
        <Database size={18} />
        <span>Stage 5 Data</span>
      </div>
    </aside>
  )
}

export default ControlPanel

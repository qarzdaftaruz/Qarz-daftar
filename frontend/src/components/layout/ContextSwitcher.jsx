import { useAuth } from '../../hooks/useAuth'

export default function ContextSwitcher() {
  const { canSwitch, view, setView } = useAuth()
  if (!canSwitch) return null

  return (
    <div
      style={{
        display: 'flex',
        gap: 4,
        padding: 4,
        borderRadius: 14,
        background: 'var(--tg-theme-secondary-bg-color, #f4f4f5)',
        marginTop: 10,
      }}
    >
      {[
        { key: 'owner',  label: "🏪 Do'konim" },
        { key: 'debtor', label: '🧾 Qarzlarim' },
      ].map(({ key, label }) => (
        <button
          key={key}
          onClick={() => setView(key)}
          style={{
            flex: 1,
            padding: '8px 12px',
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 600,
            border: 'none',
            cursor: 'pointer',
            transition: 'all 0.2s cubic-bezier(0.22, 1, 0.36, 1)',
            background: view === key ? 'var(--tg-theme-bg-color, #fff)' : 'transparent',
            color: view === key ? 'var(--tg-theme-text-color, #000)' : 'var(--tg-theme-hint-color, #707579)',
            boxShadow: view === key
              ? '0 2px 8px rgba(0,0,0,0.08), 0 1px 0 rgba(255,255,255,0.6) inset'
              : 'none',
            transform: view === key ? 'scale(1.01)' : 'scale(1)',
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

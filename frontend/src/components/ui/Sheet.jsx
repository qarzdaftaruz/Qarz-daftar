import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

export default function Sheet({ open, onClose, title, children }) {
  useEffect(() => {
    if (!open) return
    const tma = window.Telegram?.WebApp
    if (tma) {
      tma.BackButton.show()
      tma.BackButton.onClick(onClose)
      return () => {
        tma.BackButton.hide()
        tma.BackButton.offClick(onClose)
      }
    }
  }, [open, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="animate-fade-in"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'flex-end',
      }}
    >
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0,0,0,0.5)',
          backdropFilter: 'blur(4px)',
          WebkitBackdropFilter: 'blur(4px)',
        }}
      />

      {/* Panel */}
      <div
        className="animate-sheet-up"
        style={{
          position: 'relative',
          background: 'var(--tg-theme-bg-color, #fff)',
          borderRadius: '28px 28px 0 0',
          maxHeight: '92svh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 -14px 52px rgba(15,23,42,0.22), 0 -1px 0 rgba(255,255,255,0.08)',
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
      >
        {/* Drag handle */}
        <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 10, paddingBottom: 4, flexShrink: 0 }}>
          <div style={{
            width: 36,
            height: 4,
            borderRadius: 99,
            background: 'var(--tg-theme-hint-color, #c8c8cc)',
            opacity: 0.35,
          }} />
        </div>

        {/* Header */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 20px 12px',
          flexShrink: 0,
        }}>
          <h2 style={{
            fontFamily: "'Space Grotesk', sans-serif",
            fontWeight: 700,
            fontSize: 17,
            letterSpacing: '-0.01em',
            color: 'var(--tg-theme-text-color, #000)',
            margin: 0,
          }}>
            {title}
          </h2>
          <button
            onClick={onClose}
            style={{
              width: 32,
              height: 32,
              borderRadius: '50%',
              background: 'var(--tg-theme-secondary-bg-color, #f4f4f5)',
              border: 'none',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            <X size={15} style={{ color: 'var(--tg-theme-hint-color)' }} />
          </button>
        </div>

        {/* Divider */}
        <div style={{
          height: 0.5,
          background: 'var(--tg-theme-secondary-bg-color, #e5e5ea)',
          marginLeft: 20,
          marginRight: 20,
          flexShrink: 0,
        }} />

        {/* Content */}
        <div style={{
          overflowY: 'auto',
          padding: '16px 20px 28px',
          flex: 1,
        }}>
          {children}
        </div>
      </div>
    </div>,
    document.body
  )
}

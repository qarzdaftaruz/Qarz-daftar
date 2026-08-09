import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { tma } from '../lib/tma'
import { shopsApi } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import { useTimedState } from '../hooks/useTimedState'
import ConfirmStamp from '../components/ui/ConfirmStamp'
import { Store, Tag, ArrowLeft } from 'lucide-react'

export default function NewShop({ standalone }) {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [form, setForm]     = useState({ shop_name: '', promo_code: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useTimedState('')
  const [sent, setSent]     = useState(false)

  const submit = async () => {
    if (!form.shop_name.trim()) { setError("Do'kon nomi kiritilishi shart"); return }
    setSaving(true); setError('')
    try {
      await shopsApi.create({ shop_name: form.shop_name.trim(), promo_code: form.promo_code.trim() })
      tma.haptic('success')
      setSent(true)
      setTimeout(async () => { await refresh(); navigate('/') }, 1700)
    } catch (e) {
      setError(e.response?.data?.detail || 'Xato yuz berdi')
      setSaving(false)
    }
  }

  return (
    <div
      className="animate-slide-up"
      style={{
        minHeight: '100svh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--tg-theme-bg-color, #fff)',
        padding: '0 0 32px',
      }}
    >
      {/* Top bar */}
      {!standalone && (
        <div style={{ padding: '14px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => navigate(-1)}
            style={{
              width: 36, height: 36, borderRadius: '50%', border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'var(--tg-theme-secondary-bg-color)',
              cursor: 'pointer',
            }}
          >
            <ArrowLeft size={18} style={{ color: 'var(--tg-theme-text-color)' }} />
          </button>
        </div>
      )}

      {/* Hero illustration */}
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        paddingTop: standalone ? 56 : 24,
        paddingBottom: 32,
      }}>
        <div style={{
          width: 88, height: 88, borderRadius: 28, marginBottom: 20,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'linear-gradient(135deg, #2678b6 0%, #7c3aed 100%)',
          boxShadow: '0 12px 40px rgba(38,120,182,0.4), 0 4px 16px rgba(124,58,237,0.2)',
        }}>
          <Store size={40} style={{ color: '#fff' }} />
        </div>
        <h1 className="font-display" style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em', textAlign: 'center', color: 'var(--tg-theme-text-color)', margin: '0 0 8px' }}>
          Do'kon ochish
        </h1>
        <p style={{ fontSize: 14, textAlign: 'center', color: 'var(--tg-theme-hint-color)', margin: 0, maxWidth: 260, lineHeight: 1.5 }}>
          Do'kon nomini kiriting, admin tez orada tasdiqlaydi
        </p>
      </div>

      {/* Form */}
      <div style={{ padding: '0 20px', display: 'flex', flexDirection: 'column', gap: 14, flex: 1 }}>
        {error && (
          <div style={{
            fontSize: 13, color: '#b91c1c',
            background: '#fef2f2',
            padding: '12px 16px', borderRadius: 14,
            border: '1px solid #fecaca',
          }}>
            {error}
          </div>
        )}

        <div>
          <label className="section-title" style={{ display: 'block', marginBottom: 7 }}>Do'kon nomi *</label>
          <input
            className="input"
            placeholder="Masalan: Alisher do'koni"
            value={form.shop_name}
            autoFocus
            onChange={e => setForm(s => ({ ...s, shop_name: e.target.value }))}
            onKeyDown={e => e.key === 'Enter' && submit()}
          />
        </div>

        <div>
          <label className="section-title" style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 7 }}>
            <Tag size={11} /> Promo kod (ixtiyoriy)
          </label>
          <input
            className="input"
            style={{ textTransform: 'uppercase', letterSpacing: '0.12em', fontFamily: 'monospace', fontWeight: 600 }}
            placeholder="PROMO2025"
            value={form.promo_code}
            onChange={e => setForm(s => ({ ...s, promo_code: e.target.value.toUpperCase() }))}
          />
        </div>

        <button onClick={submit} disabled={saving} className="btn-primary" style={{ marginTop: 4 }}>
          {saving ? 'Yuborilmoqda…' : "So'rov yuborish"}
        </button>

        {!standalone && (
          <button onClick={() => navigate(-1)} className="btn-ghost">
            Bekor qilish
          </button>
        )}
      </div>

      <p style={{ fontSize: 12, textAlign: 'center', color: 'var(--tg-theme-hint-color)', margin: '24px 0 0' }}>
        Tasdiqlangach Telegram orqali xabardor qilinasiz
      </p>

      {/* So'rov qabul qilindi — "TASDIQLANDI" muhri */}
      {sent && createPortal(
        <div
          className="animate-fade-in"
          style={{
            position: 'fixed', inset: 0, zIndex: 10000,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 22, padding: 32, textAlign: 'center',
            background: 'rgba(15,23,42,0.55)', backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
          }}
        >
          <div style={{
            width: 180, height: 180, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--tg-theme-bg-color, #fff)',
            boxShadow: '0 20px 60px rgba(22,163,74,0.4)',
          }}>
            <ConfirmStamp label="QABUL QILINDI" size={140} />
          </div>
          <div>
            <p className="font-display" style={{ fontSize: 19, fontWeight: 700, color: '#fff', margin: '0 0 6px' }}>
              So'rovingiz yuborildi!
            </p>
            <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.8)', margin: 0 }}>
              Admin tez orada ko'rib chiqadi
            </p>
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

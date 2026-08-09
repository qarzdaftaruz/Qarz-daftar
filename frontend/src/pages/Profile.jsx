import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { tma } from '../lib/tma'
import { profileApi } from '../lib/api'
import { useAuth } from '../hooks/useAuth'
import { useTimedState } from '../hooks/useTimedState'
import { Phone, Plus, ChevronLeft, Pencil, Trash2, Check, X, Lock } from 'lucide-react'

export default function Profile() {
  const navigate = useNavigate()
  const { user, refresh, canSwitch } = useAuth()

  const [newPhone, setNewPhone] = useState('')
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useTimedState('')
  const [msg, setMsg]           = useTimedState('')
  const [editing, setEditing]   = useState(null)
  const [editError, setEditError] = useTimedState('')

  const clearMessages = () => { setError(''); setMsg(''); setEditError('') }

  const addPhone = async () => {
    if (!newPhone.trim()) return
    setSaving(true); clearMessages()
    try {
      await profileApi.addPhone(newPhone.trim())
      tma.haptic('light')
      setNewPhone('')
      setMsg("✅ Raqam qo'shildi")
      await refresh()
    } catch (e) {
      setError(e.response?.data?.detail || 'Xato yuz berdi')
    } finally { setSaving(false) }
  }

  const startEdit  = (i) => { setEditing({ index: i, value: user.extra_phones[i] }); setEditError('') }
  const cancelEdit = ()  => { setEditing(null); setEditError('') }

  const saveEdit = async () => {
    if (!editing?.value.trim()) return
    setSaving(true); setEditError('')
    try {
      await profileApi.updatePhone(editing.index, editing.value.trim())
      tma.haptic('light')
      setEditing(null)
      setMsg('✅ Raqam yangilandi')
      await refresh()
    } catch (e) {
      setEditError(e.response?.data?.detail || 'Xato yuz berdi')
    } finally { setSaving(false) }
  }

  const removePhone = async (i) => {
    setSaving(true); clearMessages()
    try {
      await profileApi.removePhone(i)
      tma.haptic('medium')
      setMsg("✅ Raqam o'chirildi")
      await refresh()
    } catch (e) {
      setError(e.response?.data?.detail || 'Xato yuz berdi')
    } finally { setSaving(false) }
  }

  const initial = user?.full_name?.[0]?.toUpperCase() || '?'

  return (
    <div
      className="animate-slide-up"
      style={{
        minHeight: '100svh',
        paddingBottom: 40,
        background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)',
      }}
    >
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        background: 'var(--tg-theme-bg-color, #fff)',
        boxShadow: '0 1px 0 rgba(0,0,0,0.06)',
        padding: '14px 16px',
      }}>
        {canSwitch && (
          <button
            onClick={() => navigate(-1)}
            style={{
              width: 36, height: 36, borderRadius: '50%', border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'var(--tg-theme-secondary-bg-color)',
              cursor: 'pointer', marginLeft: -6,
            }}
          >
            <ChevronLeft size={20} style={{ color: 'var(--tg-theme-text-color)' }} />
          </button>
        )}
        <h1 className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--tg-theme-text-color)', margin: 0 }}>
          Profil
        </h1>
      </div>

      <div style={{ padding: '16px 16px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {/* User card */}
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 60, height: 60, borderRadius: 22, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 24, fontWeight: 800, color: '#fff',
              background: 'linear-gradient(135deg, #2678b6 0%, #7c3aed 100%)',
              boxShadow: '0 6px 20px rgba(38,120,182,0.35)',
            }}>
              {initial}
            </div>
            <div>
              <p className="font-display" style={{ fontWeight: 700, fontSize: 17, letterSpacing: '-0.01em', color: 'var(--tg-theme-text-color)', margin: '0 0 5px' }}>
                {user?.full_name}
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Phone size={13} style={{ color: 'var(--tg-theme-hint-color)' }} />
                <p style={{ fontSize: 14, color: 'var(--tg-theme-hint-color)', margin: 0 }}>{user?.phone}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Extra phones */}
        <div className="card">
          <p className="section-title" style={{ marginBottom: 14 }}>Qo'shimcha raqamlar</p>

          {user?.extra_phones?.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 12 }}>
              {user.extra_phones.map((p, i) => (
                <div key={i}>
                  {editing?.index === i ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <div style={{ display: 'flex', gap: 8 }}>
                        <input
                          className="input"
                          style={{ flex: 1 }}
                          value={editing.value}
                          onChange={e => setEditing(s => ({ ...s, value: e.target.value }))}
                          autoFocus
                        />
                        <button
                          onClick={saveEdit}
                          disabled={saving}
                          style={{
                            width: 42, height: 42, borderRadius: 14, flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
                            border: 'none', cursor: 'pointer',
                          }}
                        >
                          <Check size={16} style={{ color: '#fff' }} />
                        </button>
                        <button
                          onClick={cancelEdit}
                          style={{
                            width: 42, height: 42, borderRadius: 14, flexShrink: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: 'var(--tg-theme-secondary-bg-color)',
                            border: 'none', cursor: 'pointer',
                          }}
                        >
                          <X size={16} style={{ color: 'var(--tg-theme-hint-color)' }} />
                        </button>
                      </div>
                      {editError && <p style={{ fontSize: 12, color: '#ef4444', margin: 0 }}>{editError}</p>}
                    </div>
                  ) : (
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '10px 14px', borderRadius: 14,
                      background: 'var(--tg-theme-secondary-bg-color)',
                    }}>
                      <Phone size={13} style={{ color: 'var(--tg-theme-hint-color)' }} />
                      <span style={{ fontSize: 14, flex: 1, color: 'var(--tg-theme-text-color)' }}>{p}</span>
                      {i === 0 ? (
                        <div
                          title="Birinchi qo'shilgan raqamni o'zgartirib bo'lmaydi"
                          style={{
                            width: 30, height: 30, borderRadius: 10,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}
                        >
                          <Lock size={12} style={{ color: 'var(--tg-theme-hint-color)', opacity: 0.7 }} />
                        </div>
                      ) : (
                        <button
                          onClick={() => startEdit(i)}
                          disabled={saving}
                          style={{
                            width: 30, height: 30, borderRadius: 10,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            background: 'var(--tg-theme-bg-color, #fff)',
                            border: 'none', cursor: 'pointer',
                          }}
                        >
                          <Pencil size={12} style={{ color: 'var(--tg-theme-hint-color)' }} />
                        </button>
                      )}
                      <button
                        onClick={() => removePhone(i)}
                        disabled={saving}
                        style={{
                          width: 30, height: 30, borderRadius: 10,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          background: 'var(--tg-theme-bg-color, #fff)',
                          border: 'none', cursor: 'pointer',
                        }}
                      >
                        <Trash2 size={12} style={{ color: '#ef4444' }} />
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '0 0 12px' }}>
            Boshqa raqamga yozilgan qarzlarni ham ko'rish uchun shu yerga qo'shing (maksimal 2 ta)
          </p>

          {error && <p style={{ fontSize: 13, color: '#ef4444', marginBottom: 8 }}>{error}</p>}
          {msg   && <p style={{ fontSize: 13, color: '#22c55e', marginBottom: 8 }}>{msg}</p>}

          {(user?.extra_phones?.length ?? 0) < 2 ? (
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="input"
                style={{ flex: 1 }}
                placeholder="+998901234567"
                value={newPhone}
                onChange={e => setNewPhone(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && addPhone()}
              />
              <button
                onClick={addPhone}
                disabled={saving}
                style={{
                  padding: '0 18px', borderRadius: 16, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'linear-gradient(135deg, #2563EB 0%, #1d4ed8 100%)',
                  border: 'none', cursor: 'pointer',
                  boxShadow: '0 4px 12px rgba(37,99,235,0.35)',
                }}
              >
                <Plus size={20} style={{ color: '#fff' }} />
              </button>
            </div>
          ) : (
            <p style={{
              fontSize: 12, textAlign: 'center', color: 'var(--tg-theme-hint-color)',
              padding: '10px 12px', borderRadius: 12,
              background: 'var(--tg-theme-secondary-bg-color)', margin: 0,
            }}>
              Maksimal 2 ta qo'shimcha raqam qo'shildi
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

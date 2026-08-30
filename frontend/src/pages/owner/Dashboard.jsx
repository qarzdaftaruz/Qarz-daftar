import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, FileText, AlertTriangle, Clock, ChevronRight, ChevronDown, Check, Plus, TrendingUp } from 'lucide-react'
import { ownerApi, errorMessage } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { fmt, statusEmoji, statusBadge } from '../../lib/utils'
import ContextSwitcher from '../../components/layout/ContextSwitcher'
import Sheet from '../../components/ui/Sheet'
import Money from '../../components/ui/Money'
import LoadError from '../../components/ui/LoadError'

function Skeleton() {
  return (
    <div className="px-4 pt-4 space-y-3">
      <div className="skeleton h-32 w-full" />
      <div className="grid grid-cols-2 gap-3">
        <div className="skeleton h-28" />
        <div className="skeleton h-28" />
      </div>
      <div className="skeleton h-48 w-full" />
    </div>
  )
}

export default function Dashboard() {
  const [data, setData]           = useState(null)
  const [loading, setLoading]     = useState(true)
  const [loadError, setLoadError] = useState('')
  const [shopSheet, setShopSheet] = useState(false)
  const { currentShopId, activeShops, pendingShops, setShop, user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => { if (currentShopId) load() }, [currentShopId])

  const load = async () => {
    setLoading(true); setLoadError('')
    try {
      const res = await ownerApi.dashboard(currentShopId)
      setData(res.data)
    } catch (e) {
      setLoadError(errorMessage(e, 'Panel yuklanmadi'))
    } finally { setLoading(false) }
  }

  const currentShopName = activeShops.find(s => s.id === currentShopId)?.name || data?.shop_name || '…'

  return (
    <div
      className="animate-slide-up"
      style={{
        minHeight: '100svh',
        paddingBottom: 96,
        background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)',
      }}
    >
      {/* Sticky Header */}
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 10,
          background: 'var(--tg-theme-bg-color, #fff)',
          boxShadow: '0 1px 0 rgba(0,0,0,0.06)',
          padding: '16px 16px 12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          {activeShops.length > 1 ? (
            <button
              onClick={() => setShopSheet(true)}
              style={{
                display: 'flex', alignItems: 'center', gap: 4,
                background: 'none', border: 'none', cursor: 'pointer',
                padding: '2px 0', marginLeft: -2,
              }}
            >
              <h1 className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--tg-theme-text-color)', margin: 0 }}>
                {currentShopName}
              </h1>
              <ChevronDown size={18} style={{ color: 'var(--tg-theme-hint-color)', marginTop: 1 }} />
            </button>
          ) : (
            <h1 className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--tg-theme-text-color)', margin: 0 }}>
              {currentShopName}
            </h1>
          )}

          <button
            onClick={() => navigate('/new-shop')}
            style={{
              fontSize: 12,
              fontWeight: 600,
              padding: '6px 12px',
              borderRadius: 10,
              border: 'none',
              cursor: 'pointer',
              background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)',
              color: 'var(--tg-theme-hint-color)',
              flexShrink: 0,
            }}
          >
            + Do'kon
          </button>
        </div>

        <ContextSwitcher />

        {pendingShops.length > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '8px 12px', borderRadius: 12, marginTop: 10,
            background: '#fffbeb',
            border: '1px solid #fef3c7',
          }}>
            <Clock size={13} style={{ color: '#d97706', flexShrink: 0 }} />
            <p style={{ fontSize: 12, fontWeight: 500, color: '#92400e', margin: 0 }}>
              {pendingShops.length === 1
                ? `"${pendingShops[0].name}" tasdiqlash kutilmoqda`
                : `${pendingShops.length} ta do'koningiz tasdiqlash kutilmoqda`}
            </p>
          </div>
        )}
      </div>

      {loading ? <Skeleton /> : loadError && !data ? (
        <LoadError message={loadError} onRetry={load} />
      ) : (
        <div style={{ padding: '16px 16px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Hero card — gradient */}
          <div className="card-hero animate-rise">
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.09em', opacity: 0.78, marginBottom: 8, position: 'relative' }}>
              Umumiy qoldiq
            </p>
            <Money
              value={data?.stats.total_remaining}
              className="font-display"
              style={{ display: 'block', fontSize: 36, fontWeight: 800, lineHeight: 1, position: 'relative' }}
            />

            {data?.stats.overdue_debts > 0 && (
              <div style={{
                position: 'relative',
                display: 'inline-flex', alignItems: 'center', gap: 5,
                marginTop: 14, padding: '6px 12px', borderRadius: 10,
                background: 'rgba(255,255,255,0.18)',
                border: '1px solid rgba(255,255,255,0.28)',
              }}>
                <AlertTriangle size={12} style={{ color: '#fca5a5' }} />
                <span style={{ fontSize: 12, fontWeight: 700, color: '#fca5a5' }}>
                  {data.stats.overdue_debts} ta muddati o'tgan
                </span>
              </div>
            )}
          </div>

          {/* Mini stats row */}
          <div className="row-stagger" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <button
              onClick={() => navigate('/clients')}
              className="card tappable"
              style={{ textAlign: 'left', border: 'none', width: '100%' }}
            >
              <div style={{
                width: 40, height: 40, borderRadius: 14,
                background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 12,
                boxShadow: '0 4px 12px rgba(59,130,246,0.35)',
              }}>
                <Users size={18} style={{ color: '#fff' }} />
              </div>
              <p className="section-title" style={{ marginBottom: 4 }}>Mijozlar</p>
              <p className="money" style={{ fontSize: 26, fontWeight: 700, color: 'var(--tg-theme-text-color)', lineHeight: 1 }}>
                {data?.stats.clients ?? 0}
              </p>
            </button>

            <button
              onClick={() => navigate('/stats')}
              className="card tappable"
              style={{ textAlign: 'left', border: 'none', width: '100%' }}
            >
              <div style={{
                width: 40, height: 40, borderRadius: 14,
                background: 'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                marginBottom: 12,
                boxShadow: '0 4px 12px rgba(139,92,246,0.35)',
              }}>
                <TrendingUp size={18} style={{ color: '#fff' }} />
              </div>
              <p className="section-title" style={{ marginBottom: 4 }}>Faol qarzlar</p>
              <p className="money" style={{ fontSize: 26, fontWeight: 700, color: 'var(--tg-theme-text-color)', lineHeight: 1 }}>
                {data?.stats.active_debts ?? 0}
              </p>
            </button>
          </div>

          {/* Recent debts */}
          {data?.recent_debts?.length > 0 ? (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '12px 16px',
                borderBottom: '0.5px solid var(--tg-theme-secondary-bg-color)',
              }}>
                <p style={{ fontSize: 14, fontWeight: 700, color: 'var(--tg-theme-text-color)', margin: 0 }}>
                  So'nggi qarzlar
                </p>
                <button
                  onClick={() => navigate('/clients')}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 2,
                    fontSize: 12, fontWeight: 700,
                    color: 'var(--tg-theme-button-color)',
                    background: 'none', border: 'none', cursor: 'pointer',
                  }}
                >
                  Barchasi <ChevronRight size={13} />
                </button>
              </div>
              <div className={data.recent_debts.length < 15 ? 'row-stagger' : ''}>
              {data.recent_debts.map(d => (
                <div key={d.id} className="list-item" onClick={() => navigate('/clients')}>
                  <div style={{
                    width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 14, color: '#fff',
                    background: d.status === 'overdue'
                      ? 'linear-gradient(135deg, #F87171 0%, #DC2626 100%)'
                      : 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
                  }}>
                    {d.client_name?.[0]?.toUpperCase()}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontWeight: 600, fontSize: 14, color: 'var(--tg-theme-text-color)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {d.client_name}
                    </p>
                    <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '2px 0 0' }}>
                      #{d.debt_number}{d.due_date && ` · ${fmt.dateShort(d.due_date)} gacha`}
                    </p>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <p className="money" style={{
                      fontWeight: 700, fontSize: 14, margin: 0,
                      color: d.status === 'overdue' ? '#ef4444' : 'var(--tg-theme-text-color)',
                    }}>
                      {fmt.money(d.remaining)}
                    </p>
                    <span className={statusBadge(d.status)}>{statusEmoji(d.status)}</span>
                  </div>
                </div>
              ))}
              </div>
            </div>
          ) : (
            <div className="card" style={{ textAlign: 'center', padding: '40px 16px' }}>
              <p style={{ fontSize: 40, marginBottom: 10 }}>📋</p>
              <p style={{ fontWeight: 700, fontSize: 15, color: 'var(--tg-theme-text-color)', margin: '0 0 4px' }}>
                Hali qarzlar yo'q
              </p>
              <p style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)', margin: 0 }}>
                Mijoz qo'shib qarz yozishni boshlang
              </p>
            </div>
          )}
        </div>
      )}

      {/* Do'kon tanlash Sheet */}
      <Sheet open={shopSheet} onClose={() => setShopSheet(false)} title="Do'kon tanlash">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingBottom: 8 }}>
          {activeShops.map(s => (
            <button
              key={s.id}
              onClick={() => { setShop(s.id); setShopSheet(false) }}
              style={{
                width: '100%',
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '14px 16px', borderRadius: 16, border: 'none', cursor: 'pointer',
                transition: 'all 0.15s ease',
                background: s.id === currentShopId
                  ? 'color-mix(in srgb, var(--tg-theme-button-color, #2678b6) 12%, transparent)'
                  : 'var(--tg-theme-secondary-bg-color, #f4f4f5)',
                outline: s.id === currentShopId
                  ? '2px solid var(--tg-theme-button-color, #2678b6)'
                  : '2px solid transparent',
              }}
            >
              <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--tg-theme-text-color)' }}>
                {s.name}
              </span>
              {s.id === currentShopId && (
                <Check size={16} style={{ color: 'var(--tg-theme-button-color, #2678b6)' }} />
              )}
            </button>
          ))}
          <button
            onClick={() => { setShopSheet(false); navigate('/new-shop') }}
            className="btn-ghost"
            style={{ marginTop: 4 }}
          >
            <Plus size={15} /> Yangi do'kon qo'shish
          </button>
        </div>
      </Sheet>
    </div>
  )
}

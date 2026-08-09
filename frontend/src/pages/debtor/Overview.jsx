import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { debtorApi } from '../../lib/api'
import { fmt } from '../../lib/utils'
import { ChevronRight, AlertCircle, User, Store } from 'lucide-react'
import ContextSwitcher from '../../components/layout/ContextSwitcher'
import Money from '../../components/ui/Money'

function Skeleton() {
  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="skeleton" style={{ height: 120 }} />
      <div className="skeleton" style={{ height: 180 }} />
    </div>
  )
}

export default function DebtorOverview() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate              = useNavigate()

  useEffect(() => { load() }, [])

  const load = async () => {
    setLoading(true)
    try {
      const res = await debtorApi.overview()
      setData(res.data)
    } finally { setLoading(false) }
  }

  return (
    <div
      className="animate-slide-up"
      style={{
        minHeight: '100svh',
        paddingBottom: 32,
        background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)',
      }}
    >
      {/* Header */}
      <div style={{
        background: 'var(--tg-theme-bg-color, #fff)',
        boxShadow: '0 1px 0 rgba(0,0,0,0.06)',
        padding: '14px 16px 12px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
          <h1 className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--tg-theme-text-color)', margin: 0 }}>
            Mening qarzlarim
          </h1>
          <button
            onClick={() => navigate('/profile')}
            style={{
              width: 36, height: 36, borderRadius: '50%', border: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              background: 'var(--tg-theme-secondary-bg-color)',
              cursor: 'pointer',
            }}
          >
            <User size={16} style={{ color: 'var(--tg-theme-hint-color)' }} />
          </button>
        </div>
        <ContextSwitcher />
      </div>

      {loading ? <Skeleton /> : (
        <div style={{ padding: '16px 16px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Hero totals — yashil (ishonch / xolis tajriba) */}
          <div className="card-hero-trust animate-rise">
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.09em', opacity: 0.85, marginBottom: 8, position: 'relative' }}>
              Umumiy qarzingiz
            </p>
            <Money
              value={data?.total_remaining}
              className="font-display"
              style={{ display: 'block', fontSize: 36, fontWeight: 800, lineHeight: 1, margin: '0 0 16px', position: 'relative' }}
            />
            <div style={{ position: 'relative', display: 'flex', gap: 24 }}>
              <div>
                <p style={{ fontSize: 11, opacity: 0.8, margin: '0 0 2px' }}>To'langan</p>
                <p className="money" style={{ fontSize: 15, fontWeight: 700, color: '#fff', margin: 0 }}>
                  {fmt.money(data?.total_paid)}
                </p>
              </div>
              <div>
                <p style={{ fontSize: 11, opacity: 0.8, margin: '0 0 2px' }}>Do'konlar</p>
                <p className="money" style={{ fontSize: 15, fontWeight: 700, color: '#fff', margin: 0 }}>
                  {data?.shops?.length ?? 0} ta
                </p>
              </div>
            </div>
          </div>

          {/* Shops */}
          {data?.shops?.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '48px 16px' }}>
              <p style={{ fontSize: 44, marginBottom: 12 }}>🎉</p>
              <p style={{ fontWeight: 800, fontSize: 16, color: 'var(--tg-theme-text-color)', margin: '0 0 4px' }}>
                Qarzingiz yo'q!
              </p>
              <p style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)', margin: 0 }}>
                Barcha qarzlar to'langan
              </p>
            </div>
          ) : (
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div style={{
                padding: '12px 16px',
                borderBottom: '0.5px solid var(--tg-theme-secondary-bg-color)',
              }}>
                <p className="section-title" style={{ margin: 0 }}>Do'konlar ({data?.shops?.length})</p>
              </div>
              <div className={(data?.shops?.length ?? 0) < 15 ? 'row-stagger' : ''}>
              {data?.shops?.map(shop => (
                <div
                  key={shop.shop_id}
                  className="list-item"
                  onClick={() => navigate(`/debtor/${shop.shop_id}`)}
                >
                  <div style={{
                    width: 42, height: 42, borderRadius: 16, flexShrink: 0,
                    background: 'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 4px 12px rgba(139,92,246,0.3)',
                  }}>
                    <Store size={18} style={{ color: '#fff' }} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <p style={{ fontWeight: 700, fontSize: 14, color: 'var(--tg-theme-text-color)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {shop.shop_name}
                      </p>
                      {shop.has_overdue && (
                        <AlertCircle size={13} style={{ color: '#ef4444', flexShrink: 0 }} />
                      )}
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '2px 0 0' }}>
                      {shop.active_count} ta faol qarz
                      {shop.has_overdue && <span style={{ color: '#ef4444' }}> · Muddati o'tgan!</span>}
                    </p>
                  </div>
                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <p className="money" style={{ fontWeight: 700, fontSize: 14, color: '#EF4444', margin: 0 }}>
                      {fmt.money(shop.remaining)}
                    </p>
                    {shop.paid > 0 && (
                      <p className="money" style={{ fontSize: 12, color: '#16A34A', margin: '2px 0 0' }}>
                        +{fmt.money(shop.paid)}
                      </p>
                    )}
                  </div>
                  <ChevronRight size={16} style={{ color: 'var(--tg-theme-hint-color)', flexShrink: 0 }} />
                </div>
              ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

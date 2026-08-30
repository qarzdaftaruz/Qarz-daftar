import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { tma } from '../../lib/tma'
import { debtorApi, errorMessage } from '../../lib/api'
import { fmt, statusBadge, statusLabel, statusEmoji } from '../../lib/utils'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer
} from 'recharts'
import { ChevronDown, ChevronUp, ArrowLeft } from 'lucide-react'
import LoadError from '../../components/ui/LoadError'

function BackBtn({ onClick }) {
  return (
    <button
      onClick={onClick}
      aria-label="Orqaga"
      className="tappable"
      style={{
        width: 40, height: 40, borderRadius: '50%', border: 'none', cursor: 'pointer',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        background: 'var(--tg-theme-secondary-bg-color, #f3f4f6)',
      }}
    >
      <ArrowLeft size={19} style={{ color: 'var(--tg-theme-text-color)' }} />
    </button>
  )
}

const STATUS_ACCENT = {
  open:     '#3B82F6',
  partial:  '#F59E0B',
  overdue:  '#EF4444',
  closed:   '#22C55E',
  archived: '#9CA3AF',
}

function Skeleton() {
  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="skeleton" style={{ height: 140 }} />
      <div className="skeleton" style={{ height: 140 }} />
      <div className="skeleton" style={{ height: 110 }} />
      <div className="skeleton" style={{ height: 110 }} />
    </div>
  )
}

export default function DebtorShopDetail() {
  const { shopId }        = useParams()
  const navigate          = useNavigate()
  const [data, setData]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [expanded, setExpanded] = useState(null)

  useEffect(() => {
    tma.backButton.show(() => navigate('/debtor'))
    load()
    return () => tma.backButton.hide()
  }, [])

  const load = async () => {
    setLoading(true); setLoadError('')
    try {
      const res = await debtorApi.shopDetail(shopId)
      setData(res.data)
    } catch (e) {
      // Ilgari catch yo'q edi: `data` null qolib, sahifa `return null`
      // qilardi — foydalanuvchi bo'sh oq ekran ko'rardi
      setLoadError(errorMessage(e, "Do'kon ma'lumoti yuklanmadi"))
    } finally { setLoading(false) }
  }

  if (loading) return (
    <div
      className="animate-slide-up"
      style={{ minHeight: '100svh', background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)' }}
    >
      <div style={{
        background: 'var(--tg-theme-bg-color, #fff)',
        boxShadow: '0 1px 0 rgba(0,0,0,0.06)',
        padding: '16px 16px 14px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <BackBtn onClick={() => navigate('/debtor')} />
        <div className="skeleton" style={{ height: 28, width: 180 }} />
      </div>
      <Skeleton />
    </div>
  )

  if (!data) return <LoadError message={loadError || "Ma'lumot topilmadi"} onRetry={load} />

  const activeDebts = data.debts.filter(d => ['open','partial','overdue'].includes(d.status))
  const closedDebts = data.debts.filter(d => d.status === 'closed')

  const totalDebt = data.total_remaining + data.total_paid
  const paidPct   = totalDebt > 0 ? Math.round((data.total_paid / totalDebt) * 100) : 0

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
        background: 'var(--tg-theme-bg-color, #fff)',
        boxShadow: '0 1px 0 rgba(0,0,0,0.06)',
        padding: '16px 16px 14px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <BackBtn onClick={() => navigate('/debtor')} />
        <h1 className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--tg-theme-text-color)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {data.shop_name}
        </h1>
      </div>

      <div style={{ padding: '16px 16px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>

        {/* Summary card */}
        <div className="card animate-rise">
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 16 }}>
            <div style={{ textAlign: 'center' }}>
              <p className="money" style={{ fontWeight: 700, fontSize: 16, color: '#EF4444', margin: 0, lineHeight: 1 }}>
                {fmt.money(data.total_remaining)}
              </p>
              <p className="section-title" style={{ marginTop: 5 }}>Qoldi</p>
            </div>
            <div style={{ textAlign: 'center' }}>
              <p className="money" style={{ fontWeight: 700, fontSize: 16, color: '#16A34A', margin: 0, lineHeight: 1 }}>
                {fmt.money(data.total_paid)}
              </p>
              <p className="section-title" style={{ marginTop: 5 }}>To'landi</p>
            </div>
            <div style={{ textAlign: 'center' }}>
              <p className="money" style={{ fontWeight: 700, fontSize: 16, color: 'var(--tg-theme-text-color)', margin: 0, lineHeight: 1 }}>
                {fmt.money(data.total_debt)}
              </p>
              <p className="section-title" style={{ marginTop: 5 }}>Jami</p>
            </div>
          </div>

          {/* Progress */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--tg-theme-hint-color)', marginBottom: 6 }}>
              <span>To'lov jarayoni</span>
              <span style={{ fontWeight: 700 }}>{paidPct}%</span>
            </div>
            <div style={{
              height: 10, borderRadius: 99, overflow: 'hidden',
              background: 'var(--tg-theme-secondary-bg-color)',
            }}>
              <div style={{
                height: '100%', borderRadius: 99,
                width: `${paidPct}%`,
                background: 'linear-gradient(90deg, #34D399, #059669)',
                transition: 'width 0.7s ease',
              }} />
            </div>
          </div>
        </div>

        {/* Chart */}
        {data.monthly?.some(m => m.amount > 0) && (
          <div className="card">
            <p className="section-title" style={{ marginBottom: 14 }}>So'nggi 6 oy</p>
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={data.monthly} margin={{ left: -28, right: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} hide />
                <Tooltip
                  formatter={(val) => [fmt.money(val), 'Qarz']}
                  contentStyle={{
                    fontSize: 12, borderRadius: 12, border: 'none',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                    background: 'var(--tg-theme-bg-color, #fff)',
                  }}
                />
                <Bar dataKey="amount" fill="#8B5CF6" radius={[6,6,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Active debts */}
        {activeDebts.length > 0 && (
          <div>
            <p className="section-title" style={{ marginBottom: 8, marginLeft: 4 }}>
              Faol qarzlar ({activeDebts.length})
            </p>
            <div className={activeDebts.length < 15 ? 'row-stagger' : ''} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {activeDebts.map(d => (
                <div key={d.id} className="card" style={{ overflow: 'hidden', padding: 0, display: 'flex' }}>
                  <div style={{ width: 4, flexShrink: 0, background: STATUS_ACCENT[d.status] || '#9CA3AF' }} />
                  <div style={{ flex: 1, padding: 14 }}>
                    <div
                      style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', cursor: 'pointer' }}
                      onClick={() => setExpanded(expanded === d.id ? null : d.id)}
                    >
                      <div style={{ flex: 1, minWidth: 0, paddingRight: 8 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                          <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: 'var(--tg-theme-hint-color)' }}>
                            #{d.debt_number}
                          </span>
                          <span className={statusBadge(d.status)}>
                            {statusEmoji(d.status)} {statusLabel(d.status)}
                          </span>
                        </div>
                        <p className="money" style={{ fontWeight: 700, fontSize: 16, color: '#EF4444', margin: 0 }}>
                          {fmt.money(d.remaining)} qoldi
                        </p>
                        <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '3px 0 0' }}>
                          {fmt.date(d.due_date)} gacha
                        </p>
                        {d.note && (
                          <p style={{
                            fontSize: 12, fontStyle: 'italic',
                            padding: '6px 10px', borderRadius: 10,
                            color: 'var(--tg-theme-hint-color)',
                            background: 'var(--tg-theme-secondary-bg-color)',
                            margin: '8px 0 0',
                          }}>
                            "{d.note}"
                          </p>
                        )}
                      </div>
                      {expanded === d.id
                        ? <ChevronUp size={16} style={{ color: 'var(--tg-theme-hint-color)', flexShrink: 0 }} />
                        : <ChevronDown size={16} style={{ color: 'var(--tg-theme-hint-color)', flexShrink: 0 }} />
                      }
                    </div>

                    {expanded === d.id && d.payments.length > 0 && (
                      <div style={{
                        marginTop: 12, paddingTop: 12,
                        borderTop: '0.5px solid var(--tg-theme-secondary-bg-color)',
                        display: 'flex', flexDirection: 'column', gap: 8,
                      }}>
                        <p className="section-title">To'lovlar</p>
                        {d.payments.map((p, i) => (
                          <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>{fmt.dateShort(p.created_at)}</span>
                            <span className="money" style={{ fontSize: 13, fontWeight: 700, color: '#16A34A' }}>+{fmt.money(p.amount)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Closed debts */}
        {closedDebts.length > 0 && (
          <div>
            <p className="section-title" style={{ marginBottom: 8, marginLeft: 4 }}>
              Yopiq ({closedDebts.length})
            </p>
            <div className="card" style={{ padding: 0, overflow: 'hidden', opacity: 0.65 }}>
              {closedDebts.map(d => (
                <div key={d.id} className="list-item">
                  <span style={{ fontSize: 13, fontFamily: 'monospace', flex: 1, color: 'var(--tg-theme-hint-color)' }}>
                    #{d.debt_number}
                  </span>
                  <span className="money" style={{ fontWeight: 700, fontSize: 13, color: '#16A34A' }}>✅ {fmt.money(d.amount)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

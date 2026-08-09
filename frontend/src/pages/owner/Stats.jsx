import { useState, useEffect } from 'react'
import {
  AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import { ownerApi, errorMessage } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { tma } from '../../lib/tma'
import { useTimedState } from '../../hooks/useTimedState'
import { fmt } from '../../lib/utils'
import Money from '../../components/ui/Money'

function Skeleton() {
  return (
    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div className="skeleton" style={{ height: 120 }} />
      <div className="skeleton" style={{ height: 90 }} />
      <div className="skeleton" style={{ height: 200 }} />
      <div className="skeleton" style={{ height: 140 }} />
    </div>
  )
}

const Row = ({ label, val, color }) => (
  <div style={{
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '12px 0',
    borderBottom: '0.5px solid var(--tg-theme-secondary-bg-color)',
  }}>
    <span style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>{label}</span>
    <span className="money" style={{ fontWeight: 700, fontSize: 13, color: color || 'var(--tg-theme-text-color)' }}>
      {val}
    </span>
  </div>
)

export default function Stats() {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const { currentShopId }     = useAuth()

  useEffect(() => { if (currentShopId) load() }, [currentShopId])

  const load = async () => {
    setLoading(true)
    try {
      const res = await ownerApi.stats(currentShopId)
      setData(res.data)
    } finally { setLoading(false) }
  }

  // Excel hisobot — fayl Telegram chatiga hujjat sifatida keladi
  const [exporting, setExporting] = useState(false)
  const [exportMsg, setExportMsg] = useTimedState('', 5000)

  const exportExcel = async () => {
    setExporting(true); setExportMsg('')
    tma.haptic('light')
    try {
      const res = await ownerApi.exportReport(currentShopId)
      setExportMsg(`✅ Hisobot Telegram'ga yuborildi (${res.data.debts} ta qarz)`)
      tma.haptic('success')
    } catch (e) {
      setExportMsg('❌ ' + errorMessage(e, 'Hisobot yuborilmadi'))
      tma.haptic('error')
    } finally { setExporting(false) }
  }

  return (
    <div
      className="animate-slide-up"
      style={{
        minHeight: '100svh',
        paddingBottom: 96,
        background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)',
      }}
    >
      {/* Header */}
      <div style={{
        background: 'var(--tg-theme-bg-color, #fff)',
        boxShadow: '0 1px 0 rgba(0,0,0,0.06)',
        padding: '16px 16px 14px',
      }}>
        <h1 className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--tg-theme-text-color)', margin: 0 }}>
          Statistika
        </h1>
      </div>

      {loading ? <Skeleton /> : (
        <div style={{ padding: '16px 16px 0', display: 'flex', flexDirection: 'column', gap: 12 }}>

          {/* Hero — gradient */}
          <div className="card-hero animate-rise">
            <p style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.09em', opacity: 0.78, marginBottom: 8, position: 'relative' }}>
              Umumiy qoldiq
            </p>
            <Money
              value={data?.total_remaining}
              className="font-display"
              style={{ display: 'block', fontSize: 36, fontWeight: 800, lineHeight: 1, margin: '0 0 16px', position: 'relative' }}
            />
            <div style={{ position: 'relative', display: 'flex', gap: 24 }}>
              <div>
                <p style={{ fontSize: 11, opacity: 0.65, margin: '0 0 2px' }}>Yig'ilgan</p>
                <p className="money" style={{ fontSize: 15, fontWeight: 700, color: '#86efac', margin: 0 }}>
                  {fmt.money(data?.total_collected)}
                </p>
              </div>
              <div>
                <p style={{ fontSize: 11, opacity: 0.65, margin: '0 0 2px' }}>Muddati o'tgan</p>
                <p className="money" style={{ fontSize: 15, fontWeight: 700, color: '#fca5a5', margin: 0 }}>
                  {fmt.money(data?.overdue_remaining)}
                </p>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          {(data?.active_remaining > 0 || data?.overdue_remaining > 0) && (
            <div className="card">
              <p className="section-title" style={{ marginBottom: 14 }}>Holat taqsimoti</p>
              {(() => {
                const a = data.active_remaining || 0
                const o = data.overdue_remaining || 0
                const sum = a + o || 1
                const aPct = Math.round((a / sum) * 100)
                const oPct = 100 - aPct
                return (
                  <>
                    <div style={{
                      display: 'flex', height: 10, borderRadius: 99, overflow: 'hidden',
                      background: 'var(--tg-theme-secondary-bg-color)', marginBottom: 12,
                    }}>
                      {aPct > 0 && <div style={{ width: `${aPct}%`, background: 'linear-gradient(90deg, #34D399, #059669)' }} />}
                      {oPct > 0 && <div style={{ width: `${oPct}%`, background: 'linear-gradient(90deg, #F87171, #DC2626)' }} />}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e', flexShrink: 0, display: 'inline-block' }} />
                        <span style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)' }}>
                          Muddatida —{' '}
                          <span style={{ fontWeight: 700, color: 'var(--tg-theme-text-color)' }}>{aPct}%</span>
                        </span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#ef4444', flexShrink: 0, display: 'inline-block' }} />
                        <span style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)' }}>
                          O'tgan —{' '}
                          <span style={{ fontWeight: 700, color: 'var(--tg-theme-text-color)' }}>{oPct}%</span>
                        </span>
                      </div>
                    </div>
                  </>
                )
              })()}
            </div>
          )}

          {/* Summary numbers */}
          <div className="card">
            <p className="section-title" style={{ marginBottom: 4 }}>Umumiy raqamlar</p>
            <Row label="Mijozlar"       val={data?.clients} />
            <Row label="Faol qarzlar"   val={data?.active_debts} />
            <Row label="Muddati o'tgan" val={data?.overdue_debts}
              color={data?.overdue_debts > 0 ? '#ef4444' : undefined} />
            <Row label="Yopiq qarzlar"  val={data?.closed_debts} color="#22c55e" />
            <Row label="Jami yig'ilgan" val={fmt.money(data?.total_collected)} color="#22c55e" />
          </div>

          {/* Monthly chart */}
          <div className="card">
            <p className="section-title" style={{ marginBottom: 16 }}>So'nggi 6 oy — qarzlar</p>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={data?.monthly || []} margin={{ left: -24, right: 4 }}>
                <defs>
                  <linearGradient id="blueGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#3B82F6" stopOpacity={0.22} />
                    <stop offset="95%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.05)" />
                <XAxis dataKey="month" tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                <Tooltip
                  formatter={(val) => [val + ' ta', 'Qarzlar']}
                  contentStyle={{
                    fontSize: 12, borderRadius: 12, border: 'none',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                    background: 'var(--tg-theme-bg-color, #fff)',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#3B82F6"
                  strokeWidth={2.5}
                  fill="url(#blueGrad)"
                  dot={false}
                  activeDot={{ r: 5, strokeWidth: 0, fill: '#3B82F6' }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Monthly collected */}
          {(data?.monthly || []).some(m => m.collected > 0) && (
            <div className="card">
              <p className="section-title" style={{ marginBottom: 4 }}>Oylik yig'ilgan</p>
              {(data?.monthly || []).map(m => (
                <div key={m.month} style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  padding: '10px 0',
                  borderBottom: '0.5px solid var(--tg-theme-secondary-bg-color)',
                }}>
                  <span style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)' }}>{m.month}</span>
                  <span className="money" style={{ fontWeight: 700, fontSize: 13, color: '#16A34A' }}>{fmt.money(m.collected)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Excel hisobot */}
          <div className="card">
            <p className="section-title" style={{ marginBottom: 4 }}>Hisobot</p>
            <p style={{ fontSize: 13, lineHeight: 1.5, color: 'var(--tg-theme-hint-color)', margin: '0 0 12px' }}>
              Qarzdorlar va qarzlar ro'yxati Excel fayl ko'rinishida Telegram chatingizga yuboriladi.
            </p>
            {exportMsg && (
              <p style={{ fontSize: 13, margin: '0 0 10px', color: 'var(--tg-theme-text-color)' }}>{exportMsg}</p>
            )}
            <button
              onClick={exportExcel}
              disabled={exporting || !currentShopId}
              style={{
                width: '100%', padding: '13px 16px', borderRadius: 14, border: 'none',
                fontSize: 15, fontWeight: 600, cursor: 'pointer',
                background: exporting ? '#9CA3AF' : 'var(--tg-theme-button-color, #2563eb)',
                color: 'var(--tg-theme-button-text-color, #fff)',
              }}
            >
              {exporting ? 'Tayyorlanmoqda…' : '📊 Excel hisobotni olish'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useParams, useNavigate } from 'react-router-dom'
import { tma } from '../../lib/tma'
import { ownerApi, errorMessage } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { useTimedState } from '../../hooks/useTimedState'
import { fmt, statusBadge, statusLabel, statusEmoji } from '../../lib/utils'
import Sheet from '../../components/ui/Sheet'
import ConfirmStamp from '../../components/ui/ConfirmStamp'
import { Plus, CreditCard, Trash2, CheckCheck, Phone, ArrowLeft, ArrowDownLeft, ArrowUpRight, BellRing } from 'lucide-react'

const STATUS_GRADIENT = {
  open:     'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
  partial:  'linear-gradient(135deg, #FBBF24 0%, #D97706 100%)',
  overdue:  'linear-gradient(135deg, #F87171 0%, #DC2626 100%)',
  closed:   'linear-gradient(135deg, #34D399 0%, #059669 100%)',
  archived: 'linear-gradient(135deg, #9CA3AF 0%, #6B7280 100%)',
}

const STATUS_ACCENT = {
  open:     '#3B82F6',
  partial:  '#F59E0B',
  overdue:  '#EF4444',
  closed:   '#22C55E',
  archived: '#9CA3AF',
}

export default function ClientDetail() {
  const { id }            = useParams()
  const navigate          = useNavigate()
  const { currentShopId } = useAuth()

  const [client, setClient]     = useState(null)
  const [loading, setLoading]   = useState(true)
  const [debtSheet, setDebtSheet]       = useState(false)
  const [paySheet, setPaySheet]         = useState(false)
  const [clearConfirm, setClearConfirm] = useState(false)
  const [showClosed, setShowClosed]     = useState(false)
  const [expandedDebt, setExpandedDebt] = useState(null)
  const [tab, setTab]                   = useState('all') // 'all' | 'debts' | 'payments'

  const [debtForm, setDebtForm] = useState({ amount: '', due_date: '', note: '' })
  const [payAmount, setPayAmount] = useState('')
  const [saving, setSaving]     = useState(false)
  const [reminding, setReminding] = useState(false)
  const [toast, setToast]       = useTimedState('')
  const [warning, setWarning]   = useTimedState('')
  const [stamp, setStamp]       = useState(null)   // { label } — "TASDIQLANDI" muhri

  const showStamp = (label) => {
    setStamp({ label })
    setTimeout(() => setStamp(null), 1700)
  }

  useEffect(() => {
    tma.backButton.show(() => navigate('/clients'))
    load()
    return () => tma.backButton.hide()
  }, [])

  const load = async () => {
    setLoading(true)
    try {
      const res = await ownerApi.getClient(currentShopId, id)
      setClient(res.data)
    } finally { setLoading(false) }
  }

  const addDebt = async () => {
    if (!debtForm.amount) return
    setSaving(true); setWarning('')
    try {
      const res = await ownerApi.addDebt(currentShopId, {
        client_id: id,
        amount:    parseInt(debtForm.amount),
        due_date:  debtForm.due_date || null,
        note:      debtForm.note || null,
      })
      if (res.data.warning) setWarning(res.data.warning)
      tma.haptic('medium')
      setDebtSheet(false)
      setDebtForm({ amount: '', due_date: '', note: '' })
      await load()
    } catch (e) {
      setWarning(e.response?.data?.detail || 'Xato')
    } finally { setSaving(false) }
  }

  const addPayment = async () => {
    if (!payAmount) return
    setSaving(true)
    try {
      await ownerApi.payTotal(currentShopId, {
        client_id: id,
        amount:    parseInt(payAmount),
      })
      tma.haptic('success')
      setPaySheet(false)
      setPayAmount('')
      await load()
      showStamp("TO'LANDI")
    } catch (e) {
      alert(e.response?.data?.detail || 'Xato')
    } finally { setSaving(false) }
  }

  const clearAllDebts = async () => {
    setSaving(true)
    try {
      await ownerApi.clearDebts(currentShopId, id)
      tma.haptic('success')
      setClearConfirm(false)
      await load()
      showStamp('QARZ YOPILDI')
    } catch (e) {
      alert(e.response?.data?.detail || 'Xato')
    } finally { setSaving(false) }
  }

  // Qo'lda eslatma. Avtomatik eslatma har kuni ketadi; bu tugma
  // "hoziroq eslat" uchun. Server tomonda kulish oralig'i (cooldown) bor.
  const sendReminder = async () => {
    setReminding(true)
    try {
      await ownerApi.remind(currentShopId, id)
      tma.haptic('success')
      setToast('Eslatma yuborildi')
      await load()
    } catch (e) {
      tma.haptic('error')
      setToast(errorMessage(e, 'Eslatma yuborilmadi'))
    } finally { setReminding(false) }
  }

  const archiveClient = async () => {
    if (!confirm(`${client.full_name} ni o'chirasizmi?`)) return
    await ownerApi.delClient(currentShopId, id)
    navigate('/clients')
  }

  if (loading || !client) {
    return (
      <div className="animate-slide-up" style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="skeleton" style={{ height: 140 }} />
        <div style={{ display: 'flex', gap: 10 }}>
          <div className="skeleton" style={{ height: 52, flex: 1 }} />
          <div className="skeleton" style={{ height: 52, flex: 1 }} />
        </div>
        <div className="skeleton" style={{ height: 120 }} />
        <div className="skeleton" style={{ height: 120 }} />
      </div>
    )
  }

  // To'langan (yopiq) qarzlar do'kon egasiga ko'rinmaydi — faqat faol qarzlar
  const activeDebts = client.debts.filter(d => ['open', 'partial', 'overdue'].includes(d.status))
  const hasOverdue  = activeDebts.some(d => d.status === 'overdue')

  // Hodisalar lentasi: qarz oldi (+) va to'lov (−), vaqt bo'yicha ketma-ket
  const debtEvents = activeDebts.map(d => ({ kind: 'debt', amount: d.amount, date: d.created_at, due: d.due_date, note: d.note }))
  const payEvents  = (client.payments || []).map(p => ({ kind: 'pay', amount: p.amount, date: p.created_at }))
  const sortAsc    = (a, b) => new Date(a.date) - new Date(b.date)
  const allEvents  = [...debtEvents, ...payEvents].sort(sortAsc)

  const renderEvent = (ev, i) => {
    const isDebt = ev.kind === 'debt'
    return (
      <div key={i} className="card" style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px' }}>
        <div style={{
          width: 38, height: 38, borderRadius: 12, flexShrink: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: isDebt ? '#fee2e2' : '#dcfce7',
        }}>
          {isDebt ? <ArrowDownLeft size={17} style={{ color: '#DC2626' }} /> : <ArrowUpRight size={17} style={{ color: '#16A34A' }} />}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontWeight: 700, fontSize: 14, color: 'var(--tg-theme-text-color)', margin: 0 }}>
            {isDebt ? 'Qarz oldi' : "To'lov berdi"}
          </p>
          <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '2px 0 0' }}>
            {fmt.date(ev.date)} · {fmt.time(ev.date)}{isDebt && ev.due ? ` · muddat ${fmt.date(ev.due)}` : ''}
          </p>
          {isDebt && ev.note && (
            <p style={{ fontSize: 12, fontStyle: 'italic', color: 'var(--tg-theme-hint-color)', margin: '4px 0 0' }}>"{ev.note}"</p>
          )}
        </div>
        <span className="money" style={{ fontWeight: 800, fontSize: 15, color: isDebt ? '#DC2626' : '#16A34A', flexShrink: 0 }}>
          {isDebt ? '+' : '−'}{fmt.money(ev.amount)}
        </span>
      </div>
    )
  }

  return (
    <div
      className="animate-slide-up"
      style={{
        minHeight: '100svh',
        paddingBottom: 112,
        background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)',
      }}
    >
      {/* Orqaga */}
      <div style={{ padding: '14px 16px 0' }}>
        <button
          onClick={() => navigate('/clients')}
          aria-label="Orqaga"
          className="tappable"
          style={{
            width: 40, height: 40, borderRadius: '50%', border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--tg-theme-bg-color, #fff)',
            boxShadow: '0 2px 10px rgba(17,24,39,0.08)',
          }}
        >
          <ArrowLeft size={19} style={{ color: 'var(--tg-theme-text-color)' }} />
        </button>
      </div>

      {/* Client header */}
      <div style={{ padding: '12px 16px 12px' }}>
        <div className="card animate-rise">
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 20, flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 800, fontSize: 22, color: '#fff',
              background: 'linear-gradient(135deg, #2678b6 0%, #7c3aed 100%)',
              boxShadow: '0 6px 20px rgba(38,120,182,0.35)',
            }}>
              {client.full_name[0]?.toUpperCase()}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h1 className="font-display" style={{ fontWeight: 700, fontSize: 18, letterSpacing: '-0.01em', color: 'var(--tg-theme-text-color)', margin: '0 0 4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {client.full_name}
              </h1>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <Phone size={12} style={{ color: 'var(--tg-theme-hint-color)' }} />
                <p style={{ fontSize: 13, color: 'var(--tg-theme-hint-color)', margin: 0 }}>{client.phone}</p>
              </div>
            </div>
          </div>

          {/* 3-col stats */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
            <div className="card-sec" style={{ borderRadius: 14, padding: '10px 8px', textAlign: 'center' }}>
              <p className="money" style={{ fontWeight: 700, fontSize: 18, color: 'var(--tg-theme-text-color)', margin: 0, lineHeight: 1 }}>
                {activeDebts.length}
              </p>
              <p className="section-title" style={{ marginTop: 4 }}>Qarz</p>
            </div>
            <div className="card-sec" style={{ borderRadius: 14, padding: '10px 8px', textAlign: 'center' }}>
              <p className="money" style={{ fontWeight: 700, fontSize: 13, margin: 0, lineHeight: 1.2, color: client.total_remaining > 0 ? '#EF4444' : '#16A34A' }}>
                {fmt.money(client.total_remaining)}
              </p>
              <p className="section-title" style={{ marginTop: 4 }}>Qoldi</p>
            </div>
            <div className="card-sec" style={{ borderRadius: 14, padding: '10px 8px', textAlign: 'center' }}>
              <p className="money" style={{ fontWeight: 700, fontSize: 13, margin: 0, lineHeight: 1.2, color: '#16A34A' }}>
                {fmt.money(client.total_paid)}
              </p>
              <p className="section-title" style={{ marginTop: 4 }}>To'landi</p>
            </div>
          </div>

          {client.debt_limit && (
            <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '10px 0 0' }}>
              Limit: {fmt.money(client.debt_limit)}
            </p>
          )}
        </div>
      </div>

      {/* Action buttons */}
      <div style={{ padding: '0 16px 10px', display: 'flex', gap: 10 }}>
        <button
          onClick={() => setDebtSheet(true)}
          className="btn-primary"
          style={{ flex: 1 }}
        >
          <Plus size={16} /> Qarz qo'shish
        </button>
        {activeDebts.length > 0 && (
          <button
            onClick={() => setPaySheet(true)}
            className="btn-success"
            style={{ flex: 1 }}
          >
            <CreditCard size={16} /> To'lov
          </button>
        )}
      </div>

      {activeDebts.length > 0 && (
        <div style={{ padding: '0 16px 10px', display: 'flex', gap: 10 }}>
          <button
            onClick={sendReminder}
            disabled={reminding}
            style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              padding: '10px 12px', borderRadius: 16, fontSize: 13, fontWeight: 700,
              border: 'none', cursor: reminding ? 'default' : 'pointer',
              background: hasOverdue ? '#fee2e2' : '#fef3c7',
              color: hasOverdue ? '#b91c1c' : '#92400e',
              opacity: reminding ? 0.6 : 1,
            }}
          >
            <BellRing size={15} /> {reminding ? 'Yuborilmoqda…' : 'Eslatma yuborish'}
          </button>
          <button
            onClick={() => setClearConfirm(true)}
            style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
              padding: '10px 12px', borderRadius: 16, fontSize: 13, fontWeight: 700,
              border: 'none', cursor: 'pointer',
              background: '#dcfce7', color: '#15803d',
            }}
          >
            <CheckCheck size={15} /> Qarzni yopish
          </button>
        </div>
      )}

      {toast && (
        <div style={{ padding: '0 16px 10px' }}>
          <div style={{
            fontSize: 13, lineHeight: 1.45, padding: '10px 14px', borderRadius: 12,
            background: 'var(--tg-theme-secondary-bg-color)',
            color: 'var(--tg-theme-text-color)',
          }}>
            {toast}
          </div>
        </div>
      )}

      {/* Filtr + ro'yxat */}
      <div style={{ padding: '0 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Segmented filtr: Olingan qarz / To'langan pul */}
        <div style={{ display: 'flex', gap: 4, padding: 4, borderRadius: 14, background: 'var(--tg-theme-secondary-bg-color)' }}>
          {[['all', 'Hammasi', '#2563EB'], ['debts', 'Olingan qarz', '#DC2626'], ['payments', "To'langan pul", '#16A34A']].map(([k, label, c]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              style={{
                flex: 1, padding: '9px 6px', borderRadius: 10, fontSize: 12.5, fontWeight: 700,
                border: 'none', cursor: 'pointer', transition: 'all 0.2s cubic-bezier(0.22,1,0.36,1)',
                background: tab === k ? 'var(--tg-theme-bg-color, #fff)' : 'transparent',
                color: tab === k ? c : 'var(--tg-theme-hint-color)',
                boxShadow: tab === k ? '0 2px 8px rgba(17,24,39,0.10)' : 'none',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {(() => {
          const list = tab === 'debts' ? debtEvents : tab === 'payments' ? payEvents : allEvents
          if (list.length === 0) {
            return (
              <div className="card" style={{ textAlign: 'center', padding: '36px 16px' }}>
                <p style={{ fontSize: 34, marginBottom: 8 }}>{tab === 'payments' ? '💳' : '✅'}</p>
                <p style={{ color: 'var(--tg-theme-hint-color)', margin: 0 }}>
                  {tab === 'payments' ? "Hali to'lov yo'q" : tab === 'debts' ? "Faol qarz yo'q" : "Hozircha yozuv yo'q"}
                </p>
              </div>
            )
          }
          return (
            <div className={list.length < 15 ? 'row-stagger' : ''} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {list.map(renderEvent)}
            </div>
          )
        })()}

        <button onClick={archiveClient} className="btn-ghost" style={{ marginTop: 8 }}>
          <Trash2 size={15} style={{ color: '#ef4444' }} />
          <span style={{ color: '#ef4444' }}>Mijozni o'chirish</span>
        </button>
      </div>

      {/* Add Debt Sheet */}
      <Sheet open={debtSheet} onClose={() => setDebtSheet(false)} title="Yangi qarz">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 8 }}>
          {warning && (
            <div style={{ fontSize: 13, color: '#92400e', background: '#fffbeb', padding: '10px 14px', borderRadius: 12 }}>
              ⚠️ {warning}
            </div>
          )}
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Miqdor (so'm) *</label>
            <input type="number" className="input" placeholder="500 000"
              value={debtForm.amount} onChange={e => setDebtForm(s => ({ ...s, amount: e.target.value }))} autoFocus />
          </div>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Qaytarish sanasi</label>
            <input type="date" className="input"
              value={debtForm.due_date} onChange={e => setDebtForm(s => ({ ...s, due_date: e.target.value }))} />
          </div>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Izoh</label>
            <textarea className="input" style={{ resize: 'none', height: 80 }}
              placeholder="Ixtiyoriy…" maxLength={200}
              value={debtForm.note} onChange={e => setDebtForm(s => ({ ...s, note: e.target.value }))} />
          </div>
          <button onClick={addDebt} disabled={saving} className="btn-primary">
            {saving ? 'Saqlanmoqda…' : "Qarz qo'shish"}
          </button>
        </div>
      </Sheet>

      {/* Payment Sheet — umumiy qoldiqdan ayiriladi */}
      <Sheet open={paySheet} onClose={() => setPaySheet(false)} title="To'lov qabul qilish">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 8 }}>
          <div style={{ padding: '14px 16px', borderRadius: 16, background: 'var(--tg-theme-secondary-bg-color)' }}>
            <p className="section-title" style={{ marginBottom: 4 }}>Umumiy qoldiq</p>
            <p className="money" style={{ fontSize: 24, fontWeight: 800, color: '#EF4444', margin: 0 }}>
              {fmt.money(client.total_remaining)}
            </p>
          </div>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>To'lov miqdori *</label>
            <input type="number" className="input" placeholder="0" autoFocus
              value={payAmount} onChange={e => setPayAmount(e.target.value)} />
            {parseInt(payAmount) > client.total_remaining ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 8, padding: '10px 12px', borderRadius: 12, background: '#fffbeb', border: '1px solid #fef3c7' }}>
                <span style={{ fontSize: 12, color: '#92400e', lineHeight: 1.4 }}>
                  ⚠️ Miqdor umumiy qoldiqdan ko'p! Faqat {fmt.money(client.total_remaining)} qabul qilinadi.
                </span>
              </div>
            ) : (
              <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '8px 2px 0', lineHeight: 1.5 }}>
                To'lov umumiy qoldiqdan ayiriladi — eng eski qarzdan boshlab avtomatik taqsimlanadi.
              </p>
            )}
          </div>
          <button
            onClick={addPayment}
            disabled={saving || !payAmount || parseInt(payAmount) > client.total_remaining}
            className="btn-success"
          >
            {saving ? 'Saqlanmoqda…' : "To'lov qabul qilish"}
          </button>
        </div>
      </Sheet>

      {/* Clear all confirm */}
      <Sheet open={clearConfirm} onClose={() => setClearConfirm(false)} title="Umumiy qarzni yopish">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 8 }}>
          <p style={{ fontSize: 14, color: 'var(--tg-theme-text-color)', margin: 0 }}>
            <b>{client.full_name}</b>ning barcha faol qarzlari ({fmt.money(client.total_remaining)})
            to'liq to'langan deb belgilanadi.
          </p>
          <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: 0 }}>
            Har bir qarz uchun to'lov yozuvi saqlanadi, hech narsa o'chirilmaydi.
          </p>
          <button onClick={clearAllDebts} disabled={saving} className="btn-success">
            {saving ? 'Saqlanmoqda…' : 'Tasdiqlash'}
          </button>
        </div>
      </Sheet>

      {/* "TASDIQLANDI" muhri — to'lov / qarz yopilgan lahza */}
      {stamp && createPortal(
        <div
          className="animate-fade-in"
          onClick={() => setStamp(null)}
          style={{
            position: 'fixed', inset: 0, zIndex: 10000,
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            gap: 18, background: 'rgba(15,23,42,0.45)', backdropFilter: 'blur(3px)',
            WebkitBackdropFilter: 'blur(3px)',
          }}
        >
          <div style={{
            width: 168, height: 168, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--tg-theme-bg-color, #fff)',
            boxShadow: '0 20px 60px rgba(22,163,74,0.35)',
          }}>
            <ConfirmStamp label={stamp.label} size={132} />
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

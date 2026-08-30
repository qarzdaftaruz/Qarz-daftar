import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Plus, CreditCard, X } from 'lucide-react'
import { ownerApi, errorMessage } from '../../lib/api'
import { useAuth } from '../../hooks/useAuth'
import { useTimedState } from '../../hooks/useTimedState'
import { tma } from '../../lib/tma'
import { fmt } from '../../lib/utils'
import Sheet from '../../components/ui/Sheet'
import LoadError from '../../components/ui/LoadError'

const LIMIT = 20
const FILTERS = [
  { key: 'all',     label: 'Barchasi' },
  { key: 'overdue', label: "Muddati o'tgan" },
  { key: 'no_debt', label: "Qarzi yo'q" },
]

function getAvatarGradient(name, hasOverdue) {
  if (hasOverdue) return 'linear-gradient(135deg, #F87171 0%, #DC2626 100%)'
  const colors = [
    'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
    'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)',
    'linear-gradient(135deg, #34D399 0%, #059669 100%)',
    'linear-gradient(135deg, #FBBF24 0%, #D97706 100%)',
    'linear-gradient(135deg, #F472B6 0%, #DB2777 100%)',
  ]
  const code = name?.charCodeAt(0) ?? 0
  return colors[code % colors.length]
}

export default function Clients() {
  const navigate = useNavigate()
  const { currentShopId } = useAuth()

  const [clients, setClients]         = useState([])
  const [total, setTotal]             = useState(0)
  const [search, setSearch]           = useState('')
  const [filter, setFilter]           = useState('all')
  const [loading, setLoading]         = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [loadError, setLoadError]     = useState('')
  const [hasMore, setHasMore]         = useState(true)

  const skipRef     = useRef(0)
  const sentinelRef = useRef(null)

  const [quick, setQuick]               = useState(null)
  const [quickAmount, setQuickAmount]   = useState('')
  const [quickDueDate, setQuickDueDate] = useState('')
  const [quickNote, setQuickNote]       = useState('')
  const [quickSaving, setQuickSaving]   = useState(false)
  const [quickError, setQuickError]     = useTimedState('')

  const [addOpen, setAddOpen]     = useState(false)
  const [addForm, setAddForm]     = useState({ full_name: '', phone: '', initial_amount: '', initial_due_date: '', initial_note: '' })
  const [addSaving, setAddSaving] = useState(false)
  const [addError, setAddError]   = useTimedState('')

  const load = useCallback(async (reset = false) => {
    if (!currentShopId) return
    const skip = reset ? 0 : skipRef.current
    if (reset) { setLoading(true); setLoadError('') } else setLoadingMore(true)
    try {
      const res = await ownerApi.clients(currentShopId, {
        search: search || undefined,
        skip,
        limit: LIMIT,
        filter: filter !== 'all' ? filter : undefined,
      })
      const list = res.data.clients
      setClients(prev => reset ? list : [...prev, ...list])
      setTotal(res.data.total)
      skipRef.current = skip + list.length
      setHasMore(skip + list.length < res.data.total)
    } catch (e) {
      // Ilgari catch yo'q edi — so'rov yiqilsa ro'yxat jimgina bo'sh
      // qolib, "Hali mijozlar yo'q" degan noto'g'ri xabar chiqardi
      setLoadError(errorMessage(e, "Mijozlar ro'yxati yuklanmadi"))
    } finally {
      reset ? setLoading(false) : setLoadingMore(false)
    }
  }, [currentShopId, search, filter])

  useEffect(() => { skipRef.current = 0; load(true) }, [currentShopId, search, filter])

  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const obs = new IntersectionObserver(entries => {
      if (entries[0].isIntersecting && hasMore && !loadingMore && !loading) load(false)
    }, { rootMargin: '200px' })
    obs.observe(el)
    return () => obs.disconnect()
  }, [hasMore, loadingMore, loading, load])

  const exactMatch = clients.some(c => c.full_name.toLowerCase() === search.trim().toLowerCase())
  const showAddSuggestion = search.trim().length > 1 && !exactMatch

  const openQuick = async (client, type) => {
    tma.haptic('light')
    setQuickError(''); setQuickAmount(''); setQuickDueDate(''); setQuickNote('')
    setQuick({ client, type, loading: true })
    try {
      const res = await ownerApi.getClient(currentShopId, client.id)
      const activeDebts = res.data.debts.filter(d => ['open', 'partial', 'overdue'].includes(d.status))
      setQuick({ client, type, loading: false, debts: activeDebts, totalRemaining: res.data.total_remaining })
    } catch {
      setQuick(null)
    }
  }

  const submitQuick = async () => {
    const amount = parseInt(quickAmount, 10)
    if (!amount || amount <= 0) { setQuickError("To'g'ri miqdor kiriting"); return }
    setQuickSaving(true); setQuickError('')
    try {
      if (quick.type === 'pay') {
        await ownerApi.payTotal(currentShopId, { client_id: quick.client.id, amount })
      } else {
        await ownerApi.addDebt(currentShopId, {
          client_id: quick.client.id,
          amount,
          due_date: quickDueDate || null,
          note:     quickNote.trim() || null,
        })
      }
      tma.haptic('success')
      setQuick(null)
      load(true)
    } catch (e) {
      setQuickError(e.response?.data?.detail || 'Xato yuz berdi')
    } finally { setQuickSaving(false) }
  }

  const openAdd = (prefillName = '') => {
    setAddForm({ full_name: prefillName, phone: '', initial_amount: '', initial_due_date: '', initial_note: '' })
    setAddError('')
    setAddOpen(true)
  }

  const submitAdd = async () => {
    if (!addForm.full_name.trim() || !addForm.phone.trim()) {
      setAddError('Ism va telefon kiritilishi shart'); return
    }
    setAddSaving(true); setAddError('')
    try {
      await ownerApi.addClient(currentShopId, {
        full_name:        addForm.full_name.trim(),
        phone:            addForm.phone.trim(),
        initial_amount:   addForm.initial_amount ? parseInt(addForm.initial_amount, 10) : undefined,
        initial_due_date: addForm.initial_due_date || undefined,
        initial_note:     addForm.initial_note.trim() || undefined,
      })
      tma.haptic('medium')
      setAddOpen(false)
      setSearch('')
      load(true)
    } catch (e) {
      setAddError(e.response?.data?.detail || 'Xato yuz berdi')
    } finally { setAddSaving(false) }
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
      {/* Sticky header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 10,
        background: 'var(--tg-theme-secondary-bg-color, #f0f2f5)',
        padding: '14px 16px 10px',
      }}>
        <h1 className="font-display" style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--tg-theme-text-color)', margin: '0 0 12px' }}>
          Mijozlar{' '}
          <span className="money" style={{ color: 'var(--tg-theme-hint-color)', fontWeight: 600 }}>({total})</span>
        </h1>

        {/* Search */}
        <div style={{ position: 'relative', marginBottom: 10 }}>
          <Search size={15} style={{
            position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)',
            color: 'var(--tg-theme-hint-color)',
          }} />
          <input
            className="input"
            style={{ paddingLeft: 38, paddingRight: 38 }}
            placeholder="Ism yoki telefon..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              style={{
                position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', cursor: 'pointer',
              }}
            >
              <X size={15} style={{ color: 'var(--tg-theme-hint-color)' }} />
            </button>
          )}
        </div>

        {/* Filter chips */}
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
          {FILTERS.map(f => (
            <button
              key={f.key}
              onClick={() => { setFilter(f.key); skipRef.current = 0 }}
              style={{
                flexShrink: 0,
                padding: '6px 14px',
                borderRadius: 99,
                fontSize: 12,
                fontWeight: 600,
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                background: filter === f.key
                  ? '#2563EB'
                  : 'var(--tg-theme-bg-color, #fff)',
                color: filter === f.key ? '#fff' : 'var(--tg-theme-hint-color)',
                boxShadow: filter === f.key ? '0 4px 12px rgba(37,99,235,0.32)' : '0 1px 3px rgba(15,23,42,0.07)',
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ padding: '4px 16px 0', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* Add suggestion */}
        {showAddSuggestion && (
          <button
            onClick={() => openAdd(search.trim())}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: 12,
              padding: '12px 16px', borderRadius: 16,
              background: 'var(--tg-theme-bg-color, #fff)',
              border: '2px dashed var(--tg-theme-button-color, #2678b6)',
              cursor: 'pointer',
            }}
          >
            <div style={{
              width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Plus size={17} style={{ color: '#fff' }} />
            </div>
            <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--tg-theme-button-color, #2678b6)', margin: 0 }}>
              "{search.trim()}" nomli mijoz qo'shish
            </p>
          </button>
        )}

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 4 }}>
            {[...Array(5)].map((_, i) => <div key={i} className="skeleton" style={{ height: 72 }} />)}
          </div>
        ) : loadError && clients.length === 0 ? (
          <LoadError message={loadError} onRetry={() => load(true)} />
        ) : clients.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '56px 0' }}>
            <p style={{ fontSize: 44, marginBottom: 8 }}>👥</p>
            <p style={{ fontSize: 14, fontWeight: 500, color: 'var(--tg-theme-hint-color)', margin: 0 }}>
              {search ? 'Mos mijoz topilmadi' : filter !== 'all' ? "Bu bo'limda mijoz yo'q" : "Hali mijozlar yo'q"}
            </p>
          </div>
        ) : (
        <div
          className={clients.length < 15 ? 'row-stagger' : ''}
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
        {clients.map(c => (
          <div
            key={c.id}
            className="card tappable"
            style={{
              display: 'flex', alignItems: 'center', gap: 12,
            }}
            onClick={() => navigate(`/clients/${c.id}`)}
          >
            {/* Avatar */}
            <div style={{
              width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontWeight: 800, fontSize: 15, color: '#fff',
              background: getAvatarGradient(c.full_name, c.has_overdue),
              boxShadow: c.has_overdue
                ? '0 3px 10px rgba(239,68,68,0.3)'
                : '0 3px 10px rgba(59,130,246,0.25)',
            }}>
              {c.full_name[0]?.toUpperCase()}
            </div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 0 }} onClick={e => e.stopPropagation()}>
              <p
                style={{ fontWeight: 700, fontSize: 14, color: 'var(--tg-theme-text-color)', margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'pointer' }}
                onClick={() => navigate(`/clients/${c.id}`)}
              >
                {c.full_name}
              </p>
              <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '2px 0 0' }}>
                {c.active_debts > 0 ? `${c.active_debts} ta faol qarz` : "Qarzi yo'q"}
              </p>
            </div>

            {/* Amount */}
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <p className="money" style={{
                fontWeight: 700, fontSize: 14, margin: 0,
                color: c.total_remaining > 0
                  ? (c.has_overdue ? '#ef4444' : 'var(--tg-theme-text-color)')
                  : '#16A34A',
              }}>
                {fmt.money(c.total_remaining)}
              </p>
            </div>

            {/* Quick actions */}
            <div style={{ display: 'flex', gap: 6, flexShrink: 0 }} onClick={e => e.stopPropagation()}>
              {c.active_debts > 0 && (
                <button
                  onClick={() => openQuick(c, 'pay')}
                  style={{
                    width: 34, height: 34, borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: '#dcfce7', border: 'none', cursor: 'pointer',
                  }}
                >
                  <CreditCard size={14} style={{ color: '#16a34a' }} />
                </button>
              )}
              <button
                onClick={() => openQuick(c, 'debt')}
                style={{
                  width: 34, height: 34, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: '#dbeafe', border: 'none', cursor: 'pointer',
                }}
              >
                <Plus size={14} style={{ color: '#2563eb' }} />
              </button>
            </div>
          </div>
        ))}
        </div>
        )}

        <div ref={sentinelRef} style={{ height: 16 }} />
        {loadingMore && (
          <p style={{ textAlign: 'center', padding: '12px 0', fontSize: 12, color: 'var(--tg-theme-hint-color)' }}>
            Yuklanmoqda…
          </p>
        )}
      </div>

      {/* FAB */}
      {!showAddSuggestion && (
        <button
          onClick={() => openAdd()}
          className="fab"
          style={{
            bottom: 88,
            right: 16,
            width: 56, height: 56,
            zIndex: 20,
            background: 'linear-gradient(135deg, #2563EB 0%, #1d4ed8 100%)',
            boxShadow: '0 8px 26px rgba(37,99,235,0.48), 0 2px 8px rgba(15,23,42,0.15)',
          }}
        >
          <Plus size={24} style={{ color: '#fff' }} />
        </button>
      )}

      {/* Quick action sheet */}
      <Sheet open={!!quick} onClose={() => setQuick(null)}
        title={quick?.type === 'pay' ? "To'lov qabul qilish" : "Qarz qo'shish"}>
        {quick?.loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, padding: '16px 0' }}>
            <div className="skeleton" style={{ height: 40 }} />
            <div className="skeleton" style={{ height: 40 }} />
          </div>
        ) : quick && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 8 }}>
            <p style={{ fontSize: 14, fontWeight: 700, color: 'var(--tg-theme-text-color)', margin: 0 }}>
              {quick.client.full_name}
            </p>

            {quick.type === 'pay' && quick.debts?.length === 0 && (
              <p style={{ fontSize: 14, textAlign: 'center', padding: '24px 0', color: 'var(--tg-theme-hint-color)' }}>
                Faol qarz yo'q
              </p>
            )}

            {quick.type === 'pay' && quick.debts?.length > 0 && (
              <>
                <div style={{ padding: '12px 14px', borderRadius: 14, background: 'var(--tg-theme-secondary-bg-color)' }}>
                  <p className="section-title" style={{ marginBottom: 3 }}>Umumiy qoldiq</p>
                  <p className="money" style={{ fontSize: 20, fontWeight: 800, color: '#EF4444', margin: 0 }}>
                    {fmt.money(quick.totalRemaining)}
                  </p>
                </div>
                <div>
                  <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>To'lov miqdori *</label>
                  <input type="number" className="input" placeholder="0"
                    value={quickAmount} onChange={e => setQuickAmount(e.target.value)} autoFocus />
                  {parseInt(quickAmount) > quick.totalRemaining ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginTop: 8, padding: '10px 12px', borderRadius: 12, background: '#fffbeb', border: '1px solid #fef3c7' }}>
                      <span style={{ fontSize: 12, color: '#92400e', lineHeight: 1.4 }}>
                        ⚠️ Miqdor umumiy qoldiqdan ko'p! ({fmt.money(quick.totalRemaining)})
                      </span>
                    </div>
                  ) : (
                    <p style={{ fontSize: 12, color: 'var(--tg-theme-hint-color)', margin: '8px 2px 0', lineHeight: 1.5 }}>
                      Umumiy qoldiqdan ayiriladi (eng eski qarzdan boshlab).
                    </p>
                  )}
                </div>
              </>
            )}

            {quick.type === 'debt' && (
              <>
                <div>
                  <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Miqdor (so'm) *</label>
                  <input type="number" className="input" placeholder="0"
                    value={quickAmount} onChange={e => setQuickAmount(e.target.value)} autoFocus />
                </div>
                <div>
                  <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Qaytarish sanasi</label>
                  <input type="date" className="input"
                    value={quickDueDate} onChange={e => setQuickDueDate(e.target.value)} />
                </div>
                <div>
                  <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Nima oldi (izoh)</label>
                  <textarea className="input" style={{ resize: 'none', height: 64 }}
                    placeholder="Masalan: un, yog', shakar…"
                    maxLength={200} value={quickNote} onChange={e => setQuickNote(e.target.value)} />
                </div>
              </>
            )}

            {quickError && <p style={{ fontSize: 13, color: '#ef4444', margin: 0 }}>{quickError}</p>}

            {(quick.type === 'debt' || (quick.type === 'pay' && quick.debts?.length > 0)) && (
              <button onClick={submitQuick}
                disabled={quickSaving || (quick.type === 'pay' && parseInt(quickAmount) > quick.totalRemaining)}
                className={quick.type === 'pay' ? 'btn-success' : 'btn-primary'}>
                {quickSaving ? 'Saqlanmoqda…' : (quick.type === 'pay' ? "To'lov qabul qilish" : "Qarz qo'shish")}
              </button>
            )}
          </div>
        )}
      </Sheet>

      {/* Yangi mijoz sheet */}
      <Sheet open={addOpen} onClose={() => setAddOpen(false)} title="Yangi mijoz">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, paddingBottom: 8 }}>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Ism *</label>
            <input className="input" value={addForm.full_name} autoFocus
              onChange={e => setAddForm(s => ({ ...s, full_name: e.target.value }))} />
          </div>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Telefon *</label>
            <input className="input" placeholder="+998901234567" value={addForm.phone}
              onChange={e => setAddForm(s => ({ ...s, phone: e.target.value }))} />
          </div>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Boshlang'ich qarz (ixtiyoriy)</label>
            <input type="number" className="input" placeholder="0" value={addForm.initial_amount}
              onChange={e => setAddForm(s => ({ ...s, initial_amount: e.target.value }))} />
          </div>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Qaytarish sanasi</label>
            <input type="date" className="input" value={addForm.initial_due_date}
              onChange={e => setAddForm(s => ({ ...s, initial_due_date: e.target.value }))} />
          </div>
          <div>
            <label className="section-title" style={{ display: 'block', marginBottom: 6 }}>Nima oldi (izoh)</label>
            <textarea className="input" style={{ resize: 'none', height: 64 }}
              placeholder="Masalan: un, yog', shakar…"
              maxLength={200} value={addForm.initial_note}
              onChange={e => setAddForm(s => ({ ...s, initial_note: e.target.value }))} />
          </div>
          {addError && <p style={{ fontSize: 13, color: '#ef4444', margin: 0 }}>{addError}</p>}
          <button onClick={submitAdd} disabled={addSaving} className="btn-primary">
            {addSaving ? 'Saqlanmoqda…' : "Qo'shish"}
          </button>
        </div>
      </Sheet>
    </div>
  )
}

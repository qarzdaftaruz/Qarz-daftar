import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import { superApi, adminExportApi, errorMessage } from '../../lib/api'
import { useTimedState } from '../../hooks/useTimedState'
import { fmt, statusBadge, statusLabel, statusEmoji } from '../../lib/utils'
import {
  Search, Store, User, ArrowLeft, Plus, CreditCard,
  Pencil, Trash2, X, AlertCircle, ChevronRight,
  ArrowDownLeft, ArrowUpRight, FileSpreadsheet,
} from 'lucide-react'

const inputCls = "w-full px-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm outline-none focus:border-blue-500 focus:bg-white transition-all"

export default function AdminSuper() {
  const [q, setQ]               = useState('')
  const [results, setResults]   = useState(null)
  const [searching, setSearching] = useState(false)

  const [shop, setShop]         = useState(null) // { id, name, clients, loading }

  const [clientId, setClientId] = useState(null)
  const [client, setClient]     = useState(null)
  const [clientLoading, setClientLoading] = useState(false)
  const [tab, setTab]           = useState('all')
  const [params]                = useSearchParams()

  const [modal, setModal]       = useState(null) // { type, debt? }
  const [form, setForm]         = useState({ amount: '', due_date: '', note: '' })
  const [saving, setSaving]     = useState(false)
  const [err, setErr]           = useTimedState('')

  // ── Debounced global search ──
  useEffect(() => {
    if (!q.trim()) { setResults(null); return }
    const t = setTimeout(async () => {
      setSearching(true)
      try { const r = await superApi.search(q.trim()); setResults(r.data) }
      catch (e) { setErr(errorMessage(e, 'Qidiruv bajarilmadi')); setResults(null) }
      finally { setSearching(false) }
    }, 350)
    return () => clearTimeout(t)
  }, [q])

  const openShop = async (s) => {
    setShop({ id: s.id, name: s.name, clients: [], loading: true })
    try {
      const r = await superApi.shopClients(s.id)
      setShop({ id: s.id, name: r.data.shop_name, clients: r.data.clients, loading: false })
    } catch (e) {
      // Ilgari catch yo'q edi — so'rov yiqilsa "yuklanmoqda" holati
      // abadiy qolib ketardi va sabab faqat konsolda ko'rinardi
      setErr(errorMessage(e, "Do'kon ochilmadi"))
      setShop(null)
    }
  }

  // Do'konlar sahifasidan "Kirish" tugmasi orqali ?shop=<id> bilan kelganda
  useEffect(() => {
    const sid = params.get('shop')
    if (sid) openShop({ id: sid, name: '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const openClient = async (cid) => {
    setClientId(cid); setClient(null); setClientLoading(true); setTab('debts')
    try { const r = await superApi.client(cid); setClient(r.data) }
    catch (e) { setErr(errorMessage(e, 'Mijoz ochilmadi')); setClientId(null) }
    finally { setClientLoading(false) }
  }
  const closeClient = () => { setClientId(null); setClient(null) }

  const reloadClient = async () => {
    try {
      if (clientId) { const r = await superApi.client(clientId); setClient(r.data) }
      if (shop) { const sr = await superApi.shopClients(shop.id); setShop(s => ({ ...s, clients: sr.data.clients })) }
    } catch (e) {
      // Amal BAJARILDI, faqat yangilash yiqildi. Buni aniq aytish shart:
      // aks holda admin eski qoldiqni ko'rib to'lovni takror kiritishi mumkin.
      setErr(errorMessage(e, "Ma'lumot yangilanmadi — sahifani yangilang"))
    }
  }

  // ── Modal (add debt / pay / edit debt) ──
  const openModal = (type, debt = null) => {
    setErr('')
    if (type === 'editDebt' && debt) {
      setForm({ amount: String(debt.amount), due_date: debt.due_date ? debt.due_date.slice(0, 10) : '', note: debt.note || '' })
    } else {
      setForm({ amount: '', due_date: '', note: '' })
    }
    setModal({ type, debt })
  }

  const submitModal = async () => {
    if (!form.amount || parseInt(form.amount) <= 0) { setErr("To'g'ri miqdor kiriting"); return }
    setSaving(true); setErr('')
    try {
      if (modal.type === 'addDebt') {
        await superApi.addDebt(clientId, { amount: parseInt(form.amount), due_date: form.due_date || null, note: form.note.trim() || null })
      } else if (modal.type === 'pay') {
        await superApi.pay(clientId, { amount: parseInt(form.amount) })
      } else if (modal.type === 'editDebt') {
        await superApi.editDebt(modal.debt.id, { amount: parseInt(form.amount), due_date: form.due_date || null, note: form.note.trim() || null })
      }
      setModal(null)
      await reloadClient()
    } catch (e) { setErr(e.response?.data?.detail || 'Xato yuz berdi') }
    finally { setSaving(false) }
  }

  const deleteDebt = async (debt) => {
    if (!confirm("Bu qarzni butunlay o'chirasizmi? (qaytarib bo'lmaydi)")) return
    setSaving(true); setErr('')
    try {
      await superApi.deleteDebt(debt.id)
      await reloadClient()
    } catch (e) {
      setErr(errorMessage(e, "Qarz o'chirilmadi"))
    } finally { setSaving(false) }
  }

  const [exporting, setExporting] = useState(false)
  const exportShop = async () => {
    if (!shop) return
    setExporting(true)
    try { await adminExportApi.shopDetail(shop.id) }
    catch (e) { alert(errorMessage(e, 'Fayl yuklab olinmadi')) }
    finally { setExporting(false) }
  }

  const activeDebts = (client?.debts || []).filter(d => ['open', 'partial', 'overdue'].includes(d.status))
  const closedDebts = (client?.debts || []).filter(d => ['closed', 'archived'].includes(d.status))

  return (
    <div className="p-6 lg:p-8 animate-fade-in">
      {err && !modal && (
        <div className="mb-4 flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3">
          <AlertCircle size={18} className="text-rose-600 shrink-0 mt-0.5" />
          <p className="text-sm text-rose-800 flex-1">{err}</p>
          <button onClick={() => setErr('')} className="text-rose-400 hover:text-rose-600"><X size={16} /></button>
        </div>
      )}
      {/* Header */}
      {shop ? (
        <div className="flex items-center gap-3 mb-5">
          <button onClick={() => setShop(null)} className="w-10 h-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center hover:bg-slate-50 transition-colors active:scale-95">
            <ArrowLeft size={18} className="text-slate-700" />
          </button>
          <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight flex-1 min-w-0 truncate">{shop.name}</h1>
          <button
            onClick={exportShop} disabled={exporting}
            title="Do'kon hisobotini Excel qilib yuklab olish"
            className="px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium
                       text-emerald-700 hover:bg-emerald-50 hover:border-emerald-200 disabled:opacity-60
                       inline-flex items-center gap-2 shrink-0 transition-colors"
          >
            <FileSpreadsheet size={16} /> {exporting ? '…' : 'Excel'}
          </button>
        </div>
      ) : (
        <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight mb-1">Super qidiruv</h1>
      )}
      {!shop && <p className="text-sm text-slate-500 mb-5">Do'kon nomi yoki qarzdor ismi/telefoni bo'yicha qidiring — istalgan qarzni boshqaring</p>}

      {/* Shop clients view */}
      {shop ? (
        <div className="bg-white rounded-2xl border border-slate-200/60 overflow-hidden shadow-sm max-w-3xl">
          {shop.loading ? (
            <div className="p-4 space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="skeleton h-14 rounded-xl" />)}</div>
          ) : shop.clients.length === 0 ? (
            <p className="text-center py-16 text-slate-400">Mijoz yo'q</p>
          ) : shop.clients.map(c => (
            <ClientRow key={c.id} c={c} onClick={() => openClient(c.id)} />
          ))}
        </div>
      ) : (
        <>
          {/* Search box */}
          <div className="relative max-w-xl mb-5">
            <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              autoFocus
              className="w-full pl-11 pr-4 py-3 bg-white border-2 border-transparent rounded-2xl text-sm outline-none focus:border-blue-500 shadow-sm transition-all"
              placeholder="Masalan: Navro'z minimarket yoki Alisher…"
              value={q}
              onChange={e => setQ(e.target.value)}
            />
          </div>

          {searching && <p className="text-sm text-slate-400">Qidirilmoqda…</p>}

          {results && (
            <div className="grid md:grid-cols-2 gap-5 max-w-5xl">
              {/* Shops */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Do'konlar ({results.shops.length})</p>
                <div className="bg-white rounded-2xl border border-slate-200/60 overflow-hidden shadow-sm">
                  {results.shops.length === 0 ? <p className="text-center py-8 text-slate-400 text-sm">Topilmadi</p>
                    : results.shops.map(s => (
                      <button key={s.id} onClick={() => openShop(s)} className="w-full flex items-center gap-3 px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50/60 transition-colors text-left">
                        <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: 'linear-gradient(135deg,#8B5CF6,#6D28D9)' }}>
                          <Store size={16} className="text-white" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-slate-900 text-sm truncate">{s.name}</p>
                          <p className="text-xs text-slate-400">{s.owner} · {s.client_count} mijoz</p>
                        </div>
                        <span className="money text-sm font-bold text-red-600 shrink-0">{fmt.money(s.total_remaining)}</span>
                        <ChevronRight size={16} className="text-slate-300 shrink-0" />
                      </button>
                    ))}
                </div>
              </div>

              {/* Clients */}
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">Qarzdorlar ({results.clients.length})</p>
                <div className="bg-white rounded-2xl border border-slate-200/60 overflow-hidden shadow-sm">
                  {results.clients.length === 0 ? <p className="text-center py-8 text-slate-400 text-sm">Topilmadi</p>
                    : results.clients.map(c => (
                      <button key={c.id} onClick={() => openClient(c.id)} className="w-full flex items-center gap-3 px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50/60 transition-colors text-left">
                        <div className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-white font-bold text-sm" style={{ background: c.has_overdue ? 'linear-gradient(135deg,#F87171,#DC2626)' : 'linear-gradient(135deg,#3B82F6,#1D4ED8)' }}>
                          {c.full_name[0]?.toUpperCase()}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-slate-900 text-sm truncate flex items-center gap-1">
                            {c.full_name}
                            {c.has_overdue && <AlertCircle size={12} className="text-red-500 shrink-0" />}
                          </p>
                          <p className="text-xs text-slate-400 truncate">{c.shop_name}</p>
                        </div>
                        <span className="money text-sm font-bold text-red-600 shrink-0">{fmt.money(c.total_remaining)}</span>
                      </button>
                    ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Client detail modal ── */}
      {clientId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in" onClick={closeClient}>
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] flex flex-col animate-scale-in" onClick={e => e.stopPropagation()}>
            {clientLoading || !client ? (
              <div className="p-6 space-y-3">
                <div className="skeleton h-16 rounded-2xl" />
                <div className="skeleton h-10 rounded-xl" />
                <div className="skeleton h-24 rounded-2xl" />
                <div className="skeleton h-24 rounded-2xl" />
              </div>
            ) : (
              <>
                {/* Header */}
                <div className="p-5 border-b border-slate-100 flex items-start gap-3">
                  <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-white font-bold text-lg shrink-0" style={{ background: 'linear-gradient(135deg,#2563EB,#7c3aed)' }}>
                    {client.full_name[0]?.toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-display font-bold text-slate-900 text-lg leading-tight truncate">{client.full_name}</p>
                    <p className="text-xs text-slate-400">{client.phone} · {client.shop_name}</p>
                    <div className="flex gap-4 mt-2">
                      <span className="text-sm"><span className="money font-bold text-red-600">{fmt.money(client.total_remaining)}</span> <span className="text-slate-400 text-xs">qoldiq</span></span>
                      <span className="text-sm"><span className="money font-bold text-green-600">{fmt.money(client.total_paid)}</span> <span className="text-slate-400 text-xs">to'langan</span></span>
                    </div>
                  </div>
                  <button onClick={closeClient} className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center hover:bg-slate-200 transition-colors shrink-0">
                    <X size={16} className="text-slate-500" />
                  </button>
                </div>

                {/* Actions */}
                <div className="px-5 pt-4 flex gap-2">
                  <button onClick={() => openModal('addDebt')} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white inline-flex items-center justify-center gap-1.5 transition-all active:scale-95" style={{ background: 'linear-gradient(135deg,#2563EB,#1d4ed8)' }}>
                    <Plus size={15} /> Qarz qo'shish
                  </button>
                  <button onClick={() => openModal('pay')} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-white inline-flex items-center justify-center gap-1.5 transition-all active:scale-95" style={{ background: 'linear-gradient(135deg,#16A34A,#15803d)' }}>
                    <CreditCard size={15} /> To'lov
                  </button>
                </div>

                {/* Tabs */}
                <div className="px-5 pt-3">
                  <div className="flex gap-1 p-1 bg-slate-100 rounded-xl">
                    {[['all', 'Hammasi', 'text-blue-600'], ['debts', 'Olingan qarz', 'text-red-600'], ['payments', "To'langan pul", 'text-green-600']].map(([k, label, cls]) => (
                      <button key={k} onClick={() => setTab(k)} className={`flex-1 py-2 rounded-lg text-[13px] font-semibold transition-all ${tab === k ? 'bg-white shadow-sm ' + cls : 'text-slate-500'}`}>{label}</button>
                    ))}
                  </div>
                </div>

                {/* Body — hodisalar lentasi (qarz oldi / to'lov), ketma-ket */}
                <div className="p-5 overflow-y-auto flex-1 space-y-2">
                  {(() => {
                    const debtEvents = (client.debts || []).map(d => ({ kind: 'debt', date: d.created_at, debt: d }))
                    const payEvents  = (client.payments || []).map((p, i) => ({ kind: 'pay', date: p.created_at, amount: p.amount, _i: i }))
                    const list = tab === 'debts' ? debtEvents
                      : tab === 'payments' ? payEvents
                      : [...debtEvents, ...payEvents].sort((a, b) => new Date(a.date) - new Date(b.date))
                    if (!list.length) {
                      return <p className="text-center py-10 text-slate-400 text-sm">{tab === 'payments' ? "Hali to'lov yo'q" : tab === 'debts' ? "Qarz yo'q" : 'Hozircha yozuv yo\'q'}</p>
                    }
                    return list.map((ev, idx) => ev.kind === 'debt'
                      ? <DebtEvent key={'d' + idx} d={ev.debt} onEdit={() => openModal('editDebt', ev.debt)} onDelete={() => deleteDebt(ev.debt)} />
                      : <PayEvent key={'p' + idx} amount={ev.amount} date={ev.date} />
                    )
                  })()}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ── Add/Edit/Pay modal ── */}
      {modal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm animate-fade-in" onClick={() => setModal(null)}>
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-sm p-6 animate-scale-in" onClick={e => e.stopPropagation()}>
            <h3 className="font-display font-bold text-slate-900 mb-4">
              {modal.type === 'addDebt' ? "Qarz qo'shish" : modal.type === 'pay' ? "To'lov qabul qilish" : "Qarzni tahrirlash"}
            </h3>
            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-500 block mb-1.5">{modal.type === 'pay' ? "To'lov miqdori" : "Miqdor (so'm)"} *</label>
                <input type="number" className={inputCls} placeholder="0" autoFocus value={form.amount} onChange={e => setForm(s => ({ ...s, amount: e.target.value }))} />
              </div>
              {modal.type !== 'pay' && (
                <>
                  <div>
                    <label className="text-xs font-semibold text-slate-500 block mb-1.5">Qaytarish sanasi</label>
                    <input type="date" className={inputCls} value={form.due_date} onChange={e => setForm(s => ({ ...s, due_date: e.target.value }))} />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-slate-500 block mb-1.5">Izoh</label>
                    <textarea className={`${inputCls} resize-none h-20`} maxLength={200} placeholder="Ixtiyoriy…" value={form.note} onChange={e => setForm(s => ({ ...s, note: e.target.value }))} />
                  </div>
                </>
              )}
              {modal.type === 'pay' && (
                parseInt(form.amount) > (client?.total_remaining ?? 0) ? (
                  <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">⚠️ Miqdor umumiy qoldiqdan ko'p! ({fmt.money(client?.total_remaining)})</p>
                ) : (
                  <p className="text-xs text-slate-400">To'lov umumiy qoldiqdan ayiriladi (eng eski qarzdan boshlab).</p>
                )
              )}
              {err && <p className="text-sm text-red-500">{err}</p>}
              <div className="flex gap-2 pt-1">
                <button onClick={() => setModal(null)} className="flex-1 py-2.5 bg-slate-100 text-slate-700 rounded-xl text-sm font-semibold hover:bg-slate-200 transition-colors">Bekor</button>
                <button onClick={submitModal}
                  disabled={saving || (modal.type === 'pay' && parseInt(form.amount) > (client?.total_remaining ?? 0))}
                  className={`flex-1 py-2.5 rounded-xl text-sm font-semibold text-white transition-colors disabled:opacity-60 ${modal.type === 'pay' ? 'bg-green-600 hover:bg-green-700' : 'bg-blue-600 hover:bg-blue-700'}`}>
                  {saving ? '...' : 'Saqlash'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ClientRow({ c, onClick }) {
  return (
    <button onClick={onClick} className="w-full flex items-center gap-3 px-4 py-3 border-b border-slate-50 last:border-0 hover:bg-slate-50/60 transition-colors text-left">
      <div className="w-9 h-9 rounded-full flex items-center justify-center shrink-0 text-white font-bold text-sm" style={{ background: c.has_overdue ? 'linear-gradient(135deg,#F87171,#DC2626)' : 'linear-gradient(135deg,#3B82F6,#1D4ED8)' }}>
        {c.full_name[0]?.toUpperCase()}
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-semibold text-slate-900 text-sm truncate">{c.full_name}</p>
        <p className="text-xs text-slate-400">{c.phone} · {c.active_debts} faol qarz</p>
      </div>
      <span className="money text-sm font-bold text-red-600 shrink-0">{fmt.money(c.total_remaining)}</span>
      <ChevronRight size={16} className="text-slate-300 shrink-0" />
    </button>
  )
}

// Qarz oldi hodisasi (super uchun tahrir/o'chirish bilan)
function DebtEvent({ d, onEdit, onDelete }) {
  return (
    <div className="rounded-xl border border-slate-100 p-3 flex items-center gap-3">
      <div className="w-9 h-9 rounded-xl bg-red-50 flex items-center justify-center shrink-0"><ArrowDownLeft size={16} className="text-red-600" /></div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900">Qarz oldi</p>
        <p className="text-[11px] text-slate-400 tabular-nums">{fmt.date(d.created_at)} · {fmt.time(d.created_at)}{d.due_date ? ` · muddat ${fmt.date(d.due_date)}` : ''}</p>
        {d.note && <p className="text-xs italic text-slate-500 mt-0.5">"{d.note}"</p>}
      </div>
      <span className="money font-bold text-red-600 shrink-0">+{fmt.money(d.amount)}</span>
      <div className="flex gap-1.5 shrink-0">
        <button onClick={onEdit} title="Tahrirlash" className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center hover:bg-blue-100 transition-colors active:scale-90"><Pencil size={14} /></button>
        <button onClick={onDelete} title="O'chirish" className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center hover:bg-rose-100 transition-colors active:scale-90"><Trash2 size={14} /></button>
      </div>
    </div>
  )
}

// To'lov hodisasi
function PayEvent({ amount, date }) {
  return (
    <div className="rounded-xl border border-slate-100 p-3 flex items-center gap-3">
      <div className="w-9 h-9 rounded-xl bg-green-50 flex items-center justify-center shrink-0"><ArrowUpRight size={16} className="text-green-600" /></div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900">To'lov</p>
        <p className="text-[11px] text-slate-400 tabular-nums">{fmt.date(date)} · {fmt.time(date)}</p>
      </div>
      <span className="money font-bold text-green-600 shrink-0">−{fmt.money(amount)}</span>
    </div>
  )
}

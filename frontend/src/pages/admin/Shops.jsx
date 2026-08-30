import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { adminShopsApi, adminProfileApi, adminExportApi, errorMessage } from '../../lib/api'
import ConfirmStamp from '../../components/ui/ConfirmStamp'
import { Check, CalendarPlus, Ban, XCircle, RotateCcw, Trash2, LogIn, FileSpreadsheet, ArchiveRestore, AlertTriangle, X } from 'lucide-react'

const TABS = [
  { key: null,       label: 'Barchasi' },
  { key: 'pending',  label: 'Kutilmoqda' },
  { key: 'active',   label: 'Faol' },
  { key: 'blocked',  label: 'Bloklangan' },
  { key: 'rejected', label: 'Rad etilgan' },
  { key: 'deleted',  label: '🗑 Chiqindi qutisi' },
]
const BADGE = {
  pending:  'bg-amber-100 text-amber-700',
  active:   'bg-green-100 text-green-700',
  blocked:  'bg-red-100 text-red-700',
  rejected: 'bg-slate-100 text-slate-600',
  deleted:  'bg-slate-800 text-white',
}
const LABEL = {
  pending: 'Kutilmoqda', active: 'Faol', blocked: 'Bloklangan',
  rejected: 'Rad etildi', deleted: "O'chirilgan",
}

export default function AdminShops() {
  const [shops, setShops]   = useState([])
  const [total, setTotal]   = useState(0)
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [modal, setModal]   = useState(null)
  const [selected, setSelected] = useState(null)
  const [reason, setReason] = useState('')
  const [days, setDays]     = useState(30)
  const [stamp, setStamp]   = useState(false)
  const [isSuper, setIsSuper] = useState(false)
  // Backend rad etgan amal (masalan «muddati tugagan do'konni blokdan
  // chiqarib bo'lmaydi») ilgari faqat brauzer konsoliga tushardi —
  // admin tugmani bosaverib, nima uchun ishlamayotganini bilmasdi.
  const [error, setError]   = useState('')
  const [busy, setBusy]     = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    adminProfileApi.me().then(r => setIsSuper(!!r.data.is_super)).catch(() => {})
  }, [])

  const load = async () => {
    setLoading(true)
    try { const res = await adminShopsApi.list(status ? { status } : {}); setShops(res.data.shops); setTotal(res.data.total) }
    catch (e) { setError(errorMessage(e, "Ro'yxat yuklanmadi")) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [status])

  const act = async (fn, ...args) => {
    setBusy(true); setError('')
    try {
      await fn(...args)
      setModal(null); setReason(''); setSelected(null)
      load()
    } catch (e) {
      // Modal ochiq qoladi — admin sababni o'qib, boshqa yo'l tanlaydi
      setError(errorMessage(e, 'Amal bajarilmadi'))
    } finally { setBusy(false) }
  }
  const approveShop = async (id) => {
    setBusy(true); setError('')
    try {
      await adminShopsApi.approve(id)
      setStamp(true)
      setTimeout(() => setStamp(false), 1700)
      load()
    } catch (e) { setError(errorMessage(e, 'Tasdiqlanmadi')) }
    finally { setBusy(false) }
  }
  const open = (type, shop) => {
    setSelected(shop); setModal(type); setError('')
    if (type === 'extend') setDays(30)
  }

  const [exporting, setExporting] = useState(false)
  const exportExcel = async () => {
    setExporting(true)
    try { await adminExportApi.shops(status) }
    catch (e) { alert(errorMessage(e, 'Fayl yuklab olinmadi')) }
    finally { setExporting(false) }
  }

  const pill    = "inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl transition-all active:scale-95"
  const iconBtn = "inline-flex items-center justify-center w-9 h-9 rounded-xl transition-all active:scale-90"

  return (
    <div className="p-6 lg:p-8 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight">
          Do'konlar <span className="text-slate-400 font-normal text-lg tabular-nums">({total})</span>
        </h1>
        <button
          onClick={exportExcel} disabled={exporting || loading}
          className="px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium
                     text-emerald-700 hover:bg-emerald-50 hover:border-emerald-200 disabled:opacity-60
                     inline-flex items-center gap-2 transition-colors"
        >
          <FileSpreadsheet size={16} /> {exporting ? 'Tayyorlanmoqda…' : 'Excel'}
        </button>
      </div>

      {error && !modal && (
        <div className="mb-4 flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3">
          <AlertTriangle size={18} className="text-rose-600 shrink-0 mt-0.5" />
          <p className="text-sm text-rose-800 flex-1">{error}</p>
          <button onClick={() => setError('')} className="text-rose-400 hover:text-rose-600">
            <X size={16} />
          </button>
        </div>
      )}

      <div className="flex gap-2 mb-5 flex-wrap">
        {TABS.map(t => (
          <button key={t.key ?? 'all'} onClick={() => setStatus(t.key)}
            className={`px-3.5 py-1.5 rounded-xl text-sm font-medium transition-all
              ${status === t.key
                ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/30'
                : 'bg-white text-slate-600 border border-slate-200 hover:border-blue-300'}`}>
            {t.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/60 overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>{(isSuper ? ["Do'kon", "Egasi", "Holat", "Muddat", "Kirish", "Amallar"] : ["Do'kon", "Egasi", "Holat", "Muddat", "Amallar"]).map(h =>
              <th key={h} className="text-left px-4 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wide">{h}</th>)}</tr>
          </thead>
          <tbody>
            {loading ? [...Array(6)].map((_, i) => (
              <tr key={i} className="border-b border-slate-50">
                <td className="px-4 py-4"><div className="skeleton h-4 w-24" /></td>
                <td className="px-4 py-4"><div className="skeleton h-4 w-32 mb-2" /><div className="skeleton h-3 w-20" /></td>
                <td className="px-4 py-4"><div className="skeleton h-6 w-16 rounded-full" /></td>
                <td className="px-4 py-4"><div className="skeleton h-3 w-20" /></td>
                {isSuper && <td className="px-4 py-4"><div className="skeleton h-9 w-20 rounded-xl" /></td>}
                <td className="px-4 py-4"><div className="flex gap-2"><div className="skeleton h-9 w-24 rounded-xl" /><div className="skeleton h-9 w-9 rounded-xl" /></div></td>
              </tr>
            ))
            : shops.length === 0 ? <tr><td colSpan={isSuper ? 6 : 5} className="text-center py-16 text-slate-400">Hech narsa topilmadi</td></tr>
            : shops.map(s => (
              <tr key={s.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                <td className="px-4 py-3 font-semibold text-slate-900">{s.name}</td>
                <td className="px-4 py-3">
                  <p className="text-slate-700">{s.owner}</p>
                  {(s.owner_phones?.length ? s.owner_phones : [s.owner_phone]).map((ph, idx) => (
                    <p key={idx} className="text-xs text-slate-400 tabular-nums">{ph}</p>
                  ))}
                </td>
                <td className="px-4 py-3">
                  <span className={`text-xs px-2.5 py-1 rounded-full font-semibold ${BADGE[s.status]}`}>{LABEL[s.status]}</span>
                  {s.deleted_by && <p className="text-[11px] text-slate-400 mt-1">o'chirgan: {s.deleted_by}</p>}
                </td>
                <td className="px-4 py-3 text-xs tabular-nums">
                  {s.status === 'deleted' ? (
                    <span className="text-rose-600 font-semibold">{s.purge_in_days} kundan keyin yo'q qilinadi</span>
                  ) : (
                    <>
                      <p className={s.is_expired ? 'text-rose-600 font-semibold' : 'text-slate-500'}>
                        {new Date(s.subscription_end || s.trial_end).toLocaleDateString('uz')}
                      </p>
                      <p className="text-[11px] text-slate-400">
                        {s.subscription_end ? 'obuna' : 'sinov muddati'}
                        {s.is_expired && ' · tugagan'}
                      </p>
                    </>
                  )}
                </td>
                {isSuper && (
                  <td className="px-4 py-3">
                    <button onClick={() => navigate(`/admin/super?shop=${s.id}`)} title="Do'kon ichiga kirish" className={`${pill} bg-violet-50 text-violet-600 ring-1 ring-violet-200 hover:bg-violet-100`}><LogIn size={14} /> Kirish</button>
                  </td>
                )}
                <td className="px-4 py-3">
                  <div className="flex gap-2 flex-wrap items-center">
                    {s.status === 'deleted' ? <>
                      <button onClick={() => act(adminShopsApi.restore, s.id)} className={`${pill} bg-green-600 text-white hover:bg-green-700 shadow-sm shadow-green-600/30`}>
                        <ArchiveRestore size={14} /> Qaytarish
                      </button>
                      {isSuper && (
                        <button onClick={() => open('purge', s)} title="Butunlay yo'q qilish"
                          className={`${iconBtn} bg-slate-800 text-white hover:bg-slate-900`}>
                          <Trash2 size={15} />
                        </button>
                      )}
                    </> : <>
                    {s.status === 'pending' && <>
                      <button onClick={() => approveShop(s.id)} className={`${pill} bg-green-600 text-white hover:bg-green-700 shadow-sm shadow-green-600/30`}><Check size={14} /> Tasdiqlash</button>
                      <button onClick={() => open('reject', s)} className={`${pill} bg-rose-50 text-rose-600 ring-1 ring-rose-200 hover:bg-rose-100`}><XCircle size={14} /> Rad etish</button>
                    </>}
                    {s.status === 'active' && <>
                      <button onClick={() => open('extend', s)} className={`${pill} bg-blue-50 text-blue-600 ring-1 ring-blue-200 hover:bg-blue-100`}><CalendarPlus size={14} /> Uzaytirish</button>
                      <button onClick={() => open('block', s)} className={`${pill} bg-amber-50 text-amber-600 ring-1 ring-amber-200 hover:bg-amber-100`}><Ban size={14} /> Bloklash</button>
                    </>}
                    {s.status === 'blocked' && <>
                      <button onClick={() => open('extend', s)} className={`${pill} bg-blue-50 text-blue-600 ring-1 ring-blue-200 hover:bg-blue-100`}><CalendarPlus size={14} /> Uzaytirish</button>
                      {/* Muddati tugagan do'konni blokdan chiqarib bo'lmaydi —
                          faqat uzaytirish orqali ochiladi */}
                      {!s.is_expired && (
                        <button onClick={() => act(adminShopsApi.unblock, s.id)} className={`${pill} bg-green-600 text-white hover:bg-green-700 shadow-sm shadow-green-600/30`}><RotateCcw size={14} /> Blokdan chiqarish</button>
                      )}
                    </>}
                    <button onClick={() => open('delete', s)} title="O'chirish" className={`${iconBtn} bg-rose-50 text-rose-600 ring-1 ring-rose-200 hover:bg-rose-100`}><Trash2 size={15} /></button>
                    </>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {modal && selected && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
          <div className="bg-white rounded-3xl p-6 w-full max-w-sm shadow-2xl animate-scale-in">
            {modal === 'delete' ? (
              <>
                <div className="w-12 h-12 rounded-2xl bg-red-100 flex items-center justify-center mb-3">
                  <Trash2 size={22} className="text-red-600" />
                </div>
                <h3 className="font-display font-bold text-slate-900 mb-1">Do'konni o'chirish</h3>
                <p className="text-sm text-slate-500 mb-3">🏪 <b>{selected.name}</b></p>
                {/* Yumshoq o'chirish — 30 kun ichida qaytarish mumkin */}
                <div className="bg-amber-50 border border-amber-100 rounded-xl px-4 py-3 mb-4">
                  <p className="text-sm text-amber-800">
                    Do'kon <b>chiqindi qutisi</b>ga tushadi. Mijozlar va qarzlar
                    <b> 30 kun</b> saqlanadi — shu muddat ichida qaytarish mumkin.
                  </p>
                </div>
                {error && (
                  <div className="flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-xl px-3.5 py-2.5 mb-4">
                    <AlertTriangle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                    <p className="text-sm text-rose-800">{error}</p>
                  </div>
                )}
                <div className="flex gap-2">
                  <button onClick={() => { setModal(null); setSelected(null); setError('') }} className="flex-1 py-2.5 bg-slate-100 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-200 transition-colors">Bekor</button>
                  <button disabled={busy} onClick={() => act(adminShopsApi.delete, selected.id)} className="flex-1 py-2.5 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors disabled:opacity-60">{busy ? 'O‘chirilmoqda…' : "Ha, o'chirish"}</button>
                </div>
              </>
            ) : modal === 'purge' ? (
              <>
                <div className="w-12 h-12 rounded-2xl bg-slate-900 flex items-center justify-center mb-3">
                  <Trash2 size={22} className="text-white" />
                </div>
                <h3 className="font-display font-bold text-slate-900 mb-1">Butunlay yo'q qilish</h3>
                <p className="text-sm text-slate-500 mb-3">🏪 <b>{selected.name}</b></p>
                <div className="bg-red-50 border border-red-100 rounded-xl px-4 py-3 mb-4">
                  <p className="text-sm text-red-700">
                    ⚠️ Barcha mijozlar, qarzlar va to'lovlar <b>darhol va butunlay</b> o'chadi.
                    Bu amalni <b>qaytarib bo'lmaydi</b>. 30 kunni kutmasdan o'chirmoqchi bo'lsangizgina bosing.
                  </p>
                </div>
                {error && (
                  <div className="flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-xl px-3.5 py-2.5 mb-4">
                    <AlertTriangle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                    <p className="text-sm text-rose-800">{error}</p>
                  </div>
                )}
                <div className="flex gap-2">
                  <button onClick={() => { setModal(null); setSelected(null); setError('') }} className="flex-1 py-2.5 bg-slate-100 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-200 transition-colors">Bekor</button>
                  <button disabled={busy} onClick={() => act(adminShopsApi.purge, selected.id)} className="flex-1 py-2.5 bg-slate-900 text-white rounded-xl text-sm font-medium hover:bg-black transition-colors disabled:opacity-60">{busy ? 'Bajarilmoqda…' : "Butunlay o'chirish"}</button>
                </div>
              </>
            ) : (
              <>
                <h3 className="font-display font-bold text-slate-900 mb-1">{modal === 'reject' ? 'Rad etish' : modal === 'block' ? 'Bloklash' : 'Obunani uzaytirish'}</h3>
                <p className="text-sm text-slate-500 mb-4">🏪 {selected.name}</p>
                {modal === 'extend' && selected.status === 'blocked' && (
                  <div className="bg-blue-50 border border-blue-100 rounded-xl px-4 py-3 mb-4">
                    <p className="text-sm text-blue-800">
                      Do'kon hozir bloklangan{selected.is_expired ? ' (obuna muddati tugagan)' : ''}.
                      Uzaytirish uni <b>o'sha zahoti faollashtiradi</b>.
                    </p>
                  </div>
                )}
                {(modal === 'reject' || modal === 'block') && <textarea className="w-full px-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm outline-none focus:border-blue-500 focus:bg-white resize-none h-24 mb-4 transition-all" placeholder="Sabab (ixtiyoriy)…" value={reason} onChange={e => setReason(e.target.value)} />}
                {modal === 'extend' && <div className="mb-4">
                  <label className="text-sm text-slate-600 block mb-1.5">Kunlar soni</label>
                  <input type="number" min="1" max="3650" className="w-full px-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm outline-none focus:border-blue-500 focus:bg-white transition-all tabular-nums" value={days} onChange={e => setDays(+e.target.value)} />
                  <div className="flex gap-2 mt-2">
                    {[7, 30, 90, 365].map(d => (
                      <button key={d} type="button" onClick={() => setDays(d)}
                        className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors
                          ${days === d ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
                        {d} kun
                      </button>
                    ))}
                  </div>
                </div>}
                {error && (
                  <div className="flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-xl px-3.5 py-2.5 mb-4">
                    <AlertTriangle size={16} className="text-rose-600 shrink-0 mt-0.5" />
                    <p className="text-sm text-rose-800">{error}</p>
                  </div>
                )}
                <div className="flex gap-2">
                  <button onClick={() => { setModal(null); setSelected(null); setError('') }} className="flex-1 py-2.5 bg-slate-100 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-200 transition-colors">Bekor</button>
                  <button
                    disabled={busy || (modal === 'extend' && (!days || days < 1 || days > 3650))}
                    onClick={() => { if (modal === 'reject') act(adminShopsApi.reject, selected.id, reason); if (modal === 'block') act(adminShopsApi.block, selected.id, reason); if (modal === 'extend') act(adminShopsApi.extend, selected.id, days) }}
                    className={`flex-1 py-2.5 rounded-xl text-sm font-medium text-white transition-colors disabled:opacity-60
                      ${modal === 'extend' ? 'bg-blue-600 hover:bg-blue-700' : 'bg-red-500 hover:bg-red-600'}`}>
                    {busy ? 'Bajarilmoqda…' : 'Tasdiqlash'}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* Tasdiqlandi muhri */}
      {stamp && createPortal(
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/50 backdrop-blur-sm animate-fade-in">
          <div className="w-44 h-44 rounded-full bg-white flex items-center justify-center" style={{ boxShadow: '0 20px 60px rgba(22,163,74,0.4)' }}>
            <ConfirmStamp label="TASDIQLANDI" size={140} />
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

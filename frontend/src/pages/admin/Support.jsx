import { useState, useEffect } from 'react'
import { adminSupportApi, errorMessage } from '../../lib/api'
import { fmt } from '../../lib/utils'
import { MessageSquare, Check, AlertTriangle, X, Store, Phone } from 'lucide-react'
import LoadError from '../../components/ui/LoadError'

/**
 * Do'kondorlardan kelgan murojaatlar.
 *
 * Backend `/api/admin/support` ni ancha oldin bergan, lekin panelda uni
 * o'qiydigan sahifa yo'q edi — xabarlar faqat Telegram orqali admin ID ga
 * ketardi. Sozlamalarda «Admin Telegram ID» bo'sh bo'lsa (yoki xabar
 * ko'zdan qochsa) murojaat butunlay yo'qolardi.
 */
export default function AdminSupport() {
  const [items, setItems]     = useState([])
  const [total, setTotal]     = useState(0)
  const [unread, setUnread]   = useState(0)
  const [unreadOnly, setUnreadOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [busyId, setBusyId]   = useState(null)

  const load = async () => {
    setLoading(true); setError('')
    try {
      const res = await adminSupportApi.list(unreadOnly ? { unread_only: true } : {})
      setItems(res.data.messages)
      setTotal(res.data.total)
      setUnread(res.data.unread)
    } catch (e) {
      setError(errorMessage(e, 'Xabarlar yuklanmadi'))
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [unreadOnly])

  const markRead = async (m) => {
    setBusyId(m.id); setError('')
    try {
      await adminSupportApi.markRead(m.id)
      load()
    } catch (e) {
      setError(errorMessage(e, 'Belgilanmadi'))
    } finally { setBusyId(null) }
  }

  return (
    <div className="p-6 lg:p-8 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3 mb-5">
        <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight">
          Xabarlar <span className="text-slate-400 font-normal text-lg tabular-nums">({total})</span>
          {unread > 0 && (
            <span className="ml-2 text-xs font-semibold px-2.5 py-1 rounded-full bg-rose-100 text-rose-700 align-middle">
              {unread} o'qilmagan
            </span>
          )}
        </h1>
        <button
          onClick={() => setUnreadOnly(v => !v)}
          className={`px-3.5 py-1.5 rounded-xl text-sm font-medium transition-all
            ${unreadOnly
              ? 'bg-blue-600 text-white shadow-sm shadow-blue-600/30'
              : 'bg-white text-slate-600 border border-slate-200 hover:border-blue-300'}`}>
          Faqat o'qilmagan
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3">
          <AlertTriangle size={18} className="text-rose-600 shrink-0 mt-0.5" />
          <p className="text-sm text-rose-800 flex-1">{error}</p>
          <button onClick={() => setError('')} className="text-rose-400 hover:text-rose-600"><X size={16} /></button>
        </div>
      )}

      {loading ? (
        <div className="flex flex-col gap-3">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-28 rounded-2xl" />)}
        </div>
      ) : error && items.length === 0 ? (
        <LoadError message={error} onRetry={load} />
      ) : items.length === 0 ? (
        <div className="bg-white rounded-2xl border border-slate-200/60 text-center py-16 shadow-sm">
          <MessageSquare size={38} className="text-slate-300 mx-auto mb-3" />
          <p className="text-slate-400 text-sm">
            {unreadOnly ? "O'qilmagan xabar yo'q" : 'Hozircha xabar yo‘q'}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {items.map(m => (
            <div key={m.id}
              className={`bg-white rounded-2xl border p-5 shadow-sm transition-colors
                ${m.is_read ? 'border-slate-200/60' : 'border-blue-200 bg-blue-50/30'}`}>
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="min-w-0">
                  <p className="font-semibold text-slate-900">
                    {m.user_full_name}
                    {!m.is_read && <span className="ml-2 w-2 h-2 rounded-full bg-blue-600 inline-block align-middle" />}
                  </p>
                  <div className="flex items-center gap-4 mt-1 text-xs text-slate-500 flex-wrap">
                    <span className="inline-flex items-center gap-1"><Store size={12} /> {m.shop_name}</span>
                    {m.user_phone && (
                      <a href={`tel:${m.user_phone}`} className="inline-flex items-center gap-1 tabular-nums hover:text-blue-600">
                        <Phone size={12} /> {m.user_phone}
                      </a>
                    )}
                    <span>{fmt.ago(m.created_at)}</span>
                  </div>
                </div>
                {!m.is_read && (
                  <button
                    onClick={() => markRead(m)} disabled={busyId === m.id}
                    className="inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl
                               bg-green-600 text-white hover:bg-green-700 transition-all active:scale-95 disabled:opacity-60">
                    <Check size={14} /> O'qildi
                  </button>
                )}
              </div>
              <p className="mt-3 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap break-words">
                {m.message}
              </p>
            </div>
          ))}
        </div>
      )}

      <p className="text-xs text-slate-400 mt-5 leading-relaxed">
        Javob berish uchun botdagi xabarga <b>reply</b> qiling — javob do'kondorga yetib boradi.
      </p>
    </div>
  )
}

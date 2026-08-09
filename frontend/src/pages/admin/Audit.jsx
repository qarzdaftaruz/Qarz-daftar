import { useState, useEffect, useCallback } from 'react'
import { adminAuditApi, errorMessage } from '../../lib/api'
import { ScrollText, AlertTriangle, RefreshCw, Search } from 'lucide-react'

const PAGE = 30

const ACTOR_LABEL = {
  super_admin: 'Super admin',
  admin: 'Admin',
  owner: "Do'kondor",
  bot: 'Bot',
  system: 'Tizim',
}

const ACTOR_STYLE = {
  super_admin: 'bg-violet-50 text-violet-700 ring-violet-200',
  admin:       'bg-blue-50 text-blue-700 ring-blue-200',
  owner:       'bg-emerald-50 text-emerald-700 ring-emerald-200',
  bot:         'bg-slate-100 text-slate-600 ring-slate-200',
  system:      'bg-slate-100 text-slate-600 ring-slate-200',
}

const inputCls = "px-3.5 py-2 bg-white border border-slate-200 rounded-xl text-sm outline-none focus:border-blue-500 transition-colors"

function fmtDate(iso) {
  const d = new Date(iso)
  return d.toLocaleString('uz-UZ', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function AdminAudit() {
  const [items, setItems]   = useState([])
  const [total, setTotal]   = useState(0)
  const [actions, setActions] = useState({})
  const [page, setPage]     = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState('')

  const [action, setAction] = useState('')
  const [actor, setActor]   = useState('')
  const [criticalOnly, setCriticalOnly] = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const { data } = await adminAuditApi.list({
        skip: page * PAGE,
        limit: PAGE,
        action: action || undefined,
        actor: actor.trim() || undefined,
        critical_only: criticalOnly || undefined,
      })
      setItems(data.items)
      setTotal(data.total)
      setActions(data.actions || {})
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setLoading(false)
    }
  }, [page, action, actor, criticalOnly])

  useEffect(() => { load() }, [load])

  // Filtr o'zgarsa birinchi sahifaga qaytamiz
  useEffect(() => { setPage(0) }, [action, criticalOnly])

  const pages = Math.ceil(total / PAGE)

  return (
    <div className="p-6 lg:p-8 space-y-5 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <ScrollText size={24} className="text-blue-600" /> Amallar tarixi
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Kim, qachon, nima qilgani. Yozuvlar 1 yil saqlanadi.
          </p>
        </div>
        <button
          onClick={load}
          className="px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium
                     text-slate-600 hover:bg-slate-50 inline-flex items-center gap-2 transition-colors"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Yangilash
        </button>
      </div>

      {/* Filtrlar */}
      <div className="flex flex-wrap items-center gap-2.5">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            className={`${inputCls} pl-9 w-56`}
            placeholder="Kim bajargan…"
            value={actor}
            onChange={e => setActor(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && (setPage(0), load())}
          />
        </div>

        <select className={inputCls} value={action} onChange={e => setAction(e.target.value)}>
          <option value="">Barcha amallar</option>
          {Object.entries(actions).map(([key, label]) => (
            <option key={key} value={key}>{label}</option>
          ))}
        </select>

        <label className="inline-flex items-center gap-2 px-3.5 py-2 bg-white border border-slate-200
                          rounded-xl text-sm text-slate-700 cursor-pointer select-none hover:bg-slate-50">
          <input
            type="checkbox"
            className="accent-rose-600"
            checked={criticalOnly}
            onChange={e => setCriticalOnly(e.target.checked)}
          />
          <AlertTriangle size={14} className="text-rose-500" /> Faqat muhimlari
        </label>

        <span className="text-sm text-slate-400 ml-auto tabular-nums">{total} ta yozuv</span>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">{error}</div>
      )}

      <div className="bg-white rounded-2xl border border-slate-200/60 shadow-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-50/80">
              <tr>
                {['Vaqt', 'Kim', 'Amal', 'Tafsilot', 'IP'].map(h => (
                  <th key={h} className="text-left px-4 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wide whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {loading ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 5 }).map((__, j) => (
                      <td key={j} className="px-4 py-3.5"><div className="skeleton h-4 w-full rounded" /></td>
                    ))}
                  </tr>
                ))
              ) : items.length === 0 ? (
                <tr><td colSpan={5} className="text-center py-16 text-slate-400">Yozuv topilmadi</td></tr>
              ) : items.map(it => (
                <tr key={it.id} className={it.is_critical ? 'bg-rose-50/40' : 'hover:bg-slate-50/60 transition-colors'}>
                  <td className="px-4 py-3.5 text-slate-500 tabular-nums whitespace-nowrap text-xs">
                    {fmtDate(it.created_at)}
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <p className="font-medium text-slate-900">{it.actor_name || '—'}</p>
                    <span className={`inline-block mt-0.5 text-[10px] px-1.5 py-0.5 rounded ring-1 font-medium
                                      ${ACTOR_STYLE[it.actor_type] || ACTOR_STYLE.system}`}>
                      {ACTOR_LABEL[it.actor_type] || it.actor_type}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 whitespace-nowrap">
                    <span className="inline-flex items-center gap-1.5 font-medium text-slate-700">
                      {it.is_critical && <AlertTriangle size={13} className="text-rose-500 shrink-0" />}
                      {it.action_label}
                    </span>
                  </td>
                  <td className="px-4 py-3.5 text-slate-600 max-w-md">{it.summary || '—'}</td>
                  <td className="px-4 py-3.5 text-slate-400 tabular-nums text-xs whitespace-nowrap">{it.ip || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {pages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-100">
            <button
              disabled={page === 0}
              onClick={() => setPage(p => p - 1)}
              className="px-3.5 py-1.5 text-sm rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition-colors"
            >
              ← Oldingi
            </button>
            <span className="text-sm text-slate-500 tabular-nums">{page + 1} / {pages}</span>
            <button
              disabled={page + 1 >= pages}
              onClick={() => setPage(p => p + 1)}
              className="px-3.5 py-1.5 text-sm rounded-lg bg-slate-100 text-slate-600 disabled:opacity-40 hover:bg-slate-200 transition-colors"
            >
              Keyingi →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

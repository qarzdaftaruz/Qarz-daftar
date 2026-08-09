import { useState, useEffect } from 'react'
import { adminPromoApi } from '../../lib/api'
import { useTimedState } from '../../hooks/useTimedState'
import { Ticket, Plus, Trash2 } from 'lucide-react'

export default function AdminPromo() {
  const [promos, setPromos] = useState([])
  const [form, setForm]     = useState({ code: '', expires_at: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving]   = useState(false)
  const [error, setError]     = useTimedState('')

  const load = () => {
    adminPromoApi.list().then(r => setPromos(r.data)).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!form.code || !form.expires_at) { setError("Kod va muddatni kiriting"); return }
    setSaving(true); setError('')
    try {
      await adminPromoApi.create({ code: form.code.toUpperCase(), expires_at: form.expires_at })
      setForm({ code: '', expires_at: '' }); load()
    } catch (e) { setError(e.response?.data?.detail || 'Xato') }
    finally { setSaving(false) }
  }

  const del = async (id) => {
    if (!confirm("O'chirishni tasdiqlaysizmi?")) return
    await adminPromoApi.delete(id); load()
  }

  const inputCls = "px-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm outline-none focus:border-blue-500 focus:bg-white transition-all"

  return (
    <div className="p-6 lg:p-8 max-w-4xl animate-fade-in">
      <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight mb-5">Promo kodlar</h1>

      <div className="bg-white rounded-2xl border border-slate-200/60 p-6 mb-5 shadow-sm">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#2563EB,#6d28d9)' }}>
            <Ticket size={18} className="text-white" />
          </div>
          <p className="font-display font-semibold text-slate-900">Yangi promo kod</p>
        </div>
        {error && <p className="text-red-500 text-sm mb-3">{error}</p>}
        <div className="flex gap-3 flex-wrap">
          <input className={`${inputCls} flex-1 min-w-32 uppercase tracking-[0.2em] font-mono font-semibold`}
            placeholder="PROMO2025"
            value={form.code}
            onChange={e => setForm(s => ({ ...s, code: e.target.value.toUpperCase() }))} />
          <input type="datetime-local"
            className={`${inputCls} flex-1 min-w-44`}
            value={form.expires_at}
            onChange={e => setForm(s => ({ ...s, expires_at: e.target.value }))} />
          <button onClick={create} disabled={saving}
            className="px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold inline-flex items-center gap-1.5
                       hover:bg-blue-700 disabled:opacity-60 whitespace-nowrap transition-colors active:scale-[0.98]">
            <Plus size={16} /> {saving ? '...' : "Qo'shish"}
          </button>
        </div>
      </div>

      <div className="bg-white rounded-2xl border border-slate-200/60 overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              {['Kod', 'Muddat', 'Ishlatildi', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? [...Array(4)].map((_, i) => (
              <tr key={i} className="border-b border-slate-50">
                <td className="px-4 py-4"><div className="skeleton h-4 w-28" /></td>
                <td className="px-4 py-4"><div className="skeleton h-3 w-24" /></td>
                <td className="px-4 py-4"><div className="skeleton h-3 w-16" /></td>
                <td className="px-4 py-4 text-right"><div className="skeleton h-8 w-20 rounded-xl ml-auto" /></td>
              </tr>
            )) : promos.length === 0 ? (
              <tr><td colSpan={4} className="text-center py-16 text-slate-400">Promo kod yo'q</td></tr>
            ) : promos.map(p => (
              <tr key={p.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                <td className="px-4 py-3 font-mono font-bold tracking-[0.15em] text-blue-700">{p.code}</td>
                <td className="px-4 py-3 text-slate-500 text-xs">
                  <span className="tabular-nums">{new Date(p.expires_at).toLocaleDateString('uz')}</span>
                  {!p.is_active && <span className="ml-2 bg-red-100 text-red-600 px-1.5 py-0.5 rounded text-xs">O'chirilgan</span>}
                </td>
                <td className="px-4 py-3 text-slate-600 tabular-nums">{p.uses_count} marta</td>
                <td className="px-4 py-3 text-right">
                  {p.is_active && (
                    <button onClick={() => del(p.id)}
                      className="text-xs px-2.5 py-1.5 rounded-lg bg-red-100 text-red-700 hover:bg-red-200 inline-flex items-center gap-1 transition-colors">
                      <Trash2 size={13} /> O'chirish
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

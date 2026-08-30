import { useState, useEffect } from 'react'
import { adminUsersApi, errorMessage } from '../../lib/api'
import { Ban, RotateCcw, AlertTriangle, X } from 'lucide-react'

const AVATARS = [
  'linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%)',
  'linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)',
  'linear-gradient(135deg, #16A34A 0%, #15803D 100%)',
  'linear-gradient(135deg, #F59E0B 0%, #B45309 100%)',
  'linear-gradient(135deg, #EC4899 0%, #BE185D 100%)',
]

export default function AdminUsers() {
  const [users, setUsers]   = useState([])
  const [loading, setLoading] = useState(true)
  // Xato faqat konsolga tushib qolmasin — admin nima bo'lganini ko'rsin
  const [error, setError]   = useState('')
  const [busyId, setBusyId] = useState(null)

  const load = () => {
    adminUsersApi.list()
      .then(r => setUsers(r.data.users))
      .catch(e => setError(errorMessage(e, "Ro'yxat yuklanmadi")))
      .finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const toggle = async (u) => {
    setBusyId(u.id); setError('')
    try {
      if (u.is_blocked) await adminUsersApi.unblock(u.id)
      else await adminUsersApi.block(u.id)
      load()
    } catch (e) { setError(errorMessage(e, 'Amal bajarilmadi')) }
    finally { setBusyId(null) }
  }

  return (
    <div className="p-6 lg:p-8 animate-fade-in">
      <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight mb-5">
        Foydalanuvchilar <span className="text-slate-400 font-normal text-lg tabular-nums">({users.length})</span>
      </h1>
      {error && (
        <div className="mb-4 flex items-start gap-2 bg-rose-50 border border-rose-200 rounded-xl px-4 py-3">
          <AlertTriangle size={18} className="text-rose-600 shrink-0 mt-0.5" />
          <p className="text-sm text-rose-800 flex-1">{error}</p>
          <button onClick={() => setError('')} className="text-rose-400 hover:text-rose-600"><X size={16} /></button>
        </div>
      )}
      <div className="bg-white rounded-2xl border border-slate-200/60 overflow-hidden shadow-sm">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 border-b border-slate-100">
            <tr>
              {['Ism', 'Telegram ID', "Do'konlar", 'Amal'].map(h => (
                <th key={h} className="text-left px-4 py-3 font-semibold text-slate-500 text-xs uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? [...Array(6)].map((_, i) => (
              <tr key={i} className="border-b border-slate-50">
                <td className="px-4 py-4">
                  <div className="flex items-center gap-3">
                    <div className="skeleton w-9 h-9 rounded-full shrink-0" />
                    <div><div className="skeleton h-4 w-28 mb-2" /><div className="skeleton h-3 w-20" /></div>
                  </div>
                </td>
                <td className="px-4 py-4"><div className="skeleton h-3 w-24" /></td>
                <td className="px-4 py-4"><div className="skeleton h-3 w-6" /></td>
                <td className="px-4 py-4"><div className="skeleton h-8 w-24 rounded-xl" /></td>
              </tr>
            )) : users.length === 0 ? (
              <tr><td colSpan={4} className="text-center py-16 text-slate-400">Foydalanuvchi yo'q</td></tr>
            ) : users.map((u, i) => (
              <tr key={u.id} className="border-b border-slate-50 hover:bg-slate-50/60 transition-colors">
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="w-9 h-9 rounded-full flex items-center justify-center text-white font-bold text-sm shrink-0"
                      style={{ background: u.is_blocked ? 'linear-gradient(135deg,#cbd5e1,#94a3b8)' : AVATARS[i % AVATARS.length] }}
                    >
                      {u.full_name?.[0]?.toUpperCase() || '?'}
                    </div>
                    <div>
                      <p className={`font-semibold ${u.is_blocked ? 'text-slate-400 line-through' : 'text-slate-900'}`}>
                        {u.full_name}
                      </p>
                      <p className="text-xs text-slate-400">{u.phone}</p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500 tabular-nums">{u.telegram_id}</td>
                <td className="px-4 py-3 text-slate-600 tabular-nums">{u.shops_count}</td>
                <td className="px-4 py-3">
                  <button onClick={() => toggle(u)} disabled={busyId === u.id}
                    className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-2 rounded-xl transition-all active:scale-95 disabled:opacity-60
                      ${u.is_blocked
                        ? 'bg-green-600 text-white hover:bg-green-700 shadow-sm shadow-green-600/30'
                        : 'bg-rose-50 text-rose-600 ring-1 ring-rose-200 hover:bg-rose-100'}`}>
                    {u.is_blocked ? <><RotateCcw size={14} /> Blokdan chiqarish</> : <><Ban size={14} /> Bloklash</>}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

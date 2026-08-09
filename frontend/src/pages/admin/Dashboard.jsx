import { useState, useEffect } from 'react'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { Store, CheckCircle2, Clock, Ban, Users } from 'lucide-react'
import { adminDashApi } from '../../lib/api'

function Stat({ icon: Icon, label, value, from, to, shadow }) {
  return (
    <div className="bg-white rounded-2xl border border-slate-200/60 p-5 shadow-sm hover:shadow-md transition-shadow">
      <div
        className="w-11 h-11 rounded-xl flex items-center justify-center mb-3"
        style={{ background: `linear-gradient(135deg, ${from} 0%, ${to} 100%)`, boxShadow: `0 6px 16px ${shadow}` }}
      >
        <Icon size={20} className="text-white" />
      </div>
      <p className="font-display text-3xl font-bold text-slate-900 leading-none tabular-nums">{value ?? '—'}</p>
      <p className="text-sm text-slate-500 mt-1.5">{label}</p>
    </div>
  )
}

export default function AdminDashboard() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    adminDashApi.get().then(r => setData(r.data)).finally(() => setLoading(false))
  }, [])

  const s = data?.stats

  return (
    <div className="p-6 lg:p-8 animate-fade-in">
      <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight mb-6">Dashboard</h1>

      {loading ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-32" />)}
          </div>
          <div className="skeleton h-72 w-full" />
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
            <Stat icon={Store}        label="Jami do'konlar"   value={s?.total_shops} from="#3B82F6" to="#1D4ED8" shadow="rgba(37,99,235,0.35)" />
            <Stat icon={CheckCircle2} label="Faol"             value={s?.active}      from="#22C55E" to="#15803D" shadow="rgba(22,163,74,0.32)" />
            <Stat icon={Clock}        label="Kutilmoqda"       value={s?.pending}     from="#FBBF24" to="#D97706" shadow="rgba(217,119,6,0.32)" />
            <Stat icon={Ban}          label="Bloklangan"       value={s?.blocked}     from="#F87171" to="#DC2626" shadow="rgba(239,68,68,0.32)" />
            <Stat icon={Users}        label="Foydalanuvchilar" value={s?.total_users} from="#8B5CF6" to="#6D28D9" shadow="rgba(139,92,246,0.32)" />
          </div>

          {/* Oylik o'sish grafigi */}
          {data?.monthly_growth?.length > 0 && (
            <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm">
              <p className="font-display font-semibold text-slate-900 mb-5">Oylik do'konlar o'sishi</p>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={data.monthly_growth} margin={{ left: -18, right: 8, top: 4 }}>
                  <defs>
                    <linearGradient id="adminGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#2563EB" stopOpacity={0.28} />
                      <stop offset="95%" stopColor="#2563EB" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" />
                  <XAxis dataKey="month" tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 12, fill: '#94a3b8' }} axisLine={false} tickLine={false} allowDecimals={false} />
                  <Tooltip
                    formatter={(val) => [val + " ta", "Do'kon"]}
                    contentStyle={{ fontSize: 13, borderRadius: 12, border: 'none', boxShadow: '0 8px 28px rgba(15,23,42,0.14)' }}
                  />
                  <Area type="monotone" dataKey="shops" stroke="#2563EB" strokeWidth={2.5}
                    fill="url(#adminGrad)" dot={{ r: 3, fill: '#2563EB', strokeWidth: 0 }}
                    activeDot={{ r: 6, strokeWidth: 0, fill: '#2563EB' }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  )
}

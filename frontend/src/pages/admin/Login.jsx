import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminAuthApi, setAdminToken, errorMessage } from '../../lib/api'
import { useTimedState } from '../../hooks/useTimedState'
import { NotebookText, Lock, User } from 'lucide-react'

export default function AdminLogin({ superadmin }) {
  const [form, setForm]       = useState({ username: superadmin ? 'Superadmin' : '', password: '' })
  const [error, setError]     = useTimedState('')
  const [loading, setLoading] = useState(false)
  const [msg, setMsg]         = useTimedState('')
  const [forgotLoading, setForgotLoading] = useState(false)
  const navigate              = useNavigate()

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true); setError(''); setMsg('')
    try {
      const params = new URLSearchParams()
      params.append('username', form.username)
      params.append('password', form.password)
      const res = await adminAuthApi.login(params)
      setAdminToken(res.data.access_token)
      // Vaqtinchalik parol bilan kirilgan bo'lsa — darhol o'zgartirishga yo'naltiramiz
      navigate(res.data.must_change_password ? '/admin/profile' : '/admin', { replace: true })
    } catch (e) {
      // 429 (ko'p urinish) va boshqa xatolar aniq matn bilan ko'rsatiladi
      setError(errorMessage(e, "Login yoki parol noto'g'ri"))
    } finally { setLoading(false) }
  }

  const forgot = async () => {
    if (!form.username.trim()) { setError('Avval loginingizni kiriting'); return }
    setForgotLoading(true); setError(''); setMsg('')
    try {
      await adminAuthApi.forgotPassword(form.username.trim())
      setMsg("✅ Agar bunday hisob mavjud bo'lsa, Telegram'ga so'rov yuborildi.")
    } catch (e) {
      setError(errorMessage(e))
    } finally { setForgotLoading(false) }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
      style={{ background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #312e81 100%)' }}
    >
      {/* Dekorativ doiralar */}
      <div className="absolute -top-24 -right-24 w-80 h-80 rounded-full" style={{ background: 'rgba(37,99,235,0.18)' }} />
      <div className="absolute -bottom-32 -left-20 w-96 h-96 rounded-full" style={{ background: 'rgba(109,40,217,0.14)' }} />

      <div className="w-full max-w-sm relative animate-slide-up">
        <div className="text-center mb-8">
          <div
            className="w-16 h-16 rounded-2xl mx-auto mb-4 flex items-center justify-center"
            style={{ background: 'linear-gradient(135deg, #2563EB 0%, #6d28d9 100%)', boxShadow: '0 12px 36px rgba(37,99,235,0.5)' }}
          >
            <NotebookText size={30} className="text-white" />
          </div>
          <h1 className="font-display text-2xl font-bold text-white tracking-tight">Qarz Daftar</h1>
          <p className="text-slate-400 text-sm mt-1">{superadmin ? 'Super admin panelga kirish' : 'Admin panelga kirish'}</p>
        </div>

        <div className="bg-white rounded-3xl shadow-2xl p-7">
          <form onSubmit={submit} className="space-y-4">
            {error && (
              <div className="bg-red-50 border border-red-100 text-red-600 text-sm px-4 py-3 rounded-xl">
                {error}
              </div>
            )}
            {msg && (
              <div className="bg-green-50 border border-green-100 text-green-700 text-sm px-4 py-3 rounded-xl">
                {msg}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Login</label>
              <div className="relative">
                <User size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm
                             outline-none focus:border-blue-500 focus:bg-white transition-all"
                  placeholder="admin"
                  value={form.username}
                  onChange={e => setForm(s => ({ ...s, username: e.target.value }))}
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Parol</label>
              <div className="relative">
                <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="password"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm
                             outline-none focus:border-blue-500 focus:bg-white transition-all"
                  placeholder="••••••••"
                  value={form.password}
                  onChange={e => setForm(s => ({ ...s, password: e.target.value }))}
                />
              </div>
            </div>
            <button
              type="submit" disabled={loading}
              className="w-full py-3 rounded-xl font-semibold text-sm text-white transition-all
                         active:scale-[0.98] disabled:opacity-60"
              style={{ background: 'linear-gradient(135deg, #2563EB 0%, #1d4ed8 100%)', boxShadow: '0 6px 18px rgba(37,99,235,0.4)' }}
            >
              {loading ? 'Kirilmoqda…' : 'Kirish'}
            </button>

            <button
              type="button" onClick={forgot} disabled={forgotLoading}
              className="w-full text-center text-sm text-slate-500 hover:text-blue-600 transition-colors disabled:opacity-60"
            >
              {forgotLoading ? 'Yuborilmoqda…' : 'Parolni unutdingizmi?'}
            </button>
          </form>
        </div>

        <p className="text-center text-slate-500 text-xs mt-6">© Qarz Daftar — boshqaruv paneli</p>
      </div>
    </div>
  )
}

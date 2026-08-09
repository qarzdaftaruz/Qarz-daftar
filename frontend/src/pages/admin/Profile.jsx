import { useState, useEffect } from 'react'
import { adminProfileApi, adminAuthApi, clearAdminToken, errorMessage } from '../../lib/api'
import { useNavigate } from 'react-router-dom'
import { useTimedState } from '../../hooks/useTimedState'
import { KeyRound, UserCog, LifeBuoy } from 'lucide-react'

const inputCls = "w-full px-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm outline-none focus:border-blue-500 focus:bg-white transition-all"
const primaryBtn = "px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 disabled:opacity-60 transition-colors active:scale-[0.98]"

export default function AdminProfile() {
  const navigate = useNavigate()
  const [me, setMe] = useState(null)

  const [pwd, setPwd] = useState({ current_password: '', new_password: '' })
  const [pwdSaving, setPwdSaving] = useState(false)
  const [pwdMsg, setPwdMsg] = useTimedState('')

  const [uname, setUname] = useState({ current_password: '', new_username: '' })
  const [unameSaving, setUnameSaving] = useState(false)
  const [unameMsg, setUnameMsg] = useTimedState('')

  const [botLoading, setBotLoading] = useState(false)
  const [botMsg, setBotMsg] = useTimedState('')

  useEffect(() => {
    adminProfileApi.me().then(r => setMe(r.data)).catch(() => {})
  }, [])

  const changePassword = async () => {
    if (!pwd.current_password || !pwd.new_password) {
      setPwdMsg('Barcha maydonlarni to\'ldiring'); return
    }
    setPwdSaving(true); setPwdMsg('')
    try {
      await adminProfileApi.changePassword(pwd)
      // Parol o'zgarganda barcha sessiyalar bekor bo'ladi — qaytadan kirish kerak
      setPwdMsg('✅ Parol o\'zgartirildi. Qayta kiring…')
      setPwd({ current_password: '', new_password: '' })
      setTimeout(() => {
        clearAdminToken()
        navigate('/admin/login', { replace: true })
      }, 1500)
    } catch (e) {
      setPwdMsg('❌ ' + errorMessage(e))
    } finally { setPwdSaving(false) }
  }

  const changeUsername = async () => {
    if (!uname.current_password || !uname.new_username) {
      setUnameMsg('Barcha maydonlarni to\'ldiring'); return
    }
    setUnameSaving(true); setUnameMsg('')
    try {
      await adminProfileApi.changeUsername(uname)
      setUnameMsg('✅ Login o\'zgartirildi. Qayta kiring…')
      setTimeout(() => {
        clearAdminToken()
        navigate('/admin/login', { replace: true })
      }, 1500)
    } catch (e) {
      setUnameMsg('❌ ' + errorMessage(e))
    } finally { setUnameSaving(false) }
  }

  const requestBotReset = async () => {
    setBotLoading(true); setBotMsg('')
    try {
      await adminAuthApi.requestPasswordChange()
      setBotMsg('✅ Botdan yangi parolni kiriting')
    } catch (e) {
      setBotMsg(e.response?.data?.detail || '❌ Xato')
    } finally { setBotLoading(false) }
  }

  return (
    <div className="p-6 lg:p-8 max-w-2xl space-y-5 animate-fade-in">
      {/* Profil sarlavhasi */}
      {!me ? (
        <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm flex items-center gap-4">
          <div className="skeleton w-14 h-14 rounded-2xl shrink-0" />
          <div><div className="skeleton h-5 w-32 mb-2" /><div className="skeleton h-4 w-20" /></div>
        </div>
      ) : (
        <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm flex items-center gap-4">
          <div
            className="w-14 h-14 rounded-2xl flex items-center justify-center text-white font-display font-bold text-xl shrink-0"
            style={{ background: 'linear-gradient(135deg,#2563EB,#6d28d9)', boxShadow: '0 8px 22px rgba(37,99,235,0.4)' }}
          >
            {me.username?.[0]?.toUpperCase() || 'A'}
          </div>
          <div>
            <h1 className="font-display text-xl font-bold text-slate-900 tracking-tight">{me.username}</h1>
            {me.is_super && <span className="inline-block mt-1 text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">Super admin</span>}
          </div>
        </div>
      )}

      {/* Parol o'zgartirish */}
      <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm">
        <div className="flex items-center gap-2.5 mb-4">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#2563EB,#1d4ed8)' }}>
            <KeyRound size={18} className="text-white" />
          </div>
          <p className="font-display font-semibold text-slate-900">Parolni o'zgartirish</p>
        </div>
        <div className="space-y-2.5">
          <input type="password" className={inputCls} placeholder="Joriy parol"
            value={pwd.current_password}
            onChange={e => setPwd(s => ({ ...s, current_password: e.target.value }))} />
          <input type="password" className={inputCls} placeholder="Yangi parol"
            value={pwd.new_password}
            onChange={e => setPwd(s => ({ ...s, new_password: e.target.value }))} />
          {pwdMsg && <p className="text-sm">{pwdMsg}</p>}
          <button onClick={changePassword} disabled={pwdSaving} className={primaryBtn}>
            {pwdSaving ? '...' : "O'zgartirish"}
          </button>
        </div>
      </div>

      {/* Login o'zgartirish */}
      <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm">
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#8B5CF6,#6d28d9)' }}>
            <UserCog size={18} className="text-white" />
          </div>
          <p className="font-display font-semibold text-slate-900">Loginni o'zgartirish</p>
        </div>
        <p className="text-sm text-slate-500 mb-4 mt-2">O'zgartirgandan keyin qayta kirishingiz kerak bo'ladi.</p>
        <div className="space-y-2.5">
          <input type="password" className={inputCls} placeholder="Joriy parol"
            value={uname.current_password}
            onChange={e => setUname(s => ({ ...s, current_password: e.target.value }))} />
          <input className={inputCls} placeholder="Yangi login"
            value={uname.new_username}
            onChange={e => setUname(s => ({ ...s, new_username: e.target.value }))} />
          {unameMsg && <p className="text-sm">{unameMsg}</p>}
          <button onClick={changeUsername} disabled={unameSaving} className={primaryBtn}>
            {unameSaving ? '...' : "O'zgartirish"}
          </button>
        </div>
      </div>

      {/* Botdan zaxira tiklash */}
      <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm">
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#475569,#1e293b)' }}>
            <LifeBuoy size={18} className="text-white" />
          </div>
          <p className="font-display font-semibold text-slate-900">Parolni unutdingizmi?</p>
        </div>
        <p className="text-sm text-slate-500 mb-4 mt-2">
          Telegram orqali yangi parol o'rnatish (faqat Telegram ID sozlangan bo'lsa ishlaydi).
        </p>
        {botMsg && <p className="text-sm mb-3">{botMsg}</p>}
        <button onClick={requestBotReset} disabled={botLoading}
          className="px-5 py-2.5 bg-slate-800 text-white rounded-xl text-sm font-semibold hover:bg-slate-900 disabled:opacity-60 transition-colors active:scale-[0.98]">
          {botLoading ? '...' : "🔐 Botdan parol o'zgartirish"}
        </button>
      </div>
    </div>
  )
}

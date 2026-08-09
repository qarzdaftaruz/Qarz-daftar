import { useState, useEffect } from 'react'
import { adminSettingsApi, adminAdminsApi, adminProfileApi, errorMessage } from '../../lib/api'
import { useTimedState } from '../../hooks/useTimedState'
import { Settings as SettingsIcon, ShieldCheck, Plus, Trash2 } from 'lucide-react'

const inputCls = "w-full px-3.5 py-2.5 bg-slate-50 border-2 border-transparent rounded-xl text-sm outline-none focus:border-blue-500 focus:bg-white transition-all"
const primaryBtn = "px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 disabled:opacity-60 transition-colors active:scale-[0.98]"

export default function AdminSettings() {
  const [settings, setSettings] = useState(null)
  const [saving, setSaving]     = useState(false)
  const [msg, setMsg]           = useTimedState('')

  // Adminlarni boshqarish faqat super adminda — backend ham shuni talab qiladi
  const [isSuper, setIsSuper]   = useState(false)
  const [admins, setAdmins]     = useState([])
  const [newAdmin, setNewAdmin] = useState({ username: '', password: '', telegram_id: '' })
  const [addMsg, setAddMsg]     = useTimedState('')
  const [addLoading, setAddLoading] = useState(false)

  useEffect(() => {
    adminSettingsApi.get().then(r => setSettings(r.data)).catch(() => {})
    adminProfileApi.me().then(r => {
      const su = !!r.data.is_super
      setIsSuper(su)
      if (su) loadAdmins()
    }).catch(() => {})
  }, [])

  const loadAdmins = () => {
    adminAdminsApi.list().then(r => setAdmins(r.data)).catch(() => {})
  }

  const saveSettings = async () => {
    setSaving(true); setMsg('')
    try { await adminSettingsApi.update(settings); setMsg('✅ Saqlandi') }
    catch (e) { setMsg('❌ ' + errorMessage(e)) }
    finally { setSaving(false) }
  }

  const addAdmin = async () => {
    if (!newAdmin.username || !newAdmin.password) { setAddMsg('Login va parol kiritilishi shart'); return }
    setAddLoading(true); setAddMsg('')
    try {
      await adminAdminsApi.create({
        username: newAdmin.username,
        password: newAdmin.password,
        telegram_id: newAdmin.telegram_id ? +newAdmin.telegram_id : null
      })
      setNewAdmin({ username: '', password: '', telegram_id: '' })
      setAddMsg('✅ Admin qo\'shildi')
      loadAdmins()
    } catch (e) { setAddMsg('❌ ' + errorMessage(e)) }
    finally { setAddLoading(false) }
  }

  const deleteAdmin = async (id) => {
    if (!confirm("Bu adminni o'chirasizmi?")) return
    try { await adminAdminsApi.delete(id); loadAdmins() }
    catch (e) { alert(errorMessage(e)) }
  }

  if (!settings) return (
    <div className="p-6 lg:p-8 max-w-2xl space-y-5">
      <div className="skeleton h-8 w-40" />
      <div className="skeleton h-64 w-full rounded-2xl" />
      <div className="skeleton h-72 w-full rounded-2xl" />
    </div>
  )

  return (
    <div className="p-6 lg:p-8 max-w-2xl space-y-5 animate-fade-in">
      <h1 className="font-display text-2xl font-bold text-slate-900 tracking-tight">Sozlamalar</h1>

      {/* Tizim sozlamalari */}
      <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm">
        <div className="flex items-center gap-2.5 mb-5">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#2563EB,#1d4ed8)' }}>
            <SettingsIcon size={18} className="text-white" />
          </div>
          <p className="font-display font-semibold text-slate-900">Tizim</p>
        </div>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Eslatma vaqti</label>
            <div className="flex items-center gap-2">
              <input type="number" min={0} max={23}
                className={`${inputCls} w-20 tabular-nums`}
                value={settings.reminder_hour}
                onChange={e => setSettings(s => ({ ...s, reminder_hour: +e.target.value }))} />
              <span className="text-slate-400 font-bold">:</span>
              <input type="number" min={0} max={59}
                className={`${inputCls} w-20 tabular-nums`}
                value={settings.reminder_minute}
                onChange={e => setSettings(s => ({ ...s, reminder_minute: +e.target.value }))} />
              <span className="text-sm text-slate-400">soat</span>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Arxiv muddati (oy)</label>
            <input type="number" min={1}
              className={`${inputCls} tabular-nums`}
              value={settings.archive_duration_months}
              onChange={e => setSettings(s => ({ ...s, archive_duration_months: +e.target.value }))} />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Asosiy admin Telegram ID</label>
            <p className="text-xs text-slate-400 mb-1.5">Do'kondorlardan kelgan xabarlar shu ID ga boradi</p>
            <input type="number"
              className={`${inputCls} tabular-nums`}
              value={settings.admin_telegram_id || ''}
              onChange={e => setSettings(s => ({ ...s, admin_telegram_id: +e.target.value }))} />
          </div>
          {msg && <p className="text-sm">{msg}</p>}
          <button onClick={saveSettings} disabled={saving} className={primaryBtn}>
            {saving ? 'Saqlanmoqda…' : 'Saqlash'}
          </button>
        </div>
      </div>

      {/* Adminlar — faqat super admin uchun */}
      {isSuper && (
      <div className="bg-white rounded-2xl border border-slate-200/60 p-6 shadow-sm">
        <div className="flex items-center gap-2.5 mb-1">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'linear-gradient(135deg,#16A34A,#15803d)' }}>
            <ShieldCheck size={18} className="text-white" />
          </div>
          <p className="font-display font-semibold text-slate-900">Adminlar</p>
        </div>
        <p className="text-sm text-slate-500 mb-4 mt-2">
          Qo'shimcha adminlar tizimni kuzatish uchun — asosiy qaror qabul qiluvchi siz qolasiz.
        </p>

        <div className="space-y-1 mb-5">
          {admins.map(a => (
            <div key={a.id} className="flex items-center justify-between py-2.5 border-b border-slate-50 last:border-0">
              <div>
                <p className="text-sm font-semibold text-slate-900">{a.username}
                  {a.is_super && <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">Super</span>}
                </p>
                {a.telegram_id && <p className="text-xs text-slate-400 tabular-nums">TG: {a.telegram_id}</p>}
              </div>
              {!a.is_super && (
                <button onClick={() => deleteAdmin(a.id)}
                  className="text-xs px-2.5 py-1.5 rounded-lg bg-red-100 text-red-700 hover:bg-red-200 inline-flex items-center gap-1 transition-colors">
                  <Trash2 size={13} /> O'chirish
                </button>
              )}
            </div>
          ))}
        </div>

        <p className="text-sm font-semibold text-slate-700 mb-3">Yangi admin qo'shish</p>
        {addMsg && <p className="text-sm mb-3">{addMsg}</p>}
        <div className="space-y-2.5">
          <input className={inputCls} placeholder="Username" value={newAdmin.username}
            onChange={e => setNewAdmin(s => ({ ...s, username: e.target.value }))} />
          <input type="password" className={inputCls} placeholder="Parol" value={newAdmin.password}
            onChange={e => setNewAdmin(s => ({ ...s, password: e.target.value }))} />
          <input type="number" className={`${inputCls} tabular-nums`} placeholder="Telegram ID (ixtiyoriy)" value={newAdmin.telegram_id}
            onChange={e => setNewAdmin(s => ({ ...s, telegram_id: e.target.value }))} />
          <button onClick={addAdmin} disabled={addLoading} className={`${primaryBtn} inline-flex items-center gap-1.5`}>
            <Plus size={16} /> {addLoading ? '...' : "Qo'shish"}
          </button>
          <p className="text-xs text-slate-400">
            Parol kamida 8 ta belgi, harf va raqam aralash bo'lishi kerak.
          </p>
        </div>
      </div>
      )}
    </div>
  )
}

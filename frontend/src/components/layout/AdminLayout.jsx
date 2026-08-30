import { useState, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Store, Users, Ticket,
  UserCircle, Settings, LogOut, NotebookText, Crown, ScrollText, MessageSquare,
} from 'lucide-react'
import { adminProfileApi, adminSupportApi, clearAdminToken } from '../../lib/api'

const baseNav = [
  { to: '/admin',          icon: LayoutDashboard, label: 'Dashboard',        end: true },
  { to: '/admin/shops',    icon: Store,           label: "Do'konlar"                   },
  { to: '/admin/users',    icon: Users,           label: 'Foydalanuvchilar'            },
  { to: '/admin/promo',    icon: Ticket,          label: 'Promo kodlar'                },
  { to: '/admin/support',  icon: MessageSquare,   label: 'Xabarlar',       badge: true },
  { to: '/admin/audit',    icon: ScrollText,      label: 'Amallar tarixi'              },
  { to: '/admin/profile',  icon: UserCircle,      label: 'Profil'                      },
  { to: '/admin/settings', icon: Settings,        label: 'Sozlamalar'                  },
]

export default function AdminLayout({ children }) {
  const navigate = useNavigate()
  const [isSuper, setIsSuper] = useState(false)
  const [unread, setUnread]   = useState(0)

  useEffect(() => {
    adminProfileApi.me().then(r => setIsSuper(!!r.data.is_super)).catch(() => {})
    // O'qilmagan murojaatlar soni — menyuda ko'rinib tursin
    adminSupportApi.list({ unread_only: true, limit: 1 })
      .then(r => setUnread(r.data.unread || 0))
      .catch(() => {})
  }, [])

  // Super admin uchun qo'shimcha "Super qidiruv" bo'limi (Dashboard'dan keyin)
  const nav = isSuper
    ? [baseNav[0], { to: '/admin/super', icon: Crown, label: 'Super qidiruv' }, ...baseNav.slice(1)]
    : baseNav

  const logout = () => {
    clearAdminToken()
    navigate('/admin/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen" style={{ background: '#F1F5F9' }}>
      {/* Sidebar */}
      <aside
        className="w-60 flex flex-col fixed h-full z-10 text-slate-300"
        style={{ background: 'linear-gradient(180deg, #0f172a 0%, #131c33 100%)' }}
      >
        <div className="px-5 py-5 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div
              className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'linear-gradient(135deg, #2563EB 0%, #6d28d9 100%)', boxShadow: '0 4px 14px rgba(37,99,235,0.45)' }}
            >
              <NotebookText size={18} className="text-white" />
            </div>
            <div>
              <p className="font-display font-bold text-white text-sm leading-none">Qarz Daftar</p>
              <p className="text-[11px] text-slate-400 mt-1 tracking-wide">Admin panel</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {nav.map(({ to, icon: Icon, label, end, badge }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all duration-200
                 ${isActive
                   ? 'bg-white/10 text-white shadow-[inset_3px_0_0_0_#2563EB]'
                   : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                 }`
              }
            >
              {({ isActive }) => (
                <>
                  <Icon size={18} strokeWidth={isActive ? 2.4 : 1.9} className="shrink-0" />
                  <span className="flex-1">{label}</span>
                  {badge && unread > 0 && (
                    <span className="text-[11px] font-bold px-1.5 min-w-[20px] h-5 inline-flex items-center justify-center rounded-full bg-rose-500 text-white tabular-nums">
                      {unread > 99 ? '99+' : unread}
                    </span>
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-white/10">
          <button
            onClick={logout}
            className="w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm
                       font-medium text-red-400 hover:bg-red-500/10 transition-all duration-200"
          >
            <LogOut size={18} strokeWidth={1.9} /> Chiqish
          </button>
        </div>
      </aside>

      {/* Content */}
      <main className="flex-1 ml-60 overflow-y-auto min-h-screen">
        {children}
      </main>
    </div>
  )
}

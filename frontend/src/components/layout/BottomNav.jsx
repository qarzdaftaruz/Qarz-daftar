import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Users, BarChart2, User } from 'lucide-react'

const tabs = [
  { to: '/',        icon: LayoutDashboard, label: 'Bosh' },
  { to: '/clients', icon: Users,           label: 'Mijozlar' },
  { to: '/stats',   icon: BarChart2,       label: 'Statistika' },
  { to: '/profile', icon: User,            label: 'Profil' },
]

export default function BottomNav() {
  return (
    <nav
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 40,
        background: 'var(--tg-theme-bg-color, #fff)',
        borderTop: '0.5px solid rgba(0,0,0,0.08)',
        boxShadow: '0 -4px 24px rgba(0,0,0,0.06)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', padding: '4px 8px' }}>
        {tabs.map(({ to, icon: Icon, label }) => (
          <NavLink key={to} to={to} end={to === '/'} style={{ flex: 1, textDecoration: 'none' }}>
            {({ isActive }) => (
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                  padding: '8px 4px',
                  margin: '0 2px',
                  borderRadius: 16,
                  transition: 'background 0.15s ease',
                  background: isActive
                    ? 'rgba(37, 99, 235, 0.12)'
                    : 'transparent',
                }}
              >
                <Icon
                  size={22}
                  strokeWidth={isActive ? 2.5 : 1.8}
                  style={{
                    color: isActive ? '#2563EB' : 'var(--tg-theme-hint-color, #64748B)',
                    transform: isActive ? 'scale(1.1)' : 'scale(1)',
                    transition: 'transform 0.15s cubic-bezier(0.22, 1, 0.36, 1), color 0.15s ease',
                  }}
                />
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: isActive ? 700 : 500,
                    lineHeight: 1,
                    color: isActive ? '#2563EB' : 'var(--tg-theme-hint-color, #64748B)',
                    transition: 'color 0.15s ease, font-weight 0.15s ease',
                  }}
                >
                  {label}
                </span>
              </div>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  )
}

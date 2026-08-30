import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'

/**
 * lazyWithRetry — yangi deploy'dan keyin brauzerda eski chunk nomi qolib,
 * dinamik import muvaffaqiyatsiz tugasa, bir marta sahifani qayta yuklaydi.
 * Bu "sahifa ochilmayapti, xato ham yo'q" muammosini bartaraf etadi.
 */
const RELOAD_KEY = 'chunk-reload-once'
function lazyWithRetry(factory) {
  return lazy(async () => {
    try {
      const mod = await factory()
      sessionStorage.removeItem(RELOAD_KEY)
      return mod
    } catch (err) {
      if (!sessionStorage.getItem(RELOAD_KEY)) {
        sessionStorage.setItem(RELOAD_KEY, '1')
        window.location.reload()
        return new Promise(() => {}) // qayta yuklanmaguncha kutamiz
      }
      throw err
    }
  })
}

// TMA pages — tez-tez ishlatiladigan asosiy ekranlar (eager)
import { AuthProvider, useAuth } from './hooks/useAuth'
import { hasValidAdminToken } from './lib/api'
import { useNoIndex } from './hooks/useNoIndex'
import { tma } from './lib/tma'
import BottomNav        from './components/layout/BottomNav'
import Dashboard        from './pages/owner/Dashboard'
import Clients          from './pages/owner/Clients'
import ClientDetail     from './pages/owner/ClientDetail'

/**
 * TEZLIK: quyidagi ekranlar birinchi ochilishda deyarli hech qachon
 * kerak bo'lmaydi — do'kondor «Do'konlar»ni, qarzdor esa «Mijozlar»ni
 * ko'rmaydi. Ilgari hammasi bitta boshlang'ich bundle'da edi va har bir
 * foydalanuvchi keraksiz kodni yuklab olardi.
 */
const DebtorOverview   = lazyWithRetry(() => import('./pages/debtor/Overview'))
const ShopStatusScreen = lazyWithRetry(() => import('./pages/Pending'))
const NewShop          = lazyWithRetry(() => import('./pages/NewShop'))
const Profile          = lazyWithRetry(() => import('./pages/Profile'))

// Recharts'ga bog'liq ekranlar — kerak bo'lganda yuklanadi (lazy + retry)
const Stats            = lazyWithRetry(() => import('./pages/owner/Stats'))
const DebtorShopDetail = lazyWithRetry(() => import('./pages/debtor/ShopDetail'))

// Admin panel — TMA boshlang'ich bundle'iga kirmaydi (lazy + retry)
const AdminLayout    = lazyWithRetry(() => import('./components/layout/AdminLayout'))
const AdminLogin     = lazyWithRetry(() => import('./pages/admin/Login'))
const AdminDashboard = lazyWithRetry(() => import('./pages/admin/Dashboard'))
const AdminShops     = lazyWithRetry(() => import('./pages/admin/Shops'))
const AdminSuper     = lazyWithRetry(() => import('./pages/admin/Super'))
const AdminUsers     = lazyWithRetry(() => import('./pages/admin/Users'))
const AdminPromo     = lazyWithRetry(() => import('./pages/admin/Promo'))
const AdminAudit     = lazyWithRetry(() => import('./pages/admin/Audit'))
const AdminSupport   = lazyWithRetry(() => import('./pages/admin/Support'))
const AdminSettings  = lazyWithRetry(() => import('./pages/admin/Settings'))
const AdminProfile   = lazyWithRetry(() => import('./pages/admin/Profile'))

// ─── Admin guard ─────────────────────────────────────────────────────────────
// Token muddati ham tekshiriladi — muddati o'tgan token bilan panel
// ochilib, keyin har bir so'rovda 401 chiqishining oldini oladi.
function AdminGuard({ children }) {
  const location = useLocation()
  return hasValidAdminToken()
    ? children
    : <Navigate to="/admin/login" replace state={{ from: location.pathname }} />
}

function AdminContentFallback() {
  return (
    <div className="flex items-center justify-center py-32">
      <div className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
    </div>
  )
}

function AdminRoutes() {
  // Admin panel qidiruv tizimlarida chiqmasligi kerak
  useNoIndex()
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="login" element={<AdminLogin />} />
        <Route path="*" element={
          <AdminGuard>
            <AdminLayout>
              {/* Ichki Suspense — tab almashganda sidebar joyida qoladi */}
              <Suspense fallback={<AdminContentFallback />}>
                <Routes>
                  <Route index           element={<AdminDashboard />} />
                  <Route path="super"    element={<AdminSuper />} />
                  <Route path="shops"    element={<AdminShops />} />
                  <Route path="users"    element={<AdminUsers />} />
                  <Route path="promo"    element={<AdminPromo />} />
                  <Route path="audit"    element={<AdminAudit />} />
                  <Route path="support"  element={<AdminSupport />} />
                  <Route path="profile"  element={<AdminProfile />} />
                  <Route path="settings" element={<AdminSettings />} />
                </Routes>
              </Suspense>
            </AdminLayout>
          </AdminGuard>
        } />
      </Routes>
    </Suspense>
  )
}

// ─── Helper screens ───────────────────────────────────────────────────────────

function Spinner() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-3"
      style={{ background: 'var(--tg-theme-bg-color, #fff)' }}>
      <div className="w-9 h-9 rounded-full border-2 border-blue-500 border-t-transparent animate-spin" />
    </div>
  )
}

function NeedBotScreen({
  title = 'Botdan boshlang',
  text = <>Tizimdan foydalanish uchun avval botda <b>/start</b> bosib, raqamingizni ulashing</>,
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center"
      style={{ background: 'var(--tg-theme-bg-color, #fff)' }}>
      <p className="text-5xl mb-5">🤖</p>
      <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--tg-theme-text-color)' }}>
        {title}
      </h1>
      <p className="text-sm leading-relaxed mb-6 max-w-xs" style={{ color: 'var(--tg-theme-hint-color)' }}>
        {text}
      </p>
      <a
        href="https://t.me/Qarzdaftaruzbotbot"
        className="px-6 py-3 rounded-xl text-white font-medium text-sm"
        style={{ background: 'var(--tg-theme-button-color, #2678b6)' }}
      >
        Botga o'tish →
      </a>
    </div>
  )
}

function ErrorScreen({ text, onRetry }) {
  return (
    <div className="flex items-center justify-center min-h-screen px-6 text-center"
      style={{ background: 'var(--tg-theme-bg-color, #fff)' }}>
      <div>
        <p className="text-4xl mb-4">⚠️</p>
        <h1 className="text-xl font-bold mb-2" style={{ color: 'var(--tg-theme-text-color)' }}>
          Ochib bo'lmadi
        </h1>
        <p className="text-sm mb-6 max-w-xs mx-auto leading-relaxed" style={{ color: 'var(--tg-theme-hint-color)' }}>
          {text || 'Internet aloqasini tekshiring'}
        </p>
        {onRetry && (
          <button onClick={onRetry} className="px-6 py-3 rounded-xl text-white font-medium text-sm"
            style={{ background: 'var(--tg-theme-button-color, #2678b6)' }}>
            Qayta urinish
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Owner / Debtor route groups ──────────────────────────────────────────────

function OwnerRoutes() {
  return (
    <>
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/"            element={<Dashboard />} />
          <Route path="/clients"     element={<Clients />} />
          <Route path="/clients/:id" element={<ClientDetail />} />
          <Route path="/stats"       element={<Stats />} />
          <Route path="/profile"     element={<Profile />} />
          <Route path="*"            element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      <BottomNav />
    </>
  )
}

function DebtorRoutes() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/debtor"         element={<DebtorOverview />} />
        <Route path="/debtor/:shopId" element={<DebtorShopDetail />} />
        <Route path="/profile"        element={<Profile />} />
        <Route path="*"               element={<Navigate to="/debtor" replace />} />
      </Routes>
    </Suspense>
  )
}

// ─── TMA root logic ───────────────────────────────────────────────────────────

function TMARoutes() {
  const location = useLocation()
  const auth = useAuth()

  // Ilova Telegram tashqarisida ochilgan (masalan Google natijasidan).
  // Ilgari bunda "Ulanish xatosi" chiqardi — endi aniq yo'riqnoma beriladi.
  if (!tma.isInTelegram && import.meta.env.PROD) {
    return (
      <NeedBotScreen
        title="Telegram orqali oching"
        text="Qarz Daftar — Telegram ilovasi. Davom etish uchun botni oching."
      />
    )
  }

  // /new-shop har doim ochiq — bot deep-link va selector orqali keladi
  if (location.pathname === '/new-shop') {
    return auth.loading ? <Spinner /> : (
      <Suspense fallback={<Spinner />}>
        <NewShop standalone={auth.shops.length === 0 && !auth.isDebtor} />
      </Suspense>
    )
  }

  if (auth.loading) return <Spinner />
  if (auth.error) return <ErrorScreen text={auth.errorText} onRetry={auth.refresh} />
  if (!auth.hasAccount) return <NeedBotScreen />

  const hasAnyShop = auth.shops.length > 0

  // Hech narsa yo'q — to'g'ridan-to'g'ri do'kon ochish formasi
  if (!hasAnyShop && !auth.isDebtor) {
    return <Suspense fallback={<Spinner />}><NewShop standalone /></Suspense>
  }

  // Faol do'kon yo'q, qarzdor ham emas — holat ekrani
  if (!auth.canBeOwner && !auth.isDebtor) {
    return <Suspense fallback={<Spinner />}><ShopStatusScreen /></Suspense>
  }

  return auth.view === 'owner' ? <OwnerRoutes /> : <DebtorRoutes />
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <Routes>
      <Route path="/superadmin/login" element={
        <Suspense fallback={<Spinner />}><AdminLogin superadmin /></Suspense>
      } />
      <Route path="/superadmin/*" element={<Navigate to="/admin" replace />} />
      <Route path="/admin/*" element={<AdminRoutes />} />
      <Route path="/*" element={
        <AuthProvider>
          <TMARoutes />
        </AuthProvider>
      } />
    </Routes>
  )
}

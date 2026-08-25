import axios from 'axios'

/**
 * Backend manzili.
 *
 * Vercel'da frontend va Railway'dagi backend — turli domenlar.
 * Shuning uchun `/api` nisbiy yo'l ishlamaydi: VITE_API_URL orqali
 * to'liq manzil beriladi (Vercel → Settings → Environment Variables).
 * Lokalda bo'sh qoldirilsa, Vite proxy'si `/api` ni 8000-portga uzatadi.
 */
const RAW_BASE = (import.meta.env.VITE_API_URL || '').trim().replace(/\/+$/, '')

if (import.meta.env.PROD && !RAW_BASE) {
  // Deploy paytida sezilmay qolmasligi uchun ochiq ogohlantirish
  console.warn('[api] VITE_API_URL o‘rnatilmagan — so‘rovlar shu domenga ketadi.')
}

export const API_BASE = RAW_BASE

const TIMEOUT = 20000

function makeClient(path) {
  return axios.create({
    baseURL: `${RAW_BASE}${path}`,
    timeout: TIMEOUT,
    // Cookie ishlatilmaydi — token Authorization header'da
    withCredentials: false,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** Backend xatosini foydalanuvchiga ko'rsatiladigan matnga aylantiradi. */
export function errorMessage(err, fallback = 'Xato yuz berdi') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return "Yuborilgan ma'lumot noto'g'ri"
  if (err?.code === 'ECONNABORTED') return 'Server javob bermadi. Qayta urinib ko‘ring.'
  if (!err?.response) return 'Internet aloqasi yo‘q'
  if (err.response.status === 429) return 'Juda ko‘p urinish. Biroz kuting.'
  if (err.response.status >= 500) return 'Serverda xatolik. Keyinroq urinib ko‘ring.'
  return fallback
}

// ─── TMA (Mini App) ──────────────────────────────────────────────────────────
const tmaApi = makeClient('/api')

tmaApi.interceptors.request.use(cfg => {
  const token = sessionStorage.getItem('tma_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

tmaApi.interceptors.response.use(
  res => res,
  err => {
    // 401 — sessiya tugadi. Qayta yuklash initData bilan yangi token oladi.
    // Cheksiz reload halqasidan himoya: 10 soniyada bir marta.
    if (err.response?.status === 401) {
      sessionStorage.removeItem('tma_token')
      const last = Number(sessionStorage.getItem('tma_reload_at') || 0)
      if (Date.now() - last > 10000) {
        sessionStorage.setItem('tma_reload_at', String(Date.now()))
        window.location.reload()
      }
    }
    return Promise.reject(err)
  }
)

export const authApi = {
  login: (init_data) => tmaApi.post('/tma/auth', { init_data }),
}

export const shopsApi = {
  create: (data) => tmaApi.post('/tma/shops', data),
}

export const profileApi = {
  addPhone:    (phone)        => tmaApi.post('/tma/profile/add-phone', { phone }),
  removePhone: (index)        => tmaApi.delete(`/tma/profile/phones/${index}`),
  updatePhone: (index, phone) => tmaApi.put(`/tma/profile/phones/${index}`, { phone }),
}

export const ownerApi = {
  dashboard:    (shop_id)           => tmaApi.get('/tma/owner/dashboard',  { params: { shop_id } }),
  clients:      (shop_id, params)   => tmaApi.get('/tma/owner/clients',    { params: { shop_id, ...params } }),
  getClient:    (shop_id, id)       => tmaApi.get(`/tma/owner/clients/${id}`, { params: { shop_id } }),
  addClient:    (shop_id, data)     => tmaApi.post('/tma/owner/clients', data, { params: { shop_id } }),
  updateClient: (shop_id, id, data) => tmaApi.put(`/tma/owner/clients/${id}`, data, { params: { shop_id } }),
  delClient:    (shop_id, id)       => tmaApi.delete(`/tma/owner/clients/${id}`, { params: { shop_id } }),
  clearDebts:   (shop_id, id)       => tmaApi.post(`/tma/owner/clients/${id}/clear-debts`, {}, { params: { shop_id } }),
  // Qarzdorga qo'lda eslatma (avtomatik kunlik eslatmadan tashqari)
  remind:       (shop_id, id)       => tmaApi.post(`/tma/owner/clients/${id}/remind`, {}, { params: { shop_id } }),
  addDebt:      (shop_id, data)     => tmaApi.post('/tma/owner/debts', data, { params: { shop_id } }),
  addPayment:   (shop_id, data)     => tmaApi.post('/tma/owner/payments', data, { params: { shop_id } }),
  payTotal:     (shop_id, data)     => tmaApi.post('/tma/owner/payments/total', data, { params: { shop_id } }),
  stats:        (shop_id)           => tmaApi.get('/tma/owner/stats', { params: { shop_id } }),
  contact:      (shop_id, data)     => tmaApi.post('/tma/owner/contact', data, { params: { shop_id } }),
  // Excel hisobot — fayl Telegram orqali botga yuboriladi
  exportReport: (shop_id)           => tmaApi.post('/tma/owner/export', {}, { params: { shop_id }, timeout: 60000 }),
}

export const debtorApi = {
  overview:   ()        => tmaApi.get('/tma/debtor/overview'),
  shopDetail: (shop_id) => tmaApi.get(`/tma/debtor/shop/${shop_id}`),
}

// ─── ADMIN (web panel) ───────────────────────────────────────────────────────
const adminHttp = makeClient('/api/admin')

adminHttp.interceptors.request.use(cfg => {
  const token = sessionStorage.getItem('admin_token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

adminHttp.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      clearAdminToken()
      if (!window.location.pathname.startsWith('/admin/login')) {
        window.location.href = '/admin/login'
      }
    }
    return Promise.reject(err)
  }
)

/**
 * Admin tokeni sessionStorage'da saqlanadi (localStorage emas).
 * Sabab: localStorage brauzer yopilgandan keyin ham qoladi —
 * umumiy kompyuterda boshqa odam panelga kirib qolishi mumkin.
 */
const ADMIN_TOKEN_KEY = 'admin_token'
const ADMIN_EXP_KEY = 'admin_token_exp'

export function setAdminToken(token) {
  sessionStorage.setItem(ADMIN_TOKEN_KEY, token)
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    if (payload?.exp) sessionStorage.setItem(ADMIN_EXP_KEY, String(payload.exp * 1000))
  } catch { /* token formati kutilmagan — muddat tekshiruvisiz davom etamiz */ }
}

export function clearAdminToken() {
  sessionStorage.removeItem(ADMIN_TOKEN_KEY)
  sessionStorage.removeItem(ADMIN_EXP_KEY)
  // Eski versiyalardan qolgan token ham tozalansin
  localStorage.removeItem(ADMIN_TOKEN_KEY)
  clearMeCache()
}

export function hasValidAdminToken() {
  const token = sessionStorage.getItem(ADMIN_TOKEN_KEY)
  if (!token) return false
  const exp = Number(sessionStorage.getItem(ADMIN_EXP_KEY) || 0)
  if (exp && Date.now() >= exp) {
    clearAdminToken()
    return false
  }
  return true
}

export const adminAuthApi = {
  login: (data) => adminHttp.post('/auth/login', data, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  }),
  requestPasswordChange: () => adminHttp.post('/auth/request-password-change'),
  forgotPassword: (username) => adminHttp.post('/auth/forgot-password', { username }),
}

/**
 * `/profile/me` bir necha komponentda kerak (sidebar, Do'konlar, Sozlamalar).
 * Kesh bo'lmasa har bir sahifa almashganda 3 ta bir xil so'rov ketardi.
 * Natija sessiya davomida o'zgarmaydi — bir marta so'raymiz.
 */
let _mePromise = null

export function clearMeCache() { _mePromise = null }

export const adminProfileApi = {
  me: () => {
    if (!_mePromise) {
      _mePromise = adminHttp.get('/profile/me').catch(err => {
        _mePromise = null      // xato bo'lsa keyingi urinishda qayta so'raladi
        throw err
      })
    }
    return _mePromise
  },
  changePassword: (d) => adminHttp.put('/profile/password', d).then(r => (clearMeCache(), r)),
  changeUsername: (d) => adminHttp.put('/profile/username', d).then(r => (clearMeCache(), r)),
}

export const adminDashApi = { get: () => adminHttp.get('/dashboard') }

export const adminShopsApi = {
  list:    (p)     => adminHttp.get('/shops', { params: p }),
  approve: (id)    => adminHttp.post(`/shops/${id}/approve`),
  reject:  (id, r) => adminHttp.post(`/shops/${id}/reject`, { reason: r || null }),
  block:   (id, r) => adminHttp.post(`/shops/${id}/block`, { reason: r || null }),
  unblock: (id)    => adminHttp.post(`/shops/${id}/unblock`),
  extend:  (id, d) => adminHttp.post(`/shops/${id}/extend`, { days: d }),
  // Yumshoq o'chirish — ma'lumot 30 kun saqlanadi
  delete:  (id)    => adminHttp.delete(`/shops/${id}`),
  restore: (id)    => adminHttp.post(`/shops/${id}/restore`),
  // Butunlay yo'q qilish — faqat super admin, qaytarib bo'lmaydi
  purge:   (id)    => adminHttp.delete(`/shops/${id}/purge`),
}

export const adminUsersApi = {
  list:    (p)  => adminHttp.get('/users', { params: p }),
  block:   (id) => adminHttp.post(`/users/${id}/block`),
  unblock: (id) => adminHttp.post(`/users/${id}/unblock`),
}

export const adminPromoApi = {
  list:   ()     => adminHttp.get('/promo-codes'),
  create: (data) => adminHttp.post('/promo-codes', data),
  delete: (id)   => adminHttp.delete(`/promo-codes/${id}`),
}

export const adminAdminsApi = {
  list:   ()     => adminHttp.get('/admins'),
  create: (data) => adminHttp.post('/admins', data),
  delete: (id)   => adminHttp.delete(`/admins/${id}`),
}

export const adminSettingsApi = {
  get:    ()     => adminHttp.get('/settings'),
  update: (data) => adminHttp.put('/settings', data),
}

export const adminAuditApi = {
  list: (params) => adminHttp.get('/audit', { params }),
}

/**
 * Excel faylni brauzerda yuklab olish.
 * Token Authorization header'da bo'lgani uchun oddiy <a href> ishlamaydi —
 * faylni blob sifatida olamiz va vaqtincha havola yasaymiz.
 */
async function downloadXlsx(path, params, fallbackName) {
  const res = await adminHttp.get(path, { params, responseType: 'blob', timeout: 120000 })
  const disposition = res.headers['content-disposition'] || ''
  const match = /filename\*=UTF-8''([^;]+)/.exec(disposition)
  const name = match ? decodeURIComponent(match[1]) : fallbackName

  const url = URL.createObjectURL(res.data)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Xotira bo'shashi uchun havolani bekor qilamiz
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return name
}

export const adminExportApi = {
  shops:     (status)   => downloadXlsx('/shops/export', status ? { status } : {}, 'dokonlar.xlsx'),
  shopDetail: (sid)     => downloadXlsx(`/super/shops/${sid}/export`, {}, 'dokon-hisoboti.xlsx'),
}

// ─── SUPER ADMIN ─────────────────────────────────────────────────────────────
export const superApi = {
  me:          ()       => adminHttp.get('/super/me'),
  search:      (q)      => adminHttp.get('/super/search', { params: { q } }),
  shopClients: (sid)    => adminHttp.get(`/super/shops/${sid}/clients`),
  client:      (cid)    => adminHttp.get(`/super/clients/${cid}`),
  addDebt:     (cid, d) => adminHttp.post(`/super/clients/${cid}/debts`, d),
  pay:         (cid, d) => adminHttp.post(`/super/clients/${cid}/payments`, d),
  editDebt:    (did, d) => adminHttp.put(`/super/debts/${did}`, d),
  deleteDebt:  (did)    => adminHttp.delete(`/super/debts/${did}`),
}

export default tmaApi

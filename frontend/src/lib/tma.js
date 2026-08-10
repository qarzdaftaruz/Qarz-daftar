/**
 * Telegram Mini App SDK wrapper.
 *
 * Dev rejim FAQAT `npm run dev` da ishlaydi (import.meta.env.DEV).
 * Ilgari bu tekshiruv yo'q edi: production build'da ham Telegram tashqarisida
 * ochilsa `dev:<ID>` yuborilardi — ya'ni brauzerdan istalgan foydalanuvchi
 * nomidan kirish mumkin bo'lardi.
 */

const inTelegram = Boolean(window.Telegram?.WebApp?.initData)
const isDev = import.meta.env.DEV && !inTelegram

// Lokal sinov uchun o'z Telegram ID ingiz (.env.local → VITE_DEV_TELEGRAM_ID)
const DEV_TELEGRAM_ID = Number(import.meta.env.VITE_DEV_TELEGRAM_ID || 5762483346)

const wa = () => window.Telegram?.WebApp

export const tma = {
  /** initData string — backend ga yuboriladi */
  get initData() {
    if (isDev) return `dev:${DEV_TELEGRAM_ID}`
    return wa()?.initData || ''
  },

  /** Foydalanuvchi ma'lumotlari (faqat ko'rsatish uchun — ishonchli emas) */
  get user() {
    if (isDev) return { id: DEV_TELEGRAM_ID, first_name: 'Dev', last_name: 'User' }
    return wa()?.initDataUnsafe?.user || {}
  },

  /** Telegram ichida ochilganmi */
  get isInTelegram() {
    return inTelegram
  },

  get isDark() {
    if (isDev) return false
    return wa()?.colorScheme === 'dark'
  },

  expand() {
    if (!isDev) wa()?.expand?.()
  },

  backButton: {
    show(onClick) {
      const b = wa()?.BackButton
      if (isDev || !b) return
      b.show()
      b.onClick(onClick)
    },
    hide() {
      const b = wa()?.BackButton
      if (isDev || !b) return
      b.hide()
      b.offClick()
    },
  },

  mainButton: {
    show(text, onClick) {
      const mb = wa()?.MainButton
      if (isDev || !mb) return
      mb.setText(text)
      mb.onClick(onClick)
      mb.show()
    },
    hide() {
      if (isDev) return
      wa()?.MainButton?.hide()
    },
  },

  /** Haptic feedback — impact (light/medium/heavy/rigid/soft) yoki notification */
  haptic(type = 'light') {
    const hf = wa()?.HapticFeedback
    if (isDev || !hf) return
    try {
      if (type === 'success' || type === 'error' || type === 'warning') {
        hf.notificationOccurred(type)
      } else {
        hf.impactOccurred(type)
      }
    } catch { /* eski Telegram versiyalarida mavjud emas */ }
  },

  ready() {
    if (!isDev) wa()?.ready?.()
  },

  close() {
    if (!isDev) wa()?.close?.()
  },
}

export const isTMADev = isDev

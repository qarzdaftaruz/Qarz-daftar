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
    /**
     * XATO TUZATILDI: `hide()` ichida `b.offClick()` argumentsiz
     * chaqirilardi. Telegram SDK'sida `offClick(cb)` obработchini
     * ro'yxatdan `indexOf(cb)` bilan qidiradi — `undefined` uchun -1
     * qaytadi va HECH NARSA o'chmaydi. Natijada har bir mijoz kartasi
     * ochilganda yangi obработchi qo'shilib, eskilari joyida qolardi:
     * bir necha ekrandan keyin «Orqaga» tugmasi bir bosishda bir necha
     * marta ishlab, foydalanuvchini noto'g'ri ekranga tashlardi
     * (qarzdor ekranidan do'kondor ekraniga va aksincha).
     *
     * Endi oxirgi obработchi eslab qolinadi va aynan o'zi o'chiriladi.
     */
    _handler: null,

    show(onClick) {
      const b = wa()?.BackButton
      if (isDev || !b) return
      // Eskisi qolib ketmasin — avval tozalaymiz
      if (this._handler) b.offClick(this._handler)
      this._handler = onClick
      b.onClick(onClick)
      b.show()
    },
    hide() {
      const b = wa()?.BackButton
      if (isDev || !b) return
      b.hide()
      if (this._handler) {
        b.offClick(this._handler)
        this._handler = null
      }
    },
  },

  mainButton: {
    // BackButton bilan bir xil muammo: obработchi hech qachon o'chmasdi
    _handler: null,

    show(text, onClick) {
      const mb = wa()?.MainButton
      if (isDev || !mb) return
      if (this._handler) mb.offClick(this._handler)
      this._handler = onClick
      mb.setText(text)
      mb.onClick(onClick)
      mb.show()
    },
    hide() {
      const mb = wa()?.MainButton
      if (isDev || !mb) return
      mb.hide()
      if (this._handler) {
        mb.offClick(this._handler)
        this._handler = null
      }
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

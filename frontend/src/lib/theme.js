/**
 * Telegram Mini App'ni DOIM yorug' (premium oq) ko'rinishda majburlash.
 *
 * Muammo: Telegram foydalanuvchining qora temasida `--tg-theme-*` o'zgaruvchilarini
 * to'q ranglarga o'rnatadi → ilova qoramtir bo'lib qoladi. Mockup esa doim oq/yorug'.
 *
 * Yechim: bu o'zgaruvchilarni <html> ga inline-style sifatida o'zimiz yozamiz
 * (inline Telegram injektsiyasidan ustun turadi). Shunda barcha
 * `var(--tg-theme-bg-color)` ishlatadigan komponentlar yorug' rangda chiqadi.
 */

const LIGHT = {
  '--tg-theme-bg-color':            '#ffffff',
  '--tg-theme-secondary-bg-color':  '#f3f4f6',
  '--tg-theme-text-color':          '#111827',
  '--tg-theme-hint-color':          '#6b7280',
  '--tg-theme-subtitle-text-color': '#6b7280',
  '--tg-theme-section-bg-color':    '#ffffff',
  '--tg-theme-button-color':        '#2563eb',
  '--tg-theme-button-text-color':   '#ffffff',
  '--tg-theme-link-color':          '#2563eb',
  '--tg-theme-destructive-text-color': '#dc2626',
}

function apply() {
  const root = document.documentElement
  for (const [k, v] of Object.entries(LIGHT)) {
    root.style.setProperty(k, v, 'important')
  }
  root.style.colorScheme = 'light'
}

export function forceLightTheme() {
  apply()

  const wa = window.Telegram?.WebApp
  if (wa) {
    try { wa.expand?.() } catch {}
    // Native chrome (header / fon) ham yorug' bo'lsin.
    //
    // Versiya tekshiruvi SHART: bu ikki metod Telegram 6.1 dan boshlab
    // qo'llab-quvvatlanadi. Eski mijozlarda SDK xato TASHLAMAYDI — u
    // faqat konsolga «Background color is not supported in version 6.0»
    // deb yozadi, ya'ni try/catch yordam bermaydi. Natijada har bir
    // ochilishda ikkita ogohlantirish chiqib, haqiqiy xatolar
    // konsolda ko'zdan qochardi.
    const canSetColors = (() => {
      try { return wa.isVersionAtLeast?.('6.1') ?? false } catch { return false }
    })()
    if (canSetColors) {
      try { wa.setBackgroundColor?.('#f3f4f6') } catch {}
      try { wa.setHeaderColor?.('#ffffff') } catch {}
    }
    // Foydalanuvchi temani almashtirsa — qayta majburlaymiz
    try { wa.onEvent?.('themeChanged', apply) } catch {}
  }

  // Telegram skript kech yuklansa — bir necha marta qayta qo'llaymiz
  let tries = 0
  const id = setInterval(() => {
    apply()
    if (++tries >= 5) clearInterval(id)
  }, 150)
}

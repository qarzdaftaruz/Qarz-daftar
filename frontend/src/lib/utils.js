export const fmt = {
  money: (n) => {
    if (n == null) return '—'
    return new Intl.NumberFormat('uz-UZ').format(n) + " so'm"
  },
  date: (d) => {
    if (!d) return 'Muddatsiz'
    const months = ['yan','fev','mar','apr','may','iyn','iyl','avg','sen','okt','noy','dek']
    const dt = new Date(d)
    return `${dt.getDate()} ${months[dt.getMonth()]} ${dt.getFullYear()}`
  },
  dateShort: (d) => {
    if (!d) return '—'
    const months = ['yan','fev','mar','apr','may','iyn','iyl','avg','sen','okt','noy','dek']
    const dt = new Date(d)
    return `${dt.getDate()} ${months[dt.getMonth()]}`
  },
  time: (d) => {
    if (!d) return '—'
    const dt = new Date(d)
    return dt.toLocaleTimeString('uz', { hour: '2-digit', minute: '2-digit' })
  },
  ago: (d) => {
    const diff = Math.floor((Date.now() - new Date(d)) / 1000)
    if (diff < 60)   return 'hozirgina'
    if (diff < 3600) return `${Math.floor(diff/60)} daqiqa oldin`
    if (diff < 86400) return `${Math.floor(diff/3600)} soat oldin`
    return `${Math.floor(diff/86400)} kun oldin`
  }
}

export const statusLabel = (s) => ({
  open:     'Ochiq',
  partial:  'Qisman',
  closed:   'Yopiq',
  overdue:  "Muddati o'tgan",
  archived: 'Arxiv',
}[s] || s)

export const statusBadge = (s) => ({
  open:     'badge-open',
  partial:  'badge-partial',
  closed:   'badge-closed',
  overdue:  'badge-overdue',
}[s] || 'badge-open')

export const statusEmoji = (s) => ({
  open: '🟢', partial: '🟡', closed: '✅', overdue: '🔴', archived: '📦'
}[s] || '⚪')

export const daysUntil = (d) => {
  if (!d) return null
  return Math.ceil((new Date(d) - Date.now()) / 86400000)
}

export const cn = (...cls) => cls.filter(Boolean).join(' ')

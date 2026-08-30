import { AlertCircle, RefreshCw } from 'lucide-react'

/**
 * Ma'lumot yuklanmaganda ko'rsatiladigan blok.
 *
 * NIMA UCHUN: ilgari yuklash so'rovi yiqilsa sahifalar `catch` siz edi —
 * skeleton abadiy aylanib turardi yoki `return null` tufayli oq ekran
 * chiqardi. Sabab faqat brauzer konsolida ko'rinardi, foydalanuvchi esa
 * nima bo'lganini ham, nima qilishni ham bilmasdi. Mobil internetda
 * (Telegram ichida) so'rov uzilishi oddiy hol.
 */
export default function LoadError({ message = 'Ma’lumot yuklanmadi', onRetry }) {
  return (
    <div style={{
      padding: 32,
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      textAlign: 'center', gap: 12, minHeight: 240,
    }}>
      <AlertCircle size={38} style={{ color: '#f43f5e' }} />
      <p style={{
        fontSize: 14, lineHeight: 1.5, margin: 0, maxWidth: 300,
        color: 'var(--tg-theme-hint-color, #64748b)',
      }}>
        {message}
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginTop: 4, padding: '10px 22px', borderRadius: 14, border: 'none',
            cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 8,
            background: '#2563EB', color: '#fff', fontWeight: 600, fontSize: 14,
          }}
        >
          <RefreshCw size={15} /> Qayta urinish
        </button>
      )}
    </div>
  )
}

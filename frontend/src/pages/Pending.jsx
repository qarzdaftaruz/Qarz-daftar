import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Clock, RefreshCw, XCircle, Plus, Ban } from 'lucide-react'

export default function ShopStatusScreen() {
  const navigate = useNavigate()
  const { pendingShops, rejectedShops, blockedShops, refresh } = useAuth()

  // XATO TUZATILDI: bloklangan do'konlar bu ekranda UMUMAN ko'rsatilmasdi.
  // Obuna muddati tugab avtomatik to'xtatilgan do'kon egasi ilovani ochsa
  // «Hozircha faol do'koningiz yo'q» va «Odatda 1-24 soat ichida
  // tasdiqlanadi» degan mutlaqo noto'g'ri xabarni ko'rardi — sababni
  // bilmasdi va yechim o'rniga «Yangi do'kon ochish» tugmasini bosib
  // dublikat do'kon yaratardi.

  return (
    <div
      className="animate-slide-up"
      style={{
        minHeight: '100svh',
        display: 'flex',
        flexDirection: 'column',
        padding: '0 20px 32px',
        background: 'var(--tg-theme-bg-color, #fff)',
      }}
    >
      {/* Hero icon */}
      <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 64, paddingBottom: 24 }}>
        <div style={{
          width: 84, height: 84, borderRadius: 28,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: '#fffbeb',
          boxShadow: '0 8px 32px rgba(245,158,11,0.2)',
        }}>
          <Clock size={38} style={{ color: '#d97706' }} />
        </div>
      </div>

      <h1 className="font-display" style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em', textAlign: 'center', color: 'var(--tg-theme-text-color)', margin: '0 0 8px' }}>
        Do'kon holati
      </h1>
      <p style={{ textAlign: 'center', fontSize: 14, color: 'var(--tg-theme-hint-color)', margin: '0 0 32px', lineHeight: 1.5 }}>
        Hozircha faol do'koningiz yo'q
      </p>

      {/* Status cards */}
      {(pendingShops.length > 0 || rejectedShops.length > 0 || blockedShops.length > 0) && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 28 }}>
          {blockedShops.map(s => (
            <div key={s.id} style={{
              borderRadius: 16, padding: '14px 16px',
              background: '#fff7ed',
              border: '1px solid #fed7aa',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                <Ban size={15} style={{ color: '#ea580c', flexShrink: 0 }} />
                <p style={{ fontWeight: 700, fontSize: 14, color: '#9a3412', margin: 0 }}>{s.name}</p>
              </div>
              <p style={{ fontSize: 12, color: '#c2410c', margin: '0 0 0 25px', lineHeight: 1.5 }}>
                {s.block_reason || "Vaqtincha to'xtatilgan"}
                <br />
                Ma'lumotlaringiz saqlanib turibdi — davom ettirish uchun admin bilan bog'laning.
              </p>
            </div>
          ))}

          {pendingShops.map(s => (
            <div key={s.id} style={{
              borderRadius: 16, padding: '14px 16px',
              background: '#fffbeb',
              border: '1px solid #fef3c7',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                <Clock size={15} style={{ color: '#d97706', flexShrink: 0 }} />
                <p style={{ fontWeight: 700, fontSize: 14, color: '#92400e', margin: 0 }}>{s.name}</p>
              </div>
              <p style={{ fontSize: 12, color: '#b45309', margin: '0 0 0 25px' }}>
                Admin tasdiqlashini kutmoqda
              </p>
            </div>
          ))}

          {rejectedShops.map(s => (
            <div key={s.id} style={{
              borderRadius: 16, padding: '14px 16px',
              background: '#fef2f2',
              border: '1px solid #fecaca',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                <XCircle size={15} style={{ color: '#dc2626', flexShrink: 0 }} />
                <p style={{ fontWeight: 700, fontSize: 14, color: '#b91c1c', margin: 0 }}>{s.name}</p>
              </div>
              <p style={{ fontSize: 12, color: '#dc2626', margin: '0 0 0 25px' }}>
                Rad etildi{s.reject_reason ? `: ${s.reject_reason}` : ''}
              </p>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button onClick={refresh} className="btn-ghost">
          <RefreshCw size={15} /> Holatni yangilash
        </button>
        <button onClick={() => navigate('/new-shop')} className="btn-primary">
          <Plus size={16} /> Yangi do'kon ochish
        </button>
      </div>

      {/* Bu matn faqat tasdiqlash kutayotgan do'kon bo'lgandagina to'g'ri.
          Ilgari bloklangan/rad etilgan do'konda ham chiqib, adashtirardi. */}
      {pendingShops.length > 0 && (
        <p style={{ fontSize: 12, textAlign: 'center', color: 'var(--tg-theme-hint-color)', marginTop: 20 }}>
          Odatda 1–24 soat ichida tasdiqlanadi
        </p>
      )}
    </div>
  )
}

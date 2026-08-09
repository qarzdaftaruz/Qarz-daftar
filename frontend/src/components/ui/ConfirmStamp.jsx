/**
 * ConfirmStamp — oddiy tasdiqlash belgisi (yashil doira + galochka).
 * Animatsiya: scale + bounce (~0.42s). reduced-motion da darhol ko'rinadi.
 *
 * Props:
 *   size  — px (default 128)
 *   color — belgi rangi (default brand.trust yashil #16A34A)
 *   label — ixtiyoriy (ishlatilmaydi, moslik uchun qoldirilgan)
 */
export default function ConfirmStamp({ size = 128, color = '#16A34A' }) {
  return (
    <svg
      className="animate-stamp-in"
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      role="img"
      aria-label="Tasdiqlandi"
      style={{ display: 'block', transformOrigin: 'center' }}
    >
      <circle cx="60" cy="60" r="54" fill={color} fillOpacity="0.12" />
      <circle cx="60" cy="60" r="40" fill={color} />
      <path
        d="M 44 61 L 55 72 L 78 49"
        stroke="#fff"
        strokeWidth="7"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

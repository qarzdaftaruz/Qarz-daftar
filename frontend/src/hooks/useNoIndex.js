import { useEffect } from 'react'

/**
 * Sahifani qidiruv tizimlaridan yashiradi (`<meta name="robots" content="noindex">`).
 *
 * Admin panel va foydalanuvchining shaxsiy ekranlari Google natijalarida
 * chiqmasligi kerak. Vercel tomonida `X-Robots-Tag` header ham qo'yilgan —
 * bu ikkinchi himoya qatlami (JS bilan render qilinadigan marshrutlar uchun).
 */
export function useNoIndex(active = true) {
  useEffect(() => {
    if (!active) return

    const tag = document.createElement('meta')
    tag.name = 'robots'
    tag.content = 'noindex, nofollow, noarchive'
    document.head.appendChild(tag)

    return () => { tag.remove() }
  }, [active])
}

export default useNoIndex

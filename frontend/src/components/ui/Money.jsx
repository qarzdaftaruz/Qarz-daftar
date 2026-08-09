import { useEffect, useRef, useState } from 'react'

const fmtNum = (n) => new Intl.NumberFormat('uz-UZ').format(Math.round(n))

/**
 * Money — pul miqdorini 0 dan (yoki oldingi qiymatdan) maqsadgacha
 * silliq sanab chiqaradigan animatsion komponent (premium tafsilot).
 * To'lov qabul qilingach / qarz yopilgach raqam jonli o'zgaradi.
 * reduced-motion da darhol yakuniy qiymatni ko'rsatadi.
 */
export default function Money({ value = 0, suffix = " so'm", duration = 750, className = '', style }) {
  const target = Number(value) || 0
  const [display, setDisplay] = useState(target)
  const fromRef = useRef(target)
  const rafRef  = useRef()

  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches
    const from = fromRef.current
    const to = target
    if (reduce || from === to) { setDisplay(to); fromRef.current = to; return }

    const start = performance.now()
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3) // easeOutCubic
      setDisplay(from + (to - from) * eased)
      if (t < 1) rafRef.current = requestAnimationFrame(tick)
      else fromRef.current = to
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [target, duration])

  return (
    <span className={`money ${className}`} style={style}>
      {fmtNum(display)}{suffix}
    </span>
  )
}

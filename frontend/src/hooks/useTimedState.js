import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * useTimedState — qiymat o'rnatilgach belgilangan vaqtdan keyin avtomatik tozalanadi.
 * Ogohlantirish/xabarlar uchun: setVal('xato') → 5s dan keyin o'chadi.
 * API useState bilan bir xil: const [msg, setMsg] = useTimedState('')
 */
export function useTimedState(initial = '', ms = 5000) {
  const [val, setValRaw] = useState(initial)
  const timer = useRef()

  const setVal = useCallback((v) => {
    setValRaw(v)
    clearTimeout(timer.current)
    if (v) timer.current = setTimeout(() => setValRaw(initial), ms)
  }, [initial, ms])

  useEffect(() => () => clearTimeout(timer.current), [])

  return [val, setVal]
}

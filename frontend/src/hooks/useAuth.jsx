import { createContext, useContext, useState, useEffect, useMemo, useRef } from 'react'
import { tma } from '../lib/tma'
import { authApi } from '../lib/api'

const AuthCtx = createContext(null)

export function AuthProvider({ children }) {
  const [state, setState] = useState({
    loading: true,
    hasAccount: false,
    error: false,
    user: null,
    shops: [],
    isDebtor: false,
  })

  const [currentShopId, setCurrentShopId] = useState(null)
  const [view, setView] = useState('owner') // 'owner' | 'debtor'
  // Boshlang'ich ko'rinish faqat BIR MARTA tanlanadi. Ilgari har bir
  // `refresh()` da qayta hisoblanardi: qarzdor ko'rinishiga o'tgan
  // do'kondor har qanday yangilanishdan keyin do'kon ko'rinishiga
  // qaytib ketardi.
  const viewChosen = useRef(false)

  useEffect(() => { init() }, [])

  const init = async () => {
    tma.ready()
    tma.expand()
    try {
      const res = await authApi.login(tma.initData)
      const { token, has_account, is_debtor, user, shops } = res.data

      if (token) sessionStorage.setItem('tma_token', token)
      // Hisob yo'q bo'lsa eski token qolib ketmasin
      else sessionStorage.removeItem('tma_token')

      const active = (shops || []).filter(s => s.status === 'active')

      setState({
        loading: false,
        hasAccount: !!has_account,
        error: false,
        user: user || null,
        shops: shops || [],
        isDebtor: !!is_debtor,
      })

      setCurrentShopId(prev => prev && active.some(s => s.id === prev) ? prev : (active[0]?.id || null))
      if (!viewChosen.current) {
        viewChosen.current = true
        setView(active.length > 0 ? 'owner' : 'debtor')
      }
    } catch (e) {
      setState(s => ({ ...s, loading: false, error: true }))
    }
  }

  const activeShops   = useMemo(() => state.shops.filter(s => s.status === 'active'),   [state.shops])
  const pendingShops  = useMemo(() => state.shops.filter(s => s.status === 'pending'),  [state.shops])
  const rejectedShops = useMemo(() => state.shops.filter(s => s.status === 'rejected'), [state.shops])
  const blockedShops  = useMemo(() => state.shops.filter(s => s.status === 'blocked'),  [state.shops])

  const canBeOwner = activeShops.length > 0
  const canSwitch  = canBeOwner && state.isDebtor

  return (
    <AuthCtx.Provider value={{
      ...state,
      activeShops, pendingShops, rejectedShops, blockedShops,
      canBeOwner, canSwitch,
      currentShopId, setShop: setCurrentShopId,
      view, setView,
      refresh: init,
    }}>
      {children}
    </AuthCtx.Provider>
  )
}

export const useAuth = () => useContext(AuthCtx)

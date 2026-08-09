import { Component } from 'react'

/**
 * Butun ilovani o'rab turuvchi xato chegarasi.
 * Runtime xatosi yuz berganda oq (bo'sh) ekran o'rniga
 * tushunarli xabar + qayta yuklash tugmasini ko'rsatadi.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    // Diagnostika uchun konsolga chiqaramiz
    console.error('UI xatosi:', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          minHeight: '100svh',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          textAlign: 'center', padding: '24px',
          background: '#ffffff', color: '#111827',
          fontFamily: 'Inter, system-ui, sans-serif',
        }}>
          <div style={{ fontSize: 44, marginBottom: 14 }}>😕</div>
          <h1 style={{ fontSize: 20, fontWeight: 800, margin: '0 0 8px', fontFamily: 'Manrope, Inter, sans-serif' }}>
            Nimadir noto'g'ri ketdi
          </h1>
          <p style={{ fontSize: 14, color: '#6b7280', margin: '0 0 22px', maxWidth: 300, lineHeight: 1.5 }}>
            Ilovani qayta yuklab ko'ring. Muammo davom etsa, biroz keyinroq urinib ko'ring.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              padding: '12px 26px', borderRadius: 16, border: 'none', cursor: 'pointer',
              background: 'linear-gradient(135deg, #2563EB 0%, #1d4ed8 100%)',
              color: '#fff', fontWeight: 700, fontSize: 14,
              boxShadow: '0 8px 22px rgba(37,99,235,0.42)',
            }}
          >
            Qayta yuklash
          </button>
          {import.meta.env.DEV && (
            <pre style={{
              marginTop: 24, maxWidth: '90vw', overflow: 'auto',
              fontSize: 11, color: '#dc2626', textAlign: 'left',
              background: '#fef2f2', padding: 12, borderRadius: 12,
            }}>
              {String(this.state.error?.stack || this.state.error)}
            </pre>
          )}
        </div>
      )
    }
    return this.props.children
  }
}

import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import ErrorBoundary from './components/ErrorBoundary'
import { forceLightTheme } from './lib/theme'
import './index.css'

// Telegram qora temasini bekor qilib, doim yorug' ko'rinishni majburlaymiz
forceLightTheme()

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </ErrorBoundary>
)

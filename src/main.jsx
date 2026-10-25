import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './styles/theme.css'
import './styles/shared.css'
import App from './App.jsx'

// Vercel Web Analytics: anonymous page views, no cookies. Only on the deployed site.
if (import.meta.env.PROD) {
  window.va = window.va || function va(...args) { (window.vaq = window.vaq || []).push(args) }
  const s = document.createElement('script')
  s.defer = true
  s.src = '/_vercel/insights/script.js'
  document.head.appendChild(s)
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

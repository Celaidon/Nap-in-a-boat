import '@fontsource/anton/400.css'
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/700.css'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles/tokens.css'
import './styles/base.css'
import './styles/app.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

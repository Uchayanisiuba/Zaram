import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { installApiCredential } from './services/apiCredential'
import './index.css'

// Before the first render, not alongside it. The credential is resolved over
// IPC, and any request that raced it would come back 401 — which the interface
// would show as the backend being unreachable, a wrong and very confusing
// answer to give about a backend that is running perfectly.
void installApiCredential().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
})

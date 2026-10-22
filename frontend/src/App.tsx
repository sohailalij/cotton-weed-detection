import { useState } from 'react'

import './App.css'
import DetectPage from './DetectPage'
import HistoryPage from './HistoryPage'

type Tab = 'detect' | 'history'

export default function App() {
  const [tab, setTab] = useState<Tab>('detect')

  return (
    <main>
      <h1>Weed detection</h1>
      <p>Upload a close-up photo of a cotton field to find weeds.</p>
      <nav aria-label="Pages" className="tabs">
        <button
          type="button"
          onClick={() => setTab('detect')}
          aria-current={tab === 'detect' ? 'page' : undefined}
        >
          Detect
        </button>
        <button
          type="button"
          onClick={() => setTab('history')}
          aria-current={tab === 'history' ? 'page' : undefined}
        >
          History
        </button>
      </nav>
      <div hidden={tab !== 'detect'}>
        <DetectPage />
      </div>
      {tab === 'history' && <HistoryPage />}
    </main>
  )
}
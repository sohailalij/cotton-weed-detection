import { useState } from 'react'

import './App.css'
import AnalyticsPage from './AnalyticsPage'
import DetectPage from './DetectPage'
import HistoryPage from './HistoryPage'

type Tab = 'detect' | 'history' | 'analytics'

const TABS: { id: Tab; label: string }[] = [
  { id: 'detect', label: 'Detect' },
  { id: 'history', label: 'History' },
  { id: 'analytics', label: 'Analytics' },
]

export default function App() {
  const [tab, setTab] = useState<Tab>('detect')

  return (
    <main>
      <h1>Weed detection</h1>
      <p>Upload a close-up photo of a cotton field to find weeds.</p>
      <nav aria-label="Pages" className="tabs">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            aria-current={tab === id ? 'page' : undefined}
          >
            {label}
          </button>
        ))}
      </nav>
      <div hidden={tab !== 'detect'}>
        <DetectPage />
      </div>
      {tab === 'history' && <HistoryPage />}
      {tab === 'analytics' && <AnalyticsPage />}
    </main>
  )
}
import { lazy, Suspense, useState } from 'react'

import './App.css'
import DetectPage from './DetectPage'
import HistoryPage from './HistoryPage'

// The charts library is large, so this page is only downloaded when its tab is opened.
const AnalyticsPage = lazy(() => import('./AnalyticsPage'))

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
      <header className="site-header">
        <div className="brand">
          <svg
            className="brand-icon"
            viewBox="0 0 32 32"
            aria-hidden="true"
            focusable="false"
          >
            <rect width="32" height="32" rx="7" fill="var(--accent)" />
            <path d="M9 23C9 14 14 9 24 8c0 9-4 15-13 15z" fill="var(--on-accent)" />
            <path
              d="M9 23l9-9"
              stroke="var(--accent)"
              strokeWidth="1.6"
              strokeLinecap="round"
            />
          </svg>
          <div>
            <h1>Weed detection</h1>
            <p>Upload a close-up photo of a cotton field to find weeds.</p>
          </div>
        </div>
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
      </header>
      {tab === 'detect' && <DetectPage />}
      {tab === 'history' && <HistoryPage />}
      {tab === 'analytics' && (
        <Suspense fallback={<p className="state">Loading...</p>}>
          <AnalyticsPage />
        </Suspense>
      )}
    </main>
  )
}
import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { colorForSpecies, formatDay, speciesInOrder, summarize, toChartRows } from './analytics'
import { api, ApiError } from './api'
import './AnalyticsPage.css'

type Series = Awaited<ReturnType<typeof api.statsDaily>>

const defaultLoad = () => api.statsDaily()

const count = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`

export default function AnalyticsPage({ load = defaultLoad }: { load?: () => Promise<Series> }) {
  const [series, setSeries] = useState<Series | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    load()
      .then((next) => {
        if (!cancelled) setSeries(next)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof ApiError ? e.message : 'Could not reach the server')
      })
    return () => {
      cancelled = true
    }
  }, [load])

  const days = series?.days ?? []
  const summary = summarize(days)
  const species = speciesInOrder(days)
  const rows = toChartRows(days, species)
  const headline = `${count(summary.detections, 'detection', 'detections')} on ${count(
    summary.activeDays,
    'day',
    'days',
  )}, ${count(summary.weeds, 'weed', 'weeds')} found`
  const speciesText = summary.species
    .map(([name, n]) => `${name.replaceAll('_', ' ')} ${n}`)
    .join(', ')

  return (
    <section className="analytics">
      <h2>Analytics</h2>
      <div role="status" aria-live="polite">
        {error && <p className="analytics-error">{error}</p>}
        {!series && !error && <p>Loading...</p>}
      </div>

      {series && days.length === 0 && <p>No detections yet. Run one on the Detect tab.</p>}

      {series && days.length > 0 && (
        <>
          <p>{headline}</p>
          <p>{speciesText}</p>

          <h3>Weeds found per day</h3>
          <div className="analytics-chart" role="img" aria-label="Bar chart of weeds found per day">
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" tickFormatter={(value: string) => formatDay(value)} />
                <YAxis allowDecimals={false} />
                <Tooltip labelFormatter={(value) => formatDay(String(value))} />
                <Legend />
                {species.map((name) => (
                  <Bar
                    key={name}
                    dataKey={name}
                    name={name.replaceAll('_', ' ')}
                    stackId="weeds"
                    fill={colorForSpecies(name)}
                    isAnimationActive={false}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>

          <h3>Average box coverage per day</h3>
          <div
            className="analytics-chart"
            role="img"
            aria-label="Line chart of average weed coverage per day"
          >
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={rows}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="day"
                  padding={{ left: 24, right: 24 }}
                  tickFormatter={(value: string) => formatDay(value)}
                />
                <YAxis domain={[0, 100]} unit="%" />
                <Tooltip labelFormatter={(value) => formatDay(String(value))} />
                <Line
                  type="monotone"
                  dataKey="coveragePercent"
                  name="Coverage"
                  unit="%"
                  stroke="#4363d8"
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  )
}
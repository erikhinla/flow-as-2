import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch, parseApiJson } from '../lib/api'

type Gap = {
  label: string
  severity: number
  score: number
  max_score: number
}

type ClientResult = {
  session_id: string
  task_id: string
  name: string
  company: string
  role: string
  industry: string
  category: string
  score: number
  max_score: number
  headline: string
  summary: string
  industry_context: string
  top_gaps: Gap[]
  recommended_infrastructure: string[]
  phased_plan: string[]
  next_move: string
  next_cta: string
  route_to: string
  owner: string
  created: string
}

declare global {
  interface Window {
    __FLOW_DESK__?: { diagnosticUrl?: string }
  }
}

function percent(score: number, max: number) {
  if (!max) return 0
  return Math.round((score / max) * 100)
}

function diagnosticHref() {
  const configured = window.__FLOW_DESK__?.diagnosticUrl?.trim()
  return configured || '/diagnostic?type=bizbuilders'
}

export function ClientOutcomes() {
  const { data, isLoading, error } = useQuery<{ results: ClientResult[] }>({
    queryKey: ['client-diagnostics'],
    queryFn: async () => {
      const response = await apiFetch('/api/client-diagnostics')
      return parseApiJson(response)
    },
    refetchInterval: 4000,
  })
  const results = data?.results || []
  const [picked, setPicked] = useState<string>('')
  const selected = results.find((item) => item.session_id === picked) || results[0]

  if (isLoading) {
    return <p className="desk-muted">Loading client reports…</p>
  }

  if (error) {
    return <p className="desk-error">{error instanceof Error ? error.message : 'Reports could not load.'}</p>
  }

  if (!selected) {
    return (
      <section className="desk-empty">
        <p className="desk-kicker">No client report yet</p>
        <h2>A finished diagnostic lands here.</h2>
        <p>
          Open the BizBuilders readiness diagnostic, answer as the client, and submit.
          The score, constraint, and phased roadmap appear on this desk.
        </p>
        <a href={diagnosticHref()}>Start a client diagnostic</a>
      </section>
    )
  }

  const friction = percent(selected.score, selected.max_score)

  return (
    <div className="desk-layout">
      <aside className="desk-list">
        <p className="desk-kicker">Client reports</p>
        {results.map((item) => (
          <button
            key={item.session_id}
            type="button"
            className={item.session_id === selected.session_id ? 'active' : ''}
            onClick={() => setPicked(item.session_id)}
          >
            <strong>{item.company || item.name}</strong>
            <span>{item.category} · {item.score}/{item.max_score}</span>
          </button>
        ))}
      </aside>
      <article className="desk-report">
        <p className="desk-kicker">{selected.industry || 'Client'} · {selected.category}</p>
        <h2>{selected.headline}</h2>
        <div className="desk-score">
          <div>
            <b>{friction}%</b>
            <span>friction</span>
          </div>
          <div>
            <b>{selected.score}/{selected.max_score}</b>
            <span>score</span>
          </div>
          <div>
            <b>{selected.owner || 'alpha'}</b>
            <span>owner</span>
          </div>
        </div>
        <p className="desk-summary">{selected.summary}</p>
        <p className="desk-context">{selected.industry_context}</p>
        <div className="desk-grid">
          <section>
            <h3>Constraints</h3>
            <ul className="gap-list">
              {selected.top_gaps.map((gap) => (
                <li key={gap.label}>
                  <div className="gap-label">
                    <span>{gap.label}</span>
                    <span>{Math.round((gap.severity || 0) * 100)}%</span>
                  </div>
                  <div className="gap-track">
                    <div style={{ width: `${Math.round((gap.severity || 0) * 100)}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3>Phased roadmap</h3>
            <ol>
              {selected.phased_plan.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
          </section>
        </div>
        <section className="desk-next">
          <h3>What the client does next</h3>
          <p>{selected.next_move}</p>
          <p className="desk-meta">
            {selected.name}{selected.role ? `, ${selected.role}` : ''}
            {selected.company ? ` · ${selected.company}` : ''}
            {' · '}
            {selected.next_cta} → {selected.route_to}
          </p>
        </section>
      </article>
    </div>
  )
}

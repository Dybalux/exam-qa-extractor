import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api.ts'
import { ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { accuracyTone, pct } from '../format.ts'
import { useTopicLabel } from '../topics.ts'

export default function Analytics() {
  const { data, error, isPending } = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })
  const topicLabel = useTopicLabel()

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const { stats, progress, performance } = data
  const topics = Object.entries(progress.by_topic)
  const perf = Object.entries(performance).sort(([, a], [, b]) => a.accuracy_pct - b.accuracy_pct)

  return (
    <div className="stack" style={{ gap: 'var(--s-6)' }}>
      <PageHead title="Estadísticas" lead="Vista general del contenido y tu progreso de estudio" />

      <dl className="facts">
        <div>
          <dt>Exámenes</dt>
          <dd>{stats.total_exams}</dd>
        </div>
        <div>
          <dt>Preguntas</dt>
          <dd>{stats.total_questions}</dd>
        </div>
        <div>
          <dt>Listas para practicar</dt>
          <dd>
            {stats.questions_ready_for_practice}
            <small>{pct(stats.practice_readiness_pct)}</small>
          </dd>
        </div>
        <div>
          <dt>Sesiones completadas</dt>
          <dd>
            {stats.completed_practice_sessions}
            <small>de {stats.total_practice_sessions} totales</small>
          </dd>
        </div>
      </dl>

      <div className="dash-grid">
        <Card title="Cobertura por tema">
          {topics.length === 0 ? (
            <p className="muted">Sin datos.</p>
          ) : (
            <ul className="meter-list">
              {topics.map(([topic, b]) => {
                const label = topicLabel(topic)
                return (
                  <li key={topic}>
                    <div className="meter-top">
                      <Link className="meter-link" to={`/questions?topic=${encodeURIComponent(topic)}`}>
                        {label}
                      </Link>
                      <span className="muted num">
                        {b.ready}/{b.total}
                      </span>
                    </div>
                    <div
                      className="meter"
                      role="progressbar"
                      aria-label={`${label}, cobertura`}
                      aria-valuenow={Math.round(b.readiness_pct)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <span style={{ width: `${b.readiness_pct}%` }} />
                    </div>
                  </li>
                )
              })}
            </ul>
          )}
        </Card>

        <Card
          title="Mi desempeño por tema"
          aside={
            perf.length > 0 ? (
              <div className="meter-legend" aria-label="Escala de precisión">
                <span>
                  <i className="meter-dot meter-dot-wrong" aria-hidden="true" />
                  &lt;60%
                </span>
                <span>
                  <i className="meter-dot meter-dot-warn" aria-hidden="true" />
                  60–79%
                </span>
                <span>
                  <i className="meter-dot meter-dot-right" aria-hidden="true" />
                  ≥80%
                </span>
              </div>
            ) : undefined
          }
        >
          {perf.length === 0 ? (
            <div className="stack">
              <p className="muted">Sin historial todavía.</p>
              <div className="row">
                <ButtonLink to="/practice">Empieza a practicar</ButtonLink>
              </div>
            </div>
          ) : (
            <>
              <ul className="meter-list">
                {perf.map(([topic, p]) => {
                  const label = topicLabel(topic)
                  const tone = accuracyTone(p.accuracy_pct)
                  return (
                    <li key={topic}>
                      <div className="meter-top">
                        <Link className="meter-link" to={`/practice?topic=${encodeURIComponent(topic)}`}>
                          {label}
                        </Link>
                        <div className="meter-meta">
                          <span className="muted num" style={{ fontSize: 'var(--text-sm)' }}>
                            {p.correct}/{p.total}
                          </span>
                          <span className={`pill pill-${tone} num`}>{pct(p.accuracy_pct)}</span>
                          <Link
                            className="meter-action"
                            to={`/practice?topic=${encodeURIComponent(topic)}`}
                            aria-label={`Practicar ${label}`}
                          >
                            Practicar →
                          </Link>
                        </div>
                      </div>
                      <div
                        className={`meter meter-${tone}`}
                        role="progressbar"
                        aria-label={`${label}, precisión`}
                        aria-valuenow={Math.round(p.accuracy_pct)}
                        aria-valuemin={0}
                        aria-valuemax={100}
                      >
                        <span style={{ width: `${p.accuracy_pct}%` }} />
                      </div>
                    </li>
                  )
                })}
              </ul>
              <p style={{ marginTop: 'var(--s-4)', marginBottom: 0 }}>
                <Link to="/analytics/weak-areas">Ver áreas débiles</Link>
              </p>
            </>
          )}
        </Card>
      </div>
    </div>
  )
}

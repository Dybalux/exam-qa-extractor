import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api.ts'
import { ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { pct } from '../format.ts'

export default function Analytics() {
  const { data, error, isPending } = useQuery({ queryKey: ['analytics'], queryFn: api.analytics })

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const { stats, progress, performance } = data
  const topics = Object.entries(progress.by_topic)
  const perf = Object.entries(performance)

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
              {topics.map(([topic, b]) => (
                <li key={topic}>
                  <div className="meter-top">
                    <span>{topic}</span>
                    <span className="muted num">
                      {b.ready}/{b.total}
                    </span>
                  </div>
                  <div
                    className="meter"
                    role="progressbar"
                    aria-label={`${topic}, cobertura`}
                    aria-valuenow={Math.round(b.readiness_pct)}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  >
                    <span style={{ width: `${b.readiness_pct}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Mi desempeño por tema">
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
                {perf.map(([topic, p]) => (
                  <li key={topic}>
                    <div className="meter-top">
                      <span>{topic}</span>
                      <span className="muted num">{pct(p.accuracy_pct)}</span>
                    </div>
                    <div
                      className="meter"
                      role="progressbar"
                      aria-label={`${topic}, precisión`}
                      aria-valuenow={Math.round(p.accuracy_pct)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    >
                      <span style={{ width: `${p.accuracy_pct}%` }} />
                    </div>
                  </li>
                ))}
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

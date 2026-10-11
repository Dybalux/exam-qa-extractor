import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api.ts'
import { ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { formatDuration, modeLabel, pct } from '../format.ts'

export default function WeakAreas() {
  const { data, error, isPending } = useQuery({
    queryKey: ['weak-areas'],
    queryFn: () => api.weakAreas(),
  })

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const { threshold, weak_areas: weak, history } = data

  return (
    <div className="stack" style={{ gap: 'var(--s-6)' }}>
      <PageHead title="Áreas débiles" lead={`Temas donde tu precisión está por debajo del ${threshold}%`} />
      <div className="row">
        <ButtonLink to="/practice">▶ Practicar ahora</ButtonLink>
      </div>

      {weak.length === 0 ? (
        <Card flat>
          <h2>¡Ningún área débil!</h2>
          <p className="muted">Tu precisión supera el {threshold}% en todos los temas practicados.</p>
          <ButtonLink to="/practice">Seguir practicando</ButtonLink>
        </Card>
      ) : (
        <Card
          title={`${weak.length} área(s) débil(es)`}
          aside={<span className="muted">Umbral: {threshold}% precisión</span>}
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Tema</th>
                  <th>Precisión</th>
                  <th>Correctas / Total</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {weak.map((a) => (
                  <tr key={a.topic}>
                    <td>
                      <span className="pill">{a.topic}</span>
                    </td>
                    <td style={{ minWidth: '10rem' }}>
                      <div className="row" style={{ flexWrap: 'nowrap' }}>
                        <div
                          className="meter"
                          style={{ flex: 1 }}
                          role="progressbar"
                          aria-label={`${a.topic}, precisión`}
                          aria-valuenow={Math.round(a.accuracy_pct)}
                          aria-valuemin={0}
                          aria-valuemax={100}
                        >
                          <span style={{ width: `${a.accuracy_pct}%`, background: 'var(--wrong)' }} />
                        </div>
                        <span className="num">{pct(a.accuracy_pct)}</span>
                      </div>
                    </td>
                    <td className="num">
                      {a.correct} / {a.total}
                    </td>
                    <td>
                      <div className="table-actions">
                        <Link to={`/practice?topic=${encodeURIComponent(a.topic)}`}>▶ Practicar</Link>
                        <Link to={`/questions?topic=${encodeURIComponent(a.topic)}`}>Ver preguntas</Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {history.length > 0 && (
        <Card title={`Últimas ${history.length} sesiones`}>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Modo</th>
                  <th>Progreso</th>
                  <th>Precisión</th>
                  <th>Tiempo</th>
                </tr>
              </thead>
              <tbody>
                {history.map((s) => (
                  <tr key={s.session_id}>
                    <td>
                      <Link to={s.is_completed ? `/practice/${s.session_id}/results` : `/practice/${s.session_id}`}>
                        {modeLabel(s.mode)}
                      </Link>
                    </td>
                    <td className="num">
                      {s.questions_answered}/{s.total_questions}
                    </td>
                    <td className="num">{pct(s.accuracy_pct)}</td>
                    <td className="num">{formatDuration(s.total_time_seconds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}

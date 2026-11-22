import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '../api.ts'
import { ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { formatDuration, modeLabel, pct } from '../format.ts'
import { useTopicLabel } from '../topics.ts'

export default function WeakAreas() {
  const { data, error, isPending } = useQuery({
    queryKey: ['weak-areas'],
    queryFn: () => api.weakAreas(),
  })
  const topicLabel = useTopicLabel()

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
                  <th className="col-actions">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {weak.map((a) => {
                  const label = topicLabel(a.topic)
                  return (
                    <tr key={a.topic}>
                      <td data-label="Tema">
                        <span className="pill">{label}</span>
                      </td>
                      <td className="cell-meter" data-label="Precisión">
                        <div className="row" style={{ flexWrap: 'nowrap', width: '100%' }}>
                          <div
                            className="meter meter-wrong"
                            style={{ flex: 1, minWidth: '6rem' }}
                            role="progressbar"
                            aria-label={`${label}, precisión`}
                            aria-valuenow={Math.round(a.accuracy_pct)}
                            aria-valuemin={0}
                            aria-valuemax={100}
                          >
                            <span style={{ width: `${a.accuracy_pct}%` }} />
                          </div>
                          <span className="num">{pct(a.accuracy_pct)}</span>
                        </div>
                      </td>
                      <td className="num" data-label="Correctas / Total">
                        {a.correct} / {a.total}
                      </td>
                      <td className="col-actions">
                        <div className="table-actions">
                          <ButtonLink to={`/practice?topic=${encodeURIComponent(a.topic)}`} small>
                            ▶ Practicar
                          </ButtonLink>
                          <ButtonLink to={`/questions?topic=${encodeURIComponent(a.topic)}`} variant="quiet" small>
                            Ver preguntas
                          </ButtonLink>
                        </div>
                      </td>
                    </tr>
                  )
                })}
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
                    <td data-label="Modo">
                      <Link to={s.is_completed ? `/practice/${s.session_id}/results` : `/practice/${s.session_id}`}>
                        {modeLabel(s.mode)}
                      </Link>
                    </td>
                    <td className="num" data-label="Progreso">
                      {s.questions_answered}/{s.total_questions}
                    </td>
                    <td className="num" data-label="Precisión">
                      <span className={`pill ${s.accuracy_pct >= 60 ? 'pill-right' : 'pill-wrong'}`}>
                        {pct(s.accuracy_pct)}
                      </span>
                    </td>
                    <td className="num" data-label="Tiempo">
                      {formatDuration(s.total_time_seconds)}
                    </td>
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

import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { api } from '../api.ts'
import { ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { formatDuration, modeLabel, pct } from '../format.ts'

export default function PracticeResults() {
  const sessionId = Number(useParams().sessionId)
  const { data, error, isPending } = useQuery({
    queryKey: ['practice-results', sessionId],
    queryFn: () => api.results(sessionId),
    enabled: Number.isFinite(sessionId),
  })

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const wrong = data.responses.filter((r) => r.is_correct === false)

  return (
    <div className="stack" style={{ gap: 'var(--s-6)' }}>
      <PageHead title={`Resultados de la sesión · ${modeLabel(data.mode)}`} />

      <Card>
        <div className="score">
          <strong className="num">{pct(data.accuracy)}</strong>
          <span className="muted">
            {data.correct_count} correctas, {data.incorrect_count} incorrectas, {data.skipped_count} saltadas ·{' '}
            {formatDuration(data.total_time_seconds)}
          </span>
        </div>
      </Card>

      <div className="row">
        <ButtonLink to="/practice" large>
          Practicar de nuevo
        </ButtonLink>
        <ButtonLink to="/" variant="quiet" large>
          Ir al dashboard
        </ButtonLink>
      </div>

      <Card title="Desglose por pregunta" aside={wrong.length > 0 ? <span className="pill pill-wrong">{wrong.length} por revisar</span> : undefined}>
        <ol className="review">
          {data.responses.map((r) => (
            <li key={r.question_id} className={r.skipped ? '' : r.is_correct ? 'is-right' : 'is-wrong'}>
              <p className="q">{r.question_text}</p>
              <dl>
                <dt>Tu respuesta</dt>
                <dd>{r.skipped ? 'No respondida' : r.selected_answer_text}</dd>
                {!r.is_correct && (
                  <>
                    <dt>Respuesta correcta</dt>
                    <dd>{r.correct_answer_text ?? '—'}</dd>
                  </>
                )}
                {r.explanation && !r.is_correct && (
                  <>
                    <dt>Explicación</dt>
                    <dd>{r.explanation}</dd>
                  </>
                )}
              </dl>
            </li>
          ))}
        </ol>
      </Card>
    </div>
  )
}

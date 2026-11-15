import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.ts'
import { Button, ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { formatDuration, modeLabel, pct } from '../format.ts'

export default function PracticeResults() {
  const sessionId = Number(useParams().sessionId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data, error, isPending } = useQuery({
    queryKey: ['practice-results', sessionId],
    queryFn: () => api.results(sessionId),
    enabled: Number.isFinite(sessionId),
  })

  // error_review draws from every question you ever missed, not only this attempt.
  const reviewErrors = useMutation({
    mutationFn: api.startPractice,
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate(`/practice/${session.session_id}`)
    },
  })

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const wrong = data.responses.filter((r) => r.is_correct === false)

  return (
    <div className="stack" style={{ gap: 'var(--s-6)' }}>
      <PageHead title={`Resultados de la sesión · ${modeLabel(data.mode)}`} />

      {data.lockout_reason && (
        <div
          style={{
            padding: 'var(--s-4)',
            background: 'var(--wrong-soft)',
            border: '2px solid var(--wrong)',
            borderRadius: 'var(--radius)',
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--s-3)',
          }}
        >
          <span style={{ fontSize: '2rem' }}>🚫</span>
          <div>
            <strong style={{ color: 'var(--wrong)', fontSize: '1.05rem' }}>
              Examen finalizado anticipadamente por sanción de anti-cheat
            </strong>
            <p style={{ margin: 'var(--s-1) 0 0', fontSize: '0.9rem', color: 'var(--ink)' }}>
              {data.lockout_reason === 'focus_lost'
                ? 'Se detectó cambio reiterado de pestaña o pérdida de foco de pantalla durante la simulación.'
                : data.lockout_reason}
            </p>
          </div>
        </div>
      )}

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
        {wrong.length > 0 && (
          <Button
            variant="quiet"
            large
            disabled={reviewErrors.isPending}
            onClick={() =>
              reviewErrors.mutate({
                mode: 'error_review',
                exam_id: null,
                topic: null,
                total_questions: Math.min(100, wrong.length),
              })
            }
          >
            {reviewErrors.isPending ? 'Iniciando…' : 'Repasar mis errores'}
          </Button>
        )}
        <ButtonLink to="/" variant="quiet" large>
          Ir al dashboard
        </ButtonLink>
      </div>
      {reviewErrors.error && <ErrorNotice error={reviewErrors.error} />}

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
                {r.explanation && (
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

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.ts'
import { useDeleteQuestion } from '../actions.ts'
import { Button, ButtonLink, Card, ErrorNotice, Flash, Loading, PageHead } from '../components.tsx'
import { useTopicLabel } from '../topics.ts'

export default function QuestionDetail() {
  const id = Number(useParams().questionId)
  const navigate = useNavigate()
  const topicLabel = useTopicLabel()
  const { data, error, isPending } = useQuery({
    queryKey: ['question', id],
    queryFn: () => api.question(id),
    enabled: Number.isFinite(id),
  })
  const queryClient = useQueryClient()
  const removeAnswer = useMutation({
    mutationFn: (answerId: number) => api.deleteAnswer(id, answerId),
    onSuccess: () => queryClient.invalidateQueries(),
  })
  const remove = useDeleteQuestion(() => navigate('/questions', { state: { flash: 'Pregunta eliminada' } }))

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const { question, answers, extracted_text, correction_notes } = data

  return (
    <div className="stack" style={{ gap: 'var(--s-5)' }}>
      <Flash />
      <PageHead title={`Pregunta #${question.id}`} />
      <div className="row">
        <span className="pill">{topicLabel(question.topic)}</span>
        <Link to={`/exams/${question.exam_id}`}>Examen #{question.exam_id}</Link>
      </div>
      <div className="row">
        <ButtonLink to={`/questions/${question.id}/correct`} variant="quiet">
          Corregir OCR
        </ButtonLink>
        <Button
          variant="danger"
          disabled={remove.isPending}
          onClick={() => remove.confirmAndDelete(question.id, question.question_text)}
        >
          Eliminar
        </Button>
        <ButtonLink to={`/questions/${question.id}/answers/new`} variant="quiet">
          + Agregar respuesta
        </ButtonLink>
        <Button variant="quiet" onClick={() => navigate(-1)}>
          Volver atrás
        </Button>
      </div>
      {(remove.error || removeAnswer.error) && <ErrorNotice error={(remove.error ?? removeAnswer.error)!} />}

      <Card
        title="Texto de la pregunta"
        aside={
          <span className={`pill ${question.is_corrected ? 'pill-right' : ''}`}>
            {question.is_corrected ? '✓ Corregida' : 'Sin corregir'}
          </span>
        }
      >
        <p className="question-text" style={{ margin: 0 }}>
          {question.question_text}
        </p>
        {correction_notes && (
          <p className="muted">
            <strong>Notas:</strong> {correction_notes}
          </p>
        )}
      </Card>

      {extracted_text && extracted_text !== question.question_text && (
        <Card title="Texto OCR original">
          <pre className="ocr-text">{extracted_text}</pre>
          {question.confidence_score != null && (
            <p className="hint" style={{ marginTop: 'var(--s-3)' }}>
              Confianza: {question.confidence_score.toFixed(1)}%
            </p>
          )}
        </Card>
      )}

      <Card
        title={`Respuestas (${answers.length})`}
        aside={
          answers.length > 1 ? <Link to={`/questions/${question.id}/answers/manage`}>Ordenar</Link> : undefined
        }
      >
        {answers.length === 0 ? (
          <div className="stack">
            <p className="muted">Agrega al menos una respuesta correcta para poder practicar.</p>
            <div className="row">
              <ButtonLink to={`/questions/${question.id}/answers/new`}>+ Agregar respuesta</ButtonLink>
            </div>
          </div>
        ) : (
          <ul className="answer-list">
              {answers.map((a) => (
                <li key={a.id} className={a.is_correct ? 'is-correct' : ''}>
                  <p>{a.answer_text}</p>
                  <div className="tags" style={{ marginTop: 'var(--s-1)' }}>
                    {a.is_correct && <span className="pill pill-right">✓ Correcta</span>}
                    {a.is_common_misconception && <span className="pill pill-warn">Error común</span>}
                  </div>
                  {a.explanation && <p className="why">{a.explanation}</p>}
                  <div className="table-actions" style={{ marginTop: 'var(--s-2)' }}>
                    <ButtonLink to={`/questions/${question.id}/answers/${a.id}/edit`} variant="quiet" small>
                      Editar
                    </ButtonLink>
                    <Button
                      variant="danger"
                      small
                      disabled={removeAnswer.isPending}
                      onClick={() => {
                        if (window.confirm('¿Eliminar esta respuesta? Esta acción no se puede deshacer.'))
                          removeAnswer.mutate(a.id)
                      }}
                    >
                      Eliminar
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
        )}
        {!question.is_ready_for_practice && (
          <div className="notice notice-info" style={{ marginTop: 'var(--s-4)' }}>
            Esta pregunta no tiene respuesta correcta — no aparecerá en práctica.
          </div>
        )}
      </Card>
    </div>
  )
}

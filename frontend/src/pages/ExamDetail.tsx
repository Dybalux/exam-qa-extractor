import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.ts'
import { useDeleteExam } from '../actions.ts'
import { Button, ButtonLink, Card, ErrorNotice, Flash, Loading, PageHead } from '../components.tsx'
import { formatExamDate, pct } from '../format.ts'

export default function ExamDetail() {
  const id = Number(useParams().examId)
  const navigate = useNavigate()
  const { data, error, isPending } = useQuery({
    queryKey: ['exam', id],
    queryFn: () => api.exam(id),
    enabled: Number.isFinite(id),
  })
  const remove = useDeleteExam(() => navigate('/exams', { state: { flash: 'Examen eliminado' } }))

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const { exam, coverage, questions } = data
  const subtitle = [exam.exam_date ? formatExamDate(exam.exam_date) : 'Sin fecha', exam.topic_tags]
    .filter(Boolean)
    .join(' · ')

  return (
    <div className="stack" style={{ gap: 'var(--s-6)' }}>
      <Flash />
      <PageHead title={`Parcial ${exam.partial_number}`} lead={subtitle} />

      <div className="row">
        <ButtonLink to={`/practice?exam_id=${exam.id}`}>▶ Practicar</ButtonLink>
        <ButtonLink to={`/exams/${exam.id}/questions/new`} variant="quiet">
          + Agregar pregunta
        </ButtonLink>
        <ButtonLink to={`/exams/${exam.id}/upload`} variant="quiet">
          ↑ Subir imagen
        </ButtonLink>
        <ButtonLink to={`/exams/${exam.id}/edit`} variant="quiet">
          Editar
        </ButtonLink>
        <Button variant="danger" disabled={remove.isPending} onClick={() => remove.confirmAndDelete(exam)}>
          Eliminar
        </Button>
      </div>
      {remove.error && <ErrorNotice error={remove.error} />}

      <dl className="facts">
        <div>
          <dt>Total preguntas</dt>
          <dd>{coverage.total_questions}</dd>
        </div>
        <div>
          <dt>Listas para practicar</dt>
          <dd>
            {coverage.ready_for_practice}
            <small>{pct(coverage.readiness_pct)}</small>
          </dd>
        </div>
        <div>
          <dt>Corregidas OCR</dt>
          <dd>
            {coverage.corrected}
            <small>{pct(coverage.correction_pct)}</small>
          </dd>
        </div>
      </dl>

      <Card title="Cobertura del examen" aside={<span className="muted num">{pct(coverage.readiness_pct)} listo</span>}>
        <div
          className="meter"
          role="progressbar"
          aria-label="Cobertura del examen"
          aria-valuenow={Math.round(coverage.readiness_pct)}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <span style={{ width: `${coverage.readiness_pct}%` }} />
        </div>
      </Card>

      <Card
        title={`Preguntas (${questions.length})`}
        aside={<Link to={`/questions/review?exam_id=${exam.id}`}>Revisar OCR</Link>}
      >
        {questions.length === 0 ? (
          <div className="stack">
            <p className="muted">Sube una imagen del examen para extraer preguntas con OCR.</p>
            <div className="row">
              <ButtonLink to={`/exams/${exam.id}/upload`}>↑ Subir imagen</ButtonLink>
            </div>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Pregunta</th>
                  <th>Tema</th>
                  <th>Estado</th>
                  <th className="col-actions">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {questions.map((q) => (
                  <tr key={q.id}>
                    <td className="num" data-label="#">
                      {q.order_in_exam ?? '—'}
                    </td>
                    <td className="cell-text" data-label="Pregunta">
                      <Link to={`/questions/${q.id}`}>
                        {q.question_text.length > 80 ? `${q.question_text.slice(0, 80)}…` : q.question_text}
                      </Link>
                    </td>
                    <td data-label="Tema">
                      <span className="pill">{q.topic}</span>
                    </td>
                    <td data-label="Estado">
                      <div className="tags">
                        <span className={`pill ${q.is_ready_for_practice ? 'pill-right' : ''}`}>
                          {q.is_ready_for_practice ? '✓ Lista' : 'Sin respuesta'}
                        </span>
                        {!q.is_corrected && q.confidence_score != null && q.confidence_score < 60 && (
                          <span className="pill pill-warn">OCR bajo</span>
                        )}
                      </div>
                    </td>
                    <td className="col-actions">
                      <div className="table-actions">
                        <ButtonLink to={`/questions/${q.id}`} variant="quiet" small>
                          Ver
                        </ButtonLink>
                        {!q.is_corrected && (
                          <ButtonLink to={`/questions/${q.id}/correct`} variant="quiet" small>
                            Corregir
                          </ButtonLink>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

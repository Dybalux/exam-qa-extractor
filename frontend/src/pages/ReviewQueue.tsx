import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.ts'
import { ButtonLink, Card, ErrorNotice, Flash, Loading, PageHead } from '../components.tsx'

export default function ReviewQueue() {
  const examId = useSearchParams()[0].get('exam_id') ?? ''
  const { data, error, isPending } = useQuery({
    queryKey: ['review', examId],
    queryFn: () => api.reviewQueue(examId),
  })

  return (
    <div className="stack" style={{ gap: 'var(--s-5)' }}>
      <Flash />
      <PageHead
        title="Cola de revisión OCR"
        lead={data ? `${data.questions.length} pregunta(s) con baja confianza o sin corregir` : undefined}
      />

      <nav className="chips" aria-label="Filtrar por examen">
        <Link to="/questions/review" className={`chip${examId === '' ? ' active' : ''}`}>
          Todos
        </Link>
        {data?.exams.map((x) => (
          <Link
            key={x.id}
            to={`/questions/review?exam_id=${x.id}`}
            className={`chip${examId === String(x.id) ? ' active' : ''}`}
          >
            Parcial {x.partial_number}
          </Link>
        ))}
      </nav>

      {isPending ? (
        <Loading />
      ) : error ? (
        <ErrorNotice error={error} />
      ) : data.questions.length === 0 ? (
        <Card flat>
          <h2>¡Todo revisado!</h2>
          <p className="muted">No hay preguntas pendientes de revisión OCR.</p>
          <ButtonLink to="/questions">Ver todas las preguntas</ButtonLink>
        </Card>
      ) : (
        <Card>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Pregunta</th>
                  <th>Confianza</th>
                  <th>Tema</th>
                  <th>Examen</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {data.questions.map((q) => (
                  <tr key={q.id}>
                    <td className="cell-text">
                      {q.question_text.length > 80 ? `${q.question_text.slice(0, 80)}…` : q.question_text}
                    </td>
                    <td className="num">
                      {q.confidence_score != null ? (
                        <span className={`pill ${q.confidence_score < 40 ? 'pill-wrong' : 'pill-warn'}`}>
                          {Math.round(q.confidence_score)}%
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <span className="pill">{q.topic}</span>
                    </td>
                    <td>
                      <Link to={`/exams/${q.exam_id}`}>Examen #{q.exam_id}</Link>
                    </td>
                    <td>
                      <div className="table-actions">
                        <Link to={`/questions/${q.id}/correct`}>Corregir</Link>
                        <Link to={`/questions/${q.id}`}>Ver</Link>
                      </div>
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

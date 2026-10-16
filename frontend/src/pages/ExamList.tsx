import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.ts'
import { useDeleteExam } from '../actions.ts'
import { Button, ButtonLink, Card, ErrorNotice, Flash, Loading, PageHead } from '../components.tsx'
import { formatExamDate, splitTags } from '../format.ts'

export default function ExamList() {
  const [params] = useSearchParams()
  const partial = params.get('partial_number') ?? ''
  const { data, error, isPending } = useQuery({
    queryKey: ['exams', partial],
    queryFn: () => api.exams(partial),
    placeholderData: keepPreviousData,
  })
  const remove = useDeleteExam()

  return (
    <div className="stack" style={{ gap: 'var(--s-5)' }}>
      <Flash />
      <PageHead
        title="Exámenes"
        lead={data ? `${data.length} examen(es) cargado(s)` : undefined}
      />
      <div className="row">
        <ButtonLink to="/exams/new">+ Nuevo examen</ButtonLink>
      </div>

      <nav className="chips" aria-label="Filtrar por parcial">
        <Link to="/exams" className={`chip${partial === '' ? ' active' : ''}`}>
          Todos
        </Link>
        {[1, 2, 3, 4].map((p) => (
          <Link
            key={p}
            to={`/exams?partial_number=${p}`}
            className={`chip${partial === String(p) ? ' active' : ''}`}
          >
            Parcial {p}
          </Link>
        ))}
      </nav>

      {remove.error && <ErrorNotice error={remove.error} />}

      {isPending ? (
        <Loading />
      ) : error ? (
        <ErrorNotice error={error} />
      ) : data.length === 0 ? (
        <Card flat>
          <h2>No hay exámenes todavía</h2>
          <p className="muted">Crea el primer examen para empezar a cargar preguntas.</p>
          <ButtonLink to="/exams/new">+ Crear examen</ButtonLink>
        </Card>
      ) : (
        <Card>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th className="col-nowrap">Parcial</th>
                  <th className="col-nowrap">Fecha</th>
                  <th>Tags</th>
                  <th className="text-center col-nowrap">Preguntas</th>
                  <th className="col-actions col-nowrap">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {data.map((exam) => (
                  <tr key={exam.id}>
                    <td className="col-nowrap" data-label="Parcial">
                      <Link to={`/exams/${exam.id}`}>Parcial {exam.partial_number}</Link>
                    </td>
                    <td className="num col-nowrap" data-label="Fecha">
                      {formatExamDate(exam.exam_date)}
                    </td>
                    <td data-label="Tags">
                      {splitTags(exam.topic_tags).length === 0 ? (
                        <span className="muted">—</span>
                      ) : (
                        <div className="tags">
                          {splitTags(exam.topic_tags).map((t) => (
                            <span key={t} className="pill">
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="num text-center col-nowrap" data-label="Preguntas">
                      {exam.question_count}
                    </td>
                    <td className="col-actions col-nowrap">
                      <div className="table-actions">
                        <ButtonLink to={`/exams/${exam.id}/upload`} variant="quiet" small>
                          ↑ Subir imagen
                        </ButtonLink>
                        <ButtonLink to={`/exams/${exam.id}/edit`} variant="quiet" small>
                          Editar
                        </ButtonLink>
                        <Button
                          variant="danger"
                          small
                          disabled={remove.isPending}
                          onClick={() => remove.confirmAndDelete(exam)}
                        >
                          Eliminar
                        </Button>
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

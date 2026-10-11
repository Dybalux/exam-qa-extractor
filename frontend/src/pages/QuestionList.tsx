import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type QuestionFilters } from '../api.ts'
import { useDeleteQuestion } from '../actions.ts'
import { Button, ButtonLink, Card, ErrorNotice, Flash, Loading, PageHead } from '../components.tsx'
import { examLabel } from '../format.ts'

const KEYS = ['exam_id', 'topic', 'is_ready', 'is_corrected'] as const

export default function QuestionList() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const filters: QuestionFilters = Object.fromEntries(KEYS.map((k) => [k, params.get(k) ?? '']))
  const { data, error, isPending } = useQuery({
    queryKey: ['questions', filters],
    queryFn: () => api.questions(filters),
  })
  const remove = useDeleteQuestion()

  const setFilter = (key: (typeof KEYS)[number], value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  return (
    <div className="stack" style={{ gap: 'var(--s-5)' }}>
      <Flash />
      <PageHead
        title="Preguntas"
        lead={data ? `${data.questions.length} pregunta(s) encontrada(s)` : undefined}
      />
      <div className="row">
        <ButtonLink to="/questions/review" variant="quiet">
          Revisar OCR
        </ButtonLink>
      </div>

      <Card>
        <div className="filters">
          <div className="field">
            <label htmlFor="f-exam">Examen</label>
            <select
              id="f-exam"
              className="control"
              value={filters.exam_id}
              onChange={(e) => setFilter('exam_id', e.target.value)}
            >
              <option value="">Todos los exámenes</option>
              {data?.exams.map((x) => (
                <option key={x.id} value={x.id}>
                  {examLabel(x)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-topic">Tema</label>
            <select
              id="f-topic"
              className="control"
              value={filters.topic}
              onChange={(e) => setFilter('topic', e.target.value)}
            >
              <option value="">Todos los temas</option>
              {data?.topics.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-ready">Respuesta</label>
            <select
              id="f-ready"
              className="control"
              value={filters.is_ready}
              onChange={(e) => setFilter('is_ready', e.target.value)}
            >
              <option value="">Todas</option>
              <option value="true">Con respuesta</option>
              <option value="false">Sin respuesta</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="f-corrected">Estado OCR</label>
            <select
              id="f-corrected"
              className="control"
              value={filters.is_corrected}
              onChange={(e) => setFilter('is_corrected', e.target.value)}
            >
              <option value="">Cualquier estado OCR</option>
              <option value="true">Corregidas</option>
              <option value="false">Sin corregir</option>
            </select>
          </div>
          <Button variant="quiet" onClick={() => setParams({}, { replace: true })}>
            Limpiar
          </Button>
        </div>
      </Card>

      {remove.error && <ErrorNotice error={remove.error} />}

      {isPending ? (
        <Loading />
      ) : error ? (
        <ErrorNotice error={error} />
      ) : data.questions.length === 0 ? (
        <Card flat>
          <h2>Sin preguntas</h2>
          <p className="muted">No hay preguntas que coincidan con los filtros.</p>
        </Card>
      ) : (
        <Card>
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Pregunta</th>
                  <th>Examen</th>
                  <th>Tema</th>
                  <th>Estado</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {data.questions.map((q) => (
                  <tr key={q.id}>
                    <td className="cell-text">
                      <Link to={`/questions/${q.id}`}>{q.question_text}</Link>
                      {q.confidence_score != null && (
                        <div className="hint">OCR: {Math.round(q.confidence_score)}%</div>
                      )}
                    </td>
                    <td>
                      <Link to={`/exams/${q.exam_id}`}>Examen #{q.exam_id}</Link>
                    </td>
                    <td>
                      <span className="pill">{q.topic}</span>
                    </td>
                    <td>
                      <div className="tags">
                        <span className={`pill ${q.is_ready_for_practice ? 'pill-right' : ''}`}>
                          {q.is_ready_for_practice ? '✓ Lista' : 'Sin respuesta'}
                        </span>
                        {q.is_corrected && <span className="pill">Corregida</span>}
                      </div>
                    </td>
                    <td>
                      <div className="table-actions">
                        <Link to={`/questions/${q.id}`}>Ver</Link>
                        {!q.is_corrected && <Link to={`/questions/${q.id}/correct`}>Corregir</Link>}
                        <Button
                          variant="danger"
                          small
                          disabled={remove.isPending}
                          onClick={() => remove.confirmAndDelete(q.id, q.question_text)}
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
      <div className="row">
        <Button variant="quiet" onClick={() => navigate('/exams')}>
          Ir a exámenes para agregar preguntas
        </Button>
      </div>
    </div>
  )
}

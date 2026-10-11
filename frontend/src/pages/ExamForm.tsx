import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type ExamInput } from '../api.ts'
import { Button, ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'

function ExamFormFields({ initial, examId }: { initial: ExamInput; examId?: number }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [partial, setPartial] = useState(String(initial.partial_number))
  const [date, setDate] = useState(initial.exam_date ?? '')
  const [tags, setTags] = useState(initial.topic_tags ?? '')

  const save = useMutation({
    mutationFn: (input: ExamInput) =>
      examId ? api.updateExam(examId, input) : api.createExam(input),
    onSuccess: () => {
      queryClient.invalidateQueries()
      navigate('/exams', { state: { flash: 'Examen guardado' } })
    },
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate({
      partial_number: Number(partial),
      exam_date: date || null,
      topic_tags: tags.trim() || null,
    })
  }

  return (
    <Card>
      <form onSubmit={onSubmit} className="stack" style={{ gap: 'var(--s-5)' }}>
        <div className="field">
          <label htmlFor="partial">Número de parcial *</label>
          <select
            id="partial"
            className="control"
            required
            value={partial}
            onChange={(e) => setPartial(e.target.value)}
          >
            {[1, 2, 3, 4].map((p) => (
              <option key={p} value={p}>
                Parcial {p}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="date">Fecha del examen</label>
          <input id="date" className="control" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          <p className="hint">Opcional, ayuda a organizar por fecha.</p>
        </div>
        <div className="field">
          <label htmlFor="tags">Tags de temas</label>
          <input
            id="tags"
            className="control"
            type="text"
            placeholder="procesos, memoria, sincronización"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
          />
          <p className="hint">Separados por coma. Ayuda a filtrar y buscar.</p>
        </div>
        {save.error && <ErrorNotice error={save.error} />}
        <div className="row">
          <Button type="submit" large disabled={save.isPending}>
            {save.isPending ? 'Guardando…' : examId ? 'Guardar cambios' : '+ Crear examen'}
          </Button>
          <ButtonLink to="/exams" variant="quiet" large>
            Cancelar
          </ButtonLink>
        </div>
      </form>
    </Card>
  )
}

export default function ExamForm() {
  const id = Number(useParams().examId)
  const editing = useParams().examId !== undefined
  const exam = useQuery({
    queryKey: ['exam', id],
    queryFn: () => api.exam(id),
    enabled: editing && Number.isFinite(id),
  })

  if (editing && exam.isPending) return <Loading />
  if (editing && exam.error) return <ErrorNotice error={exam.error} />

  const initial: ExamInput = exam.data
    ? {
        partial_number: exam.data.exam.partial_number,
        exam_date: exam.data.exam.exam_date,
        topic_tags: exam.data.exam.topic_tags,
      }
    : { partial_number: 1, exam_date: null, topic_tags: null }

  return (
    <div className="stack form-card" style={{ gap: 'var(--s-5)' }}>
      <PageHead title={editing ? 'Editar examen' : 'Nuevo examen'} />
      <ExamFormFields initial={initial} examId={editing ? id : undefined} />
    </div>
  )
}

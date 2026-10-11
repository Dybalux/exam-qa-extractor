import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api.ts'
import { Button, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { MODE_INFO } from '../format.ts'

export default function PracticeStart() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const options = useQuery({ queryKey: ['practice-options'], queryFn: api.practiceOptions })

  // Deep links from exams and weak areas preselect the filters (?exam_id=…&topic=…).
  const [params] = useSearchParams()
  const [mode, setMode] = useState(() =>
    params.get('exam_id') ? 'by_partial' : params.get('topic') ? 'by_topic' : 'random',
  )
  const [examId, setExamId] = useState(() => params.get('exam_id') ?? '')
  const [topic, setTopic] = useState(() => params.get('topic') ?? '')
  const [total, setTotal] = useState(10)

  const start = useMutation({
    mutationFn: api.startPractice,
    onSuccess: (session) => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate(`/practice/${session.session_id}`)
    },
  })

  if (options.isPending) return <Loading />
  if (options.error) return <ErrorNotice error={options.error} />

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    start.mutate({
      mode,
      exam_id: examId ? Number(examId) : null,
      topic: topic || null,
      total_questions: total,
    })
  }

  const { modes, exams, topics } = options.data

  return (
    <form className="stack" style={{ gap: 'var(--s-6)' }} onSubmit={onSubmit}>
      <PageHead title="Iniciar práctica" lead="Configura tu sesión de estudio" />

      <fieldset className="mode-grid">
        <legend style={{ marginBottom: 'var(--s-2)' }}>Modo de práctica</legend>
        {modes.map((m) => (
          <label key={m} className="mode">
            <input type="radio" name="mode" value={m} checked={mode === m} onChange={() => setMode(m)} />
            <strong>{MODE_INFO[m]?.label ?? m}</strong>
            <span>{MODE_INFO[m]?.hint}</span>
          </label>
        ))}
      </fieldset>

      <Card title="Filtros">
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <div className="field">
            <label htmlFor="exam">Examen (opcional)</label>
            <select id="exam" className="control" value={examId} onChange={(e) => setExamId(e.target.value)}>
              <option value="">Todos</option>
              {exams.map((x) => (
                <option key={x.id} value={x.id}>
                  Parcial {x.partial_number}
                  {x.exam_date ? ` · ${x.exam_date}` : ''}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="topic">Tema (opcional)</label>
            <select id="topic" className="control" value={topic} onChange={(e) => setTopic(e.target.value)}>
              <option value="">Todos</option>
              {topics.map((t) => (
                <option key={t.slug} value={t.slug}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ minWidth: '8rem', flex: '0 0 8rem' }}>
            <label htmlFor="total">Cantidad de preguntas</label>
            <input
              id="total"
              className="control num"
              type="number"
              min={1}
              max={100}
              value={total}
              onChange={(e) => setTotal(Math.min(100, Math.max(1, Number(e.target.value) || 1)))}
            />
          </div>
        </div>
      </Card>

      {start.error && <ErrorNotice error={start.error} />}

      <div className="row">
        <Button type="submit" large disabled={start.isPending}>
          {start.isPending ? 'Iniciando…' : 'Comenzar'}
        </Button>
      </div>
    </form>
  )
}

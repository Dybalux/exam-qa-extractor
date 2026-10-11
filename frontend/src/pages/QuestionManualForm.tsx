import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.ts'
import { Button, ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { examLabel } from '../format.ts'

export default function QuestionManualForm() {
  const examId = Number(useParams().examId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const exam = useQuery({ queryKey: ['exam', examId], queryFn: () => api.exam(examId), enabled: Number.isFinite(examId) })
  const topics = useQuery({ queryKey: ['topics'], queryFn: api.topics })

  const [text, setText] = useState('')
  const [topic, setTopic] = useState('')
  const [order, setOrder] = useState('')
  const [correct, setCorrect] = useState('')
  const [explanation, setExplanation] = useState('')

  const save = useMutation({
    mutationFn: () =>
      api.createManualQuestion(examId, {
        question_text: text.trim(),
        topic,
        order_in_exam: order ? Number(order) : null,
        correct_answer_text: correct.trim(),
        explanation: explanation.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries()
      navigate('/questions', { state: { flash: 'Pregunta guardada' } })
    },
  })

  if (exam.isPending || topics.isPending) return <Loading />
  if (exam.error) return <ErrorNotice error={exam.error} />
  if (topics.error) return <ErrorNotice error={topics.error} />

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="stack form-card" style={{ gap: 'var(--s-5)' }}>
      <PageHead title="Nueva pregunta" lead={examLabel(exam.data.exam)} />
      <Card>
        <form onSubmit={onSubmit} className="stack" style={{ gap: 'var(--s-5)' }}>
          <div className="field">
            <label htmlFor="q-text">Texto de la pregunta *</label>
            <textarea
              id="q-text"
              className="control"
              rows={4}
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Escribe el enunciado de la pregunta…"
            />
          </div>
          <div className="row" style={{ alignItems: 'flex-start' }}>
            <div className="field">
              <label htmlFor="q-topic">Tema *</label>
              <select id="q-topic" className="control" required value={topic} onChange={(e) => setTopic(e.target.value)}>
                <option value="">Selecciona un tema…</option>
                {topics.data.map((t) => (
                  <option key={t.slug} value={t.slug}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field" style={{ flex: '0 0 9rem', minWidth: '8rem' }}>
              <label htmlFor="q-order">Número en el examen</label>
              <input
                id="q-order"
                className="control num"
                type="number"
                min={1}
                value={order}
                onChange={(e) => setOrder(e.target.value)}
              />
            </div>
          </div>
          <div className="field">
            <label htmlFor="q-correct">Respuesta correcta *</label>
            <textarea
              id="q-correct"
              className="control"
              rows={2}
              required
              value={correct}
              onChange={(e) => setCorrect(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="q-expl">Explicación</label>
            <textarea
              id="q-expl"
              className="control"
              rows={3}
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
            />
            <p className="hint">Opcional. Se muestra al responder en práctica.</p>
          </div>
          {save.error && <ErrorNotice error={save.error} />}
          <div className="row">
            <Button type="submit" large disabled={save.isPending}>
              {save.isPending ? 'Guardando…' : 'Guardar pregunta'}
            </Button>
            <ButtonLink to={`/exams/${examId}`} variant="quiet" large>
              Cancelar
            </ButtonLink>
          </div>
        </form>
      </Card>
    </div>
  )
}

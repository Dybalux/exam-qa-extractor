import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api, type AnswerRow } from '../api.ts'
import { Button, ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'

function AnswerFormFields({ questionId, answer }: { questionId: number; answer?: AnswerRow }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [text, setText] = useState(answer?.answer_text ?? '')
  const [type, setType] = useState(answer?.answer_type ?? 'incorrect')
  const [explanation, setExplanation] = useState(answer?.explanation ?? '')
  const [misconception, setMisconception] = useState(answer?.is_common_misconception ?? false)

  const save = useMutation({
    mutationFn: () => {
      const input = {
        answer_text: text.trim(),
        answer_type: type,
        explanation: explanation.trim() || null,
        is_common_misconception: misconception,
      }
      return answer
        ? api.updateAnswer(questionId, answer.id, input)
        : api.createAnswer(questionId, input)
    },
    onSuccess: () => {
      queryClient.invalidateQueries()
      navigate(`/questions/${questionId}`, {
        state: { flash: answer ? 'Respuesta actualizada correctamente' : 'Respuesta agregada correctamente' },
      })
    },
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <Card>
      <form onSubmit={onSubmit} className="stack" style={{ gap: 'var(--s-5)' }}>
        <div className="field">
          <label htmlFor="a-text">Texto de la respuesta *</label>
          <textarea
            id="a-text"
            className="control"
            rows={4}
            required
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Escribe la respuesta…"
          />
        </div>
        <div className="field">
          <label htmlFor="a-type">Tipo *</label>
          <select id="a-type" className="control" required value={type} onChange={(e) => setType(e.target.value)}>
            <option value="correct">✓ Correcta</option>
            <option value="incorrect">✗ Incorrecta</option>
            <option value="partial">~ Parcialmente correcta</option>
          </select>
          <p className="hint">Solo puede haber una respuesta correcta por pregunta.</p>
        </div>
        <div className="field">
          <label htmlFor="a-expl">Explicación</label>
          <textarea
            id="a-expl"
            className="control"
            rows={3}
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
            placeholder="¿Por qué es correcta/incorrecta?"
          />
          <p className="hint">Se muestra después de responder en modo práctica.</p>
        </div>
        <label className="check-row">
          <input type="checkbox" checked={misconception} onChange={(e) => setMisconception(e.target.checked)} />
          <span>Error común (confunde a muchos estudiantes)</span>
        </label>
        {save.error && <ErrorNotice error={save.error} />}
        <div className="row">
          <Button type="submit" large disabled={save.isPending}>
            {save.isPending ? 'Guardando…' : answer ? 'Guardar' : '+ Crear respuesta'}
          </Button>
          <ButtonLink to={`/questions/${questionId}`} variant="quiet" large>
            Cancelar
          </ButtonLink>
        </div>
      </form>
    </Card>
  )
}

/** Create (`/questions/:id/answers/new`) and edit (`…/answers/:answerId/edit`) in one screen. */
export default function AnswerForm() {
  const params = useParams()
  const questionId = Number(params.questionId)
  const answerId = params.answerId === undefined ? undefined : Number(params.answerId)
  const { data, error, isPending } = useQuery({
    queryKey: ['question', questionId],
    queryFn: () => api.question(questionId),
    enabled: Number.isFinite(questionId),
  })

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const answer = answerId === undefined ? undefined : data.answers.find((a) => a.id === answerId)
  if (answerId !== undefined && !answer) {
    return <ErrorNotice error={new Error('La respuesta no existe.')} />
  }

  const preview = data.question.question_text
  return (
    <div className="stack form-card" style={{ gap: 'var(--s-5)' }}>
      <PageHead
        title={answer ? 'Editar respuesta' : 'Nueva respuesta'}
        lead={preview.length > 80 ? `${preview.slice(0, 80)}…` : preview}
      />
      <AnswerFormFields key={answer?.id ?? 'new'} questionId={questionId} answer={answer} />
    </div>
  )
}

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type AnswerRow } from '../api.ts'
import { Button, ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'

const TYPE_LABEL: Record<string, string> = {
  correct: 'Correcta',
  incorrect: 'Incorrecta',
  partial: 'Parcialmente correcta',
}

function OrderList({ questionId, initial }: { questionId: number; initial: AnswerRow[] }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [items, setItems] = useState(initial)
  const [dragging, setDragging] = useState<number | null>(null)

  const save = useMutation({
    mutationFn: () => api.reorderAnswers(questionId, items.map((a) => a.id)),
    onSuccess: () => {
      queryClient.invalidateQueries()
      navigate(`/questions/${questionId}`, { state: { flash: 'Orden guardado' } })
    },
  })

  const move = (from: number, to: number) => {
    if (to < 0 || to >= items.length || from === to) return
    const next = [...items]
    next.splice(to, 0, next.splice(from, 1)[0])
    setItems(next)
  }

  const dirty = items.some((a, i) => a.id !== initial[i].id)

  return (
    <div className="stack">
      <ul className="answer-list">
        {items.map((a, i) => (
          <li
            key={a.id}
            draggable
            onDragStart={() => setDragging(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => {
              if (dragging !== null) move(dragging, i)
              setDragging(null)
            }}
            onDragEnd={() => setDragging(null)}
            className={a.is_correct ? 'is-correct' : ''}
            style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-3)', opacity: dragging === i ? 0.5 : 1 }}
          >
            <span aria-hidden="true" className="muted" style={{ cursor: 'grab' }}>
              ⠿
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p>{a.answer_text.length > 80 ? `${a.answer_text.slice(0, 80)}…` : a.answer_text}</p>
              <div className="tags" style={{ marginTop: 'var(--s-1)' }}>
                {a.is_correct && <span className="pill pill-right">✓ Correcta</span>}
                {a.is_common_misconception && <span className="pill pill-warn">Error común</span>}
                <span className="pill">{TYPE_LABEL[a.answer_type] ?? a.answer_type}</span>
              </div>
            </div>
            <div className="table-actions">
              <Button variant="quiet" small disabled={i === 0} aria-label="Subir" onClick={() => move(i, i - 1)}>
                ↑
              </Button>
              <Button
                variant="quiet"
                small
                disabled={i === items.length - 1}
                aria-label="Bajar"
                onClick={() => move(i, i + 1)}
              >
                ↓
              </Button>
              <Link to={`/questions/${questionId}/answers/${a.id}/edit`}>Editar</Link>
            </div>
          </li>
        ))}
      </ul>
      {save.error && <ErrorNotice error={save.error} />}
      <div className="row">
        <Button large disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? 'Guardando…' : 'Guardar orden'}
        </Button>
      </div>
    </div>
  )
}

export default function AnswerManage() {
  const questionId = Number(useParams().questionId)
  const { data, error, isPending } = useQuery({
    queryKey: ['question', questionId],
    queryFn: () => api.question(questionId),
    enabled: Number.isFinite(questionId),
  })

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const text = data.question.question_text
  return (
    <div className="stack" style={{ gap: 'var(--s-5)' }}>
      <PageHead title="Gestionar respuestas" lead={text.length > 60 ? `${text.slice(0, 60)}…` : text} />
      <div className="row">
        <ButtonLink to={`/questions/${questionId}/answers/new`}>+ Nueva</ButtonLink>
        <ButtonLink to={`/questions/${questionId}`} variant="quiet">
          Volver
        </ButtonLink>
      </div>
      <Card
        title="Respuestas — arrastra o usa las flechas para reordenar"
        aside={<span className="muted">{data.answers.length} respuesta(s)</span>}
      >
        {data.answers.length === 0 ? (
          <div className="stack">
            <p className="muted">Sin respuestas.</p>
            <div className="row">
              <ButtonLink to={`/questions/${questionId}/answers/new`}>+ Agregar primera respuesta</ButtonLink>
            </div>
          </div>
        ) : (
          <OrderList questionId={questionId} initial={data.answers} />
        )}
      </Card>
    </div>
  )
}

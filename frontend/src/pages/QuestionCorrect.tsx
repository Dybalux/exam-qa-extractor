import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.ts'
import { Button, ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'

function CorrectionForm({ id, initialText, initialNotes }: { id: number; initialText: string; initialNotes: string }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [text, setText] = useState(initialText)
  const [notes, setNotes] = useState(initialNotes)

  const save = useMutation({
    mutationFn: () => api.correctQuestion(id, { corrected_text: text.trim(), notes: notes.trim() || null }),
    onSuccess: () => {
      queryClient.invalidateQueries()
      navigate('/questions', { state: { flash: 'Corrección guardada' } })
    },
  })

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <form onSubmit={onSubmit} className="stack" style={{ gap: 'var(--s-5)' }}>
      <div className="field">
        <label htmlFor="c-text">Texto corregido *</label>
        <textarea
          id="c-text"
          className="control"
          rows={8}
          required
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Escribe el texto correcto de la pregunta…"
        />
        <p className="hint">Este texto reemplazará al texto actual y marcará la pregunta como corregida.</p>
      </div>
      <div className="field">
        <label htmlFor="c-notes">Notas de corrección</label>
        <input
          id="c-notes"
          className="control"
          type="text"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Ej: Se agregó tilde, se corrigió 'procesoo' → 'proceso'"
        />
        <p className="hint">Opcional. Útil para documentar qué cambió.</p>
      </div>
      {save.error && <ErrorNotice error={save.error} />}
      <div className="row">
        <Button type="submit" large disabled={save.isPending}>
          {save.isPending ? 'Guardando…' : '✓ Guardar corrección'}
        </Button>
        <ButtonLink to="/questions" variant="quiet" large>
          Cancelar
        </ButtonLink>
      </div>
    </form>
  )
}

export default function QuestionCorrect() {
  const id = Number(useParams().questionId)
  const { data, error, isPending } = useQuery({
    queryKey: ['question', id],
    queryFn: () => api.question(id),
    enabled: Number.isFinite(id),
  })

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const { question, extracted_text, correction_notes } = data

  return (
    <div className="stack form-card" style={{ gap: 'var(--s-5)' }}>
      <PageHead title="Corregir texto OCR" lead={`Pregunta #${question.id} · Examen #${question.exam_id}`} />
      <Card
        title="Texto OCR original"
        aside={
          question.confidence_score != null ? (
            <span className="pill">{Math.round(question.confidence_score)}% confianza</span>
          ) : undefined
        }
      >
        <pre className="ocr-text">{extracted_text || question.question_text}</pre>
      </Card>
      <Card title="Texto corregido">
        <CorrectionForm id={id} initialText={question.question_text} initialNotes={correction_notes ?? ''} />
      </Card>
    </div>
  )
}

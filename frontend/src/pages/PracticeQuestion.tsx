import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import {
  api,
  type AnswerFeedback,
  type PracticeQuestion as Question,
  type SessionProgress,
} from '../api.ts'
import { Button, ErrorNotice, Loading } from '../components.tsx'
import { modeLabel } from '../format.ts'

type Outcome = 'right' | 'wrong' | 'skip'

function Ticks({ session, outcomes }: { session: SessionProgress; outcomes: Outcome[] }) {
  return (
    <div
      className="ticks"
      role="progressbar"
      aria-label="Progreso de la sesión"
      aria-valuemin={0}
      aria-valuemax={session.total_questions}
      aria-valuenow={session.questions_answered}
    >
      {Array.from({ length: session.total_questions }, (_, i) => {
        const done = i < session.questions_answered + session.skipped_count
        // Outcomes are tracked locally; after a reload earlier ones show as neutral.
        const cls = outcomes[i] ? `tick-${outcomes[i]}` : done ? 'tick-skip' : i === outcomes.length ? 'tick-now' : ''
        return <span key={i} className={`tick ${cls}`} />
      })}
    </div>
  )
}

const KEYS = 'ABCDEFGH'

function QuestionCard({
  sessionId,
  question,
  onAnswered,
  onSkipped,
  onNext,
}: {
  sessionId: number
  question: Question
  onAnswered: (fb: AnswerFeedback) => void
  onSkipped: () => void
  onNext: () => void
}) {
  const startedAt = useRef(Date.now())
  const [picked, setPicked] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<AnswerFeedback | null>(null)
  const elapsed = () => Math.round((Date.now() - startedAt.current) / 1000)

  const submit = useMutation({
    mutationFn: (answerId: number) =>
      api.submitAnswer(sessionId, {
        question_id: question.id,
        selected_answer_id: answerId,
        time_spent_seconds: elapsed(),
      }),
    onSuccess: (fb) => {
      setFeedback(fb)
      onAnswered(fb)
    },
  })

  const skip = useMutation({
    mutationFn: () =>
      api.skipQuestion(sessionId, { question_id: question.id, time_spent_seconds: elapsed() }),
    onSuccess: onSkipped,
  })

  const choose = (id: number) => {
    if (feedback || submit.isPending) return
    setPicked(id)
    submit.mutate(id)
  }

  // Keyboard: A–H picks an option, Enter moves on once feedback is showing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (feedback) {
        if (e.key === 'Enter') onNext()
        return
      }
      const idx = KEYS.indexOf(e.key.toUpperCase())
      if (e.key.length === 1 && idx >= 0 && idx < question.answers.length) {
        choose(question.answers[idx].id)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const error = submit.error ?? skip.error

  return (
    <div>
      <span className="pill">{question.topic}</span>
      <p className="question-text">{question.text}</p>

      <ul className="options">
        {question.answers.map((a, i) => {
          let state = ''
          if (feedback) {
            if (a.id === feedback.correct_answer_id) state = 'option-right'
            else if (a.id === picked) state = 'option-wrong'
          }
          return (
            <li key={a.id}>
              <button
                type="button"
                className={`option ${state}`}
                disabled={feedback !== null || submit.isPending || skip.isPending}
                onClick={() => choose(a.id)}
                aria-pressed={picked === a.id}
              >
                <span className="option-key">{KEYS[i]}</span>
                <span className="option-text">{a.text}</span>
              </button>
            </li>
          )
        })}
      </ul>

      {error && (
        <div style={{ marginTop: 'var(--s-4)' }}>
          <ErrorNotice error={error} />
        </div>
      )}

      {feedback && (
        <div className={`verdict ${feedback.is_correct ? '' : 'verdict-wrong'}`} role="status">
          <h3>{feedback.is_correct ? 'Correcta' : 'Incorrecta'}</h3>
          {!feedback.is_correct && feedback.correct_answer_text && (
            <p>La respuesta correcta está resaltada arriba.</p>
          )}
          {feedback.explanation && <p className="explain">{feedback.explanation}</p>}
        </div>
      )}

      <div className="actions">
        {feedback ? (
          <Button onClick={onNext} large>
            {feedback.session.questions_answered + feedback.session.skipped_count >=
            feedback.session.total_questions
              ? 'Ver resultados'
              : 'Siguiente pregunta'}
          </Button>
        ) : (
          <Button variant="quiet" onClick={() => skip.mutate()} disabled={skip.isPending || submit.isPending}>
            Saltar esta pregunta
          </Button>
        )}
      </div>
    </div>
  )
}

export default function PracticeQuestion() {
  const { sessionId: raw } = useParams()
  const sessionId = Number(raw)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [outcomes, setOutcomes] = useState<Outcome[]>([])

  const current = useQuery({
    queryKey: ['practice-current', sessionId],
    queryFn: () => api.currentQuestion(sessionId),
    staleTime: Infinity, // refetching would reshuffle answers / pick another question
    gcTime: 0,
    enabled: Number.isFinite(sessionId),
  })

  const finished = current.data && current.data.question === null
  useEffect(() => {
    if (finished) {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate(`/practice/${sessionId}/results`, { replace: true })
    }
  }, [finished, navigate, queryClient, sessionId])

  if (!Number.isFinite(sessionId)) return <Navigate to="/practice" replace />
  if (current.isPending) return <Loading />
  if (current.error) {
    return (
      <div className="stack">
        <ErrorNotice error={current.error} />
        <div className="row">
          <Button variant="quiet" onClick={() => navigate('/practice')}>
            Volver a práctica
          </Button>
        </div>
      </div>
    )
  }

  const { session, question } = current.data
  if (!question) return <Loading />

  return (
    <div>
      <div className="session-bar">
        <span className="muted">{modeLabel(session.mode)}</span>
        <Ticks session={session} outcomes={outcomes} />
        <span className="num muted">
          {session.correct_count} ✓ · {session.incorrect_count} ✗
        </span>
      </div>
      <QuestionCard
        key={question.id}
        sessionId={sessionId}
        question={question}
        onAnswered={(fb) => setOutcomes((o) => [...o, fb.is_correct ? 'right' : 'wrong'])}
        onSkipped={() => {
          setOutcomes((o) => [...o, 'skip'])
          current.refetch()
        }}
        onNext={() => current.refetch()}
      />
    </div>
  )
}

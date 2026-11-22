import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Navigate, useNavigate, useParams } from 'react-router-dom'
import {
  api,
  type AnswerFeedback,
  type ExamPaperResponse,
  type PracticeQuestion as Question,
  type SessionProgress,
} from '../api.ts'
import { Button, ErrorNotice, Loading } from '../components.tsx'
import { modeLabel } from '../format.ts'
import { useTopicLabel } from '../topics.ts'

type Outcome = 'right' | 'wrong' | 'skip' | 'done'

const EXAM_DURATION_SECONDS = 600 // 10 minutos para simulacro de examen
const KEYS = 'ABCDEFGH'

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
        const done = i < session.questions_answered
        const cls = outcomes[i] ? `tick-${outcomes[i]}` : done ? 'tick-skip' : i === outcomes.length ? 'tick-now' : ''
        return <span key={i} className={`tick ${cls}`} />
      })}
    </div>
  )
}

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
  const topicLabel = useTopicLabel()
  const startedAt = useRef(0)
  const [picked, setPicked] = useState<number | null>(null)
  const [feedback, setFeedback] = useState<AnswerFeedback | null>(null)
  useEffect(() => {
    startedAt.current = Date.now()
  }, [])
  const elapsed = () => Math.max(0, Math.round((Date.now() - startedAt.current) / 1000))

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
      <span className="pill">{topicLabel(question.topic)}</span>
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
            {feedback.session.questions_answered >= feedback.session.total_questions
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

function ExamSimulationPaper({
  sessionId,
  paper,
  onComplete,
}: {
  sessionId: number
  paper: ExamPaperResponse
  onComplete: () => void
}) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, number | null>>(() => {
    const init: Record<number, number | null> = {}
    for (const q of paper.questions) {
      init[q.id] = q.selected_answer_id
    }
    return init
  })
  const [showConfirm, setShowConfirm] = useState(false)
  const [timeLeft, setTimeLeft] = useState(EXAM_DURATION_SECONDS)
  const [showWarningModal, setShowWarningModal] = useState(false)
  const topicLabel = useTopicLabel()
  const startedAt = useRef(0)
  const lastViolationAt = useRef(0)
  const isSubmittingRef = useRef(false)

  useEffect(() => {
    startedAt.current = Date.now()
  }, [])

  // Anti-cheat: monitor tab visibility, window focus, and prevent copy/cut
  useEffect(() => {
    const handleViolation = () => {
      if (isSubmittingRef.current) return
      const now = Date.now()
      // 1.5s cooldown to debounce blur and visibilitychange firing together
      if (now - lastViolationAt.current < 1500) return
      lastViolationAt.current = now

      const strikesKey = `exam_sim_strikes_${sessionId}`
      const currentStrikes = Number(sessionStorage.getItem(strikesKey) || '0') + 1
      sessionStorage.setItem(strikesKey, String(currentStrikes))

      if (currentStrikes === 1) {
        // First violation: display warning modal
        setShowWarningModal(true)
      } else if (currentStrikes >= 2) {
        // Second violation: auto-submit and lockout
        isSubmittingRef.current = true
        setShowWarningModal(false)
        sessionStorage.removeItem(`exam_sim_start_${sessionId}`)
        sessionStorage.removeItem(strikesKey)
        api.completeSession(sessionId, { lockout_reason: 'focus_lost' }).finally(() => {
          onComplete()
        })
      }
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        handleViolation()
      }
    }

    const isTouchDevice = window.matchMedia('(pointer: coarse)').matches
    const onBlur = () => {
      // On mobile touch devices, rely on visibilitychange so OS banners don't falsely penalize
      if (!isTouchDevice) {
        handleViolation()
      }
    }

    const onPrevent = (e: Event) => {
      e.preventDefault()
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('blur', onBlur)
    document.addEventListener('copy', onPrevent)
    document.addEventListener('cut', onPrevent)

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('blur', onBlur)
      document.removeEventListener('copy', onPrevent)
      document.removeEventListener('cut', onPrevent)
    }
  }, [sessionId, onComplete])

  // Countdown timer
  useEffect(() => {
    const storageKey = `exam_sim_start_${sessionId}`
    let startTime = Number(sessionStorage.getItem(storageKey))
    if (!startTime || Number.isNaN(startTime)) {
      startTime = Date.now()
      sessionStorage.setItem(storageKey, String(startTime))
    }

    const checkTime = () => {
      const elapsed = Math.floor((Date.now() - startTime) / 1000)
      const remaining = Math.max(0, EXAM_DURATION_SECONDS - elapsed)
      setTimeLeft(remaining)

      if (remaining <= 0) {
        if (isSubmittingRef.current) return
        isSubmittingRef.current = true
        sessionStorage.removeItem(storageKey)
        sessionStorage.removeItem(`exam_sim_strikes_${sessionId}`)
        api.completeSession(sessionId).finally(() => {
          onComplete()
        })
      }
    }

    checkTime()
    const interval = setInterval(checkTime, 1000)
    return () => clearInterval(interval)
  }, [sessionId, onComplete])

  const currentQ = paper.questions[currentIndex]

  const submitAnswerMutation = useMutation({
    mutationFn: ({ qId, aId }: { qId: number; aId: number }) =>
      api.submitAnswer(sessionId, {
        question_id: qId,
        selected_answer_id: aId,
        time_spent_seconds: Math.max(0, Math.round((Date.now() - startedAt.current) / 1000)),
      }),
  })

  const pickAnswer = (answerId: number) => {
    if (!currentQ) return
    setAnswers((prev) => ({ ...prev, [currentQ.id]: answerId }))
    submitAnswerMutation.mutate({ qId: currentQ.id, aId: answerId })
  }

  // Keyboard navigation: A-D picks answer, ArrowLeft/ArrowRight navigates
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if (e.key === 'ArrowLeft' && currentIndex > 0) {
        setCurrentIndex((i) => i - 1)
        return
      }
      if (e.key === 'ArrowRight' && currentIndex < paper.questions.length - 1) {
        setCurrentIndex((i) => i + 1)
        return
      }
      if (!currentQ) return
      const idx = KEYS.indexOf(e.key.toUpperCase())
      if (e.key.length === 1 && idx >= 0 && idx < currentQ.answers.length) {
        pickAnswer(currentQ.answers[idx].id)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const answeredCount = Object.values(answers).filter((a) => a !== null && a !== undefined).length
  const unansweredCount = paper.questions.length - answeredCount

  const handleFinish = () => {
    if (unansweredCount > 0) {
      setShowConfirm(true)
    } else {
      executeFinish()
    }
  }

  const executeFinish = () => {
    if (isSubmittingRef.current) return
    isSubmittingRef.current = true
    sessionStorage.removeItem(`exam_sim_start_${sessionId}`)
    sessionStorage.removeItem(`exam_sim_strikes_${sessionId}`)
    api.completeSession(sessionId).finally(() => {
      onComplete()
    })
  }

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60)
    const secs = seconds % 60
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  if (!currentQ) return <Loading />

  return (
    <div>
      <div className="exam-nav">
        <div className="exam-nav-header">
          <div className="row" style={{ alignItems: 'center', gap: 'var(--s-3)' }}>
            <strong>{modeLabel(paper.session.mode)}</strong>
            <span
              className={`countdown-timer ${timeLeft <= 60 ? 'is-urgent' : ''}`}
              title="Tiempo restante de examen"
            >
              ⏱️ {formatTimer(timeLeft)}
            </span>
          </div>

          <div className="row" style={{ alignItems: 'center', gap: 'var(--s-3)' }}>
            <span className="muted" style={{ fontSize: '0.9rem' }}>
              {answeredCount} de {paper.questions.length} respondidas
            </span>
            <Button onClick={handleFinish}>
              Finalizar examen
            </Button>
          </div>
        </div>

        {/* Navigation Palette */}
        <div className="exam-palette" role="navigation" aria-label="Navegación de preguntas">
          {paper.questions.map((q, idx) => {
            const isAns = answers[q.id] != null
            const isCur = idx === currentIndex
            return (
              <button
                key={q.id}
                type="button"
                className={`palette-btn ${isCur ? 'is-current' : ''} ${isAns ? 'is-answered' : ''}`}
                onClick={() => setCurrentIndex(idx)}
                title={`Pregunta ${idx + 1}: ${isAns ? 'Respondida' : 'Sin responder'}`}
              >
                {idx + 1}
              </button>
            )
          })}
        </div>
      </div>

      {/* Confirmation Dialog */}
      {showConfirm && (
        <div
          style={{
            marginBottom: 'var(--s-5)',
            padding: 'var(--s-4)',
            background: 'var(--surface)',
            border: '2px solid var(--accent)',
            borderRadius: 'var(--radius)',
          }}
        >
          <h4 style={{ margin: '0 0 var(--s-2)' }}>¿Seguro que querés finalizar el examen?</h4>
          <p className="muted" style={{ margin: '0 0 var(--s-4)' }}>
            Tenés <strong>{unansweredCount}</strong> {unansweredCount === 1 ? 'pregunta' : 'preguntas'} sin responder.
          </p>
          <div className="row" style={{ gap: 'var(--s-3)' }}>
            <Button onClick={executeFinish}>
              Sí, entregar examen
            </Button>
            <Button variant="quiet" onClick={() => setShowConfirm(false)}>
              Seguir respondiendo
            </Button>
          </div>
        </div>
      )}

      {/* Anti-cheat Strike 1 Warning Dialog */}
      {showWarningModal && (
        <div className="modal-backdrop">
          <div className="modal-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--s-3)', marginBottom: 'var(--s-3)' }}>
              <span style={{ fontSize: '2rem' }}>⚠️</span>
              <h3 style={{ margin: 0, color: 'var(--wrong)' }}>Advertencia de Seguridad</h3>
            </div>
            <p style={{ margin: '0 0 var(--s-3)', lineHeight: 1.5 }}>
              Detectamos que saliste de la ventana del examen o cambiaste de aplicación.
            </p>
            <p className="muted" style={{ margin: '0 0 var(--s-5)', fontSize: '0.9rem' }}>
              <strong>Esta es tu única advertencia.</strong> Si volvés a perder el foco de pantalla o cambiar de pestaña, el examen se entregará y bloqueará de manera automática y definitiva.
            </p>
            <Button
              onClick={() => {
                setShowWarningModal(false)
                lastViolationAt.current = Date.now()
                window.focus()
              }}
              style={{ width: '100%' }}
            >
              Entendido, continuar examen
            </Button>
          </div>
        </div>
      )}

      {/* Question Card */}
      <div>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--s-2)' }}>
          <span className="pill">{topicLabel(currentQ.topic)}</span>
          <span className="muted" style={{ fontSize: '0.875rem' }}>
            Pregunta {currentIndex + 1} de {paper.questions.length}
          </span>
        </div>

        <p className="question-text">{currentQ.text}</p>

        <ul className="options">
          {currentQ.answers.map((a, i) => {
            const isSelected = answers[currentQ.id] === a.id
            return (
              <li key={a.id}>
                <button
                  type="button"
                  className={`option ${isSelected ? 'option-selected' : ''}`}
                  onClick={() => pickAnswer(a.id)}
                  aria-pressed={isSelected}
                >
                  <span className="option-key">{KEYS[i]}</span>
                  <span className="option-text">{a.text}</span>
                </button>
              </li>
            )
          })}
        </ul>

        {/* Footer Navigation */}
        <div className="exam-footer-nav">
          <Button
            variant="quiet"
            disabled={currentIndex === 0}
            onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
          >
            ← Anterior
          </Button>

          <span className="muted exam-footer-status">
            {answers[currentQ.id] != null ? '✓ Guardada' : 'Sin responder'}
          </span>

          {currentIndex < paper.questions.length - 1 ? (
            <Button onClick={() => setCurrentIndex((i) => Math.min(paper.questions.length - 1, i + 1))}>
              Siguiente →
            </Button>
          ) : (
            <Button onClick={handleFinish}>
              Finalizar examen
            </Button>
          )}
        </div>
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

  // Fetch session metadata first to determine mode safely without mutations or racing
  const sessionQuery = useQuery({
    queryKey: ['practice-session', sessionId],
    queryFn: () => api.session(sessionId),
    staleTime: Infinity,
    gcTime: 0,
    enabled: Number.isFinite(sessionId),
  })

  const mode = sessionQuery.data?.mode
  const isExamSimulation = mode === 'exam_simulation'

  // Query for exam simulation full paper - ONLY enabled if mode is exam_simulation
  const paperQuery = useQuery({
    queryKey: ['practice-paper', sessionId],
    queryFn: () => api.examPaper(sessionId),
    staleTime: Infinity,
    gcTime: 0,
    enabled: Number.isFinite(sessionId) && isExamSimulation,
  })

  // Regular practice query - ONLY enabled if mode is known and NOT exam_simulation
  const current = useQuery({
    queryKey: ['practice-current', sessionId],
    queryFn: () => api.currentQuestion(sessionId),
    staleTime: Infinity,
    gcTime: 0,
    enabled: Number.isFinite(sessionId) && mode !== undefined && !isExamSimulation,
  })

  const onExamComplete = () => {
    queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    navigate(`/practice/${sessionId}/results`, { replace: true })
  }

  const finished = current.data && current.data.question === null
  useEffect(() => {
    if (finished && !isExamSimulation) {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      navigate(`/practice/${sessionId}/results`, { replace: true })
    }
  }, [finished, isExamSimulation, navigate, queryClient, sessionId])

  if (!Number.isFinite(sessionId)) return <Navigate to="/practice" replace />

  if (sessionQuery.isPending) return <Loading />
  if (sessionQuery.error) {
    return (
      <div className="stack">
        <ErrorNotice error={sessionQuery.error} />
        <div className="row">
          <Button variant="quiet" onClick={() => navigate('/practice')}>
            Volver a práctica
          </Button>
        </div>
      </div>
    )
  }

  // If in Exam Simulation mode: render full navigable exam paper!
  if (isExamSimulation) {
    if (paperQuery.isPending) return <Loading />
    if (paperQuery.error) {
      return (
        <div className="stack">
          <ErrorNotice error={paperQuery.error} />
          <div className="row">
            <Button variant="quiet" onClick={() => navigate('/practice')}>
              Volver a práctica
            </Button>
          </div>
        </div>
      )
    }
    if (paperQuery.data) {
      if (paperQuery.data.session.is_completed) {
        return <Navigate to={`/practice/${sessionId}/results`} replace />
      }
      return (
        <ExamSimulationPaper
          sessionId={sessionId}
          paper={paperQuery.data}
          onComplete={onExamComplete}
        />
      )
    }
    return <Loading />
  }

  // Classic Flashcard Practice flow for other modes
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

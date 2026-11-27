/** Typed client for the FastAPI `/api/v1/ui` endpoints. */

export interface OverallStats {
  total_exams: number
  total_questions: number
  questions_ready_for_practice: number
  questions_corrected: number
  practice_readiness_pct: number
  total_practice_sessions: number
  completed_practice_sessions: number
}

export interface ProgressBucket {
  total: number
  ready: number
  readiness_pct: number
}

export interface ExamSummary {
  id: number
  uuid: string
  partial_number: number
  exam_date: string | null
  topic_tags: string | null
}

export interface SessionHistoryItem {
  session_id: number
  mode: string
  is_completed: boolean
  total_questions: number
  questions_answered: number
  correct_count: number
  accuracy_pct: number
  total_time_seconds: number | null
  started_at: string
  completed_at: string | null
}

export interface Dashboard {
  stats: OverallStats
  progress: {
    by_partial: Record<string, ProgressBucket>
    by_topic: Record<string, ProgressBucket>
  }
  exams: ExamSummary[]
  history: SessionHistoryItem[]
}

export interface PracticeOptions {
  modes: string[]
  exams: ExamSummary[]
  topics: { slug: string; name: string }[]
}

export interface SessionProgress {
  session_id: number
  mode: string
  total_questions: number
  questions_answered: number
  correct_count: number
  incorrect_count: number
  skipped_count: number
  is_completed: boolean
}

export interface PracticeQuestion {
  id: number
  text: string
  topic: string
  answers: { id: number; text: string }[]
}

export interface CurrentQuestion {
  session: SessionProgress
  question: PracticeQuestion | null
}

export interface ExamPaperQuestion {
  id: number
  text: string
  topic: string
  answers: { id: number; text: string }[]
  selected_answer_id: number | null
}

export interface ExamPaperResponse {
  session: SessionProgress
  questions: ExamPaperQuestion[]
}

export interface AnswerFeedback {
  is_correct: boolean
  correct_answer_id: number | null
  correct_answer_text: string | null
  explanation: string | null
  session: SessionProgress
}

export interface ResponseRecord {
  question_id: number
  question_text: string | null
  selected_answer_id: number | null
  selected_answer_text: string | null
  is_correct: boolean | null
  correct_answer_text: string | null
  explanation: string | null
  time_spent_seconds: number
  was_flagged: boolean
  skipped: boolean
  is_skipped?: boolean
}

export interface PracticeResults {
  session_id: number
  mode: string
  is_completed: boolean
  total_questions: number
  questions_answered: number
  correct_count: number
  incorrect_count: number
  skipped_count: number
  accuracy: number
  total_time_seconds: number | null
  lockout_reason?: string | null
  responses: ResponseRecord[]
}

export interface StartPracticeInput {
  mode: string
  exam_id: number | null
  topic: string | null
  total_questions: number
  /** error_review only: review exactly these questions. */
  question_ids?: number[]
}

export interface ExamListItem extends ExamSummary {
  question_count: number
}

export interface ExamInput {
  partial_number: number
  exam_date: string | null
  topic_tags: string | null
}

export interface QuestionRow {
  id: number
  exam_id: number
  question_text: string
  topic: string
  order_in_exam: number | null
  confidence_score: number | null
  is_corrected: boolean
  is_ready_for_practice: boolean
}

export interface ExamCoverage {
  exam_id: number
  total_questions: number
  ready_for_practice: number
  corrected: number
  readiness_pct: number
  correction_pct: number
}

export interface ExamDetail {
  exam: ExamListItem
  coverage: ExamCoverage
  questions: QuestionRow[]
}

export interface TopicOption {
  slug: string
  name: string
}

export interface QuestionList {
  questions: QuestionRow[]
  exams: ExamSummary[]
  topics: TopicOption[]
}

export interface QuestionFilters {
  exam_id?: string
  topic?: string
  is_ready?: string
  is_corrected?: string
}

export interface ReviewQueue {
  questions: QuestionRow[]
  exams: ExamSummary[]
}

export interface AnswerRow {
  id: number
  answer_text: string
  answer_type: string
  is_correct: boolean
  is_common_misconception: boolean
  explanation: string | null
}

export interface QuestionDetail {
  question: QuestionRow
  extracted_text: string | null
  correction_notes: string | null
  answers: AnswerRow[]
}

export interface AnswerInput {
  answer_text: string
  answer_type: string
  explanation: string | null
  is_common_misconception: boolean
}

export interface ImportPreview {
  to_create: number
  to_update: number
  to_delete: number
}

export interface ManualQuestionInput {
  question_text: string
  topic: string
  order_in_exam: number | null
  correct_answer_text: string
  explanation: string | null
}

export interface UploadResult {
  created: number
  needing_review: number
  message: string
}

export interface Analytics {
  stats: OverallStats
  progress: Dashboard['progress']
  performance: Record<string, { correct: number; total: number; accuracy_pct: number }>
}

export interface WeakAreas {
  threshold: number
  weak_areas: { topic: string; correct: number; total: number; accuracy_pct: number }[]
  history: SessionHistoryItem[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** FastAPI sends `detail` as a string, or as a list of validation issues. */
function errorMessage(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map((d) => (typeof d?.msg === 'string' ? d.msg : null))
      .filter((m): m is string => m !== null)
    if (msgs.length) return `Datos inválidos: ${msgs.join('; ')}`
  }
  return fallback
}

const CSRF_HEADERS = { 'X-Requested-With': 'XMLHttpRequest' } as const

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isForm = init?.body instanceof FormData
  const headers = new Headers(init?.headers)
  headers.set('X-Requested-With', 'XMLHttpRequest')
  // For multipart bodies the browser must set the boundary itself.
  if (!isForm && init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const res = await fetch(`/api/v1/ui${path}`, {
    credentials: 'same-origin',
    ...init,
    headers,
  })
  if (!res.ok) {
    let message = `La solicitud falló (${res.status})`
    try {
      message = errorMessage(await res.json(), message)
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(res.status, message)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })

const qs = (params: Record<string, string | number | null | undefined>) => {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v !== '' && v != null) q.set(k, String(v))
  const s = q.toString()
  return s ? `?${s}` : ''
}

export const api = {
  dashboard: () => request<Dashboard>('/dashboard'),
  practiceOptions: () => request<PracticeOptions>('/practice/options'),
  startPractice: (input: StartPracticeInput) =>
    post<SessionProgress>('/practice/sessions', input),
  session: (id: number) => request<SessionProgress>(`/practice/sessions/${id}`),
  currentQuestion: (id: number) =>
    request<CurrentQuestion>(`/practice/sessions/${id}/current`),
  submitAnswer: (
    id: number,
    body: { question_id: number; selected_answer_id: number; time_spent_seconds: number },
  ) => post<AnswerFeedback>(`/practice/sessions/${id}/answer`, body),
  skipQuestion: (
    id: number,
    body: { question_id: number; time_spent_seconds: number },
  ) => post<{ session: SessionProgress }>(`/practice/sessions/${id}/skip`, body),
  results: (id: number) => request<PracticeResults>(`/practice/sessions/${id}/results`),
  completeSession: (id: number, payload?: { lockout_reason?: string | null }) =>
    post<SessionProgress>(`/practice/sessions/${id}/complete`, payload ?? {}),
  examPaper: (id: number) => request<ExamPaperResponse>(`/practice/sessions/${id}/paper`),

  topics: () => request<TopicOption[]>('/topics'),

  exams: (partial?: string) => request<ExamListItem[]>(`/exams${qs({ partial_number: partial })}`),
  exam: (id: number) => request<ExamDetail>(`/exams/${id}`),
  createExam: (input: ExamInput) => post<ExamListItem>('/exams', input),
  updateExam: (id: number, input: ExamInput) => put<ExamListItem>(`/exams/${id}`, input),
  deleteExam: (id: number, force: boolean) =>
    request<void>(`/exams/${id}${qs({ force: force ? 'true' : null })}`, { method: 'DELETE' }),
  uploadExamImage: (id: number, file: File, language: string) => {
    const body = new FormData()
    body.append('file', file)
    body.append('language', language)
    return request<UploadResult>(`/exams/${id}/upload`, { method: 'POST', body })
  },
  createManualQuestion: (examId: number, input: ManualQuestionInput) =>
    post<{ id: number }>(`/exams/${examId}/questions`, input),

  questions: (filters: QuestionFilters) => request<QuestionList>(`/questions${qs({ ...filters })}`),
  reviewQueue: (examId?: string) => request<ReviewQueue>(`/questions/review${qs({ exam_id: examId })}`),
  question: (id: number) => request<QuestionDetail>(`/questions/${id}`),
  correctQuestion: (id: number, input: { corrected_text: string; notes: string | null }) =>
    post<QuestionRow>(`/questions/${id}/correct`, input),
  deleteQuestion: (id: number) => request<void>(`/questions/${id}`, { method: 'DELETE' }),

  createAnswer: (questionId: number, input: AnswerInput) =>
    post<AnswerRow>(`/questions/${questionId}/answers`, input),
  updateAnswer: (questionId: number, answerId: number, input: AnswerInput) =>
    put<AnswerRow>(`/questions/${questionId}/answers/${answerId}`, input),
  deleteAnswer: (questionId: number, answerId: number) =>
    request<void>(`/questions/${questionId}/answers/${answerId}`, { method: 'DELETE' }),
  reorderAnswers: (questionId: number, orderedIds: number[]) =>
    put<AnswerRow[]>(`/questions/${questionId}/answers/order`, { ordered_ids: orderedIds }),

  analytics: () => request<Analytics>('/analytics'),
  weakAreas: (threshold?: number) => request<WeakAreas>(`/analytics/weak-areas${qs({ threshold })}`),
}

// ── Backup (core REST endpoints, not under /ui) ───────────

/** Validation problems reported by `/api/v1/import` (HTTP 400). */
export class ImportValidationError extends ApiError {
  details: unknown[]
  constructor(message: string, details: unknown[]) {
    super(400, message)
    this.details = details
  }
}

async function importRequest<T>(file: File, confirm: boolean): Promise<T> {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch(`/api/v1/import${confirm ? '?confirm=true' : ''}`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: CSRF_HEADERS,
    body,
  })
  if (res.status === 413) throw new ApiError(413, 'El archivo es demasiado grande (máx. 10 MB).')
  const data = await res.json().catch(() => ({}))
  if (res.status === 400 && Array.isArray(data.validation_errors)) {
    throw new ImportValidationError(data.detail || 'Errores de validación', data.validation_errors)
  }
  if (!res.ok) throw new ApiError(res.status, errorMessage(data, `Error al importar (HTTP ${res.status}).`))
  return data as T
}

export const backup = {
  /** Downloads the full database as a JSON file. */
  async download(): Promise<void> {
    const res = await fetch('/api/v1/export', {
      method: 'POST',
      credentials: 'same-origin',
      headers: CSRF_HEADERS,
    })
    if (!res.ok) throw new ApiError(res.status, `Error al exportar (HTTP ${res.status}).`)
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url
    a.download =
      /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') ?? '')?.[1] ?? 'exam-backup.json'
    a.click()
    URL.revokeObjectURL(url)
  },
  preview: (file: File) => importRequest<ImportPreview>(file, false),
  apply: (file: File) => importRequest<unknown>(file, true),
}

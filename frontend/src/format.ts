export const MODE_INFO: Record<string, { label: string; hint: string }> = {
  random: { label: 'Aleatorio', hint: 'Preguntas de todos los exámenes al azar' },
  by_partial: { label: 'Por parcial', hint: 'Enfócate en un examen específico' },
  by_topic: { label: 'Por tema', hint: 'Practica un tema en particular' },
  exam_simulation: { label: 'Simulacro de parcial', hint: '10 min cronometrados · Corrección diferida al entregar' },
  error_review: { label: 'Errores', hint: 'Preguntas que alguna vez respondiste mal' },
}

export const modeLabel = (mode: string) => MODE_INFO[mode]?.label ?? mode

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m} min ${s} s` : `${s} s`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('es', { month: 'short', day: 'numeric' })
}

export const pct = (n: number) => `${Math.round(n)}%`

/** `YYYY-MM-DD` → `DD/MM/YYYY` without going through a timezone-shifting Date. */
export function formatExamDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

export const examLabel = (e: { partial_number: number; exam_date: string | null }) =>
  `Parcial ${e.partial_number}${e.exam_date ? ` · ${formatExamDate(e.exam_date)}` : ''}`

export const splitTags = (tags: string | null | undefined) =>
  (tags ?? '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean)

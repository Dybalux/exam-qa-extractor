import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, type ProgressBucket } from '../api.ts'
import { ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import BackupCard from './BackupCard.tsx'
import { formatDate, modeLabel, pct } from '../format.ts'
import { useTopicLabel } from '../topics.ts'

function Meters({
  title,
  data,
  prefix,
  formatKey,
}: {
  title: string
  data: Record<string, ProgressBucket>
  prefix?: string
  formatKey?: (key: string) => string
}) {
  const entries = Object.entries(data)
  return (
    <Card title={title}>
      {entries.length === 0 ? (
        <p className="muted">Aún no hay datos. Agrega preguntas con respuesta correcta para ver el progreso.</p>
      ) : (
        <ul className="meter-list">
          {entries.map(([key, b]) => {
            const label = formatKey ? formatKey(key) : prefix ? `${prefix} ${key}` : key
            return (
              <li key={key}>
                <div className="meter-top">
                  <span>{label}</span>
                  <span className="muted num">
                    {b.ready}/{b.total} listas
                  </span>
                </div>
                <div
                  className="meter"
                  role="progressbar"
                  aria-label={`${label}, preparación`}
                  aria-valuenow={Math.round(b.readiness_pct)}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <span style={{ width: `${b.readiness_pct}%` }} />
                </div>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

export default function Dashboard() {
  const { data, error, isPending } = useQuery({ queryKey: ['dashboard'], queryFn: api.dashboard })
  const topicLabel = useTopicLabel()

  if (isPending) return <Loading />
  if (error) return <ErrorNotice error={error} />

  const { stats, progress, history } = data
  const hasQuestions = stats.questions_ready_for_practice > 0

  return (
    <div className="stack" style={{ gap: 'var(--s-6)' }}>
      <PageHead
        title={hasQuestions ? 'Continúa donde lo dejaste' : 'Agrega preguntas para empezar a estudiar'}
        lead={
          hasQuestions
            ? `${stats.questions_ready_for_practice} de ${stats.total_questions} preguntas están listas para practicar.`
            : 'La práctica necesita preguntas con respuesta correcta. Agrega algunas desde los exámenes.'
        }
      />
      <div className="row">
        {hasQuestions ? (
          <ButtonLink to="/practice" large>
            Comenzar práctica
          </ButtonLink>
        ) : (
          <ButtonLink to="/exams" large>
            Gestionar exámenes
          </ButtonLink>
        )}
      </div>

      <dl className="facts">
        <div>
          <dt>Exámenes</dt>
          <dd>{stats.total_exams}</dd>
        </div>
        <div>
          <dt>Preguntas</dt>
          <dd>{stats.total_questions}</dd>
        </div>
        <div>
          <dt>Listas para practicar</dt>
          <dd>{pct(stats.practice_readiness_pct)}</dd>
        </div>
        <div>
          <dt>Sesiones finalizadas</dt>
          <dd>
            {stats.completed_practice_sessions}/{stats.total_practice_sessions}
          </dd>
        </div>
      </dl>

      <div className="dash-grid">
        <Meters title="Por examen" data={progress.by_partial} prefix="Parcial" />
        <Meters title="Por tema" data={progress.by_topic} formatKey={topicLabel} />
      </div>

      <Card title="Sesiones recientes">
        {history.length === 0 ? (
          <p className="muted">Aún no hay sesiones. Las últimas cinco aparecerán aquí.</p>
        ) : (
          <ul className="history">
            {history.map((h) => (
              <li key={h.session_id}>
                <div>
                  <Link to={h.is_completed ? `/practice/${h.session_id}/results` : `/practice/${h.session_id}`}>
                    {modeLabel(h.mode)}
                  </Link>
                  <div className="muted">{formatDate(h.started_at)}</div>
                </div>
                <div className="row">
                  <span className="muted num">
                    {h.questions_answered}/{h.total_questions} respondidas
                  </span>
                  {h.is_completed ? (
                    <span className={`pill ${h.accuracy_pct >= 60 ? 'pill-right' : 'pill-wrong'}`}>
                      {pct(h.accuracy_pct)}
                    </span>
                  ) : (
                    <span className="pill">En curso</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <BackupCard />
    </div>
  )
}

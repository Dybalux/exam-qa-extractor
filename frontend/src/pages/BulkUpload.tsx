import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api.ts'
import { Button, ButtonLink, Card, ErrorNotice, Loading, PageHead } from '../components.tsx'
import { examLabel } from '../format.ts'

export default function BulkUpload() {
  const examId = Number(useParams().examId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const exam = useQuery({ queryKey: ['exam', examId], queryFn: () => api.exam(examId), enabled: Number.isFinite(examId) })
  const [file, setFile] = useState<File | null>(null)
  const [language, setLanguage] = useState('spa')

  const upload = useMutation({
    mutationFn: () => api.uploadExamImage(examId, file as File, language),
    onSuccess: (result) => {
      queryClient.invalidateQueries()
      navigate(result.needing_review > 0 ? `/questions/review?exam_id=${examId}` : `/exams/${examId}`, {
        state: { flash: result.message },
      })
    },
  })

  if (exam.isPending) return <Loading />
  if (exam.error) return <ErrorNotice error={exam.error} />

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    if (file) upload.mutate()
  }

  return (
    <div className="stack form-card" style={{ gap: 'var(--s-5)' }}>
      <PageHead title="Subir imágenes" lead={examLabel(exam.data.exam)} />
      <Card>
        <form onSubmit={onSubmit} className="stack" style={{ gap: 'var(--s-5)' }}>
          <div className="field">
            <label htmlFor="file">Imagen del examen *</label>
            <label htmlFor="file" className={`dropzone${file ? ' has-file' : ''}`}>
              <strong>{file ? file.name : 'Arrastra una imagen o haz clic para seleccionar'}</strong>
              <span className="hint">JPEG, PNG, PDF — máx. 10 MB</span>
              <input
                id="file"
                type="file"
                accept="image/*,.pdf"
                required
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
          </div>
          <div className="field">
            <label htmlFor="lang">Idioma OCR</label>
            <select id="lang" className="control" value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="spa">Español</option>
              <option value="eng">Inglés</option>
              <option value="spa+eng">Español + Inglés</option>
            </select>
          </div>
          <div className="notice notice-info">
            Después del procesamiento OCR, revisa y corrige las preguntas extraídas desde{' '}
            <Link to={`/questions/review?exam_id=${examId}`}>la cola de revisión</Link>.
          </div>
          {upload.error && <ErrorNotice error={upload.error} />}
          <div className="row">
            <Button type="submit" large disabled={!file || upload.isPending}>
              {upload.isPending ? 'Procesando…' : '↑ Procesar imagen con OCR'}
            </Button>
            <ButtonLink to={`/exams/${examId}`} variant="quiet" large>
              Volver al examen
            </ButtonLink>
          </div>
        </form>
      </Card>
    </div>
  )
}

import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { backup, ImportValidationError, type ImportPreview } from '../api.ts'
import { Button, Card, ErrorNotice } from '../components.tsx'

/** Export / import of the whole database as JSON. */
export default function BackupCard() {
  const queryClient = useQueryClient()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [done, setDone] = useState(false)

  const download = useMutation({ mutationFn: backup.download })
  const check = useMutation({
    mutationFn: (f: File) => backup.preview(f),
    onSuccess: (p) => {
      setPreview(p)
      setDone(false)
    },
  })
  const apply = useMutation({
    mutationFn: (f: File) => backup.apply(f),
    onSuccess: () => {
      setPreview(null)
      setFile(null)
      setDone(true)
      if (input.current) input.current.value = ''
      queryClient.invalidateQueries()
    },
  })

  const error = download.error ?? check.error ?? apply.error
  const validation = error instanceof ImportValidationError ? error : null

  return (
    <Card title="Copia de seguridad">
      <div className="stack">
        <p className="muted" style={{ margin: 0 }}>
          Descarga todos tus exámenes, preguntas y respuestas en un archivo JSON, o restáuralos desde uno. Verás una
          vista previa antes de aplicar los cambios.
        </p>
        <div className="row">
          <Button variant="quiet" disabled={download.isPending} onClick={() => download.mutate()}>
            ⬇ Descargar backup
          </Button>
          <input
            ref={input}
            type="file"
            accept="application/json,.json"
            hidden
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null)
              setPreview(null)
              setDone(false)
              check.reset()
              apply.reset()
            }}
          />
          <Button variant="quiet" onClick={() => input.current?.click()}>
            Elegir archivo…
          </Button>
          <span className="muted file-name">{file ? file.name : 'Ningún archivo seleccionado'}</span>
          <Button disabled={!file || check.isPending} onClick={() => file && check.mutate(file)}>
            {check.isPending ? 'Analizando…' : 'Vista previa'}
          </Button>
        </div>

        {preview && file && (
          <div className="notice notice-info" role="status">
            <p style={{ margin: 0 }}>El archivo importará los siguientes cambios:</p>
            <dl className="facts" style={{ margin: 'var(--s-3) 0' }}>
              <div>
                <dt>Crear</dt>
                <dd>{preview.to_create}</dd>
              </div>
              <div>
                <dt>Actualizar</dt>
                <dd>{preview.to_update}</dd>
              </div>
              <div>
                <dt>Eliminar</dt>
                <dd>{preview.to_delete}</dd>
              </div>
            </dl>
            <div className="row">
              <Button disabled={apply.isPending} onClick={() => apply.mutate(file)}>
                {apply.isPending ? 'Importando…' : 'Confirmar import'}
              </Button>
              <Button variant="quiet" onClick={() => setPreview(null)}>
                Cancelar
              </Button>
            </div>
          </div>
        )}

        {done && (
          <div className="notice notice-info" role="status">
            Import aplicado correctamente.
          </div>
        )}
        {error && <ErrorNotice error={error} />}
        {validation && (
          <ul className="muted">
            {validation.details.slice(0, 20).map((d, i) => (
              <li key={i}>{typeof d === 'string' ? d : JSON.stringify(d)}</li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from './api.ts'

/**
 * Delete flows shared by several screens. Both ask for native confirmation first;
 * deleting an exam that still has questions sends `force`,.
 */
export function useDeleteExam(onDone?: () => void) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: ({ id, force }: { id: number; force: boolean }) => api.deleteExam(id, force),
    onSuccess: () => {
      queryClient.invalidateQueries()
      onDone?.()
    },
  })

  const confirmAndDelete = (exam: { id: number; partial_number: number; question_count: number }) => {
    const warning =
      exam.question_count > 0
        ? ` También se eliminarán sus ${exam.question_count} preguntas y respuestas.`
        : ''
    if (!window.confirm(`¿Eliminar el Parcial ${exam.partial_number}?${warning} Esta acción no se puede deshacer.`))
      return
    mutation.mutate({ id: exam.id, force: exam.question_count > 0 })
  }
  return { confirmAndDelete, error: mutation.error, isPending: mutation.isPending }
}

export function useDeleteQuestion(onDone?: () => void) {
  const queryClient = useQueryClient()
  const mutation = useMutation({
    mutationFn: (id: number) => api.deleteQuestion(id),
    onSuccess: () => {
      queryClient.invalidateQueries()
      onDone?.()
    },
  })

  const confirmAndDelete = (id: number, preview: string) => {
    const short = preview.length > 60 ? `${preview.slice(0, 60)}…` : preview
    if (!window.confirm(`¿Eliminar esta pregunta?\n\n“${short}”\n\nSe eliminarán también sus respuestas. Esta acción no se puede deshacer.`))
      return
    mutation.mutate(id)
  }
  return { confirmAndDelete, error: mutation.error, isPending: mutation.isPending }
}

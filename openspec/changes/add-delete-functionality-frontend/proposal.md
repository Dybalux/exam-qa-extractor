# Proposal: Agregar funcionalidad de eliminación de exámenes y preguntas en el frontend

## Intent

Permitir a los usuarios eliminar exámenes y preguntas directamente desde la interfaz web, utilizando los endpoints DELETE ya implementados en el backend. Esto mejora la UX al evitar que los usuarios deban usar herramientas externas (Postman/curl) o acceder directamente a la base de datos.

## Scope

### In Scope
- Botón "Eliminar" en la lista de exámenes (`/exams`)
- Botón "Eliminar" en la lista de preguntas (`/questions`)
- Modal de confirmación antes de eliminar
- Soporte para `force=true|false` en eliminación de exámenes
- Manejo de errores y feedback visual (flash messages)
- Actualización dinámica de la UI tras eliminar

### Out of Scope
- Soft delete o papelera de reciclaje
- Batch delete (eliminar múltiples items)
- Edición inline de exámenes/preguntas
- Notificaciones por email al eliminar

## Capabilities

### New Capabilities
- `exam-delete`: Eliminar un examen existente con confirmación modal y opción force
- `question-delete`: Eliminar una pregunta existente con confirmación modal

### Modified Capabilities
- None

## Approach

1. **UI**: Agregar botones rojos "Eliminar" en las tablas de exámenes y preguntas
2. **Modal**: Implementar modal de confirmación reutilizable (HTML + CSS) con mensaje descriptivo
3. **JS**: Extender `app.js` con funciones `deleteExam()` y `deleteQuestion()` que:
   - Realicen fetch DELETE al backend
   - Manejen respuestas 200/204 y errores 400/404/409
   - Recarguen la página o actualicen el DOM tras éxito
4. **UX**: Mostrar spinner durante la operación y mensaje de confirmación/éxito

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/templates/exams/list.html` | Modified | Agregar botón "Eliminar" en columna de acciones |
| `app/templates/questions/list.html` | Modified | Agregar botón "Eliminar" en columna de acciones |
| `app/templates/base.html` | Modified | Incluir modal de confirmación reutilizable |
| `app/static/js/app.js` | Modified | Funciones `deleteExam()` y `deleteQuestion()` |
| `app/static/css/app.css` | Modified | Estilos para botones danger y modal |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Borrado accidental de examen con preguntas | Medium | Modal de confirmación explícito; mostrar conteo de preguntas asociadas; opción `force=false` por defecto |
| Race condition: item ya fue eliminado | Low | Manejar 404 con mensaje "El recurso ya no existe" |
| Usuario cierra modal accidentalmente | Low | Botón "Eliminar" requiere click explícito; no cerrar modal al hacer click fuera |
| Error de red durante DELETE | Low | Mostrar mensaje de error y permitir reintentar |

## Rollback Plan

1. Revertir los commits de esta funcionalidad
2. En caso de hotfix urgente: comentar las líneas de los botones "Eliminar" en los templates (no afecta datos)

## Dependencies

- Backend endpoints DELETE ya implementados
- Sin dependencias de librerías externas (usar fetch nativo)

## Success Criteria

- [ ] Usuario puede eliminar un examen desde `/exams` y recibe confirmación visual
- [ ] Usuario puede eliminar una pregunta desde `/questions` y recibe confirmación visual
- [ ] Modal muestra información relevante antes de confirmar (nombre del examen, cantidad de preguntas)
- [ ] Eliminación con `force=true` funciona para exámenes con preguntas
- [ ] Mensajes de error claros si el backend responde 400/404/409
- [ ] La UI se actualiza sin necesidad de recargar la página (o con reload limpio)
- [ ] Tests manuales exitosos en Chrome y Firefox

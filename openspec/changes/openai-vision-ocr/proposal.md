# Proposal: OpenAI Vision API as Alternative OCR Provider

## Intent

El servicio OCR actual (`OCRService`) es monolítico, usa solo Tesseract vía pytesseract, y NO extrae respuestas — solo texto crudo que luego se parsea con regex para preguntas. Integrar OpenAI Vision API (`gpt-4o-mini`) como proveedor alternativo permite extraer preguntas Y respuestas estructuradas en una sola llamada, con salida JSON validada por schema.

## Scope

### In Scope
- Interfaz `BaseOCRProvider` (ABC) con contrato unificado de extracción
- Implementación `TesseractProvider` (refactor del código actual)
- Implementación `OpenAIVisionProvider` con schema JSON para preguntas + respuestas
- Feature flag `OCR_PROVIDER=tesseract|openai` en configuración
- Fallback automático a Tesseract si OpenAI falla (rate limit, timeout, error)
- Validación de tamaño de imagen (<4MB para OpenAI)
- Nuevo endpoint de configuración para verificar proveedor activo

### Out of Scope
- Migración automática de datos existentes
- Soporte para otros proveedores (Google Vision, AWS Textract)
- UI para seleccionar proveedor por imagen
- Caché de respuestas de OpenAI
- Streaming de respuestas

## Capabilities

### New Capabilities
- `ocr-provider-factory`: Patrón factory/ABC para proveedores OCR intercambiables con feature flag
- `openai-vision-extraction`: Extracción estructurada de preguntas Y respuestas vía OpenAI Vision con JSON schema

### Modified Capabilities
- `ocr-text-extraction`: El servicio OCR actual pasa de monolítico a delegar al proveedor seleccionado por factory

## Approach

1. **ABC + Factory**: `BaseOCRProvider` define `async def extract(file_data) -> OCRResult`. Factory resuelve proveedor según `OCR_PROVIDER` env var.
2. **TesseractProvider**: Extraer lógica actual de `OCRService` a este provider. `OCRService` se convierte en fachada que delega al factory.
3. **OpenAIVisionProvider**: Usa `openai` package. Envía imagen como base64 a `gpt-4o-mini` con system prompt + JSON schema. Extrae preguntas Y respuestas en una llamada.
4. **Fallback**: Si OpenAI falla (rate limit, timeout, auth), log warning y fallback a Tesseract automáticamente.
5. **Config**: Agregar `openai_api_key`, `ocr_provider`, `openai_model` a `Settings`. Validar tamaño <4MB antes de enviar.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/services/ocr_service.py` | Modified | Refactor a fachada + factory; extraer providers a módulos separados |
| `app/services/providers/base.py` | New | `BaseOCRProvider` ABC con contrato de extracción |
| `app/services/providers/tesseract.py` | New | `TesseractProvider` con lógica actual de pytesseract |
| `app/services/providers/openai_vision.py` | New | `OpenAIVisionProvider` con llamada a gpt-4o-mini + JSON schema |
| `app/services/providers/factory.py` | New | Factory que resuelve proveedor según config |
| `app/config.py` | Modified | Agregar `openai_api_key`, `ocr_provider`, `openai_model` |
| `app/api/v1/endpoints/exams.py` | Modified | Validar tamaño imagen según proveedor activo |
| `requirements.txt` | Modified | Agregar `openai` package |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Costo API (~$0.003-0.01/imagen) | Medium | Feature flag permite desactivar; monitorear uso; fallback a Tesseract |
| Rate limits (TPM/RPM) de OpenAI | Medium | Fallback automático a Tesseract; retry con backoff exponencial |
| Imagen >4MB rechazada por OpenAI | High | Validar y redimensionar antes de enviar; log warning |
| Latencia adicional por llamada HTTP | Medium | Timeout configurable (30s); fallback rápido si timeout |
| Respuestas no deterministas del modelo | Low | JSON schema estricto; validación de output; `requires_review` en baja confianza |

## Rollback Plan

1. Cambiar `OCR_PROVIDER=tesseract` en `.env` — desactiva OpenAI inmediatamente sin deploy
2. Si hay bugs en el factory: revertir commits de refactor, `OCRService` vuelve a monolítico
3. Si `openai` package causa conflictos: `pip uninstall openai`, el provider no se carga si el package no está disponible

## Dependencies

- `openai` Python package (incluye httpx como HTTP client)
- API key de OpenAI con acceso a `gpt-4o-mini`
- Refactor previo de `OCRService` a provider pattern (parte de este cambio)

## Success Criteria

- [ ] `OCR_PROVIDER=tesseract` funciona idéntico al comportamiento actual (ningún test roto)
- [ ] `OCR_PROVIDER=openai` extrae preguntas Y respuestas en formato JSON válido
- [ ] Fallback a Tesseract funciona cuando OpenAI retorna error 429, 500, o timeout
- [ ] Imágenes >4MB se redimensionan antes de enviar a OpenAI
- [ ] Schema de respuesta de OpenAI se valida antes de retornar `OCRResult`
- [ ] Config `OCR_PROVIDER` invalida retorna error claro al startup
- [ ] Tests unitarios para cada provider + factory + fallback

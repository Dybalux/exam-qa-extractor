// ── Import/Export dashboard controller ───────────────────────
//
// Self-contained module: hooks the export button, the import file
// picker, and the preview/confirm modal that dashboard.html exposes
// (T3.3). Reuses the shared #toast-container that app.js provides
// for success/error feedback — the toast creation code below mirrors
// app.js's showToast() signature but lives in this file so the
// module has no globals pulled from app.js.
//
// Behaviour (T3.4 acceptance contract):
//   1. Export click      → POST /api/v1/export → blob download
//                          with filename exam-backup-${Date.now()}.json.
//   2. File picker change → enable the preview button, show the
//                          filename in the label.
//   3. Preview click     → POST /api/v1/import (no confirm).
//                          • 200 with counts → render modal.
//                          • 400 with validation_errors array → render
//                            errors inside the modal.
//                          • 413 / 5xx → error toast.
//   4. Confirm click     → POST /api/v1/import?confirm=true.
//                          201 → success toast + location.reload().
//                          4xx/5xx → error toast (or modal errors for 400).
//   5. Cancel click      → close the modal without applying.
//
// base.html loads this script after app.js; the order is harmless
// in practice (the toast container lives in the HTML, not in app.js)
// but matches the plan's contract.

(function () {
  'use strict';

  // ── Element references ──────────────────────────────────
  const exportBtn          = document.getElementById('export-btn');
  const importFileInput    = document.getElementById('import-file-input');
  const importPickBtn      = document.getElementById('import-pick-btn');
  const importFilenameLbl  = document.getElementById('import-filename-label');
  const previewBtn         = document.getElementById('preview-btn');
  const importModal        = document.getElementById('import-preview-modal');
  const prevCreate         = document.getElementById('prev-create');
  const prevUpdate         = document.getElementById('prev-update');
  const prevDelete         = document.getElementById('prev-delete');
  const importErrors       = document.getElementById('import-errors');
  const importConfirmBtn   = document.getElementById('import-confirm-btn');
  const importCancelBtn    = document.getElementById('import-cancel-btn');
  const toastContainer     = document.getElementById('toast-container');

  // base.html loads this on every page. If the page has none of our
  // controls, this module is a no-op (other pages don't need it).
  if (!exportBtn && !importFileInput) return;

  // ── Toast helper (mirrors app.js's showToast contract) ──
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text == null ? '' : String(text);
    return div.innerHTML;
  }

  function showToast(type, message) {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    const icon = type === 'success' ? '&#10003;'
               : type === 'error'   ? '&#10007;'
                                    : '&#9888;';
    toast.innerHTML =
      '<span class="toast-icon">' + icon + '</span>' +
      '<span class="toast-message">' + escapeHtml(message) + '</span>' +
      '<button type="button" class="toast-close" aria-label="Cerrar">&times;</button>';

    toastContainer.appendChild(toast);

    let removed = false;
    const close = () => {
      if (removed) return;
      removed = true;
      toast.classList.add('toast-hiding');
      setTimeout(() => toast.remove(), 300);
    };
    toast.addEventListener('click', close);
    toast.querySelector('.toast-close').addEventListener('click', (e) => {
      e.stopPropagation();
      close();
    });
    setTimeout(close, 4000);
  }

  // ── Export ──────────────────────────────────────────────
  if (exportBtn) {
    exportBtn.addEventListener('click', async () => {
      if (exportBtn.disabled) return;
      exportBtn.disabled = true;
      try {
        const res = await fetch('/api/v1/export', { method: 'POST' });
        if (!res.ok) {
          showToast('error', 'Error al exportar (HTTP ' + res.status + ').');
          return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'exam-backup-' + Date.now() + '.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
        showToast('success', 'Backup descargado.');
      } catch (err) {
        showToast('error', 'Error al exportar: ' + (err && err.message || err));
      } finally {
        exportBtn.disabled = false;
      }
    });
  }

  // ── Import: file picker ─────────────────────────────────
  let selectedFile = null;

  if (importPickBtn && importFileInput) {
    importPickBtn.addEventListener('click', () => importFileInput.click());
  }
  if (importFileInput) {
    importFileInput.addEventListener('change', () => {
      const file = importFileInput.files && importFileInput.files[0];
      selectedFile = file || null;
      if (importFilenameLbl) {
        importFilenameLbl.textContent = file
          ? file.name
          : 'Ningún archivo seleccionado';
      }
      if (previewBtn) previewBtn.disabled = !file;
      // Reset any previous preview state when a new file is picked.
      hideModalErrors();
    });
  }

  // ── Modal open / close ──────────────────────────────────
  function openModal() {
    if (!importModal) return;
    importModal.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  function closeModal() {
    if (!importModal) return;
    importModal.hidden = true;
    document.body.style.overflow = '';
  }
  function showModalErrors(detail, errors) {
    if (!importErrors) return;
    importErrors.hidden = false;
    const items = (errors || []).map((e) => {
      const loc = e.loc || e.location || '';
      const msg = e.msg || e.message || JSON.stringify(e);
      return '<li>' + escapeHtml((loc ? loc + ': ' : '') + msg) + '</li>';
    }).join('');
    importErrors.innerHTML =
      '<strong>' + escapeHtml(detail || 'Errores de validación') + '</strong>' +
      (items ? '<ul style="margin:8px 0 0 16px; padding:0">' + items + '</ul>' : '');
  }
  function hideModalErrors() {
    if (!importErrors) return;
    importErrors.hidden = true;
    importErrors.innerHTML = '';
  }

  if (importModal) {
    importModal.querySelectorAll('[data-import-modal-close]').forEach((el) => {
      el.addEventListener('click', closeModal);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !importModal.hidden) closeModal();
    });
  }
  if (importCancelBtn) {
    importCancelBtn.addEventListener('click', closeModal);
  }

  // ── Preview click ───────────────────────────────────────
  if (previewBtn) {
    previewBtn.addEventListener('click', async () => {
      if (!selectedFile || previewBtn.disabled) return;
      previewBtn.disabled = true;
      try {
        const fd = new FormData();
        fd.append('file', selectedFile);
        const res = await fetch('/api/v1/import', { method: 'POST', body: fd });
        const data = await res.json().catch(() => ({}));

        if (res.status === 200) {
          if (prevCreate) prevCreate.textContent = String(data.to_create  ?? 0);
          if (prevUpdate) prevUpdate.textContent = String(data.to_update  ?? 0);
          if (prevDelete) prevDelete.textContent = String(data.to_delete  ?? 0);
          hideModalErrors();
          openModal();
        } else if (res.status === 400 && Array.isArray(data.validation_errors)) {
          if (prevCreate) prevCreate.textContent = '0';
          if (prevUpdate) prevUpdate.textContent = '0';
          if (prevDelete) prevDelete.textContent = '0';
          showModalErrors(data.detail || 'Errores de validación', data.validation_errors);
          openModal();
        } else if (res.status === 413) {
          showToast('error', 'El archivo es demasiado grande (máx. 10 MB).');
        } else {
          showToast('error', 'Error en la vista previa (HTTP ' + res.status + ').');
        }
      } catch (err) {
        showToast('error', 'Error en la vista previa: ' + (err && err.message || err));
      } finally {
        previewBtn.disabled = !selectedFile;
      }
    });
  }

  // ── Confirm click ───────────────────────────────────────
  if (importConfirmBtn) {
    importConfirmBtn.addEventListener('click', async () => {
      if (!selectedFile || importConfirmBtn.disabled) return;
      importConfirmBtn.disabled = true;
      try {
        const fd = new FormData();
        fd.append('file', selectedFile);
        const res = await fetch('/api/v1/import?confirm=true', {
          method: 'POST',
          body: fd,
        });
        if (res.status === 201) {
          showToast('success', 'Import aplicado correctamente.');
          closeModal();
          // Reload after a short delay so the user sees the toast.
          setTimeout(() => window.location.reload(), 250);
          return;
        }
        if (res.status === 400) {
          const data = await res.json().catch(() => ({}));
          if (Array.isArray(data.validation_errors)) {
            showModalErrors(
              data.detail || 'Errores de validación',
              data.validation_errors,
            );
          } else {
            showToast('error', data.detail || ('Error HTTP ' + res.status));
          }
        } else if (res.status === 413) {
          showToast('error', 'El archivo es demasiado grande (máx. 10 MB).');
        } else {
          showToast('error', 'Error al importar (HTTP ' + res.status + ').');
        }
      } catch (err) {
        showToast('error', 'Error al importar: ' + (err && err.message || err));
      } finally {
        importConfirmBtn.disabled = false;
      }
    });
  }
})();

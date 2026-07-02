// ── Mobile Sidebar Toggle ───────────────────────────────────
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');

if (mobileMenuBtn && sidebar && sidebarOverlay) {
  const toggleSidebar = () => {
    sidebar.classList.toggle('open');
    sidebarOverlay.classList.toggle('open');
    document.body.style.overflow = sidebar.classList.contains('open') ? 'hidden' : '';
  };

  mobileMenuBtn.addEventListener('click', toggleSidebar);
  sidebarOverlay.addEventListener('click', toggleSidebar);

  // Close sidebar with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar.classList.contains('open')) {
      toggleSidebar();
    }
  });
}

// ── Flash messages ──────────────────────────────────────────
document.querySelectorAll('.alert[data-autohide]').forEach(el => {
  setTimeout(() => el.remove(), 4000);
});

// ── Active nav link ─────────────────────────────────────────
const path = window.location.pathname;
document.querySelectorAll('.nav-item').forEach(link => {
  const href = link.getAttribute('href') || '';
  if (href && path.startsWith(href) && href !== '/') {
    link.classList.add('active');
  } else if (href === '/' && path === '/') {
    link.classList.add('active');
  }
});

// ── Answer option selection ─────────────────────────────────
document.querySelectorAll('.answer-option').forEach(option => {
  option.addEventListener('click', () => {
    document.querySelectorAll('.answer-option').forEach(o => o.classList.remove('selected'));
    option.classList.add('selected');
    const radio = option.querySelector('input[type="radio"]');
    if (radio) radio.checked = true;
  });
});

// ── Practice timer ──────────────────────────────────────────
const timerEl = document.getElementById('quiz-timer');
const timerInput = document.getElementById('time_spent_seconds');
if (timerEl && timerInput) {
  let seconds = 0;
  const interval = setInterval(() => {
    seconds++;
    const m = String(Math.floor(seconds / 60)).padStart(2, '0');
    const s = String(seconds % 60).padStart(2, '0');
    timerEl.textContent = `${m}:${s}`;
    timerInput.value = seconds;
  }, 1000);
  // Stop timer on form submit
  document.querySelectorAll('form').forEach(f => {
    f.addEventListener('submit', () => clearInterval(interval));
  });
}

// ── Confirm delete ──────────────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', (e) => {
    if (!confirm(el.dataset.confirm || '¿Estás seguro?')) {
      e.preventDefault();
    }
  });
});

// ── Progress bar animation ──────────────────────────────────
document.querySelectorAll('.progress-fill').forEach(bar => {
  const target = bar.dataset.value || '0';
  bar.style.width = '0%';
  setTimeout(() => { bar.style.width = target + '%'; }, 100);
});

// ── Drag-and-drop reorder (answers) ────────────────────────
const reorderList = document.getElementById('answer-reorder-list');
if (reorderList) {
  let dragSrc = null;
  reorderList.querySelectorAll('[draggable]').forEach(item => {
    item.addEventListener('dragstart', () => { dragSrc = item; item.style.opacity = '0.4'; });
    item.addEventListener('dragend',   () => { item.style.opacity = '1'; });
    item.addEventListener('dragover',  (e) => { e.preventDefault(); });
    item.addEventListener('drop', (e) => {
      e.preventDefault();
      if (dragSrc !== item) {
        const allItems = [...reorderList.querySelectorAll('[draggable]')];
        const srcIdx = allItems.indexOf(dragSrc);
        const tgtIdx = allItems.indexOf(item);
        if (srcIdx < tgtIdx) item.after(dragSrc);
        else item.before(dragSrc);
        // Update hidden input with new order
        const orderedIds = [...reorderList.querySelectorAll('[data-id]')].map(el => el.dataset.id);
        const input = document.getElementById('ordered-ids');
        if (input) input.value = JSON.stringify(orderedIds);
      }
    });
  });
}

// ── Shared helpers (global scope — used by multiple IIFEs) ─────
var toastContainer = document.getElementById('toast-container');

function escapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function hideToast(toast) {
  toast.classList.add('toast-hiding');
  setTimeout(function () { toast.remove(); }, 800);
}

function showToast(type, message) {
  var toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  var icon = type === 'success' ? '&#10003;' : type === 'error' ? '&#10007;' : '&#9888;';
  toast.innerHTML =
    '<span class="toast-icon">' + icon + '</span>' +
    '<span class="toast-message">' + escapeHtml(message) + '</span>' +
    '<button type="button" class="toast-close" aria-label="Cerrar">&times;</button>';
  toastContainer.appendChild(toast);
  toast.addEventListener('click', function () { hideToast(toast); });
  toast.querySelector('.toast-close').addEventListener('click', function (e) {
    e.stopPropagation();
    hideToast(toast);
  });
  setTimeout(function () { hideToast(toast); }, 4000);
}

// ═══════════════════════════════════════════════════════════════
// DELETE MODAL FUNCTIONALITY
// ═══════════════════════════════════════════════════════════════

(function() {
  // DOM Elements
  const modal = document.getElementById('delete-modal');
  const modalTitle = document.getElementById('delete-modal-title');
  const modalMessage = document.getElementById('delete-modal-message');
  const modalWarning = document.getElementById('delete-modal-warning');
  const warningMessage = document.getElementById('warning-message');
  const checkboxWrapper = document.getElementById('delete-modal-checkbox-wrapper');
  const checkbox = document.getElementById('delete-modal-checkbox');
  const errorDiv = document.getElementById('delete-modal-error');
  const confirmBtn = document.getElementById('delete-modal-confirm');
  const btnText = confirmBtn.querySelector('.btn-text');
  const btnSpinner = confirmBtn.querySelector('.btn-spinner');

  // State
  let currentDeleteData = null;
  let isDeleting = false;

  // Error messages by HTTP status
  const ERROR_MESSAGES = {
    400: 'Solicitud inválida. Recarga la página e intenta nuevamente.',
    401: 'Tu sesión expiró. Por favor inicia sesión nuevamente.',
    403: 'No tienes permisos para eliminar este recurso.',
    404: 'El recurso ya fue eliminado o no existe.',
    409: 'Conflicto: el examen tiene dependencias que impiden su eliminación.',
    422: 'Datos inválidos. Verifica la información e intenta nuevamente.',
    500: 'Error del servidor. Intenta nuevamente más tarde.',
    503: 'Servicio temporalmente no disponible. Intenta más tarde.',
    network: 'No hay conexión. Verifica tu red e intenta nuevamente.',
    timeout: 'La operación tardó demasiado. Intenta nuevamente.',
    default: 'Ocurrió un error inesperado. Intenta nuevamente.'
  };

  /**
   * Open delete modal with entity data
   * @param {HTMLElement} triggerBtn - Button that triggered the modal
   */
  function openDeleteModal(triggerBtn) {
    const entity = triggerBtn.dataset.entity;
    const id = triggerBtn.dataset.id;
    const name = triggerBtn.dataset.name || '';
    const preview = triggerBtn.dataset.preview || '';
    const questionsCount = parseInt(triggerBtn.dataset.questionsCount || '0', 10);

    // Store data for later use
    currentDeleteData = {
      entity,
      id,
      name,
      preview,
      questionsCount,
      row: triggerBtn.closest('tr'),
      trigger: triggerBtn
    };

    // Configure modal based on entity type
    if (entity === 'exam') {
      modalTitle.textContent = '¿Eliminar examen?';
      modalMessage.textContent = `Estás a punto de eliminar el examen "${name}". Esta acción no se puede deshacer.`;

      if (questionsCount > 0) {
        // Show warning and checkbox for exams with questions
        modalWarning.hidden = false;
        warningMessage.innerHTML = `Este examen contiene <strong>${questionsCount}</strong> pregunta(s) asociada(s). Si eliminas el examen, TODAS las preguntas serán eliminadas permanentemente.`;
        checkboxWrapper.hidden = false;
        checkbox.checked = false;
        confirmBtn.disabled = true;
      } else {
        // No questions - simple modal
        modalWarning.hidden = true;
        checkboxWrapper.hidden = true;
        confirmBtn.disabled = false;
      }
    } else if (entity === 'question') {
      modalTitle.textContent = '¿Eliminar pregunta?';
      const displayText = preview || `Pregunta #${id}`;
      modalMessage.textContent = `Estás a punto de eliminar ${displayText.length > 50 ? displayText.substring(0, 50) + '...' : displayText}. Esta acción no se puede deshacer.`;
      modalWarning.hidden = true;
      checkboxWrapper.hidden = true;
      confirmBtn.disabled = false;
    }

    // Clear any previous errors
    errorDiv.hidden = true;
    errorDiv.textContent = '';

    // Show modal
    modal.hidden = false;
    document.body.style.overflow = 'hidden';

    // Focus management: a disabled button is not focusable, so .focus()
    // would be a no-op and activeElement would stay on the trigger
    // (outside the modal), leaving the focus trap inert. When the
    // confirm button is disabled, focus the close button instead so
    // focus lands inside the modal and the trap engages.
    if (confirmBtn.disabled) {
      var closeBtn = modal.querySelector('button[data-modal-close]');
      if (closeBtn) {
        closeBtn.focus();
      } else {
        // Fallback: focus the modal container itself.
        modal.setAttribute('tabindex', '-1');
        modal.focus();
      }
    } else {
      confirmBtn.focus();
    }
  }

  /**
   * Close modal and reset state
   */
  function closeModal() {
    // Restore focus to the element that triggered the modal.
    var trigger = currentDeleteData && currentDeleteData.trigger;
    if (trigger) {
      trigger.focus();
    }
    modal.hidden = true;
    document.body.style.overflow = '';
    currentDeleteData = null;
    isDeleting = false;

    // Reset UI state
    checkbox.checked = false;
    confirmBtn.disabled = false;
    btnText.hidden = false;
    btnSpinner.hidden = true;
    errorDiv.hidden = true;
    errorDiv.textContent = '';
  }

  /**
   * Execute DELETE request
   */
  async function executeDelete() {
    if (!currentDeleteData || isDeleting) return;

    isDeleting = true;
    const { entity, id, questionsCount } = currentDeleteData;

    // Build URL (API REST endpoints)
    let url;
    if (entity === 'exam') {
      const force = questionsCount > 0 && checkbox.checked;
      url = `/api/v1/exams/${id}?force=${force}`;
    } else {
      url = `/api/v1/questions/${id}`;
    }

    // Show loading state
    confirmBtn.disabled = true;
    btnText.hidden = true;
    btnSpinner.hidden = false;
    errorDiv.hidden = true;

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      const response = await fetch(url, {
        method: 'DELETE',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        handleDeleteSuccess();
      } else {
        handleDeleteError(response.status);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        handleDeleteError('timeout');
      } else if (!navigator.onLine) {
        handleDeleteError('network');
      } else {
        handleDeleteError('default');
      }
    } finally {
      isDeleting = false;
      btnText.hidden = false;
      btnSpinner.hidden = true;
    }
  }

  /**
   * Handle successful deletion
   */
  function handleDeleteSuccess() {
    const { entity, id, name, row } = currentDeleteData;

    // Close modal
    closeModal();

    // Show success toast
    const entityName = entity === 'exam' ? 'Examen' : 'Pregunta';
    const displayName = entity === 'exam' ? name : `#${id}`;
    showToast('success', `${entityName} "${displayName}" eliminado correctamente`);

    // Remove row from table with animation
    if (row) {
      removeTableRow(row);
    } else {
      // Fallback: reload page
      window.location.reload();
    }
  }

  /**
   * Handle deletion error
   * @param {number|string} status - HTTP status code or error type
   */
  function handleDeleteError(status) {
    const message = ERROR_MESSAGES[status] || ERROR_MESSAGES.default;
    errorDiv.textContent = message;
    errorDiv.hidden = false;

    // Re-enable confirm button (user can retry)
    confirmBtn.disabled = entity === 'exam' && currentDeleteData?.questionsCount > 0 ? !checkbox.checked : false;

    // If 404, also refresh the table since the resource is already gone
    if (status === 404) {
      setTimeout(() => {
        if (currentDeleteData?.row) {
          removeTableRow(currentDeleteData.row);
        }
      }, 2000);
    }
  }

  /**
   * Remove table row with fade animation
   * @param {HTMLElement} row - Table row to remove
   */
  function removeTableRow(row) {
    row.classList.add('table-row-deleting');
    setTimeout(() => {
      row.remove();

      // Check if table is now empty - show empty state without reload
      const tbody = row.closest('tbody');
      if (tbody && tbody.querySelectorAll('tr').length === 0) {
        const tableWrap = tbody.closest('.table-wrap');
        if (tableWrap) {
          // Replace table with empty state message
          const emptyState = document.createElement('div');
          emptyState.className = 'empty-state';
          emptyState.innerHTML = '<h3>Sin elementos</h3><p>Todos los elementos han sido eliminados.</p>';
          tableWrap.replaceWith(emptyState);
        }
      }
    }, 300);
  }

  // Event Listeners

  // Checkbox toggle for exams with questions
  if (checkbox) {
    checkbox.addEventListener('change', () => {
      if (currentDeleteData?.entity === 'exam' && currentDeleteData?.questionsCount > 0) {
        confirmBtn.disabled = !checkbox.checked;
      }
    });
  }

  // Confirm delete button
  if (confirmBtn) {
    confirmBtn.addEventListener('click', executeDelete);
  }

  // Close modal buttons
  modal?.querySelectorAll('[data-modal-close]').forEach(btn => {
    btn.addEventListener('click', closeModal);
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal?.hidden) {
      closeModal();
    }
  });

  // Prevent closing when clicking modal content (only backdrop)
  modal?.querySelector('.modal-content')?.addEventListener('click', (e) => {
    e.stopPropagation();
  });

  // Event delegation for delete buttons
  document.addEventListener('click', (e) => {
    const triggerBtn = e.target.closest('[data-delete-modal]');
    if (triggerBtn) {
      e.preventDefault();
      e.stopPropagation();
      openDeleteModal(triggerBtn);
    }
  });
})();

// ═══════════════════════════════════════════════════════════════
// DIRTY TRACKING + CANCEL INTERCEPTION + UNSAVED MODAL + REORDER
// ═══════════════════════════════════════════════════════════════

(function () {
  'use strict';

  // ── 4.1 Dirty Tracking ────────────────────────────────────

  function markDirty(form) {
    if (!form.dataset.dirty) {
      form.dataset.dirty = 'true';
    }
  }

  document.addEventListener('input', function (e) {
    var form = e.target.closest('form[data-track-dirty]');
    if (form) markDirty(form);
  });

  document.addEventListener('change', function (e) {
    var form = e.target.closest('form[data-track-dirty]');
    if (form) markDirty(form);
  });

  // Clear dirty flag on submit (form will POST normally).
  document.addEventListener('submit', function (e) {
    var form = e.target.closest('form[data-track-dirty]');
    if (form) {
      delete form.dataset.dirty;
    }
  });

  // ── 4.2 Cancel-Link Interception (two-tier) ──────────────

  function isCancelClick(link) {
    // Tier 1: header cancel with data-cancel-for attribute.
    if (link.dataset && link.dataset.cancelFor) {
      var form = document.getElementById(link.dataset.cancelFor);
      return form && form.dataset.dirty === 'true';
    }
    // Tier 2: in-form cancel (link is inside a data-track-dirty form).
    var form = link.closest('form[data-track-dirty]');
    if (form && form.dataset.dirty === 'true') {
      var href = link.getAttribute('href');
      // Only intercept real URLs, not javascript: pseudo-links.
      if (href && href.indexOf('javascript:') !== 0) {
        return true;
      }
    }
    return false;
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest('a');
    if (!link) return;

    if (isCancelClick(link)) {
      e.preventDefault();
      e.stopPropagation();

      var form;
      if (link.dataset && link.dataset.cancelFor) {
        form = document.getElementById(link.dataset.cancelFor);
      } else {
        form = link.closest('form[data-track-dirty]');
      }
      openUnsavedModal(link.href, form || null);
    }
  });

  // ── 4.3 Unsaved-Changes Modal ────────────────────────────

  var unsavedModal = document.getElementById('unsaved-modal');
  var unsavedSaveBtn = document.getElementById('unsaved-save');
  var unsavedDiscardBtn = document.getElementById('unsaved-discard');
  var unsavedState = null; // { href: string, form: HTMLElement|null, trigger: Element }

  function openUnsavedModal(href, form) {
    unsavedState = {
      href: href,
      form: form,
      trigger: document.activeElement
    };
    unsavedModal.hidden = false;
    document.body.style.overflow = 'hidden';
    unsavedSaveBtn.focus();
  }

  function closeUnsavedModal() {
    unsavedModal.hidden = true;
    document.body.style.overflow = '';
    if (unsavedState && unsavedState.trigger) {
      unsavedState.trigger.focus();
    }
    unsavedState = null;
  }

  // "Guardar y salir" — submit the form natively. Hide the modal so the
  // form (and any native validation bubble on an invalid field) is visible,
  // but do NOT restore focus to the trigger: on validation failure the
  // browser must keep focus on the invalid field; on success the page
  // navigates away and focus is moot.
  if (unsavedSaveBtn) {
    unsavedSaveBtn.addEventListener('click', function () {
      var form = unsavedState && unsavedState.form;
      unsavedModal.hidden = true;
      document.body.style.overflow = '';
      unsavedState = null;
      if (form) {
        form.requestSubmit();
      }
    });
  }

  // "Descartar" — navigate away without saving.
  if (unsavedDiscardBtn) {
    unsavedDiscardBtn.addEventListener('click', function () {
      if (unsavedState && unsavedState.href) {
        window.location.href = unsavedState.href;
      }
    });
  }

  // Close buttons (×, Cancelar, backdrop).
  unsavedModal && unsavedModal.querySelectorAll('[data-modal-close]').forEach(function (btn) {
    btn.addEventListener('click', closeUnsavedModal);
  });

  // Escape key closes unsaved modal.
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && unsavedModal && !unsavedModal.hidden) {
      closeUnsavedModal();
    }
  });

  // ── 4.4 Reorder Fetch Interceptor ────────────────────────

  var reorderForm = document.getElementById('reorder-form');
  if (reorderForm) {
    // Pre-fill hidden ordered_ids from DOM order on page load.
    var orderedIdsInput = document.getElementById('ordered-ids');
    function refreshOrderedIds() {
      if (orderedIdsInput) {
        var items = document.querySelectorAll('#answer-reorder-list [data-id]');
        orderedIdsInput.value = JSON.stringify(
          Array.prototype.map.call(items, function (el) {
            return parseInt(el.dataset.id, 10);
          })
        );
      }
    }
    refreshOrderedIds();

    reorderForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      refreshOrderedIds();
      var ids = JSON.parse(orderedIdsInput.value || '[]');

      try {
        var response = await fetch(reorderForm.getAttribute('action'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ordered_ids: ids })
        });

        if (response.ok) {
          showToast('success', 'Orden guardado correctamente');
          var qid = reorderForm.dataset.questionId;
          if (qid) {
            setTimeout(function () {
              window.location.href = '/questions/' + qid;
            }, 800);
          } else {
            // Fallback: reload the page.
            setTimeout(function () { window.location.reload(); }, 800);
          }
        } else {
          showToast('error', 'Error al guardar el orden');
        }
      } catch (err) {
        showToast('error', 'Error de red al guardar el orden');
      }
    });
  }

  // ── Focus Trap (applied to BOTH modals) ──────────────────

  function trapFocus(e, modalId) {
    var modal = document.getElementById(modalId);
    if (!modal || modal.hidden) return;
    if (e.key !== 'Tab') return;

    var focusable = modal.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), ' +
      'select:not([disabled]), textarea:not([disabled]), ' +
      '[tabindex]:not([tabindex="-1"])'
    );
    if (focusable.length === 0) return;
    var first = focusable[0];
    var last = focusable[focusable.length - 1];

    // If focus escaped the modal (e.g. the user clicked a non-focusable
    // element like the modal body <p>, moving activeElement to <body>),
    // pull it back inside before applying edge-wrap logic.
    if (!modal.contains(document.activeElement)) {
      e.preventDefault();
      first.focus();
      return;
    }

    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  document.addEventListener('keydown', function (e) {
    trapFocus(e, 'delete-modal');
    trapFocus(e, 'unsaved-modal');
  });

})();

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
  const toastContainer = document.getElementById('toast-container');

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
      row: triggerBtn.closest('tr')
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

    // Focus management
    confirmBtn.focus();
  }

  /**
   * Close modal and reset state
   */
  function closeModal() {
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

      // Check if table is now empty
      const tbody = row.closest('tbody');
      if (tbody && tbody.querySelectorAll('tr').length === 0) {
        // Reload to show empty state
        window.location.reload();
      }
    }, 300);
  }

  /**
   * Show toast notification
   * @param {string} type - 'success', 'error', 'warning'
   * @param {string} message - Message to display
   */
  function showToast(type, message) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icon = type === 'success' ? '&#10003;' : type === 'error' ? '&#10007;' : '&#9888;';

    toast.innerHTML = `
      <span class="toast-icon">${icon}</span>
      <span class="toast-message">${escapeHtml(message)}</span>
      <button type="button" class="toast-close" aria-label="Cerrar">&times;</button>
    `;

    toastContainer.appendChild(toast);

    // Close on click
    toast.addEventListener('click', () => hideToast(toast));
    toast.querySelector('.toast-close').addEventListener('click', (e) => {
      e.stopPropagation();
      hideToast(toast);
    });

    // Auto-hide after 4 seconds
    setTimeout(() => hideToast(toast), 4000);
  }

  /**
   * Hide toast with animation
   * @param {HTMLElement} toast - Toast element
   */
  function hideToast(toast) {
    toast.classList.add('toast-hiding');
    setTimeout(() => toast.remove(), 300);
  }

  /**
   * Escape HTML to prevent XSS
   * @param {string} text - Text to escape
   * @returns {string} Escaped text
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
    console.log('Click detected on:', e.target);
    const triggerBtn = e.target.closest('[data-delete-modal]');
    console.log('Trigger button found:', triggerBtn);
    if (triggerBtn) {
      e.preventDefault();
      e.stopPropagation();
      console.log('Opening modal for:', triggerBtn.dataset);
      openDeleteModal(triggerBtn);
    }
  });
})();

// Fallback: ensure DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, delete modal functionality ready');
  });
} else {
  console.log('DOM already loaded, delete modal functionality ready');
}

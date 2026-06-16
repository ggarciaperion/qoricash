/**
 * QoriCash Trading V2 - Common JavaScript Functions
 * Funciones comunes reutilizables en todo el sistema
 * VERSION: 20260527_v13
 */

console.log('🔔 QoriCash Common.js cargado - Versión: 20251219_v7_simple (Alertas cada 10min)');

// Socket.IO connection
let socket = null;

/**
 * startDashboardPolling(fn)
 *
 * Inicia un polling adaptativo para el dashboard:
 *   - WebSocket conectado  → cada 5 minutos (heartbeat de seguridad)
 *   - WebSocket caído      → cada 60 segundos (modo degradado)
 *
 * Llama a fn() inmediatamente si el socket está desconectado al arrancar.
 * Los eventos del socket (nueva_operacion, operacion_actualizada) ya llaman
 * a loadDashboardData() directamente, por lo que el polling es solo fallback.
 */
function startDashboardPolling(fn) {
    var INTERVAL_WS  = 5 * 60 * 1000;  // 5 minutos cuando WS activo
    var INTERVAL_FB  = 60 * 1000;       // 60 s cuando WS caído
    var _timer = null;

    function _schedule() {
        if (_timer) clearTimeout(_timer);
        var connected = socket && socket.connected;
        _timer = setTimeout(function() {
            fn();
            _schedule();
        }, connected ? INTERVAL_WS : INTERVAL_FB);
    }

    // Rescheduler cuando cambia el estado del socket
    document.addEventListener('socketConnected',    _schedule);
    document.addEventListener('socketDisconnected', _schedule);

    _schedule();
}

/**
 * qoriToast — Motor centralizado de notificaciones en tiempo real.
 * Reutiliza el mismo diseño, animación y timing que #pbToast.
 *
 * @param {object} opts
 *   title   {string}  — Etiqueta superior (uppercase, muted)
 *   message {string}  — Texto principal
 *   type    {string}  — 'success' | 'warning' | 'danger' | 'info'  (default: 'info')
 *   url     {string}  — Si se indica, el toast es clickable y navega a esa URL
 *   sound   {boolean} — Reproducir chime (default: true para success, false para el resto)
 *   duration {number} — ms antes de auto-dismiss (default: 4500)
 */
window.qoriToast = function(opts) {
    const stack = document.getElementById('qoriToastStack');
    if (!stack) return;

    const type     = opts.type     || 'info';
    const duration = opts.duration || 4500;
    const url      = opts.url      || '';

    const icons = {
        success: 'bi bi-check-circle-fill',
        warning: 'bi bi-exclamation-triangle-fill',
        danger:  'bi bi-x-circle-fill',
        info:    'bi bi-bell-fill',
    };

    const el = document.createElement('div');
    el.className = `qori-toast qt-${type}${url ? ' qt-clickable' : ''}`;

    el.innerHTML =
        `<div class="qt-icon"><i class="${icons[type] || icons.info}"></i></div>` +
        `<div class="qt-body">` +
            `<div class="qt-title">${opts.title || 'Notificación'}</div>` +
            `<div class="qt-message">${opts.message || ''}</div>` +
        `</div>` +
        `<button class="qt-close" aria-label="Cerrar"><i class="bi bi-x"></i></button>`;

    if (url) {
        el.addEventListener('click', function(e) {
            if (!e.target.closest('.qt-close')) window.location.href = url;
        });
    }

    const dismiss = function() {
        el.classList.remove('qt-show');
        el.classList.add('qt-hide');
        el.addEventListener('transitionend', function() { el.remove(); }, { once: true });
    };

    el.querySelector('.qt-close').addEventListener('click', function(e) {
        e.stopPropagation();
        dismiss();
    });

    stack.appendChild(el);

    // Trigger enter animation (next frame to allow paint)
    requestAnimationFrame(function() {
        requestAnimationFrame(function() { el.classList.add('qt-show'); });
    });

    var timer = setTimeout(dismiss, duration);

    // Pause on hover
    el.addEventListener('mouseenter', function() { clearTimeout(timer); });
    el.addEventListener('mouseleave', function() { timer = setTimeout(dismiss, 2000); });

    // Sound
    var playSound = (opts.sound !== undefined) ? opts.sound : (type === 'success');
    if (playSound && typeof playCompletedSound === 'function') playCompletedSound();
    else if (typeof playNotificationSound === 'function') {
        if (opts.sound === true) playNotificationSound();
    }
};

/**
 * Conectar a SocketIO para actualizaciones en tiempo real
 */
function connectSocketIO() {
    if (socket) {
        console.log('ℹ️ SocketIO ya está conectado');
        return; // Ya conectado
    }

    console.log('🔌 Intentando conectar a SocketIO...');
    socket = io({
        transports: ['websocket', 'polling'],  // polling como fallback para Safari
        reconnection: true,
        reconnectionDelay: 2000,
        reconnectionAttempts: 10
    });
    window._qoriSocket = socket;

    socket.on('connect', function() {
        console.log('✅ SocketIO conectado exitosamente');
        console.log('🔌 Socket ID:', socket.id);
        console.log('👤 Usuario actual:', window.currentUserRole);
        // No mostrar notificación de conexión
        document.dispatchEvent(new Event('socketConnected'));
    });

    socket.on('disconnect', function() {
        console.log('⚠️  SocketIO desconectado');
        // No mostrar notificación de desconexión
        document.dispatchEvent(new Event('socketDisconnected'));
    });

    socket.on('connection_established', function(data) {
        console.log('✅ Conexión establecida:', data);
    });

    // ============================================
    // EVENTOS DE OPERACIONES
    // ============================================

    socket.on('nueva_operacion', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            qoriToast({
                title:   '📋 Nueva Operación',
                message: `${data.operation_id} · ${data.client_name}${data.amount_usd ? ' · $' + parseFloat(data.amount_usd).toLocaleString('en-US', {minimumFractionDigits:2,maximumFractionDigits:2}) : ''}`,
                type:    'info',
                sound:   true,
            });
            if (window._menuBadgeInc) window._menuBadgeInc('ops');
        }

        // Actualizar dashboard para todos
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }

        // Actualizar tabla de operaciones si existe
        if (typeof refreshOperationsTable === 'function') {
            refreshOperationsTable();
        }
    });

    socket.on('operacion_actualizada', function(data) {
        console.log('📡 [Socket.IO] Evento operacion_actualizada recibido:', data);
        console.log('📡 [Socket.IO] Operador asignado:', data.assigned_operator_name, '(ID:', data.assigned_operator_id, ')');

        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            const msg = data.assigned_operator_name
                ? `${data.operation_id} → ${data.status} · ${data.assigned_operator_name}`
                : `${data.operation_id} → ${data.status}`;
            qoriToast({ title: '🔄 Operación Actualizada', message: msg, type: 'info', sound: !!data.sound });
        }

        // Actualizar dashboard para todos
        if (typeof loadDashboardData === 'function') {
            console.log('📡 [Socket.IO] Llamando loadDashboardData()');
            loadDashboardData();
        }

        // Actualizar tabla de operaciones si existe
        if (typeof refreshOperationsTable === 'function') {
            console.log('📡 [Socket.IO] Llamando refreshOperationsTable()');
            refreshOperationsTable();
        } else {
            console.warn('⚠️ [Socket.IO] refreshOperationsTable() no está definida');
        }
    });

    socket.on('operacion_completada', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            qoriToast({ title: '✅ Operación Completada', message: `${data.operation_id}${data.client_name ? ' · ' + data.client_name : ''}`, type: 'success', sound: true });
        }

        // Actualizar dashboard para todos
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }

        // Actualizar tabla de operaciones si existe
        if (typeof refreshOperationsTable === 'function') {
            refreshOperationsTable();
        }
    });

    socket.on('operacion_cancelada', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            qoriToast({ title: '❌ Operación Cancelada', message: `${data.operation_id}${data.client_name ? ' · ' + data.client_name : ''}`, type: 'warning', sound: true });
        }

        // Actualizar dashboard para todos
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }

        // Actualizar tabla de operaciones si existe
        if (typeof refreshOperationsTable === 'function') {
            refreshOperationsTable();
        }
    });

    socket.on('operacion_en_proceso', function(data) {
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            qoriToast({
                title:   '⏳ Comprobante Subido',
                message: data.message || `${data.operation_id} — pendiente de verificar`,
                type:    'warning',
                sound:   true,
                duration: 6000,
            });
            if (typeof window._menuBadgeInc === 'function') {
                window._menuBadgeInc('ops');
            }
        }
        if (typeof refreshOperationsTable === 'function') refreshOperationsTable();
        if (typeof loadDashboardData     === 'function') loadDashboardData();
    });

    socket.on('comprobante_deposito', function(data) {
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            qoriToast({
                title:   '📎 Comprobante de Abono',
                message: data.message || data.operation_id,
                type:    'info',
                duration: 5000,
            });
        }
        if (typeof refreshOperationsTable === 'function') refreshOperationsTable();
    });

    socket.on('comprobante_pago', function(data) {
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Trader' || window.currentUserRole === 'Operador') {
            qoriToast({
                title:   '💳 Comprobante de Pago',
                message: data.message || data.operation_id,
                type:    'info',
                duration: 5000,
            });
        }
        if (typeof refreshOperationsTable === 'function') refreshOperationsTable();
    });

    socket.on('cliente_activado', function(data) {
        qoriToast({
            title:   '✅ Cliente Activado',
            message: data.message || data.client_name,
            type:    'success',
            sound:   true,
            duration: 7000,
        });
        if (window._menuBadgeInc) window._menuBadgeInc('clients');
        if (typeof refreshClientsTable === 'function') refreshClientsTable();
    });

    // ============================================
    // EVENTOS DE CLIENTES
    // ============================================

    // Escuchar ambos nombres de evento (nuevo_cliente y client_created) para compatibilidad
    function onNewClient(data) {
        const name  = data.client_name || (data.client && (data.client.full_name || data.client.razon_social)) || 'Nuevo cliente';
        const dni   = data.client_dni  || (data.client && data.client.dni) || '';
        const canal = data.created_by  || '';

        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador' || window.currentUserRole === 'Middle Office') {
            const canalLabel = canal === 'App Móvil' ? '📱 App' : (canal === 'Web' || canal === 'web' ? '🌐 Web' : (canal || ''));
            qoriToast({
                title:   '👤 Nuevo Cliente' + (canalLabel ? ' · ' + canalLabel : ''),
                message: `${name}${dni ? ' · ' + dni : ''}`,
                type:    'info',
                sound:   true,
            });
            if (window._menuBadgeInc) window._menuBadgeInc('clients');
        }
        if (typeof refreshClientsTable === 'function') {
            refreshClientsTable();
        }
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }
    }

    socket.on('nuevo_cliente',  onNewClient);
    socket.on('client_created', onNewClient);

    socket.on('client_updated', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            qoriToast({ title: '✏️ Cliente Actualizado', message: data.client_name || '', type: 'info' });
        }

        // Actualizar tabla de clientes si existe
        if (typeof refreshClientsTable === 'function') {
            refreshClientsTable();
        }
    });

    socket.on('client_deleted', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            qoriToast({ title: '🗑️ Cliente Eliminado', message: data.client_name || '', type: 'warning' });
        }

        // Actualizar tabla de clientes si existe
        if (typeof refreshClientsTable === 'function') {
            refreshClientsTable();
        }

        // Actualizar dashboard para todos
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }
    });

    // ============================================
    // EVENTOS DE USUARIOS
    // ============================================

    socket.on('nuevo_usuario', function(data) {
        qoriToast({ title: '🧑‍💼 Nuevo Usuario', message: `${data.username} · ${data.role}`, type: 'info' });

        // Actualizar tabla de usuarios si existe
        if (typeof refreshUsersTable === 'function') {
            refreshUsersTable();
        }

        // Actualizar dashboard
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }
    });

    socket.on('user_updated', function(data) {
        qoriToast({ title: '✏️ Usuario Actualizado', message: data.username || '', type: 'info' });

        // Actualizar tabla de usuarios si existe
        if (typeof refreshUsersTable === 'function') {
            refreshUsersTable();
        }
    });

    socket.on('user_deleted', function(data) {
        qoriToast({ title: '🗑️ Usuario Eliminado', message: data.username || '', type: 'warning' });

        // Actualizar tabla de usuarios si existe
        if (typeof refreshUsersTable === 'function') {
            refreshUsersTable();
        }

        // Actualizar dashboard
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }
    });

    // ============================================
    // EVENTOS DEL DASHBOARD
    // ============================================

    socket.on('dashboard_update', function() {
        // Actualizar dashboard si estamos en esa página
        if (typeof loadDashboardData === 'function') {
            loadDashboardData();
        }
    });

    // ============================================
    // EVENTOS GENERALES
    // ============================================

    socket.on('notification', function(data) {
        qoriToast({ title: data.title || 'Notificación', message: data.message || '', type: data.type || 'info' });
    });

    // ============================================
    // EVENTOS DE ASIGNACIÓN DE OPERACIONES
    // ============================================

    socket.on('operacion_asignada', function(data) {
        console.log('Operación asignada recibida:', data);

        // Mostrar notificación al operador
        qoriToast({ title: '📌 Operación Asignada', message: data.message || '', type: 'info', sound: true, duration: 8000 });
        if (window._menuBadgeInc) window._menuBadgeInc('ops');

        // Si estamos en la página de operaciones, refrescar la tabla
        if (typeof refreshOperationsTable === 'function') {
            refreshOperationsTable();
        }

        // Si el modal de edición está abierto con esta operación, recargarlo
        if (typeof currentOperation !== 'undefined' && currentOperation &&
            currentOperation.id === data.operation_db_id) {
            if (typeof loadEditModal === 'function') {
                loadEditModal();
            }
        }
    });

    socket.on('operacion_reasignada_removida', function(data) {
        console.log('Operación reasignada removida:', data);

        // Mostrar notificación al operador anterior
        qoriToast({ title: '↩️ Operación Reasignada', message: data.message || '', type: 'warning', duration: 8000 });

        // Si estamos en la página de operaciones, refrescar la tabla
        if (typeof refreshOperationsTable === 'function') {
            refreshOperationsTable();
        }

        // Si el modal de edición está abierto con esta operación, cerrarlo
        if (typeof currentOperation !== 'undefined' && currentOperation &&
            currentOperation.id === data.operation_db_id) {
            // Cerrar el modal ya que ya no está asignada a este operador
            const editModal = bootstrap.Modal.getInstance(document.getElementById('editOperationModal'));
            if (editModal) {
                editModal.hide();
            }
        }
    });

    // ============================================
    // EVENTOS DE REASIGNACIÓN DE CLIENTES
    // ============================================

    socket.on('cliente_asignado', function(data) {
        console.log('📋 Cliente asignado recibido:', data);

        const clientName = data.client_name || 'Cliente';
        const clientDni  = data.client_dni  || '';

        // Popup modal prominente para el Trader que recibe el cliente
        if (typeof Swal !== 'undefined') {
            Swal.fire({
                icon: 'info',
                title: '¡Cliente Asignado!',
                html: `<p>Se te ha asignado el siguiente cliente:</p>
                       <p style="font-size:1.1em;font-weight:700;color:#0D1B2A;">${clientName}</p>
                       <p style="color:#64748b;font-size:0.9em;">${clientDni}</p>`,
                confirmButtonText: 'Ver cliente',
                showCancelButton: true,
                cancelButtonText: 'Cerrar',
                confirmButtonColor: '#5CB85C',
                allowOutsideClick: false,
            }).then(function(result) {
                if (result.isConfirmed && data.client_id) {
                    window.location.href = '/clients/' + data.client_id;
                }
            });
        } else {
            qoriToast({ title: '📋 Cliente Asignado', message: `${clientName}${clientDni ? ' · ' + clientDni : ''}`, type: 'info', duration: 10000 });
        }

        playNotificationSound();
        if (window._menuBadgeInc) window._menuBadgeInc('clients');

        if (typeof refreshClientsTable === 'function') {
            refreshClientsTable();
        }
    });

    socket.on('cliente_reasignado_removido', function(data) {
        console.log('📋 Cliente reasignado removido:', data);

        const clientName = data.client_name || 'Cliente';

        // Notificación de aviso para el Trader que pierde el cliente
        qoriToast({ title: '↩️ Cliente Reasignado', message: `${clientName} fue asignado a otro ejecutivo`, type: 'warning', duration: 8000 });

        if (typeof refreshClientsTable === 'function') {
            refreshClientsTable();
        }
    });
}

/**
 * Mostrar notificación toast moderna — delega a qoriToast (motor centralizado)
 */
function showNotification(message, type = 'info', duration = 5000) {
    if (typeof window.qoriToast === 'function') {
        window.qoriToast({ title: 'Notificación', message: message, type: type === 'danger' ? 'danger' : type, duration: duration });
    } else if (typeof Swal !== 'undefined') {
        Swal.mixin({ toast: true, position: 'top-end', showConfirmButton: false, timer: duration, timerProgressBar: true })
            .fire({ icon: type === 'danger' ? 'error' : type, title: message });
    } else {
        showAlert(message, type);
    }
}

/**
 * Mostrar alerta (toast notification) - Fallback
 */
function showAlert(message, type = 'info') {
    const alertTypes = {
        'success': 'alert-success',
        'danger': 'alert-danger',
        'warning': 'alert-warning',
        'info': 'alert-info'
    };

    const alertClass = alertTypes[type] || 'alert-info';
    const icons = {
        'success': 'bi-check-circle-fill',
        'danger': 'bi-exclamation-circle-fill',
        'warning': 'bi-exclamation-triangle-fill',
        'info': 'bi-info-circle-fill'
    };
    const icon = icons[type] || 'bi-info-circle-fill';

    const alertHtml = `
        <div class="alert ${alertClass} alert-dismissible fade show position-fixed" role="alert" style="top: 20px; right: 20px; z-index: 9999; min-width: 300px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
            <i class="bi ${icon} me-2"></i> ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    // Agregar al body
    $('body').append(alertHtml);

    // Auto-remover después de 5 segundos
    setTimeout(function() {
        $('body').find('.alert').last().fadeOut(function() {
            $(this).remove();
        });
    }, 5000);
}

/**
 * Hacer petición AJAX
 */
function ajaxRequest(url, method, data, successCallback, errorCallback) {
    // PROTECCIÓN ADICIONAL: Prevenir múltiples peticiones POST simultáneas al mismo endpoint
    if (method === 'POST') {
        const requestKey = `${method}:${url}`;
        window.activeAjaxRequests = window.activeAjaxRequests || new Set();

        if (window.activeAjaxRequests.has(requestKey)) {
            console.warn('🚫 BLOQUEADO: Ya hay una petición en proceso a', url);
            return;
        }

        window.activeAjaxRequests.add(requestKey);
    }

    const csrfToken = $('meta[name="csrf-token"]').attr('content');

    $.ajax({
        url: url,
        type: method,
        contentType: 'application/json',
        data: data ? JSON.stringify(data) : null,
        headers: {
            'X-CSRFToken': csrfToken
        },
        success: function(response) {
            // Remover del set de peticiones activas
            if (method === 'POST' && window.activeAjaxRequests) {
                window.activeAjaxRequests.delete(`${method}:${url}`);
            }

            // Interceptar respuestas de modo demo
            if (response && response.demo_mode) {
                if (typeof Swal !== 'undefined') {
                    Swal.fire({
                        title: 'Modo Demo',
                        html: '<p>Esta acción está <strong>bloqueada</strong> en el entorno de demostración.</p><p class="text-muted small mt-2">Los datos que ves son de muestra y no se modifican.</p>',
                        icon: 'info',
                        confirmButtonText: 'Entendido',
                        confirmButtonColor: '#0d6efd'
                    });
                }
                return; // No ejecutar successCallback
            }

            if (successCallback) {
                successCallback(response);
            }
        },
        error: function(xhr, status, error) {
            // Remover del set de peticiones activas
            if (method === 'POST' && window.activeAjaxRequests) {
                window.activeAjaxRequests.delete(`${method}:${url}`);
            }

            // Solo mostrar error si es relevante (no errores de recursos estáticos)
            if (xhr.status !== 0 && xhr.status !== 404) {
                const errorMsg = xhr.responseJSON?.message || error || 'Error en la petición';
                showNotification(errorMsg, 'danger');
            } else if (xhr.status === 404) {
                console.error('Recurso no encontrado:', url, xhr);
            }

            if (errorCallback) {
                errorCallback(xhr, status, error);
            }
        }
    });
}

/**
 * Formatear número como moneda
 */
function formatCurrency(amount, currency = 'USD') {
    const num = parseFloat(amount);
    if (isNaN(num)) return '0.00';
    
    const formatted = num.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    
    return currency === 'USD' ? `$ ${formatted}` : `S/ ${formatted}`;
}

/**
 * Parsear fecha de forma segura — compatible con Safari/iOS.
 * Safari no acepta "2024-01-01 12:00:00" (espacio en lugar de T).
 * Normaliza a ISO 8601 con Z antes de crear el objeto Date.
 */
function parseSafeDate(str) {
    if (!str) return null;
    // "2024-01-01 12:00:00" → "2024-01-01T12:00:00Z"
    // "2024-01-01T12:00:00" → "2024-01-01T12:00:00Z"
    const normalized = String(str).replace(' ', 'T').replace(/(\d{2}:\d{2}:\d{2})$/, '$1Z');
    const d = new Date(normalized);
    return isNaN(d.getTime()) ? null : d;
}

/**
 * Formatear fecha
 */
function formatDate(dateString) {
    if (!dateString) return '-';

    const date = parseSafeDate(dateString) || new Date(dateString);
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    
    return `${day}/${month}/${year} ${hours}:${minutes}`;
}

/**
 * Validar DNI peruano (8 dígitos)
 */
function validateDNI(dni) {
    return /^[0-9]{8}$/.test(dni);
}

/**
 * Validar email
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Validar teléfono peruano
 */
function validatePhone(phone) {
    return /^[0-9]{9}$/.test(phone) || /^[0-9]{7}$/.test(phone);
}

/**
 * Sistema de audio con fallback progresivo:
 * 1. AudioContext desbloqueado (no bloqueado por política de autoplay del navegador)
 * 2. HTMLAudio como fallback (puede ser bloqueado si no hubo gesto)
 * El AudioContext se desbloquea en base.html en el primer click/keydown del usuario.
 */
function _playSound(file, volume) {
    const url = '/static/sounds/' + file + '.mp3';
    // Crear AudioContext si no existe aún
    if (!window._audioCtx) {
        try { window._audioCtx = new (window.AudioContext || window.webkitAudioContext)(); }
        catch(e) { _playAudioTag(url, volume); return; }
    }
    const ctx = window._audioCtx;
    const _doPlay = function() {
        fetch(url)
            .then(function(r) { return r.arrayBuffer(); })
            .then(function(buf) { return ctx.decodeAudioData(buf); })
            .then(function(decoded) {
                const src  = ctx.createBufferSource();
                const gain = ctx.createGain();
                gain.gain.value = volume;
                src.buffer = decoded;
                src.connect(gain);
                gain.connect(ctx.destination);
                src.start(0);
            })
            .catch(function() { _playAudioTag(url, volume); });
    };
    if (ctx.state === 'running') {
        _doPlay();
    } else if (ctx.state === 'suspended') {
        ctx.resume().then(_doPlay).catch(function() { _playAudioTag(url, volume); });
    } else {
        _playAudioTag(url, volume);
    }
}

function _playAudioTag(url, volume) {
    try {
        const a = new Audio(url);
        a.volume = volume;
        const p = a.play();
        if (p) p.catch(() => {});
    } catch(e) {}
}

function playNotificationSound() {
    if (window.QoriPlaySound) { window.QoriPlaySound('notification', 0.6); }
    else { _playSound('allnotificaciones', 0.6); }
}
function playCompletedSound() {
    if (window.QoriPlaySound) { window.QoriPlaySound('completada', 0.7); }
    else { _playSound('completada', 0.7); }
}

/**
 * Confirmar acción
 */
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

/**
 * Copiar al portapapeles
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showNotification('Copiado al portapapeles', 'success');
    }).catch(function() {
        showNotification('Error al copiar', 'danger');
    });
}

/**
 * Exportar tabla a Excel
 */
function exportToExcel() {
    // Esta función requiere una librería adicional o backend
    showNotification('Función de exportación en desarrollo', 'info');
}

/**
 * NOTA: El manejo de cambio de contraseña se ha movido a base.html como script inline
 * para evitar problemas de timing con la carga de scripts y event listeners.
 * Ver app/templates/base.html líneas ~181-312
 */

/**
 * Cargar datos del dashboard
 */
function loadDashboardData(month = null, year = null) {
    let url = '/dashboard/api/dashboard_data';
    if (month && year) {
        url += `?month=${month}&year=${year}`;
    }
    
    ajaxRequest(url, 'GET', null, function(data) {
        // Actualizar estadísticas del día
        $('#clientsToday').text(data.clients_today || 0);
        $('#operationsToday').text(data.operations_today || 0);
        $('#usdToday').text(formatCurrency(data.usd_today || 0, 'USD'));
        $('#penToday').text(formatCurrency(data.pen_today || 0, 'PEN'));
        
        // Actualizar estadísticas del mes
        $('#clientsMonth').text(data.clients_month || 0);
        $('#activeClientsMonth').text(data.active_clients_month || 0);
        $('#operationsMonth').text(data.operations_month || 0);
        $('#usdMonth').text(formatCurrency(data.usd_month || 0, 'USD'));
        $('#penMonth').text(formatCurrency(data.pen_month || 0, 'PEN'));
        $('#completedMonth').text(data.completed_count || 0);
        
        // Actualizar estado de operaciones
        $('#pendingCount').text(data.pending_count || 0);
        $('#inProcessCount').text(data.in_process_count || 0);
        $('#completedCount').text(data.completed_count || 0);
        $('#canceledCount').text(data.canceled_count || 0);
        
        // Actualizar sistema (solo para Master)
        if (data.total_users !== undefined) {
            $('#totalUsers').text(data.total_users || 0);
            $('#activeUsers').text(data.active_users || 0);
            $('#totalClients').text(data.total_clients || 0);
        }
    });
}

// ============================================
// SISTEMA DE SEGURIDAD: INACTIVIDAD Y CIERRE DE PESTAÑA
// ============================================

let inactivityTimeout     = null;
let scheduleCheckInterval = null;
const INACTIVITY_TIME  = 20 * 60 * 1000; // 20 minutos
const SESSION_CHECK_KEY = 'qoricash_session_active';

// Horario laboral: Lunes–Sábado 09:00–13:30 (Perú, UTC-5)
const BUSINESS_START_MIN = 9 * 60;       // 540 min
const BUSINESS_END_MIN   = 13 * 60 + 30; // 810 min

/**
 * Devuelve true si ahora mismo es horario laboral en Perú (UTC-5).
 * Durante ese horario NO se aplica el cierre por inactividad.
 */
function isBusinessHours() {
    // Convertir a hora Perú (UTC-5) de forma explícita
    const now     = new Date();
    const utcMs   = now.getTime() + now.getTimezoneOffset() * 60000;
    const peruDate = new Date(utcMs - 5 * 3600000); // UTC-5

    const day      = peruDate.getDay();                           // 0=Dom … 6=Sáb
    const totalMin = peruDate.getHours() * 60 + peruDate.getMinutes();

    const isWeekday = day >= 1 && day <= 6;
    const inWindow  = totalMin >= BUSINESS_START_MIN && totalMin < BUSINESS_END_MIN;

    return isWeekday && inWindow;
}

/**
 * Resetear el temporizador de inactividad.
 * Si estamos en horario laboral, cancela cualquier timer pendiente y no hace nada más.
 */
function resetInactivityTimer() {
    if (inactivityTimeout) {
        clearTimeout(inactivityTimeout);
        inactivityTimeout = null;
    }
    if (isBusinessHours()) return; // horario laboral → sin restricción

    inactivityTimeout = setTimeout(function() {
        handleInactivityLogout();
    }, INACTIVITY_TIME);
}

/**
 * Manejar cierre de sesión por inactividad
 */
function handleInactivityLogout() {
    console.log('⏰ Sesión cerrada por inactividad (20 minutos sin actividad)');

    if (typeof Swal !== 'undefined') {
        Swal.fire({
            icon: 'warning',
            title: 'Sesión Cerrada',
            text: 'Su sesión expiró por inactividad',
            allowOutsideClick: false,
            allowEscapeKey: false,
            confirmButtonText: 'Entendido'
        }).then(function() {
            window.location.href = '/logout';
        });
    } else {
        alert('Su sesión expiró por inactividad');
        window.location.href = '/logout';
    }
}

/**
 * Inicializar sistema de detección de inactividad.
 * Registra los eventos de actividad y evalúa cada minuto si
 * el horario laboral cambió para activar / desactivar el timer.
 */
function initInactivityDetection() {
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
    events.forEach(function(event) {
        document.addEventListener(event, resetInactivityTimer, true);
    });

    // Evaluación inicial
    if (isBusinessHours()) {
        console.log('✅ Sistema de inactividad: SUSPENDIDO (horario laboral 09:00–13:30)');
    } else {
        resetInactivityTimer();
        console.log('✅ Sistema de detección de inactividad iniciado (20 minutos)');
    }

    // Revisar cada minuto si el horario cambia (activa/desactiva sin recargar)
    if (scheduleCheckInterval) clearInterval(scheduleCheckInterval);
    scheduleCheckInterval = setInterval(function() {
        if (isBusinessHours()) {
            // Si había un timer corriendo, cancelarlo
            if (inactivityTimeout) {
                clearTimeout(inactivityTimeout);
                inactivityTimeout = null;
                console.log('🟢 Horario laboral iniciado — inactividad suspendida');
            }
        } else {
            // Fuera de horario laboral: asegurar que el timer esté activo
            if (!inactivityTimeout) {
                resetInactivityTimer();
                console.log('🔴 Horario laboral terminado — inactividad activada (20 min)');
            }
        }
    }, 60000); // cada 60 segundos
}

/**
 * Verificar si la sesión es válida (detectar apertura de nueva pestaña)
 */
function checkSessionValidity() {
    // Generar ID único para esta pestaña
    const tabId = 'tab_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

    // Verificar si hay una sesión activa en sessionStorage
    const sessionActive = sessionStorage.getItem(SESSION_CHECK_KEY);

    if (!sessionActive) {
        // No hay sesión en sessionStorage para esta pestaña
        // Verificar si hay pestañas cerradas marcadas en localStorage
        const tabClosed = localStorage.getItem('qoricash_tab_closed');

        // Verificar si el navegador tiene cookies de sesión de Flask
        const hasFlaskSession = document.cookie.includes('session=');

        if (hasFlaskSession && tabClosed === 'true') {
            // Hay una cookie de sesión Flask pero la última pestaña se cerró
            console.log('🔒 Sesión inválida: todas las pestañas fueron cerradas. Cerrando sesión...');

            // Limpiar marca de cierre
            localStorage.removeItem('qoricash_tab_closed');

            // Cerrar sesión inmediatamente
            window.location.href = '/logout';
            return false;
        }
    }

    // Marcar sesión como activa en sessionStorage de esta pestaña
    sessionStorage.setItem(SESSION_CHECK_KEY, tabId);

    // Registrar esta pestaña como activa en localStorage
    registerActiveTab(tabId);

    // Remover marca de cierre si existe (porque ahora hay una pestaña activa)
    localStorage.removeItem('qoricash_tab_closed');

    return true;
}

/**
 * Registrar pestaña activa
 */
function registerActiveTab(tabId) {
    // Obtener lista de pestañas activas
    let activeTabs = JSON.parse(localStorage.getItem('qoricash_active_tabs') || '[]');

    // Agregar esta pestaña si no está
    if (!activeTabs.includes(tabId)) {
        activeTabs.push(tabId);
        localStorage.setItem('qoricash_active_tabs', JSON.stringify(activeTabs));
    }

    // Limpiar pestañas inactivas periódicamente
    cleanupInactiveTabs(tabId);
}

/**
 * Limpiar pestañas que ya no existen
 */
function cleanupInactiveTabs(currentTabId) {
    let activeTabs = JSON.parse(localStorage.getItem('qoricash_active_tabs') || '[]');

    // Filtrar solo la pestaña actual (esto se ejecuta en cada pestaña)
    // El truco es que cada pestaña solo se conoce a sí misma
    const updatedTabs = activeTabs.filter(id => id === currentTabId);

    localStorage.setItem('qoricash_active_tabs', JSON.stringify(updatedTabs));
}

/**
 * Marcar que se cerró una pestaña
 */
function markTabClosed() {
    const tabId = sessionStorage.getItem(SESSION_CHECK_KEY);

    if (tabId) {
        // Obtener pestañas activas
        let activeTabs = JSON.parse(localStorage.getItem('qoricash_active_tabs') || '[]');

        // Remover esta pestaña
        activeTabs = activeTabs.filter(id => id !== tabId);

        // Si no quedan pestañas activas, marcar que se cerró la última
        if (activeTabs.length === 0) {
            console.log('🔒 Última pestaña cerrada, marcando para cerrar sesión');
            localStorage.setItem('qoricash_tab_closed', 'true');
        }

        localStorage.setItem('qoricash_active_tabs', JSON.stringify(activeTabs));
    }
}

/**
 * Limpiar sessionStorage y marcar pestaña como cerrada
 */
function cleanupSessionStorage() {
    markTabClosed();
    sessionStorage.removeItem(SESSION_CHECK_KEY);
}

// Auto-iniciar al cargar la página
$(document).ready(function() {
    if (window.currentUserId) {
        // Verificar validez de la sesión
        checkSessionValidity();

        // Iniciar sistema de detección de inactividad
        initInactivityDetection();

        // Detectar cierre de pestaña o navegador
        window.addEventListener('beforeunload', function() { markTabClosed(); });
        window.addEventListener('pagehide',     function() { markTabClosed(); });
        // NOTA: connectSocketIO() se llama desde base.html (global, todas las páginas)
    }

    // Iniciar verificación de operaciones pendientes (solo para Operador)
    if (window.currentUserRole === 'Operador') {
        initPendingOperationsMonitor();
    }

    // Limpiar sessionStorage cuando se cierra sesión
    $('a[href*="/logout"]').on('click', function() {
        cleanupSessionStorage();
    });
});

// ============================================
// SISTEMA DE NOTIFICACIONES PARA OPERADOR
// ============================================

let pendingOperationsCheckInterval = null;
let alertedOperationsMap = new Map(); // Rastrear operaciones alertadas con su último tiempo
let isModalCurrentlyShowing = false; // Prevenir múltiples modales simultáneos

/**
 * Iniciar monitoreo de operaciones pendientes (solo para Operador)
 */
function initPendingOperationsMonitor() {
    console.log('🔔 Iniciando monitoreo de operaciones pendientes para Operador');

    // Verificar inmediatamente al cargar
    checkPendingOperations();

    // Verificar cada 1 minuto (60000 ms)
    pendingOperationsCheckInterval = setInterval(function() {
        checkPendingOperations();
    }, 60000);
}

/**
 * Verificar operaciones pendientes de atención
 */
function checkPendingOperations() {
    // Si ya hay un modal mostrándose, no verificar
    if (isModalCurrentlyShowing) {
        console.log('Modal ya está visible, omitiendo verificación');
        return;
    }

    ajaxRequest('/operations/api/check_pending_operations', 'GET', null, function(response) {
        if (response.success && response.count > 0) {
            const operationsToAlert = [];

            // Filtrar operaciones que realmente necesitan alerta ahora
            response.pending_operations.forEach(function(operation) {
                const timeInProcess = operation.time_in_process_minutes;
                const opId = operation.operation_id;

                // Lógica de alerta:
                // - Primera alerta a los 10 minutos exactos
                // - Alertas subsiguientes cada 10 minutos (20, 30, 40, etc.)
                const shouldAlert = (timeInProcess % 10 === 0);

                if (shouldAlert) {
                    // Verificar si ya fue alertada en este tiempo específico
                    const lastAlertedTime = alertedOperationsMap.get(opId);

                    // Solo alertar si:
                    // 1. Nunca ha sido alertada, O
                    // 2. El tiempo actual es diferente al último tiempo alertado
                    if (!lastAlertedTime || lastAlertedTime !== timeInProcess) {
                        operationsToAlert.push(operation);
                        // Registrar que esta operación será alertada en este minuto
                        alertedOperationsMap.set(opId, timeInProcess);
                    }
                }
            });

            // Si hay operaciones para alertar, mostrar modal
            if (operationsToAlert.length > 0) {
                showPendingOperationsAlert(operationsToAlert);
            }

            // Limpiar operaciones completadas del mapa de rastreo
            cleanupAlertedOperationsMap(response.pending_operations);
        }
    }, function(error) {
        console.error('Error al verificar operaciones pendientes:', error);
    });
}

/**
 * Limpiar el mapa de operaciones alertadas para remover operaciones que ya no están en proceso
 */
function cleanupAlertedOperationsMap(currentOperations) {
    const currentOpIds = new Set(currentOperations.map(op => op.operation_id));

    // Eliminar operaciones que ya no están en la lista
    for (let [opId, time] of alertedOperationsMap.entries()) {
        if (!currentOpIds.has(opId)) {
            alertedOperationsMap.delete(opId);
        }
    }
}

/**
 * Mostrar alerta modal de operaciones pendientes
 */
function showPendingOperationsAlert(operations) {
    // Marcar que el modal está visible
    isModalCurrentlyShowing = true;

    let contentHtml = '<div class="alert alert-warning mb-3">';
    contentHtml += '<strong><i class="bi bi-clock-history me-2"></i>Tienes operaciones que requieren atención inmediata:</strong>';
    contentHtml += '</div>';

    contentHtml += '<div class="list-group">';

    operations.forEach(function(op) {
        const timeInProcess = op.time_in_process_minutes;
        const clientName = op.client_name || 'N/A';
        const operationType = op.operation_type || 'N/A';
        const amountUSD = op.amount_usd ? '$' + parseFloat(op.amount_usd).toFixed(2) : '$0.00';

        contentHtml += '<div class="list-group-item">';
        contentHtml += '<div class="d-flex w-100 justify-content-between align-items-center">';
        contentHtml += '<div>';
        contentHtml += '<h6 class="mb-1"><strong>' + op.operation_id + '</strong> - ' + clientName + '</h6>';
        contentHtml += '<p class="mb-1"><small>' + operationType + ' | ' + amountUSD + '</small></p>';
        contentHtml += '</div>';
        contentHtml += '<div class="text-end">';
        contentHtml += '<span class="badge bg-danger fs-6">' + timeInProcess + ' min</span>';
        contentHtml += '</div>';
        contentHtml += '</div>';
        contentHtml += '</div>';
    });

    contentHtml += '</div>';

    // Llenar contenido del modal
    $('#pendingOperationsAlertContent').html(contentHtml);

    // Obtener o crear instancia del modal
    const modalElement = document.getElementById('pendingOperationsAlertModal');
    let alertModal = bootstrap.Modal.getInstance(modalElement);

    if (!alertModal) {
        alertModal = new bootstrap.Modal(modalElement, {
            backdrop: 'static',
            keyboard: false
        });
    }

    // Escuchar cuando el modal se oculta para resetear el flag
    $(modalElement).off('hidden.bs.modal').on('hidden.bs.modal', function() {
        isModalCurrentlyShowing = false;
        console.log('Modal cerrado, permitiendo nuevas verificaciones');
    });

    // Mostrar modal
    alertModal.show();
}

/**
 * Manejar clic en "Ver Operaciones"
 */
$(document).on('click', '#btnViewPendingOperations', function() {
    // Cerrar modal (el evento hidden.bs.modal se encargará de resetear isModalCurrentlyShowing)
    const modalElement = document.getElementById('pendingOperationsAlertModal');
    const alertModal = bootstrap.Modal.getInstance(modalElement);
    if (alertModal) {
        alertModal.hide();
    }

    // Redirigir a la vista de operaciones
    window.location.href = '/operations/list';
});

/**
 * Manejar clic en "Entendido"
 */
$(document).on('click', '#btnDismissAlert', function() {
    // Cerrar modal (el evento hidden.bs.modal se encargará de resetear isModalCurrentlyShowing)
    const modalElement = document.getElementById('pendingOperationsAlertModal');
    const alertModal = bootstrap.Modal.getInstance(modalElement);
    if (alertModal) {
        alertModal.hide();
    }
});

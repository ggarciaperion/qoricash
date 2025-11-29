/**
 * QoriCash Trading V2 - Common JavaScript Functions
 * Funciones comunes reutilizables en todo el sistema
 */

// Socket.IO connection
let socket = null;

/**
 * Conectar a SocketIO para actualizaciones en tiempo real
 */
function connectSocketIO() {
    if (socket) return; // Ya conectado

    socket = io();

    socket.on('connect', function() {
        console.log('✅ SocketIO conectado');
        // No mostrar notificación de conexión
    });

    socket.on('disconnect', function() {
        console.log('⚠️  SocketIO desconectado');
        // No mostrar notificación de desconexión
    });

    socket.on('connection_established', function(data) {
        console.log('Conexión establecida:', data);
    });

    // ============================================
    // EVENTOS DE OPERACIONES
    // ============================================

    socket.on('nueva_operacion', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            showNotification(`Nueva operación: ${data.operation_id} - ${data.client_name}`, 'info');
            playNotificationSound();
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
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            showNotification(`Operación ${data.operation_id} actualizada a: ${data.status}`, 'info');
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

    socket.on('operacion_completada', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            showNotification(`Operación ${data.operation_id} completada exitosamente`, 'success');
            playNotificationSound();
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
            showNotification(`Operación ${data.operation_id} cancelada`, 'warning');
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

    // ============================================
    // EVENTOS DE CLIENTES
    // ============================================

    socket.on('nuevo_cliente', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            showNotification(`Nuevo cliente: ${data.client_name} (${data.client_dni})`, 'info');
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

    socket.on('client_updated', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            showNotification(`Cliente actualizado: ${data.client_name}`, 'info');
        }

        // Actualizar tabla de clientes si existe
        if (typeof refreshClientsTable === 'function') {
            refreshClientsTable();
        }
    });

    socket.on('client_deleted', function(data) {
        // Solo mostrar notificación a Master y Operador
        if (window.currentUserRole === 'Master' || window.currentUserRole === 'Operador') {
            showNotification(`Cliente eliminado: ${data.client_name}`, 'warning');
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
        showNotification(`Nuevo usuario: ${data.username} (${data.role})`, 'info');

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
        showNotification(`Usuario actualizado: ${data.username}`, 'info');

        // Actualizar tabla de usuarios si existe
        if (typeof refreshUsersTable === 'function') {
            refreshUsersTable();
        }
    });

    socket.on('user_deleted', function(data) {
        showNotification(`Usuario eliminado: ${data.username}`, 'warning');

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
        showNotification(data.message, data.type || 'info');
    });

    // ============================================
    // EVENTOS DE ASIGNACIÓN DE OPERACIONES
    // ============================================

    socket.on('operacion_asignada', function(data) {
        console.log('Operación asignada recibida:', data);

        // Mostrar notificación al operador
        showNotification(data.message, 'info', 8000);

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

        // Reproducir sonido de notificación si está disponible
        playNotificationSound();
    });

    socket.on('operacion_reasignada_removida', function(data) {
        console.log('Operación reasignada removida:', data);

        // Mostrar notificación al operador anterior
        showNotification(data.message, 'warning', 8000);

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
}

/**
 * Mostrar notificación toast moderna
 */
function showNotification(message, type = 'info', duration = 5000) {
    // Usar SweetAlert2 Toast si está disponible
    if (typeof Swal !== 'undefined') {
        const Toast = Swal.mixin({
            toast: true,
            position: 'top-end',
            showConfirmButton: false,
            timer: duration,
            timerProgressBar: true,
            didOpen: (toast) => {
                toast.addEventListener('mouseenter', Swal.stopTimer)
                toast.addEventListener('mouseleave', Swal.resumeTimer)
            }
        });

        Toast.fire({
            icon: type === 'danger' ? 'error' : type,
            title: message
        });
    } else {
        // Fallback a showAlert
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
            if (successCallback) {
                successCallback(response);
            }
        },
        error: function(xhr, status, error) {
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
 * Formatear fecha
 */
function formatDate(dateString) {
    if (!dateString) return '-';
    
    const date = new Date(dateString);
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
 * Reproducir sonido de notificación
 */
function playNotificationSound() {
    // Crear audio element
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIGGe77OecTBMEUKzj8Lf4CgABCQAAAAAAAAA');
    audio.play().catch(() => {
        // Ignorar errores de reproducción
    });
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
 * Manejo de cambio de contraseña (modal global)
 * Usando event delegation y búsqueda dentro del modal para evitar conflictos
 */
$(document).on('click', '#btnChangePassword', function(e) {
    e.preventDefault();
    e.stopPropagation();

    // Buscar los campos dentro del modal específico
    const modal = $('#changePasswordModal');
    const oldPassword = modal.find('#current_password').val();
    const newPassword = modal.find('#new_password').val();
    const confirmPassword = modal.find('#confirm_password').val();

    console.log('=== CAMBIO DE CONTRASEÑA DEBUG ===');
    console.log('Modal encontrado:', modal.length > 0);
    console.log('Campo current_password:', {
        existe: modal.find('#current_password').length > 0,
        valor: oldPassword ? '*** (' + oldPassword.length + ' chars)' : 'EMPTY'
    });
    console.log('Campo new_password:', {
        existe: modal.find('#new_password').length > 0,
        valor: newPassword ? '*** (' + newPassword.length + ' chars)' : 'EMPTY'
    });
    console.log('Campo confirm_password:', {
        existe: modal.find('#confirm_password').length > 0,
        valor: confirmPassword ? '*** (' + confirmPassword.length + ' chars)' : 'EMPTY'
    });

    // Validar
    if (!oldPassword || !newPassword || !confirmPassword) {
        console.error('❌ Validación FALLIDA: campos vacíos');
        showNotification('Completa todos los campos', 'warning');
        return;
    }

    if (newPassword !== confirmPassword) {
        console.error('❌ Validación FALLIDA: contraseñas no coinciden');
        showNotification('Las contraseñas no coinciden', 'warning');
        return;
    }

    if (newPassword.length < 8) {
        console.error('❌ Validación FALLIDA: contraseña muy corta');
        showNotification('La contraseña debe tener al menos 8 caracteres', 'warning');
        return;
    }

    console.log('✅ Validación EXITOSA, enviando petición...');

    // Enviar
    const data = {
        old_password: oldPassword,
        new_password: newPassword
    };

    ajaxRequest('/change_password', 'POST', data, function(response) {
        console.log('✅ Contraseña cambiada exitosamente');
        showNotification(response.message, 'success');
        modal.modal('hide');
        modal.find('#changePasswordForm')[0].reset();
    });
});

/**
 * Cargar datos del dashboard
 */
function loadDashboardData(month = null, year = null) {
    let url = '/api/dashboard_data';
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

// Auto-conectar SocketIO al cargar la página
$(document).ready(function() {
    // Solo conectar si el usuario está autenticado
    if ($('nav.navbar').length > 0) {
        connectSocketIO();
    }

    // Iniciar verificación de operaciones pendientes (solo para Operador)
    if (window.currentUserRole === 'Operador') {
        initPendingOperationsMonitor();
    }
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
                // - Alertas subsiguientes cada 5 minutos (15, 20, 25, etc.)
                const shouldAlert = (timeInProcess === 10) ||
                                   (timeInProcess > 10 && (timeInProcess - 10) % 5 === 0);

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

    // Agregar sonido de alerta
    playNotificationSound();

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

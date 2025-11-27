/**
 * QoriCash Trading V2 - Operations Management JavaScript
 */

/**
 * Ver operación
 */
function viewOperation(operationId) {
    ajaxRequest(`/operations/api/${operationId}`, 'GET', null, function(response) {
        const op = response.operation;
        
        const html = `
            <div class="row">
                <div class="col-md-6">
                    <h6>Información de la Operación</h6>
                    <p><strong>ID:</strong> ${op.operation_id}</p>
                    <p><strong>Tipo:</strong> <span class="badge bg-${op.operation_type === 'Compra' ? 'success' : 'primary'}">${op.operation_type}</span></p>
                    <p><strong>Estado:</strong> <span class="badge bg-warning">${op.status}</span></p>
                    <p><strong>Usuario:</strong> ${op.user_name}</p>
                    <p><strong>Creado:</strong> ${formatDate(op.created_at)}</p>
                    ${op.completed_at ? `<p><strong>Completado:</strong> ${formatDate(op.completed_at)}</p>` : ''}
                </div>
                <div class="col-md-6">
                    <h6>Cliente</h6>
                    <p><strong>Nombre:</strong> ${op.client_name}</p>
                    <hr>
                    <h6>Montos</h6>
                    <p><strong>Monto USD:</strong> ${formatCurrency(op.amount_usd, 'USD')}</p>
                    <p><strong>Tipo de Cambio:</strong> ${parseFloat(op.exchange_rate).toFixed(4)}</p>
                    <p><strong>Monto PEN:</strong> ${formatCurrency(op.amount_pen, 'PEN')}</p>
                </div>
            </div>
            ${op.source_account || op.destination_account ? `
                <hr>
                <h6>Cuentas Bancarias</h6>
                ${op.source_account ? `<p><strong>Cuenta Origen:</strong> ${op.source_account}</p>` : ''}
                ${op.destination_account ? `<p><strong>Cuenta Destino:</strong> ${op.destination_account}</p>` : ''}
            ` : ''}
            ${op.notes ? `<hr><p><strong>Notas:</strong> ${op.notes}</p>` : ''}
            ${op.payment_proof_url || op.operator_proof_url ? `
                <hr>
                <h6>Comprobantes</h6>
                ${op.payment_proof_url ? `<p><a href="${op.payment_proof_url}" target="_blank" class="btn btn-sm btn-outline-primary"><i class="bi bi-file-earmark"></i> Ver Comprobante Cliente</a></p>` : ''}
                ${op.operator_proof_url ? `<p><a href="${op.operator_proof_url}" target="_blank" class="btn btn-sm btn-outline-primary"><i class="bi bi-file-earmark"></i> Ver Comprobante Operador</a></p>` : ''}
            ` : ''}
        `;
        
        $('#operationDetails').html(html);
        $('#viewOperationModal').modal('show');
    });
}

/**
 * Actualizar estado
 */
function updateStatus(operationId) {
    ajaxRequest(`/operations/api/${operationId}`, 'GET', null, function(response) {
        const op = response.operation;
        
        $('#status_operation_id').val(op.id);
        $('#status_operation_code').text(op.operation_id);
        $('#status_current').html(`<span class="badge bg-warning">${op.status}</span>`);
        
        // Limpiar select y agregar opciones válidas
        $('#status_new').html('<option value="">Seleccionar...</option>');
        
        if (op.status === 'Pendiente') {
            $('#status_new').append('<option value="En proceso">En Proceso</option>');
        } else if (op.status === 'En proceso') {
            $('#status_new').append('<option value="Completada">Completada</option>');
        }
        
        $('#updateStatusModal').modal('show');
    });
}

/**
 * Confirmar actualización de estado
 */
function confirmUpdateStatus() {
    const operationId = $('#status_operation_id').val();
    const newStatus = $('#status_new').val();
    const notes = $('textarea[name="notes"]').val();
    
    if (!newStatus) {
        showAlert('Selecciona un nuevo estado', 'warning');
        return;
    }
    
    const data = {
        status: newStatus,
        notes: notes
    };
    
    ajaxRequest(`/operations/api/update_status/${operationId}`, 'PATCH', data, function(response) {
        showAlert(response.message, 'success');
        $('#updateStatusModal').modal('hide');
        setTimeout(() => location.reload(), 1000);
    });
}

/**
 * Subir comprobante
 */
function uploadProof(operationId) {
    ajaxRequest(`/operations/api/${operationId}`, 'GET', null, function(response) {
        const op = response.operation;
        
        $('#proof_operation_id').val(op.id);
        $('#proof_operation_code').text(op.operation_id);
        
        $('#uploadProofModal').modal('show');
    });
}

/**
 * Confirmar upload de comprobante
 */
function confirmUploadProof() {
    const operationId = $('#proof_operation_id').val();
    const formData = new FormData($('#uploadProofForm')[0]);
    
    $.ajax({
        url: `/operations/api/upload_proof/${operationId}`,
        type: 'POST',
        data: formData,
        processData: false,
        contentType: false,
        success: function(response) {
            showAlert('Comprobante subido exitosamente', 'success');
            $('#uploadProofModal').modal('hide');
            setTimeout(() => location.reload(), 1000);
        },
        error: function(xhr) {
            showAlert('Error: ' + (xhr.responseJSON?.message || 'Error al subir comprobante'), 'danger');
        }
    });
}

/**
 * Cancelar operación
 */
function cancelOperation(operationId) {
    ajaxRequest(`/operations/api/${operationId}`, 'GET', null, function(response) {
        const op = response.operation;
        
        $('#cancel_operation_id').val(op.id);
        $('#cancel_operation_code').text(op.operation_id);
        
        $('#cancelOperationModal').modal('show');
    });
}

/**
 * Confirmar cancelación de operación
 */
function confirmCancelOperation() {
    const operationId = $('#cancel_operation_id').val();
    const reason = $('textarea[name="reason"]').val().trim();
    
    if (!reason) {
        showAlert('Debes ingresar una razón para cancelar', 'warning');
        return;
    }
    
    const data = { reason: reason };
    
    ajaxRequest(`/operations/api/cancel/${operationId}`, 'POST', data, function(response) {
        showAlert(response.message, 'success');
        $('#cancelOperationModal').modal('hide');
        setTimeout(() => location.reload(), 1000);
    });
}

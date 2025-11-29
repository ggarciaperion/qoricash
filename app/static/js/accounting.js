/**
 * accounting.js - Módulo de Contabilidad para QoriCash Trading V2
 */

// Función auxiliar para formatear montos con separador de miles
function formatAmount(amount, decimals = 2) {
    const num = parseFloat(amount) || 0;
    return num.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Variables globales
let availableOperations = [];
let allMatches = [];
let allBatches = [];

// Inicializar al cargar la página
$(document).ready(function() {
    loadMatches();
    loadBatches();

    // Configurar fecha por defecto
    const today = new Date().toISOString().split('T')[0];
    $('#batchDate').val(today);
});

// === AMARRES ===

function loadMatches() {
    ajaxRequest('/accounting/api/matches', 'GET', null, function(response) {
        if (response.success) {
            allMatches = response.matches;
            renderMatchesTable();
        }
    });
}

function renderMatchesTable() {
    const tbody = $('#matchesTableBody');
    tbody.empty();

    if (allMatches.length === 0) {
        tbody.html('<tr><td colspan="9" class="text-center">No hay amarres registrados</td></tr>');
        return;
    }

    allMatches.forEach(match => {
        const row = `
            <tr>
                <td>${match.id}</td>
                <td><small>${match.buy_operation_code}</small><br>${match.buy_client_name}</td>
                <td><small>${match.sell_operation_code}</small><br>${match.sell_client_name}</td>
                <td>$ ${formatAmount(match.matched_amount_usd, 2)}</td>
                <td>${match.buy_exchange_rate.toFixed(4)}</td>
                <td>${match.sell_exchange_rate.toFixed(4)}</td>
                <td class="${match.profit_pen >= 0 ? 'text-success' : 'text-danger'}">
                    S/ ${formatAmount(match.profit_pen, 2)}
                </td>
                <td>${match.batch_id || '-'}</td>
                <td>
                    ${!match.batch_id ? `
                        <button class="btn btn-sm btn-danger" onclick="deleteMatch(${match.id})">
                            <i class="bi bi-trash"></i>
                        </button>
                    ` : '<span class="text-muted">En batch</span>'}
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

function showCreateMatchModal() {
    // Cargar operaciones disponibles
    ajaxRequest('/accounting/api/available_operations', 'GET', null, function(response) {
        if (response.success) {
            availableOperations = response.operations;
            populateOperationSelects();
            const modal = new bootstrap.Modal(document.getElementById('createMatchModal'));
            modal.show();
        }
    });
}

function populateOperationSelects() {
    const buySelect = $('#buyOperationSelect');
    const sellSelect = $('#sellOperationSelect');

    buySelect.empty().append('<option value="">Seleccione...</option>');
    sellSelect.empty().append('<option value="">Seleccione...</option>');

    const buyOps = availableOperations.filter(op => op.operation_type === 'Compra');
    const sellOps = availableOperations.filter(op => op.operation_type === 'Venta');

    buyOps.forEach(op => {
        buySelect.append(`
            <option value="${op.id}">
                ${op.operation_id} - ${op.client_name} - $ ${formatAmount(op.available_usd, 2)} disponible
            </option>
        `);
    });

    sellOps.forEach(op => {
        sellSelect.append(`
            <option value="${op.id}">
                ${op.operation_id} - ${op.client_name} - $ ${formatAmount(op.available_usd, 2)} disponible
            </option>
        `);
    });
}

function createMatch() {
    const data = {
        buy_operation_id: parseInt($('#buyOperationSelect').val()),
        sell_operation_id: parseInt($('#sellOperationSelect').val()),
        matched_amount_usd: parseFloat($('#matchedAmount').val()),
        notes: $('#matchNotes').val()
    };

    if (!data.buy_operation_id || !data.sell_operation_id || !data.matched_amount_usd) {
        showNotification('Por favor complete todos los campos', 'warning');
        return;
    }

    ajaxRequest('/accounting/api/create_match', 'POST', data, function(response) {
        if (response.success) {
            showNotification('Amarre creado exitosamente', 'success');
            bootstrap.Modal.getInstance(document.getElementById('createMatchModal')).hide();
            $('#createMatchForm')[0].reset();
            loadMatches();
        }
    });
}

function deleteMatch(matchId) {
    if (!confirm('¿Está seguro de eliminar este amarre?')) return;

    ajaxRequest(`/accounting/api/delete_match/${matchId}`, 'DELETE', null, function(response) {
        if (response.success) {
            showNotification('Amarre eliminado', 'success');
            loadMatches();
        }
    });
}

// === BATCHES ===

function loadBatches() {
    ajaxRequest('/accounting/api/batches', 'GET', null, function(response) {
        if (response.success) {
            allBatches = response.batches;
            renderBatchesTable();
        }
    });
}

function renderBatchesTable() {
    const tbody = $('#batchesTableBody');
    tbody.empty();

    if (allBatches.length === 0) {
        tbody.html('<tr><td colspan="8" class="text-center">No hay lotes de neteo</td></tr>');
        return;
    }

    allBatches.forEach(batch => {
        const statusBadge = batch.status === 'Cerrado'
            ? '<span class="badge bg-success">Cerrado</span>'
            : '<span class="badge bg-warning text-dark">Abierto</span>';

        const row = `
            <tr>
                <td><strong>${batch.batch_code}</strong></td>
                <td>${new Date(batch.netting_date).toLocaleDateString('es-PE')}</td>
                <td>$ ${formatAmount(batch.total_buys_usd, 2)}</td>
                <td>$ ${formatAmount(batch.total_sells_usd, 2)}</td>
                <td class="text-success"><strong>S/ ${formatAmount(batch.total_profit_pen, 2)}</strong></td>
                <td>${batch.num_matches}</td>
                <td>${statusBadge}</td>
                <td>
                    <button class="btn btn-sm btn-info" onclick="viewBatchDetails(${batch.id})">
                        <i class="bi bi-eye"></i>
                    </button>
                    ${batch.status === 'Abierto' ? `
                        <button class="btn btn-sm btn-success" onclick="closeBatch(${batch.id})">
                            <i class="bi bi-lock"></i> Cerrar
                        </button>
                    ` : ''}
                </td>
            </tr>
        `;
        tbody.append(row);
    });
}

function showCreateBatchModal() {
    // Cargar amarres sin batch
    ajaxRequest('/accounting/api/matches?status=Activo', 'GET', null, function(response) {
        if (response.success) {
            const availableMatches = response.matches.filter(m => !m.batch_id);
            populateAvailableMatches(availableMatches);
            const modal = new bootstrap.Modal(document.getElementById('createBatchModal'));
            modal.show();
        }
    });
}

function populateAvailableMatches(matches) {
    const container = $('#availableMatchesList');
    container.empty();

    if (matches.length === 0) {
        container.html('<p class="text-muted">No hay amarres disponibles</p>');
        return;
    }

    matches.forEach(match => {
        container.append(`
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="${match.id}" id="match_${match.id}">
                <label class="form-check-label" for="match_${match.id}">
                    <strong>Match #${match.id}</strong>: ${match.buy_operation_code} ↔ ${match.sell_operation_code}
                    - $ ${formatAmount(match.matched_amount_usd, 2)} - Utilidad: S/ ${formatAmount(match.profit_pen, 2)}
                </label>
            </div>
        `);
    });
}

function createBatch() {
    const selectedMatches = [];
    $('#availableMatchesList input:checked').each(function() {
        selectedMatches.push(parseInt($(this).val()));
    });

    if (selectedMatches.length === 0) {
        showNotification('Debe seleccionar al menos un amarre', 'warning');
        return;
    }

    const data = {
        match_ids: selectedMatches,
        description: $('#batchDescription').val(),
        netting_date: $('#batchDate').val()
    };

    ajaxRequest('/accounting/api/create_batch', 'POST', data, function(response) {
        if (response.success) {
            showNotification('Lote de neteo creado exitosamente', 'success');
            bootstrap.Modal.getInstance(document.getElementById('createBatchModal')).hide();
            $('#createBatchForm')[0].reset();
            loadBatches();
            loadMatches();
        }
    });
}

function viewBatchDetails(batchId) {
    ajaxRequest(`/accounting/api/batch/${batchId}`, 'GET', null, function(response) {
        if (response.success) {
            const batch = response.batch;
            let html = `
                <h5>${batch.batch_code}</h5>
                <p><strong>Fecha:</strong> ${new Date(batch.netting_date).toLocaleDateString('es-PE')}</p>
                <p><strong>Descripción:</strong> ${batch.description || '-'}</p>
                <hr>
                <h6>Resumen:</h6>
                <ul>
                    <li>Total Compras: $ ${formatAmount(batch.total_buys_usd, 2)}</li>
                    <li>Total Ventas: $ ${formatAmount(batch.total_sells_usd, 2)}</li>
                    <li>Utilidad: S/ ${formatAmount(batch.total_profit_pen, 2)}</li>
                    <li>Número de Matches: ${batch.num_matches}</li>
                </ul>
                <hr>
                <h6>Asiento Contable:</h6>
                <table class="table table-sm">
                    <thead>
                        <tr><th>Cuenta</th><th>Debe</th><th>Haber</th></tr>
                    </thead>
                    <tbody>
            `;

            batch.accounting_entry.forEach(entry => {
                html += `
                    <tr>
                        <td>${entry.cuenta}</td>
                        <td>${entry.debe > 0 ? 'S/ ' + formatAmount(entry.debe, 2) : '-'}</td>
                        <td>${entry.haber > 0 ? 'S/ ' + formatAmount(entry.haber, 2) : '-'}</td>
                    </tr>
                `;
            });

            html += '</tbody></table>';

            Swal.fire({
                title: 'Detalles del Lote',
                html: html,
                width: 800,
                showCloseButton: true
            });
        }
    });
}

function closeBatch(batchId) {
    if (!confirm('¿Cerrar este lote? No se podrá modificar después.')) return;

    ajaxRequest(`/accounting/api/close_batch/${batchId}`, 'POST', null, function(response) {
        if (response.success) {
            showNotification('Lote cerrado exitosamente', 'success');
            loadBatches();
        }
    });
}

// === REPORTES ===

function exportLibroDiario() {
    window.location.href = '/accounting/export/libro_diario';
    showNotification('Descargando libro diario...', 'info');
}

function showProfitByClient() {
    ajaxRequest('/accounting/api/profit_by_client', 'GET', null, function(response) {
        if (response.success) {
            const profits = response.profits;
            let html = '<table class="table table-striped"><thead><tr><th>Cliente</th><th>Operaciones</th><th>Utilidad PEN</th></tr></thead><tbody>';

            profits.forEach(p => {
                html += `<tr><td>${p.client_name}</td><td>${p.num_operations}</td><td class="text-success">S/ ${formatAmount(p.profit_pen, 2)}</td></tr>`;
            });

            html += '</tbody></table>';

            Swal.fire({
                title: 'Utilidad por Cliente',
                html: html,
                width: 700,
                showCloseButton: true
            });
        }
    });
}

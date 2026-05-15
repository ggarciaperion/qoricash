/**
 * dashboard_analysis.js
 * Funciones compartidas del bloque "Análisis de Gestión" del Dashboard.
 * Usadas por master.html y trader.html.
 *
 * Dependencias globales esperadas (definidas por cada template):
 *   - currentFilters  { year, month, trader_id? }
 *   - inactiveData    { inactive_30, inactive_60, inactive_90, count_30, count_60, count_90 }
 *   - getTraderIdFilter()  (master) o CURRENT_TRADER_ID (trader)
 */

/**
 * Resuelve el trader_id que debe enviarse a los endpoints de análisis.
 * Master: usa getTraderIdFilter() (puede ser '' para "todos").
 * Trader: usa la constante CURRENT_TRADER_ID fijada en el template.
 */
function _getAnalysisTraderId() {
    if (typeof getTraderIdFilter === 'function') return getTraderIdFilter();
    return (typeof CURRENT_TRADER_ID !== 'undefined') ? CURRENT_TRADER_ID : '';
}

// ============================================
// TOP CLIENTES — MAYOR VOLUMEN USD
// ============================================
function loadTopClients() {
    const params = new URLSearchParams();
    const tid = _getAnalysisTraderId();
    if (tid) params.append('trader_id', tid);
    if (currentFilters.year)  params.append('year',  currentFilters.year);
    if (currentFilters.month) params.append('month', currentFilters.month);

    ajaxRequest(`/dashboard/api/dashboard/top-clients?${params.toString()}`, 'GET', null, function(response) {
        const clients = response.top_clients || [];
        const container = $('#topClientsList');
        $('#topClientsCount').text(clients.length);

        if (clients.length === 0) {
            container.html('<div class="text-center text-muted py-4 small">Sin datos para el período</div>');
            return;
        }

        const medals = [
            '<i class="bi bi-trophy-fill text-warning"></i>',
            '<i class="bi bi-trophy-fill text-secondary"></i>',
            '<i class="bi bi-trophy-fill" style="color:#cd7f32"></i>'
        ];
        const maxUsd = clients[0].total_usd || 1;

        let html = '';
        clients.forEach(function(c, idx) {
            const pct   = Math.round((c.total_usd / maxUsd) * 100);
            const medal = idx < 3 ? medals[idx] : `<span class="text-muted small fw-bold">#${idx+1}</span>`;
            html += `
                <div class="list-group-item list-group-item-action px-3 py-2"
                     style="cursor:pointer"
                     onclick="loadClientHistory(${c.client_id}, '${escapeHtml(c.name)}', '${c.dni}')">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center gap-2 overflow-hidden">
                            <span style="min-width:24px;">${medal}</span>
                            <span class="text-truncate small fw-semibold" title="${escapeHtml(c.name)}">${escapeHtml(c.name)}</span>
                        </div>
                        <div class="text-end ms-2 flex-shrink-0">
                            <div class="small fw-bold text-primary">$ ${formatNumber(c.total_usd, 0)}</div>
                            <div class="text-muted" style="font-size:0.7rem;">${c.op_count} op.</div>
                        </div>
                    </div>
                    <div class="progress mt-1" style="height:3px;">
                        <div class="progress-bar bg-primary" style="width:${pct}%"></div>
                    </div>
                </div>`;
        });
        container.html(html);
    });
}

// ============================================
// CLIENTES INACTIVOS
// ============================================
function loadInactiveClients() {
    const params = new URLSearchParams();
    const tid = _getAnalysisTraderId();
    if (tid) params.append('trader_id', tid);

    ajaxRequest(`/dashboard/api/dashboard/inactive-clients?${params.toString()}`, 'GET', null, function(response) {
        inactiveData = response;
        $('#badge30d').text(`30d: ${response.count_30}`);
        $('#badge60d').text(`60d: ${response.count_60}`);
        $('#badge90d').text(`90d+: ${response.count_90}`);
        $('#tab30Count').text(response.count_30);
        $('#tab60Count').text(response.count_60);
        $('#tab90Count').text(response.count_90);
        showInactiveTab('30');
    });
}

function showInactiveTab(tab) {
    $('#inactiveTabs .nav-link').removeClass('active');
    $(`#inactiveTabs .nav-link[data-tab="${tab}"]`).addClass('active');

    const list      = inactiveData[`inactive_${tab}`] || [];
    const container = $('#inactiveClientsContent');

    if (list.length === 0) {
        container.html('<div class="text-center text-success py-3 small"><i class="bi bi-check-circle me-1"></i>No hay clientes inactivos en este rango</div>');
        return;
    }

    const badgeClass = tab === '30' ? 'bg-warning text-dark' : (tab === '60' ? 'bg-danger' : 'bg-dark');
    let html = `<div class="table-responsive"><table class="table table-sm table-hover mb-0">
        <thead class="table-light">
            <tr>
                <th class="small">Cliente</th>
                <th class="small">DNI/RUC</th>
                <th class="small">Última Operación</th>
                <th class="small text-end">Días sin operar</th>
                <th class="small text-end">Acción</th>
            </tr>
        </thead><tbody>`;

    list.forEach(function(c) {
        html += `<tr>
            <td class="small fw-semibold">${escapeHtml(c.name)}</td>
            <td class="small text-muted">${c.dni}</td>
            <td class="small">${c.last_op || '-'}</td>
            <td class="text-end"><span class="badge ${badgeClass}">${c.days_inactive}d</span></td>
            <td class="text-end">
                <button class="btn btn-outline-primary py-0 px-1" style="font-size:0.7rem"
                        onclick="loadClientHistory(${c.client_id}, '${escapeHtml(c.name)}', '${c.dni}')">
                    <i class="bi bi-clock-history"></i> Ver historial
                </button>
            </td>
        </tr>`;
    });
    html += '</tbody></table></div>';
    container.html(html);
}

// ============================================
// TOP CLIENTES — MAYOR UTILIDAD
// ============================================
function loadTopProfit() {
    const params = new URLSearchParams();
    const tid = _getAnalysisTraderId();
    if (tid) params.append('trader_id', tid);
    if (currentFilters.year)  params.append('year',  currentFilters.year);
    if (currentFilters.month) params.append('month', currentFilters.month);

    ajaxRequest(`/dashboard/api/dashboard/top-clients-profit?${params.toString()}`, 'GET', null, function(response) {
        const clients = response.top_clients || [];
        const container = $('#topProfitList');
        $('#topProfitCount').text(clients.length);

        if (clients.length === 0) {
            container.html('<div class="text-center text-muted py-4 small">Sin datos de utilidad en el período<br><span style="font-size:0.7rem">Registra la tasa base en las operaciones</span></div>');
            return;
        }

        const medals = [
            '<i class="bi bi-trophy-fill text-warning"></i>',
            '<i class="bi bi-trophy-fill text-secondary"></i>',
            '<i class="bi bi-trophy-fill" style="color:#cd7f32"></i>'
        ];
        const maxProfit = Math.abs(clients[0].total_profit) || 1;

        let html = '';
        clients.forEach(function(c, idx) {
            const pct    = Math.round((Math.abs(c.total_profit) / maxProfit) * 100);
            const medal  = idx < 3 ? medals[idx] : `<span class="text-muted small fw-bold">#${idx+1}</span>`;
            const pClass = c.total_profit >= 0 ? 'text-success' : 'text-danger';
            html += `
                <div class="list-group-item list-group-item-action px-3 py-2" style="cursor:pointer"
                     onclick="loadClientHistory(${c.client_id}, '${escapeHtml(c.name)}', '${c.dni}')">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center gap-2 overflow-hidden">
                            <span style="min-width:24px;">${medal}</span>
                            <span class="text-truncate small fw-semibold" title="${escapeHtml(c.name)}">${escapeHtml(c.name)}</span>
                        </div>
                        <div class="text-end ms-2 flex-shrink-0">
                            <div class="small fw-bold ${pClass}">S/ ${formatNumber(c.total_profit, 2)}</div>
                            <div class="text-muted" style="font-size:0.7rem;">${c.op_count} op.</div>
                        </div>
                    </div>
                    <div class="progress mt-1" style="height:3px;">
                        <div class="progress-bar bg-success" style="width:${pct}%"></div>
                    </div>
                </div>`;
        });
        container.html(html);
    });
}

// ============================================
// TOP CLIENTES — MÁS OPERACIONES
// ============================================
function loadTopOps() {
    const params = new URLSearchParams();
    const tid = _getAnalysisTraderId();
    if (tid) params.append('trader_id', tid);
    if (currentFilters.year)  params.append('year',  currentFilters.year);
    if (currentFilters.month) params.append('month', currentFilters.month);

    ajaxRequest(`/dashboard/api/dashboard/top-clients-ops?${params.toString()}`, 'GET', null, function(response) {
        const clients = response.top_clients || [];
        const container = $('#topOpsList');
        $('#topOpsCount').text(clients.length);

        if (clients.length === 0) {
            container.html('<div class="text-center text-muted py-4 small">Sin datos para el período</div>');
            return;
        }

        const medals = [
            '<i class="bi bi-trophy-fill text-warning"></i>',
            '<i class="bi bi-trophy-fill text-secondary"></i>',
            '<i class="bi bi-trophy-fill" style="color:#cd7f32"></i>'
        ];
        const maxOps = clients[0].op_count || 1;

        let html = '';
        clients.forEach(function(c, idx) {
            const pct   = Math.round((c.op_count / maxOps) * 100);
            const medal = idx < 3 ? medals[idx] : `<span class="text-muted small fw-bold">#${idx+1}</span>`;
            html += `
                <div class="list-group-item list-group-item-action px-3 py-2" style="cursor:pointer"
                     onclick="loadClientHistory(${c.client_id}, '${escapeHtml(c.name)}', '${c.dni}')">
                    <div class="d-flex justify-content-between align-items-center">
                        <div class="d-flex align-items-center gap-2 overflow-hidden">
                            <span style="min-width:24px;">${medal}</span>
                            <span class="text-truncate small fw-semibold" title="${escapeHtml(c.name)}">${escapeHtml(c.name)}</span>
                        </div>
                        <div class="text-end ms-2 flex-shrink-0">
                            <div class="small fw-bold text-primary">${c.op_count} ops</div>
                            <div class="text-muted" style="font-size:0.7rem;">$ ${formatNumber(c.total_usd, 0)}</div>
                        </div>
                    </div>
                    <div class="progress mt-1" style="height:3px;">
                        <div class="progress-bar bg-primary" style="width:${pct}%"></div>
                    </div>
                </div>`;
        });
        container.html(html);
    });
}

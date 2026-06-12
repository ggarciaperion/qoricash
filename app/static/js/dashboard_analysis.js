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

// ============================================
// RANKING CARD — TAB SWITCHER
// ============================================
function switchRankingTab(tab) {
    document.querySelectorAll('.ranking-tab-btn').forEach(function(b) {
        b.classList.toggle('active', b.dataset.tab === tab);
    });
    document.querySelectorAll('.ranking-panel').forEach(function(p) {
        p.classList.toggle('active', p.id === 'rankingPanel-' + tab);
    });
}

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
// CLIENTES INACTIVOS — v2
// ============================================
function loadInactiveClients() {
    const params = new URLSearchParams();
    const tid = _getAnalysisTraderId();
    if (tid) params.append('trader_id', tid);

    ajaxRequest(`/dashboard/api/dashboard/inactive-clients?${params.toString()}`, 'GET', null, function(response) {
        inactiveData = response;
        $('#badge30d').text(response.count_30);
        $('#badge60d').text(response.count_60);
        $('#badge90d').text(response.count_90);
        $('#tab30Count').text(response.count_30);
        $('#tab60Count').text(response.count_60);
        $('#tab90Count').text(response.count_90);
        showInactiveTab('30');
    });
}

function _inactiveColor(tab) {
    return tab === '30' ? 'amber' : (tab === '60' ? 'red' : 'dark');
}

function _initials(name) {
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function _waLink(phone) {
    if (!phone) return null;
    const raw = phone.split(';')[0].replace(/\D/g, '');
    if (!raw) return null;
    const num = raw.startsWith('51') ? raw : '51' + raw;
    return `https://wa.me/${num}`;
}

function showInactiveTab(tab) {
    $('.inactive-tab-btn').removeClass('active amber-active red-active');
    const activeBtn = $(`.inactive-tab-btn[data-tab="${tab}"]`);
    activeBtn.addClass('active');
    if (tab === '30') activeBtn.addClass('amber-active');
    if (tab === '60') activeBtn.addClass('red-active');

    const list      = inactiveData[`inactive_${tab}`] || [];
    const container = $('#inactiveClientsContent');
    const color     = _inactiveColor(tab);

    if (list.length === 0) {
        container.html(`
            <div class="inactive-empty">
                <i class="bi bi-check-circle-fill"></i>
                <span>¡Sin clientes inactivos en este rango!</span>
            </div>`);
        return;
    }

    let html = '';
    list.forEach(function(c, i) {
        const initials = _initials(c.name);
        const waUrl    = _waLink(c.phone);
        const delay    = Math.min(i * 0.045, 0.4).toFixed(3);
        const daysLabel = c.days_inactive + 'd';

        html += `
        <div class="icard ${color}-card" style="animation-delay:${delay}s">
            <div class="icard-avatar ${color}">${initials}</div>
            <div class="icard-info">
                <div class="icard-name">${escapeHtml(c.name)}</div>
                <div class="icard-meta">${c.dni} &middot; &uacute;lt. op: ${c.last_op || 'N/A'}</div>
            </div>
            <div class="icard-days">
                <span class="days-badge ${color}">${daysLabel}</span>
            </div>
            <div class="icard-actions">
                <a href="/clients/detail/${c.client_id}" class="icard-btn cta" title="Ver perfil cliente">
                    <i class="bi bi-arrow-right-circle-fill"></i>
                </a>
                <button class="icard-btn hist" title="Ver historial"
                        onclick="loadClientHistory(${c.client_id}, '${escapeHtml(c.name)}', '${c.dni}')">
                    <i class="bi bi-clock-history"></i>
                </button>
                ${waUrl ? `<a href="${waUrl}" target="_blank" class="icard-btn wa" title="WhatsApp"><i class="bi bi-whatsapp"></i></a>` : ''}
            </div>
        </div>`;
    });

    container.addClass('tab-entering').html(html);
    setTimeout(() => container.removeClass('tab-entering'), 300);
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

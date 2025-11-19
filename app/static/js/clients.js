/**
 * JavaScript para Gestión de Clientes - VERSIÓN MEJORADA
 * QoriCash Trading V2
 *
 * Incluye:
 * - Validación de mayúsculas en tiempo real
 * - Validación de teléfonos (solo números y separación con ;)
 * - Gestión dinámica de cuentas bancarias (2-6 cuentas)
 * - Validación de cuentas duplicadas
 * - Visualización de archivos existentes en modo edición
 * - Restricciones por rol (TRADER solo edita cuentas bancarias)
 */

let editingClientId = null;
let currentUserRole = null; // Se establecerá desde el HTML
let bankAccountsCount = 0;
const MAX_ACCOUNTS = 6;
const MIN_ACCOUNTS = 2;

/**
 * Configuración de validaciones en tiempo real al cargar
 */
document.addEventListener('DOMContentLoaded', function() {
    // Verificar que el contenedor existe antes de inicializar
    const container = document.getElementById('bankAccountsContainer');
    if (container) {
        // Inicializar cuentas bancarias vacías
        initializeBankAccounts();
    }

    // Forzar mayúsculas en campos de texto específicos
    setupUpperCaseInputs();

    // Validar teléfono (solo números y punto y coma)
    setupPhoneValidation();
});

/**
 * Inicializar sistema de cuentas bancarias
 */
function initializeBankAccounts() {
    const container = document.getElementById('bankAccountsContainer');
    if (!container) {
        console.error('Container bankAccountsContainer no encontrado');
        return;
    }

    // Agregar las 2 cuentas mínimas requeridas
    addBankAccount(); // Cuenta 1
    addBankAccount(); // Cuenta 2

    // Ocultar mensaje de validación inicialmente
    const validationMessage = document.getElementById('accountsValidationMessage');
    if (validationMessage) {
        validationMessage.style.display = 'none';
    }
}

/**
 * Agregar nueva cuenta bancaria
 */
function addBankAccount() {
    if (bankAccountsCount >= MAX_ACCOUNTS) {
        showAlert('error', `Máximo ${MAX_ACCOUNTS} cuentas permitidas`);
        return;
    }

    bankAccountsCount++;
    const accountIndex = bankAccountsCount;
    const isRequired = accountIndex <= MIN_ACCOUNTS;

    const container = document.getElementById('bankAccountsContainer');

    const accountHtml = `
        <div class="bank-account-group" id="bankAccount${accountIndex}" data-account-index="${accountIndex}">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h6 class="mb-0">
                    <i class="bi bi-bank"></i> Cuenta Bancaria ${accountIndex}
                    ${isRequired ? '<span class="text-danger">*</span>' : '<span class="text-muted">(Opcional)</span>'}
                </h6>
                ${!isRequired ? `<button type="button" class="btn btn-danger btn-sm" onclick="removeBankAccount(${accountIndex})">
                    <i class="bi bi-trash"></i> Eliminar
                </button>` : ''}
            </div>

            <div class="row mb-3">
                <div class="col-md-3">
                    <label class="form-label">Origen ${isRequired ? '<span class="text-danger">*</span>' : ''}</label>
                    <select class="form-select bank-origen" id="origen${accountIndex}" name="origen${accountIndex}"
                            ${isRequired ? 'required' : ''} onchange="validateDuplicateAccounts()">
                        <option value="">Seleccionar...</option>
                        <option value="Lima">Lima</option>
                        <option value="Provincia">Provincia</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Banco ${isRequired ? '<span class="text-danger">*</span>' : ''}</label>
                    <select class="form-select bank-name" id="bankName${accountIndex}" name="bank_name${accountIndex}"
                            ${isRequired ? 'required' : ''} onchange="validateCCI(${accountIndex}); validateDuplicateAccounts()">
                        <option value="">Seleccionar...</option>
                        <option value="BCP">BCP</option>
                        <option value="INTERBANK">INTERBANK</option>
                        <option value="PICHINCHA">PICHINCHA</option>
                        <option value="BANBIF">BANBIF</option>
                        <option value="BBVA">BBVA</option>
                        <option value="SCOTIABANK">SCOTIABANK</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Tipo de Cuenta ${isRequired ? '<span class="text-danger">*</span>' : ''}</label>
                    <select class="form-select bank-account-type" id="accountType${accountIndex}" name="account_type${accountIndex}"
                            ${isRequired ? 'required' : ''}>
                        <option value="">Seleccionar...</option>
                        <option value="Ahorro">Ahorro</option>
                        <option value="Corriente">Corriente</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">Moneda ${isRequired ? '<span class="text-danger">*</span>' : ''}</label>
                    <select class="form-select bank-currency" id="currency${accountIndex}" name="currency${accountIndex}"
                            ${isRequired ? 'required' : ''} onchange="validateMinimumAccounts(); validateDuplicateAccounts()">
                        <option value="">Seleccionar...</option>
                        <option value="S/">S/ (Soles)</option>
                        <option value="$">$ (Dólares)</option>
                    </select>
                </div>
            </div>
            <div class="row">
                <div class="col-md-12">
                    <label class="form-label">Número de Cuenta ${isRequired ? '<span class="text-danger">*</span>' : ''}</label>
                    <input type="text" class="form-control bank-account-number" id="bankAccountNumber${accountIndex}"
                           name="bank_account_number${accountIndex}" ${isRequired ? 'required' : ''} maxlength="20">
                    <small class="form-text text-muted" id="cciHelp${accountIndex}">Ingrese el número de cuenta</small>
                </div>
            </div>
        </div>
    `;

    container.insertAdjacentHTML('beforeend', accountHtml);

    // Setup validation for account number input (only numbers)
    const accountInput = document.getElementById(`bankAccountNumber${accountIndex}`);
    accountInput.addEventListener('input', function(e) {
        this.value = this.value.replace(/[^0-9]/g, '');
    });

    updateAccountCount();
    updateAddButton();
}

/**
 * Eliminar cuenta bancaria
 */
function removeBankAccount(accountIndex) {
    const account = document.getElementById(`bankAccount${accountIndex}`);
    if (account) {
        account.remove();
        bankAccountsCount--;
        updateAccountCount();
        updateAddButton();
        validateMinimumAccounts();
        validateDuplicateAccounts();
    }
}

/**
 * Actualizar contador de cuentas
 */
function updateAccountCount() {
    const activeAccounts = document.querySelectorAll('.bank-account-group').length;
    const accountCountElement = document.getElementById('accountCount');
    if (accountCountElement) {
        accountCountElement.textContent = activeAccounts;
    }
}

/**
 * Actualizar estado del botón Agregar
 */
function updateAddButton() {
    const btn = document.getElementById('addBankAccountBtn');
    if (!btn) return;

    if (bankAccountsCount >= MAX_ACCOUNTS) {
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-x-circle"></i> Máximo de cuentas alcanzado';
    } else {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-plus-circle"></i> Agregar Cuenta Bancaria';
    }
}

/**
 * Validar que existan al menos 2 cuentas: una en S/ y otra en $
 */
function validateMinimumAccounts() {
    const currencySelects = document.querySelectorAll('.bank-currency');

    // Debug
    console.log('Validando cuentas:', currencySelects.length, 'selects encontrados');

    if (currencySelects.length === 0) {
        console.warn('No se encontraron selectores de moneda');
        return false;
    }

    const currencies = Array.from(currencySelects)
        .map(select => select.value)
        .filter(val => val !== '');

    console.log('Monedas seleccionadas:', currencies);

    const message = document.getElementById('accountsValidationMessage');

    if (!message) {
        console.warn('Elemento accountsValidationMessage no encontrado');
        return true; // Si no hay elemento de mensaje, no bloquear
    }

    // Si no hay suficientes cuentas con moneda seleccionada
    if (currencies.length < MIN_ACCOUNTS) {
        console.log('Faltan cuentas: se requieren', MIN_ACCOUNTS, 'pero hay', currencies.length);
        message.style.display = 'block';
        return false;
    }

    const hasSoles = currencies.includes('S/');
    const hasDolares = currencies.includes('$');

    console.log('Tiene Soles:', hasSoles, '| Tiene Dólares:', hasDolares);

    if (hasSoles && hasDolares) {
        message.style.display = 'none';
        return true;
    } else {
        message.style.display = 'block';
        return false;
    }
}

/**
 * Validar cuentas duplicadas (mismo banco y misma moneda)
 */
function validateDuplicateAccounts() {
    const accounts = [];
    const accountGroups = document.querySelectorAll('.bank-account-group');

    accountGroups.forEach(group => {
        const index = group.dataset.accountIndex;
        const bank = document.getElementById(`bankName${index}`)?.value;
        const currency = document.getElementById(`currency${index}`)?.value;

        if (bank && currency) {
            accounts.push({ bank, currency, index });
        }
    });

    // Buscar duplicados
    const duplicates = [];
    for (let i = 0; i < accounts.length; i++) {
        for (let j = i + 1; j < accounts.length; j++) {
            if (accounts[i].bank === accounts[j].bank &&
                accounts[i].currency === accounts[j].currency) {
                duplicates.push({ i: accounts[i].index, j: accounts[j].index });
            }
        }
    }

    const message = document.getElementById('duplicateAccountsMessage');

    if (duplicates.length > 0) {
        message.style.display = 'block';
        return false;
    } else {
        message.style.display = 'none';
        return true;
    }
}

/**
 * Configurar inputs de mayúsculas automáticas
 */
function setupUpperCaseInputs() {
    const upperCaseInputs = document.querySelectorAll('.text-uppercase-input');
    upperCaseInputs.forEach(input => {
        input.addEventListener('input', function(e) {
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.toUpperCase();
            this.setSelectionRange(start, end);
        });
    });
}

/**
 * Validar teléfono: solo números y punto y coma
 */
function setupPhoneValidation() {
    const phoneInput = document.getElementById('phone');
    if (phoneInput) {
        phoneInput.addEventListener('input', function(e) {
            // Permitir solo números y punto y coma
            this.value = this.value.replace(/[^0-9;]/g, '');

            // Prevenir múltiples punto y coma consecutivos
            this.value = this.value.replace(/;+/g, ';');
        });

        phoneInput.addEventListener('blur', function(e) {
            // Limpiar punto y coma al inicio o al final
            this.value = this.value.replace(/^;+|;+$/g, '');
        });
    }
}

/**
 * Validar CCI según banco seleccionado
 */
function validateCCI(accountNumber) {
    const bankSelect = document.getElementById(`bankName${accountNumber}`);
    const accountInput = document.getElementById(`bankAccountNumber${accountNumber}`);
    const helpText = document.getElementById(`cciHelp${accountNumber}`);

    if (!bankSelect || !accountInput || !helpText) return;

    const selectedBank = bankSelect.value;

    if (selectedBank === 'BBVA' || selectedBank === 'SCOTIABANK') {
        accountInput.setAttribute('minlength', '20');
        accountInput.setAttribute('maxlength', '20');
        accountInput.setAttribute('pattern', '[0-9]{20}');
        helpText.textContent = `CCI de ${selectedBank}: exactamente 20 dígitos`;
        helpText.className = 'form-text text-danger';
    } else {
        accountInput.removeAttribute('minlength');
        accountInput.setAttribute('maxlength', '20');
        accountInput.removeAttribute('pattern');
        helpText.textContent = 'Ingrese el número de cuenta';
        helpText.className = 'form-text text-muted';
    }
}

/**
 * Cambiar tipo de documento y mostrar campos correspondientes
 */
function changeDocumentType() {
    const docType = document.getElementById('documentType').value;
    const dniCeFields = document.getElementById('dniCeFields');
    const rucFields = document.getElementById('rucFields');
    const dniInput = document.getElementById('dni');
    const dniHelp = document.getElementById('dniHelp');

    // Ocultar todos los campos
    dniCeFields.style.display = 'none';
    rucFields.style.display = 'none';

    // Resetear required en campos condicionales
    document.getElementById('apellidoPaterno').required = false;
    document.getElementById('apellidoMaterno').required = false;
    document.getElementById('nombres').required = false;
    document.getElementById('razonSocial').required = false;

    if (docType === 'DNI') {
        dniCeFields.style.display = 'block';
        dniHelp.textContent = 'Ingrese 8 dígitos';
        dniInput.maxLength = 8;
        dniInput.pattern = '[0-9]{8}';
        document.getElementById('apellidoPaterno').required = true;
        document.getElementById('apellidoMaterno').required = true;
        document.getElementById('nombres').required = true;
    } else if (docType === 'CE') {
        dniCeFields.style.display = 'block';
        dniHelp.textContent = 'Ingrese entre 9 y 12 caracteres';
        dniInput.maxLength = 12;
        dniInput.pattern = '[A-Z0-9]{9,12}';
        document.getElementById('apellidoPaterno').required = true;
        document.getElementById('apellidoMaterno').required = true;
        document.getElementById('nombres').required = true;
    } else if (docType === 'RUC') {
        rucFields.style.display = 'block';
        dniHelp.textContent = 'Ingrese 11 dígitos';
        dniInput.maxLength = 11;
        dniInput.pattern = '[0-9]{11}';
        document.getElementById('razonSocial').required = true;
    }
}

/**
 * Aplicar restricciones por rol - VERSIÓN ROBUSTA
 */
function applyRoleRestrictions(role) {
    console.log('Aplicando restricciones para rol:', role);

    if (role !== 'Trader') {
        console.log('No es Trader, permitir todo');
        return;
    }

    console.log('ES TRADER - Bloqueando campos...');

    // TRADER: solo puede editar cuentas bancarias
    // Bloquear TODOS los inputs, selects y textareas del formulario
    const form = document.getElementById('clientForm');
    if (!form) {
        console.error('Formulario no encontrado');
        return;
    }

    // Obtener todos los inputs, selects y textareas
    const allFields = form.querySelectorAll('input:not(.bank-account-number):not(.bank-name):not(.bank-currency):not(.bank-origen):not(.bank-account-type), select:not(.bank-name):not(.bank-currency):not(.bank-origen):not(.bank-account-type), textarea');

    console.log('Total de campos a bloquear:', allFields.length);

    allFields.forEach(field => {
        // No bloquear campos de cuentas bancarias (tienen clases específicas)
        const fieldClasses = field.className;
        if (fieldClasses.includes('bank-')) {
            console.log('Saltando campo bancario:', field.id);
            return; // Skip bank account fields
        }

        // Bloquear el campo
        field.disabled = true;
        field.readOnly = true;
        field.style.backgroundColor = '#e9ecef';
        field.style.cursor = 'not-allowed';
        field.style.opacity = '0.6';

        console.log('Bloqueado:', field.id || field.name);
    });

    // Ocultar completamente la sección de documentos
    const dniCeFields = document.getElementById('dniCeFields');
    const rucFields = document.getElementById('rucFields');

    if (dniCeFields) {
        const documentSection = dniCeFields.querySelector('.document-section');
        if (documentSection) {
            documentSection.style.display = 'none';
        }
    }

    if (rucFields) {
        const documentSection = rucFields.querySelector('.document-section');
        if (documentSection) {
            documentSection.style.display = 'none';
        }
    }

    // Agregar nota informativa prominente
    const existingNote = document.getElementById('traderRestrictionNote');
    if (!existingNote) {
        const modalBody = document.querySelector('#createClientModal .modal-body');
        if (modalBody) {
            const traderNote = document.createElement('div');
            traderNote.className = 'alert alert-warning mb-3';
            traderNote.id = 'traderRestrictionNote';
            traderNote.style.position = 'sticky';
            traderNote.style.top = '0';
            traderNote.style.zIndex = '1000';
            traderNote.innerHTML = `
                <h6 class="alert-heading"><i class="bi bi-exclamation-triangle"></i> Modo Solo Lectura (Trader)</h6>
                <p class="mb-0"><strong>Solo puedes editar las cuentas bancarias.</strong> Los demás campos están bloqueados y no se pueden modificar.</p>
            `;
            modalBody.insertBefore(traderNote, modalBody.firstChild);
        }
    }

    console.log('Restricciones aplicadas completamente');
}

/**
 * Ver detalles de un cliente
 */
function viewClient(clientId) {
    fetch(`/clients/api/${clientId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const client = data.client;
                let html = '<div class="row">';

                // Información básica
                html += '<div class="col-md-12"><h6 class="border-bottom pb-2 mb-3">Información Básica</h6></div>';
                html += `<div class="col-md-6"><strong>Tipo de Documento:</strong> ${client.document_type}</div>`;
                html += `<div class="col-md-6"><strong>Número:</strong> ${client.dni}</div>`;
                html += `<div class="col-md-12 mt-2"><strong>Nombre:</strong> ${client.full_name || '-'}</div>`;

                // Contacto
                html += '<div class="col-md-12 mt-4"><h6 class="border-bottom pb-2 mb-3">Contacto</h6></div>';
                html += `<div class="col-md-6"><strong>Email:</strong> ${client.email}</div>`;
                html += `<div class="col-md-6"><strong>Teléfono:</strong> ${client.phone || 'No registrado'}</div>`;

                // Dirección
                if (client.full_address) {
                    html += '<div class="col-md-12 mt-4"><h6 class="border-bottom pb-2 mb-3">Dirección</h6></div>';
                    html += `<div class="col-md-12">${client.full_address}</div>`;
                }

                // Documentos - VERSIÓN MEJORADA
                html += '<div class="col-md-12 mt-4"><h6 class="border-bottom pb-2 mb-3"><i class="bi bi-folder2-open"></i> Documentos Adjuntos</h6></div>';

                let hasDocuments = false;

                if (client.document_type === 'RUC') {
                    if (client.dni_representante_front_url) {
                        hasDocuments = true;
                        html += `
                            <div class="col-md-6 mb-3">
                                <div class="card">
                                    <div class="card-body p-2">
                                        <strong class="d-block mb-2"><i class="bi bi-file-earmark-person"></i> DNI Representante (Frontal)</strong>
                                        <img src="${client.dni_representante_front_url}"
                                             class="img-fluid img-thumbnail mb-2"
                                             style="max-height: 150px; cursor: pointer;"
                                             onclick="window.open('${client.dni_representante_front_url}', '_blank')"
                                             onerror="this.onerror=null; this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23999%22>Error</text></svg>'; this.style.maxHeight='60px';">
                                        <br>
                                        <a href="${client.dni_representante_front_url}" target="_blank" class="btn btn-sm btn-primary">
                                            <i class="bi bi-eye"></i> Ver
                                        </a>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    if (client.dni_representante_back_url) {
                        hasDocuments = true;
                        html += `
                            <div class="col-md-6 mb-3">
                                <div class="card">
                                    <div class="card-body p-2">
                                        <strong class="d-block mb-2"><i class="bi bi-file-earmark-person"></i> DNI Representante (Reverso)</strong>
                                        <img src="${client.dni_representante_back_url}"
                                             class="img-fluid img-thumbnail mb-2"
                                             style="max-height: 150px; cursor: pointer;"
                                             onclick="window.open('${client.dni_representante_back_url}', '_blank')"
                                             onerror="this.onerror=null; this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23999%22>Error</text></svg>'; this.style.maxHeight='60px';">
                                        <br>
                                        <a href="${client.dni_representante_back_url}" target="_blank" class="btn btn-sm btn-primary">
                                            <i class="bi bi-eye"></i> Ver
                                        </a>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    if (client.ficha_ruc_url) {
                        hasDocuments = true;
                        const isPdf = client.ficha_ruc_url.match(/\.pdf$/i);
                        if (isPdf) {
                            html += `
                                <div class="col-md-12 mb-3">
                                    <div class="card">
                                        <div class="card-body p-2">
                                            <strong class="d-block mb-2"><i class="bi bi-file-pdf"></i> Ficha RUC</strong>
                                            <a href="${client.ficha_ruc_url}" target="_blank" class="btn btn-primary">
                                                <i class="bi bi-file-pdf"></i> Ver PDF
                                            </a>
                                        </div>
                                    </div>
                                </div>
                            `;
                        } else {
                            html += `
                                <div class="col-md-12 mb-3">
                                    <div class="card">
                                        <div class="card-body p-2">
                                            <strong class="d-block mb-2"><i class="bi bi-file-earmark-text"></i> Ficha RUC</strong>
                                            <img src="${client.ficha_ruc_url}"
                                                 class="img-fluid img-thumbnail mb-2"
                                                 style="max-height: 200px; cursor: pointer;"
                                                 onclick="window.open('${client.ficha_ruc_url}', '_blank')"
                                                 onerror="this.onerror=null; this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23999%22>PDF</text></svg>'; this.style.maxHeight='60px';">
                                            <br>
                                            <a href="${client.ficha_ruc_url}" target="_blank" class="btn btn-sm btn-primary">
                                                <i class="bi bi-eye"></i> Ver
                                            </a>
                                        </div>
                                    </div>
                                </div>
                            `;
                        }
                    }
                } else {
                    // DNI o CE
                    if (client.dni_front_url) {
                        hasDocuments = true;
                        html += `
                            <div class="col-md-6 mb-3">
                                <div class="card">
                                    <div class="card-body p-2">
                                        <strong class="d-block mb-2"><i class="bi bi-file-earmark-person"></i> Documento (Frontal)</strong>
                                        <img src="${client.dni_front_url}"
                                             class="img-fluid img-thumbnail mb-2"
                                             style="max-height: 150px; cursor: pointer;"
                                             onclick="window.open('${client.dni_front_url}', '_blank')"
                                             onerror="this.onerror=null; this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23999%22>Error</text></svg>'; this.style.maxHeight='60px';">
                                        <br>
                                        <a href="${client.dni_front_url}" target="_blank" class="btn btn-sm btn-primary">
                                            <i class="bi bi-eye"></i> Ver
                                        </a>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    if (client.dni_back_url) {
                        hasDocuments = true;
                        html += `
                            <div class="col-md-6 mb-3">
                                <div class="card">
                                    <div class="card-body p-2">
                                        <strong class="d-block mb-2"><i class="bi bi-file-earmark-person"></i> Documento (Reverso)</strong>
                                        <img src="${client.dni_back_url}"
                                             class="img-fluid img-thumbnail mb-2"
                                             style="max-height: 150px; cursor: pointer;"
                                             onclick="window.open('${client.dni_back_url}', '_blank')"
                                             onerror="this.onerror=null; this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><rect fill=%22%23ddd%22 width=%22100%22 height=%22100%22/><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 fill=%22%23999%22>Error</text></svg>'; this.style.maxHeight='60px';">
                                        <br>
                                        <a href="${client.dni_back_url}" target="_blank" class="btn btn-sm btn-primary">
                                            <i class="bi bi-eye"></i> Ver
                                        </a>
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                }

                if (!hasDocuments) {
                    html += '<div class="col-md-12"><p class="text-muted"><i class="bi bi-info-circle"></i> No hay documentos adjuntos</p></div>';
                }

                // Información bancaria
                if (client.bank_accounts && client.bank_accounts.length > 0) {
                    html += '<div class="col-md-12 mt-4"><h6 class="border-bottom pb-2 mb-3">Información Bancaria</h6></div>';
                    client.bank_accounts.forEach((account, index) => {
                        html += `<div class="col-md-12 mb-3"><strong>Cuenta ${index + 1}:</strong></div>`;
                        html += `<div class="col-md-3"><strong>Origen:</strong> ${account.origen || '-'}</div>`;
                        html += `<div class="col-md-3"><strong>Banco:</strong> ${account.bank_name}</div>`;
                        html += `<div class="col-md-3"><strong>Tipo:</strong> ${account.account_type}</div>`;
                        html += `<div class="col-md-3"><strong>Moneda:</strong> ${account.currency}</div>`;
                        html += `<div class="col-md-12 mt-1"><strong>Número:</strong> ${account.account_number}</div>`;
                    });
                }

                // Estadísticas
                if (client.total_operations !== undefined) {
                    html += '<div class="col-md-12 mt-4"><h6 class="border-bottom pb-2 mb-3">Estadísticas</h6></div>';
                    html += `<div class="col-md-6"><strong>Total Operaciones:</strong> ${client.total_operations}</div>`;
                    html += `<div class="col-md-6"><strong>Estado:</strong> <span class="badge bg-${client.status === 'Activo' ? 'success' : 'secondary'}">${client.status}</span></div>`;
                }

                html += '</div>';

                document.getElementById('viewClientBody').innerHTML = html;
                const modal = new bootstrap.Modal(document.getElementById('viewClientModal'));
                modal.show();
            } else {
                showAlert('error', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'Error al cargar los datos del cliente');
        });
}

/**
 * Editar cliente
 */
function editClient(clientId) {
    fetch(`/clients/api/${clientId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const client = data.client;
                editingClientId = clientId;

                // Cambiar título del modal
                const modalTitle = document.getElementById('modalTitle');
                if (modalTitle) {
                    modalTitle.innerHTML = '<i class="bi bi-pencil"></i> Editar Cliente';
                }

                // Llenar formulario básico
                const clientIdField = document.getElementById('clientId');
                const documentTypeField = document.getElementById('documentType');
                const dniField = document.getElementById('dni');
                const emailField = document.getElementById('email');
                const phoneField = document.getElementById('phone');

                if (clientIdField) clientIdField.value = client.id;
                if (documentTypeField) documentTypeField.value = client.document_type;
                if (dniField) dniField.value = client.dni;
                if (emailField) emailField.value = client.email;
                if (phoneField) phoneField.value = client.phone || '';

                // Llamar a la función para mostrar campos correctos
                changeDocumentType();

                // Llenar campos según tipo de documento
                if (client.document_type === 'RUC') {
                    const razonSocialField = document.getElementById('razonSocial');
                    const personaContactoField = document.getElementById('personaContacto');

                    if (razonSocialField) razonSocialField.value = client.razon_social || '';
                    if (personaContactoField) personaContactoField.value = client.persona_contacto || '';

                    // Mostrar archivos existentes
                    showExistingFile('dniRepFrontPreview', client.dni_representante_front_url, 'DNI Representante Frontal');
                    showExistingFile('dniRepBackPreview', client.dni_representante_back_url, 'DNI Representante Reverso');
                    showExistingFile('fichaRucPreview', client.ficha_ruc_url, 'Ficha RUC');
                } else {
                    const apellidoPaternoField = document.getElementById('apellidoPaterno');
                    const apellidoMaternoField = document.getElementById('apellidoMaterno');
                    const nombresField = document.getElementById('nombres');

                    if (apellidoPaternoField) apellidoPaternoField.value = client.apellido_paterno || '';
                    if (apellidoMaternoField) apellidoMaternoField.value = client.apellido_materno || '';
                    if (nombresField) nombresField.value = client.nombres || '';

                    // Mostrar archivos existentes
                    showExistingFile('dniFrontPreview', client.dni_front_url, 'Documento Frontal');
                    showExistingFile('dniBackPreview', client.dni_back_url, 'Documento Reverso');
                }

                // Dirección
                const direccionField = document.getElementById('direccion');
                const distritoField = document.getElementById('distrito');
                const provinciaField = document.getElementById('provincia');
                const departamentoField = document.getElementById('departamento');

                if (direccionField) direccionField.value = client.direccion || '';
                if (distritoField) distritoField.value = client.distrito || '';
                if (provinciaField) provinciaField.value = client.provincia || '';
                if (departamentoField) departamentoField.value = client.departamento || '';

                // Limpiar cuentas bancarias existentes
                const bankAccountsContainer = document.getElementById('bankAccountsContainer');
                if (bankAccountsContainer) {
                    bankAccountsContainer.innerHTML = '';
                    bankAccountsCount = 0;

                    // Cargar cuentas bancarias del cliente
                    if (client.bank_accounts && client.bank_accounts.length > 0) {
                        client.bank_accounts.forEach((account, index) => {
                            addBankAccount();
                            const accountIndex = index + 1;

                            const origenField = document.getElementById(`origen${accountIndex}`);
                            const bankNameField = document.getElementById(`bankName${accountIndex}`);
                            const accountTypeField = document.getElementById(`accountType${accountIndex}`);
                            const currencyField = document.getElementById(`currency${accountIndex}`);
                            const accountNumberField = document.getElementById(`bankAccountNumber${accountIndex}`);

                            if (origenField) origenField.value = account.origen || '';
                            if (bankNameField) bankNameField.value = account.bank_name || '';
                            if (accountTypeField) accountTypeField.value = account.account_type || '';
                            if (currencyField) currencyField.value = account.currency || '';
                            if (accountNumberField) accountNumberField.value = account.account_number || '';
                        });
                    } else {
                        // Si no hay cuentas, agregar las 2 mínimas
                        addBankAccount();
                        addBankAccount();
                    }
                }

                // Deshabilitar cambio de tipo de documento y número al editar
                if (documentTypeField) {
                    documentTypeField.disabled = true;
                    documentTypeField.classList.add('bg-light');
                }
                if (dniField) {
                    dniField.disabled = true;
                    dniField.classList.add('bg-light');
                }

                // Mostrar modal
                // Las restricciones se aplicarán automáticamente con el evento 'shown.bs.modal'
                const modalElement = document.getElementById('createClientModal');
                if (modalElement) {
                    const modal = new bootstrap.Modal(modalElement);
                    modal.show();
                }
            } else {
                showAlert('error', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('error', 'Error al cargar los datos del cliente');
        });
}

/**
 * Mostrar archivo existente en el preview - VERSIÓN MEJORADA
 */
function showExistingFile(previewElementId, fileUrl, fileName) {
    const previewElement = document.getElementById(previewElementId);

    console.log('showExistingFile:', previewElementId, fileUrl, fileName);

    if (!previewElement) {
        console.warn('Preview element no encontrado:', previewElementId);
        return;
    }

    if (!fileUrl) {
        console.log('No hay URL de archivo para:', previewElementId);
        previewElement.innerHTML = '<small class="text-muted">No hay archivo cargado</small>';
        return;
    }

    const isImage = fileUrl.match(/\.(jpg|jpeg|png|gif|webp)$/i);
    const isPdf = fileUrl.match(/\.pdf$/i);

    if (isImage) {
        previewElement.innerHTML = `
            <div class="mb-2">
                <small class="text-success"><i class="bi bi-check-circle"></i> Archivo cargado:</small><br>
                <img src="${fileUrl}" class="document-preview img-thumbnail mt-1"
                     alt="${fileName}"
                     onclick="window.open('${fileUrl}', '_blank')"
                     style="max-width: 150px; cursor: pointer;"
                     onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22>Error</text></svg>'">
                <br>
                <a href="${fileUrl}" target="_blank" class="btn btn-sm btn-outline-primary mt-2">
                    <i class="bi bi-download"></i> Ver/Descargar
                </a>
            </div>
        `;
    } else if (isPdf) {
        previewElement.innerHTML = `
            <div class="alert alert-success mb-2">
                <i class="bi bi-file-pdf fs-4"></i> <strong>${fileName}</strong>
                <br>
                <a href="${fileUrl}" target="_blank" class="btn btn-sm btn-primary mt-2">
                    <i class="bi bi-eye"></i> Ver PDF
                </a>
            </div>
        `;
    } else {
        // Archivo genérico
        previewElement.innerHTML = `
            <div class="alert alert-success mb-2">
                <i class="bi bi-file-earmark fs-4"></i> <strong>${fileName}</strong>
                <br>
                <a href="${fileUrl}" target="_blank" class="btn btn-sm btn-primary mt-2">
                    <i class="bi bi-download"></i> Descargar
                </a>
            </div>
        `;
    }

    console.log('Archivo mostrado exitosamente');
}

/**
 * Guardar cliente (crear o editar)
 */
function saveClient() {
    const form = document.getElementById('clientForm');

    if (!form) {
        showAlert('error', 'Formulario no encontrado');
        return;
    }

    // Validar formulario HTML5
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }

    // Validar cuentas bancarias mínimas
    const validationResult = validateMinimumAccounts();
    if (!validationResult) {
        showAlert('error', 'Debes registrar al menos una cuenta en Soles (S/) y otra en Dólares ($)');
        document.getElementById('accountsValidationMessage')?.scrollIntoView({ behavior: 'smooth' });
        return;
    }

    // Validar duplicados
    if (!validateDuplicateAccounts()) {
        showAlert('error', 'Tienes cuentas duplicadas (mismo banco y misma moneda). Por favor, elimina los duplicados.');
        document.getElementById('duplicateAccountsMessage')?.scrollIntoView({ behavior: 'smooth' });
        return;
    }

    // Validar CCI para BBVA y SCOTIABANK
    const accountGroups = document.querySelectorAll('.bank-account-group');
    for (let group of accountGroups) {
        const index = group.dataset.accountIndex;
        const bank = document.getElementById(`bankName${index}`)?.value;
        const account = document.getElementById(`bankAccountNumber${index}`)?.value;

        if (bank && account && (bank === 'BBVA' || bank === 'SCOTIABANK') && account.length !== 20) {
            showAlert('error', `El CCI de ${bank} debe tener exactamente 20 dígitos`);
            return;
        }
    }

    const formData = new FormData(form);
    const clientData = {};

    // Construir objeto de datos (excluir archivos y cuentas bancarias por ahora)
    formData.forEach((value, key) => {
        if (value && key !== 'client_id' &&
            !key.includes('_front') && !key.includes('_back') &&
            !key.includes('ficha_ruc') &&
            !key.startsWith('origen') && !key.startsWith('bank') &&
            !key.startsWith('account') && !key.startsWith('currency')) {
            clientData[key] = value;
        }
    });

    // Normalizar campos a mayúsculas
    if (clientData.apellido_paterno) clientData.apellido_paterno = clientData.apellido_paterno.toUpperCase();
    if (clientData.apellido_materno) clientData.apellido_materno = clientData.apellido_materno.toUpperCase();
    if (clientData.nombres) clientData.nombres = clientData.nombres.toUpperCase();
    if (clientData.razon_social) clientData.razon_social = clientData.razon_social.toUpperCase();
    if (clientData.persona_contacto) clientData.persona_contacto = clientData.persona_contacto.toUpperCase();

    // Sanitizar teléfono
    if (clientData.phone) {
        clientData.phone = clientData.phone.replace(/\s*;\s*/g, ';').trim();
    }

    // Recolectar todas las cuentas bancarias activas
    const bankAccounts = [];
    accountGroups.forEach(group => {
        const index = group.dataset.accountIndex;
        const origen = document.getElementById(`origen${index}`)?.value;
        const bankName = document.getElementById(`bankName${index}`)?.value;
        const accountType = document.getElementById(`accountType${index}`)?.value;
        const currency = document.getElementById(`currency${index}`)?.value;
        const accountNumber = document.getElementById(`bankAccountNumber${index}`)?.value;

        // Solo agregar cuentas completas
        if (bankName && accountNumber && currency) {
            bankAccounts.push({
                origen: origen || '',
                bank_name: bankName,
                account_type: accountType || '',
                currency: currency,
                account_number: accountNumber
            });
        }
    });

    clientData.bank_accounts = bankAccounts;

    const clientId = document.getElementById('clientId').value;
    const isEditing = clientId !== '';

    const url = isEditing ? `/clients/api/update/${clientId}` : '/clients/api/create';
    const method = isEditing ? 'PUT' : 'POST';

    // Mostrar loading
    showLoading();

    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(clientData)
    })
    .then(response => response.json())
    .then(data => {
        hideLoading();

        if (data.success) {
            // Si hay archivos, subirlos
            const files = new FormData();
            let hasFiles = false;

            const docType = document.getElementById('documentType').value;

            if (docType === 'RUC') {
                const dniRepFront = document.getElementById('dniRepFront').files[0];
                const dniRepBack = document.getElementById('dniRepBack').files[0];
                const fichaRuc = document.getElementById('fichaRuc').files[0];

                if (dniRepFront) {
                    files.append('dni_representante_front', dniRepFront);
                    hasFiles = true;
                }
                if (dniRepBack) {
                    files.append('dni_representante_back', dniRepBack);
                    hasFiles = true;
                }
                if (fichaRuc) {
                    files.append('ficha_ruc', fichaRuc);
                    hasFiles = true;
                }
            } else {
                const dniFront = document.getElementById('dniFront').files[0];
                const dniBack = document.getElementById('dniBack').files[0];

                if (dniFront) {
                    files.append('dni_front', dniFront);
                    hasFiles = true;
                }
                if (dniBack) {
                    files.append('dni_back', dniBack);
                    hasFiles = true;
                }
            }

            if (hasFiles) {
                // Subir archivos
                uploadClientDocuments(data.client.id, files)
                    .then(() => {
                        showAlert('success', data.message);
                        setTimeout(() => location.reload(), 1500);
                    });
            } else {
                showAlert('success', data.message);
                setTimeout(() => location.reload(), 1500);
            }

            // Cerrar modal
            bootstrap.Modal.getInstance(document.getElementById('createClientModal')).hide();
        } else {
            showAlert('error', data.message);
        }
    })
    .catch(error => {
        hideLoading();
        console.error('Error:', error);
        showAlert('error', 'Error al guardar el cliente');
    });
}

/**
 * Subir documentos del cliente
 */
function uploadClientDocuments(clientId, files) {
    return fetch(`/clients/api/upload_documents/${clientId}`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCSRFToken()
        },
        body: files
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            throw new Error(data.message);
        }
        return data;
    });
}

/**
 * Cambiar estado del cliente
 */
function toggleClientStatus(clientId, currentStatus) {
    const newStatus = currentStatus === 'Activo' ? 'Inactivo' : 'Activo';
    const action = newStatus === 'Activo' ? 'activar' : 'desactivar';

    Swal.fire({
        title: '¿Está seguro?',
        text: `¿Desea ${action} este cliente?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: newStatus === 'Activo' ? '#28a745' : '#6c757d',
        cancelButtonColor: '#6c757d',
        confirmButtonText: `Sí, ${action}`,
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/clients/api/change_status/${clientId}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken()
                },
                body: JSON.stringify({ status: newStatus })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('success', data.message);

                    // Actualizar badge en la tabla
                    const row = document.querySelector(`tr[data-client-id="${clientId}"]`);
                    const badge = row.querySelector('.status-badge');
                    badge.className = `badge bg-${newStatus === 'Activo' ? 'success' : 'secondary'} status-badge`;
                    badge.textContent = newStatus;

                    // Actualizar botón
                    const btn = row.querySelector(`button[onclick*="toggleClientStatus"]`);
                    btn.className = `btn btn-${newStatus === 'Activo' ? 'secondary' : 'success'}`;
                    btn.innerHTML = `<i class="bi bi-${newStatus === 'Activo' ? 'x-circle' : 'check-circle'}"></i>`;
                    btn.setAttribute('onclick', `toggleClientStatus(${clientId}, '${newStatus}')`);
                    btn.title = newStatus === 'Activo' ? 'Desactivar' : 'Activar';
                } else {
                    showAlert('error', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('error', 'Error al cambiar el estado');
            });
        }
    });
}

/**
 * Eliminar cliente
 */
function deleteClient(clientId) {
    Swal.fire({
        title: '¿Está seguro?',
        text: 'Esta acción no se puede deshacer',
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sí, eliminar',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/clients/api/delete/${clientId}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': getCSRFToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('success', data.message);
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showAlert('error', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('error', 'Error al eliminar el cliente');
            });
        }
    });
}

/**
 * Exportar clientes a CSV
 */
function exportClients() {
    showLoading();

    fetch('/clients/api/export/csv')
        .then(response => {
            if (response.ok) {
                return response.blob();
            } else {
                throw new Error('Error al exportar');
            }
        })
        .then(blob => {
            hideLoading();

            // Crear link de descarga
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `clientes_qoricash_${new Date().toISOString().split('T')[0]}.csv`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            showAlert('success', 'Clientes exportados exitosamente');
        })
        .catch(error => {
            hideLoading();
            console.error('Error:', error);
            showAlert('error', 'Error al exportar los clientes');
        });
}

/**
 * Limpiar formulario al cerrar modal
 */
const createClientModal = document.getElementById('createClientModal');
if (createClientModal) {
    createClientModal.addEventListener('hidden.bs.modal', function () {
        const form = document.getElementById('clientForm');
        if (form) {
            form.reset();
        }

        const clientIdField = document.getElementById('clientId');
        if (clientIdField) clientIdField.value = '';

        const modalTitle = document.getElementById('modalTitle');
        if (modalTitle) modalTitle.innerHTML = '<i class="bi bi-person-plus"></i> Nuevo Cliente';

        const dniCeFields = document.getElementById('dniCeFields');
        const rucFields = document.getElementById('rucFields');
        if (dniCeFields) dniCeFields.style.display = 'none';
        if (rucFields) rucFields.style.display = 'none';

        const accountsValidationMessage = document.getElementById('accountsValidationMessage');
        const duplicateAccountsMessage = document.getElementById('duplicateAccountsMessage');
        if (accountsValidationMessage) accountsValidationMessage.style.display = 'none';
        if (duplicateAccountsMessage) duplicateAccountsMessage.style.display = 'none';

        // Habilitar campos
        const documentTypeField = document.getElementById('documentType');
        const dniField = document.getElementById('dni');
        if (documentTypeField) documentTypeField.disabled = false;
        if (dniField) dniField.disabled = false;

        // Remover restricciones de Trader
        const traderNote = document.getElementById('traderRestrictionNote');
        if (traderNote) {
            traderNote.remove();
        }

        // Habilitar todos los campos y remover estilos
        if (form) {
            const allInputs = form.querySelectorAll('input, select, textarea');
            allInputs.forEach(input => {
                input.disabled = false;
                input.readOnly = false;
                input.classList.remove('bg-light');
                input.style.cursor = '';
                input.style.display = '';
            });

            // Restaurar labels de archivos
            const fileInputs = ['dniFront', 'dniBack', 'dniRepFront', 'dniRepBack', 'fichaRuc'];
            fileInputs.forEach(inputId => {
                const input = document.getElementById(inputId);
                if (input) {
                    input.style.display = '';
                    const label = input.previousElementSibling;
                    if (label && label.tagName === 'LABEL') {
                        label.style.display = '';
                    }
                }
            });
        }

        // Limpiar previews de archivos
        const previews = [
            'dniFrontPreview', 'dniBackPreview',
            'dniRepFrontPreview', 'dniRepBackPreview', 'fichaRucPreview'
        ];
        previews.forEach(previewId => {
            const preview = document.getElementById(previewId);
            if (preview) preview.innerHTML = '';
        });

        // Resetear cuentas bancarias
        const bankAccountsContainer = document.getElementById('bankAccountsContainer');
        if (bankAccountsContainer) {
            bankAccountsContainer.innerHTML = '';
            bankAccountsCount = 0;
            initializeBankAccounts();
        }

        editingClientId = null;
    });
}

/**
 * Preview de archivos seleccionados
 */
document.getElementById('dniFront')?.addEventListener('change', function(e) {
    previewFile(e.target.files[0], 'dniFrontPreview');
});

document.getElementById('dniBack')?.addEventListener('change', function(e) {
    previewFile(e.target.files[0], 'dniBackPreview');
});

document.getElementById('dniRepFront')?.addEventListener('change', function(e) {
    previewFile(e.target.files[0], 'dniRepFrontPreview');
});

document.getElementById('dniRepBack')?.addEventListener('change', function(e) {
    previewFile(e.target.files[0], 'dniRepBackPreview');
});

document.getElementById('fichaRuc')?.addEventListener('change', function(e) {
    previewFile(e.target.files[0], 'fichaRucPreview');
});

/**
 * Mostrar preview del archivo
 */
function previewFile(file, previewElementId) {
    const previewElement = document.getElementById(previewElementId);

    if (!file) {
        previewElement.innerHTML = '';
        return;
    }

    const reader = new FileReader();

    reader.onload = function(e) {
        if (file.type.startsWith('image/')) {
            previewElement.innerHTML = `<img src="${e.target.result}" class="document-preview img-thumbnail" alt="Preview">`;
        } else if (file.type === 'application/pdf') {
            previewElement.innerHTML = `<div class="alert alert-info"><i class="bi bi-file-pdf"></i> ${file.name}</div>`;
        }
    };

    reader.readAsDataURL(file);
}

/**
 * Obtener CSRF Token
 */
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
}

/**
 * Mostrar alerta con SweetAlert2
 */
function showAlert(type, message) {
    const icon = type === 'success' ? 'success' : 'error';
    const title = type === 'success' ? '¡Éxito!' : 'Error';

    Swal.fire({
        icon: icon,
        title: title,
        text: message,
        timer: 3000,
        showConfirmButton: false,
        toast: true,
        position: 'top-end'
    });
}

/**
 * Mostrar loading
 */
function showLoading() {
    Swal.fire({
        title: 'Procesando...',
        allowOutsideClick: false,
        allowEscapeKey: false,
        showConfirmButton: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
}

/**
 * Ocultar loading
 */
function hideLoading() {
    Swal.close();
}

// ==========================================
// WEBSOCKET - ACTUALIZACIÓN EN TIEMPO REAL
// ==========================================

/**
 * Conexión WebSocket para actualizaciones en tiempo real
 */
if (typeof io !== 'undefined') {
    console.log('Inicializando WebSocket para clientes...');

    // Conectar al namespace /clients
    const socket = io('/clients');

    socket.on('connect', function() {
        console.log('✅ WebSocket conectado al servidor (clientes)');
    });

    socket.on('disconnect', function() {
        console.warn('⚠️ WebSocket desconectado del servidor');
    });

    socket.on('connect_error', function(error) {
        console.error('❌ Error de conexión WebSocket:', error);
    });

    // Evento: Cliente creado
    socket.on('client_created', function(data) {
        console.log('📬 Cliente creado:', data);

        // Mostrar notificación
        Swal.fire({
            icon: 'info',
            title: 'Nuevo Cliente',
            text: `${data.created_by} ha creado un nuevo cliente`,
            timer: 3000,
            toast: true,
            position: 'top-end',
            showConfirmButton: false
        });

        // Recargar la tabla si DataTable está disponible
        if ($.fn.DataTable && $.fn.DataTable.isDataTable('#clientsTable')) {
            // Opción 1: Recargar completamente la página (más simple y confiable)
            setTimeout(() => location.reload(), 1000);

            // Opción 2: Solo actualizar DataTable (comentada porque requiere más configuración)
            // $('#clientsTable').DataTable().ajax.reload(null, false);
        }
    });

    // Evento: Cliente actualizado
    socket.on('client_updated', function(data) {
        console.log('✏️ Cliente actualizado:', data);

        // Mostrar notificación
        Swal.fire({
            icon: 'info',
            title: 'Cliente Actualizado',
            text: `${data.updated_by} ha actualizado un cliente`,
            timer: 3000,
            toast: true,
            position: 'top-end',
            showConfirmButton: false
        });

        // Recargar la tabla
        if ($.fn.DataTable && $.fn.DataTable.isDataTable('#clientsTable')) {
            setTimeout(() => location.reload(), 1000);
        }
    });

    // Evento: Estado del cliente cambiado
    socket.on('client_status_changed', function(data) {
        console.log('🔄 Estado de cliente cambiado:', data);

        // Mostrar notificación
        const statusIcon = data.new_status === 'Activo' ? 'success' : 'warning';
        Swal.fire({
            icon: statusIcon,
            title: 'Estado Cambiado',
            text: `Cliente cambió de ${data.old_status} a ${data.new_status}`,
            timer: 3000,
            toast: true,
            position: 'top-end',
            showConfirmButton: false
        });

        // Actualizar el badge en la tabla si existe
        const row = document.querySelector(`tr[data-client-id="${data.client_id}"]`);
        if (row) {
            const badge = row.querySelector('.status-badge');
            if (badge) {
                badge.className = `badge bg-${data.new_status === 'Activo' ? 'success' : 'secondary'} status-badge`;
                badge.textContent = data.new_status;
            }

            // Actualizar botón de cambio de estado
            const btn = row.querySelector(`button[onclick*="toggleClientStatus"]`);
            if (btn) {
                btn.className = `btn btn-${data.new_status === 'Activo' ? 'secondary' : 'success'}`;
                btn.innerHTML = `<i class="bi bi-${data.new_status === 'Activo' ? 'x-circle' : 'check-circle'}"></i>`;
                btn.setAttribute('onclick', `toggleClientStatus(${data.client_id}, '${data.new_status}')`);
                btn.title = data.new_status === 'Activo' ? 'Desactivar' : 'Activar';
            }
        }
    });

    // Evento: Cliente eliminado
    socket.on('client_deleted', function(data) {
        console.log('🗑️ Cliente eliminado:', data);

        // Mostrar notificación
        Swal.fire({
            icon: 'warning',
            title: 'Cliente Eliminado',
            text: `${data.deleted_by} ha eliminado el cliente: ${data.client_name}`,
            timer: 3000,
            toast: true,
            position: 'top-end',
            showConfirmButton: false
        });

        // Eliminar la fila de la tabla
        const row = document.querySelector(`tr[data-client-id="${data.client_id}"]`);
        if (row) {
            row.style.transition = 'opacity 0.5s';
            row.style.opacity = '0';
            setTimeout(() => {
                row.remove();
                // Recalcular numeración si es necesario
                if ($.fn.DataTable && $.fn.DataTable.isDataTable('#clientsTable')) {
                    $('#clientsTable').DataTable().row(row).remove().draw();
                }
            }, 500);
        }
    });

    console.log('✅ Event listeners de WebSocket configurados');
} else {
    console.warn('⚠️ Socket.IO no está disponible. Las actualizaciones en tiempo real no funcionarán.');
}

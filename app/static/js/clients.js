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
        showNotification('error', `Máximo ${MAX_ACCOUNTS} cuentas permitidas`);
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
                        <option value="OTROS">OTROS</option>
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
 * Validar cuentas duplicadas EXACTAS (banco + tipo + número + moneda)
 * ACTUALIZADO: Ahora permite múltiples cuentas del mismo banco en la misma moneda
 * Solo rechaza si TODA la información es idéntica
 */
function validateDuplicateAccounts() {
    const accounts = [];
    const accountGroups = document.querySelectorAll('.bank-account-group');

    accountGroups.forEach(group => {
        const index = group.dataset.accountIndex;
        const bank = document.getElementById(`bankName${index}`)?.value;
        const accountType = document.getElementById(`accountType${index}`)?.value;
        const accountNumber = document.getElementById(`bankAccountNumber${index}`)?.value;
        const currency = document.getElementById(`currency${index}`)?.value;

        // Solo validar si todos los campos están completos
        if (bank && accountType && accountNumber && currency) {
            accounts.push({
                bank,
                accountType,
                accountNumber: accountNumber.trim(),
                currency,
                index
            });
        }
    });

    // Buscar duplicados EXACTOS (toda la información idéntica)
    const duplicates = [];
    for (let i = 0; i < accounts.length; i++) {
        for (let j = i + 1; j < accounts.length; j++) {
            if (accounts[i].bank === accounts[j].bank &&
                accounts[i].accountType === accounts[j].accountType &&
                accounts[i].accountNumber === accounts[j].accountNumber &&
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
    const upperCaseInputs = document.querySelectorAll('.text-uppercase-input, .text-uppercase-field');
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

    if (selectedBank === 'BBVA' || selectedBank === 'SCOTIABANK' || selectedBank === 'OTROS') {
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
 * Función helper para desbloquear campos bancarios para Trader
 */
function unlockBankFields() {
    console.log('Desbloqueando campos bancarios para Trader...');

    const form = document.getElementById('clientForm');
    if (!form) return;

    // Seleccionar todos los campos dentro del contenedor de cuentas bancarias
    const bankContainer = document.getElementById('bankAccountsContainer');
    if (!bankContainer) {
        console.warn('Contenedor de cuentas bancarias no encontrado');
        return;
    }

    // Desbloquear TODOS los campos dentro del contenedor de cuentas bancarias
    const bankFields = bankContainer.querySelectorAll('input, select, textarea, button');
    bankFields.forEach(field => {
        field.disabled = false;
        field.readOnly = false;
        field.classList.remove('bg-light');
        field.style.backgroundColor = '';
        field.style.cursor = '';
        field.style.opacity = '1';
        field.style.pointerEvents = '';
        console.log('Campo desbloqueado:', field.id || field.name || field.tagName);
    });

    // Asegurar que el botón "Agregar Cuenta Bancaria" esté habilitado
    const addBtn = document.getElementById('addBankAccountBtn');
    if (addBtn) {
        addBtn.disabled = false;
        addBtn.style.opacity = '1';
        addBtn.style.cursor = 'pointer';
        addBtn.style.pointerEvents = 'auto';
        console.log('Botón Agregar Cuenta habilitado');
    }
}

/**
 * Aplicar restricciones por rol - TRADER SOLO EDITA CUENTAS BANCARIAS
 *
 * El rol Trader SOLO puede editar la sección de cuentas bancarias.
 * Todos los demás campos están en modo lectura.
 */
function applyRoleRestrictions(role) {
    console.log('Aplicando restricciones para rol:', role);

    if (role !== 'Trader') {
        console.log('No es Trader, permitir todo');
        return;
    }

    // IMPORTANTE: Solo aplicar restricciones si está EDITANDO, NO al crear
    const clientId = document.getElementById('clientId')?.value;
    const isEditing = clientId && clientId.trim() !== '';

    if (!isEditing) {
        console.log('✅ Trader CREANDO cliente - Permitir todos los campos');
        return; // No aplicar restricciones al crear
    }

    console.log('🔒 Trader EDITANDO cliente - Bloqueando campos excepto cuentas bancarias y documentos...');

    const form = document.getElementById('clientForm');
    if (!form) {
        console.error('Formulario no encontrado');
        return;
    }

    // PASO 1: Bloquear TODOS los campos del formulario primero
    const allFields = form.querySelectorAll('input, select, textarea');
    console.log('Total de campos encontrados:', allFields.length);

    allFields.forEach(field => {
        // No bloquear campos de archivos (documentos)
        if (field.type === 'file') {
            console.log('Campo de archivo detectado, NO se bloqueará:', field.id);
            return; // Saltar este campo, mantenerlo habilitado
        }

        field.disabled = true;
        field.readOnly = true;
        field.classList.add('bg-light');
        field.style.backgroundColor = '#e9ecef';
        field.style.cursor = 'not-allowed';
        field.style.opacity = '0.7';
    });

    // PASO 2: Desbloquear SOLO los campos de cuentas bancarias
    unlockBankFields();

    // PASO 3: Mantener visibles las secciones de documentos para que el Trader pueda subirlos
    // NO ocultar las secciones de documentos, solo deshabilitar otros campos
    console.log('Secciones de documentos permanecen visibles para subida de archivos')

    // PASO 3: Configurar MutationObserver para desbloquear campos bancarios nuevos
    const bankAccountsContainer = document.getElementById('bankAccountsContainer');
    if (bankAccountsContainer) {
        // Desconectar observer anterior si existe
        if (window.bankAccountsObserver) {
            window.bankAccountsObserver.disconnect();
        }

        // Crear nuevo observer
        window.bankAccountsObserver = new MutationObserver(function(mutations) {
            console.log('MutationObserver detectó cambios en cuentas bancarias');
            // Usar setTimeout para asegurar que los elementos están completamente renderizados
            setTimeout(() => {
                unlockBankFields();
            }, 50);
        });

        window.bankAccountsObserver.observe(bankAccountsContainer, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['disabled', 'readonly']
        });

        console.log('MutationObserver configurado para cuentas bancarias');
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

                // Persona de Contacto para RUC
                if (client.document_type === 'RUC' && client.persona_contacto) {
                    html += `<div class="col-md-12 mt-2"><strong>Persona de Contacto:</strong> ${client.persona_contacto}</div>`;
                }

                // Dirección
                if (client.full_address) {
                    html += '<div class="col-md-12 mt-4"><h6 class="border-bottom pb-2 mb-3">Dirección</h6></div>';
                    html += `<div class="col-md-12">${client.full_address}</div>`;
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
                showNotification('error', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('error', 'Error al cargar los datos del cliente');
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
                const departamentoField = document.getElementById('departamento');
                const provinciaField = document.getElementById('provincia');
                const distritoField = document.getElementById('distrito');

                if (direccionField) direccionField.value = client.direccion || '';

                // Cargar ubicaciones en cascada si existen datos
                if (client.departamento) {
                    // Esperar a que los departamentos estén cargados
                    setTimeout(async () => {
                        if (departamentoField) {
                            departamentoField.value = client.departamento;
                            await loadProvincias();

                            if (client.provincia && provinciaField) {
                                provinciaField.value = client.provincia;
                                await loadDistritos();

                                if (client.distrito && distritoField) {
                                    distritoField.value = client.distrito;
                                }
                            }
                        }
                    }, 300);
                }

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

                // Actualizar sección de Validación OC
                if (typeof currentUserRole !== 'undefined') {
                    toggleValidationOcSection(currentUserRole);
                    updateValidationOcStatus(client.validation_oc_url);
                }

                // Mostrar modal
                const modalElement = document.getElementById('createClientModal');
                if (modalElement) {
                    const modal = new bootstrap.Modal(modalElement);
                    modal.show();

                    // Aplicar restricciones de rol después de que el modal se muestre
                    if (typeof currentUserRole !== 'undefined') {
                        // Esperar un momento para que el modal esté completamente renderizado
                        setTimeout(() => {
                            applyRoleRestrictions(currentUserRole);
                        }, 100);
                    }
                }
            } else {
                showNotification('error', data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('error', 'Error al cargar los datos del cliente');
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
 * REFACTORIZADO: Manejo correcto de permisos para Trader
 */
function saveClient() {
    // ============================================
    // PROTECCIÓN CONTRA DOBLE CLIC
    // ============================================
    if (window.isSavingClient) {
        console.warn('🚫 BLOQUEADO: Ya hay una operación de guardado en proceso');
        return;
    }

    window.isSavingClient = true;

    // Deshabilitar botón inmediatamente
    const $saveBtn = $('#btnSaveClient');
    const originalBtnText = $saveBtn.html();
    $saveBtn.prop('disabled', true)
            .addClass('disabled')
            .html('<span class="spinner-border spinner-border-sm me-2"></span>Guardando...');

    const form = document.getElementById('clientForm');

    if (!form) {
        showNotification('error', 'Formulario no encontrado');
        // Restaurar botón en caso de error
        window.isSavingClient = false;
        $saveBtn.prop('disabled', false).removeClass('disabled').html(originalBtnText);
        return;
    }

    // Función helper para restaurar el botón en caso de error de validación
    const restoreButton = () => {
        window.isSavingClient = false;
        $saveBtn.prop('disabled', false).removeClass('disabled').html(originalBtnText);
    };

    // Validar formulario HTML5
    if (!form.checkValidity()) {
        form.reportValidity();
        restoreButton();
        return;
    }

    // Validar cuentas bancarias mínimas
    const validationResult = validateMinimumAccounts();
    if (!validationResult) {
        showNotification('error', 'Debes registrar al menos una cuenta en Soles (S/) y otra en Dólares ($)');
        document.getElementById('accountsValidationMessage')?.scrollIntoView({ behavior: 'smooth' });
        restoreButton();
        return;
    }

    // Validar duplicados
    if (!validateDuplicateAccounts()) {
        showNotification('error', 'Tienes cuentas duplicadas (mismo banco y misma moneda). Por favor, elimina los duplicados.');
        document.getElementById('duplicateAccountsMessage')?.scrollIntoView({ behavior: 'smooth' });
        restoreButton();
        return;
    }

    // Validar CCI para BBVA y SCOTIABANK
    const accountGroups = document.querySelectorAll('.bank-account-group');
    for (let group of accountGroups) {
        const index = group.dataset.accountIndex;
        const bank = document.getElementById(`bankName${index}`)?.value;
        const account = document.getElementById(`bankAccountNumber${index}`)?.value;

        if (bank && account && (bank === 'BBVA' || bank === 'SCOTIABANK') && account.length !== 20) {
            showNotification('error', `El CCI de ${bank} debe tener exactamente 20 dígitos`);
            restoreButton();
            return;
        }
    }

    const clientId = document.getElementById('clientId').value;
    const isEditing = clientId !== '';
    const isTrader = (typeof window.currentUserRole !== 'undefined' && window.currentUserRole === 'Trader');

    // ============================================
    // ESTRATEGIA DIFERENTE PARA TRADER EN EDICIÓN
    // ============================================
    if (isTrader && isEditing) {
        console.log('🔄 Trader editando cliente - Solo actualizar cuentas bancarias y documentos');

        // Paso 1: Actualizar solo cuentas bancarias
        const bankAccounts = [];
        accountGroups.forEach(group => {
            const index = group.dataset.accountIndex;
            const origen = document.getElementById(`origen${index}`)?.value;
            const bankName = document.getElementById(`bankName${index}`)?.value;
            const accountType = document.getElementById(`accountType${index}`)?.value;
            const currency = document.getElementById(`currency${index}`)?.value;
            const accountNumber = document.getElementById(`bankAccountNumber${index}`)?.value;

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

        const traderData = {
            bank_accounts: bankAccounts
        };

        // LOG DETALLADO para debugging
        console.log('📤 Datos que se enviarán al backend:');
        console.log('   - Cliente ID:', clientId);
        console.log('   - Rol:', window.currentUserRole);
        console.log('   - Campos en traderData:', Object.keys(traderData));
        console.log('   - bank_accounts:', JSON.stringify(bankAccounts, null, 2));

        showLoading();

        // Actualizar cuentas bancarias
        fetch(`/clients/api/update/${clientId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken()
            },
            body: JSON.stringify(traderData)
        })
        .then(response => {
            console.log('📥 Respuesta del servidor:', response.status, response.statusText);
            if (!response.ok) {
                return response.json().then(errorData => {
                    console.error('❌ Error del servidor:', errorData);
                    throw new Error(errorData.message || `Error ${response.status}: ${response.statusText}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('📥 Data recibida:', data);
            if (data.success) {
                console.log('✅ Cuentas bancarias actualizadas');

                // Paso 2: Subir documentos si hay archivos nuevos
                const files = new FormData();
                let hasFiles = false;
                const docType = document.getElementById('documentType').value;

                if (docType === 'RUC') {
                    const dniRepFront = document.getElementById('dniRepFront')?.files[0];
                    const dniRepBack = document.getElementById('dniRepBack')?.files[0];
                    const fichaRuc = document.getElementById('fichaRuc')?.files[0];

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
                    const dniFront = document.getElementById('dniFront')?.files[0];
                    const dniBack = document.getElementById('dniBack')?.files[0];

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
                    console.log('📄 Subiendo documentos...');
                    return uploadClientDocuments(clientId, files);
                } else {
                    console.log('ℹ️ No hay documentos nuevos para subir');
                    return Promise.resolve({ success: true });
                }
            } else {
                throw new Error(data.message || 'Error al actualizar cuentas bancarias');
            }
        })
        .then(() => {
            hideLoading();
            window.isSavingClient = false;  // Restaurar flag
            showNotification('success', 'Cliente actualizado exitosamente');
            bootstrap.Modal.getInstance(document.getElementById('createClientModal')).hide();
            setTimeout(() => location.reload(), 1500);
        })
        .catch(error => {
            hideLoading();
            restoreButton();  // Restaurar botón en caso de error
            console.error('Error:', error);
            showNotification('error', error.message || 'Error al actualizar el cliente');
        });

        return; // Salir de la función para Trader
    }

    // ============================================
    // FLUJO NORMAL PARA OTROS ROLES O CREACIÓN
    // ============================================
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

    const url = isEditing ? `/clients/api/update/${clientId}` : '/clients/api/create';
    const method = isEditing ? 'PUT' : 'POST';

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
                uploadClientDocuments(data.client.id, files)
                    .then(() => {
                        hideLoading();
                        window.isSavingClient = false;  // Restaurar flag
                        showNotification('success', data.message);
                        bootstrap.Modal.getInstance(document.getElementById('createClientModal')).hide();
                        setTimeout(() => location.reload(), 1500);
                    })
                    .catch(error => {
                        hideLoading();
                        restoreButton();  // Restaurar botón en caso de error
                        showNotification('error', error.message || 'Error al procesar documentos del cliente');
                    });
            } else {
                hideLoading();
                window.isSavingClient = false;  // Restaurar flag
                showNotification('success', data.message);
                bootstrap.Modal.getInstance(document.getElementById('createClientModal')).hide();
                setTimeout(() => location.reload(), 1500);
            }
        } else {
            restoreButton();  // Restaurar botón en caso de error
            showNotification('error', data.message);
        }
    })
    .catch(error => {
        hideLoading();
        restoreButton();  // Restaurar botón en caso de error
        console.error('Error:', error);
        showNotification('error', 'Error al guardar el cliente');
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
                    showNotification('success', data.message);

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
                    showNotification('error', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('error', 'Error al cambiar el estado');
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
                    showNotification('success', data.message);
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showNotification('error', data.message);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('error', 'Error al eliminar el cliente');
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

            showNotification('success', 'Clientes exportados exitosamente');
        })
        .catch(error => {
            hideLoading();
            console.error('Error:', error);
            showNotification('error', 'Error al exportar los clientes');
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
function showNotification(type, message) {
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

    // Usar el namespace por defecto (ya configurado globalmente)
    const socket = io();

    socket.on('connect', function() {
        console.log('[OK] WebSocket conectado al servidor (clientes)');
    });

    socket.on('disconnect', function() {
        console.warn('[WARNING] WebSocket desconectado del servidor');
    });

    socket.on('connect_error', function(error) {
        console.error('[ERROR] Error de conexión WebSocket:', error);
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

    console.log('[OK] Event listeners de WebSocket configurados');
} else {
    console.warn('[WARNING] Socket.IO no está disponible. Las actualizaciones en tiempo real no funcionarán.');
}

/**
 * ===========================================
 * VALIDACIÓN OFICIAL DE CUMPLIMIENTO (OC)
 * ===========================================
 */

/**
 * Mostrar/Ocultar sección de Validación OC según rol del usuario
 */
function toggleValidationOcSection(userRole) {
    const section = document.getElementById('validationOcSection');
    if (!section) return;

    // Solo mostrar para Master y Operador
    if (userRole === 'Master' || userRole === 'Operador') {
        section.style.display = 'block';
    } else {
        section.style.display = 'none';
    }
}

/**
 * Actualizar estado de validación OC
 */
function updateValidationOcStatus(validationOcUrl) {
    const statusDiv = document.getElementById('validationOcStatus');
    const uploadBtn = document.getElementById('uploadValidationOcBtn');
    const fileInput = document.getElementById('validationOcFile');
    const preview = document.getElementById('validationOcPreview');

    if (!statusDiv) return;

    if (validationOcUrl) {
        // Ya existe documento de validación
        statusDiv.innerHTML = `
            <div class="alert alert-success">
                <i class="bi bi-check-circle-fill"></i>
                <strong>Validación completada</strong>
                <p class="mb-0">El documento de validación OC ha sido cargado exitosamente.</p>
            </div>
        `;

        // Mostrar archivo existente
        if (preview) {
            const isPdf = validationOcUrl.match(/\.pdf$/i);
            const isDoc = validationOcUrl.match(/\.(doc|docx)$/i);

            if (isPdf || isDoc) {
                preview.innerHTML = `
                    <div class="alert alert-info mt-2">
                        <i class="bi bi-file-earmark-pdf fs-4"></i> <strong>Documento de Validación OC</strong>
                        <br>
                        <a href="${validationOcUrl}" target="_blank" class="btn btn-sm btn-primary mt-2">
                            <i class="bi bi-eye"></i> Ver Documento
                        </a>
                    </div>
                `;
            } else {
                preview.innerHTML = `
                    <div class="alert alert-info mt-2">
                        <img src="${validationOcUrl}" class="img-thumbnail" style="max-height: 150px; cursor: pointer;" onclick="window.open('${validationOcUrl}', '_blank')">
                        <br>
                        <a href="${validationOcUrl}" target="_blank" class="btn btn-sm btn-primary mt-2">
                            <i class="bi bi-download"></i> Ver/Descargar
                        </a>
                    </div>
                `;
            }
        }

        // Ocultar botón de subida y deshabilitar input
        if (uploadBtn) uploadBtn.style.display = 'none';
        if (fileInput) fileInput.disabled = true;
    } else {
        // No existe documento de validación
        statusDiv.innerHTML = `
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle-fill"></i>
                <strong>Validación pendiente</strong>
                <p class="mb-0">Aún no se ha cargado el documento de validación del Oficial de Cumplimiento.</p>
            </div>
        `;

        // Mostrar botón de subida si hay archivo seleccionado
        if (fileInput) {
            fileInput.disabled = false;
            fileInput.addEventListener('change', function() {
                if (this.files.length > 0) {
                    if (uploadBtn) uploadBtn.style.display = 'block';
                } else {
                    if (uploadBtn) uploadBtn.style.display = 'none';
                }
            });
        }
    }
}

/**
 * Subir documento de validación OC
 */
function uploadValidationOc() {
    const fileInput = document.getElementById('validationOcFile');
    const file = fileInput ? fileInput.files[0] : null;

    if (!file) {
        showNotification('error', 'Por favor selecciona un archivo');
        return;
    }

    if (!editingClientId) {
        showNotification('error', 'No se ha identificado el cliente');
        return;
    }

    // Validar tamaño (máximo 10MB)
    if (file.size > 10 * 1024 * 1024) {
        showNotification('error', 'El archivo no debe superar 10MB');
        return;
    }

    const formData = new FormData();
    formData.append('validation_oc_file', file);

    const uploadBtn = document.getElementById('uploadValidationOcBtn');
    if (uploadBtn) {
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Subiendo...';
    }

    fetch(`/clients/api/upload_validation_oc/${editingClientId}`, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('success', 'Documento de validación OC subido correctamente');
            // Actualizar estado
            updateValidationOcStatus(data.validation_oc_url);
        } else {
            showNotification('error', data.message || 'Error al subir el documento');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('error', 'Error al subir el documento de validación');
    })
    .finally(() => {
        if (uploadBtn) {
            uploadBtn.disabled = false;
            uploadBtn.innerHTML = '<i class="bi bi-upload"></i> Subir Documento de Validación';
        }
    });
}

/* ============================================
 * FUNCIONES DE REASIGNACIÓN DE CLIENTES
 * ============================================ */

let activeTraders = []; // Cache de traders activos

/**
 * Cargar traders activos desde el servidor
 */
async function loadActiveTraders() {
    try {
        const response = await fetch('/clients/api/traders/active', {
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json();

        if (data.success) {
            activeTraders = data.traders;
            return activeTraders;
        } else {
            showNotification('error', 'Error al cargar traders');
            return [];
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('error', 'Error al cargar traders');
        return [];
    }
}

/**
 * Mostrar modal de reasignación individual
 */
async function showReassignModal(clientId) {
    // Cargar traders
    const traders = await loadActiveTraders();

    // Obtener datos del cliente
    const row = document.querySelector(`tr[data-client-id="${clientId}"]`);
    if (!row) {
        showNotification('error', 'Cliente no encontrado');
        return;
    }

    const clientName = row.querySelector('td strong').textContent;
    const currentTraderBadge = row.querySelector('td .badge.bg-secondary');
    const currentTrader = currentTraderBadge ? currentTraderBadge.textContent.trim() : 'N/A';

    // Llenar modal
    document.getElementById('reassignClientId').value = clientId;
    document.getElementById('reassignClientName').textContent = clientName;
    document.getElementById('reassignCurrentTrader').textContent = currentTrader;

    // Llenar select de traders
    const select = document.getElementById('reassignNewTrader');
    select.innerHTML = '<option value="">Seleccione un trader...</option>';

    traders.forEach(trader => {
        const option = document.createElement('option');
        option.value = trader.id;
        option.textContent = `${trader.username} (${trader.total_clients} clientes)`;
        select.appendChild(option);
    });

    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('reassignClientModal'));
    modal.show();
}

/**
 * Confirmar reasignación individual
 */
async function confirmReassignClient() {
    const clientId = document.getElementById('reassignClientId').value;
    const newTraderId = document.getElementById('reassignNewTrader').value;

    if (!newTraderId) {
        showNotification('error', 'Debe seleccionar un trader');
        return;
    }

    try {
        const response = await fetch(`/clients/api/reassign/${clientId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_trader_id: parseInt(newTraderId) })
        });

        const data = await response.json();

        if (data.success) {
            showNotification('success', data.message);

            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('reassignClientModal'));
            modal.hide();

            // Recargar página para actualizar la tabla
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showNotification('error', data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('error', 'Error al reasignar cliente');
    }
}

/**
 * Mostrar modal de reasignación masiva
 */
async function showBulkReassignModal() {
    // Cargar traders
    const traders = await loadActiveTraders();

    // Llenar selects
    const selects = ['bulkNewTrader', 'bulkSourceTrader', 'bulkTargetTrader'];
    selects.forEach(selectId => {
        const select = document.getElementById(selectId);
        select.innerHTML = '<option value="">Seleccione un trader...</option>';

        traders.forEach(trader => {
            const option = document.createElement('option');
            option.value = trader.id;
            option.textContent = `${trader.username} (${trader.total_clients} clientes)`;
            option.dataset.clientCount = trader.total_clients;
            select.appendChild(option);
        });
    });

    // Actualizar contador de seleccionados
    updateBulkSelectedCount();

    // Event listener para mostrar info del trader origen
    document.getElementById('bulkSourceTrader').addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        const clientCount = selectedOption.dataset.clientCount || 0;
        document.getElementById('bulkSourceTraderInfo').textContent =
            clientCount > 0 ? `Este trader tiene ${clientCount} cliente(s)` : '';
    });

    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('bulkReassignModal'));
    modal.show();
}

/**
 * Actualizar contador de clientes seleccionados
 */
function updateBulkSelectedCount() {
    const checkboxes = document.querySelectorAll('.client-checkbox:checked');
    const count = checkboxes.length;
    const countElement = document.getElementById('bulkSelectedCount');

    if (count > 0) {
        countElement.textContent = `${count} cliente(s) seleccionado(s)`;
        countElement.classList.remove('text-muted');
        countElement.classList.add('text-primary', 'fw-bold');
    } else {
        countElement.textContent = 'No hay clientes seleccionados';
        countElement.classList.remove('text-primary', 'fw-bold');
        countElement.classList.add('text-muted');
    }
}

/**
 * Reasignar clientes seleccionados
 */
async function confirmBulkReassignSelected() {
    const checkboxes = document.querySelectorAll('.client-checkbox:checked');
    const clientIds = Array.from(checkboxes).map(cb => parseInt(cb.value));
    const newTraderId = document.getElementById('bulkNewTrader').value;

    if (clientIds.length === 0) {
        showNotification('error', 'Debe seleccionar al menos un cliente');
        return;
    }

    if (!newTraderId) {
        showNotification('error', 'Debe seleccionar un trader');
        return;
    }

    if (!confirm(`¿Está seguro de reasignar ${clientIds.length} cliente(s)?`)) {
        return;
    }

    try {
        const response = await fetch('/clients/api/reassign/bulk', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                client_ids: clientIds,
                new_trader_id: parseInt(newTraderId)
            })
        });

        const data = await response.json();

        if (data.success || (data.results && data.results.success.length > 0)) {
            showNotification('success', data.message);

            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('bulkReassignModal'));
            modal.hide();

            // Recargar página
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showNotification('error', data.message);
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('error', 'Error al reasignar clientes');
    }
}

/**
 * Reasignar todos los clientes de un trader
 */
async function confirmBulkReassignFromTrader() {
    const sourceTraderId = document.getElementById('bulkSourceTrader').value;
    const targetTraderId = document.getElementById('bulkTargetTrader').value;

    if (!sourceTraderId) {
        showNotification('error', 'Debe seleccionar el trader origen');
        return;
    }

    if (!targetTraderId) {
        showNotification('error', 'Debe seleccionar el trader destino');
        return;
    }

    if (sourceTraderId === targetTraderId) {
        showNotification('error', 'El trader origen y destino no pueden ser el mismo');
        return;
    }

    try {
        // Obtener clientes del trader origen
        const response = await fetch(`/clients/api/trader/${sourceTraderId}/clients`, {
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json();

        if (!data.success) {
            showNotification('error', 'Error al obtener clientes del trader');
            return;
        }

        if (data.total === 0) {
            showNotification('warning', 'El trader seleccionado no tiene clientes');
            return;
        }

        const clientIds = data.clients.map(c => c.id);

        if (!confirm(`¿Está seguro de reasignar TODOS los ${data.total} cliente(s) del trader seleccionado?`)) {
            return;
        }

        // Realizar reasignación masiva
        const reassignResponse = await fetch('/clients/api/reassign/bulk', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                client_ids: clientIds,
                new_trader_id: parseInt(targetTraderId)
            })
        });

        const reassignData = await reassignResponse.json();

        if (reassignData.success || (reassignData.results && reassignData.results.success.length > 0)) {
            showNotification('success', reassignData.message);

            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('bulkReassignModal'));
            modal.hide();

            // Recargar página
            setTimeout(() => {
                location.reload();
            }, 1500);
        } else {
            showNotification('error', reassignData.message);
        }
    } catch (error) {
        console.error('Error:', error);
        showNotification('error', 'Error al reasignar clientes');
    }
}

/**
 * Inicializar funcionalidad de selección de todos los checkboxes
 */
document.addEventListener('DOMContentLoaded', function() {
    const selectAllCheckbox = document.getElementById('selectAllClients');

    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const checkboxes = document.querySelectorAll('.client-checkbox');
            checkboxes.forEach(cb => {
                cb.checked = this.checked;
            });
            updateBulkSelectedCount();
        });
    }

    // Event listener para checkboxes individuales
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('client-checkbox')) {
            updateBulkSelectedCount();

            // Actualizar estado del checkbox "seleccionar todos"
            const allCheckboxes = document.querySelectorAll('.client-checkbox');
            const checkedCheckboxes = document.querySelectorAll('.client-checkbox:checked');
            const selectAll = document.getElementById('selectAllClients');

            if (selectAll) {
                selectAll.checked = allCheckboxes.length === checkedCheckboxes.length;
            }
        }
    });

    // Event listener para limpiar campos PEP cuando se cierra el modal
    const createClientModal = document.getElementById('createClientModal');
    if (createClientModal) {
        createClientModal.addEventListener('hidden.bs.modal', function () {
            // Limpiar checkbox y campos PEP
            const isPepCheckbox = document.getElementById('isPepCheckbox');
            if (isPepCheckbox) {
                isPepCheckbox.checked = false;
                togglePepFields(); // Ocultar campos PEP
            }

            // Limpiar valores de campos PEP
            const pepFields = ['pepType', 'pepPosition', 'pepEntity', 'pepDesignationDate', 'pepEndDate', 'pepNotes'];
            pepFields.forEach(fieldId => {
                const field = document.getElementById(fieldId);
                if (field) {
                    field.value = '';
                }
            });
        });
    }

    // Cargar departamentos al iniciar
    loadDepartamentos();
});

/**
 * ===========================================
 * GESTIÓN DE UBICACIONES DE PERÚ (CASCADA)
 * ===========================================
 */

let peruLocationsData = null;

/**
 * Cargar datos de ubicaciones de Perú
 */
async function loadPeruLocations() {
    if (peruLocationsData) {
        return peruLocationsData;
    }

    try {
        const response = await fetch('/static/data/peru_locations.json');
        peruLocationsData = await response.json();
        return peruLocationsData;
    } catch (error) {
        console.error('Error al cargar datos de ubicaciones:', error);
        return null;
    }
}

/**
 * Cargar departamentos en el selector
 */
async function loadDepartamentos() {
    const data = await loadPeruLocations();
    if (!data || !data.departamentos) return;

    const departamentoSelect = document.getElementById('departamento');
    if (!departamentoSelect) return;

    // Guardar el valor actual si existe (para modo edición)
    const currentValue = departamentoSelect.value;

    // Limpiar opciones excepto la primera
    departamentoSelect.innerHTML = '<option value="">Seleccionar...</option>';

    // Agregar departamentos
    data.departamentos.forEach(dep => {
        const option = document.createElement('option');
        option.value = dep.nombre;
        option.textContent = dep.nombre;
        departamentoSelect.appendChild(option);
    });

    // Restaurar valor si existe
    if (currentValue) {
        departamentoSelect.value = currentValue;
        loadProvincias();
    }
}

/**
 * Cargar provincias según el departamento seleccionado
 */
async function loadProvincias() {
    const data = await loadPeruLocations();
    if (!data || !data.departamentos) return;

    const departamentoSelect = document.getElementById('departamento');
    const provinciaSelect = document.getElementById('provincia');
    const distritoSelect = document.getElementById('distrito');

    if (!departamentoSelect || !provinciaSelect || !distritoSelect) return;

    const departamentoValue = departamentoSelect.value;

    // Guardar valor actual de provincia (para modo edición)
    const currentProvinciaValue = provinciaSelect.value;

    // Limpiar provincias y distritos
    provinciaSelect.innerHTML = '<option value="">Seleccionar...</option>';
    distritoSelect.innerHTML = '<option value="">Seleccionar...</option>';
    distritoSelect.disabled = true;

    if (!departamentoValue) {
        provinciaSelect.disabled = true;
        return;
    }

    // Buscar departamento
    const departamento = data.departamentos.find(d => d.nombre === departamentoValue);
    if (!departamento || !departamento.provincias) {
        provinciaSelect.disabled = true;
        return;
    }

    // Habilitar selector de provincias
    provinciaSelect.disabled = false;

    // Agregar provincias
    departamento.provincias.forEach(prov => {
        const option = document.createElement('option');
        option.value = prov.nombre;
        option.textContent = prov.nombre;
        provinciaSelect.appendChild(option);
    });

    // Restaurar valor si existe
    if (currentProvinciaValue) {
        provinciaSelect.value = currentProvinciaValue;
        loadDistritos();
    }
}

/**
 * Cargar distritos según la provincia seleccionada
 */
async function loadDistritos() {
    const data = await loadPeruLocations();
    if (!data || !data.departamentos) return;

    const departamentoSelect = document.getElementById('departamento');
    const provinciaSelect = document.getElementById('provincia');
    const distritoSelect = document.getElementById('distrito');

    if (!departamentoSelect || !provinciaSelect || !distritoSelect) return;

    const departamentoValue = departamentoSelect.value;
    const provinciaValue = provinciaSelect.value;

    // Guardar valor actual de distrito (para modo edición)
    const currentDistritoValue = distritoSelect.value;

    // Limpiar distritos
    distritoSelect.innerHTML = '<option value="">Seleccionar...</option>';

    if (!departamentoValue || !provinciaValue) {
        distritoSelect.disabled = true;
        return;
    }

    // Buscar departamento y provincia
    const departamento = data.departamentos.find(d => d.nombre === departamentoValue);
    if (!departamento || !departamento.provincias) {
        distritoSelect.disabled = true;
        return;
    }

    const provincia = departamento.provincias.find(p => p.nombre === provinciaValue);
    if (!provincia || !provincia.distritos) {
        distritoSelect.disabled = true;
        return;
    }

    // Habilitar selector de distritos
    distritoSelect.disabled = false;

    // Agregar distritos
    provincia.distritos.forEach(dist => {
        const option = document.createElement('option');
        option.value = dist;
        option.textContent = dist;
        distritoSelect.appendChild(option);
    });

    // Restaurar valor si existe
    if (currentDistritoValue) {
        distritoSelect.value = currentDistritoValue;
    }
}

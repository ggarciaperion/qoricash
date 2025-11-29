/**
 * QoriCash Trading V2 - Users Management JavaScript
 */

/**
 * Crear usuario
 */
function createUser() {
    const formData = {
        username: $('input[name="username"]').val().trim(),
        email: $('input[name="email"]').val().trim(),
        dni: $('input[name="dni"]').val().trim(),
        password: $('input[name="password"]').val(),
        role: $('select[name="role"]').val()
    };

    // Validar
    if (!formData.username || !formData.email || !formData.dni || !formData.password || !formData.role) {
        showNotification('Completa todos los campos', 'warning');
        return;
    }

    if (!validateDNI(formData.dni)) {
        showNotification('DNI inválido (debe ser 8 dígitos)', 'warning');
        return;
    }

    if (!validateEmail(formData.email)) {
        showNotification('Email inválido', 'warning');
        return;
    }

    // Enviar
    ajaxRequest('/users/api/create', 'POST', formData, function(response) {
        showNotification(response.message, 'success');
        $('#createUserModal').modal('hide');
        $('#createUserForm')[0].reset();

        // Recargar página
        setTimeout(() => location.reload(), 1000);
    });
}

/**
 * Editar usuario
 */
function editUser(userId) {
    ajaxRequest(`/users/api/${userId}`, 'GET', null, function(response) {
        const user = response.user;
        
        $('#edit_user_id').val(user.id);
        $('#edit_username').val(user.username);
        $('#edit_email').val(user.email);
        $('#edit_dni').val(user.dni);
        $('#edit_role').val(user.role);
        $('#edit_status').val(user.status);
        
        $('#editUserModal').modal('show');
    });
}

/**
 * Actualizar usuario
 */
function updateUser() {
    const userId = $('#edit_user_id').val();
    const formData = {
        email: $('#edit_email').val().trim(),
        dni: $('#edit_dni').val().trim(),
        role: $('#edit_role').val(),
        status: $('#edit_status').val()
    };

    ajaxRequest(`/users/api/update/${userId}`, 'PUT', formData, function(response) {
        showNotification(response.message, 'success');
        $('#editUserModal').modal('hide');
        setTimeout(() => location.reload(), 1000);
    });
}

/**
 * Toggle estado de usuario
 */
function toggleUserStatus(userId) {
    if (confirm('¿Cambiar el estado de este usuario?')) {
        ajaxRequest(`/users/api/toggle_status/${userId}`, 'POST', null, function(response) {
            showNotification(response.message, 'success');
            setTimeout(() => location.reload(), 1000);
        });
    }
}

/**
 * Resetear contraseña
 */
function resetPassword(userId) {
    ajaxRequest(`/users/api/${userId}`, 'GET', null, function(response) {
        const user = response.user;
        
        $('#reset_user_id').val(user.id);
        $('#reset_username').text(user.username);
        $('#reset_password').val('');
        
        $('#resetPasswordModal').modal('show');
    });
}

/**
 * Confirmar reset de contraseña
 */
function confirmResetPassword() {
    const userId = $('#reset_user_id').val();
    const newPassword = $('#reset_password').val();

    if (!newPassword || newPassword.length < 8) {
        showNotification('La contraseña debe tener al menos 8 caracteres', 'warning');
        return;
    }

    const data = { new_password: newPassword };

    ajaxRequest(`/reset_password/${userId}`, 'POST', data, function(response) {
        showNotification(response.message, 'success');
        $('#resetPasswordModal').modal('hide');
    });
}

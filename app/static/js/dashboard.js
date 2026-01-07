/**
 * QoriCash Trading V2 - Dashboard JavaScript
 * Funciones para animaciones y efectos del dashboard
 */

/**
 * Anima un número desde 0 hasta su valor final
 * @param {jQuery} $element - Elemento jQuery que contiene el número
 * @param {number} finalValue - Valor final del contador
 * @param {number} duration - Duración de la animación en ms (default: 1000)
 * @param {string} prefix - Prefijo opcional (ej: "$", "S/")
 * @param {number} decimals - Número de decimales (default: 0)
 */
function animateCounter($element, finalValue, duration = 1000, prefix = '', decimals = 0) {
    // Si el elemento no existe, salir
    if (!$element || $element.length === 0) return;

    // Convertir el valor final a número
    const endValue = parseFloat(finalValue) || 0;
    const startValue = 0;
    const startTime = Date.now();

    // Función de easing (ease-out-cubic)
    function easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    // Función de animación
    function updateCounter() {
        const currentTime = Date.now();
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);

        // Aplicar easing
        const easedProgress = easeOutCubic(progress);

        // Calcular valor actual
        const currentValue = startValue + (endValue - startValue) * easedProgress;

        // Formatear el número
        let formattedValue;
        if (decimals > 0) {
            formattedValue = currentValue.toFixed(decimals);
        } else {
            formattedValue = Math.floor(currentValue).toString();
        }

        // Agregar separadores de miles
        formattedValue = formattedValue.replace(/\B(?=(\d{3})+(?!\d))/g, ',');

        // Actualizar el elemento
        $element.text(prefix + ' ' + formattedValue);

        // Continuar la animación si no ha terminado
        if (progress < 1) {
            requestAnimationFrame(updateCounter);
        } else {
            // Asegurar que el valor final sea exacto
            let finalFormatted;
            if (decimals > 0) {
                finalFormatted = endValue.toFixed(decimals);
            } else {
                finalFormatted = Math.floor(endValue).toString();
            }
            finalFormatted = finalFormatted.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
            $element.text(prefix + ' ' + finalFormatted);
        }
    }

    // Iniciar la animación
    requestAnimationFrame(updateCounter);
}

/**
 * Anima todos los contadores del dashboard
 */
function animateDashboardCounters() {
    // Animar contadores sin prefijo (números simples)
    $('.counter').each(function() {
        const $this = $(this);
        const value = parseFloat($this.text().replace(/[^0-9.-]/g, '')) || 0;
        animateCounter($this, value, 1200);
    });

    // Animar contadores con moneda USD
    $('.counter-usd').each(function() {
        const $this = $(this);
        const value = parseFloat($this.text().replace(/[^0-9.-]/g, '')) || 0;
        animateCounter($this, value, 1200, '$', 2);
    });

    // Animar contadores con moneda PEN
    $('.counter-pen').each(function() {
        const $this = $(this);
        const value = parseFloat($this.text().replace(/[^0-9.-]/g, '')) || 0;
        animateCounter($this, value, 1200, 'S/', 2);
    });

    // Animar progress bars
    $('.progress-bar').each(function() {
        const $this = $(this);
        const targetWidth = $this.attr('aria-valuenow') || $this.data('value') || 0;

        // Animar el ancho de la barra
        $this.css('width', '0%');
        setTimeout(() => {
            $this.css({
                'width': targetWidth + '%',
                'transition': 'width 1.5s cubic-bezier(0.4, 0, 0.2, 1)'
            });
        }, 100);
    });
}

/**
 * Inicializar tooltips y popovers si existen
 */
function initializeDashboardUI() {
    // Inicializar tooltips de Bootstrap si existen
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Agregar clases de animación a las cards
    $('.stat-card, .metric-card, .status-item').addClass('fade-in');
}

/**
 * Actualizar un contador específico con animación
 * @param {string} selector - Selector jQuery del elemento
 * @param {number} newValue - Nuevo valor
 * @param {string} prefix - Prefijo (ej: "$", "S/")
 * @param {number} decimals - Número de decimales
 */
function updateCounterValue(selector, newValue, prefix = '', decimals = 0) {
    const $element = $(selector);
    if ($element.length > 0) {
        animateCounter($element, newValue, 800, prefix, decimals);
    }
}

// Exportar funciones para uso global
window.animateCounter = animateCounter;
window.animateDashboardCounters = animateDashboardCounters;
window.initializeDashboardUI = initializeDashboardUI;
window.updateCounterValue = updateCounterValue;

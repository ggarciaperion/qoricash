// Shared Set para deduplicar alertas de cancelación entre AppNavigator y pantallas específicas.
// El handler que se ejecuta primero marca el opId; los demás lo omiten.
export const shownCancelAlerts = new Set<string>();

/**
 * Format currency with symbol
 */
export const formatCurrency = (amount: number, currency: 'PEN' | 'USD' = 'PEN'): string => {
  const symbol = currency === 'PEN' ? 'S/' : '$';
  return `${symbol} ${amount.toFixed(2)}`;
};

/**
 * Format date to locale string
 */
export const formatDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString('es-PE', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
};

/**
 * Format datetime to locale string
 */
export const formatDateTime = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleString('es-PE', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * Format time ago
 */
export const formatTimeAgo = (dateString: string): string => {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Hace un momento';
  if (diffMins < 60) return `Hace ${diffMins} min`;
  if (diffHours < 24) return `Hace ${diffHours}h`;
  if (diffDays < 7) return `Hace ${diffDays}d`;
  return formatDate(dateString);
};

/**
 * Format bank account number (mask middle digits)
 */
export const formatBankAccount = (accountNumber: string): string => {
  if (accountNumber.length <= 8) return accountNumber;
  const first = accountNumber.substring(0, 4);
  const last = accountNumber.substring(accountNumber.length - 4);
  return `${first}****${last}`;
};

/**
 * Format exchange rate
 */
export const formatExchangeRate = (rate: number): string => {
  return rate.toFixed(4);
};

/**
 * Calculate amount based on exchange rate
 */
export const calculateAmount = (amount: number, rate: number): number => {
  return parseFloat((amount * rate).toFixed(2));
};

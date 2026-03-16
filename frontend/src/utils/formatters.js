// src/utils/formatters.js

/**
 * Formats a number into USD currency string.
 * @param {number} amount 
 * @returns {string}
 */
export const formatCurrency = (amount) => {
  if (typeof amount !== 'number') return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
};

/**
 * Formats a date string into a readable format.
 * @param {string} dateString 
 * @returns {string}
 */
export const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};

/**
 * Truncates text if it exceeds length.
 * @param {string} str 
 * @param {number} length 
 * @returns {string}
 */
export const truncateText = (str, length = 20) => {
  if (!str) return '';
  return str.length > length ? str.substring(0, length) + '...' : str;
};
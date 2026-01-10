/**
 * Sistema de logging para QoriCash Mobile App
 * Permite registrar logs en consola y almacenarlos para debugging
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

const LOGS_STORAGE_KEY = '@qoricash_app_logs';
const MAX_LOGS = 500; // Máximo de logs a almacenar

export enum LogLevel {
  DEBUG = 'DEBUG',
  INFO = 'INFO',
  WARN = 'WARN',
  ERROR = 'ERROR',
}

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  tag: string;
  message: string;
  data?: any;
}

class Logger {
  private logs: LogEntry[] = [];
  private enabled: boolean = true;

  constructor() {
    this.loadLogs();
  }

  /**
   * Cargar logs almacenados
   */
  private async loadLogs() {
    try {
      const storedLogs = await AsyncStorage.getItem(LOGS_STORAGE_KEY);
      if (storedLogs) {
        this.logs = JSON.parse(storedLogs);
      }
    } catch (error) {
      console.error('[Logger] Error loading logs:', error);
    }
  }

  /**
   * Guardar logs en AsyncStorage
   */
  private async saveLogs() {
    try {
      // Mantener solo los últimos MAX_LOGS logs
      const logsToSave = this.logs.slice(-MAX_LOGS);
      await AsyncStorage.setItem(LOGS_STORAGE_KEY, JSON.stringify(logsToSave));
    } catch (error) {
      console.error('[Logger] Error saving logs:', error);
    }
  }

  /**
   * Agregar un log
   */
  private addLog(level: LogLevel, tag: string, message: string, data?: any) {
    if (!this.enabled) return;

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      level,
      tag,
      message,
      data,
    };

    // Agregar a memoria
    this.logs.push(entry);

    // Log en consola con formato mejorado
    const emoji = {
      [LogLevel.DEBUG]: '🔍',
      [LogLevel.INFO]: 'ℹ️',
      [LogLevel.WARN]: '⚠️',
      [LogLevel.ERROR]: '❌',
    }[level];

    const consoleMessage = `${emoji} [${tag}] ${message}`;

    switch (level) {
      case LogLevel.DEBUG:
        console.log(consoleMessage, data || '');
        break;
      case LogLevel.INFO:
        console.info(consoleMessage, data || '');
        break;
      case LogLevel.WARN:
        console.warn(consoleMessage, data || '');
        break;
      case LogLevel.ERROR:
        console.error(consoleMessage, data || '');
        break;
    }

    // Guardar en AsyncStorage (con debounce implícito)
    this.saveLogs();
  }

  /**
   * Log de debugging
   */
  debug(tag: string, message: string, data?: any) {
    this.addLog(LogLevel.DEBUG, tag, message, data);
  }

  /**
   * Log informativo
   */
  info(tag: string, message: string, data?: any) {
    this.addLog(LogLevel.INFO, tag, message, data);
  }

  /**
   * Log de advertencia
   */
  warn(tag: string, message: string, data?: any) {
    this.addLog(LogLevel.WARN, tag, message, data);
  }

  /**
   * Log de error
   */
  error(tag: string, message: string, data?: any) {
    this.addLog(LogLevel.ERROR, tag, message, data);
  }

  /**
   * Obtener todos los logs
   */
  getLogs(): LogEntry[] {
    return [...this.logs];
  }

  /**
   * Obtener logs filtrados por nivel
   */
  getLogsByLevel(level: LogLevel): LogEntry[] {
    return this.logs.filter(log => log.level === level);
  }

  /**
   * Obtener logs filtrados por tag
   */
  getLogsByTag(tag: string): LogEntry[] {
    return this.logs.filter(log => log.tag === tag);
  }

  /**
   * Obtener logs recientes (últimos N)
   */
  getRecentLogs(count: number = 50): LogEntry[] {
    return this.logs.slice(-count);
  }

  /**
   * Limpiar logs
   */
  async clearLogs() {
    this.logs = [];
    await AsyncStorage.removeItem(LOGS_STORAGE_KEY);
    console.log('[Logger] Logs cleared');
  }

  /**
   * Exportar logs como string
   */
  exportLogs(): string {
    return this.logs
      .map(log => {
        const dataStr = log.data ? ` | Data: ${JSON.stringify(log.data)}` : '';
        return `[${log.timestamp}] [${log.level}] [${log.tag}] ${log.message}${dataStr}`;
      })
      .join('\n');
  }

  /**
   * Habilitar/deshabilitar logging
   */
  setEnabled(enabled: boolean) {
    this.enabled = enabled;
  }
}

// Exportar instancia singleton
export const logger = new Logger();

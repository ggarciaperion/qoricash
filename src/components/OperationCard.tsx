import React from 'react';
import { View, StyleSheet, TouchableOpacity } from 'react-native';
import { Card, Text, Chip, Icon } from 'react-native-paper';
import { Operation } from '../types';
import { formatCurrency, formatDateTime, formatTimeAgo } from '../utils/formatters';
import { STATUS_COLORS, STATUS_ICONS } from '../constants/config';

interface OperationCardProps {
  operation: Operation;
  onPress: () => void;
  compact?: boolean;
}

export const OperationCard: React.FC<OperationCardProps> = ({ operation, onPress, compact = false }) => {
  const getStatusColor = (status: string) => {
    return STATUS_COLORS[status as keyof typeof STATUS_COLORS] || '#757575';
  };

  const getStatusIcon = (status: string) => {
    return STATUS_ICONS[status as keyof typeof STATUS_ICONS] || 'help-circle';
  };

  const getTypeColor = (type: string) => {
    return type === 'Compra' ? '#9C27B0' : '#2196F3'; // Compra: Morado, Venta: Azul
  };

  // Versión compacta para el historial
  if (compact) {
    return (
      <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
        <Card style={styles.card}>
          <Card.Content style={styles.compactContent}>
            {/* Título compacto con chips de color */}
            <View style={styles.compactHeader}>
              <Text variant="titleMedium" style={styles.compactId}>
                {operation.operation_id}
              </Text>

              <Text variant="titleMedium" style={styles.compactType}>
                {operation.operation_type.toUpperCase()}
              </Text>

              <Text variant="titleMedium" style={styles.compactAmount}>
                ${operation.amount_usd.toFixed(2)}
              </Text>

              <Text variant="bodySmall" style={styles.compactRate}>
                TC: {operation.exchange_rate.toFixed(2)}
              </Text>

              <Chip
                mode="flat"
                style={[styles.compactStatusChip, { backgroundColor: getStatusColor(operation.status) }]}
                textStyle={styles.compactChipText}
                compact
              >
                {operation.status.toUpperCase()}
              </Chip>
            </View>

            {/* Fecha de completado */}
            {operation.completed_at && (
              <View style={styles.compactFooter}>
                <Icon source="check-circle" size={14} color="#82C16C" />
                <Text variant="bodySmall" style={styles.completedText}>
                  Completada: {formatDateTime(operation.completed_at)}
                </Text>
              </View>
            )}

            {operation.status === 'Cancelada' && operation.updated_at && (
              <View style={styles.compactFooter}>
                <Icon source="close-circle" size={14} color="#F44336" />
                <Text variant="bodySmall" style={styles.cancelledText}>
                  Cancelada: {formatDateTime(operation.updated_at)}
                </Text>
              </View>
            )}

            {operation.status === 'expirado' && operation.updated_at && (
              <View style={styles.compactFooter}>
                <Icon source="clock-alert" size={14} color="#757575" />
                <Text variant="bodySmall" style={styles.expiredText}>
                  Expirada: {formatDateTime(operation.updated_at)}
                </Text>
              </View>
            )}
          </Card.Content>
        </Card>
      </TouchableOpacity>
    );
  }

  // Versión completa para operaciones pendientes
  return (
    <TouchableOpacity onPress={onPress} activeOpacity={0.7}>
      <Card style={styles.card}>
        <Card.Content>
          {/* Header */}
          <View style={styles.header}>
            <View style={styles.headerLeft}>
              <Text variant="titleMedium" style={styles.operationId}>
                {operation.operation_id}
              </Text>
              <Text variant="bodySmall" style={styles.timeAgo}>
                {formatTimeAgo(operation.created_at)}
              </Text>
            </View>
            <Chip
              mode="flat"
              style={[styles.statusChip, { backgroundColor: getStatusColor(operation.status) }]}
              textStyle={styles.chipText}
              icon={() => (
                <Icon source={getStatusIcon(operation.status)} size={16} color="#FFF" />
              )}
            >
              {operation.status}
            </Chip>
          </View>

          {/* Type Badge */}
          <Chip
            mode="flat"
            style={[styles.typeChip, { backgroundColor: getTypeColor(operation.operation_type) }]}
            textStyle={styles.chipText}
            compact
          >
            {operation.operation_type}
          </Chip>

          {/* Amounts */}
          <View style={styles.amountsContainer}>
            <View style={styles.amountRow}>
              <Text variant="bodyMedium" style={styles.label}>
                Monto USD:
              </Text>
              <Text variant="titleMedium" style={styles.amountUsd}>
                {formatCurrency(operation.amount_usd, 'USD')}
              </Text>
            </View>

            <View style={styles.exchangeRate}>
              <Icon source="swap-horizontal" size={16} color="#757575" />
              <Text variant="bodySmall" style={styles.rate}>
                T.C. {operation.exchange_rate.toFixed(4)}
              </Text>
            </View>

            <View style={styles.amountRow}>
              <Text variant="bodyMedium" style={styles.label}>
                Monto PEN:
              </Text>
              <Text variant="titleMedium" style={styles.amountPen}>
                {formatCurrency(operation.amount_pen, 'PEN')}
              </Text>
            </View>
          </View>

          {/* Footer */}
          {operation.completed_at && (
            <View style={styles.footer}>
              <Icon source="check-circle" size={14} color="#82C16C" />
              <Text variant="bodySmall" style={styles.completedText}>
                Completada: {formatDateTime(operation.completed_at)}
              </Text>
            </View>
          )}

          {operation.status === 'en_proceso' && operation.time_in_process_minutes && (
            <View style={styles.footer}>
              <Icon source="clock-outline" size={14} color="#FF9800" />
              <Text variant="bodySmall" style={styles.processingText}>
                En proceso hace {operation.time_in_process_minutes} minutos
              </Text>
            </View>
          )}
        </Card.Content>
      </Card>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    marginHorizontal: 16,
    marginVertical: 8,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  headerLeft: {
    flex: 1,
  },
  operationId: {
    fontWeight: 'bold',
    color: '#1976D2',
  },
  timeAgo: {
    color: '#757575',
    marginTop: 2,
  },
  statusChip: {
    marginLeft: 8,
  },
  chipText: {
    color: '#FFF',
    fontSize: 12,
    fontWeight: '600',
  },
  typeChip: {
    alignSelf: 'flex-start',
    marginBottom: 12,
  },
  amountsContainer: {
    backgroundColor: '#F5F5F5',
    padding: 12,
    borderRadius: 8,
  },
  amountRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginVertical: 4,
  },
  label: {
    color: '#616161',
  },
  amountUsd: {
    fontWeight: 'bold',
    color: '#2196F3',
  },
  amountPen: {
    fontWeight: 'bold',
    color: '#82C16C',
  },
  exchangeRate: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginVertical: 8,
  },
  rate: {
    marginLeft: 4,
    color: '#757575',
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E0E0E0',
  },
  completedText: {
    marginLeft: 4,
    color: '#82C16C',
  },
  processingText: {
    marginLeft: 4,
    color: '#FF9800',
  },
  compactContent: {
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  compactHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'nowrap',
    gap: 4,
  },
  compactId: {
    fontWeight: 'bold',
    color: '#1976D2',
    fontSize: 13,
  },
  compactType: {
    fontWeight: 'bold',
    color: '#1976D2',
    fontSize: 13,
  },
  compactStatusChip: {
    height: 22,
    marginHorizontal: 0,
    marginLeft: 'auto',
  },
  compactChipText: {
    color: '#FFF',
    fontSize: 10,
    fontWeight: '700',
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  compactAmount: {
    fontWeight: 'bold',
    color: '#212121',
    fontSize: 13,
  },
  compactRate: {
    color: '#757575',
    fontSize: 10,
    fontStyle: 'italic',
  },
  compactFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
  },
  cancelledText: {
    marginLeft: 4,
    color: '#F44336',
  },
  expiredText: {
    marginLeft: 4,
    color: '#757575',
  },
});

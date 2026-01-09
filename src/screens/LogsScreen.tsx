import React, { useState, useEffect } from 'react';
import {
  View,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Share,
  Alert,
} from 'react-native';
import {
  Text,
  Card,
  Button,
  Chip,
  Searchbar,
  FAB,
} from 'react-native-paper';
import { logger, LogLevel } from '../utils/logger';
import { Colors } from '../constants/colors';

interface LogsScreenProps {
  navigation: any;
}

export const LogsScreen: React.FC<LogsScreenProps> = ({ navigation }) => {
  const [logs, setLogs] = useState(logger.getLogs());
  const [filteredLogs, setFilteredLogs] = useState(logger.getLogs());
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedLevel, setSelectedLevel] = useState<LogLevel | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadLogs();
  }, []);

  useEffect(() => {
    filterLogs();
  }, [searchQuery, selectedLevel, logs]);

  const loadLogs = () => {
    const allLogs = logger.getLogs();
    setLogs(allLogs);
    setFilteredLogs(allLogs);
  };

  const filterLogs = () => {
    let filtered = logs;

    // Filtrar por nivel
    if (selectedLevel) {
      filtered = filtered.filter(log => log.level === selectedLevel);
    }

    // Filtrar por búsqueda
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        log =>
          log.message.toLowerCase().includes(query) ||
          log.tag.toLowerCase().includes(query)
      );
    }

    setFilteredLogs(filtered);
  };

  const handleRefresh = () => {
    setRefreshing(true);
    loadLogs();
    setRefreshing(false);
  };

  const handleClearLogs = () => {
    Alert.alert(
      'Limpiar Logs',
      '¿Estás seguro de que deseas eliminar todos los logs?',
      [
        { text: 'Cancelar', style: 'cancel' },
        {
          text: 'Eliminar',
          style: 'destructive',
          onPress: async () => {
            await logger.clearLogs();
            loadLogs();
          },
        },
      ]
    );
  };

  const handleExportLogs = async () => {
    try {
      const logsText = logger.exportLogs();
      await Share.share({
        message: logsText,
        title: 'QoriCash App Logs',
      });
    } catch (error) {
      Alert.alert('Error', 'No se pudieron exportar los logs');
    }
  };

  const getLevelColor = (level: LogLevel) => {
    switch (level) {
      case LogLevel.DEBUG:
        return '#607D8B';
      case LogLevel.INFO:
        return '#2196F3';
      case LogLevel.WARN:
        return '#FF9800';
      case LogLevel.ERROR:
        return '#F44336';
      default:
        return '#9E9E9E';
    }
  };

  const getLevelEmoji = (level: LogLevel) => {
    switch (level) {
      case LogLevel.DEBUG:
        return '🔍';
      case LogLevel.INFO:
        return 'ℹ️';
      case LogLevel.WARN:
        return '⚠️';
      case LogLevel.ERROR:
        return '❌';
      default:
        return '📝';
    }
  };

  return (
    <View style={styles.container}>
      {/* Search Bar */}
      <Searchbar
        placeholder="Buscar en logs..."
        onChangeText={setSearchQuery}
        value={searchQuery}
        style={styles.searchBar}
      />

      {/* Filter Chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.filterContainer}>
        <Chip
          selected={selectedLevel === null}
          onPress={() => setSelectedLevel(null)}
          style={styles.filterChip}
        >
          Todos ({logs.length})
        </Chip>
        <Chip
          selected={selectedLevel === LogLevel.DEBUG}
          onPress={() => setSelectedLevel(LogLevel.DEBUG)}
          style={styles.filterChip}
        >
          🔍 Debug ({logger.getLogsByLevel(LogLevel.DEBUG).length})
        </Chip>
        <Chip
          selected={selectedLevel === LogLevel.INFO}
          onPress={() => setSelectedLevel(LogLevel.INFO)}
          style={styles.filterChip}
        >
          ℹ️ Info ({logger.getLogsByLevel(LogLevel.INFO).length})
        </Chip>
        <Chip
          selected={selectedLevel === LogLevel.WARN}
          onPress={() => setSelectedLevel(LogLevel.WARN)}
          style={styles.filterChip}
        >
          ⚠️ Warn ({logger.getLogsByLevel(LogLevel.WARN).length})
        </Chip>
        <Chip
          selected={selectedLevel === LogLevel.ERROR}
          onPress={() => setSelectedLevel(LogLevel.ERROR)}
          style={styles.filterChip}
        >
          ❌ Error ({logger.getLogsByLevel(LogLevel.ERROR).length})
        </Chip>
      </ScrollView>

      {/* Logs List */}
      <ScrollView
        style={styles.logsList}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
      >
        {filteredLogs.length === 0 ? (
          <Card style={styles.emptyCard}>
            <Card.Content>
              <Text style={styles.emptyText}>No hay logs para mostrar</Text>
            </Card.Content>
          </Card>
        ) : (
          filteredLogs.reverse().map((log, index) => (
            <Card key={index} style={[styles.logCard, { borderLeftColor: getLevelColor(log.level) }]}>
              <Card.Content>
                <View style={styles.logHeader}>
                  <Text style={styles.logEmoji}>{getLevelEmoji(log.level)}</Text>
                  <Chip
                    style={[styles.levelChip, { backgroundColor: getLevelColor(log.level) }]}
                    textStyle={styles.levelChipText}
                  >
                    {log.level}
                  </Chip>
                  <Chip style={styles.tagChip}>{log.tag}</Chip>
                </View>
                <Text style={styles.logMessage}>{log.message}</Text>
                {log.data && (
                  <Text style={styles.logData}>
                    Data: {JSON.stringify(log.data, null, 2)}
                  </Text>
                )}
                <Text style={styles.logTimestamp}>
                  {new Date(log.timestamp).toLocaleString()}
                </Text>
              </Card.Content>
            </Card>
          ))
        )}
      </ScrollView>

      {/* Action Buttons */}
      <View style={styles.actionsContainer}>
        <Button
          mode="outlined"
          onPress={handleExportLogs}
          style={styles.actionButton}
          icon="share-variant"
        >
          Exportar
        </Button>
        <Button
          mode="outlined"
          onPress={handleClearLogs}
          style={styles.actionButton}
          icon="delete"
          buttonColor="#F44336"
          textColor="#FFFFFF"
        >
          Limpiar
        </Button>
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  searchBar: {
    margin: 16,
    marginBottom: 8,
  },
  filterContainer: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    maxHeight: 60,
  },
  filterChip: {
    marginRight: 8,
  },
  logsList: {
    flex: 1,
    paddingHorizontal: 16,
  },
  emptyCard: {
    marginTop: 32,
    backgroundColor: Colors.surface,
  },
  emptyText: {
    textAlign: 'center',
    color: '#999999',
    fontSize: 16,
  },
  logCard: {
    marginVertical: 4,
    backgroundColor: Colors.surface,
    borderLeftWidth: 4,
  },
  logHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  logEmoji: {
    fontSize: 20,
    marginRight: 8,
  },
  levelChip: {
    height: 24,
    marginRight: 8,
  },
  levelChipText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: 'bold',
  },
  tagChip: {
    height: 24,
    backgroundColor: '#E0E0E0',
  },
  logMessage: {
    fontSize: 14,
    color: Colors.textDark,
    marginBottom: 8,
  },
  logData: {
    fontSize: 12,
    color: '#666666',
    backgroundColor: '#F5F5F5',
    padding: 8,
    borderRadius: 4,
    fontFamily: 'monospace',
    marginBottom: 8,
  },
  logTimestamp: {
    fontSize: 11,
    color: '#999999',
  },
  actionsContainer: {
    flexDirection: 'row',
    padding: 16,
    gap: 8,
  },
  actionButton: {
    flex: 1,
  },
});

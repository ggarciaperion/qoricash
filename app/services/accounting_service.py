"""
Servicio de Contabilidad para QoriCash Trading V2

Maneja la lógica de amarres contables, neteo y reportes
"""
from app.extensions import db
from app.models import Operation, AccountingMatch, AccountingBatch, Client
from app.utils.formatters import now_peru
from sqlalchemy import func, and_, or_
from datetime import datetime, date
from decimal import Decimal


class AccountingService:
    """Servicio de contabilidad y neteo"""

    @staticmethod
    def get_available_operations(fecha_inicio=None, fecha_fin=None, operation_type=None):
        """
        Obtener operaciones completadas disponibles para amarrar

        Args:
            fecha_inicio: Fecha de inicio (opcional)
            fecha_fin: Fecha de fin (opcional)
            operation_type: 'Compra' o 'Venta' (opcional)

        Returns:
            list: Lista de operaciones disponibles
        """
        query = Operation.query.filter(
            Operation.status == 'Completada'
        )

        if operation_type:
            query = query.filter(Operation.operation_type == operation_type)

        if fecha_inicio:
            if isinstance(fecha_inicio, str):
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            query = query.filter(func.date(Operation.completed_at) >= fecha_inicio)

        if fecha_fin:
            if isinstance(fecha_fin, str):
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            query = query.filter(func.date(Operation.completed_at) <= fecha_fin)

        return query.order_by(Operation.completed_at.desc()).all()

    @staticmethod
    def get_matched_amount_for_operation(operation_id):
        """
        Calcular cuánto USD de una operación ya está amarrado

        Args:
            operation_id: ID de la operación

        Returns:
            Decimal: Monto USD ya amarrado
        """
        buy_matches = db.session.query(func.sum(AccountingMatch.matched_amount_usd)).filter(
            AccountingMatch.buy_operation_id == operation_id,
            AccountingMatch.status == 'Activo'
        ).scalar() or Decimal('0')

        sell_matches = db.session.query(func.sum(AccountingMatch.matched_amount_usd)).filter(
            AccountingMatch.sell_operation_id == operation_id,
            AccountingMatch.status == 'Activo'
        ).scalar() or Decimal('0')

        return max(buy_matches, sell_matches)

    @staticmethod
    def get_available_amount_for_operation(operation_id):
        """
        Calcular cuánto USD disponible queda en una operación para amarrar

        Args:
            operation_id: ID de la operación

        Returns:
            Decimal: Monto USD disponible
        """
        operation = Operation.query.get(operation_id)
        if not operation:
            return Decimal('0')

        matched_amount = AccountingService.get_matched_amount_for_operation(operation_id)
        available = Decimal(str(operation.amount_usd)) - matched_amount

        return max(available, Decimal('0'))

    @staticmethod
    def create_match(buy_operation_id, sell_operation_id, matched_amount_usd, user_id, notes=None):
        """
        Crear un amarre entre una operación de compra y una de venta

        Args:
            buy_operation_id: ID de operación de compra
            sell_operation_id: ID de operación de venta
            matched_amount_usd: Monto USD a amarrar
            user_id: ID del usuario que crea el match
            notes: Notas adicionales

        Returns:
            tuple: (success, message, match)
        """
        try:
            # Validar operaciones
            buy_op = Operation.query.get(buy_operation_id)
            sell_op = Operation.query.get(sell_operation_id)

            if not buy_op or not sell_op:
                return False, 'Operación no encontrada', None

            if buy_op.operation_type != 'Compra':
                return False, 'La primera operación debe ser de tipo Compra', None

            if sell_op.operation_type != 'Venta':
                return False, 'La segunda operación debe ser de tipo Venta', None

            if buy_op.status != 'Completada' or sell_op.status != 'Completada':
                return False, 'Ambas operaciones deben estar completadas', None

            # Validar montos disponibles
            buy_available = AccountingService.get_available_amount_for_operation(buy_operation_id)
            sell_available = AccountingService.get_available_amount_for_operation(sell_operation_id)

            matched_amount = Decimal(str(matched_amount_usd))

            if matched_amount > buy_available:
                return False, f'Monto excede lo disponible en la operación de compra (disponible: ${buy_available})', None

            if matched_amount > sell_available:
                return False, f'Monto excede lo disponible en la operación de venta (disponible: ${sell_available})', None

            # Calcular utilidad
            buy_tc = Decimal(str(buy_op.exchange_rate))
            sell_tc = Decimal(str(sell_op.exchange_rate))

            # Utilidad = (TC Venta - TC Compra) * USD Amarrado
            profit_pen = (sell_tc - buy_tc) * matched_amount
            profit_percentage = ((sell_tc - buy_tc) / buy_tc) * Decimal('100') if buy_tc > 0 else Decimal('0')

            # Crear match
            match = AccountingMatch(
                buy_operation_id=buy_operation_id,
                sell_operation_id=sell_operation_id,
                matched_amount_usd=matched_amount,
                buy_exchange_rate=buy_tc,
                sell_exchange_rate=sell_tc,
                profit_pen=profit_pen,
                profit_percentage=profit_percentage,
                status='Activo',
                notes=notes,
                created_by=user_id
            )

            db.session.add(match)
            db.session.commit()

            return True, 'Match creado exitosamente', match

        except Exception as e:
            db.session.rollback()
            return False, f'Error al crear match: {str(e)}', None

    @staticmethod
    def delete_match(match_id, user_id):
        """
        Eliminar (anular) un match

        Args:
            match_id: ID del match
            user_id: ID del usuario

        Returns:
            tuple: (success, message)
        """
        try:
            match = AccountingMatch.query.get(match_id)
            if not match:
                return False, 'Match no encontrado'

            if match.batch_id:
                batch = AccountingBatch.query.get(match.batch_id)
                if batch and batch.status == 'Cerrado':
                    return False, 'No se puede eliminar un match de un batch cerrado'

            match.status = 'Anulado'
            db.session.commit()

            # Si pertenecía a un batch, recalcular totales
            if match.batch_id:
                batch = AccountingBatch.query.get(match.batch_id)
                if batch:
                    batch.calculate_totals()
                    db.session.commit()

            return True, 'Match eliminado exitosamente'

        except Exception as e:
            db.session.rollback()
            return False, f'Error al eliminar match: {str(e)}'

    @staticmethod
    def create_batch(match_ids, description, netting_date, user_id):
        """
        Crear un batch de neteo con múltiples matches

        Args:
            match_ids: Lista de IDs de matches
            description: Descripción del batch
            netting_date: Fecha del neteo
            user_id: ID del usuario

        Returns:
            tuple: (success, message, batch)
        """
        try:
            if not match_ids or len(match_ids) == 0:
                return False, 'Debe seleccionar al menos un match', None

            # Validar que los matches existan y estén activos
            matches = AccountingMatch.query.filter(
                AccountingMatch.id.in_(match_ids),
                AccountingMatch.status == 'Activo'
            ).all()

            if len(matches) != len(match_ids):
                return False, 'Algunos matches no existen o no están activos', None

            # Validar que ninguno esté en otro batch
            for match in matches:
                if match.batch_id:
                    return False, f'El match {match.id} ya pertenece a otro batch', None

            # Crear batch
            batch_code = AccountingBatch.generate_batch_code()

            if isinstance(netting_date, str):
                netting_date = datetime.strptime(netting_date, '%Y-%m-%d').date()

            batch = AccountingBatch(
                batch_code=batch_code,
                description=description,
                netting_date=netting_date,
                status='Abierto',
                created_by=user_id
            )

            db.session.add(batch)
            db.session.flush()  # Para obtener el ID

            # Asignar matches al batch
            for match in matches:
                match.batch_id = batch.id

            # Calcular totales
            batch.calculate_totals()

            # Generar asiento contable automático
            AccountingService.generate_accounting_entry(batch)

            db.session.commit()

            return True, 'Batch creado exitosamente', batch

        except Exception as e:
            db.session.rollback()
            return False, f'Error al crear batch: {str(e)}', None

    @staticmethod
    def generate_accounting_entry(batch):
        """
        Generar asiento contable automático para un batch

        Args:
            batch: Instancia de AccountingBatch
        """
        entry = []

        # DEBE: Efectivo recibido (ventas en PEN)
        if batch.total_sells_pen > 0:
            entry.append({
                'cuenta': '101 - Caja y Bancos',
                'debe': float(batch.total_sells_pen),
                'haber': 0,
                'glosa': f'Por venta de USD {float(batch.total_sells_usd):,.2f} - Batch {batch.batch_code}'
            })

        # HABER: Efectivo entregado (compras en PEN)
        if batch.total_buys_pen > 0:
            entry.append({
                'cuenta': '101 - Caja y Bancos',
                'debe': 0,
                'haber': float(batch.total_buys_pen),
                'glosa': f'Por compra de USD {float(batch.total_buys_usd):,.2f} - Batch {batch.batch_code}'
            })

        # DEBE: Moneda extranjera recibida (compras en USD)
        if batch.total_buys_usd > 0:
            entry.append({
                'cuenta': '104 - Moneda Extranjera',
                'debe': float(batch.total_buys_usd),
                'haber': 0,
                'glosa': f'Por compra de USD - Batch {batch.batch_code}'
            })

        # HABER: Moneda extranjera entregada (ventas en USD)
        if batch.total_sells_usd > 0:
            entry.append({
                'cuenta': '104 - Moneda Extranjera',
                'debe': 0,
                'haber': float(batch.total_sells_usd),
                'glosa': f'Por venta de USD - Batch {batch.batch_code}'
            })

        # Utilidad o pérdida
        if batch.total_profit_pen > 0:
            # HABER: Ganancia
            entry.append({
                'cuenta': '776 - Ganancia por diferencia de cambio',
                'debe': 0,
                'haber': float(batch.total_profit_pen),
                'glosa': f'Utilidad neta del neteo - Batch {batch.batch_code}'
            })
        elif batch.total_profit_pen < 0:
            # DEBE: Pérdida
            entry.append({
                'cuenta': '676 - Pérdida por diferencia de cambio',
                'debe': abs(float(batch.total_profit_pen)),
                'haber': 0,
                'glosa': f'Pérdida neta del neteo - Batch {batch.batch_code}'
            })

        batch.accounting_entry = entry

    @staticmethod
    def close_batch(batch_id, user_id):
        """
        Cerrar un batch (no se podrán hacer más cambios)

        Args:
            batch_id: ID del batch
            user_id: ID del usuario

        Returns:
            tuple: (success, message)
        """
        try:
            batch = AccountingBatch.query.get(batch_id)
            if not batch:
                return False, 'Batch no encontrado'

            if batch.status == 'Cerrado':
                return False, 'El batch ya está cerrado'

            batch.status = 'Cerrado'
            batch.closed_at = now_peru()
            db.session.commit()

            return True, 'Batch cerrado exitosamente'

        except Exception as e:
            db.session.rollback()
            return False, f'Error al cerrar batch: {str(e)}'

    @staticmethod
    def get_profit_by_operation(fecha_inicio=None, fecha_fin=None):
        """
        Obtener utilidad por operación

        Returns:
            list: Lista de operaciones con su utilidad
        """
        # Subconsultas para obtener utilidades por compra y venta
        buy_profits = db.session.query(
            AccountingMatch.buy_operation_id.label('operation_id'),
            func.sum(AccountingMatch.profit_pen).label('profit')
        ).filter(
            AccountingMatch.status == 'Activo'
        ).group_by(AccountingMatch.buy_operation_id).subquery()

        sell_profits = db.session.query(
            AccountingMatch.sell_operation_id.label('operation_id'),
            func.sum(AccountingMatch.profit_pen).label('profit')
        ).filter(
            AccountingMatch.status == 'Activo'
        ).group_by(AccountingMatch.sell_operation_id).subquery()

        # Obtener operaciones con utilidades
        operations = db.session.query(
            Operation,
            func.coalesce(buy_profits.c.profit, 0).label('buy_profit'),
            func.coalesce(sell_profits.c.profit, 0).label('sell_profit')
        ).outerjoin(
            buy_profits, Operation.id == buy_profits.c.operation_id
        ).outerjoin(
            sell_profits, Operation.id == sell_profits.c.operation_id
        ).filter(
            Operation.status == 'Completada'
        )

        if fecha_inicio:
            if isinstance(fecha_inicio, str):
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            operations = operations.filter(func.date(Operation.completed_at) >= fecha_inicio)

        if fecha_fin:
            if isinstance(fecha_fin, str):
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            operations = operations.filter(func.date(Operation.completed_at) <= fecha_fin)

        results = []
        for op, buy_profit, sell_profit in operations.all():
            total_profit = float(buy_profit) + float(sell_profit)
            if total_profit != 0:  # Solo mostrar operaciones con utilidad
                results.append({
                    'operation_id': op.operation_id,
                    'operation_type': op.operation_type,
                    'amount_usd': float(op.amount_usd),
                    'exchange_rate': float(op.exchange_rate),
                    'client_name': op.client.full_name if op.client else 'N/A',
                    'completed_at': op.completed_at.isoformat() if op.completed_at else None,
                    'profit_pen': total_profit
                })

        return results

    @staticmethod
    def get_profit_by_client(fecha_inicio=None, fecha_fin=None):
        """
        Obtener utilidad por cliente

        Returns:
            list: Lista de clientes con su utilidad total
        """
        # Obtener todos los matches activos con sus operaciones
        matches = AccountingMatch.query.filter(
            AccountingMatch.status == 'Activo'
        ).all()

        client_profits = {}

        for match in matches:
            # Filtrar por fechas si se especificaron
            if fecha_inicio or fecha_fin:
                match_date = match.created_at.date()
                if fecha_inicio:
                    if isinstance(fecha_inicio, str):
                        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
                    if match_date < fecha_inicio:
                        continue
                if fecha_fin:
                    if isinstance(fecha_fin, str):
                        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
                    if match_date > fecha_fin:
                        continue

            # Sumar utilidad al cliente de compra
            if match.buy_operation and match.buy_operation.client:
                client_id = match.buy_operation.client_id
                client_name = match.buy_operation.client.full_name or match.buy_operation.client.razon_social
                if client_id not in client_profits:
                    client_profits[client_id] = {
                        'client_name': client_name,
                        'profit_pen': 0,
                        'num_operations': 0
                    }
                client_profits[client_id]['profit_pen'] += float(match.profit_pen)
                client_profits[client_id]['num_operations'] += 1

            # Sumar utilidad al cliente de venta
            if match.sell_operation and match.sell_operation.client:
                client_id = match.sell_operation.client_id
                client_name = match.sell_operation.client.full_name or match.sell_operation.client.razon_social
                if client_id not in client_profits:
                    client_profits[client_id] = {
                        'client_name': client_name,
                        'profit_pen': 0,
                        'num_operations': 0
                    }
                # La utilidad ya se contó en la compra, solo incrementar el contador
                # client_profits[client_id]['profit_pen'] += float(match.profit_pen)
                client_profits[client_id]['num_operations'] += 1

        return list(client_profits.values())

    @staticmethod
    def get_all_batches(fecha_inicio=None, fecha_fin=None, status=None):
        """
        Obtener todos los batches

        Args:
            fecha_inicio: Fecha de inicio (opcional)
            fecha_fin: Fecha de fin (opcional)
            status: Estado del batch (opcional)

        Returns:
            list: Lista de batches
        """
        query = AccountingBatch.query

        if fecha_inicio:
            if isinstance(fecha_inicio, str):
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            query = query.filter(AccountingBatch.netting_date >= fecha_inicio)

        if fecha_fin:
            if isinstance(fecha_fin, str):
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            query = query.filter(AccountingBatch.netting_date <= fecha_fin)

        if status:
            query = query.filter(AccountingBatch.status == status)

        return query.order_by(AccountingBatch.created_at.desc()).all()

    @staticmethod
    def get_all_matches(fecha_inicio=None, fecha_fin=None, batch_id=None, status='Activo'):
        """
        Obtener todos los matches

        Args:
            fecha_inicio: Fecha de inicio (opcional)
            fecha_fin: Fecha de fin (opcional)
            batch_id: ID del batch (opcional)
            status: Estado del match (opcional)

        Returns:
            list: Lista de matches
        """
        query = AccountingMatch.query

        if status:
            query = query.filter(AccountingMatch.status == status)

        if batch_id:
            query = query.filter(AccountingMatch.batch_id == batch_id)

        if fecha_inicio:
            if isinstance(fecha_inicio, str):
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            query = query.filter(func.date(AccountingMatch.created_at) >= fecha_inicio)

        if fecha_fin:
            if isinstance(fecha_fin, str):
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            query = query.filter(func.date(AccountingMatch.created_at) <= fecha_fin)

        return query.order_by(AccountingMatch.created_at.desc()).all()

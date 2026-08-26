"""
Script de anulación contable — EXP-878 y EXP-873
================================================
Ejecutar en Render Shell:
    python anular_operaciones_prueba.py

Qué hace:
  1. Localiza las operaciones por operation_id
  2. Cambia su status a 'Cancelado' y limpia completed_at
  3. Elimina las líneas de asientos (journal_entry_lines) asociadas
  4. Elimina los asientos (journal_entries) con source_type='operation' y source_id=<id>
  5. Hace rollback si ocurre cualquier error
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from sqlalchemy import text

TARGET_OPS = ['EXP-878', 'EXP-873']

def main():
    app = create_app()
    with app.app_context():
        try:
            # ── 1. Obtener las operaciones ────────────────────────────────────
            placeholders = ','.join([f"'{op}'" for op in TARGET_OPS])
            ops = db.session.execute(
                text(f"SELECT id, operation_id, status, amount_usd, amount_pen, completed_at "
                     f"FROM operations WHERE operation_id IN ({placeholders})")
            ).fetchall()

            if not ops:
                print("❌ No se encontraron las operaciones. Verifica los IDs.")
                sys.exit(1)

            print(f"\n{'='*60}")
            print("OPERACIONES ENCONTRADAS:")
            for op in ops:
                print(f"  ID={op.id} | {op.operation_id} | status={op.status} | "
                      f"USD={op.amount_usd} | PEN={op.amount_pen}")
            print(f"{'='*60}\n")

            # Verificar que estén en estado Completada (solo aviso, no bloquea)
            for op in ops:
                if op.status != 'Completada':
                    print(f"⚠️  {op.operation_id} tiene status '{op.status}' (se procesará igualmente)")

            op_ids = [op.id for op in ops]

            # ── 2. Buscar asientos contables vinculados ───────────────────────
            if op_ids:
                id_list = ','.join(str(i) for i in op_ids)
                journal_entries = db.session.execute(
                    text(f"SELECT id, entry_number, description, total_debe, total_haber "
                         f"FROM journal_entries "
                         f"WHERE source_type='operation' AND source_id IN ({id_list})")
                ).fetchall()
            else:
                journal_entries = []

            if journal_entries:
                print(f"ASIENTOS CONTABLES A ELIMINAR ({len(journal_entries)}):")
                for je in journal_entries:
                    print(f"  JE id={je.id} | {je.entry_number} | {je.description} | "
                          f"Debe={je.total_debe} | Haber={je.total_haber}")
                print()
            else:
                print("ℹ️  No se encontraron asientos contables vinculados.\n")

            # ── 3. Confirmar antes de ejecutar ────────────────────────────────
            print("ACCIONES A REALIZAR:")
            for op in ops:
                print(f"  ✦ {op.operation_id}: Completada → Cancelado, completed_at → NULL")
            if journal_entries:
                je_ids = [je.id for je in journal_entries]
                print(f"  ✦ Eliminar {len(je_ids)} journal_entry_lines de asientos: {je_ids}")
                print(f"  ✦ Eliminar {len(je_ids)} journal_entries: {je_ids}")
            print()

            confirm = input("¿Confirmar? Escribe 'SI' para continuar: ").strip().upper()
            if confirm != 'SI':
                print("Abortado por el usuario.")
                sys.exit(0)

            # ── 4. Ejecutar cambios ───────────────────────────────────────────
            now = datetime.utcnow()

            # 4a. Cancelar operaciones
            for op in ops:
                db.session.execute(text(
                    "UPDATE operations "
                    "SET status='Cancelado', completed_at=NULL, updated_at=:now "
                    "WHERE id=:id"
                ), {'now': now, 'id': op.id})
                print(f"  ✅ {op.operation_id} → Cancelado")

            # 4b. Eliminar líneas de asientos
            if journal_entries:
                je_ids = [je.id for je in journal_entries]
                id_list = ','.join(str(i) for i in je_ids)

                result_lines = db.session.execute(
                    text(f"DELETE FROM journal_entry_lines WHERE journal_entry_id IN ({id_list})")
                )
                print(f"  ✅ Eliminadas {result_lines.rowcount} líneas contables")

                # 4c. Eliminar asientos
                result_je = db.session.execute(
                    text(f"DELETE FROM journal_entries WHERE id IN ({id_list})")
                )
                print(f"  ✅ Eliminados {result_je.rowcount} asientos contables")

            db.session.commit()

            print(f"\n{'='*60}")
            print("✅ ANULACIÓN COMPLETADA EXITOSAMENTE")
            print(f"   Operaciones canceladas: {', '.join(TARGET_OPS)}")
            print(f"   Asientos eliminados: {len(journal_entries)}")
            print(f"   Ejecutado: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
            print(f"{'='*60}\n")

        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERROR — Se hizo rollback de todos los cambios:")
            print(f"   {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    main()

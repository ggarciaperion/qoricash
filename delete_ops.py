#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: No se encontro DATABASE_URL")
    sys.exit(1)

print("Conectando a la base de datos...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM operations"))
        total = result.scalar()
        print(f"Total de operaciones: {total}")

        result = conn.execute(text("""
            SELECT operation_id, status
            FROM operations
            WHERE operation_id != 'EXP-1134'
            ORDER BY created_at DESC
        """))
        ops = result.fetchall()

        print(f"\nSe eliminaran {len(ops)} operaciones:")
        for op in ops:
            print(f"   - {op[0]} ({op[1]})")

        print(f"\nADVERTENCIA: Solo se mantendra EXP-1134")
        confirm = input("Continuar? (SI para confirmar): ")

        if confirm.upper() != 'SI':
            print("Cancelado")
            sys.exit(0)

        print("\nEliminando...")
        result = conn.execute(text("""
            DELETE FROM operations
            WHERE operation_id != 'EXP-1134'
        """))
        conn.commit()

        print(f"Eliminadas: {result.rowcount}")

        result = conn.execute(text("SELECT COUNT(*) FROM operations"))
        remaining = result.scalar()
        print(f"Restantes: {remaining}")

        print("\nCompletado!")

except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)

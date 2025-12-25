#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("ERROR: No se encontro DATABASE_URL")
    sys.exit(1)

print("Creando operacion EXP-1134...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Crear operación
        result = conn.execute(text("""
            INSERT INTO operations (
                operation_id,
                client_id,
                user_id,
                operation_type,
                amount_usd,
                exchange_rate,
                amount_pen,
                source_account,
                destination_account,
                status,
                created_at,
                updated_at,
                in_process_since
            ) VALUES (
                'EXP-1134',
                7,
                1,
                'Compra',
                100.00,
                3.750,
                375.00,
                'BCP - 1234567890',
                'BBVA - 0987654321',
                'En proceso',
                NOW(),
                NOW(),
                NOW()
            )
            RETURNING id, operation_id, status
        """))
        conn.commit()

        op = result.fetchone()
        print(f"Operacion creada exitosamente!")
        print(f"  ID: {op[0]}")
        print(f"  Operation ID: {op[1]}")
        print(f"  Estado: {op[2]}")

except Exception as e:
    print(f"ERROR: {str(e)}")
    sys.exit(1)

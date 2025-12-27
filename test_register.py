"""
Script para probar el endpoint de registro
"""
import requests
import json

url = "https://app.qoricash.pe/api/client/register"

data = {
    "tipo_persona": "Natural",
    "dni": "87654321",
    "email": "juan.perez@example.com",
    "nombres": "Juan",
    "apellido_paterno": "Pérez",
    "apellido_materno": "García",
    "telefono": "+51987654321"
}

print("Enviando petición a:", url)
print("Datos:", json.dumps(data, indent=2))

try:
    response = requests.post(url, json=data)
    print(f"\nStatus Code: {response.status_code}")
    print(f"Response: {response.text}")

    if response.status_code == 201:
        print("\n✅ Registro exitoso!")
    else:
        print("\n❌ Error en el registro")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")

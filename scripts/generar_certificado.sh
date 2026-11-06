#!/usr/bin/env bash
# Genera un certificado TLS autofirmado para la API local (válido 365 días).
# El SAN (subjectAltName) es obligatorio: los clientes modernos ignoran el CN
# y fallan con "hostname mismatch" si localhost/127.0.0.1 no están en el SAN.
set -euo pipefail

DIR_CERTS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/certs"
CRT="$DIR_CERTS/servidor.crt"
KEY="$DIR_CERTS/servidor.key"

mkdir -p "$DIR_CERTS"
if [[ -f "$CRT" && "${1:-}" != "--forzar" ]] && openssl x509 -checkend 86400 -noout -in "$CRT"; then
    echo "[OK] Certificado vigente: $CRT (use --forzar para regenerarlo)"
    exit 0
fi

umask 077  # la llave privada nace sin permisos para grupo/otros
openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 365 \
    -keyout "$KEY" -out "$CRT" \
    -subj "/C=PE/L=Lima/O=IDAT DevOps/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" 2>/dev/null

chmod 600 "$KEY"   # solo el propietario lee la llave privada
chmod 644 "$CRT"   # el certificado es público
echo "[OK] Certificado generado:"
openssl x509 -in "$CRT" -noout -subject -enddate -ext subjectAltName

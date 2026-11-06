#!/usr/bin/env bash
# Controla la API simulada en segundo plano: ./scripts/api.sh {iniciar|detener|estado}
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID="$PROYECTO/logs/api.pid"
PUERTO="${PUERTO:-8443}"

esta_activa() { [[ -f "$PID" ]] && kill -0 "$(cat "$PID")" 2>/dev/null; }

case "${1:-estado}" in
    iniciar)
        if esta_activa; then echo "La API ya está activa (PID $(cat "$PID"))"; exit 0; fi
        cd "$PROYECTO"
        nohup python3 api_simulada/servidor_https.py --puerto "$PUERTO" >> logs/api_consola.log 2>&1 &
        echo $! > "$PID"
        for _ in $(seq 1 20); do   # espera activa hasta que el puerto responda
            if curl -s --cacert certs/servidor.crt "https://localhost:$PUERTO/api/v1/salud" >/dev/null; then
                echo "API iniciada (PID $(cat "$PID")) en https://localhost:$PUERTO/api/v1"; exit 0
            fi
            sleep 0.5
        done
        echo "La API no respondió; revise logs/api_consola.log" >&2; exit 1 ;;
    detener)
        if esta_activa; then kill "$(cat "$PID")" && rm -f "$PID" && echo "API detenida"; else echo "La API no estaba activa"; fi ;;
    estado)
        if esta_activa; then
            echo "Activa (PID $(cat "$PID"))"; ss -tlnp 2>/dev/null | grep ":$PUERTO " || true
        else
            echo "Detenida"
        fi ;;
    *) echo "Uso: $0 {iniciar|detener|estado}" >&2; exit 2 ;;
esac

#!/usr/bin/env bash
# =============================================================================
# setup_entorno.sh - Prepara y asegura el entorno del proyecto de inventario.
#
#   ./scripts/setup_entorno.sh               entorno de usuario (sin sudo)
#   sudo ./scripts/setup_entorno.sh --equipo crea grupo netops + usuario de
#                                            servicio y aplica permisos de grupo
#   ./scripts/setup_entorno.sh --cron        programa el reporte cada hora
#
# Es idempotente: puede ejecutarse varias veces sin duplicar nada.
# =============================================================================
set -euo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRUPO="netops"
USUARIO_SERVICIO="devops_prueba"
PROPIETARIO="${SUDO_USER:-$(id -un)}"
MARCA_CRON="# inventario-red-reporte"

info()  { printf '\033[1;34m[INFO]\033[0m %s\n' "$*"; }
ok()    { printf '\033[1;32m[ OK ]\033[0m %s\n' "$*"; }
error() { printf '\033[1;31m[ERR ]\033[0m %s\n' "$*" >&2; exit 1; }

verificar_dependencias() {
    info "Verificando dependencias"
    local faltan=0
    for cmd in python3 git openssl curl; do
        if command -v "$cmd" >/dev/null; then ok "$cmd -> $(command -v "$cmd")"; else echo "  falta $cmd"; faltan=1; fi
    done
    python3 - <<'PY' || faltan=1
import importlib, sys
for m in ("requests", "yaml"):
    try:
        importlib.import_module(m)
    except ImportError:
        print("  falta el módulo", m, "-> pip3 install -r requirements.txt"); sys.exit(1)
PY
    [[ $faltan -eq 0 ]] || error "Instale las dependencias faltantes"
}

crear_estructura() {
    info "Creando estructura de directorios"
    mkdir -p "$PROYECTO"/{logs,reportes,certs}
    ok "logs/ reportes/ certs/"
}

crear_env() {
    local env="$PROYECTO/.env"
    if [[ -f "$env" ]]; then
        ok ".env ya existe (no se sobrescribe)"
    else
        info "Generando .env con una API key aleatoria"
        ( umask 077
          { echo "# Generado por setup_entorno.sh el $(date '+%F %T') - NO versionar"
            echo "API_BASE_URL=https://localhost:8443/api/v1"
            echo "API_KEY=$(openssl rand -hex 24)"
            echo "API_CA_CERT=$PROYECTO/certs/servidor.crt"
          } > "$env" )
    fi
    chmod 600 "$env"
    ok ".env con permiso $(stat -c '%a' "$env")"
}

aplicar_permisos() {
    info "Aplicando permisos (mínimo privilegio)"
    # Directorios: propietario total, grupo puede entrar y leer, otros nada
    find "$PROYECTO" -path "$PROYECTO/.git" -prune -o -type d -print0 | xargs -0 chmod 750
    # Archivos de código y datos: propietario rw, grupo r
    find "$PROYECTO" -path "$PROYECTO/.git" -prune -o -type f \
        \( -name '*.py' -o -name '*.json' -o -name '*.yaml' -o -name '*.csv' -o -name '*.xml' \
           -o -name '*.md' -o -name '*.txt' -o -name '.gitignore' -o -name '.env.example' \) \
        -print0 | xargs -0 chmod 640
    # Ejecutables: solo los puntos de entrada
    chmod 750 "$PROYECTO/main.py" "$PROYECTO/api_simulada/servidor_https.py" "$PROYECTO"/scripts/*.sh
    # Secretos: solo el propietario
    chmod 600 "$PROYECTO/.env"
    [[ -f "$PROYECTO/certs/servidor.key" ]] && chmod 600 "$PROYECTO/certs/servidor.key"
    # logs/ y reportes/: setgid -> lo que se cree dentro hereda el grupo
    chmod 2770 "$PROYECTO/logs" "$PROYECTO/reportes"
    # El kernel descarta el setgid en silencio si quien ejecuta chmod no es root
    # y no tiene activo el grupo del directorio (usermod -aG exige nueva sesión).
    if [[ ! -g "$PROYECTO/logs" ]]; then
        echo "  [AVISO] setgid no aplicado en logs/: el grupo $(stat -c %G "$PROYECTO/logs") no está"
        echo "          activo en esta sesión. Use 'newgrp $GRUPO', vuelva a iniciar sesión o ejecute con sudo."
    fi
    ok "Permisos aplicados"
}

configurar_equipo() {
    [[ $EUID -eq 0 ]] || error "--equipo requiere sudo"
    info "Configurando grupo '$GRUPO' y usuario de servicio '$USUARIO_SERVICIO'"
    getent group "$GRUPO" >/dev/null || groupadd "$GRUPO"
    if ! id "$USUARIO_SERVICIO" >/dev/null 2>&1; then
        useradd -m -s /bin/bash -c "Cuenta de servicio inventario" "$USUARIO_SERVICIO"
        passwd -l "$USUARIO_SERVICIO" >/dev/null   # sin login por contraseña
    fi
    usermod -aG "$GRUPO" "$USUARIO_SERVICIO"
    usermod -aG "$GRUPO" "$PROPIETARIO"
    chown -R "$PROPIETARIO:$GRUPO" "$PROYECTO"
    echo "  Nota: $PROPIETARIO debe cerrar sesión (o usar 'newgrp $GRUPO') para activar el grupo."
    # el home del propietario debe permitir "atravesarlo" para que el grupo llegue al proyecto
    ok "Miembros de $GRUPO: $(getent group "$GRUPO" | cut -d: -f4)"
}

programar_cron() {
    info "Programando reporte horario en crontab de $PROPIETARIO"
    local linea="0 * * * * cd $PROYECTO && /usr/bin/python3 main.py reporte datos/ --exportar reportes/inventario_\$(date +\\%Y\\%m\\%d_\\%H).json >> logs/cron.log 2>&1 $MARCA_CRON"
    ( crontab -l 2>/dev/null | grep -v "$MARCA_CRON" || true; echo "$linea" ) | crontab -
    ok "$(crontab -l | grep -c "$MARCA_CRON") tarea(s) del inventario en crontab"
}

main() {
    cd "$PROYECTO"
    info "Proyecto: $PROYECTO (propietario: $PROPIETARIO)"
    case "${1:-}" in
        --equipo) configurar_equipo; aplicar_permisos ;;
        --cron)   programar_cron ;;
        "")       verificar_dependencias; crear_estructura; crear_env
                  bash "$PROYECTO/scripts/generar_certificado.sh"; aplicar_permisos ;;
        *)        error "Opción desconocida: $1" ;;
    esac
    ok "Listo"
}

main "$@"

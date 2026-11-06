#!/usr/bin/env bash
# Audita permisos del proyecto y reporta riesgos. Código de salida 1 si hay hallazgos.
set -uo pipefail

PROYECTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
hallazgos=0

echo "== Permisos (octal  simbólico  propietario:grupo  archivo) =="
find "$PROYECTO" -path "$PROYECTO/.git" -prune -o -print0 \
    | xargs -0 stat -c '%a  %A  %U:%G  %n' | sed "s|$PROYECTO/||" | sort -k4

echo
echo "== Archivos escribibles por 'otros' (o+w) =="
if find "$PROYECTO" -path "$PROYECTO/.git" -prune -o -perm -o+w -print | grep -q .; then
    find "$PROYECTO" -path "$PROYECTO/.git" -prune -o -perm -o+w -print; hallazgos=1
else
    echo "ninguno ✓"
fi

echo
echo "== Secretos con permisos distintos de 600 =="
for secreto in "$PROYECTO/.env" "$PROYECTO/certs/servidor.key"; do
    [[ -f "$secreto" ]] || continue
    permiso=$(stat -c '%a' "$secreto")
    if [[ "$permiso" != "600" ]]; then echo "✗ $secreto ($permiso)"; hallazgos=1; else echo "✓ ${secreto#$PROYECTO/} (600)"; fi
done

echo
echo "== Secretos que Git podría versionar =="
if [[ -d "$PROYECTO/.git" ]]; then
    git -C "$PROYECTO" ls-files | grep -E '(^|/)\.env$|\.key$' && hallazgos=1 || echo "ninguno ✓ (.gitignore efectivo)"
fi

echo
[[ $hallazgos -eq 0 ]] && echo "RESULTADO: sin hallazgos" || echo "RESULTADO: revisar hallazgos"
exit $hallazgos

#!/usr/bin/env bash
#
# backup.sh — Backup del database SQLite della cassa festa.
#
# Crea una copia consistente del DB tramite il comando `.backup` di sqlite3
# (sicuro anche con il server in esecuzione) dentro la cartella backups/,
# con timestamp nel nome: festa-YYYYMMDD-HHMMSS.sqlite3
#
# Uso:
#   bash scripts/backup.sh
#
# Va lanciato dalla root del progetto (oppure da qualsiasi cartella: lo script
# si posiziona automaticamente sulla root del progetto).

set -euo pipefail

# Risale alla root del progetto a partire dalla posizione di questo script
# (scripts/ -> root), così funziona indipendentemente dalla cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

DB_PATH="${PROJECT_ROOT}/data/festa.sqlite3"
BACKUP_DIR="${PROJECT_ROOT}/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/festa-${TIMESTAMP}.sqlite3"

# Verifica che sqlite3 sia disponibile.
if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "ERRORE: 'sqlite3' non trovato. Installa con: sudo apt install -y sqlite3" >&2
  exit 1
fi

# Verifica che il DB esista.
if [[ ! -f "${DB_PATH}" ]]; then
  echo "ERRORE: database non trovato: ${DB_PATH}" >&2
  echo "        Inizializzalo con: python scripts/init_db.py" >&2
  exit 1
fi

# Crea la cartella dei backup se manca.
if [[ ! -d "${BACKUP_DIR}" ]]; then
  echo "Creo la cartella backups: ${BACKUP_DIR}"
  mkdir -p "${BACKUP_DIR}"
fi

echo "Backup in corso..."
echo "  Sorgente:    ${DB_PATH}"
echo "  Destinazione: ${BACKUP_FILE}"

# Esegue un backup consistente del database.
sqlite3 "${DB_PATH}" ".backup '${BACKUP_FILE}'"

# Riepilogo finale.
BACKUP_SIZE="$(du -h "${BACKUP_FILE}" | cut -f1)"
echo "OK: backup completato (${BACKUP_SIZE}) -> ${BACKUP_FILE}"

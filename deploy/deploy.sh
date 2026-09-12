#!/usr/bin/env bash
#
# Server-side deploy script for the Odoo 17 service.
# Pulls the configured branch, upgrades any changed Odoo modules,
# then (re)starts the systemd service.
#
# Optional overrides: create ~/.odoo-deploy.env with the variables below.
#
set -euo pipefail

# ---- defaults (override via ~/.odoo-deploy.env) ----
REPO_DIR="${REPO_DIR:-$HOME/odooProjects/odoo17/kemosco}"
ODOO_BASE="${ODOO_BASE:-$HOME/odooProjects/odoo17}"
ODOO_BIN="${ODOO_BIN:-$ODOO_BASE/odoo-bin}"
ODOO_CONF="${ODOO_CONF:-$ODOO_BASE/config/odoo17.conf}"
ODOO_DB="${ODOO_DB:-}"
ODOO_PYTHON="${ODOO_PYTHON:-python3}"
SERVICE="${SERVICE:-odoo17.service}"
BRANCH="${BRANCH:-main}"
# ---------------------------------------------------

# shellcheck source=/dev/null
[ -f "$HOME/.odoo-deploy.env" ] && . "$HOME/.odoo-deploy.env"

log() { printf '\n[deploy] %s\n' "$*"; }

cd "$REPO_DIR"

if [ -n "${DEPLOY_OLD_SHA:-}" ]; then
    # The caller already fetched/updated the working tree.
    OLD="$DEPLOY_OLD_SHA"
    NEW="$(git rev-parse HEAD)"
else
    OLD="$(git rev-parse HEAD)"
    log "Fetching origin/$BRANCH ..."
    git fetch --prune origin
    git reset --hard "origin/$BRANCH"
    NEW="$(git rev-parse HEAD)"
fi

if [ "$OLD" = "$NEW" ]; then
    log "Working tree already at $NEW."
fi

# Modules changed on the server between the deployed and the new revision.
SERVER_MODULES="$(
    git diff --name-only "$OLD" "$NEW" \
    | awk -F/ '{print $1}' \
    | sort -u \
    | while read -r d; do
          if [ -f "$REPO_DIR/$d/__manifest__.py" ]; then
              echo "$d"
          fi
      done
)"

# Modules reported by CI for this push (keeps retries idempotent).
CI_MODULES=""
if [ "${DEPLOY_MODULES+set}" = "set" ] && [ "$DEPLOY_MODULES" != "auto" ] && [ -n "$DEPLOY_MODULES" ]; then
    CI_MODULES="$(printf '%s' "$DEPLOY_MODULES" | tr ',' '\n')"
fi

MODULES="$(printf '%s\n%s\n' "$SERVER_MODULES" "$CI_MODULES" \
    | sed '/^[[:space:]]*$/d' | sort -u | tr '\n' ',' | sed 's/,$//')"

if [ -z "$MODULES" ] && [ "$OLD" = "$NEW" ]; then
    log "Already up to date ($NEW). Nothing to do."
    exit 0
fi
log "Deploying $OLD -> $NEW"
log "Modules to upgrade: ${MODULES:-<none>}"

if [ -n "$MODULES" ] && [ -n "$ODOO_DB" ]; then
    log "Upgrading changed modules: $MODULES"
    sudo systemctl stop "$SERVICE"
    start_service() { sudo systemctl start "$SERVICE"; }
    trap start_service EXIT
    "$ODOO_PYTHON" "$ODOO_BIN" -c "$ODOO_CONF" -d "$ODOO_DB" \
        -u "$MODULES" --stop-after-init --no-http
    trap - EXIT
    start_service
    log "Modules upgraded and service started."
else
    if [ -n "$MODULES" ] && [ -z "$ODOO_DB" ]; then
        log "WARNING: modules changed ($MODULES) but ODOO_DB is not set -> restart only."
    fi
    log "Restarting $SERVICE ..."
    sudo systemctl restart "$SERVICE"
fi

log "Done. Now at $NEW"

#!/usr/bin/env bash
#
# Runs on the server (piped over SSH from the workflow).
# Pulls the latest main and hands off to deploy/deploy.sh.
#
set -euo pipefail

REPO="$HOME/odooProjects/odoo17/kemosco"
cd "$REPO"

OLD="$(git rev-parse HEAD)"
git fetch --prune origin
git reset --hard origin/main

DEPLOY_OLD_SHA="$OLD" bash deploy/deploy.sh

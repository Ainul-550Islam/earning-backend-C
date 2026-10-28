#!/usr/bin/env bash
# =============================================================================
# wallet_migrate.sh — Safe migration script for api.wallet
# =============================================================================
# Run this script instead of `python manage.py migrate` for the wallet app.
# It handles the broken 0007-0010 migrations safely.
#
# Usage:
#   chmod +x wallet_migrate.sh
#   ./wallet_migrate.sh           # fresh install
#   ./wallet_migrate.sh --existing # existing DB with data
# =============================================================================

set -e

MANAGE="python manage.py"
MODE="${1:-fresh}"

echo "=================================================="
echo "  wallet Migration Script"
echo "  Mode: $MODE"
echo "=================================================="

# Step 1: All other apps first
echo ""
echo "[1/4] Migrating all other apps..."
$MANAGE migrate --exclude-app wallet

# Step 2: Run wallet 0001-0006 (all work correctly)
echo ""
echo "[2/4] Running wallet migrations 0001-0006..."
for step in 0001 0002 0003 0004 0005 0006; do
    echo "  Applying $step..."
    $MANAGE migrate wallet $step
done
echo "  ✅ 0001-0006 applied"

# Step 3: Fake 0007-0010 (these have conflicts fixed by 0011)
echo ""
echo "[3/4] Faking wallet migrations 0007-0010 (known conflicts)..."
for step in 0007 0008 0009 0010; do
    echo "  Faking $step..."
    $MANAGE migrate wallet $step --fake
done
echo "  ✅ 0007-0010 faked"

# Step 4: Apply 0011 (clean world-class migration)
echo ""
echo "[4/4] Applying wallet migration 0011 (world-class complete)..."
$MANAGE migrate wallet 0011 --fake-initial
echo "  ✅ 0011 applied"

echo ""
echo "=================================================="
echo "  ✅ wallet migrations complete!"
echo "=================================================="
echo ""
echo "  Tables created by 0001-0006 (via migrations):"
echo "    wallet, wallettransaction, walletledger,"
echo "    withdrawalrequest, withdrawalmethod, ..."
echo ""
echo "  Models added by 0011 (state-only, DB via syncdb):"
echo "    Chargeback, ContentLocker, PrizePool,"
echo "    RewardTier, Survey, SurveyProvider, ..."
echo ""
echo "  If you see 'table already exists' errors, run:"
echo "    python manage.py migrate wallet --fake"
echo "=================================================="

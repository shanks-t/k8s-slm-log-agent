#!/usr/bin/env bash
#
# Enable passwordless sudo for user 'trey' on Ubuntu
# Safe, idempotent, and validated with visudo
#

set -euo pipefail

USER_TO_CONFIG="trey"
SUDOERS_FILE="/etc/sudoers.d/${USER_TO_CONFIG}"

echo "=== Passwordless sudo setup for user: ${USER_TO_CONFIG} ==="

# 1. Ensure user exists
if ! id "${USER_TO_CONFIG}" &>/dev/null; then
    echo "ERROR: User '${USER_TO_CONFIG}' does not exist."
    exit 1
fi

# 2. Ensure user is in sudo group
if groups "${USER_TO_CONFIG}" | grep -q "\bsudo\b"; then
    echo "[OK] User '${USER_TO_CONFIG}' already in 'sudo' group."
else
    echo "Adding '${USER_TO_CONFIG}' to sudo group..."
    sudo usermod -aG sudo "${USER_TO_CONFIG}"
    echo "[OK] Added to sudo group."
fi

# 3. Create sudoers drop-in file
echo "Configuring passwordless sudo in ${SUDOERS_FILE}..."

# Backup old file if exists
if [ -f "${SUDOERS_FILE}" ]; then
    sudo cp "${SUDOERS_FILE}" "${SUDOERS_FILE}.bak.$(date +%s)"
    echo "Backup of existing sudoers file created."
fi

# Write rule
echo "${USER_TO_CONFIG} ALL=(ALL) NOPASSWD:ALL" | sudo tee "${SUDOERS_FILE}" >/dev/null

# 4. Set correct permissions
sudo chmod 440 "${SUDOERS_FILE}"

# 5. Syntax validate the new sudoers file
if sudo visudo -c -f "${SUDOERS_FILE}" >/dev/null 2>&1; then
    echo "[OK] sudoers file syntax validated."
else
    echo "ERROR: sudoers file has invalid syntax. Restoring backup..."
    sudo mv "${SUDOERS_FILE}.bak" "${SUDOERS_FILE}"
    exit 1
fi

echo "=== Passwordless sudo configured successfully. ==="

echo
echo "Verification:"
echo "  Run: sudo -k"
echo "  Then: sudo id"
echo "  → You should NOT be prompted for your password."
echo

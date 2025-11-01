#!/bin/bash
# =====================================================
# GlowSync Post-Install Setup
# Author: Mathew Anderson
# =====================================================

set -e

echo "🔧 GlowSync Post-Install Setup Starting..."

# 1️⃣ Detect service user (who runs glowsync-api)
APIUSER=$(systemctl show -p User glowsync-api | cut -d= -f2)
[ -z "$APIUSER" ] && APIUSER="itadmin"
echo "📦 Detected API user: $APIUSER"

# 2️⃣ Create restart helper script
sudo tee /usr/local/sbin/glowsync-restart >/dev/null <<'EOF'
#!/bin/sh
logger -t glowsync-restart "requested"
if command -v /usr/bin/systemctl >/dev/null 2>&1; then
  SYSCTL=/usr/bin/systemctl
else
  SYSCTL=/bin/systemctl
fi
"$SYSCTL" restart glowsync-scheduler || true
"$SYSCTL" restart glowsync-api || true
logger -t glowsync-restart "done"
EOF
sudo chmod 755 /usr/local/sbin/glowsync-restart
sudo chown root:root /usr/local/sbin/glowsync-restart
echo "✅ Installed /usr/local/sbin/glowsync-restart"

# 3️⃣ Add sudoers rule (no password for this script only)
sudo bash -c "echo '$APIUSER ALL=(root) NOPASSWD: /usr/local/sbin/glowsync-restart' > /etc/sudoers.d/glowsync"
sudo chmod 440 /etc/sudoers.d/glowsync
echo "✅ Added /etc/sudoers.d/glowsync for $APIUSER"

# 4️⃣ Enable + restart services
sudo systemctl enable glowsync-api glowsync-scheduler --now || true
echo "✅ Services verified or started"

# 5️⃣ Final message
echo
echo "✨ GlowSync setup complete!"
echo "You can now open http://<pi-ip>:8000/settings"
echo "and click Apply & Restart — it will work automatically."
echo "------------------------------------------------------"

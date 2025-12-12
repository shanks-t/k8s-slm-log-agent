#!/bin/bash

echo "=========================================="
echo "  Kubernetes Prerequisites Verification"
echo "=========================================="
echo ""

echo "1. SWAP STATUS (should be disabled)"
echo "-----------------------------------"
free -h | grep Swap
SWAP_TOTAL=$(free -m | grep Swap | awk '{print $2}')
if [ "$SWAP_TOTAL" -eq 0 ]; then
    echo "✅ PASS: Swap is disabled"
else
    echo "❌ FAIL: Swap is still enabled ($SWAP_TOTAL MB)"
fi
echo ""

echo "2. KERNEL MODULES (should be loaded)"
echo "-----------------------------------"
echo "Checking overlay module..."
if lsmod | grep -q overlay; then
    echo "✅ PASS: overlay module is loaded"
    lsmod | grep overlay
else
    echo "❌ FAIL: overlay module is NOT loaded"
fi
echo ""

echo "Checking br_netfilter module..."
if lsmod | grep -q br_netfilter; then
    echo "✅ PASS: br_netfilter module is loaded"
    lsmod | grep br_netfilter
else
    echo "❌ FAIL: br_netfilter module is NOT loaded"
fi
echo ""

echo "3. SYSCTL PARAMETERS (all should = 1)"
echo "-----------------------------------"
echo "Checking net.bridge.bridge-nf-call-iptables..."
IPTABLES=$(sysctl -n net.bridge.bridge-nf-call-iptables 2>/dev/null)
if [ "$IPTABLES" = "1" ]; then
    echo "✅ PASS: net.bridge.bridge-nf-call-iptables = 1"
else
    echo "❌ FAIL: net.bridge.bridge-nf-call-iptables = $IPTABLES (should be 1)"
fi

echo "Checking net.bridge.bridge-nf-call-ip6tables..."
IP6TABLES=$(sysctl -n net.bridge.bridge-nf-call-ip6tables 2>/dev/null)
if [ "$IP6TABLES" = "1" ]; then
    echo "✅ PASS: net.bridge.bridge-nf-call-ip6tables = 1"
else
    echo "❌ FAIL: net.bridge.bridge-nf-call-ip6tables = $IP6TABLES (should be 1)"
fi

echo "Checking net.ipv4.ip_forward..."
FORWARD=$(sysctl -n net.ipv4.ip_forward 2>/dev/null)
if [ "$FORWARD" = "1" ]; then
    echo "✅ PASS: net.ipv4.ip_forward = 1"
else
    echo "❌ FAIL: net.ipv4.ip_forward = $FORWARD (should be 1)"
fi
echo ""

echo "4. CONFIGURATION FILES (should exist)"
echo "-----------------------------------"
if [ -f /etc/modules-load.d/k8s.conf ]; then
    echo "✅ PASS: /etc/modules-load.d/k8s.conf exists"
    echo "Contents:"
    cat /etc/modules-load.d/k8s.conf
else
    echo "❌ FAIL: /etc/modules-load.d/k8s.conf not found"
fi
echo ""

if [ -f /etc/sysctl.d/k8s.conf ]; then
    echo "✅ PASS: /etc/sysctl.d/k8s.conf exists"
    echo "Contents:"
    cat /etc/sysctl.d/k8s.conf
else
    echo "❌ FAIL: /etc/sysctl.d/k8s.conf not found"
fi
echo ""

echo "=========================================="
echo "  Verification Complete"
echo "=========================================="
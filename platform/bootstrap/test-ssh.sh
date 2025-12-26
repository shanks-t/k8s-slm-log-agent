#!/bin/bash

echo "Testing SSH on potential Mini PC IPs..."

for ip in 10.0.0.78 10.0.0.123 10.0.0.154; do
	echo -e "\n=== Testing $ip ==="

	# Test if port 22 (SSH) is open
	timeout 2 bash -c "cat < /dev/null > /dev/tcp/$ip/22" 2>/dev/null

	if [ $? -eq 0 ]; then
		echo "✓ SSH port is open on $ip"
		echo "Try: ssh root@$ip or ssh ubuntu@$ip"
	else
		echo "✗ SSH port closed or filtered on $ip"
	fi
done

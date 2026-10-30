#!/bin/bash
# verify-inbound-setup.sh - Verify SendGrid Inbound Parse configuration
#
# Usage: ./verify-inbound-setup.sh <hostname>
#
# Examples:
#   ./verify-inbound-setup.sh parse.example.com

set -e

# Help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
  echo "Usage: $0 <hostname>"
  echo ""
  echo "Verify SendGrid Inbound Parse configuration:"
  echo "  1. Check MX record points to mx.sendgrid.net"
  echo "  DNS-only: active webhook probing is disabled."
  echo ""
  echo "Examples:"
  echo "  $0 parse.example.com"
  echo "Webhook accessibility and authentication are not tested."
  exit 0
fi

# Reject the removed capability before any DNS or HTTP operation. Do not silently
# ignore old URL arguments: callers must know no endpoint was tested.
if [[ $# -gt 1 ]]; then
  echo "Error: Active webhook probing is disabled. Use: $0 <hostname>" >&2
  echo "Review an owned, trusted HTTPS endpoint separately; this helper checks MX only." >&2
  exit 1
fi

# Validate hostname
if [[ -z "$1" ]]; then
  echo "❌ Error: Hostname required"
  echo "Usage: $0 <hostname>"
  exit 1
fi

HOSTNAME="$1"

# Security: Validate HOSTNAME to prevent shell injection.
# Only alphanumeric characters, dots, and hyphens are permitted.
# This blocks shell metacharacters and ensures dig/nslookup receive safe input.
if [[ ! "$HOSTNAME" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?$ ]]; then
  echo "❌ Error: Invalid hostname. Only letters, numbers, dots, and hyphens are allowed."
  exit 1
fi

echo "🔍 Verifying Inbound Parse setup for: $HOSTNAME"
echo ""

# Check if dig is available
if ! command -v dig &> /dev/null; then
  echo "⚠️  Warning: 'dig' command not found, using 'nslookup' instead"
  USE_NSLOOKUP=1
fi

# Check MX record
echo "📝 Checking MX record..."
if [[ -n "$USE_NSLOOKUP" ]]; then
  MX_RECORDS=$(nslookup -type=MX "$HOSTNAME" 2>&1 | grep "mail exchanger" || true)
else
  MX_RECORDS=$(dig +short MX "$HOSTNAME" 2>&1 || true)
fi

if [[ -z "$MX_RECORDS" ]]; then
  echo "❌ Error: No MX records found for $HOSTNAME"
  echo ""
  echo "Expected MX record:"
  echo "  Type: MX"
  echo "  Host: $HOSTNAME"
  echo "  Priority: 10"
  echo "  Value: mx.sendgrid.net"
  echo ""
  echo "Note: DNS propagation can take 24-48 hours"
  exit 1
fi

echo "✅ MX records found:"
echo "$MX_RECORDS"
echo ""

# Check if mx.sendgrid.net is in records
if echo "$MX_RECORDS" | grep -q "mx.sendgrid.net"; then
  echo "✅ MX record correctly points to mx.sendgrid.net"
else
  echo "⚠️  Warning: MX record does not point to mx.sendgrid.net"
  echo ""
  echo "Expected: mx.sendgrid.net"
  echo "Found: $MX_RECORDS"
  echo ""
  echo "Update your MX record to:"
  echo "  Type: MX"
  echo "  Host: $HOSTNAME"
  echo "  Priority: 10"
  echo "  Value: mx.sendgrid.net"
  exit 1
fi

echo ""

# Summary
echo "📋 Summary:"
echo "  ✅ MX record configured correctly"
echo "  Webhook accessibility and authentication were not tested."
echo ""
echo "Next steps:"
echo "  1. Configure Inbound Parse in SendGrid Console"
echo "     → Settings → Inbound Parse → Add Host & URL"
echo "  2. Set Hostname: $HOSTNAME"
echo "  3. Review an owned, trusted HTTPS destination and its authentication separately."
echo "  4. Only after recipient/content approval, send a live test email to an address you control."
echo ""
echo "Note: DNS propagation can take up to 48 hours"

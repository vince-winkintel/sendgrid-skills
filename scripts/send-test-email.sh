#!/bin/bash
# send-test-email.sh - Send a test email via SendGrid to validate configuration
# LIVE SEND: obtain approval for sender, all recipients and exact content first.
# Recipient/content data goes to SendGrid; minimize sensitive data. Mail Send key only.
#
# Usage: ./send-test-email.sh <recipient-email> [subject] [message]
#
# Examples:
#   ./send-test-email.sh vince@example.com
#   ./send-test-email.sh vince@example.com "Test Subject" "Test message body"

set -e

# Help
if [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
  echo "Usage: $0 <recipient-email> [subject] [message]"
  echo ""
  echo "Send a test email via SendGrid to validate API key and configuration."
  echo "LIVE SEND: approve sender, recipients and exact content before running."
  echo "Data goes to SendGrid and recipients; minimize sensitive data. Use a Mail Send-only key."
  echo "Requires curl and jq. This helper has no dry-run or approval prompt."
  echo ""
  echo "Examples:"
  echo "  $0 vince@example.com"
  echo "  $0 vince@example.com \"Test Subject\" \"Test message\""
  echo ""
  echo "Environment variables:"
  echo "  SENDGRID_API_KEY - SendGrid API key (required)"
  echo "  SENDGRID_FROM    - Sender email (default: test@example.com)"
  exit 0
fi

# Validate API key
if [[ -z "$SENDGRID_API_KEY" ]]; then
  echo "❌ Error: SENDGRID_API_KEY environment variable not set"
  echo ""
  echo "Get your API key at: https://app.sendgrid.com/settings/api_keys"
  echo "Then set it: export SENDGRID_API_KEY=SG.xxxxxxxxx"
  exit 1
fi

# Validate recipient
if [[ -z "$1" ]]; then
  echo "❌ Error: Recipient email required"
  echo "Usage: $0 <recipient-email> [subject] [message]"
  exit 1
fi

RECIPIENT="$1"
SUBJECT="${2:-SendGrid Test Email}"
MESSAGE="${3:-This is a test email sent via SendGrid API to validate configuration.}"
FROM="${SENDGRID_FROM:-test@example.com}"

echo "LIVE SEND: sending approved recipient/content data to SendGrid. No dry-run."
echo "📧 Sending test email..."
echo "  From: $FROM"
echo "  To: $RECIPIENT"
echo "  Subject: $SUBJECT"
echo ""

# Encode every input as data before opening a connection. jq failure stops the send.
JSON_PAYLOAD=$(jq -n \
  --arg to "$RECIPIENT" \
  --arg from "$FROM" \
  --arg subject "$SUBJECT" \
  --arg message "$MESSAGE" \
  '{
    personalizations: [{to: [{email: $to}]}],
    from: {email: $from},
    subject: $subject,
    content: [
      {type: "text/plain", value: $message},
      {type: "text/html", value: ("<p>" + ($message | gsub("&"; "&amp;") | gsub("<"; "&lt;") | gsub(">"; "&gt;")) + "</p>")}
    ]
  }')

# Send email via SendGrid API
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST \
  https://api.sendgrid.com/v3/mail/send \
  -H "Authorization: Bearer $SENDGRID_API_KEY" \
  -H "Content-Type: application/json" \
  --data-binary "$JSON_PAYLOAD")

# Extract status code and body
HTTP_CODE=${RESPONSE##*$'\n'}
BODY=${RESPONSE%$'\n'*}

# Check response
if [[ "$HTTP_CODE" == "202" ]]; then
  echo "✅ Success! Email queued for delivery (HTTP $HTTP_CODE)"
  echo ""
  echo "Note: Check recipient inbox/spam folder in ~1 minute"
elif [[ "$HTTP_CODE" == "401" ]]; then
  echo "❌ Error: Unauthorized (HTTP $HTTP_CODE)"
  echo "API key is invalid or missing Mail Send permissions"
  echo ""
  echo "Response: $BODY"
  exit 1
elif [[ "$HTTP_CODE" == "403" ]]; then
  echo "❌ Error: Forbidden (HTTP $HTTP_CODE)"
  echo "Sender email '$FROM' may not be verified"
  echo ""
  echo "Verify sender at: https://app.sendgrid.com/settings/sender_auth"
  echo ""
  echo "Response: $BODY"
  exit 1
else
  echo "❌ Error: Unexpected response (HTTP $HTTP_CODE)"
  echo ""
  echo "Response: $BODY"
  exit 1
fi

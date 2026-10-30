# Installation (SendGrid SDK)

**Live-send safety:** these examples send real email through SendGrid and may incur charges. Obtain approval for the sender, all To/CC/BCC recipients, exact subject/body, template data and attachments before running them. Recipient data, content and attachments go to SendGrid and recipients. Minimize personal data; never include secrets, regulated data or sensitive files without authorization. Read only approved attachment/HTML files. Use a Mail Send-only API key from the environment and never print it. Use recipients you control for approved tests; example addresses are placeholders, not delivery approval.

## Node.js / TypeScript

```bash
pnpm add @sendgrid/mail
```

```ts
import sgMail from '@sendgrid/mail';
sgMail.setApiKey(process.env.SENDGRID_API_KEY!);
```

## Python

```bash
pip install sendgrid
```

```py
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
```

## Go

```bash
go get github.com/sendgrid/sendgrid-go
```

```go
import (
  "os"
  "github.com/sendgrid/sendgrid-go"
  "github.com/sendgrid/sendgrid-go/helpers/mail"
)

sg := sendgrid.NewSendClient(os.Getenv("SENDGRID_API_KEY"))
```

## PHP

```bash
composer require sendgrid/sendgrid
```

## Ruby

```bash
gem install sendgrid-ruby
```

## Java

```xml
<dependency>
  <groupId>com.sendgrid</groupId>
  <artifactId>sendgrid-java</artifactId>
  <version>4.10.3</version>
</dependency>
```

## C# (.NET)

```bash
dotnet add package SendGrid
```

## cURL

**Live POST:** sends message data to SendGrid and attempts delivery. Approve recipients and content first.

```bash
curl -X POST "https://api.sendgrid.com/v3/mail/send" \
  -H "Authorization: Bearer $SENDGRID_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"personalizations":[{"to":[{"email":"test@example.com"}]}],"from":{"email":"support@example.com"},"subject":"Hello","content":[{"type":"text/plain","value":"Hi"}]}'
```

## Templates (Dynamic)

Dynamic templates are referenced by `template_id` and optional `dynamic_template_data`.
See: <https://docs.sendgrid.com/ui/sending-email/how-to-send-an-email-with-dynamic-templates>

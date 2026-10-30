# Single Email Examples (SendGrid)

**Live-send safety:** these examples send real email through SendGrid and may incur charges. Obtain approval for the sender, all To/CC/BCC recipients, exact subject/body, template data and attachments before running them. Recipient data, content and attachments go to SendGrid and recipients. Minimize personal data; never include secrets, regulated data or sensitive files without authorization. Read only approved attachment/HTML files. Use a Mail Send-only API key from the environment and never print it. Use recipients you control for approved tests; example addresses are placeholders, not delivery approval.

## Node.js / TypeScript

```ts
import sgMail from '@sendgrid/mail';

sgMail.setApiKey(process.env.SENDGRID_API_KEY!);

await sgMail.send({
  from: 'Support <support@example.com>',
  to: ['test@example.com'],
  cc: ['cc@example.com'],
  bcc: ['bcc@example.com'],
  replyTo: 'support@example.com',
  subject: 'SendGrid test',
  text: 'Plain text body',
  html: '<p>HTML body</p>',
  attachments: [
    {
      filename: 'hello.txt',
      content: Buffer.from('hello').toString('base64'),
      type: 'text/plain',
      disposition: 'attachment',
    }
  ]
});
```

### Dynamic Template (Node)

```ts
await sgMail.send({
  from: 'Support <support@example.com>',
  to: ['test@example.com'],
  templateId: 'd-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
  dynamicTemplateData: { first_name: 'Vince' }
});
```

## Python

```py
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Cc, Bcc, ReplyTo, Attachment, FileContent, FileName, FileType, Disposition

message = Mail(
    from_email=Email('support@example.com'),
    to_emails=To('test@example.com'),
    subject='SendGrid test',
    plain_text_content='Plain text body',
    html_content='<p>HTML body</p>'
)
message.add_cc(Cc('cc@example.com'))
message.add_bcc(Bcc('bcc@example.com'))
message.reply_to = ReplyTo('support@example.com')

attachment = Attachment(
    FileContent('aGVsbG8='),
    FileName('hello.txt'),
    FileType('text/plain'),
    Disposition('attachment')
)
message.add_attachment(attachment)

sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
response = sg.send(message)
```

### Dynamic Template (Python)

```py
message = Mail(
    from_email='support@example.com',
    to_emails='test@example.com'
)
message.template_id = 'd-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
message.dynamic_template_data = {'first_name': 'Vince'}

sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
sg.send(message)
```

## cURL

**Live POST:** the following commands send to every listed To/CC/BCC recipient. Review the exact content and attachment before approving.

```bash
curl -X POST "https://api.sendgrid.com/v3/mail/send" \
  -H "Authorization: Bearer $SENDGRID_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"personalizations":[{"to":[{"email":"test@example.com"}],"cc":[{"email":"cc@example.com"}],"bcc":[{"email":"bcc@example.com"}]}],"from":{"email":"support@example.com"},"reply_to":{"email":"support@example.com"},"subject":"SendGrid test","content":[{"type":"text/plain","value":"Plain text body"},{"type":"text/html","value":"<p>HTML body</p>"}],"attachments":[{"content":"aGVsbG8=","type":"text/plain","filename":"hello.txt","disposition":"attachment"}]}'
```

### Dynamic Template (cURL)

**Live POST:** approve the selected template, recipient and template data first.

```bash
curl -X POST "https://api.sendgrid.com/v3/mail/send" \
  -H "Authorization: Bearer $SENDGRID_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"from":{"email":"support@example.com"},"personalizations":[{"to":[{"email":"test@example.com"}],"dynamic_template_data":{"first_name":"Vince"}}],"template_id":"d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"}'
```

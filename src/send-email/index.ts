import sgMail from '@sendgrid/mail';

export interface SendEmailInput {
  from: string;
  to: string | string[];
  subject: string;
  text?: string;
  html?: string;
  attachments?: Array<{
    filename: string;
    content: string; // base64-encoded
    type?: string;
    disposition?: string;
  }>;
}

export interface SendEmailResult {
  success: boolean;
  message?: string;
}

export async function sendEmail(input: SendEmailInput): Promise<SendEmailResult> {
  const apiKey = process.env.SENDGRID_API_KEY;
  if (!apiKey) {
    throw new Error('SENDGRID_API_KEY is not set');
  }

  sgMail.setApiKey(apiKey);

  if (!input.text && !input.html) {
    throw new Error('Either text or html body must be provided');
  }

  const msg: sgMail.MailDataRequired = input.html
    ? {
        from: input.from,
        to: input.to,
        subject: input.subject,
        html: input.html,
        text: input.text,
        attachments: input.attachments,
      }
    : {
        from: input.from,
        to: input.to,
        subject: input.subject,
        text: input.text!,
        attachments: input.attachments,
      };

  await sgMail.send(msg);

  return { success: true, message: 'Email sent via SendGrid' };
}

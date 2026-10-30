"""Offline integration tests: real helpers/encoders, recording transports only.

Run: python3 tests/test_security.py --scratch /path/to/scratch -v
Use --root /path/to/export to test a baseline without changing the worktree.
"""
import argparse
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


options = argparse.ArgumentParser(add_help=False)
options.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
options.add_argument("--scratch", type=Path, required=True)
OPTIONS, TEST_ARGS = options.parse_known_args()
ROOT = OPTIONS.root.resolve()

# All network-facing commands available to the helpers are recording doubles.
# jq, shell utilities and the local Node parser remain real.
TRANSPORT = r'''
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
body = sys.stdin.read() if "@-" in args else ""
with open(os.environ["RECORD"], "a") as f:
    f.write(json.dumps({"tool": name, "args": args, "stdin": body}) + "\n")
if name == "curl":
    print(os.environ.get("RESPONSE_BODY", ""))
    print(os.environ.get("HTTP_STATUS", "202"), end="")
    sys.exit(int(os.environ.get("CURL_EXIT", "0")))
if name == "dig":
    print(os.environ.get("MX_RECORDS", "10 mx.sendgrid.net.") if "MX" in args
          else os.environ.get("ADDRESS_RECORDS", "127.0.0.1"))
elif name == "nslookup":
    print("parse.example.com mail exchanger = " + os.environ.get("MX_RECORDS", "10 mx.sendgrid.net."))
else:
    print(os.environ.get("ADDRESS_RECORDS", "127.0.0.1"))
'''


class HelperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sendgrid-test-", dir=OPTIONS.scratch)
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.record = self.work / "transport.jsonl"
        for name in ("bash", "jq", "node", "cat", "head", "tail", "grep", "basename", "realpath"):
            executable = shutil.which(name)
            if not executable:
                self.fail("Required test dependency missing: " + name)
            (self.bin / name).symlink_to(executable)
        for name in ("curl", "dig", "nslookup", "host", "getent", "wget"):
            path = self.bin / name
            path.write_text("#!" + sys.executable + "\n" + TRANSPORT)
            path.chmod(0o755)
        # Do not inherit credentials, proxy configuration, shell hooks or user HOME.
        self.env = {
            "PATH": str(self.bin), "HOME": str(self.work), "TMPDIR": str(self.work),
            "LC_ALL": "C", "RECORD": str(self.record),
            "SENDGRID_API_KEY": "SG.synthetic-regression-only",
            "SENDGRID_FROM": "sender@example.com",
        }

    def run_helper(self, name, *args, input=None):
        runtime = "node" if name.endswith(".js") else "bash"
        return subprocess.run([str(self.bin / runtime), str(ROOT / "scripts" / name), *args],
                              input=input, capture_output=True, text=True, env=self.env,
                              cwd=self.work, timeout=10)

    def calls(self):
        return [json.loads(line) for line in self.record.read_text().splitlines()] if self.record.exists() else []

    def payload(self):
        calls = self.calls()
        self.assertEqual(len(calls), 1, calls)
        call = calls[0]
        self.assertEqual(call["tool"], "curl")
        args = call["args"]
        self.assertIn("https://api.sendgrid.com/v3/mail/send", args)
        self.assertIn("Authorization: Bearer SG.synthetic-regression-only", args)
        self.assertIn("Content-Type: application/json", args)
        self.assertIn("POST", args)
        flag = next(flag for flag in ("--data-binary", "--data", "-d") if flag in args)
        data = args[args.index(flag) + 1]
        try:
            return json.loads(call["stdin"] if data == "@-" else data)
        except json.JSONDecodeError as error:
            self.fail("Helper emitted invalid JSON: " + str(error))

    def test_test_email_values_remain_data(self):
        recipient = 'quoted"\\\t\r\n雪@example.com'
        sender = 'sender"\\\t\r\n😀@example.com'
        subject = 'Hello" , "bcc": [{"email":"injected@example.com"}], "x":"\\\t\r\n雪'
        message = 'Line "one"\\\t\r\n雪 😀\b\f $(touch NEVER) `id`'
        self.env["SENDGRID_FROM"] = sender
        result = self.run_helper("send-test-email.sh", recipient, subject, message)
        payload = self.payload()
        self.assertEqual(payload, {
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": {"email": sender}, "subject": subject,
            "content": [{"type": "text/plain", "value": message},
                        {"type": "text/html", "value": "<p>" + message + "</p>"}],
        })
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse((self.work / "NEVER").exists())

    def test_plain_message_is_not_html_markup(self):
        result = self.run_helper("send-test-email.sh", "test@example.com", "Test", '<a href="x">Tom & Jo</a>')
        self.assertEqual(self.payload()["content"], [
            {"type": "text/plain", "value": '<a href="x">Tom & Jo</a>'},
            {"type": "text/html", "value": '<p>&lt;a href="x"&gt;Tom &amp; Jo&lt;/a&gt;</p>'},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_html_helper_preserves_encoded_data_and_success(self):
        html = '<p title="quoted">雪 & more\\\nsecond\tline</p>'
        result = self.run_helper("send-html-email.sh", "test@example.com", 'Test "quotes"', html)
        self.assertEqual(self.payload(), {
            "personalizations": [{"to": [{"email": "test@example.com"}]}],
            "from": {"email": "sender@example.com"}, "subject": 'Test "quotes"',
            "content": [{"type": "text/html", "value": html}],
        })
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_webhook_arguments_are_rejected_before_any_network(self):
        # The boundary removes probing, rather than classifying addresses. Even
        # mixed/rebinding DNS fixtures must never be consulted or connected to.
        cases = [
            ("https://127.0.0.1/", "127.0.0.1"),
            ("https://localhost/", "::1"),
            ("https://10.0.0.1/", "10.0.0.1"),
            ("https://172.16.0.1/", "172.16.0.1"),
            ("https://192.168.1.1/", "192.168.1.1"),
            ("https://169.254.169.254/", "169.254.169.254"),
            ("https://100.64.0.1/", "100.64.0.1"),
            ("https://192.0.2.1/", "192.0.2.1"),
            ("https://0.0.0.0/", "0.0.0.0"),
            ("https://224.0.0.1/", "224.0.0.1"),
            ("https://240.0.0.1/", "240.0.0.1"),
            ("https://2130706433/", "127.0.0.1"),
            ("https://0177.0.0.1/", "127.0.0.1"),
            ("https://0x7f000001/", "127.0.0.1"),
            ("https://127.1/", "127.0.0.1"),
            ("https://[::1]/", "::1"),
            ("https://[::ffff:127.0.0.1]/", "::ffff:127.0.0.1"),
            ("https://[fc00::1]/", "fc00::1"),
            ("https://[fe80::1%25eth0]/", "fe80::1"),
            ("https://[2001:db8::1]/", "2001:db8::1"),
            ("https://mixed.example/", "93.184.216.34\n10.0.0.1\n::1"),
            ("https://rebind.example/", "93.184.216.34\n127.0.0.1"),
            ("https://service.internal/", "192.168.1.2"),
            ("https://public.example/redirect", "93.184.216.34"),
            ("https://public.example@127.0.0.1/", "127.0.0.1"),
            ("http://127.0.0.1/", "127.0.0.1"),
            ("file:///synthetic-only", ""),
            ("--help", ""), ("", ""),
        ]
        for url, addresses in cases:
            with self.subTest(url=url):
                if self.record.exists():
                    self.record.unlink()
                self.env.update({"ADDRESS_RECORDS": addresses,
                                 "HTTP_STATUS": "302",
                                 "https_proxy": "http://127.0.0.1:8080",
                                 "HTTPS_PROXY": "http://127.0.0.1:8080",
                                 "ALL_PROXY": "socks5://127.0.0.1:1080"})
                result = self.run_helper("verify-inbound-setup.sh", "parse.example.com", url)
                self.assertEqual(self.calls(), [], "Rejected URL must not cause DNS or HTTP calls")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("disabled", result.stdout + result.stderr)

    def test_mx_check_uses_only_dns_and_does_not_claim_webhook_tested(self):
        result = self.run_helper("verify-inbound-setup.sh", "parse.example.com")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.calls(), [{"tool": "dig", "args": ["+short", "MX", "parse.example.com"], "stdin": ""}])
        self.assertIn("Webhook accessibility and authentication were not tested", result.stdout)

    def test_mx_fallback_and_failure(self):
        (self.bin / "dig").unlink()
        result = self.run_helper("verify-inbound-setup.sh", "parse.example.com")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(self.calls(), [{"tool": "nslookup", "args": ["-type=MX", "parse.example.com"], "stdin": ""}])
        self.record.unlink()
        self.env["MX_RECORDS"] = "10 other.example."
        result = self.run_helper("verify-inbound-setup.sh", "parse.example.com")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([call["tool"] for call in self.calls()], ["nslookup"])

    def test_helpers_disclose_live_sends_and_parser_trust_boundary(self):
        for helper in ("send-test-email.sh", "send-html-email.sh"):
            with self.subTest(helper=helper):
                result = self.run_helper(helper, "--help")
                self.assertEqual(result.returncode, 0)
                self.assertIn("LIVE SEND", result.stdout)
                self.assertIn("approve", result.stdout.lower())
                self.assertIn("Mail Send", result.stdout)
                self.assertEqual(self.calls(), [])
        result = self.run_helper("parse-webhook-payload.js", "--help")
        self.assertIn("untrusted", result.stdout.lower())
        self.assertIn("trusted HTTPS", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_json_structure_cannot_add_recipients(self):
        recipient = 'test@example.com"}], "bcc":[{"email":"extra@example.com'
        result = self.run_helper("send-test-email.sh", recipient)
        self.assertEqual(self.payload()["personalizations"], [{"to": [{"email": recipient}]}])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_encoder_fails_without_transport(self):
        (self.bin / "jq").unlink()
        for helper in ("send-test-email.sh", "send-html-email.sh"):
            with self.subTest(helper=helper):
                result = self.run_helper(helper, "test@example.com", "Test", "Body")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls(), [])

    def test_send_http_failures_and_transport_failure(self):
        for helper in ("send-test-email.sh", "send-html-email.sh"):
            for status in ("400", "401", "403", "429", "500"):
                with self.subTest(helper=helper, status=status):
                    if self.record.exists():
                        self.record.unlink()
                    self.env.update(HTTP_STATUS=status, RESPONSE_BODY='{"errors":[{"message":"synthetic failure"}]}')
                    result = self.run_helper(helper, "test@example.com", "Test", "Body")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("HTTP " + status, result.stdout)
                    self.assertIn("synthetic failure", result.stdout)
                    self.assertEqual(self.payload()["subject"], "Test")
                    self.assertNotIn(self.env["SENDGRID_API_KEY"], result.stdout + result.stderr)
            self.record.unlink()
            self.env["CURL_EXIT"] = "7"
            result = self.run_helper(helper, "test@example.com", "Test", "Body")
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("Success!", result.stdout)
            self.env.pop("CURL_EXIT")

    def test_parser_treats_code_like_payload_as_data(self):
        code = 'require("fs").writeFileSync("NEVER", "executed"); $(touch NEVER)'
        # A normal multipart body. This simple diagnostic parser is lossy for the
        # closing part; the first part suffices to exercise the code/data boundary.
        fixture = ('--fixture\r\nContent-Disposition: form-data; name="text"\r\n\r\n' + code +
                   '\r\n--fixture\r\nContent-Disposition: form-data; name="subject"\r\n\r\nTest\r\n--fixture--\r\n')
        result = self.run_helper("parse-webhook-payload.js", input=fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["text"], code)
        self.assertFalse((self.work / "NEVER").exists())
        self.assertEqual(self.calls(), [])

    def run_curl_examples(self, relative):
        document = (ROOT / relative).read_text()
        blocks = [block for block in re.findall(r"```bash\n(.*?)```", document, re.S)
                  if block.lstrip().startswith("curl ")]
        self.assertTrue(blocks, "Expected executable curl examples in " + relative)
        for block in blocks:
            if self.record.exists():
                self.record.unlink()
            result = subprocess.run([str(self.bin / "bash"), "-c", block], env=self.env,
                                    cwd=self.work, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            yield self.calls()

    def test_webhook_example_keeps_text_fields_literal(self):
        # The attachment is synthetic; only curl is replaced. Execute the actual
        # documentation block, asserting argv at the external transport boundary.
        (self.work / "hello.txt").write_text("synthetic attachment")
        for calls in self.run_curl_examples("sendgrid-inbound/references/webhook-examples.md"):
            self.assertEqual(calls, [{"tool": "curl", "stdin": "", "args": [
                "-X", "POST", "https://your-domain.com/inbound",
                "--form-string", "from=alice@example.com",
                "--form-string", "to=support@parse.example.com",
                "--form-string", "subject=Hello",
                "--form-string", "text=Plain text body",
                "--form-string", "html=<p>HTML body</p>",
                "-F", "attachment1=@./hello.txt",
            ]}])

    def test_standalone_mail_examples_send_only_documented_data(self):
        examples = {
            "send-email/references/installation.md": [{
                "personalizations": [{"to": [{"email": "test@example.com"}]}],
                "from": {"email": "support@example.com"}, "subject": "Hello",
                "content": [{"type": "text/plain", "value": "Hi"}],
            }],
            "send-email/references/single-email-examples.md": [{
                "personalizations": [{"to": [{"email": "test@example.com"}],
                                      "cc": [{"email": "cc@example.com"}],
                                      "bcc": [{"email": "bcc@example.com"}]}],
                "from": {"email": "support@example.com"},
                "reply_to": {"email": "support@example.com"}, "subject": "SendGrid test",
                "content": [{"type": "text/plain", "value": "Plain text body"},
                            {"type": "text/html", "value": "<p>HTML body</p>"}],
                "attachments": [{"content": "aGVsbG8=", "type": "text/plain",
                                 "filename": "hello.txt", "disposition": "attachment"}],
            }, {
                "from": {"email": "support@example.com"},
                "personalizations": [{"to": [{"email": "test@example.com"}],
                                      "dynamic_template_data": {"first_name": "Vince"}}],
                "template_id": "d-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
            }],
        }
        for relative, expected in examples.items():
            # Run copied documentation alone: no root helper/sibling dependency.
            document = self.work / "selected-skill" / relative
            document.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, document)
            calls = list(self.run_curl_examples(str(document)))
            self.assertEqual(len(calls), len(expected))
            for actual, payload in zip(calls, expected):
                self.assertEqual(len(actual), 1)
                self.assertEqual(actual[0]["tool"], "curl")
                args = actual[0]["args"]
                self.assertEqual(args[:8], ["-X", "POST", "https://api.sendgrid.com/v3/mail/send",
                                           "-H", "Authorization: Bearer SG.synthetic-regression-only",
                                           "-H", "Content-Type: application/json", "-d"])
                self.assertEqual(len(args), 9)
                self.assertEqual(json.loads(args[8]), payload)

    def test_missing_key_and_invalid_dns_input_do_not_use_transport(self):
        self.env.pop("SENDGRID_API_KEY")
        for helper in ("send-test-email.sh", "send-html-email.sh"):
            result = self.run_helper(helper, "test@example.com", "Test", "Body")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.calls(), [])
        for hostname in ("", "-option", "$(touch NEVER)", "https://parse.example.com/"):
            result = self.run_helper("verify-inbound-setup.sh", hostname)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *TEST_ARGS])

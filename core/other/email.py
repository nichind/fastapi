import smtplib


class Email:
    smtp = smtplib.SMTP("localhost", 25, local_hostname="localhost")
    from_addr = None

    def send(self, to_addr, subject, body):
        if not self.from_addr:
            self.from_addr = self.smtp.ehlo()[1] or "localhost"
        self.smtp.sendmail(self.from_addr, to_addr, f"Subject: {subject}\n\n{body}")

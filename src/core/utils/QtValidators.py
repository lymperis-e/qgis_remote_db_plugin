import re
from PyQt5.QtGui import QValidator


class PortValidator(QValidator):
    def validate(self, input_text, pos):
        # Check if the input is a valid integer
        if input_text.isdigit():
            # Check if the input is in the range 1-65535
            if 1 <= int(input_text) <= 65535:
                return (QValidator.Acceptable, input_text, pos)
            return (QValidator.Intermediate, input_text, pos)
        else:
            return (QValidator.Intermediate, input_text, pos)


class HostValidator(QValidator):
    def validate(self, input_text, pos):
        # Check if the input is a valid IP address
        ip_pattern = r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"
        domain_pattern = r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        if re.match(ip_pattern, input_text):
            parts = input_text.split(".")
            for part in parts:
                if not (0 <= int(part) <= 255):
                    return (QValidator.Intermediate, input_text, pos)
            return (QValidator.Acceptable, input_text, pos)
        elif re.match(domain_pattern, input_text):
            return (QValidator.Acceptable, input_text, pos)
        else:
            return (QValidator.Intermediate, input_text, pos)

from PyQt5.QtGui import QValidator


class PortValidator(QValidator):
    def validate(self, input_text, pos):
        # Check if the input is a valid integer
        if input_text.isdigit():
            # Check if the input is in the range 1001-65535
            if 1 <= int(input_text) <= 65535:
                return (QValidator.Acceptable, input_text, pos)
            else:
                return (QValidator.Intermediate, input_text, pos)
        else:
            return (QValidator.Intermediate, input_text, pos)


class IPAddressValidator(QValidator):
    def validate(self, input_text, pos):
        # Split the input into parts using dot as separator
        parts = input_text.split(".")

        # Check if there are exactly four parts in the IP address
        if len(parts) != 4:
            return (QValidator.Intermediate, input_text, pos)

        # Check each part for validity
        for part in parts:
            if not part.isdigit() or not (0 <= int(part) <= 255):
                return (QValidator.Intermediate, input_text, pos)

        return (QValidator.Acceptable, input_text, pos)

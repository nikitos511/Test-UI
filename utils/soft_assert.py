import allure

class SoftAssert:
    def __init__(self):
        self.errors = []

    def add(self, message: str):
        self.errors.append(message)
        try:
            allure.attach(message, name="SoftAssert error", attachment_type=allure.attachment_type.TEXT)
        except Exception:
            pass

    def assert_all(self):
        if self.errors:
            summary = "\n".join(self.errors)
            try:
                allure.attach(summary, name="All errors summary", attachment_type=allure.attachment_type.TEXT)
            except Exception:
                pass
            raise AssertionError(f"Found {len(self.errors)} error(s):\n{summary}")

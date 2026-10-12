class AgentError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class CognitionError(AgentError):
    def __init__(self, message: str = "I couldn't get a reliable reading. Try a clearer photo or PDF."):
        super().__init__(message, 422)

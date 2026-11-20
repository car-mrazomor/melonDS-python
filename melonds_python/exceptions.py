class PymelonDSException(Exception):
    pass


class PymelonDSInvalidInputException(PymelonDSException):
    pass


class PymelonDSInvalidOperationException(PymelonDSException):
    pass


class PymelonDSDependencyError(PymelonDSException):
    pass

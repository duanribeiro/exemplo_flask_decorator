from abc import ABC, abstractmethod
import traceback

from libep import log_error


class ValidationError(Exception):
    pass    


class ValidationSuccess(object):
    pass


class BusinessLogicException(ValidationError):
    pass


class ValidationSuccessValue(ValidationSuccess):
    def __init__(self, value):
        self.value = value


class ValidationExecute():
    def execute(self, *args, **kwargs):
        try:
            result = self._execute(*args, **kwargs)
        except ValidationError as e:
            raise e
        except Exception as e:
            log_error(f'ValidationExecution error: {type(e)} {str(e)}')
            traceback.print_exc()
            raise e

        return result


class CadastroBase(ValidationExecute, ABC):
    def __init__(self):
        pass


class GestaoContratosBase(ValidationExecute, ABC):
    def __init__(self):
        pass


class KnowYourClientBase(ValidationExecute, ABC):
    def __init__(self):
        pass


class PotentialFutureExposureBase(ValidationExecute, ABC):
    def __init__(self):
        pass


class LimiteBase(ValidationExecute, ABC):
    def __init__(self):
        pass

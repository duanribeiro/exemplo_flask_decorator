from validation.base import ValidationSuccess, ValidationSuccessValue
from validation.base import CadastroBase, GestaoContratosBase, KnowYourClientBase, PotentialFutureExposureBase, LimiteBase


class Cadastro(CadastroBase):
    def _execute(*args, **kwargs):
        return ValidationSuccessValue('#222')


class GestaoContratos(GestaoContratosBase):
    def _execute(*args, **kwargs):
        return ValidationSuccess()


class KnowYourClient(KnowYourClientBase):
    def _execute(*args, **kwargs):
        return ValidationSuccess()


class PotentialFutureExposure(PotentialFutureExposureBase):
    def _execute(*args, **kwargs):
        return ValidationSuccessValue(1)


class Limite(LimiteBase):
    def _execute(*args, **kwargs):
        return ValidationSuccess()
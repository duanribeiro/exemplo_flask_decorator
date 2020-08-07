class RejectException(Exception):
    pass


class ResultHasntChanged(Exception):
    pass


def raise_if_none(condition, message):
    if condition is None:
        raise RejectException(message)

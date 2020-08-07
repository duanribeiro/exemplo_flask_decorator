from abc import ABC, abstractmethod

class MktDataBase(ABC):
    @abstractmethod
    def loop(self):
        pass


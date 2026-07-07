from abc import ABC, abstractmethod


class BaseStrategy(ABC):

    @abstractmethod
    def generate_signal(self, data):
        """
        매매 신호 생성

        Returns
        -------
        BUY
        SELL
        HOLD
        """
        pass
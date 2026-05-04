import numpy as np
from collections import defaultdict


class Curiosity:
    def __init__(self, config: dict):
        """
        config: curiosity config section
        """
        self.beta = config["beta"]  

        self.visit_counts = defaultdict(int)

    def _state_to_key(self, state):
        """
        Преобразует состояние в хешируемый ключ.
        ВАЖНО: зависит от того, что у тебя state (position / observation)
        """
        # если numpy массив (например observation)
        if isinstance(state, np.ndarray):
            return tuple(state.flatten())

        # fallback
        return str(state)

    def step(self, state):
        """
        Вызывается на каждом шаге.
        Возвращает intrinsic reward.
        """

        key = self._state_to_key(state)

        # увеличиваем счетчик
        self.visit_counts[key] += 1
        N = self.visit_counts[key]

        # curiosity reward
        r_curiosity = self.beta * (1.0 / np.sqrt(N))

        return r_curiosity

    def reset(self):
        """
        эпизодическая curiosity
        """
        self.visit_counts.clear()



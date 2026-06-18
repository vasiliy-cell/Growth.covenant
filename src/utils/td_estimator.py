from dataclasses import dataclass


@dataclass
class TDTransition:
    state: any
    action: int
    reward: float
    next_state: any
    done: bool


class TDErrorLogger:
    def __init__(self, gamma: float):
        self.gamma = gamma

    def compute_from_values(
        self,
        reward: float,
        current_q: float,
        next_q: float,
        done: bool,
    ) -> float:

        if done:
            target = reward
        else:
            target = reward + self.gamma * next_q

        return target - current_q

from dataclasses import dataclass
from typing import Optional


@dataclass
class TDTransition:
    state: tuple
    action: int
    reward: float
    next_state: tuple
    done: bool


class TDErrorLogger:
    """
    Computes TD-error for diagnostics/logging.

    This class does NOT write logs.
    It only computes TD-related metrics.
    """

    def __init__(self, gamma: float):
        self.gamma = gamma

    def compute_q_table_td_error(
        self,
        transition: TDTransition,
        q_table,
    ) -> float:
        """
        Computes TD-error for tabular Q-learning.

        δ = r + γ * max(Q(s')) - Q(s)

        If episode is done:
        δ = r - Q(s)

        Parameters
        ----------
        transition : TDTransition
            Environment transition.

        q_table :
            Your Q-table object.

        Returns
        -------
        float
            TD-error.
        """

        current_q = q_table.get_q_value(
            transition.state,
            transition.action,
        )

        if transition.done:
            target_q = transition.reward
        else:
            next_max_q = max(
                q_table.get_all_q_values(
                    transition.next_state
                )
            )

            target_q = (
                transition.reward
                + self.gamma * next_max_q
            )

        td_error = target_q - current_q

        return td_error

    def compute_from_values(
        self,
        reward: float,
        current_q: float,
        next_q: float,
        done: bool,
    ) -> float:
        """
        Generic TD-error computation.

        Useful later for neural networks / DQN.
        """

        if done:
            target_q = reward
        else:
            target_q = reward + self.gamma * next_q

        return target_q - current_q

    @staticmethod
    def abs_td_error(td_error: float) -> float:
        return abs(td_error)
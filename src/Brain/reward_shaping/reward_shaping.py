class RewardShaping:
    def __init__(self, curiosity=None, food_bonus=0.0):
        """
        curiosity:  intrinsic reward module (e.g. Curiosity)
        food_bonus: extra intrinsic reward on every step the world paid
                    something positive (food). The world still pays +5 and
                    energy still follows the world; only what this mind
                    LEARNS from is louder, so food outweighs danger and
                    touching cells stops being a zero-sum bet.
        """
        self.curiosity = curiosity
        self.food_bonus = food_bonus

    def compute(self, next_state, env_reward):
        """
        Combine environment reward with intrinsic reward.

        next_state: state AFTER action (important for curiosity)
        env_reward: reward from environment

        returns:
            total_reward
        """

        r_intrinsic = 0.0

        if self.curiosity is not None:
            # pass state object (not key)
            r_intrinsic = self.curiosity.step(next_state)

        if env_reward > 0:
            r_intrinsic += self.food_bonus

        total_reward = env_reward + r_intrinsic

        return total_reward, r_intrinsic

    def reset(self):
        """
        Reset intrinsic modules (e.g. curiosity)
        """
        if self.curiosity is not None:
            self.curiosity.reset()

    # -----------------------------
    # STATE (CHECKPOINT)
    # -----------------------------
    def state(self):
        if self.curiosity is None:
            return None

        return self.curiosity.state()

    def load_state(self, state):
        if self.curiosity is not None and state is not None:
            self.curiosity.load_state(state)
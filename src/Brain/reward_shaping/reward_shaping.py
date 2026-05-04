class RewardShaping:
    def __init__(self, curiosity=None):
        """
        curiosity: intrinsic reward module (e.g. Curiosity)
        """
        self.curiosity = curiosity

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

        total_reward = env_reward + r_intrinsic

        return total_reward, r_intrinsic

    def reset(self):
        """
        Reset intrinsic modules (e.g. curiosity)
        """
        if self.curiosity is not None:
            self.curiosity.reset()
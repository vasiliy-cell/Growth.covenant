import torch


class Brain:
    def __init__(self, trainer, policy):
        self.trainer = trainer
        self.model = trainer.model
        self.policy = policy

    def choose_action(self, state, available_actions):
        # q_values нужны только для exploitation, но Policy сам решает
        # exploration/exploitation внутри select_action — поэтому
        # считаем их всегда, без torch.no_grad() здесь не страшно,
        # т.к. это просто forward для выбора действия, не backward.
        q_values = self.trainer.model(state)
        return self.policy.select_action(q_values, available_actions)

    def learn(self, state, action, reward, next_state, done):
        self.trainer.update(state, action, reward, next_state, done)
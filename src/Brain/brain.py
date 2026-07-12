import torch


class Brain:
    def __init__(self, trainer, policy):
        self.trainer = trainer
        self.policy_net = trainer.policy_net
        self.policy = policy

    def choose_action(self, state, available_actions):
        # q_values нужны только для exploitation, но Policy сам решает
        # exploration/exploitation внутри select_action — поэтому
        # считаем их всегда, без torch.no_grad() здесь не страшно,
        # т.к. это просто forward для выбора действия, не backward.
        q_values = self.trainer.policy_net(state)
        return self.policy.select_action(q_values, available_actions)

    def learn(self, states, actions, rewards, next_states, dones):
        return self.trainer.update(states, actions, rewards, next_states, dones)
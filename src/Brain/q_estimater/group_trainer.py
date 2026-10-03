import torch


# -----------------------------
# THE ARITHMETIC, COMPILED
# -----------------------------
# The two functions below are where a group spends its time, and both are
# compiled by torch.compile. Run op by op, Adam walks every member's
# weights, gradients and both moments some ten times per update - each walk
# a separate pass over megabytes of memory - and the update waits on
# memory, not on arithmetic. Compiled, the chain of elementwise ops becomes
# one loop that reads every number once and writes it once; in the forward
# pass the bias and the ReLU are folded around the matrix product.
#
# The formulas are exactly the ones written here. What can move is the last
# bits of a float (the order of roundings), so a run is reproducible against
# itself, not bit for bit against a run of the uncompiled code.
#
# dynamic=True: a group changes size whenever somebody is born, dies or
# finishes warming up, and that must not trigger a fresh compilation.
# The first call of a process compiles (seconds), every later one does not.

def _forward_core(params, x, layers):
    """
    params is [weight, bias, weight, bias, ...] stacked over members, the
    order MLP lays its layers down in: Linear -> ReLU after every layer
    except the last.
    """
    for layer in range(layers):
        weight, bias = params[2 * layer], params[2 * layer + 1]
        x = torch.baddbmm(bias.unsqueeze(1), x, weight.transpose(1, 2))

        if layer < layers - 1:
            x = torch.relu(x)

    return x


def _adam_core(params, grads, exp_avgs, exp_avg_sqs,
               one_minus_beta1, beta2, one_minus_beta2, eps,
               step_size, bias_correction2_sqrt):
    """
    The elementwise half of torch's Adam (no weight decay, no amsgrad), in
    place, for every member at once. The per-member constants come already
    broadcast to each parameter's shape, one list entry per parameter.
    """
    for k, (param, grad, exp_avg, exp_avg_sq) in enumerate(
        zip(params, grads, exp_avgs, exp_avg_sqs)
    ):
        shape = (-1,) + (1,) * (grad.dim() - 1)

        exp_avg.lerp_(grad, one_minus_beta1[k])
        exp_avg_sq.mul_(beta2[k]).addcmul_(grad, grad * one_minus_beta2[k])

        denom = (exp_avg_sq.sqrt() / bias_correction2_sqrt.view(shape)).add_(eps[k])
        param.addcdiv_(exp_avg * step_size.view(shape), denom, value=-1)


_forward_stack = torch.compile(_forward_core, dynamic=True)
_adam_step = torch.compile(_adam_core, dynamic=True)


class GroupTrainer:
    """
    One DQN update for SEVERAL minds at once, when their networks have the
    same shape and they learn from batches of the same size.

    Nothing is shared between the minds: every one keeps its own weights,
    target net, Adam moments and step, learning rate, gamma, max_norm and
    target schedule, and samples its own batch from its own buffer with its
    own stream. The group only stacks them along a first dimension so the
    arithmetic of all of them runs as one batched kernel instead of one
    small kernel per mind - the same update DQNTrainer.update makes, done
    side by side.

    The stacks OWN the numbers while the group lives: every parameter of
    every member's policy net and target net, and its Adam state, is a view
    into one row of a stack. So a member's own network (the one
    choose_action and the checkpoint read) always shows exactly what the
    group has learned, without copying anything back. When the group is
    dissolved, every member gets a private copy of its row again.
    """

    def __init__(self, trainers):
        self.trainers = list(trainers)

        first = self.trainers[0]
        self.layers = len(list(first.policy_net.parameters())) // 2

        self.policy = self._stack([t.policy_net for t in self.trainers])
        self.target = self._stack([t.target_net for t in self.trainers])

        self.exp_avg, self.exp_avg_sq, self.steps = self._stack_adam()

        self.gamma = self._column([t.gamma for t in self.trainers])
        self.max_norm = self._column([t.max_norm for t in self.trainers])

        group = [t.optimizer.param_groups[0] for t in self.trainers]
        self.lr = [g["lr"] for g in group]
        self.beta1 = [g["betas"][0] for g in group]
        self.beta2 = [g["betas"][1] for g in group]
        self.eps = self._column([g["eps"] for g in group])

        # The per-member Adam constants, already broadcast to every
        # parameter's shape - computed once here because _adam runs on
        # every update of the group.
        self._shapes = [(-1, *[1] * (stack.dim() - 1)) for stack in self.policy]

        beta1 = self._column(self.beta1)
        beta2 = self._column(self.beta2)
        self._one_minus_beta1 = [(1 - beta1).view(s) for s in self._shapes]
        self._beta2 = [beta2.view(s) for s in self._shapes]
        self._one_minus_beta2 = [(1 - beta2).view(s) for s in self._shapes]
        self._eps = [self.eps.view(s) for s in self._shapes]

    # -----------------------------
    # STACKING
    # -----------------------------
    @staticmethod
    def _column(values):
        return torch.tensor(values, dtype=torch.float32)

    @staticmethod
    def _stack(nets):
        """Stacks one parameter at a time and points every net at its row."""
        per_net = [list(net.parameters()) for net in nets]
        stacks = []

        for k in range(len(per_net[0])):
            stack = torch.stack([params[k].detach() for params in per_net])

            for row, params in enumerate(per_net):
                params[k].data = stack[row]

            stacks.append(stack)

        return stacks

    def _stack_adam(self):
        """
        The Adam state of every member, stacked the same way.

        A mind that has never taken a step has no Adam state yet; it gets
        the one torch would have created on its first step - zero moments
        and step 0.
        """
        exp_avg, exp_avg_sq = [], []

        for k, stack in enumerate(self.policy):
            exp_avg.append(torch.zeros_like(stack))
            exp_avg_sq.append(torch.zeros_like(stack))

        steps = torch.zeros(len(self.trainers), dtype=torch.float32)

        for row, trainer in enumerate(self.trainers):
            optimizer = trainer.optimizer

            for k, param in enumerate(trainer.policy_net.parameters()):
                state = optimizer.state[param]

                if state:
                    exp_avg[k][row].copy_(state["exp_avg"])
                    exp_avg_sq[k][row].copy_(state["exp_avg_sq"])
                    steps[row] = float(state["step"])

                optimizer.state[param] = {
                    "step": steps[row],
                    "exp_avg": exp_avg[k][row],
                    "exp_avg_sq": exp_avg_sq[k][row],
                }

        return exp_avg, exp_avg_sq, steps

    def dissolve(self):
        """Gives every member a private copy of its row back."""
        for trainer in self.trainers:
            for net in (trainer.policy_net, trainer.target_net):
                for param in net.parameters():
                    param.data = param.data.clone()

            for param in trainer.policy_net.parameters():
                state = trainer.optimizer.state[param]

                for key in ("step", "exp_avg", "exp_avg_sq"):
                    state[key] = state[key].clone()

    # -----------------------------
    # FORWARD
    # -----------------------------
    def _forward(self, params, x):
        """
        The MLP of every member at once: (G, B, in) -> (G, B, actions).
        See _forward_stack.
        """
        return _forward_stack(list(params), x, self.layers)

    # -----------------------------
    # ACTING
    # -----------------------------
    def q_values(self, states):
        """
        Q for one state per member, (G, obs) -> (G, actions): the acting
        twin of update(), each row through that member's own policy net,
        no gradient.
        """
        with torch.no_grad():
            return self._forward(self.policy, states.unsqueeze(1)).squeeze(1)

    # -----------------------------
    # DQN UPDATE
    # -----------------------------
    def update(self, batches):
        """
        batches: one (states, actions, rewards, next_states, dones) per
        member, in member order - each sampled from that member's buffer.

        Returns one metrics dict per member, the same as DQNTrainer.update.
        """
        # One flat stack and a reshape instead of a stack per member: the
        # values and their layout are identical, the per-call overhead is
        # one stack instead of G+1.
        members, batch_size = len(batches), len(batches[0][0])

        states = torch.stack(
            [state for batch in batches for state in batch[0]]
        ).view(members, batch_size, -1)                                   # (G, B, obs)
        next_states = torch.stack(
            [state for batch in batches for state in batch[3]]
        ).view(members, batch_size, -1)                                   # (G, B, obs)
        actions = torch.tensor([b[1] for b in batches], dtype=torch.long)       # (G, B)
        rewards = torch.tensor([b[2] for b in batches], dtype=torch.float32)    # (G, B)
        dones = torch.tensor([b[4] for b in batches], dtype=torch.float32)      # (G, B)

        params = [stack.detach().requires_grad_() for stack in self.policy]

        q_values = self._forward(params, states)
        current_q = q_values.gather(2, actions.unsqueeze(2)).squeeze(2)        # (G, B)

        # Double DQN: the policy net CHOOSES the next action, the target net
        # VALUES it - each member with its own pair of nets.
        with torch.no_grad():
            next_actions = self._forward(self.policy, next_states).argmax(dim=2)
            next_q = self._forward(self.target, next_states)
            next_q = next_q.gather(2, next_actions.unsqueeze(2)).squeeze(2)

            target_q = rewards + self.gamma.unsqueeze(1) * next_q * (1.0 - dones)

        # One MSE per member; their sum has every member's own gradient,
        # because no member's loss depends on another's weights.
        losses = ((current_q - target_q) ** 2).mean(dim=1)                  # (G,)
        grads = torch.autograd.grad(losses.sum(), params)

        with torch.no_grad():
            grad_norm = self._clip(grads)
            self._adam(grads)
            self._sync_targets()

        td_error = (target_q - current_q).detach().mean(dim=1)

        return [
            {
                "loss": loss,
                "td_error": td,
                "grad_norm": norm,
                "target_q": target,
                "q_prediction": prediction,
            }
            for loss, td, norm, target, prediction in zip(
                losses.detach().tolist(),
                td_error.tolist(),
                grad_norm.tolist(),
                target_q.mean(dim=1).tolist(),
                current_q.detach().mean(dim=1).tolist(),
            )
        ]

    def _clip(self, grads):
        """
        clip_grad_norm_ per member: the norm is over that member's whole
        gradient, and each member is scaled to its own max_norm.
        """
        norms = torch.stack([g.flatten(1).norm(dim=1) for g in grads])     # (P, G)
        total_norm = norms.norm(dim=0)                                      # (G,)

        coef = (self.max_norm / (total_norm + 1e-6)).clamp(max=1.0)

        for g in grads:
            g.mul_(coef.view(-1, *[1] * (g.dim() - 1)))

        return total_norm

    def _adam(self, grads):
        """
        torch's Adam (no weight decay, no amsgrad), with each member's own
        lr, betas and step.
        """
        self.steps.add_(1)
        steps = self.steps.tolist()

        step_size = self._column([
            lr / (1 - b1 ** step) for lr, b1, step in zip(self.lr, self.beta1, steps)
        ])
        bias_correction2_sqrt = self._column([
            (1 - b2 ** step) ** 0.5 for b2, step in zip(self.beta2, steps)
        ])

        _adam_step(
            self.policy, list(grads), self.exp_avg, self.exp_avg_sq,
            self._one_minus_beta1, self._beta2, self._one_minus_beta2, self._eps,
            step_size, bias_correction2_sqrt,
        )

    def _sync_targets(self):
        """Each member copies its policy net into its target on ITS schedule."""
        for row, trainer in enumerate(self.trainers):
            trainer.training_step += 1

            if trainer.training_step % trainer.target_update_freq == 0:
                for target, policy in zip(self.target, self.policy):
                    target[row].copy_(policy[row])

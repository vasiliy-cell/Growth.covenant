class Brain:
    """
    One mind, belonging to exactly one agent.

    Everything in here is personal: the network that values the world, the
    exploration state, the memories it learns from and its own sense of
    what is new. Two agents never share a Brain - without that there is no
    identity for anything to grow into.

    The brain never touches the world and the world never touches the
    brain. They meet only through an action going one way and an
    observation coming back, which is why nothing under src/world or
    src/environment imports torch.
    """

    def __init__(self, trainer, policy, replay_buffer, reward_shaping,
                 batch_size, min_buffer_size):
        self.trainer = trainer
        self.policy = policy
        self.replay_buffer = replay_buffer
        self.reward_shaping = reward_shaping

        self.batch_size = batch_size
        self.min_buffer_size = min_buffer_size

        # Steps this mind has lived through. It is what makes the record on
        # disk mean something, and it is what an exploration schedule tied
        # to the individual rather than to the run is measured in.
        self.age = 0

    # -----------------------------
    # ACTING
    # -----------------------------
    def choose_action(self, state, available_actions):
        # Policy decides exploration/exploitation inside select_action, so
        # the q values are computed either way - this is a plain forward
        # for choosing, never a backward.
        q_values = self.trainer.policy_net(state)
        return self.policy.select_action(q_values, available_actions)

    # -----------------------------
    # VALUING
    # -----------------------------
    def shape_reward(self, observation, env_reward):
        """
        Adds this agent's own curiosity to what the world paid it.

        The novelty counter is personal, so a newborn finds the whole map
        new even where the rest of the population has already been - "have
        I been here" and not "has anyone been here".
        """
        return self.reward_shaping.compute(observation, env_reward)

    # -----------------------------
    # REMEMBERING
    # -----------------------------
    def remember(self, state, action, reward, next_state, done):
        self.replay_buffer.push(state, action, reward, next_state, done)
        self.age += 1

    # -----------------------------
    # LEARNING
    # -----------------------------
    def learn(self):
        """
        One update on a batch of this agent's OWN memories, or None while
        the buffer is still warming up.

        Because one agent stores exactly one transition per tick,
        buffer_size and min_buffer_size keep the very meaning they had when
        a single agent lived in the world: so many ticks of personal
        history, so many ticks of warmup. A shared buffer would have
        rescaled both by the size of the population.
        """
        if len(self.replay_buffer) < self.min_buffer_size:
            return None

        batch = self.replay_buffer.sample(self.batch_size)
        return self.trainer.update(*batch)

    # -----------------------------
    # LOGGING WINDOW BOUNDARY
    # -----------------------------
    def next_episode(self):
        """
        Decays this mind's own epsilon and curiosity.

        Every brain starts at the epsilon from the config, so an agent born
        late begins exploring from scratch while the veterans around it are
        already exploiting. The schedule follows the age of the individual,
        not the age of the run - which only became possible once the policy
        stopped being shared.
        """
        self.policy.next_episode()
        self.reward_shaping.reset()

    # -----------------------------
    # RECORD
    # -----------------------------
    def summary(self):
        """The cheap scalars describing this mind, without the weights."""
        curiosity = self.reward_shaping.curiosity

        return {
            "epsilon": self.policy.epsilon,
            "curiosity_beta": curiosity.beta if curiosity is not None else None,
            "age": self.age,
        }

    def state(self):
        """
        Everything of this mind worth writing down.

        Weights alone would not be a record: without epsilon and age you
        cannot tell whether you are holding a cautious veteran or a reckless
        newborn, and you cannot continue either of them.
        """
        record = self.summary()
        record["policy_net"] = self.trainer.state_dict()

        return record

# Q-Learning Basics

ML is basically impossible without some kind of theory behind it.

In this short file I want to explain the absolute base of the simplest RL method, namely how a Q-table works and a bit about policy.

---

## Core Structure

Put simply, there are three main parts:

* the **agent** is the one who moves and “sees”
* the **world** is, well, the world
* and the most important part is the **brain**

Right now my brain looks like this:

* **Q-table** → the value estimator
* **policy** → the system that decides how we use those values

Simply speaking, policy is what chooses the action.

In my case:

* **argmax** → picks the best known action
* **ε-greedy** → with probability ε takes a random action to explore the world

One important thing here:

> policy is here to stay for a long time

But the second important part, the Q-table, will be replaced later.

---

# Q-Table

Q-table is basically a table that stores values of taking a specific action in a specific state:

Q(s,a)

The Q-table is **NOT** created once at the beginning and then left alone.

It is constantly updated and changed, and this is basically the core idea of machine learning.

At the beginning:

* we don’t have full information about the world
* we don’t know rewards
* we don’t know future states
* we don’t know which actions are good

So initially we create a table filled with zeros
(sometimes other values are used, but that is less common and usually just for faster convergence).

The initial Q-table is basically:

> a “guessing board”.

Over time, as we take actions and observe results, the table slowly becomes closer to reality.

---

# Updating the Q-Table

Now the question is:

> how do we update it?

For that we use a special update rule:

Q(s,a) \leftarrow Q(s,a)+\alpha \cdot \delta

The goal of this formula is to continuously adjust (Q(s,a)) so it becomes closer to reality.

---

# Breaking Down the Formula

## Q(s,a)

The value of taking action (a) in state (s).

* (Q) = value
* (s) = state
* (a) = action

The arrow means assignment:
we replace the old value with the new one.

---

## α (Alpha)

The learning rate.

Important:

> this is NOT the action “a”

It controls how much we trust new experience compared to old knowledge.

* higher α → faster learning, but more instability
* lower α → slower learning, but more stable updates

---

## r (Reward)

The reward returned after taking an action.

In my project it comes from:

* interactions with objects
* exploration rewards
* curiosity rewards

Rewards can be:

* positive
* negative
* zero

---

# TD Error (δ)

This was honestly the hardest part for me to understand.

I tried to understand this for days.

δ is the **TD error**
(Temporal Difference error).

Simply put:

> it is the difference between what you expected and what actually happened after the step.

More concretely:

* it is the difference between the new estimate (target)
* and the old estimate (Q(s,a))

So:

* if the new estimate is higher than the old one
  → ( \delta > 0 )
  → we underestimated the action
  → increase (Q(s,a))

* if the new estimate is lower
  → ( \delta < 0 )
  → we overestimated the action
  → decrease (Q(s,a))

---

# TD Error Formula

The TD error itself is calculated like this:

\delta=r+\gamma \max Q(s',a')-Q(s,a)

where:

* (r + \gamma \max Q(s',a')) is the target
* (Q(s,a)) is the old estimate before the step
* (\max Q(s',a')) is the best possible action in the next state (s')

Important:

> this is NOT necessarily what we actually do

It is:

> what we *would* do if we acted optimally.

---

# Gamma (γ)

(\gamma) (gamma) is a discount factor that controls how much we care about the future.

* if gamma is 0
  → the agent only cares about immediate reward

* if gamma is 1
  → the agent plans far into the future

So basically:

we thought an action had value:

Q(s,a)

but after the step we discovered it actually leads to:

r+\gamma \max Q(s',a')

The difference between these two is the error, and that is what we use to correct our estimate.

---

# Final Update Equation

The final full update equation used in the code:

Q(s,a) \leftarrow Q(s,a)+\alpha(r+\gamma \max Q(s',a')-Q(s,a))

This update happens constantly during training.

The agent:

* acts
* receives reward
* updates estimates
* slowly improves behavior

Over time, the system gradually builds a better approximation of:

> which actions are useful and which are not.

---

# Curiosity and Exploration

One important thing I discovered while experimenting:

without exploration, the agent behaves *extremely* lazily.

It often:

* stays in safe places
* avoids uncertainty
* stops exploring
* loops simple behaviors

So I added curiosity-driven rewards.

The current curiosity reward looks like this:

r_{curiosity}=\frac{\beta}{\sqrt{N}}

where:

* (N) is the number of visits to a state
* (\beta) controls curiosity strength

So:

* unexplored states become attractive
* repeatedly visited states become less interesting

If I’m being completely honest, this is not really “curiosity” in the human sense.

It’s closer to:

> old states becoming boring.

But in RL this kind of intrinsic exploration reward is still usually called curiosity.

Without it, the agent almost refuses to meaningfully explore the map.

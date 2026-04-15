


### Stage 1 — Foundation (Environment + Learning Core)

**The goal of this stage** is to build a solid base where I can later plug in a real AI and be confident that the environment, rewards, and overall world are working correctly and actually push the agent to learn. 
(If I start with a real AI right away, I won’t be able to tell whether problems come from the AI itself or from a poorly designed environment.)

##### Building a simple world (grid-world)

- there is a space where the agent operates
- there are objects and interactions (for now: reward, danger, and empty cells)
- there is a reward and penalty system
- there is logging to understand what’s going on
##### Building the agent

- it has a body
- it can move
- it has observations
- it has a state
##### Brain
- Q-table (will be replaced later)
- policy

This is not a final intelligence, but a **temporary learning mechanism** used to validate the environment:

- can the agent learn at all
- are the rewards working correctly
- does meaningful behavior emerge

If learning doesn’t happen at this stage, the problem is not the “brain” — it’s the environment.

##### Visualization

- I built simple graphics for training loops (there are 2 run files: one without graphics for training since it’s much faster, and another — `visualized_run.py` — if you want to see how the agent moves)
    
- there is also log visualization using scripts that read log files and turn them into charts, graphs, and other tools for easier analysis
    
---

### Connection to the next stage

Once the system starts learning consistently:

- we **don’t touch the world**
- we don’t change the rewards
- we don’t change the mechanics
- we don’t change the policy

We simply replace the Q-table with a neural network.











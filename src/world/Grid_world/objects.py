OBJECTS = {
    0: {"name": "empty"},
    1: {"name": "food"},
    2: {"name": "danger"},
}

# What another agent's body looks like inside a local view.
#
# Deliberately NOT a member of OBJECTS: Map generates and refills from the
# non-zero ids of that dict, and a body is not something the world can grow.
# This value exists only in what an agent SEES - the map itself never holds
# it, so REWARDS never has to answer for it either.
AGENT_CELL = 3

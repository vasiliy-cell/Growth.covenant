from itertools import combinations
import yaml

with open("config.yml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

def choose_partners(agents):   
    threshold = config["energy"]["reproduction_threshold"]
    zone = 3
    ready = [agent for agent in agents if agent.energy >= threshold]   
    couples = []
    used = set()
    for agent, b in combinations(ready, 2):
        if agent.agent_id in used or b.agent_id in used:   
            continue
        ax, ay = agent.get_position()
        bx, by = b.get_position()
        if abs(ax - bx) <= zone and abs(ay - by) <= zone:   
            couples.append((agent, b))
            used.add(agent.agent_id)
            used.add(b.agent_id)
    return couples



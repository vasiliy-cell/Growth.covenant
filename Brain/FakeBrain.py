import random

# Brain/FakeBrain.py
class FakeBrain:
    def choose_action(self, observation):
        # Достаем список действий из атрибута объекта Observation
        actions = observation.available_actions
        
        if not actions:
            raise ValueError("No available actions")

        return random.choice(actions)
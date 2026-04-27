import random

"""
Testing Purpose
"""

def random_agent(legal_moves: list) -> dict:
    """Picks a random legal move. Used for smoke testing the engine."""
    return random.choice(legal_moves)
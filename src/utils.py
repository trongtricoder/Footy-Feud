import json
import random
import os

def load_players():
    """Loads the athlete data from the JSON file."""
    # This helps find the file regardless of where you run the script from
    base_path = os.path.dirname(__file__)
    file_path = os.path.join(base_path, '../data/players.json')
    
    with open(file_path, 'r') as f:
        return json.load(f)

def get_random_player(player_list):
    """Selects one random athlete to be the 'Secret Player'."""
    return random.choice(player_list)
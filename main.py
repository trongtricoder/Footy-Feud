from src.utils import load_players, get_random_player
from src.logics import find_player_by_name, get_feedback

def play_game():
    all_players = load_players()
    secret_player = get_random_player(all_players)
    
    attempts = 6
    print("\n" + "="*40)
    print("      FOOTYFEUD: GUESS THE ATHLETE")
    print("="*40)
    print("Legend: [ Nationality ] [ League ] [ Club ] [ Position ] [ Age ]")

    while attempts > 0:
        user_input = input(f"\n({attempts} tries left) Guess player: ")
        guessed_player = find_player_by_name(user_input, all_players)

        if not guessed_player:
            print("❌ Player not in database.")
            continue

        if guessed_player["name"] == secret_player["name"]:
            print(f"🌟 GOAL! {secret_player['name']} is correct!")
            break
        
        attempts -= 1
        print(get_feedback(guessed_player, secret_player))

    if attempts == 0:
        print(f"\nOUT OF TIME! The player was: {secret_player['name']}")

if __name__ == "__main__":
    play_game()
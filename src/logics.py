from colorama import Fore, Style, init
from rapidfuzz import process, fuzz

# Initialize colorama for Windows/Mac compatibility
init(autoreset=True)

def find_player_by_name(guess_name, player_list):
    # Create a list of all full names from your JSON
    names = [p["name"] for p in player_list]

    # Find the best match. 'extractOne' returns (name, score, index)
    match = process.extractOne(guess_name, names, scorer=fuzz.WRatio)

    # If the score is high enough (e.g., > 70%), return that player
    if match and match[1] > 70:
        index = match[2]
        return player_list[index]
    return None

def get_feedback(guess, secret):
    """
    Compares all 5 attributes and returns a color-coded string.
    """
    def colorize(text, is_correct):
        return f"{Fore.GREEN}{text}{Style.RESET_ALL}" if is_correct else f"{Fore.RED}{text}{Style.RESET_ALL}"

    # 1. Nationality, Position, Club (Direct Matches)
    nat_status = colorize(guess['nationality'], guess['nationality'] == secret['nationality'])
    pos_status = colorize(guess['position'], guess['position'] == secret['position'])
    club_status = colorize(guess['club'], guess['club'] == secret['club'])

    # 2. League (Yellow if same league but wrong club)
    if guess['league'] == secret['league']:
        league_status = f"{Fore.GREEN}{guess['league']}{Style.RESET_ALL}"
    else:
        league_status = f"{Fore.RED}{guess['league']}{Style.RESET_ALL}"

    # 3. Age (Higher/Lower logic)
    age_diff = abs(guess['age'] - secret['age'])
    
    # Determine the Arrow
    arrow = "↑" if guess['age'] < secret['age'] else "↓"
    
    if guess['age'] == secret['age']:
        age_feedback = f"{Fore.GREEN}{guess['age']} {Style.RESET_ALL}"
    elif age_diff <= 2: # This covers a range of 3 (e.g., if secret is 28: 26, 27, 29, 30 are yellow)
        age_feedback = f"{Fore.YELLOW}{guess['age']} ({arrow}){Style.RESET_ALL}"
    else:
        # No Fore color applied, just the plain text and arrow
        age_feedback = f"{guess['age']} ({arrow})"

    # Return formatted block
    return (
        f"\n[ {nat_status} ] [ {league_status} ] [ {club_status} ] "
        f"[ {pos_status} ] [ {age_feedback} ]"
    )
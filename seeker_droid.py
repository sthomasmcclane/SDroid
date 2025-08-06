import curses
import json
import random
import math
import time
import os
from datetime import datetime, timedelta, timezone

# --- Setup ---
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, 'gamedata.json')
RESOURCES_FILE = os.path.join(SCRIPT_DIR, 'resources.json')

# --- Data Handling ---
def load_game_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_game_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_resources():
    try:
        with open(RESOURCES_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # --- CHANGE: Updated default resource name ---
        return {"Salvage": 0, "Biochemicals": 0}

def update_resources(resource_type, quantity):
    resources = load_resources()
    resources[resource_type] = resources.get(resource_type, 0) + quantity
    with open(RESOURCES_FILE, 'w') as f:
        json.dump(resources, f, indent=2)

def check_and_reset_sites(data):
    AEST = timezone(timedelta(hours=10))
    now_aest = datetime.now(AEST)
    reset_time = now_aest.replace(hour=22, minute=0, second=0, microsecond=0)
    last_reset_str = data.get("last_reset_utc", "2000-01-01T00:00:00")
    last_reset = datetime.fromisoformat(last_reset_str).replace(tzinfo=timezone.utc)
    if now_aest >= reset_time and last_reset.astimezone(AEST) < reset_time:
        for planet in data:
            if isinstance(data[planet], dict):
                for site in data[planet]:
                    data[planet][site]['depleted'] = False
        data["last_reset_utc"] = now_aest.astimezone(timezone.utc).isoformat()
        save_game_data(data)
        return True
    return False

# --- Map and Drawing ---
def create_irregular_map(width, height, max_tiles):
    game_map = [['#' for _ in range(width)] for _ in range(height)]
    x, y = random.randint(1, width - 2), random.randint(1, height - 2)
    for _ in range(max_tiles):
        game_map[y][x] = '.'
        dx, dy = random.choice([(0, 1), (0, -1), (1, 0), (-1, 0)])
        x, y = max(1, min(x + dx, width - 2)), max(1, min(y + dy, height - 2))
    return game_map

def place_on_map(game_map, existing_coords):
    width, height = len(game_map[0]), len(game_map)
    while True:
        x, y = random.randint(1, width - 2), random.randint(1, height - 2)
        if game_map[y][x] == '.' and (x, y) not in existing_coords:
            return x, y

def draw_map_viewport(stdscr, game_map, cam_y, cam_x, enemies):
    h, w = stdscr.getmaxyx()
    map_h, map_w = len(game_map), len(game_map[0])
    for y in range(h - 1):
        for x in range(w - 1):
            map_char_y, map_char_x = y + cam_y, x + cam_x
            if 0 <= map_char_y < map_h and 0 <= map_char_x < map_w:
                is_enemy = False
                for enemy in enemies:
                    if enemy['y'] == map_char_y and enemy['x'] == map_char_x:
                        stdscr.addch(y, x, enemy['char'], enemy['color'])
                        is_enemy = True
                        break
                if not is_enemy:
                    stdscr.addch(y, x, game_map[map_char_y][map_char_x])

def draw_health_bar(stdscr, y, x, label, health, max_health, bar_width):
    health_percentage = health / max_health
    health_chunks = int(bar_width * health_percentage)
    if health_percentage > 0.6: color = curses.color_pair(2)
    elif health_percentage > 0.3: color = curses.color_pair(4)
    else: color = curses.color_pair(3)
    stdscr.addstr(y, x, f"[{label}: ")
    for i in range(health_chunks): stdscr.addch('#', color)
    for i in range(bar_width - health_chunks): stdscr.addch(' ')
    stdscr.addstr(f"] {health}/{max_health}")

def draw_resources_display(stdscr):
    resources = load_resources()
    salvage = resources.get("Salvage", 0)
    # --- CHANGE: Updated resource name ---
    biochemicals = resources.get("Biochemicals", 0)
    display_str = f"Salvage: {salvage} | Biochemicals: {biochemicals}"
    stdscr.addstr(1, 1, display_str)

def draw_ring(stdscr, y_on_screen, x_on_screen, radius, color_pair, indicator_char=None, angle=None, start_angle=0, end_angle=360):
    h, w = stdscr.getmaxyx()
    for i in range(start_angle, end_angle):
        rad = math.radians(i)
        y = round(y_on_screen + radius * math.sin(rad))
        x = round(x_on_screen + radius * 2 * math.cos(rad))
        if 0 <= y < h - 1 and 0 <= x < w - 2:
            stdscr.addch(y, x, '*', color_pair)
    if indicator_char and angle is not None:
        y = round(y_on_screen + radius * math.sin(angle))
        x = round(x_on_screen + radius * 2 * math.cos(rad))
        if 0 <= y < h - 1 and 0 <= x < w - 2:
            stdscr.addch(y, x, indicator_char, color_pair | curses.A_BOLD)

# --- Menus ---
def draw_menu(stdscr, title, options):
    stdscr.bkgd(' ', curses.color_pair(1))
    stdscr.clear()
    h, w = stdscr.getmaxyx()
    stdscr.addstr(2, (w - len(title)) // 2, title)
    for i, option in enumerate(options):
        stdscr.addstr(4 + i, (w - len(option)) // 2, f"{i + 1}. {option}")
    stdscr.refresh()
    while True:
        key = stdscr.getkey()
        if '1' <= key <= str(len(options)):
            return int(key) - 1
        elif key == 'q':
            return None

def choose_planet(stdscr, game_data):
    planets = [p for p in game_data.keys() if p != "last_reset_utc"]
    choice_index = draw_menu(stdscr, "Choose a Planet (q to quit)", planets)
    return planets[choice_index] if choice_index is not None else None

def choose_dig_site(stdscr, game_data, planet):
    sites = game_data.get(planet, {})
    available_sites = [name for name, data in sites.items() if not data.get('depleted', False)]
    if not available_sites:
        stdscr.clear()
        msg = f"All dig sites on {planet} are depleted."
        stdscr.addstr(2, (stdscr.getmaxyx()[1] - len(msg)) // 2, msg)
        stdscr.addstr(4, (stdscr.getmaxyx()[1] - 20) // 2, "Press any key...")
        stdscr.getch()
        return None
    choice_index = draw_menu(stdscr, f"Choose a Dig Site on {planet} (q to quit)", available_sites)
    return available_sites[choice_index] if choice_index is not None else None

# --- Game Loops (Combat, Main) ---
def combat_loop(stdscr, player_health, enemy):
    h, w = stdscr.getmaxyx()
    enemy_health = enemy['health']
    while player_health > 0 and enemy_health > 0:
        stdscr.clear()
        draw_health_bar(stdscr, h // 2 - 5, w // 2 - 15, "Player", player_health, 100, 20)
        draw_health_bar(stdscr, h // 2 - 3, w // 2 - 15, "Enemy ", enemy_health, 50, 20)
        stdscr.addstr(h // 2, w // 2 - 10, "1. Attack")
        stdscr.addstr(h // 2 + 1, w // 2 - 10, "2. Flee")
        stdscr.refresh()
        key = stdscr.getkey()
        if key == '1':
            damage = random.randint(15, 25)
            enemy_health -= damage
            stdscr.addstr(h // 2 + 3, w // 2 - 15, f"You hit the enemy for {damage} damage!")
        elif key == '2':
            if random.random() < 0.5:
                stdscr.addstr(h // 2 + 3, w // 2 - 15, "You successfully fled!")
                stdscr.refresh()
                time.sleep(1.5)
                return player_health, 'FLED'
            else:
                stdscr.addstr(h // 2 + 3, w // 2 - 15, "You failed to flee!")
        else: continue
        stdscr.refresh()
        time.sleep(1.5)
        if enemy_health > 0:
            damage = random.randint(5, 15)
            player_health -= damage
            stdscr.addstr(h // 2 + 4, w // 2 - 15, f"The enemy hits you for {damage} damage!")
            stdscr.refresh()
            time.sleep(1.5)
    return (0, 'DEFEATED') if player_health <= 0 else (player_health, 'VICTORY')

def game_loop(stdscr, game_map, site_data, planet_name, site_name, current_health):
    h, w = stdscr.getmaxyx()
    map_h, map_w = len(game_map), len(game_map[0])
    GREEN_RING, RED_RING, YELLOW_RING = curses.color_pair(2), curses.color_pair(3), curses.color_pair(4)
    PLAYER_COLOR, ENEMY_PASSIVE_COLOR, ENEMY_AGGRO_COLOR = curses.color_pair(5), curses.color_pair(6), curses.color_pair(7)

    stdscr.nodelay(True)
    last_heal_time = time.time()
    heal_interval = 2.5

    player_health = current_health
    coords = set()
    player_x, player_y = place_on_map(game_map, coords)
    coords.add((player_x, player_y))

    treasures = []
    for _ in range(site_data.get('major_treasure', 0)):
        while True:
            tx, ty = place_on_map(game_map, coords)
            if math.dist((player_x, player_y), (tx, ty)) > 30:
                treasures.append({'x': tx, 'y': ty, 'type': 'major'})
                coords.add((tx, ty))
                break
    for _ in range(site_data.get('minor_treasures', 0)):
        tx, ty = place_on_map(game_map, coords)
        treasures.append({'x': tx, 'y': ty, 'type': 'minor'})
        coords.add((tx, ty))

    enemy_char_map = {"Tatooine": "W", "Alderaan": "K", "Hoth": "T", "Makeb": "V"}
    fauna_name_map = {
        "Tatooine": "Womp Rat",
        "Alderaan": "Kath Hound",
        "Hoth": "Tauntaun",
        "Makeb": "Vrake"
    }
    enemy_char = enemy_char_map.get(planet_name, 'E')

    enemies = []
    for i in range(10):
        ex, ey = place_on_map(game_map, coords)
        enemies.append({'x': ex, 'y': ey, 'char': enemy_char, 'color': ENEMY_PASSIVE_COLOR, 'health': 50, 'id': i})
        coords.add((ex, ey))

    while True:
        current_time = time.time()
        if current_time - last_heal_time >= heal_interval:
            if player_health < 100:
                player_health += 1
            last_heal_time = current_time

        try:
            key = stdscr.getkey()
        except curses.error:
            key = None

        if key is not None:
            new_y, new_x = player_y, player_x
            if key in ('e', 'KEY_UP'): new_y -= 1
            elif key in ('d', 'KEY_DOWN'): new_y += 1
            elif key in ('s', 'KEY_LEFT'): new_x -= 1
            elif key in ('f', 'KEY_RIGHT'): new_x += 1
            elif key == 'q': break
            elif key == ' ':
                if not treasures: continue
                dists = [(math.dist((player_x, player_y), (t['x'], t['y'])), t) for t in treasures]
                dist, nearest_treasure = min(dists, key=lambda item: item[0])
                
                radius = 2
                
                draw_map_viewport(stdscr, game_map, cam_y, cam_x, enemies)
                stdscr.addstr(player_screen_y, player_screen_x, '@', PLAYER_COLOR)
                for i in range(0, 361, 15):
                    draw_ring(stdscr, player_screen_y, player_screen_x, radius, YELLOW_RING, start_angle=0, end_angle=i)
                    stdscr.refresh()
                    time.sleep(0.05)
                
                draw_map_viewport(stdscr, game_map, cam_y, cam_x, enemies)
                stdscr.addstr(player_screen_y, player_screen_x, '@', PLAYER_COLOR)

                if dist < 3:
                    treasures.remove(nearest_treasure)
                    treasure_type = nearest_treasure['type']
                    quantity = 3 if treasure_type == 'major' else 1
                    update_resources("Salvage", quantity)
                    if treasure_type == 'major':
                        site_data['depleted'] = True
                        save_game_data(game_data)
                        msg = f"Major treasure found! ({quantity} salvage)"
                        stdscr.addstr(h // 2 + 5, (w - len(msg)) // 2, msg)
                        stdscr.refresh()
                        time.sleep(2)
                        stdscr.nodelay(False)
                        return player_health
                    else:
                        msg = f"Minor treasure found! ({quantity} salvage)"
                        stdscr.addstr(h // 2 + 5, (w - len(msg)) // 2, msg)
                        stdscr.refresh()
                        time.sleep(1)
                elif dist < 15:
                    angle = math.atan2(nearest_treasure['y'] - player_y, nearest_treasure['x'] - player_x)
                    draw_ring(stdscr, player_screen_y, player_screen_x, 1, GREEN_RING, 'X', angle)
                    stdscr.refresh()
                    time.sleep(0.75)
                else:
                    draw_ring(stdscr, player_screen_y, player_screen_x, 2, RED_RING)
                    stdscr.refresh()
                    time.sleep(0.75)

            if 0 <= new_y < map_h and 0 <= new_x < map_w and game_map[new_y][new_x] == '.':
                player_y, player_x = new_y, new_x

        stdscr.clear()
        cam_y, cam_x = player_y - h // 2, player_x - w // 2
        draw_map_viewport(stdscr, game_map, cam_y, cam_x, enemies)
        player_screen_y, player_screen_x = h // 2, w // 2
        stdscr.addstr(player_screen_y, player_screen_x, '@', PLAYER_COLOR)
        
        draw_health_bar(stdscr, 0, 1, "Health", player_health, 100, w // 4)
        draw_resources_display(stdscr)
        
        stdscr.refresh()

        enemy_to_fight = None
        for enemy in enemies:
            dist_to_player = math.dist((player_x, player_y), (enemy['x'], enemy['y']))
            if dist_to_player < 5:
                enemy['color'] = ENEMY_AGGRO_COLOR
                if dist_to_player > 1:
                    dx = 1 if player_x > enemy['x'] else -1 if player_x < enemy['x'] else 0
                    dy = 1 if player_y > enemy['y'] else -1 if player_y < enemy['y'] else 0
                    new_ex, new_ey = enemy['x'] + dx, enemy['y'] + dy
                    if game_map[new_ey][new_ex] == '.':
                        enemy['x'], enemy['y'] = new_ex, new_ey
                if player_x == enemy['x'] and player_y == enemy['y']:
                    enemy_to_fight = enemy
            else:
                enemy['color'] = ENEMY_PASSIVE_COLOR
        
        if enemy_to_fight:
            stdscr.nodelay(False)
            player_health, result = combat_loop(stdscr, player_health, enemy_to_fight)
            stdscr.nodelay(True)
            
            if result == 'VICTORY':
                enemies = [e for e in enemies if e['id'] != enemy_to_fight['id']]
                # --- CHANGE: Updated resource name ---
                update_resources("Biochemicals", 1)
                
                fauna_name = fauna_name_map.get(planet_name, "creature")
                # --- CHANGE: Updated resource name in message ---
                msg = f"Harvested 1 unit of Biochemicals from the defeated {fauna_name}."
                
                stdscr.addstr(h // 2 + 5, (w - len(msg)) // 2, msg)
                stdscr.refresh()
                time.sleep(2)
            elif result == 'DEFEATED':
                msg = "You have been defeated!"
                stdscr.clear()
                stdscr.addstr(h // 2, (w - len(msg)) // 2, msg)
                stdscr.refresh()
                time.sleep(2)
                stdscr.nodelay(False)
                return 0
        
        time.sleep(0.01)

    stdscr.nodelay(False)
    return player_health

# --- Main ---
def main(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_WHITE, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_RED, -1)
    curses.init_pair(4, curses.COLOR_YELLOW, -1)
    curses.init_pair(5, curses.COLOR_CYAN, -1)
    curses.init_pair(6, curses.COLOR_YELLOW, -1)
    curses.init_pair(7, curses.COLOR_RED, -1)
    stdscr.bkgd(' ', curses.color_pair(1))

    global game_data
    game_data = load_game_data()
    if check_and_reset_sites(game_data):
        stdscr.addstr(0, 0, "Dig sites have been reset for the day!")
        stdscr.refresh()
        time.sleep(2)

    player_health = 100
    while True:
        chosen_planet = choose_planet(stdscr, game_data)
        if not chosen_planet: break
        chosen_site = choose_dig_site(stdscr, game_data, chosen_planet)
        if chosen_site:
            game_map = create_irregular_map(150, 50, 16000)
            player_health = game_loop(stdscr, game_map, game_data[chosen_planet][chosen_site], chosen_planet, chosen_site, player_health)
            if player_health <= 0:
                player_health = 100

if __name__ == "__main__":
    curses.wrapper(main)

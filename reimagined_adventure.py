#!/usr/bin/env python3
"""
Reimagined Adventure — a tiny, expandable text adventure.

Features
- Procedurally assembles a mini-world each run (rooms, items, exits).
- Lightweight parser: go/move, take/get, use, look/examine, inventory, help, quit.
- A small puzzle with multiple endings.
- Designed as a single file so you can read and extend it easily.

Run:  python3 reimagined_adventure.py
"""
from __future__ import annotations
import random
import textwrap
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ------------------------------
# Data structures
# ------------------------------

@dataclass
class Item:
    name: str
    description: str
    portable: bool = True
    usable_with: Optional[str] = None  # name of target this item can be used with

@dataclass
class Room:
    key: str
    title: str
    description: str
    exits: Dict[str, str] = field(default_factory=dict)  # direction -> room key
    items: List[Item] = field(default_factory=list)
    locked: bool = False
    lock_name: Optional[str] = None  # what text describes the lock (e.g., 'iron gate')

@dataclass
class World:
    rooms: Dict[str, Room]
    start: str
    goal: str

# ------------------------------
# World generation
# ------------------------------

ROOM_TITLES = [
    ("Tumbledown Gate", "A leaning arch of stone guards the path. Moss carpets every crevice."),
    ("Whispering Pines", "Wind threads through tall trees, carrying secrets and the scent of resin."),
    ("Forgotten Courtyard", "Cracked tiles form a mosaic of constellations underfoot."),
    ("Glimmering Pool", "Water mirrors the sky. Coins wink from the depths."),
    ("Crumbling Library", "Shelves sag with worm-eaten books and ideas that never died."),
    ("Echoing Cavern", "Your words rebound, returning slightly changed—like they learned something."),
]

DIRECTIONS = ["north", "south", "east", "west"]

LORE_SNIPPETS = [
    "They say the gate remembers every traveler who ever touched it.",
    "A blackbird watches you with a scholar's patience.",
    "An inscription: 'All maps are apologies for the land.'",
    "Footprints circle twice, then vanish—a ritual of the cautious.",
    "You smell rain that hasn't fallen yet.",
]


def generate_world(seed: Optional[int] = None) -> World:
    rng = random.Random(seed)

    # Pick 4-5 rooms for a tiny map
    chosen = rng.sample(ROOM_TITLES, k=5)
    rooms: Dict[str, Room] = {}
    for i, (title, desc) in enumerate(chosen):
        key = f"r{i}"
        fluff = rng.choice(LORE_SNIPPETS)
        rooms[key] = Room(
            key=key,
            title=title,
            description=f"{desc} {fluff}",
            exits={},
            items=[],
        )

    # Link rooms in a simple loop, then add a couple cross-links
    keys = list(rooms.keys())
    for i, k in enumerate(keys):
        nxt = keys[(i + 1) % len(keys)]
        rooms[k].exits["east"] = nxt
        rooms[nxt].exits["west"] = k

    # Cross links
    if len(keys) >= 4:
        rooms[keys[0]].exits["north"] = keys[2]
        rooms[keys[2]].exits["south"] = keys[0]
        rooms[keys[1]].exits["south"] = keys[3]
        rooms[keys[3]].exits["north"] = keys[1]

    # Place items
    key_item = Item("rusty key", "A heavy key with teeth like a skyline.")
    lens_item = Item("prism lens", "A shard of crystal that splits light into choices.")
    rope_item = Item("coiled rope", "Frayed but trustworthy.")

    rng.choice(list(rooms.values())).items.append(key_item)
    rng.choice(list(rooms.values())).items.append(lens_item)
    rng.choice(list(rooms.values())).items.append(rope_item)

    # Choose goal room and lock it
    goal_key = rng.choice(keys)
    lock_text = rng.choice(["iron gate", "braided thorns", "shimmering seal"]) 
    rooms[goal_key].locked = True
    rooms[goal_key].lock_name = lock_text

    # Seed a clue in a different room
    if len(keys) > 1:
        clue_room = rooms[rng.choice([k for k in keys if k != goal_key])]
        clue_room.items.append(Item(
            name="scribbled note",
            description=(
                "'Seek the " + lock_text + ".' There's a sketch of a key shining through a prism.\n"
                "Below it: 'Three paths, one truth.'"
            ),
            portable=False,
        ))

    return World(rooms=rooms, start=keys[0], goal=goal_key)

# ------------------------------
# Game engine
# ------------------------------

class Game:
    def __init__(self, world: World, seed: Optional[int] = None):
        self.world = world
        self.current = world.start
        self.rng = random.Random(seed)
        self.inventory: List[Item] = []
        self.used_lens = False
        self.unlocked_goal = False
        self.game_over = False

    # ---- Utility ----
    def room(self) -> Room:
        return self.world.rooms[self.current]

    def find_item(self, where: List[Item], name: str) -> Optional[Item]:
        name = name.lower()
        for it in where:
            if it.name.lower() == name:
                return it
        return None

    # ---- Rendering ----
    def say(self, text: str) -> None:
        print("\n" + textwrap.fill(text, width=80))

    def look(self) -> None:
        r = self.room()
        self.say(f"{r.title}\n{'-' * len(r.title)}\n{r.description}")
        if r.items:
            names = ", ".join([it.name for it in r.items])
            self.say(f"You notice: {names}.")
        exits = ", ".join(sorted(r.exits.keys())) or "nowhere"
        self.say(f"Exits: {exits}.")
        if r.locked:
            self.say(f"An obstacle blocks progress here: {r.lock_name}.")

    # ---- Commands ----
    def cmd_go(self, direction: str) -> None:
        r = self.room()
        direction = direction.lower()
        if direction not in r.exits:
            self.say("You can't go that way.")
            return
        target_key = r.exits[direction]
        # If trying to enter the goal room while locked, block
        if target_key == self.world.goal and self.world.rooms[target_key].locked:
            self.say(f"The {self.world.rooms[target_key].lock_name} bars your path.")
            return
        self.current = target_key
        self.look()

    def cmd_take(self, name: str) -> None:
        r = self.room()
        item = self.find_item(r.items, name)
        if not item:
            self.say("You don't see that here.")
            return
        if not item.portable:
            self.say("It won't budge, but you can study it.")
            return
        r.items.remove(item)
        self.inventory.append(item)
        self.say(f"Taken: {item.name}.")

    def cmd_inventory(self) -> None:
        if not self.inventory:
            self.say("Your pockets are philosophically empty.")
        else:
            names = ", ".join(it.name for it in self.inventory)
            self.say(f"You carry: {names}.")

    def cmd_look(self, target: Optional[str]) -> None:
        if not target:
            self.look()
            return
        # Look at item in room or inventory
        r = self.room()
        it = self.find_item(r.items, target) or self.find_item(self.inventory, target)
        if it:
            self.say(it.description)
        else:
            self.say("You find nothing special.")

    def attempt_unlock(self) -> None:
        goal = self.world.rooms[self.world.goal]
        # Multiple ways to resolve: key, or prism puzzle
        has_key = any(it.name == "rusty key" for it in self.inventory)
        if has_key:
            goal.locked = False
            self.unlocked_goal = True
            self.say("You turn the rusty key. The lock protests, then yields.")
            return
        if self.used_lens:
            # Lens riddle: choose a beam (three choices)
            self.say("Through the prism lens, three beams split across the lock: red, green, blue.")
            choice = input("> choose beam (red/green/blue): ").strip().lower()
            if choice in {"red", "green", "blue"}:
                # Weighted to make it a little unpredictable
                correct = self.rng.choice(["red", "green", "blue", "green"])  # green slightly favored
                if choice == correct:
                    goal.locked = False
                    self.unlocked_goal = True
                    self.say(f"The {choice} beam unthreads the seal. It sighs open.")
                else:
                    self.say("The beam fizzles. The seal remains. Perhaps try another approach.")
            else:
                self.say("Indecision refracts into nothing.")
        else:
            self.say("You need a way to work on the lock. A tool, or a trick of light?")

    def cmd_use(self, name: str, target: Optional[str]) -> None:
        name = name.lower()
        inv = self.find_item(self.inventory, name)
        if not inv:
            self.say("You don't have that.")
            return

        # Using prism lens on lock
        if inv.name == "prism lens" and (target in {"lock", "gate", "seal", None}):
            self.used_lens = True
            self.say("You hold the lens to the obstacle. Light fractures into clues.")
            self.attempt_unlock()
            return

        # Using rope contextually
        if inv.name == "coiled rope":
            # If in goal room but locked, maybe you can climb around?
            if self.current == self.world.goal and self.world.rooms[self.world.goal].locked:
                self.say("You try to climb around, but the rope needs an anchor you can't reach.")
            else:
                self.say("You coil and uncoil the rope. It inspires confidence, if not progress.")
            return

        # Using key on lock
        if inv.name == "rusty key" and (target in {"lock", "gate", "seal", None}):
            self.attempt_unlock()
            return

        self.say("That doesn't seem helpful right now.")

    # ---- Win / Endings ----
    def check_win(self) -> bool:
        if self.current != self.world.goal:
            return False
        if self.world.rooms[self.world.goal].locked:
            return False
        # Endings depend on whether you used the lens or the key
        self.game_over = True
        if self.unlocked_goal and self.used_lens:
            self.say("You step through. The land tilts, reimagined by light. You found the clever way.")
        elif self.unlocked_goal:
            self.say("You step through. The old mechanisms still work, and so do you. A classic victory.")
        else:
            # Rare: reached goal after it became unlocked indirectly
            self.say("You slip through as if it were always open. Perhaps it was.")
        self.say("THE END")
        return True

    # ---- Parser ----
    def handle(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        parts = line.split()
        verb = parts[0].lower()
        rest = parts[1:]

        if verb in {"go", "move"}:
            if not rest:
                self.say("Go where?")
            else:
                self.cmd_go(rest[0])
                if not self.game_over:
                    self.check_win()
            return
        if verb in {"look", "examine", "l"}:
            self.cmd_look(" ".join(rest) if rest else None)
            return
        if verb in {"take", "get"}:
            if not rest:
                self.say("Take what?")
            else:
                self.cmd_take(" ".join(rest))
            return
        if verb in {"use"}:
            if not rest:
                self.say("Use what?")
            else:
                # allow 'use X on Y'
                if " on " in line:
                    before, after = line[4:].split(" on ", 1)
                    self.cmd_use(before.strip(), after.strip())
                else:
                    self.cmd_use(" ".join(rest), None)
            return
        if verb in {"inventory", "inv", "i"}:
            self.cmd_inventory()
            return
        if verb in {"help", "?"}:
            self.say(
                "Commands: go/move <dir>, look [thing], take <item>, use <item> [on <target>],\n"
                "inventory (i), help, quit. Directions: north, south, east, west."
            )
            return
        if verb in {"quit", "exit"}:
            self.say("You let the adventure continue without you—for now.")
            self.game_over = True
            return

        self.say("Your words scatter like leaves. Try a different phrasing.")

    # ---- Game loop ----
    def start(self) -> None:
        self.say("Welcome to Reimagined Adventure! Type 'help' for commands.")
        self.look()
        while not self.game_over:
            try:
                line = input("\n> ")
            except (EOFError, KeyboardInterrupt):
                print()
                self.say("The story closes softly.")
                break
            self.handle(line)
            if not self.game_over:
                self.check_win()


def main() -> None:
    # Seed is random by default. Uncomment to make the map repeatable.
    # seed = 42
    seed = None
    world = generate_world(seed)
    game = Game(world, seed)
    game.start()


if __name__ == "__main__":
    main()

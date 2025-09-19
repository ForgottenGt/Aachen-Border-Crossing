import pygame
import sys
import random
import sqlite3
# --- Initialisation --- #
pygame.init()
pygame.font.init()
font = pygame.font.SysFont('VT323', 50)
clock = pygame.time.Clock()
Black = (0,0,0)
White = (255,255,255)
FPS = 60
SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 800
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
background_image = pygame.image.load('Images/Background1.png').convert()
background_image = pygame.transform.scale(background_image, (SCREEN_WIDTH, SCREEN_HEIGHT))
# convert scaled size to ints to avoid float dimensions errors
background_image2 = pygame.image.load('Images/Background9.png').convert()
background_image2 = pygame.transform.scale(background_image2, (int(SCREEN_WIDTH / 1.4945), int(SCREEN_HEIGHT / 1.520)))
pygame.display.set_caption("Rhineland Border Control - Aachen Checkpoint")
pygame.mouse.set_visible(True)
conn = sqlite3.connect('example.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS high_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    score INTEGER
)
''')
lose = False
exit = False
player_color = (100, 100, 100)
player_radius = 5
player_grow = 1.05
player_rect = pygame.Rect(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, 50, 50)
music = True
working = True
npc_restricted = False   # renamed from 'round' to avoid shadowing built-in
npc_spawning = True
setup1 = True
setup3 = True
money_subtracted = False
change_documents = True
immigrants_processed = -1
immigrants_wrong = 0
player_name = None  # <-- added to store player's name

# Add: one-time flag so flashing runs once then game resumes
low_balance_flash_done = False

info_display_active = False  # Initialize info_display_active outside the game loop
current_info_index = 1  # Start with the first info file

# --- Sprite Classes --- #
class InfoSprite(pygame.sprite.Sprite):
    def __init__(self, img_path, x, y, small_size, large_size, label, vx=0, vy=0):
        super().__init__()
        self.img_path = img_path
        self.small_size = small_size
        self.large_size = large_size
        self.label = label
        # robust image loading: fall back to a simple surface if load fails
        try:
            self.image = pygame.image.load(img_path).convert_alpha()
            self.image = pygame.transform.scale(self.image, small_size)
        except Exception as e:
            print(f"Image load error for '{img_path}': {e} -- using placeholder")
            self.image = pygame.Surface(small_size, pygame.SRCALPHA)
            self.image.fill((150,150,150,255))
        self.rect = self.image.get_rect(topleft=(x, y))
        # movement velocity in pixels per frame
        self.vx = vx
        self.vy = vy
        self.timer = 10 * FPS  # 10-second timer in frames

    def update(self, player_radius, mouse_pos):
        # move sprite first
        if self.vx or self.vy:
            self.rect.x += int(self.vx)
            self.rect.y += int(self.vy)
            # left boundary and bounce
            if self.rect.left < 225:
                self.rect.left = 225
                self.vx = -self.vx
            # top/bottom bounce
            if self.rect.top < 0:
                self.rect.top = 0
                self.vy = -self.vy
            if self.rect.bottom > SCREEN_HEIGHT:
                self.rect.bottom = SCREEN_HEIGHT
                self.vy = -self.vy

            if npc_restricted:
                if self.rect.right > SCREEN_WIDTH / 2 + 50:
                    self.rect.right = SCREEN_WIDTH / 2 + 50

        if player_radius >= 4 and self.rect.collidepoint(mouse_pos):
            self.image = pygame.image.load(self.img_path).convert_alpha()
            self.image = pygame.transform.scale(self.image, self.large_size)
        else:
            self.image = pygame.image.load(self.img_path).convert_alpha()
            self.image = pygame.transform.scale(self.image, self.small_size)

        self.timer -= 1  # Decrease timer every frame

# --- Create Sprites --- #
NPC_x = 225
NPC_y = 200
NPC_move = 500
spawn_x = 225  # ensure spawn_x is always defined before any spawn uses
NPCs_info = [
    ("Images/P1F.png", (NPC_x,NPC_y), (300,325), (300,325), "Bertram Heinze - German"),
    ("Images/P2M.png", (NPC_x,NPC_y), (300,325), (300,325), "Fernand Salzmann - German"),
    ("Images/P3M.png", (NPC_x,NPC_y), (300,325), (300,325), "Gaspard Poincaré - Walloon/French"),
    ("Images/P4M.png", (NPC_x,NPC_y), (300,325), (300,325), "Burkhard Hoff - Walloon/French"),
    ("Images/P5F.png", (NPC_x,NPC_y), (300,325), (300,325), "Gudrun Auer - Bavarian"),
    ("Images/P6F.png", (NPC_x,NPC_y), (300,325), (300,325), "Olivia Lefevre - German"),
    ("Images/P7M.png", (NPC_x,NPC_y), (300,325), (300,325), "Trude Stoll - Imperial Diplomat"),
    ("Images/P8F.png", (NPC_x,NPC_y), (300,325), (300,325), "Elie Deramoudt - Bavarian")
]
# Add acceptance rules mapping for each NPC name -> set of acceptable document prompts
ACCEPT_RULES = {
    "Bertram Heinze - German": {"Bundesrepublik-Deutscheland Reisepass", "Deusche-Democratik Republic Reisepass"},
    "Fernand Salzmann - German": {"Bundesrepublik-Deutscheland Reisepass", "Deusche-Democratik Republic Reisepass"},
    "Gaspard Poincaré - Walloon/French": {"Royaume of Wallonia Passeport", "French Visa"},
    "Burkhard Hoff - Walloon/French": {"Royaume of Wallonia Passeport", "French Visa"},
    "Gudrun Auer - Bavarian": {"Freistaat Bayern Reisepass"},
    "Olivia Lefevre - German": {"Bundesrepublik-Deutscheland Reisepass", "Deusche-Democratik Republic Reisepass"},
    "Trude Stoll - Imperial Diplomat": {"DDR Diplomatic Reisepass1", "DDR Diplomatic Reisepass2"},
    "Elie Deramoudt - Bavarian": {"Freistaat Bayern Reisepass"},
}
NPCs = pygame.sprite.Group()
for img, pos, small, large, label in NPCs_info:
    NPC = InfoSprite(img, pos[0], pos[1], small, large, label, vx=NPC_move, vy=0)
    if npc_restricted == False and npc_spawning == True:
      NPCs.add(NPC)
      npc_spawning = False
NPC_list = list(NPCs)  # keep a list for easy random choice
all_sprites = pygame.sprite.Group()
def draw_ui(surface, prompt, score, remaining_time):
    pygame.draw.rect(surface, (30, 30, 30), (0, 0, SCREEN_WIDTH, 75))
    ui_font = pygame.font.SysFont('Times New Roman', 32)
    # use prompt parameter (was referencing undefined 'label')
    info_text = f"Applicant: {label} | Current Balance: ${score} | Time Left: {remaining_time // FPS}s"
    text_surface = ui_font.render(info_text, True, White)

    surface.blit(text_surface, (20, 15))

sprites_info = [
    ("Images/info1.png", (300, 600), (50, 75), (100, 150), "Information File"),
    ("Images/Passport1.png", (150, 600), (50, 75), (100, 150), "Bundesrepublik-Deutscheland Reisepass"),
    ("Images/Passport2.png", (150, 600), (50, 75), (100, 150), "Deusche-Democratik Republic Reisepass"),
    ("Images/Passport3.png", (150, 600), (50, 75), (100, 150), "Royaume of Wallonia Passeport"),
    ("Images/Passport4.png", (150, 600), (50, 75), (100, 150), "Freistaat Bayern Reisepass"),
    ("Images/French Visa.png", (150, 600), (50, 75), (100, 150), "French Visa"),
    ("Images/DDR Passport2.png", (150, 600), (75, 75), (150, 150), "DDR Diplomatic Reisepass1"),
    ("Images/DDR Passport3.png", (150, 600), (75, 75), (150, 150), "DDR Diplomatic Reisepass2"),
]
# create a standalone info sprite from the first entry and do not include it in random selection
info_entry = sprites_info[0]
info_sprite = InfoSprite(info_entry[0], info_entry[1][0], info_entry[1][1], info_entry[2], info_entry[3], info_entry[4])

# create the rest of the sprites (these will be used for the random selection)
sprites = pygame.sprite.Group()
for img, pos, small, large, label in sprites_info[1:]:
    sprite = InfoSprite(img, pos[0], pos[1], small, large, label)
    sprites.add(sprite)
sprite_list = list(sprites)  # keep a list for easy random choice
all_sprites = pygame.sprite.Group()

Tracks = [
    "Sounds/Track 1 - Die Wacht am Rhein.mp3",
    "Sounds/Track 2 - Pariser Einzugsmarsch.mp3",
    "Sounds/Track 3 - Heil dir im Siegerkranz.mp3",
    "Sounds/Track 4 - Siegesmarsch von Metz.mp3",
    "Sounds/Track 5 - Die Wacht am Rhein (Bells).mp3",
    "Sounds/Track 6 - Das Enheitsfrontlied.mp3",
    "Sounds/Track 7 - One out of a Billion.mp3",
    "Sounds/Track 8 - Cutting Ties.mp3",
]
score = 12

current_track_index = 0
MUSIC_END = pygame.USEREVENT + 1
pygame.mixer.music.set_endevent(MUSIC_END)
if music:
    try:
        pygame.mixer.music.load(Tracks[current_track_index])
        pygame.mixer.music.play()
        #pygame.mixer.music.set_volume(0)
    except Exception as e:
        print("Music load/play error:", e)

game_state = 'menu'

def draw_menu(surface):
    surface.blit(background_image, (0, 0))
    surface.blit(background_image2, (225, 25))
    title_font = pygame.font.SysFont('VT323', 72)
    title = title_font.render("Rhineland Border Control", True, White)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3))
    surface.blit(title, title_rect)

    btn_font = pygame.font.SysFont('VT323', 48)
    start_surf = btn_font.render("Begin", True, White)
    quit_surf = btn_font.render("Quit Job", True, White)
    music_surf = btn_font.render("Music Toggle", True, White)
    tutorial_surf = btn_font.render("Tutorial", True, White)
    start_rect = start_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
    quit_rect = quit_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 80))
    music_rect = music_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 160))

    pygame.draw.rect(surface, (50, 50, 50), start_rect.inflate(40, 20))
    pygame.draw.rect(surface, (50, 50, 50), quit_rect.inflate(40, 20))
    pygame.draw.rect(surface, (50, 50, 50), music_rect.inflate(40, 20))
    surface.blit(start_surf, start_rect)
    surface.blit(quit_surf, quit_rect)
    surface.blit(music_surf, music_rect)

    return start_rect, quit_rect, music_rect

def draw_game_mechanics(surface):
    btn_font = pygame.font.SysFont('VT323', 48)
    pass_surf = btn_font.render("Pass", True, (White))
    pass_rect = pass_surf.get_rect(center=(110,200))
    deny_surf = btn_font.render("Deny", True, (White))
    deny_rect = deny_surf.get_rect(center=(110,300))

    pygame.draw.rect(surface, (50, 150, 50), pass_rect.inflate(40, 20))
    pygame.draw.rect(surface, (150, 50, 50), deny_rect.inflate(40, 20))

    surface.blit(pass_surf,pass_rect)
    surface.blit(deny_surf,deny_rect)

    return pass_rect, deny_rect

def draw_tutorial(surface):
    # Load and scale GreyBackground.png for the tutorial background
    tutorial_background = pygame.image.load('Images/Background3.png').convert()
    tutorial_background = pygame.transform.scale(tutorial_background, (SCREEN_WIDTH, SCREEN_HEIGHT))
    surface.blit(tutorial_background, (0, 0))

    title_font = pygame.font.SysFont('VT323', 56)
    title = title_font.render("Tutorial", True, White)
    title_rect = title.get_rect(center=(SCREEN_WIDTH // 2, 100))
    surface.blit(title, title_rect)

    body_font = pygame.font.SysFont('VT323', 28)
    instructions = [
        "Welcome to the Aachen Checkpoint, Frontline of the Rhineland.",
        "As a border control officer, your assigned duty is to inspect the documents of all entrants to ensure compliance.",
        "You will have to verify their identity and authenticity of their documents in ten seconds.",
        "You have full authorisation to all documentation on entrants/persons seeking entry.",
        "Entrants may possess false or incorrect documentation. Reject these entrants.",
        "Use Pass / Deny buttons to accept or reject entrants.",
        "Rules may change in accordance to government policy.",
        "Good luck, Glory to the Rhine."
    ]
    y = 180
    for line in instructions:
        line_surf = body_font.render(line, True, White)
        line_rect = line_surf.get_rect(center=(SCREEN_WIDTH // 2, y))
        surface.blit(line_surf, line_rect)
        y += 36

    btn_font = pygame.font.SysFont('VT323', 44)
    back_surf = btn_font.render("Back", True, White)
    begin_surf = btn_font.render("Begin", True, White)
    info_surf = btn_font.render("View Info", True, White)
    back_rect = back_surf.get_rect(center=(SCREEN_WIDTH // 2 - 200, SCREEN_HEIGHT - 80))
    begin_rect = begin_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 80))
    info_rect = info_surf.get_rect(center=(SCREEN_WIDTH // 2 + 200, SCREEN_HEIGHT - 80))
    pygame.draw.rect(surface, (80, 80, 80), back_rect.inflate(30, 20))
    pygame.draw.rect(surface, (80, 80, 80), begin_rect.inflate(30, 20))
    pygame.draw.rect(surface, (80, 80, 80), info_rect.inflate(30, 20))
    surface.blit(back_surf, back_rect)
    surface.blit(begin_surf, begin_rect)
    surface.blit(info_surf, info_rect)

    return back_rect, begin_rect, info_rect

def display_info_file(surface, current_info_index):
    # Display the current info file in full screen with navigation buttons
    info_image_path = f"Images/info{current_info_index}.png"
    try:
        info_image = pygame.image.load(info_image_path).convert_alpha()
        info_image = pygame.transform.scale(info_image, (SCREEN_WIDTH/2.2, SCREEN_HEIGHT))
        surface.blit(info_image, (0, 0))
    except pygame.error:
        error_font = pygame.font.SysFont('VT323', 32)
        error_text = error_font.render("No more info files available.", True, White)
        error_rect = error_text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        surface.blit(error_text, error_rect)

    # Draw navigation buttons
    btn_font = pygame.font.SysFont('VT323', 44)
    prev_surf = btn_font.render("Previous", True, White)
    next_surf = btn_font.render("Next", True, White)
    close_surf = btn_font.render("Close", True, White)
    prev_rect = prev_surf.get_rect(center=(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT - 80))
    next_rect = next_surf.get_rect(center=(SCREEN_WIDTH // 2 + 150, SCREEN_HEIGHT - 80))
    close_rect = close_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT - 150))
    pygame.draw.rect(surface, (80, 80, 80), prev_rect.inflate(30, 20))
    pygame.draw.rect(surface, (80, 80, 80), next_rect.inflate(30, 20))
    pygame.draw.rect(surface, (80, 80, 80), close_rect.inflate(30, 20))
    surface.blit(prev_surf, prev_rect)
    surface.blit(next_surf, next_rect)
    surface.blit(close_surf, close_rect)

    return prev_rect, next_rect, close_rect

# add non-blocking name entry UI
def ask_name(prompt_text="Enter your name"):
    name = ""
    entry_active = True
    box_rect = pygame.Rect(SCREEN_WIDTH//2 - 300, SCREEN_HEIGHT//2 - 30, 600, 60)
    small_font = pygame.font.SysFont('VT323', 28)
    while entry_active:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN:
                    entry_active = False
                elif ev.key == pygame.K_BACKSPACE:
                    name = name[:-1]
                else:
                    if ev.unicode and len(ev.unicode) == 1:
                        name += ev.unicode
        # draw overlay UI
        screen.blit(background_image, (0,0))
        screen.blit(background_image2, (225, 25))
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0,0,0,160))
        screen.blit(overlay, (0,0))
        pygame.draw.rect(screen, (240,240,240), box_rect)
        pygame.draw.rect(screen, (100,100,100), box_rect, 3)
        prompt_surf = small_font.render(prompt_text, True, (10,10,10))
        screen.blit(prompt_surf, (box_rect.x + 8, box_rect.y - 30))
        name_surf = small_font.render(name, True, (10,10,10))
        screen.blit(name_surf, (box_rect.x + 10, box_rect.y + 16))
        info_surf = small_font.render("Press Enter to confirm", True, (200,200,200))
        screen.blit(info_surf, (box_rect.x + 8, box_rect.y + box_rect.height + 8))
        pygame.display.flip()
        clock.tick(FPS)
    return name.strip() or "Player"

#-------SPRITES------#
if sprite_list and change_documents == True:
    current_sprite = random.choice(sprite_list)
    current_prompt = current_sprite.label
    #change_documents == False
else:
    current_sprite = info_sprite
    current_prompt = current_sprite.label
    #change_documents == False

#------START------#
found = False
game_state = 'menu'
running = True
while running:
    events = pygame.event.get()
    mouse_x, mouse_y = pygame.mouse.get_pos()
    # MENU STATE
    if game_state == 'menu':
        screen.blit(background_image2, (0, 0))
        screen.blit(background_image, (0, 0))
        start_rect, quit_rect, music_rect = draw_menu(screen)
        # don't reload/play all tracks every frame; playback is handled by MUSIC_END

        for event in events:
            # handle playlist end event so we can advance to the next track
            if event.type == MUSIC_END:
                current_track_index = (current_track_index + 1) % len(Tracks)
                try:
                    pygame.mixer.music.load(Tracks[current_track_index])
                    pygame.mixer.music.play()
                except Exception as e:
                    print("Music load/play error:", e)
            elif event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if start_rect.collidepoint(event.pos):
                    game_state = 'tutorial'
                elif quit_rect.collidepoint(event.pos):
                    running = False
                # toggle music pause/unpause instead of reloading/playing all tracks
                elif music_rect.collidepoint(event.pos):
                    if music:
                        pygame.mixer.music.pause()
                        music = False
                    else:
                        pygame.mixer.music.unpause()
                        music = True
        pygame.display.flip()
        clock.tick(FPS)
        continue
    # TUTORIAL STATE
    if game_state == 'tutorial':
        if info_display_active:
            prev_rect, next_rect, close_rect = display_info_file(screen, current_info_index)
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if prev_rect.collidepoint(event.pos):
                        current_info_index = max(1, current_info_index - 1)  # Decrease index but not below 1
                    elif next_rect.collidepoint(event.pos):
                        # Check if the next file exists before incrementing
                        if current_info_index < 5:
                         next_info_path = f"Images/info{current_info_index + 1}.png"
                         pygame.image.load(next_info_path)
                         current_info_index += 1
                        elif current_info_index >= 5:
                         close_rect.collidepoint(event.pos)
                         info_display_active = False  # Close the info file display
                        #pass  # Do nothing if the file doesn't exist
                    elif close_rect.collidepoint(event.pos):
                        info_display_active = False  # Close the info file display
        else:
            back_rect, begin_rect, info_rect = draw_tutorial(screen)
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if back_rect.collidepoint(event.pos):
                        game_state = 'menu'
                    elif begin_rect.collidepoint(event.pos):
                        # ask for player's name using non-blocking pygame dialog, store in DB, then start playing
                        player_name_local = ask_name("Enter your name:")
                        player_name = player_name_local
                        try:
                            cursor.execute('INSERT INTO high_scores (name, score) VALUES (?, ?)', (player_name, 0))
                            conn.commit()
                        except Exception as e:
                            print("DB insert error:", e)
                        game_state = 'playing'
                    elif info_rect.collidepoint(event.pos):
                        info_display_active = True  # Activate the info file display
        pygame.display.flip()
        clock.tick(FPS)
        continue
#-------PLAYING-------#
    if game_state == 'playing':
        pass_rect, deny_rect = draw_game_mechanics(screen)
        for event in events:
            if event.type == MUSIC_END:
                current_track_index = (current_track_index + 1) % len(Tracks)
                try:
                    pygame.mixer.music.load(Tracks[current_track_index])
                    pygame.mixer.music.play()
                except Exception as e:
                    print("Music load/play error:", e)
            elif event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # handle Pass click: check first NPC against ACCEPT_RULES; count fail if not matching
                if pass_rect.collidepoint(event.pos):
                    if NPCs:
                        current_npc = NPCs.sprites()[0]
                        name = current_npc.label
                        acceptable = ACCEPT_RULES.get(name.strip(), set())
                        # success if current_prompt in acceptable
                        if current_prompt in acceptable:
                            # success: reward and count processed
                            current_npc.kill()
                            score += 3
                            immigrants_processed += 1
                        else:
                            # fail: penalize and count wrong
                            current_npc.kill()
                            immigrants_wrong += 1
                            score -= 10
                        # spawn replacement and update prompt/sprite
                        img, pos, small, large, label = random.choice(NPCs_info)
                        new_n = InfoSprite(img, spawn_x, NPC_y, small, large, label, vx=NPC_move, vy=0)
                        NPCs.add(new_n)
                        npc_restricted = True
                        change_documents = True
                        if sprite_list:
                            current_sprite = random.choice(sprite_list)
                            current_prompt = current_sprite.label
                    else:
                        # no NPC present: do nothing (or you could count as fail)
                        pass

                # Deny button: remove one NPC and spawn replacement (no reward)
                elif deny_rect.collidepoint(event.pos):
                    npc_restricted = True
                    score -= 1
                    if NPCs:
                        victim = NPCs.sprites()[0]
                        victim.kill()
                        img, pos, small, large, label = random.choice(NPCs_info)
                        new_n = InfoSprite(img, spawn_x, NPC_y, small, large, label, vx=NPC_move, vy=0)
                        NPCs.add(new_n)
                        change_documents = True
                        if sprite_list:
                            current_sprite = random.choice(sprite_list)
                            current_prompt = current_sprite.label
                    # visual feedback
                    if player_radius > 6:
                        pygame.draw.rect(screen, (100, 50, 50), deny_rect.inflate(40, 20))
                    pygame.draw.circle(screen, player_color, (mouse_x, mouse_y), int(player_radius))

        pygame.display.flip()

     # update mouse-following player
        player_rect.center = (mouse_x, mouse_y)
        if mouse_x > SCREEN_WIDTH - 20:
            mouse_x = SCREEN_WIDTH - 20
            pygame.mouse.set_pos(mouse_x,mouse_y)
        if mouse_y > SCREEN_HEIGHT - 20:
            mouse_y = SCREEN_HEIGHT - 20
            pygame.mouse.set_pos(mouse_x,mouse_y)
        if mouse_x < 20:
            mouse_x = 20
            pygame.mouse.set_pos(mouse_x,mouse_y)
        if mouse_y < 20:
            mouse_y = 20
            pygame.mouse.set_pos(mouse_x,mouse_y)
    # handle player radius growth using mouse button state
    if pygame.mouse.get_pressed()[0] and player_radius <= 10.5:
        player_radius = player_radius * player_grow * 1.1

    elif player_radius > 5:
        player_radius = player_radius / (player_grow * 1.1)
    else:
        player_radius = 5

    # draw scene
    screen.blit(background_image, (0, 0))
    screen.blit(background_image2, (225, 25))
    if NPCs:
        remaining_time = min(npc.timer for npc in NPCs)  # Get the lowest remaining time among NPCs
    else:
        remaining_time = 0  # Default to 0 if no NPCs are present

    draw_ui(screen, current_prompt, score, remaining_time)

    # update and draw NPCs, show label when hovered

    if player_radius >= 4:
        label_font = pygame.font.SysFont('VT323', 20)
        for npc in NPCs:
            if npc.rect.collidepoint((mouse_x, mouse_y)):
                text_surface = label_font.render(npc.label, True, White)
                text_rect = text_surface.get_rect(midtop=(npc.rect.centerx - 10, npc.rect.bottom + 25))
                screen.blit(text_surface, text_rect)
    NPCs.update(player_radius, (mouse_x, mouse_y))
    NPCs.draw(screen)
        # handle NPCs that passed or expired
    passed_spawns = 0
    expired_spawns = 0
    for npc in list(NPCs):
        if npc.rect.right >= SCREEN_WIDTH - 200:
                passed_spawns += 1
                immigrants_processed = immigrants_processed + 1
                npc.kill()  # remove passed NPC
        elif npc.timer < 0:
                expired_spawns += 1
                npc.kill()  # remove expired NPC and penalize below
                immigrants_wrong = immigrants_wrong + 1

        money_subtracted = False

        # spawn replacements for passed NPCs (reward)
        for _ in range(passed_spawns):
            NPC_move = 5
            img, pos, small, large, label = random.choice(NPCs_info)
            spawn_x = 225
            new_npc = InfoSprite(img, spawn_x, NPC_y, small, large, label, vx=NPC_move, vy=0)
            NPCs.add(new_npc)
            npc_restricted = True
            change_documents = True
            score += 3
            money_subtracted = False
            immigrants_processed = immigrants_processed + 1
            if sprite_list:
                current_sprite = random.choice(sprite_list)
                current_prompt = current_sprite.label
    

        # spawn replacements for expired NPCs (penalty)
        for _ in range(expired_spawns):
            NPC_move = 5
            img, pos, small, large, label = random.choice(NPCs_info)
            spawn_x = 225
            new_npc = InfoSprite(img, spawn_x, NPC_y, small, large, label, vx=NPC_move, vy=0)
            NPCs.add(new_npc)
            npc_restricted = True
            change_documents = True
            if sprite_list:
                current_sprite = random.choice(sprite_list)
                current_prompt = current_sprite.label
            immigrants_wrong = immigrants_wrong + 1
            score -= 10

    if current_sprite:
        sprites.update(player_radius, (mouse_x, mouse_y))
        screen.blit(current_sprite.image, current_sprite.rect)
        if player_radius >= 4 and current_sprite.rect.collidepoint((mouse_x, mouse_y)):
            label_font = pygame.font.SysFont('VT323', 20)
            text_surface = label_font.render(current_sprite.label, True, White)
            text_rect = text_surface.get_rect(midtop=(current_sprite.rect.centerx - 10, current_sprite.rect.bottom + 75))
            screen.blit(text_surface, text_rect)

    if score < 11:
        # Flash a short red warning for 1.5 seconds once, then resume gameplay
        if not low_balance_flash_done:
            flash_duration = 1500  # total milliseconds to flash (1.5s)
            flash_interval = 300   # toggle color every 300 ms
            start_time = pygame.time.get_ticks()
            term_font = pygame.font.SysFont('VT323', 32)
            term_msg = "Balance low."
            while pygame.time.get_ticks() - start_time < flash_duration:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        try:
                            conn.close()
                        except:
                            pass
                        pygame.quit()
                        sys.exit()
                elapsed = pygame.time.get_ticks() - start_time
                color = (255, 0, 0) if ((elapsed // flash_interval) % 2 == 0) else White

                # draw background and flashing text
                screen.blit(background_image, (0, 0))
                screen.blit(background_image2, (225, 25))
                text_surf = term_font.render(term_msg, True, color)
                text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
                pad = 20
                bg_rect = pygame.Rect(text_rect.x - pad, text_rect.y - pad, text_rect.width + pad*2, text_rect.height + pad*2)
                pygame.draw.rect(screen, (20, 20, 20), bg_rect)
                screen.blit(text_surf, text_rect)
                pygame.display.flip()
                clock.tick(FPS)
            low_balance_flash_done = True
        # otherwise do nothing (game continues)

    else:
        # reset flag if player recovers above threshold
        low_balance_flash_done = False

    if score < 0:
        # save final result then exit cleanly
        try:
            final_name = player_name or "Player"
            cursor.execute('INSERT INTO high_scores (name, score) VALUES (?, ?)', (final_name,immigrants_processed))
            conn.commit()
        except Exception as e:
            print("DB final insert error:", e)
        flash_duration = 3500  # total milliseconds to flash
        flash_interval = 450   # interval in ms between color toggles
        start_time = pygame.time.get_ticks()
        term_font = pygame.font.SysFont('VT323', 32)
        term_msg = f"Your service has been terminated for outstanding debts. Processed: {immigrants_processed}, wrong: {immigrants_wrong}."
        # minimal responsive flashing loop
        while pygame.time.get_ticks() - start_time < flash_duration:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    try:
                        conn.close()
                    except:
                        pass
                    pygame.quit()
                    sys.exit()
            elapsed = pygame.time.get_ticks() - start_time
            color = (255, 0, 0) if ((elapsed // flash_interval) % 2 == 0) else White

            # draw basic scene background and flashing text
            screen.blit(background_image, (0, 0))
            screen.blit(background_image2, (225, 25))
            text_surf = term_font.render(term_msg, True, color)
            text_rect = text_surf.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
            # draw a simple dark box behind text for readability
            pad = 20
            bg_rect = pygame.Rect(text_rect.x - pad, text_rect.y - pad, text_rect.width + pad*2, text_rect.height + pad*2)
            pygame.draw.rect(screen, (20, 20, 20), bg_rect)
            screen.blit(text_surf, text_rect)

            pygame.display.flip()
            clock.tick(FPS)

        # save to DB and exit
        try:
            final_name = player_name or "Player"
            cursor.execute('INSERT INTO high_scores (name, score) VALUES (?, ?)', (final_name,immigrants_processed))
            conn.commit()
        except Exception as e:
            print("DB final insert error:", e)
        try:
            conn.close()
        except:
            pass
        pygame.quit()
        sys.exit()

    keys = pygame.key.get_pressed()
    all_sprites.draw(screen)
    #pygame.display.flip()
    pygame.draw.circle(screen, player_color, (mouse_x, mouse_y), int(player_radius))
    clock.tick(FPS)

pygame.quit()
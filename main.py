"""
main.py – Hand Cricket (pygame front-end)

Controls
--------
SPACE   Show gesture prompt (camera or keyboard 1-6) and play a ball.
R       Restart after game over.
ESC     Quit.

FIXES:
  - Asset path now checks both "assets/" subfolder and current directory.
  - Score HUD shows live score correctly.
  - "RUN" banner shows how many runs were scored each ball.
  - Handles new "WIN" status from game.py.
  - save_result guards against duplicate saves.
"""

import sys
import os
import random
import pygame

from db import create_tables, cursor, conn
from auth import login, register
from game import HandCricket
from gesture import get_number, cleanup as gesture_cleanup

# ── Database ─────────────────────────────────────────────────────────────────
create_tables()

# ── Auth (console) ───────────────────────────────────────────────────────────
print("=== Hand Cricket ===")
print("1. Login\n2. Sign up")
choice = input("Choice: ").strip()

username = input("Username: ").strip()
password = input("Password: ").strip()

if choice == "2":
    if not register(username, password):
        print("Username already taken. Please restart and log in.")
        sys.exit(1)
    print("Account created!")

if not login(username, password):
    print("Login failed. Wrong username or password.")
    sys.exit(1)

print(f"Welcome, {username}!")

# ── Pygame setup ─────────────────────────────────────────────────────────────
pygame.init()
screen = pygame.display.set_mode((800, 600))
pygame.display.set_caption("Hand Cricket")
clock    = pygame.time.Clock()
font_lg  = pygame.font.SysFont(None, 60)
font_md  = pygame.font.SysFont(None, 40)
font_sm  = pygame.font.SysFont(None, 30)
font_hud = pygame.font.SysFont(None, 46)


# ── Asset loading ─────────────────────────────────────────────────────────────
def _find_asset(name: str) -> str:
    """Try assets/ subfolder first, then current directory."""
    for candidate in [os.path.join("assets", name), name,
                      os.path.join(os.path.dirname(__file__), "assets", name),
                      os.path.join(os.path.dirname(__file__), name)]:
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError(f"Asset not found: {name}")


def load_image(name: str, size=None) -> pygame.Surface:
    path = _find_asset(name)
    img  = pygame.image.load(path).convert_alpha()
    if size:
        img = pygame.transform.scale(img, size)
    return img


bg        = load_image("bg.png",    (800, 600))
cloud     = load_image("cloud.png")
hand_imgs = {i: load_image(f"hand{i}.png", (200, 200)) for i in range(1, 7)}

# ── Scene state ──────────────────────────────────────────────────────────────
bg_x      = 0
cloud_x   = 0
particles = [[random.randint(0, 800), random.randint(0, 600)] for _ in range(50)]

game         = HandCricket()
player_n     = None
computer_n   = None
last_runs    = None   # runs scored on the last ball
result_saved = False

# ── Banner system ─────────────────────────────────────────────────────────────
BANNER_DURATION = 90   # frames (~1.5 s at 60 fps)
banner_text  = ""
banner_timer = 0
banner_color = (255, 255, 255)


def show_banner(text: str, color=(255, 255, 100)):
    global banner_text, banner_timer, banner_color
    banner_text  = text
    banner_timer = BANNER_DURATION
    banner_color = color


def draw_banner():
    global banner_timer
    if banner_timer <= 0:
        return
    banner_timer -= 1

    if banner_timer > BANNER_DURATION - 20:
        alpha = int(255 * (BANNER_DURATION - banner_timer) / 20)
    elif banner_timer < 40:
        alpha = int(255 * banner_timer / 40)
    else:
        alpha = 255

    font_banner = pygame.font.SysFont(None, 90)
    text_surf   = font_banner.render(banner_text, True, banner_color)

    pad_x, pad_y = 30, 16
    tw, th = text_surf.get_size()
    pill = pygame.Surface((tw + pad_x*2, th + pad_y*2), pygame.SRCALPHA)
    pygame.draw.rect(pill, (0, 0, 0, 180), pill.get_rect(), border_radius=18)
    pill.set_alpha(alpha)
    text_surf.set_alpha(alpha)

    px = screen.get_width()  // 2 - pill.get_width()  // 2
    py = screen.get_height() // 2 - pill.get_height() // 2 - 40
    screen.blit(pill, (px, py))
    screen.blit(text_surf, (px + pad_x, py + pad_y))


# ── Helpers ──────────────────────────────────────────────────────────────────
def save_result(score: int, result_str: str):
    cursor.execute(
        "INSERT INTO history VALUES (NULL, ?, ?, ?)",
        (username, score, result_str),
    )
    conn.commit()


def draw_background():
    global bg_x, cloud_x
    bg_x -= 1
    if bg_x <= -800:
        bg_x = 0
    screen.blit(bg, (bg_x, 0))
    screen.blit(bg, (bg_x + 800, 0))

    cloud_x += 2
    if cloud_x > 900:
        cloud_x = -cloud.get_width()
    screen.blit(cloud, (cloud_x, 80))

    for p in particles:
        p[1] += 1
        if p[1] > 600:
            p[1] = 0
        pygame.draw.circle(screen, (255, 255, 255), (int(p[0]), int(p[1])), 2)


def animate_computer(final_num: int):
    """Slot-machine spin before revealing computer's number."""
    for _ in range(10):
        rand = random.randint(1, 6)
        draw_background()
        screen.blit(hand_imgs[rand], (460, 180))
        lbl = font_sm.render("Computer", True, (255, 255, 0))
        screen.blit(lbl, (475, 155))
        pygame.display.update()
        pygame.time.delay(70)

    # Show real result
    draw_background()
    screen.blit(hand_imgs[final_num], (460, 180))
    pygame.display.update()


def draw_hud():
    # Score box (top-left)
    pygame.draw.rect(screen, (30, 20, 10), (20, 20, 180, 70), border_radius=10)
    pygame.draw.rect(screen, (180, 120, 40), (20, 20, 180, 70), width=2, border_radius=10)
    score_lbl  = font_sm.render("SCORE", True, (200, 160, 80))
    score_val  = font_hud.render(str(game.score).zfill(3), True, (255, 220, 80))
    screen.blit(score_lbl, (30, 28))
    screen.blit(score_val, (30, 52))

    # Player hand (left)
    if player_n:
        screen.blit(hand_imgs[player_n], (100, 180))
        lbl = font_sm.render("You", True, (100, 220, 255))
        screen.blit(lbl, (170, 155))

    # Computer hand (right)
    if computer_n:
        screen.blit(hand_imgs[computer_n], (460, 180))
        lbl = font_sm.render("Computer", True, (255, 220, 100))
        screen.blit(lbl, (475, 155))

    # Last ball runs
    if last_runs is not None and not game.game_over:
        runs_surf = font_md.render(f"+{last_runs} runs", True, (100, 255, 150))
        screen.blit(runs_surf, (screen.get_width()//2 - runs_surf.get_width()//2, 420))

    # Game over overlay
    if game.game_over:
        if game.result == "WIN":
            over_surf = font_lg.render("YOU WIN! 🏆", True, (80, 255, 80))
        else:
            over_surf = font_lg.render("GAME OVER", True, (255, 50, 50))

        screen.blit(over_surf, (
            screen.get_width()//2 - over_surf.get_width()//2, 280))

        final_surf = font_md.render(
            f"Final score: {game.score}  |  Press R to restart", True, (255, 255, 255))
        screen.blit(final_surf, (
            screen.get_width()//2 - final_surf.get_width()//2, 355))

    # Bottom hint
    hint = font_sm.render("SPACE = play  |  R = restart  |  ESC = quit", True, (200, 200, 200))
    screen.blit(hint, (screen.get_width()//2 - hint.get_width()//2, 573))


# ── Main loop ────────────────────────────────────────────────────────────────
running = True
show_banner("GAME START 🏏", color=(80, 255, 120))

while running:
    draw_background()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:

            if event.key == pygame.K_ESCAPE:
                running = False

            elif event.key == pygame.K_r and game.game_over:
                game         = HandCricket()
                player_n     = None
                computer_n   = None
                last_runs    = None
                result_saved = False
                show_banner("GAME RESTART 🔄", color=(80, 200, 255))

            elif event.key == pygame.K_SPACE and not game.game_over:
                try:
                    player_n = get_number()
                except SystemExit:
                    running = False
                    break

                status, computer_n = game.play(player_n)
                animate_computer(computer_n)

                if status == "OUT":
                    last_runs = None
                    if not result_saved:
                        save_result(game.score, "LOSS")
                        result_saved = True
                    show_banner(f"OUT!  Score: {game.score}", color=(255, 80, 80))

                elif status == "WIN":
                    last_runs = None
                    if not result_saved:
                        save_result(game.score, "WIN")
                        result_saved = True
                    show_banner("YOU WIN! 🏆", color=(80, 255, 80))

                else:  # "RUN"
                    last_runs = player_n
                    if player_n == 6:
                        show_banner("SIX! 🏏", color=(255, 200, 0))
                    elif player_n == 4:
                        show_banner("FOUR! 🏏", color=(255, 160, 0))
                    else:
                        show_banner(f"+{player_n}", color=(200, 255, 200))

    draw_hud()
    draw_banner()
    pygame.display.update()
    clock.tick(60)

gesture_cleanup()
pygame.quit()
sys.exit()

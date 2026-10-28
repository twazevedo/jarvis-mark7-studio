"""Tarefa: Jogo da Cobrinha Stark Edition (Inspirado no Vídeo 7 — snake_game.py)."""
from pathlib import Path
import subprocess
import sys

description = "Abre e inicia o clássico Jogo da Cobrinha (Snake Game) em uma janela interativa Pygame."
trigger = "Quando o usuário pedir para jogar o jogo da cobrinha ou abrir o snake game."
example = "{'type': 'snake_game', 'content': 'Jogar o jogo da cobrinha'}"


def jogar():
    import pygame
    import random

    pygame.init()
    cyan = (0, 240, 255)
    dark = (3, 12, 22)
    gold = (255, 170, 0)
    green = (0, 255, 157)
    red = (255, 59, 92)

    width, height = 640, 440
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("J.A.R.V.I.S. — Snake Game (Stark Edition)")
    clock = pygame.time.Clock()

    snake_block = 16
    snake_speed = 13
    font_style = pygame.font.SysFont("segoeui", 22, bold=True)
    score_font = pygame.font.SysFont("consolas", 24, bold=True)

    def show_score(score):
        val = score_font.render(f"STARK SCORE: {score}", True, cyan)
        screen.blit(val, [12, 10])

    def draw_snake(block, snake_list):
        for i, x in enumerate(snake_list):
            color = cyan if i == len(snake_list) - 1 else green
            pygame.draw.rect(screen, color, [x[0], x[1], block - 1, block - 1], border_radius=4)

    def game_loop():
        game_over = False
        game_close = False
        x1 = (width // 2 // snake_block) * snake_block
        y1 = (height // 2 // snake_block) * snake_block
        x1_change, y1_change = 0, 0
        snake_list = []
        length = 1

        foodx = random.randrange(1, (width - snake_block) // snake_block) * snake_block
        foody = random.randrange(3, (height - snake_block) // snake_block) * snake_block

        while not game_over:
            while game_close:
                screen.fill(dark)
                msg = font_style.render("Fim de Jogo! Pressione [C] Jogar de Novo ou [Q] Sair", True, red)
                screen.blit(msg, [width // 2 - msg.get_width() // 2, height // 2 - 20])
                show_score(length - 1)
                pygame.display.update()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        game_over = True
                        game_close = False
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_q:
                            game_over = True
                            game_close = False
                        if event.key == pygame.K_c:
                            return game_loop()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game_over = True
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a) and x1_change == 0:
                        x1_change = -snake_block
                        y1_change = 0
                    elif event.key in (pygame.K_RIGHT, pygame.K_d) and x1_change == 0:
                        x1_change = snake_block
                        y1_change = 0
                    elif event.key in (pygame.K_UP, pygame.K_w) and y1_change == 0:
                        y1_change = -snake_block
                        x1_change = 0
                    elif event.key in (pygame.K_DOWN, pygame.K_s) and y1_change == 0:
                        y1_change = snake_block
                        x1_change = 0

            if x1 >= width or x1 < 0 or y1 >= height or y1 < 0:
                game_close = True

            x1 += x1_change
            y1 += y1_change
            screen.fill(dark)
            pygame.draw.rect(screen, gold, [foodx, foody, snake_block - 1, snake_block - 1], border_radius=4)
            head = [x1, y1]
            snake_list.append(head)
            if len(snake_list) > length:
                del snake_list[0]

            for seg in snake_list[:-1]:
                if seg == head and (x1_change != 0 or y1_change != 0):
                    game_close = True

            draw_snake(snake_block, snake_list)
            show_score(length - 1)
            pygame.display.update()

            if x1 == foodx and y1 == foody:
                foodx = random.randrange(1, (width - snake_block) // snake_block) * snake_block
                foody = random.randrange(3, (height - snake_block) // snake_block) * snake_block
                length += 1

            clock.tick(snake_speed)

        pygame.quit()

    game_loop()


def execute(content: str = "") -> str:
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--run"])
    return "🐍 **Jogo da Cobrinha (Stark Edition)** iniciado em uma nova janela, senhor! Use as setas do teclado ou WASD para jogar."


if __name__ == "__main__":
    if "--run" in sys.argv:
        jogar()


from typing import Dict, Any

import pygame

from gale.input_handler import InputData
from gale.state import BaseState
from gale.text import render_text
from gale.timer import Timer

import settings
from src.Camera import Camera
from src.GameLevel import GameLevel
from src.Player import Player
from src.Boss import Boss
from src.states import game_states

class PlayState(BaseState):
    # X position where the boss arena begins; the gate rendered here blocks
    # the player until the mid-level key has been picked up.
    BOSS_GATE_X = 1024
    BOSS_GATE_Y = 288

    def enter(self, **enter_params: Dict[str, Any]) -> None:
        self.level = enter_params.get("level", 1)
        self.game_level = enter_params.get("game_level")
        self.lives = enter_params.get("lives",3)

        if self.game_level is None:
            self.game_level = GameLevel(self.level)
            pygame.mixer.music.load(
                settings.BASE_DIR / "assets" / "sounds" / "musicWorld.ogg"
            )
            pygame.mixer.music.play(loops=-1)

        self.tilemap = self.game_level.tilemap

        self.player = enter_params.get("player")
        if self.player is None:
            self.player = Player(0, 400 - 60, self.game_level)
            self.player.change_state("idle")

        self.camera = enter_params.get("camera")
        if self.camera is None:
            self.camera = Camera(0, 192, settings.VIRTUAL_WIDTH, settings.VIRTUAL_HEIGHT)
            self.camera.set_collision_boundaries(self.game_level.get_rect())
            self.camera.attach_to(self.player)

        self.boss = None
        if self.level == 2:
            self.boss = enter_params.get("boss")
            if self.boss is None:
                self.boss = Boss(1232,  400 - 110, self.game_level, "dead_Walk")
                self.boss.change_state("idle")

        self.band = enter_params.get("band",True)

        Timer.resume()

    def update(self, dt: float) -> None:

        if self.player.is_dead:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            Timer.clear()
            self.state_machine.pop()
            self.state_machine.push(game_states.GameOverState(self.state_machine), self.level)
    
        self.player.update(dt)

        if self.player.y >= self.player.tilemap.height:
            self.player.is_dead = True
            return
        
        self.camera.update()
        self.game_level.set_render_boundaries(self.camera.get_rect())
        self.game_level.update(dt)

        if self.level == 2 and not self.player.pickup_key:
            if self.player.x + self.player.width > self.BOSS_GATE_X and self.player.y > 250:
                self.player.x = self.BOSS_GATE_X - self.player.width
                if self.player.vx > 0:
                    self.player.vx = 0

        for creature in self.game_level.creatures:
            if self.player.texture_id == "Knight_Attack" or self.player.texture_id == "Knight_Attack2" :
                if self.player.collides(creature) and creature.flipped == self.player.flipped:
                    if not self.player.wounded:
                        settings.SOUNDS["wounded"].play()
                        self.lives-=1    
                        self.player.wounded = True
                        Timer.after(3,self.player.recovery)

                if creature.collides2(self.player.attack_zone(self.player.flipped)):
                    self.game_level.creatures.remove(creature)
                    settings.SOUNDS["dead"].play()
            elif self.player.collides(creature):
                if not self.player.wounded:
                    settings.SOUNDS["wounded"].play()
                    self.lives-=1    
                    self.player.wounded = True
                    Timer.after(3,self.player.recovery)
        
        if self.lives == 0: 
            self.player.change_state("dead")            

        for item in self.game_level.items:
            if not item.active or not item.collidable:
                continue

            if self.player.collides(item):
                item.on_consume(self.player)
                if self.player.pickup_key:
                    item.on_collide(self.player)

        if self.player.key_puzzle_pending:
            self.player.key_puzzle_pending = False
            self.state_machine.push(
                game_states.WheresTheKeyState(self.state_machine), player=self.player
            )
            return

        for trap in self.game_level.traps:
            if self.player.collides(trap):
                
                if self.lives == 0: 
                    self.player.change_state("dead")

                elif not self.player.wounded:
                    settings.SOUNDS["wounded"].play()
                    self.lives-=1    
                    self.player.wounded = True
                    Timer.after(3,self.player.recovery)

        if self.player.open_door:
            Timer.after(1, self.next_level)

        if (
            (self.player.x > self.BOSS_GATE_X)
            and (self.player.y > 320)
            and (self.band == True)
            and (self.level == 2)
            and self.player.pickup_key
        ):
            self.band = False
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()

            pygame.mixer.music.load(
                settings.BASE_DIR / "assets" / "sounds" / "Boss_Battle.wav"
            )
            pygame.mixer.music.play(loops=-1)
            self.boss.start_battle()

        if self.level == 2 and self.boss is not None:
            self.boss.update(dt, self.player)

            player_attacking = self.player.texture_id in ("Knight_Attack", "Knight_Attack2")

            if player_attacking and self.boss.texture_id == "dead_Walk":

                if self.boss.collides2(self.player.attack_zone(self.player.flipped)):
                    if not self.boss.wounded:
                            settings.SOUNDS["dead"].play()
                            self.boss.take_damage()
                            self.boss.wounded = True
                            Timer.after(1,self.boss.recovery)

                    if self.boss.vx !=0:
                        if not self.player.wounded:
                            settings.SOUNDS["wounded"].play()
                            self.lives -= 1
                            self.player.wounded = True
                            Timer.after(3,self.player.recovery)

            elif not player_attacking:
                    if self.boss.collides(self.player):
                        if self.boss.vx !=0:
                            if not self.player.wounded:
                                settings.SOUNDS["wounded"].play()
                                self.lives -= 1
                                self.player.wounded = True
                                Timer.after(3,self.player.recovery)

            if self.boss.is_defeated():
                    Timer.clear()
                    Timer.after(5, self.__pop)
                    self.boss = None

        if self.lives == 0:
                self.player.change_state("dead")

    def __pop(self)-> None:
        self.state_machine.pop()
        self.state_machine.push(game_states.GameOverState(self.state_machine),self.level)
        self.state_machine.push(game_states.ScenaState(self.state_machine),"End")
            
    def render(self, surface: pygame.Surface) -> None:

        world_surface = pygame.Surface((self.tilemap.width, self.tilemap.height))
        self.game_level.render(world_surface)
        self.player.render(world_surface)

        if self.level == 2:
            if not self.player.pickup_key:
                world_surface.blit(
                    settings.TEXTURES["boss_gate"],
                    (self.BOSS_GATE_X, self.BOSS_GATE_Y),
                    settings.FRAMES["boss_gate"][0],
                )

            if self.boss is not None:
                self.boss.render(world_surface)
                i = 0
                live_boss_x = 1120
                while i < self.boss.lives:
                    world_surface.blit(
                        settings.TEXTURES["live_boss"], (live_boss_x, 224), settings.FRAMES["live_boss"][5]
                    )
                    live_boss_x += 16
                    i += 1

        surface.blit(world_surface, (-self.camera.x, -self.camera.y))

        heart_x = settings.VIRTUAL_WIDTH - 11
        i = 0
        while i < self.lives:
            surface.blit(
                settings.TEXTURES["hearts"], (heart_x, 5), settings.FRAMES["hearts"][0]
            )
            heart_x -= 11
            i += 1


    def next_level(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
        Timer.clear()
        self.state_machine.pop()
        self.state_machine.push(game_states.WinerLevelState(self.state_machine), level = self.level + 1)

    def on_input(self, input_id: str, input_data: InputData) -> None:
        if input_id == "pause" and input_data.pressed:
            Timer.pause()
            self.state_machine.push(game_states.PauseState(self.state_machine))
        else:
            self.player.on_input(input_id, input_data)
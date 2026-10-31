import random


class HandCricket:
    def __init__(self):
        self.score = 0
        self.game_over = False
        self.result = None   # "WIN" | "LOSS" | None

    def play(self, player: int):
        """
        player  – integer 1-6 chosen by the human
        Returns (status, computer_number)
            status: "RUN"  – still batting, score updated
                    "OUT"  – player is out (matched computer's number)
        """
        if self.game_over:
            raise RuntimeError("Game is already over. Create a new HandCricket instance.")

        if not (1 <= player <= 6):
            raise ValueError(f"player must be 1-6, got {player}")

        computer = random.randint(1, 6)

        if player == computer:
            self.game_over = True
            self.result = "LOSS"
            return "OUT", computer

        self.score += player

        # Optional win condition: score 100 or more
        if self.score >= 100:
            self.game_over = True
            self.result = "WIN"
            return "WIN", computer

        return "RUN", computer

    def reset(self):
        self.__init__()

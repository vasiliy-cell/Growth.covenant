import matplotlib.pyplot as plt
import numpy as np

# Colors for the population. Beyond its size agents start sharing colors -
# with dozens of bodies on screen that is unavoidable and harmless.
AGENT_PALETTE = plt.get_cmap("tab20")


class Renderer:
    def __init__(self):
        plt.ion()

        self.fig, self.ax = plt.subplots()

        bg = [0.051, 0.067, 0.090]
        self.fig.patch.set_facecolor(bg)
        self.ax.set_facecolor(bg)

        self.colors = {
            0: [0.051, 0.067, 0.090],  # empty
            1: [0.165, 0.835, 0.345],  # reward
            2: [0.831, 0.169, 0.247],  # danger
        }

        self.alive = True

    @staticmethod
    def agent_color(index):
        """
        A stable color for the whole life of an agent: its index is never
        reused, so a color never jumps to somebody else when an agent is
        born or dies. Taking the color from the drawing order instead would
        reshuffle the whole picture on every death.
        """
        return AGENT_PALETTE(index % AGENT_PALETTE.N)

    def render(self, grid, agent_positions):
        """agent_positions: {agent index: (x, y)} - the whole population."""
        if not self.alive:
            return

        grid = np.array(grid)

        size = grid.shape[0]
        image = np.zeros((size, size, 3))

        for y in range(size):
            for x in range(size):
                image[y, x] = self.colors.get(int(grid[y, x]), [0, 0, 0])

        self.ax.clear()
        self.ax.imshow(image)

        if agent_positions:
            self.ax.scatter(
                [position[0] for position in agent_positions.values()],
                [position[1] for position in agent_positions.values()],
                c=[self.agent_color(index) for index in agent_positions],
                s=120,
            )

        self.ax.set_xticks(np.arange(-0.5, size, 1))
        self.ax.set_yticks(np.arange(-0.5, size, 1))
        self.ax.grid(color="#30363d", linewidth=0.5)

        self.ax.set_xticklabels([])
        self.ax.set_yticklabels([])

        self.ax.set_aspect("equal")

        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        plt.pause(0.03)

    def close(self):
        self.alive = False
        plt.ioff()
        plt.close(self.fig)
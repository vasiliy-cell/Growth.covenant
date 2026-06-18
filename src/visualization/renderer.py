import matplotlib.pyplot as plt
import numpy as np


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

    def render(self, grid, agent_pos):
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

        ax_x, ax_y = agent_pos
        self.ax.scatter(ax_x, ax_y, c="#692ad5", s=120)

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
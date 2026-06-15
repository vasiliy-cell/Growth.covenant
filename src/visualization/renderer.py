import matplotlib.pyplot as plt
import numpy as np


class Renderer:
    def __init__(self):
        plt.ion()  # интерактивный режим
        self.fig, self.ax = plt.subplots()
        
        
        # ставим фон
        bg = [0.051, 0.067, 0.090]
        self.fig.patch.set_facecolor(bg)
        self.ax.set_facecolor(bg)



        self.colors = {
            0: [0.051, 0.067, 0.090],  # empty
            1: [0.165, 0.835, 0.345],  # reward (#2ad558)
            2: [0.831, 0.169, 0.247],  # danger (#d42b3f)
        }


    def render(self, grid, agent_pos):
        size = grid.shape[0]

        # создаём RGB картинку
        image = np.zeros((size, size, 3))

        for y in range(size):
            for x in range(size):
                image[y, x] = self.colors.get(grid[y, x], [0, 0, 0])

        # рисуем
        self.ax.clear()
        self.ax.imshow(image)

        # агент 
        ax_x, ax_y = agent_pos
        self.ax.scatter(ax_x, ax_y, c="#692ad5", s=100)

        # сетка
        self.ax.set_xticks(np.arange(-0.5, size, 1))
        self.ax.set_yticks(np.arange(-0.5, size, 1))
        self.ax.grid(color="#30363d", linestyle='-', linewidth=0.5)

        # убираем цифры
        self.ax.set_xticklabels([])
        self.ax.set_yticklabels([])

        plt.pause(0.2)  # скорость (можешь менять)

    def close(self):
        plt.ioff()
        plt.show()
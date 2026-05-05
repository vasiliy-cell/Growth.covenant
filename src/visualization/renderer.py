import matplotlib.pyplot as plt
import numpy as np


class Renderer:
    def __init__(self):
        plt.ion()  # интерактивный режим
        self.fig, self.ax = plt.subplots()
        
        
        # ставим фон
        bg = [0.212, 0.227, 0.310]
        self.fig.patch.set_facecolor(bg)
        self.ax.set_facecolor(bg)



        self.colors = {
            0: [0.212, 0.227, 0.310],  # empty
            1: [0.651, 0.855, 0.584],  # reward
            2: [0.929, 0.529, 0.588],  # danger
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
        self.ax.scatter(ax_x, ax_y, c="#F5C542", s=100)

        # сетка
        self.ax.set_xticks(np.arange(-0.5, size, 1))
        self.ax.set_yticks(np.arange(-0.5, size, 1))
        self.ax.grid(color="black", linestyle='-', linewidth=0.5)

        # убираем цифры
        self.ax.set_xticklabels([])
        self.ax.set_yticklabels([])

        plt.pause(0.2)  # скорость (можешь менять)

    def close(self):
        plt.ioff()
        plt.show()

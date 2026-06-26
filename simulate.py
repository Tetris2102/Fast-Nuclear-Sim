import tkinter as tk

colors = (
    "#FF0000", "#00FF00", "#0000FF",
    "#FFFF00", "#FF00FF", "#00FFFF",
    "#AA0000", "#00AA00", "#0000AA",
    "#AAAA00", "#AA00AA", "#00AAAA"
)
background_color = "#000000"
cell_side = 20
spacing = 20

def draw_reactor(canvas, cell_colors):
    for i in range(len(cell_colors)):
        for j in range(len(cell_colors[i])):
            x0 = spacing + j * cell_side
            y0 = spacing + i * cell_side
            index = 15 * i + j
            canvas.create_rectangle(x0, y0, x0 + 20, y0 + 20, fill=cell_colors[i][j])

root = tk.Tk()
root.title("Reactor")

canvas = tk.Canvas(root, width=340, height=340, bg="black")
# canvas.create_rectangle()

def background_row(num_blank, fill_color, background_color):
    row = []
    for i in range(num_blank):
        row.append(background_color)
    for i in range(15 - 2 * num_blank):
        row.append(fill_color)
    for i in range(num_blank):
        row.append(background_color)
    return row


def reactor_matrix(fill_color, background_color):
    reactor = []

    reactor.append(background_row(3, fill_color, background_color))
    reactor.append(background_row(2, fill_color, background_color))
    reactor.append(background_row(1, fill_color, background_color))

    colored_row = [fill_color, fill_color, fill_color,
                fill_color, fill_color, fill_color,
                fill_color, fill_color, fill_color,
                fill_color, fill_color, fill_color,
                fill_color, fill_color, fill_color]
    for i in range(9):
        reactor.append(colored_row)
    
    reactor.append(background_row(1, fill_color, background_color))
    reactor.append(background_row(2, fill_color, background_color))
    reactor.append(background_row(3, fill_color, background_color))

    return reactor

def rod_matrix(reactor_matrix, firstRodXY):
    rod_matrix = [firstRodXY]
    x = firstRodXY[0]
    x_init = 0
    if(x % 2 != 0):
        x_init = 1
    y = firstRodXY[1]

    while(y < 15):
        x_new = x + 2
        if(x_new < 15):
            x = x_new
            if(reactor_matrix[y][x] != background_color):
                rod_matrix.append((x, y));
        else:
            x = x_init
            y += 2
    
    return rod_matrix

reactor_matrix = reactor_matrix(colors[0], background_color)
rod_matrix = rod_matrix(reactor_matrix, (3, 1))

for i in rod_matrix:
    x = i[0]
    y = i[1]
    reactor_matrix[y][x] = colors[2]


draw_reactor(canvas, reactor_matrix)

canvas.pack()

root.mainloop()

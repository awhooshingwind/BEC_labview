# -*- coding: utf-8 -*-
"""
Created on Wed Feb 22 09:03:08 2023

@author: BEC
"""
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button

#Some parameters
x0 = 1; #Distance from slit to screen
k_laser = 2*np.pi / (660e-9) #Laser wavelength

# The parametrized function to be plotted
#b is single slit width, d is spacing between the double slits
def f(theta, b, d):
    return 4*(np.sin(b*k_laser*theta/2) / (k_laser*theta*b/2))**2 * np.cos(k_laser*d*theta/2)**2 

thetas = np.linspace(-np.radians(5), np.radians(5), 1000) #values for the plot

# Define initial parameters
init_b = 50 #in microns
init_d = 500 #in microns

# Create the figure and the line that we will manipulate
fig, ax = plt.subplots()
line, = ax.plot(x0*np.tan(thetas), f(thetas, init_b/1e6, init_d/1e6), lw=2)
ax.set_xlabel('Position on screen [m]')
ax.set_ylabel('Intensity / b**2')
ax.set_ylim([0,4])

# adjust the main plot to make room for the sliders
fig.subplots_adjust(bottom=0.4)


# Make a horizontal slider to control the frequency.
axb = fig.add_axes([0.25, 0.1, 0.65, 0.03])
b_slider = Slider(
    ax=axb,
    label='Slit width [$\mu$m]',
    valmin=0,
    valmax=1000,
    valinit=init_b,
)

# Make a horizontal slider to control the amplitude
axd = fig.add_axes([0.25, 0.2, 0.65, 0.03])
d_slider = Slider(
    ax=axd,
    label='Slit spacing [$\mu$m]',
    valmin=0,
    valmax=1000,
    valinit=init_d,
)


# The function to be called anytime a slider's value changes
def update(val):
    line.set_ydata(f(thetas, b_slider.val/1e6, d_slider.val/1e6))
    
    fig.canvas.draw_idle()


# register the update function with each slider
b_slider.on_changed(update)
d_slider.on_changed(update)

# Create a `matplotlib.widgets.Button` to reset the sliders to initial values.
resetax = fig.add_axes([0.8, 0.025, 0.1, 0.04])
button = Button(resetax, 'Reset', hovercolor='0.975')


def reset(event):
    b_slider.reset()
    d_slider.reset()
button.on_clicked(reset)

plt.show()
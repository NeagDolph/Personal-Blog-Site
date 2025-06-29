from PIL import Image, ImageFilter, ImageDraw
import numpy as np
import matplotlib.pyplot as plt

# Image size
width, height = 1024, 1024

# Define the colors
start_color = np.array([29, 68, 173], dtype=np.float32)  # #3a64d3
end_color = np.array([255, 255, 255], dtype=np.float32)   # white

# Create a gradient
gradient = np.zeros((height, width, 3), dtype=np.uint8)

for y in range(height):
    for x in range(width):
        t = (x + y) / (width + height)  # Diagonal gradient
        # Make the gradient more abrupt by applying a power function
        t = t ** 1.5  # This makes the transition more abrupt
        color = (1 - t) * start_color + t * end_color
        gradient[y, x] = color.astype(np.uint8)

# Convert to image
gradient_image = Image.fromarray(gradient)

# Generate grain (noise)
noise = np.random.normal(loc=128, scale=100, size=(height, width)).astype(np.uint8)
noise_image = Image.fromarray(noise, mode='L').convert("RGB")

# Blend noise with gradient
grainy_image = Image.blend(gradient_image, noise_image, alpha=0.10)

# Save the image
file_path = "assets/img/gradient_background_generated.png"
grainy_image.save(file_path)
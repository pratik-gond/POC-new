import numpy as np
import os
from PIL import Image

def is_single_color_image(image_path, threshold=20):
    """
    Check if an image is of a single color by comparing pixels to the average color.
    An image is considered single-colored if more than 50% of pixels are within threshold
    of the average color.
    
    Args:
        image_path (str): Path to the image file
        threshold (int): Threshold value for considering pixels as the same color (0-255)
        
    Returns:
        bool: True if image is not a single color, False if it is a single color
    """
    try:
        img = Image.open(image_path)
        img_array = np.array(img)
        
        if len(img_array.shape) == 3:  # Color image (RGB/RGBA)
            avg_color = np.mean(img_array[:, :, :3], axis=(0,1)).astype(int)
            color_diff = np.abs(img_array[:, :, :3] - avg_color)
            pixels_within_threshold = np.sum(np.all(color_diff <= threshold, axis=2))
            total_pixels = img_array.shape[0] * img_array.shape[1]
            percentage_within_threshold = (pixels_within_threshold / total_pixels) * 100
            return percentage_within_threshold <= 50
            
        elif len(img_array.shape) == 2:  # Grayscale image
            avg_value = np.mean(img_array).astype(int)
            differences = np.abs(img_array - avg_value)
            pixels_within_threshold = np.sum(differences <= threshold)
            total_pixels = img_array.shape[0] * img_array.shape[1]
            percentage_within_threshold = (pixels_within_threshold / total_pixels) * 100
            return percentage_within_threshold <= 50
            
        else:
            return True
            
    except Exception:
        return True

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.join(current_dir, "test_images")
    os.makedirs(test_dir, exist_ok=True)
    
    print("\nSingle Color Image Detector")
    print("-------------------------")
    
    while True:
        print("\nOptions:")
        print("1. Check if an image is of a single color")
        print("2. Exit")
        
        choice = input("\nEnter your choice (1-2): ")
        
        if choice == "1":
            image_path = input("Enter the path to the image file: ")
            
            if not os.path.exists(image_path):
                print("Error: File does not exist!")
                continue
            
            is_multiple_color = is_single_color_image(image_path)
            
            if is_multiple_color:
                print("Result: The image contains multiple colors.")
            else:
                print("Result: The image is of a single color!")
                
        elif choice == "2":
            print("Goodbye!")
            break
            
        else:
            print("Invalid choice! Please try again.")

if __name__ == "__main__":
    main()
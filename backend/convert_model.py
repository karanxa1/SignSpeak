import os
import tensorflow as tf

def convert_h5_to_tflite(h5_path, tflite_path):
    print(f"Loading {h5_path}...")
    model = tf.keras.models.load_model(h5_path)
    
    print("Converting to TFLite...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)
    # Enable optimizations for speed
    converter.optimizations = [tf.lite.Optimize.DEFAULT]
    tflite_model = converter.convert()
    
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)
    print(f"Successfully saved to {tflite_path}!")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    h5_file = os.path.join(current_dir, "cnn8grps_rad1_model.h5")
    tflite_file = os.path.join(current_dir, "model.tflite")
    
    if os.path.exists(h5_file):
        convert_h5_to_tflite(h5_file, tflite_file)
    else:
        print(f"Could not find {h5_file}")

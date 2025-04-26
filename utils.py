from pylibrelinkup import PyLibreLinkUp
import os
import json
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np

# Libre link up client
client = PyLibreLinkUp(email=os.environ["LIBRELINK_EMAIL"], password=os.environ["LIBRELINK_PASSWORD"])
client.authenticate()
patient = client.get_patients()[0]

def calculate_insulin_dose(glucose, carbs):
    # Load client data from JSON file
    with open("clientdata.json", "r") as f:
        client_data = json.load(f)

    ratio = client_data["ratio"]
    sensitivity = client_data["sensitivity"]
    lower_threshold = client_data["lower_threshold"]
    high_threshold = client_data["high_threshold"]

    # Calculate insulin dose based on the provided formula
    insulin_dose = (glucose - lower_threshold) / sensitivity + (carbs / ratio)
    
    return insulin_dose

def get_latest_glucose_data():
    latest_glucose = client.latest(patient_identifier=patient)
    return latest_glucose

def get_graph_data():
    graph_data = client.graph(patient_identifier=patient)
    return graph_data

def get_graph_data_text(stride=2):
    graph_data  = get_graph_data()
    graph_data_text = ""

    for i, entry in enumerate(graph_data):
        if i % stride == 0:
            measurement = str(entry.value)
            date = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            line = f"Measurement: {measurement} mg/dL, Date: {date}\n"
            graph_data_text += line
    
    # Create plot of measurements
    plt.figure(figsize=(10, 6))
    measurements = [entry.value for entry in graph_data]
    timestamps = [entry.timestamp for entry in graph_data]
    plt.plot(timestamps, measurements)
    plt.xlabel('Time')
    plt.ylabel('Glucose (mg/dL)')
    plt.title('Glucose Measurements Over Time')
    plt.xticks(rotation=45)
    plt.tight_layout()
    graph_image = plt.gcf()
    plt.savefig('glucose_plot.png')
    graph_image = np.array(Image.open('glucose_plot.png'))
    
    return graph_data_text, graph_image

if __name__ == "__main__":
    get_graph_data()
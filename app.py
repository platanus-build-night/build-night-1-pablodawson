import streamlit as st
from openai import OpenAI
import dotenv
dotenv.load_dotenv()

import os
import json
from utils import get_latest_glucose_data, calculate_insulin_dose, get_graph_data_text
import base64
import re
from PIL import Image
import io



st.title("Glucosinho 🍪")

# Create an OpenAI client.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

ready = False
# Check if the client data file exists, if not, prompt the user for input.
if os.path.exists("clientdata.json"):
    with open("clientdata.json", "r") as f:
        client_data = json.load(f)
        ready = True
else:
    st.write("Enter your treatment data to start:")
    
    if not ready:
        ratio = st.slider('Insulin to Carb Ratio (g/U)', min_value=5, max_value=50, value=12)
        sensitivity = st.number_input('Insulin Sensitivity Factor (mg/dL per U)', min_value=50, max_value=300, value=60)
        lower_threshold = st.number_input('Lower Blood Glucose Threshold (mg/dL)', min_value=0, value=100)
        high_threshold = st.number_input('High Blood Glucose Threshold (mg/dL)', min_value=0, value=150)

        ready = st.button("Ready")
        client_data = {
            "ratio": ratio,
            "sensitivity": sensitivity,
            "lower_threshold": lower_threshold,
            "high_threshold": high_threshold,
        }
        if ready:
            with open("clientdata.json", "w") as f:
                json.dump(client_data, f)
            ready = True
            st.rerun()

# Persistent messages
if "messages" not in st.session_state:
    st.session_state.messages = []

if ready:
    # Display the existing chat messages via `st.chat_message`.
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Create columns for text and image
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(message["content"])
            with col2:
                if "image" in message and message["image"]:
                    st.image(message["image"], use_container_width =True)

    prompt = st.chat_input(
        "Ask me anything about your treatment, or upload a photo of your meal",
        accept_file=True,
        file_type=["jpg", "jpeg", "png"],
    )

    if prompt:

        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(prompt.text)
            with col2:
                if prompt["files"]:
                    st.image(prompt["files"][0], use_container_width =True)

        # If there's an image, check carbs
        # Convert the uploaded file to base64
        if prompt["files"]:
            # Open image and resize while maintaining aspect ratio
            img = Image.open(prompt["files"][0])
            width = 500
            ratio = width / float(img.size[0])
            height = int(float(img.size[1]) * ratio)
            img = img.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")

            # Convert to base64
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

            response = client.chat.completions.create(
                model="gpt-4.1",
                response_format={"type": "json_object"},
                messages=[
                            {
                                "role": "system",
                                "content": """You are a dietitian. A user sends you an image of a meal and you tell them how many carbohidrates are in it. Use the following JSON format:

                {
                    "reasoning": "reasoning for the total carbohidrates",
                    "food_items": [
                        {
                            "name": "food item name",
                            "carbohidrates": "carbohidrates in the food item"
                        }
                    ],
                    "total": "total carbohidrates in the meal"
                }"""
                            },
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "How many carbohidrates is in this meal?"
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/jpeg;base64,{base64_image}"
                                        }
                                    }
                                ]
                            },
                        ],
            )

            response_message = response.choices[0].message
            content = response_message.content

            try:
                # Extraer cantidad de carbohidratos del JSON
                json_response = json.loads(content)
                carbs = re.sub('\D', '', str(json_response["total"]))
                reasoning = json_response["reasoning"]
                food_items = json_response["food_items"]
                food_items_list = "\n".join([f"- {item['name']}: {item['carbohidrates']}" for item in food_items])
                carbs = int(carbs)
            except json.JSONDecodeError:
                st.error("Could not parse the response. Please try again.")
                st.session_state.messages.append({"role": "assistant", "content": "Could not parse the response. Please try again."})

            # Parse the JSON response
            current_sensor_data = get_latest_glucose_data()
            needed_dose = int(round(calculate_insulin_dose(current_sensor_data.value, carbs)))

            message = f"""
                ### Carbohydrate Analysis 🔍
                {reasoning}

                ### Meal Summary 🍽️
                Total carbohydrates: **{carbs}g**

                ### Insulin Recommendation 💉
                Current glucose level: **{current_sensor_data.value} mg/dL**
                Recommended insulin dose: **{needed_dose} U**

                """
            
            # Append to the session state messages
            st.session_state.messages.append({"role": "assistant", "content": message})

            # Show the response in the chat
            with st.chat_message("assistant"):
                col1, col2 = st.columns([3, 1])
                st.markdown(message)
        else:
            graph_data, graph = get_graph_data_text(stride=2)

            system_msg = "You are a diabetologist. You got the following data from the glucose sensor of a patient: " + graph_data + "and the following treatment data: " + str(client_data) + ". Answer to the user, using the provided information and measurements if necessary. You can style your message with markdown."

            user_messages = []
            for m in st.session_state.messages:
                if isinstance(m["content"], str):
                    content = m["content"]
                else:
                    content = m["content"].text
                user_messages.append({
                    "role": m["role"],
                    "content": content
                })
            
            messages = [
                {"role": "system", "content": system_msg},
            ] + user_messages

            # No image, just answer with 
            stream = client.chat.completions.create(
                model="gpt-4.1",
                messages=messages,
                stream=True,
            )
            
            with st.chat_message("assistant"):
                response = st.write_stream(stream)
                # Check if response contains measurement-related words
                if any(word in response.lower() for word in ["measure", "measurement", "readings", "glucose", "levels"]):
                    st.image(graph)
                message = response
            
            st.session_state.messages.append({"role": "assistant", "content": message})
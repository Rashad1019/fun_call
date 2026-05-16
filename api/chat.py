import os
import ast
import operator
import requests
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

MODEL_NAME = "gemini-3.1-flash-lite"

TOOL_DECLARATIONS = [
    {
        "name": "get_weather",
        "description": "Get the current weather and temperature for any city in the world",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {
                    "type": "STRING",
                    "description": "The name of the city (e.g., 'Delhi', 'London', 'New York', 'Tokyo')"
                }
            },
            "required": ["city"]
        }
    },
    {
        "name": "calculate",
        "description": (
            "Perform mathematical calculations. "
            "Supports +, -, *, /, ** (power), % (modulo), and parentheses."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "expression": {
                    "type": "STRING",
                    "description": "Math expression to evaluate (e.g., '15 * 4', '2 ** 10', '(5 + 3) * 2')"
                }
            },
            "required": ["expression"]
        }
    },
    {
        "name": "get_current_time",
        "description": "Get the current date and time",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]


def get_weather(city: str) -> str:
    try:
        geo_url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={requests.utils.quote(city)}&count=1&language=en&format=json"
        )
        geo_data = requests.get(geo_url, timeout=10).json()

        if not geo_data.get("results"):
            return f"City not found: {city}"

        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        name = loc["name"]
        country = loc.get("country", "")

        weather_url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true"
        )
        w_data = requests.get(weather_url, timeout=10).json()
        cw = w_data["current_weather"]

        wmo_codes = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Foggy", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
            55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
            71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
            80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
            95: "Thunderstorm", 96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail"
        }
        condition = wmo_codes.get(cw.get("weathercode", 0), "Unknown")

        return (
            f"Weather in {name}, {country}: {condition}. "
            f"Temperature: {cw['temperature']}°C, Wind: {cw['windspeed']} km/h"
        )
    except requests.RequestException as e:
        return f"Network error: {e}"
    except (KeyError, ValueError) as e:
        return f"Data error: {e}"


def calculate(expression: str) -> str:
    ALLOWED_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def safe_eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.BinOp):
            op = ALLOWED_OPS.get(type(node.op))
            if not op:
                raise ValueError(f"Unsupported: {type(node.op).__name__}")
            left, right = safe_eval(node.left), safe_eval(node.right)
            if isinstance(node.op, ast.Div) and right == 0:
                raise ValueError("Division by zero")
            return op(left, right)
        if isinstance(node, ast.UnaryOp):
            op = ALLOWED_OPS.get(type(node.op))
            if not op:
                raise ValueError(f"Unsupported: {type(node.op).__name__}")
            return op(safe_eval(node.operand))
        raise ValueError(f"Unsupported element: {type(node).__name__}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = safe_eval(tree.body)
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f"{expression} = {result}"
    except ValueError as e:
        return f"Math error: {e}"
    except SyntaxError:
        return f"Invalid expression: {expression}"


def get_current_time() -> str:
    return datetime.now().strftime("Current date and time: %A, %B %d, %Y at %I:%M %p")


TOOL_FUNCTIONS = {
    "get_weather": lambda args: get_weather(args.get("city", "")),
    "calculate": lambda args: calculate(args.get("expression", "")),
    "get_current_time": lambda args: get_current_time(),
}


@app.route("/api/chat", methods=["POST", "OPTIONS"])
@app.route("/", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        return "", 200

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return jsonify({
            "error": "GEMINI_API_KEY is not set. Add it to your .env file or environment variables."
        }), 500

    genai.configure(api_key=api_key)

    data = request.get_json()
    if not data or not data.get("message", "").strip():
        return jsonify({"error": "Missing or empty 'message' field"}), 400

    user_message = data["message"].strip()

    model = genai.GenerativeModel(
        model_name=MODEL_NAME,
        tools=[{"function_declarations": TOOL_DECLARATIONS}],
        system_instruction=(
            "You are a helpful AI assistant demonstrating function calling in LLMs. "
            "Use the available tools when appropriate. "
            "Always briefly mention which tools you used in your answer."
        )
    )

    tool_calls_log = []

    try:
        chat_session = model.start_chat()
        response = chat_session.send_message(user_message)

        for _ in range(5):
            function_call = None
            for part in response.candidates[0].content.parts:
                if hasattr(part, "function_call") and part.function_call.name:
                    function_call = part.function_call
                    break

            if not function_call:
                break

            func_name = function_call.name
            func_args = dict(function_call.args)

            func_result = (
                TOOL_FUNCTIONS[func_name](func_args)
                if func_name in TOOL_FUNCTIONS
                else f"Unknown function: {func_name}"
            )

            tool_calls_log.append({
                "name": func_name,
                "arguments": func_args,
                "result": func_result
            })

            response = chat_session.send_message(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=func_name,
                        response={"result": func_result}
                    )
                )
            )

        final_text = "".join(
            part.text
            for part in response.candidates[0].content.parts
            if hasattr(part, "text") and part.text
        ) or "No response generated."

        return jsonify({
            "response": final_text,
            "tool_calls": tool_calls_log,
            "model": MODEL_NAME
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)

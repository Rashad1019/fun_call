# Function Calling in LLMs

A live demo of function calling with Google Gemini. Ask a question — watch the model decide whether to use a tool, call it, and fold the result into its answer.

![Black and red UI showing a chat interface with tool call visualization](https://github.com/Rashad1019/fun_call/raw/main/assets/preview.png)

## What it does

Most LLM demos show text generation. This one shows the step in between: the model reading your question, deciding a tool is needed, generating structured arguments, running the function, and only then writing its response.

Every tool call is rendered visibly — function name, input arguments, and the raw result — so you can see exactly what happened before the final answer appeared.

## Tools available

| Tool | What it does |
|------|-------------|
| `get_weather(city)` | Live weather for any city via the free Open-Meteo API |
| `calculate(expression)` | Safe math evaluator — `2**10`, `(15 * 4) / 3`, etc. |
| `get_current_time()` | Current date and time |

## Stack

- **Model** — `gemini-3.1-flash-lite` via the Google Generative AI SDK
- **Backend** — Flask (Python), deployed as a Vercel serverless function
- **Frontend** — Single `index.html`, no framework, no build step
- **Weather data** — [Open-Meteo](https://open-meteo.com/) (free, no API key required)

## Run locally

**1. Clone and set up the environment**

```bash
git clone https://github.com/Rashad1019/fun_call.git
cd fun_call
python -m venv venv
```

**2. Activate the virtual environment**

```bash
# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Add your Gemini API key**

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder with your key:

```
GEMINI_API_KEY=your_key_here
```

Get a free key at [aistudio.google.com](https://aistudio.google.com/app/apikey).

**5. Start the server**

```bash
python app.py
```

**6. Open the frontend**

Open `index.html` directly in your browser. It auto-detects localhost and points requests to `http://localhost:5000`.

## Deploy to Vercel

1. Push to GitHub
2. Import the repo at [vercel.com/new](https://vercel.com/new)
3. Add `GEMINI_API_KEY` as an environment variable in the Vercel dashboard
4. Deploy

The `vercel.json` config routes `/api/chat` to the Flask app and serves `index.html` as a static file at the root.

## Project structure

```
fun_call/
├── app.py           # Flask backend — Gemini function calling logic
├── index.html       # Frontend chat UI
├── requirements.txt # Python dependencies
├── vercel.json      # Vercel deployment config
├── .env.example     # Environment variable template
└── .gitignore
```

## How function calling works

```
User query
    ↓
Gemini reads the query + tool definitions
    ↓
Model decides: does this need a tool?
    ↓ (if yes)
Model outputs structured arguments — e.g. { "city": "Tokyo" }
    ↓
app.py executes the matching Python function
    ↓
Result is sent back to the model
    ↓
Model writes the final response using real data
```

The backend runs this loop up to 5 times per request to handle multi-step tool use.

## License

MIT

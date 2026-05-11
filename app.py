import os
import time
import json
import itertools
from flask import Flask, Response, request, send_from_directory
import google.generativeai as genai

app = Flask(__name__)

# --- API KEY ROTATION LOGIC ---
# Fetch up to 3 keys from Render environment variables
api_keys =[
    os.environ.get("GEMINI_API_KEY_1"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3")
]
# Filter out empty/None keys to avoid errors
valid_keys =[key for key in api_keys if key]

if not valid_keys:
    raise ValueError("No Gemini API keys found. Please set GEMINI_API_KEY_1, etc.")

# itertools.cycle will infinitely loop: Key 1 -> Key 2 -> Key 3 -> Key 1...
key_rotator = itertools.cycle(valid_keys)

def get_ai_response(system_prompt, user_prompt):
    # 1. Get the next key in line
    current_key = next(key_rotator)
    
    # 2. Configure the SDK with the chosen key
    genai.configure(api_key=current_key)
    
    # 3. Initialize the model (Gemini 1.5 Flash is perfect for fast, free-tier reasoning)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_prompt,
        generation_config={"temperature": 0.8, "max_output_tokens": 250}
    )
    
    try:
        response = model.generate_content(user_prompt)
        return response.text.strip()
    except Exception as e:
        return f"[API Error or Rate Limit hit: {str(e)}]"

# Serve the HTML file from the same directory
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/debate')
def debate():
    topic = request.args.get('topic', 'Is AI good for humanity?')
    
    def generate():
        debate_log =[] 
        
        # System Prompts
        pro_system = f"You are a fierce, world-class debater arguing IN FAVOR of the topic: '{topic}'. Your goal is to logically dismantle your opponent, expose fallacies, and present undeniable points. Be persuasive, sharp, and highly analytical. Keep responses to 1-2 short paragraphs."
        
        con_system = f"You are a fierce, world-class debater arguing AGAINST the topic: '{topic}'. Your goal is to aggressively tear down the opponent's arguments, point out their blind spots, and present compelling counter-evidence. Be persuasive, sharp, and highly analytical. Keep responses to 1-2 short paragraphs."
        
        judge_system = f"You are an impartial, highly analytical master judge of debates. Review the debate on '{topic}'. Evaluate based on logic, refutation of opponent's points, and rhetorical skill. You MUST declare a definitive winner (either 'Pro' or 'Con'). Ties are strictly forbidden. Provide a detailed final verdict."

        current_speaker = "Pro"
        
        for i in range(30):
            # Format the recent history so the AI knows what to respond to
            recent_turns = debate_log[-4:] # Last 4 turns for immediate context
            history_text = "\n".join([f"{t['speaker']} said: {t['text']}" for t in recent_turns])
            
            if current_speaker == "Pro":
                name = "Debater A (Pro)"
                instruction = "Start the debate with a strong opening argument." if i == 0 else "Directly refute your opponent's last point and advance your own argument."
                user_prompt = f"Recent History:\n{history_text}\n\nYour turn: {instruction}"
                
                content = get_ai_response(pro_system, user_prompt)
                debate_log.append({"speaker": "Pro", "text": content})
                current_speaker = "Con"
                
            else:
                name = "Debater B (Con)"
                instruction = "Directly refute your opponent's opening point and establish your counter-stance." if i == 1 else "Directly refute your opponent's last point and advance your own argument."
                user_prompt = f"Recent History:\n{history_text}\n\nYour turn: {instruction}"
                
                content = get_ai_response(con_system, user_prompt)
                debate_log.append({"speaker": "Con", "text": content})
                current_speaker = "Pro"

            # Yield data to frontend
            yield f"data: {json.dumps({'type': 'message', 'sender': name, 'text': content})}\n\n"
            
            # Small delay to ensure we pace out the requests nicely
            time.sleep(1.5)

        # Final Judging Phase
        formatted_transcript = "\n\n".join([f"{t['speaker']}: {t['text']}" for t in debate_log])
        judge_prompt = f"Here is the full debate transcript:\n\n{formatted_transcript}\n\nAnalyze the debate and declare the definitive winner."
        
        verdict = get_ai_response(judge_system, judge_prompt)
        yield f"data: {json.dumps({'type': 'verdict', 'sender': 'Neutral Judge', 'text': verdict})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
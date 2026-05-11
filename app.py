import os
import time
import json
import itertools
from flask import Flask, Response, request, send_from_directory
import google.generativeai as genai

app = Flask(__name__)

# --- API KEY ROTATION ---
api_keys =[
    os.environ.get("GEMINI_API_KEY_1"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3")
]
valid_keys =[key for key in api_keys if key]

if not valid_keys:
    raise ValueError("No Gemini API keys found. Please set GEMINI_API_KEY_1, etc.")

key_rotator = itertools.cycle(valid_keys)

def get_ai_response(system_prompt, user_prompt):
    current_key = next(key_rotator)
    genai.configure(api_key=current_key)
    
    # Increased max_output_tokens to 1500 to prevent truncation
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        generation_config={
            "temperature": 0.8, 
            "max_output_tokens": 1500,
            "top_p": 0.95
        }
    )
    
    try:
        response = model.generate_content(user_prompt)
        # Check if the model stopped because it hit the token limit
        if response.candidates[0].finish_reason != 1: # 1 is STOP
            print(f"Warning: Model finished with reason {response.candidates[0].finish_reason}")
            
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/debate')
def debate():
    topic = request.args.get('topic', 'We live in a simulation')
    
    def generate():
        debate_log =[]
        
        pro_system = f"""You are a master orator and elite intellectual debating IN FAVOR of the topic: '{topic}'.
RULES:
1. Never agree with or concede points.
2. Use sharp analogies and philosophical logic.
3. Ruthlessly deconstruct your opponent's fallacies.
4. Tone: Aggressive but sophisticated.
5. COMPLETE YOUR THOUGHTS: Ensure every sentence is finished and your argument is fully fleshed out."""

        con_system = f"""You are a brilliant, relentlessly skeptical debater arguing AGAINST the topic: '{topic}'.
RULES:
1. Never agree with or concede points.
2. Exploit blind spots, contradictions, and logical gaps in the opponent's arguments.
3. Play offense, attacking the foundation of their premise.
4. Tone: Cold, calculating, and unapologetically critical.
5. COMPLETE YOUR THOUGHTS: Ensure every sentence is finished and your argument is fully fleshed out."""

        judge_system = f"You are the Supreme Arbiter of a debate on '{topic}'. Evaluate logic, rebuttal quality, and rhetoric. Declare a definitive winner. Provide a detailed final verdict with critique and the turning point."

        current_speaker = "Pro"
        
        for i in range(30):
            recent_turns = debate_log[-4:] 
            history_text = "\n".join([f"[{t['speaker']}]: {t['text']}" for t in recent_turns])
            
            instruction = "Start the debate with a strong opening." if i == 0 else "Refute the last point and advance your argument."
            
            user_prompt = f"""--- DEBATE HISTORY ---
{history_text}
----------------------
YOUR TASK: {instruction}
CRITICAL: Do not repeat previous points. Do not quote the opponent. Write a complete, logical, and fully formed response."""
            
            if current_speaker == "Pro":
                content = get_ai_response(pro_system, user_prompt)
                debate_log.append({"speaker": "Pro", "text": content})
                current_speaker = "Con"
                sender_name = "Debater A (Pro)"
            else:
                content = get_ai_response(con_system, user_prompt)
                debate_log.append({"speaker": "Con", "text": content})
                current_speaker = "Pro"
                sender_name = "Debater B (Con)"

            yield f"data: {json.dumps({'type': 'message', 'sender': sender_name, 'text': content})}\n\n"
            time.sleep(1.5)

        # Judging
        formatted_transcript = "\n\n".join([f"[{t['speaker']}]: {t['text']}" for t in debate_log])
        verdict = get_ai_response(judge_system, f"Here is the debate:\n{formatted_transcript}\n\nDeclare a winner and provide detailed reasoning.")
        yield f"data: {json.dumps({'type': 'verdict', 'sender': 'Neutral Judge', 'text': verdict})}\n\n"

    return Response(generate(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, port=5000)

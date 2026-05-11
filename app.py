import os
import time
import json
import itertools
from flask import Flask, Response, request, send_from_directory
import google.generativeai as genai

app = Flask(__name__)

# --- API KEY ROTATION ---
api_keys =[os.environ.get(f"GEMINI_API_KEY_{i}") for i in range(1, 4)]
valid_keys = [key for key in api_keys if key]
key_rotator = itertools.cycle(valid_keys)

def get_ai_response(system_prompt, user_prompt):
    genai.configure(api_key=next(key_rotator))
    # Using 800 tokens: enough for ~600 words. Prevents mid-sentence cut-offs.
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=system_prompt,
        generation_config={"temperature": 0.7, "max_output_tokens": 800}
    )
    try:
        response = model.generate_content(user_prompt)
        return response.text.strip() if response.text else "..."
    except Exception as e:
        return f"Debate interrupted: {str(e)}"

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/debate')
def debate():
    topic = request.args.get('topic', 'We live in a simulation')
    
    def generate():
        debate_log =[]
        
        # New Persona: Complex ideas, simple, accessible words.
        pro_system = f"You are debating FOR '{topic}'. Use simple, clear language to explain complex ideas. Be punchy, aggressive, and never concede."
        con_system = f"You are debating AGAINST '{topic}'. Use simple, clear language to explain complex ideas. Be punchy, skeptical, and never concede."
        
        for i in range(30):
            instruction = "Start strong." if i == 0 else "Refute the last point and advance your own."
            history = "\n".join([f"[{t['speaker']}]: {t['text']}" for t in debate_log[-4:]])
            
            prompt = f"History:\n{history}\n\nTask: {instruction}\nRules: Use simple words, explain complex concepts clearly. Max 2 paragraphs. Finish your sentences."
            
            if i % 2 == 0:
                content = get_ai_response(pro_system, prompt)
                debate_log.append({"speaker": "Pro", "text": content})
                yield f"data: {json.dumps({'type': 'message', 'sender': 'Debater A (Pro)', 'text': content})}\n\n"
            else:
                content = get_ai_response(con_system, prompt)
                debate_log.append({"speaker": "Con", "text": content})
                yield f"data: {json.dumps({'type': 'message', 'sender': 'Debater B (Con)', 'text': content})}\n\n"
            
            time.sleep(1) # Keep connection alive

        verdict = get_ai_response("You are the judge.", f"Debate transcript:\n{debate_log}\n\nDeclare a winner and explain why.")
        yield f"data: {json.dumps({'type': 'verdict', 'sender': 'Neutral Judge', 'text': verdict})}\n\n"

    # Important: Set headers for streaming stability
    return Response(generate(), mimetype='text/event-stream', headers={'X-Accel-Buffering': 'no'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

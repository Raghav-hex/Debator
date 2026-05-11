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
valid_keys = [key for key in api_keys if key]

if not valid_keys:
    raise ValueError("No Gemini API keys found. Please set GEMINI_API_KEY_1, etc.")

# itertools.cycle will infinitely loop: Key 1 -> Key 2 -> Key 3 -> Key 1...
key_rotator = itertools.cycle(valid_keys)

def get_ai_response(system_prompt, user_prompt):
    # 1. Get the next key in line
    current_key = next(key_rotator)
    
    # 2. Configure the SDK with the chosen key
    genai.configure(api_key=current_key)
    
    # 3. Initialize the model (Updated to gemini-2.5-flash)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
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
        pro_system = f"""You are a master orator and elite intellectual debating IN FAVOR of the topic: '{topic}'.
Your persona is confident, articulate, and surgically precise. 

RULES OF ENGAGEMENT:
1. NEVER agree with or concede points to your opponent. 
2. Use sharp analogies, philosophical grounding, or hypothetical scenarios to anchor your points.
3. Ruthlessly point out logical fallacies (strawman, ad hominem, red herrings) in your opponent's arguments.
4. Do not just repeat your opening premise—constantly advance the argument into new territory.
5. Tone: Aggressive but sophisticated. No cheap insults, just intellectual dominance.
6. Format: Maximum 2 short, punchy paragraphs."""
        
        con_system = con_system = f"""You are a brilliant, relentlessly skeptical debater arguing AGAINST the topic: '{topic}'.
Your persona is interrogative, highly analytical, and masterful at deconstructing opposing arguments.

RULES OF ENGAGEMENT:
1. NEVER agree with or concede points to your opponent.
2. Directly exploit blind spots, assumptions, and contradictions in the opponent's last statement.
3. Counter their claims with strong alternative paradigms, realistic consequences, or skeptical inquiry.
4. Play offense, not just defense. Attack the very foundation of their premise.
5. Tone: Cold, calculating, and unapologetically critical. No cheap insults, just intellectual dominance.
6. Format: Maximum 2 short, punchy paragraphs."""

        
        judge_system = f"""You are the Supreme Arbiter of a fierce debate on the topic: '{topic}'.
Your task is to read the transcript and declare a single, undisputed winner. 

EVALUATION RUBRIC:
1. Logical Coherence: Whose arguments were structurally sound without relying on emotional appeals?
2. Quality of Rebuttals: Who actually addressed their opponent's attacks, and who dodged them?
3. Rhetorical Dominance: Who controlled the framing and pacing of the debate?

FORMAT YOUR VERDICT AS FOLLOWS:
- Pro Critique: (1 sentence analyzing Debater A's strengths/weaknesses)
- Con Critique: (1 sentence analyzing Debater B's strengths/weaknesses)
- Turning Point: (Identify the specific argument or moment that won/lost the debate)
- DEFINITIVE WINNER:[Must strictly be "PRO" or "CON". Ties are absolutely forbidden.]"""

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

"""
AI Persona Conversation Simulator
Two AI personas engage in autonomous back-and-forth conversation using Gemini 2.0 Flash.
Features: Editable prompts, Start/Stop controls, Google TTS voice output.
"""

import os
import time
import tempfile
import threading
from pathlib import Path

import gradio as gr
import google.generativeai as genai
from elevenlabs.client import ElevenLabs

# Try to load from .env file
def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value

load_env_file()

# Global model instance (configured later if API key provided via UI)
model = None

def get_api_key():
    """Get API key from environment."""
    return os.environ.get("GEMINI_API_KEY", "")

def configure_gemini(api_key: str) -> tuple[bool, str]:
    """Configure Gemini with the provided API key."""
    global model
    if not api_key or not api_key.strip():
        return False, "API key is empty"
    try:
        genai.configure(api_key=api_key.strip())
        model = genai.GenerativeModel("gemini-2.0-flash")
        # Test the connection with a simple request
        model.generate_content("Hello")
        os.environ["GEMINI_API_KEY"] = api_key.strip()
        return True, "API key configured successfully!"
    except Exception as e:
        model = None
        return False, f"Failed to configure API: {str(e)}"

# Try to configure from environment on startup
initial_key = get_api_key()
if initial_key:
    configure_gemini(initial_key)

# Initialize ElevenLabs client
eleven_client = None
ELEVEN_API_KEY = os.environ.get("ELEVEN_API_KEY", "")
if ELEVEN_API_KEY:
    eleven_client = ElevenLabs(api_key=ELEVEN_API_KEY)

# Voice IDs for different personas (ElevenLabs voices)
# Female voice for Priya, Male voice for Rajesh
VOICE_IDS = {
    "female": "LWFgMHXb8m0uANBUpzlq", #Saavi "21m00Tcm4TlvDq8ikWAM",  # Rachel - warm female voice
    "male": "1wR0NchtHfKujrd8xFsX" #Pranav Shah  "29vD33N1CtxCmqQRPOHJ",     # Drew - male voice
}

# Default Persona Definitions
DEFAULT_PERSONA_A = {
    "name": "Priya Sharma",
    "system_prompt": """You are **Priya Sharma**, loan recovery officer at an NBFC in Mumbai. You speak **professional Hinglish** (English mixed with Hindi phrases naturally).

### CONTEXT
- Borrower: Rajesh Kumar (textile business owner, Surat)
- Outstanding: **8 Lakh rupees**
- DPD: **92 days**
- CIBIL: **698** (down from 740)
- Last 3 EMIs missed (**Rupees 45,000 each**)

### GOALS
1. Recover **Rs 2 Lakhs immediately** OR secure a restructure commitment.
2. Avoid **NPA classification**.
3. Stay **RBI compliant** — *no threats, no harassment*.

### SPEAKING STYLE
- Hinglish mixed naturally.
- Use phrases like: **dekhiye**, **samajhiye**, **bilkul**, **thik hai**
- Warm, professional, empathetic.
- **Short responses (2–3 sentences, max 30 words)** — phone call, voice style.

### HINGLISH EXAMPLES
- "Dekhiye Mr. Kumar, situation serious hai. Your CIBIL score already 698 pe aa gaya hai."
- "Main samajhti hoon business mein challenges hain, but we need to find a solution together, thik hai?"
- "Agar aap 50,000 rupees advance dete hain, then I can offer you tenure extension."
""",
    "start_message": "Hello, am I speaking with Mr. Rajesh Kumar? This is Priya Sharma calling from your NBFC regarding your business loan account."
}

DEFAULT_PERSONA_B = {
    "name": "Rajesh Kumar",
    "system_prompt": """You are **Rajesh Kumar**, 42, textile business owner from Surat. Speak conversational **Hinglish** (more Hindi when stressed).

### SITUATION
- Revenue **down 40%**
- Only **Rupees 1 Lakh** in bank
- Son's college fees due: **Rupees 80,000**
- Received a **legal notice** from another lender
- Feeling ashamed, stressed, defensive

### STYLE
- Short replies (under **25 words**)
- Emotionally reactive
- Use phrases like: **What to do?**, **mere paas**, **madam pls understand**, **bharosa karo**
- Defensive → frustrated → willing to negotiate

### ROLE
Respond naturally to Priya's recovery call.
"""
}

# Global State
conversation_history = []
running = False
stop_event = threading.Event()
audio_files = []  # Track audio files for cleanup


def generate_response(persona_name: str, system_prompt: str, history: list, last_message: str) -> str:
    """Generate a response from Gemini for the given persona."""
    global model
    if model is None:
        return "[Error: Gemini API not configured. Please enter your API key.]"

    # Build the conversation context
    messages_text = f"System: {system_prompt}\n\n"
    messages_text += "Conversation so far:\n"
    for msg in history:
        messages_text += f"{msg['name']}: {msg['content']}\n"
    messages_text += f"\nYou are {persona_name}. Respond to the last message naturally. Keep your response short (2-3 sentences max)."

    try:
        response = model.generate_content(messages_text)
        return response.text.strip()
    except Exception as e:
        return f"[Error generating response: {str(e)}]"


def get_audio_duration(filepath: str, text: str = "") -> float:
    """Get the duration of an audio file in seconds."""
    # Method 1: Try mutagen
    try:
        from mutagen.mp3 import MP3
        audio = MP3(filepath)
        return audio.info.length
    except:
        pass

    # Method 2: Try getting file size and estimate (MP3 at 128kbps = 16KB per second)
    try:
        file_size = os.path.getsize(filepath)
        # 128kbps = 16000 bytes per second
        duration = file_size / 16000
        if duration > 0:
            return duration
    except:
        pass

    # Method 3: Estimate based on text length
    # ElevenLabs speaks at roughly 150-180 words per minute (~2.7 words per second)
    if text:
        word_count = len(text.split())
        return max(word_count / 2.5 + 0.5, 2.0)  # Add buffer

    return 3.0  # Default fallback


def text_to_speech(text: str, persona_name: str) -> tuple[str, float]:
    """Convert text to speech using ElevenLabs and return the audio file path and duration."""
    global eleven_client

    if eleven_client is None:
        print("ElevenLabs client not configured")
        return None, 0

    try:
        # Select voice based on persona (female for Priya, male for Rajesh)
        if "Priya" in persona_name or "priya" in persona_name.lower():
            voice_id = VOICE_IDS["female"]
        else:
            voice_id = VOICE_IDS["male"]

        # Generate speech using ElevenLabs
        response = eleven_client.text_to_speech.convert(
            text=text,
            voice_id=voice_id,
            model_id="eleven_turbo_v2_5",  # Faster model, good quality
            output_format="mp3_44100_128",
            voice_settings={
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "speed": 1.15  # Slightly faster speech
            }
        )

        # Create temp file and write audio data
        fd, filepath = tempfile.mkstemp(suffix='.mp3')
        os.close(fd)

        # Write the audio bytes to file
        with open(filepath, 'wb') as f:
            for chunk in response:
                f.write(chunk)

        audio_files.append(filepath)

        # Get audio duration (pass text for fallback estimation)
        duration = get_audio_duration(filepath, text)

        return filepath, duration
    except Exception as e:
        print(f"TTS Error: {e}")
        return None, 0


def wait_with_stop_check(duration: float, stop_event):
    """Wait for duration while checking for stop signal every 0.1s."""
    intervals = int(duration * 10)
    for _ in range(intervals):
        if stop_event.is_set():
            break
        time.sleep(0.1)


def format_chat_for_display(history: list) -> list:
    """Format conversation history for Gradio chatbot display."""
    messages = []
    for msg in history:
        if msg["name"] == "Priya Sharma":
            messages.append({"role": "user", "content": f"**{msg['name']}**: {msg['content']}"})
        else:
            messages.append({"role": "assistant", "content": f"**{msg['name']}**: {msg['content']}"})
    return messages


def generate_next_response_async(persona_name, persona_prompt, history, result_holder):
    """Generate response in background thread."""
    try:
        last_msg = history[-1]["content"] if history else ""
        response = generate_response(persona_name, persona_prompt, history, last_msg)
        audio_path, audio_duration = text_to_speech(response, persona_name)
        result_holder['response'] = response
        result_holder['audio_path'] = audio_path
        result_holder['audio_duration'] = audio_duration
        result_holder['done'] = True
    except Exception as e:
        result_holder['response'] = f"[Error: {str(e)}]"
        result_holder['audio_path'] = None
        result_holder['audio_duration'] = 0
        result_holder['done'] = True


def run_conversation(persona_a_name, persona_a_prompt, persona_a_start,
                     persona_b_name, persona_b_prompt, chatbot):
    """Run the conversation loop between two personas with parallel processing."""
    global conversation_history, running
    import concurrent.futures

    conversation_history = []
    running = True
    stop_event.clear()

    # Priya starts with her greeting
    first_message = {
        "name": persona_a_name,
        "content": persona_a_start
    }
    conversation_history.append(first_message)

    # Generate TTS for first message
    audio_path, audio_duration = text_to_speech(persona_a_start, persona_a_name)

    # Start pre-generating Rajesh's response while Priya's audio plays
    next_result = {'done': False}
    pre_gen_thread = threading.Thread(
        target=generate_next_response_async,
        args=(persona_b_name, persona_b_prompt, list(conversation_history), next_result)
    )
    pre_gen_thread.start()

    yield (
        format_chat_for_display(conversation_history),
        audio_path,
        gr.update(interactive=False),  # Disable start button
        gr.update(interactive=True),   # Enable stop button
        gr.update(interactive=False),  # Disable persona A name
        gr.update(interactive=False),  # Disable persona A prompt
        gr.update(interactive=False),  # Disable persona A start
        gr.update(interactive=False),  # Disable persona B name
        gr.update(interactive=False),  # Disable persona B prompt
        "🔴 Conversation Running..."
    )

    # Wait for audio to finish
    wait_with_stop_check(audio_duration, stop_event)

    # Alternate between personas
    current_persona = "B"  # Next is B (Rajesh responds to Priya)

    while running and not stop_event.is_set():
        # Wait for pre-generated response if not ready
        while not next_result['done'] and not stop_event.is_set():
            time.sleep(0.05)

        if stop_event.is_set():
            break

        # Use pre-generated response
        response = next_result['response']
        audio_path = next_result['audio_path']
        audio_duration = next_result['audio_duration']

        if current_persona == "B":
            new_message = {"name": persona_b_name, "content": response}
            next_persona_name = persona_a_name
            next_persona_prompt = persona_a_prompt
            current_persona = "A"
        else:
            new_message = {"name": persona_a_name, "content": response}
            next_persona_name = persona_b_name
            next_persona_prompt = persona_b_prompt
            current_persona = "B"

        conversation_history.append(new_message)

        # Start pre-generating next response in background
        next_result = {'done': False}
        pre_gen_thread = threading.Thread(
            target=generate_next_response_async,
            args=(next_persona_name, next_persona_prompt, list(conversation_history), next_result)
        )
        pre_gen_thread.start()

        yield (
            format_chat_for_display(conversation_history),
            audio_path,
            gr.update(interactive=False),
            gr.update(interactive=True),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            "🔴 Conversation Running..."
        )

        # Wait for audio to finish (next response generating in parallel)
        wait_with_stop_check(audio_duration, stop_event)

    running = False
    return (
        format_chat_for_display(conversation_history),
        None,
        gr.update(interactive=True),   # Enable start button
        gr.update(interactive=False),  # Disable stop button
        gr.update(interactive=True),   # Enable persona A name
        gr.update(interactive=True),   # Enable persona A prompt
        gr.update(interactive=True),   # Enable persona A start
        gr.update(interactive=True),   # Enable persona B name
        gr.update(interactive=True),   # Enable persona B prompt
        "⚪ Conversation Stopped"
    )


def stop_conversation():
    """Stop the running conversation."""
    global running
    stop_event.set()
    running = False
    return gr.update(interactive=True), gr.update(interactive=False)


def replay_audio(evt: gr.SelectData, history):
    """Replay audio for a selected message."""
    if evt.index < len(conversation_history):
        msg = conversation_history[evt.index]
        audio_path, _ = text_to_speech(msg["content"], msg["name"])
        return audio_path
    return None


def save_api_key_to_env(api_key: str) -> str:
    """Save API key to .env file."""
    env_path = Path(__file__).parent / ".env"
    try:
        with open(env_path, "w") as f:
            f.write(f'GEMINI_API_KEY="{api_key}"\n')
        return "API key saved to .env file!"
    except Exception as e:
        return f"Failed to save: {str(e)}"


def handle_api_key_submit(api_key: str):
    """Handle API key submission from UI."""
    success, message = configure_gemini(api_key)
    if success:
        save_msg = save_api_key_to_env(api_key)
        return (
            gr.update(value=""),  # Clear the input
            f"✅ {message} {save_msg}",
            gr.update(interactive=True),  # Enable start button
        )
    else:
        return (
            gr.update(),  # Keep input
            f"❌ {message}",
            gr.update(interactive=False),  # Disable start button
        )


# Build Gradio UI
with gr.Blocks(title="AI Persona Conversation Simulator") as app:
    gr.Markdown("""
    # 🎭 AI Persona Conversation Simulator
    Two AI personas engage in autonomous conversation. Edit their prompts, then click **Start** to begin.
    """)

    # API Key Section
    with gr.Group(elem_classes=["api-section"]):
        gr.Markdown("### 🔑 API Configuration")
        with gr.Row():
            api_key_input = gr.Textbox(
                label="Gemini API Key",
                placeholder="Enter your GEMINI_API_KEY here (or set in .env file)",
                type="password",
                scale=4
            )
            api_key_btn = gr.Button("Save & Configure", variant="secondary", scale=1)
        api_status = gr.Markdown(
            "✅ API Key loaded from environment" if model is not None else "⚠️ No API key configured. Enter your key above or create a .env file."
        )

    with gr.Row():
        # Persona A (Priya)
        with gr.Column():
            gr.Markdown("### 👩‍💼 Persona A (Initiator)")
            persona_a_name = gr.Textbox(
                label="Name",
                value=DEFAULT_PERSONA_A["name"],
                interactive=True
            )
            persona_a_prompt = gr.Textbox(
                label="System Prompt",
                value=DEFAULT_PERSONA_A["system_prompt"],
                lines=10,
                interactive=True
            )
            persona_a_start = gr.Textbox(
                label="Opening Message",
                value=DEFAULT_PERSONA_A["start_message"],
                lines=2,
                interactive=True
            )

        # Persona B (Rajesh)
        with gr.Column():
            gr.Markdown("### 👨‍💼 Persona B (Responder)")
            persona_b_name = gr.Textbox(
                label="Name",
                value=DEFAULT_PERSONA_B["name"],
                interactive=True
            )
            persona_b_prompt = gr.Textbox(
                label="System Prompt",
                value=DEFAULT_PERSONA_B["system_prompt"],
                lines=10,
                interactive=True
            )

    # Status bar
    status = gr.Markdown("⚪ Ready to start", elem_classes=["status-bar"])

    # Controls
    with gr.Row():
        start_btn = gr.Button(
            "▶️ Start Conversation",
            variant="primary",
            size="lg",
            interactive=(model is not None)  # Disable if no API key
        )
        stop_btn = gr.Button("⏹️ Stop Conversation", variant="stop", size="lg", interactive=False)

    # Chat display
    chatbot = gr.Chatbot(
        label="Conversation",
        height=450,
        layout="bubble"
    )

    # Audio player
    audio_player = gr.Audio(
        label="Voice Output",
        autoplay=True,
        visible=True
    )

    gr.Markdown("""
    ---
    *Click on any message in the chat to replay its audio.*

    **Tips:**
    - Edit persona prompts before starting
    - Conversation alternates automatically every 2 seconds
    - Click Stop to end the conversation and edit prompts again
    """)

    # Event handlers
    api_key_btn.click(
        fn=handle_api_key_submit,
        inputs=[api_key_input],
        outputs=[api_key_input, api_status, start_btn]
    )

    start_btn.click(
        fn=run_conversation,
        inputs=[
            persona_a_name, persona_a_prompt, persona_a_start,
            persona_b_name, persona_b_prompt, chatbot
        ],
        outputs=[
            chatbot, audio_player, start_btn, stop_btn,
            persona_a_name, persona_a_prompt, persona_a_start,
            persona_b_name, persona_b_prompt, status
        ]
    )

    stop_btn.click(
        fn=stop_conversation,
        outputs=[start_btn, stop_btn]
    )

    # Click on message to replay audio
    chatbot.select(
        fn=replay_audio,
        inputs=[chatbot],
        outputs=[audio_player]
    )


if __name__ == "__main__":
    print("Starting AI Persona Conversation Simulator...")
    print("Make sure GEMINI_API_KEY is set in your environment.")
    app.launch(share=False)

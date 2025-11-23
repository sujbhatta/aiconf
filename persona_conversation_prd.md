# AI Persona Conversation Simulator – PRD
### Two-Way Hinglish Loan Recovery Simulation Demo

## 1. Overview
The **AI Persona Conversation Simulator** is a single-file Python application (`persona_chat.py`) showcasing two AI personas engaging in autonomous, back-and-forth voice conversation.

**Key Components:**
- **LLM**: Google Gemini 2.0 Flash for conversation generation
- **TTS**: ElevenLabs for natural voice output
- **UI**: Gradio web interface
- **Config**: `.env` file for API keys

## 2. Goals
- Demonstrate multi-persona AI voice conversation
- Allow editing of persona system prompts via UI
- Use full conversation history per turn for contextual coherence
- Provide clean, modern web UI
- Single-file implementation for easy deployment

## 3. Non-Goals
- No long-term memory or persistence
- No authentication
- No cloud deployment
- No analytics or logging

## 4. Dependencies

```bash
pip install gradio google-generativeai elevenlabs mutagen
```

## 5. Configuration

### 5.1 Environment Variables (`.env` file)
```
GEMINI_API_KEY="your_gemini_api_key"
ELEVEN_API_KEY="your_elevenlabs_api_key"
```

### 5.2 ElevenLabs Voice IDs
```python
VOICE_IDS = {
    "female": "LWFgMHXb8m0uANBUpzlq",  # Saavi - Indian female voice
    "male": "1wR0NchtHfKujrd8xFsX"      # Pranav Shah - Indian male voice
}
```

## 6. Core Features

### 6.1 Persona Management
- Editable **name** and **system prompt** for each persona
- Editable **opening message** for Persona A (initiator)
- Persona editing disabled while conversation is running
- API key can be entered via UI or `.env` file

### 6.2 Conversation Engine
- Persona A starts first with predefined greeting
- Alternating turns between Persona A and Persona B
- Dynamic wait time based on audio duration (+ 0.5s buffer)
- Immediate stop on user command

### 6.3 Voice Output (ElevenLabs)
```python
from elevenlabs.client import ElevenLabs

client = ElevenLabs(api_key=ELEVEN_API_KEY)

response = client.text_to_speech.convert(
    text=text,
    voice_id=voice_id,
    model_id="eleven_turbo_v2_5",  # Fast model, good quality
    output_format="mp3_44100_128",
    voice_settings={
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.0,
        "speed": 1.15  # Slightly faster speech
    }
)
```

### 6.4 Audio Duration Detection
Uses `mutagen` library for accurate MP3 duration, with fallbacks:
1. Mutagen MP3 parsing
2. File size estimation (128kbps = 16KB/sec)
3. Text length estimation (~2.5 words/sec)

### 6.5 UI Components
- API key input with save/configure button
- Two-column persona editor (name, system prompt, opening message)
- Start/Stop conversation buttons
- Chat display with bubble layout
- Auto-playing audio player
- Click-to-replay on chat messages

## 7. Technical Architecture

### 7.1 Global State
```python
model = None                    # Gemini model instance
eleven_client = None            # ElevenLabs client
conversation_history = []       # List of {name, content} dicts
running = False                 # Conversation loop flag
stop_event = threading.Event()  # For graceful stop
```

### 7.2 LLM Input Structure
```python
messages_text = f"System: {system_prompt}\n\n"
messages_text += "Conversation so far:\n"
for msg in history:
    messages_text += f"{msg['name']}: {msg['content']}\n"
messages_text += f"\nYou are {persona_name}. Respond naturally. Keep response short (2-3 sentences max)."
```

### 7.3 Conversation Flow
1. User clicks Start
2. Persona A's opening message displayed + TTS played
3. Wait for audio duration + 0.5s buffer
4. Generate Persona B response via Gemini
5. Display + TTS for Persona B
6. Wait for audio duration + 0.5s buffer
7. Generate Persona A response via Gemini
8. Repeat steps 5-7 until Stop clicked

## 8. User Flow

### Initial State
- Empty chat area
- Persona prompts editable
- Start button enabled (if API key configured)

### On Start
- Clear conversation history
- Disable persona editing
- Begin alternating conversation loop

### On Stop
- Set stop event
- Re-enable persona editing
- Chat transcript remains visible

## 9. File Structure
```
persona_chat.py    # Single-file application
.env               # API keys (GEMINI_API_KEY, ELEVEN_API_KEY)
```

## 10. Running the Application
```bash
python persona_chat.py
```
Opens Gradio UI at `http://127.0.0.1:7860`

---

# Persona Definitions

## Persona 1 – Priya Sharma (Loan Recovery Officer)

### System Prompt
```
You are **Priya Sharma**, loan recovery officer at an NBFC in Mumbai. You speak **professional Hinglish** (English mixed with Hindi phrases naturally).

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
```

### Opening Message
```
Hello, am I speaking with Mr. Rajesh Kumar? This is Priya Sharma calling from your NBFC regarding your business loan account.
```

---

## Persona 2 – Rajesh Kumar (Borrower in Distress)

### System Prompt
```
You are **Rajesh Kumar**, 42, textile business owner from Surat. Speak conversational **Hinglish** (more Hindi when stressed).

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
```

---

## 11. Future Enhancements
- Multi-persona (3+ participants)
- Persistent conversation memory
- Export conversation transcript
- Voice-to-voice mode (STT + TTS)
- Persona trait sliders (empathy, aggression, etc.)
- Multiple language support

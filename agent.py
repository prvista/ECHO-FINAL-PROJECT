import os
import logging
import asyncio
from dotenv import load_dotenv

# 🧹 Clear invalid proxy variables (like skooltech.com)
for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "PROXY"]:
    if var in os.environ:
        del os.environ[var]

# --- Load .env file ---
ROOT_DIR = os.path.dirname(__file__)
ENV_PATH = os.path.join(ROOT_DIR, ".env")

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
    print(f"✅ Loaded environment file: {ENV_PATH}")
else:
    raise FileNotFoundError(f"❌ Could not find .env at {ENV_PATH}")

# --- Debug Print ---
print("LIVEKIT_URL:", os.getenv("LIVEKIT_URL"))
print("LIVEKIT_API_KEY:", os.getenv("LIVEKIT_API_KEY"))
print("LIVEKIT_API_SECRET:", os.getenv("LIVEKIT_API_SECRET"))
print("GOOGLE_API_KEY:", os.getenv("GOOGLE_API_KEY"))

# --- LiveKit Agent Setup ---
from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import noise_cancellation, google
from prompts import AGENT_INSTRUCTION, SESSION_INSTRUCTION
from tools import (
    get_weather,
    search_web,
    send_email,
    open_app,
    greet_user,
    schedule_task_with_google_calendar,  # ✅ Replaced set_reminder
)


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=AGENT_INSTRUCTION,
            llm=google.beta.realtime.RealtimeModel(
                voice="Aoede",
                temperature=0.8,
            ),
            tools=[
                get_weather,
                search_web,
                send_email,
                open_app,
                greet_user,
                schedule_task_with_google_calendar,  # ✅ Added Google Calendar scheduler
            ],
        )

    async def on_audio(self, audio_data, session: AgentSession):
        """Handle voice commands and respond intelligently."""
        try:
            command_text = await google.beta.realtime.realtime_transcribe(audio_data)
            print("[DEBUG] User said:", command_text)
            cmd_lower = command_text.lower()

            # Default response
            response = "Hmm, not sure what that means, Sir."

            if cmd_lower.startswith("open "):
                app_name = cmd_lower.replace("open ", "")
                response = f"Roger that, opening {app_name}."
                await session.speak(response)
                tool_result = await open_app(None, app_name)
                print("[TOOL RESULT]", tool_result)

            elif "weather" in cmd_lower:
                response = "Check! Getting the weather."
                await session.speak(response)
                city = cmd_lower.replace("weather in ", "").strip()
                tool_result = await get_weather(None, city or "Manila")
                print("[TOOL RESULT]", tool_result)

            elif "search for" in cmd_lower:
                response = "Will do, searching the web."
                await session.speak(response)
                query = cmd_lower.replace("search for ", "")
                tool_result = await search_web(None, query)
                print("[TOOL RESULT]", tool_result)

            elif "send email" in cmd_lower:
                response = "Check! Sending your email."
                await session.speak(response)
                try:
                    parts = cmd_lower.split(" ")
                    to_index = parts.index("to") + 1
                    subj_index = parts.index("subject") + 1
                    msg_index = parts.index("message") + 1
                    to_email = parts[to_index]
                    subject = " ".join(parts[subj_index:msg_index - 1])
                    message = " ".join(parts[msg_index:])
                    tool_result = await send_email(None, to_email, subject, message)
                    print("[TOOL RESULT]", tool_result)
                except Exception:
                    print("[ERROR] Failed to parse email command")

            # ✅ New Google Calendar scheduling command
            elif "schedule" in cmd_lower or "remind me" in cmd_lower:
                response = "Got it! Scheduling that in your Google Calendar."
                await session.speak(response)
                try:
                    # Example voice command: "schedule meeting in 10 minutes"
                    if " in " in cmd_lower and " minutes" in cmd_lower:
                        title_part = cmd_lower.split(" in ")[0].replace("schedule", "").replace("remind me to", "").strip()
                        minutes = int(cmd_lower.split(" in ")[1].replace(" minutes", "").strip())
                        tool_result = await schedule_task_with_google_calendar(None, title_part, title_part, minutes)
                        print("[TOOL RESULT]", tool_result)
                        await session.speak("Event successfully added to Google Calendar, Sir.")
                    else:
                        await session.speak("Please specify the time, like 'in 10 minutes'.")
                except Exception as e:
                    print("[ERROR] Failed to parse schedule command:", e)
                    await session.speak("I couldn’t set that schedule, Sir.")

            elif "hello" in cmd_lower or "hi" in cmd_lower:
                response = await greet_user(None)
                await session.speak(response)
            else:
                await session.speak(response)

        except Exception as e:
            print("[ERROR] Audio processing failed:", e)
            await session.speak("Apologies, I couldn't process that command.")


async def entrypoint(ctx: agents.JobContext):
    session = AgentSession()
    await ctx.connect()
    await session.start(
        room=ctx.room,
        agent=Assistant(),
        room_input_options=RoomInputOptions(
            video_enabled=True,
            audio_enabled=True,
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
    await session.generate_reply(instructions=SESSION_INSTRUCTION)


if __name__ == "__main__":
    agents.cli.run_app(
        agents.WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
        )
    )

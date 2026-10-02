# Step-1
import streamlit as st
from google import genai
from google.genai import types  
from prompts import SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE
# Step-2
MODEL_NAME = "gemini-3.5-flash"

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]


@st.cache_resource
def get_gemini_client(): 
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()
#  Step-3

# Step 5: Onboarding screen

if "onboarded" not in st.session_state:
    st.title("🥗 MacroSnap")
    st.caption("Snap it. Track it. Text yourself the results.")

    with st.form("onboarding_form"):
        name = st.text_input("Your name")

        whatsapp_number = st.text_input(
            "WhatsApp number (with country code)",
            placeholder="+91XXXXXXXXXX",
        )

        submitted = st.form_submit_button("Let's go 🚀")

    if submitted:
        if not name.strip() or not whatsapp_number.strip():
            st.warning("Please fill in both your name and WhatsApp number.")
        else:
            st.session_state.name = name.strip()
            st.session_state.whatsapp_number = whatsapp_number.strip()

            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT
                ),
            )

            st.session_state.messages = []
            st.session_state.onboarded = True
            st.rerun()

    st.stop()


# Step 6: Chat interface

def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append({
        "role": role,
        "kind": kind,
        "content": content
    })
    render_message(st.session_state.messages[-1])


st.title("🥗 MacroSnap")

st.caption(
    f"Logged in as {st.session_state.name} "
    f"- updates go to {st.session_state.whatsapp_number}"
)

if not st.session_state.messages:
    add_message(
        "assistant",
        "text",
        WELCOME_MESSAGE_TEMPLATE.format(
            name=st.session_state.name
        )
    )
else:
    for message in st.session_state.messages:
        render_message(message)


# Step 7.1: Send input to Gemini

def ask_gemini(parts):
    try:
        return st.session_state.chat.send_message(parts).text
    except Exception as error:
        return f"Sorry, something went wrong: {error}"


# Step 7.2: User text and photo input

user_input = st.chat_input(
    "Ask a question, or attach a photo of your meal",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
) 


# Step 7.3: Process user input

if user_input:
    photo = user_input.files[0] if user_input.files else None
    text = user_input.text
    parts = []

    if photo is not None:
        photo_bytes = photo.getvalue()

        add_message("user", "image", photo_bytes)

        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type
            )
        )

    if text:
        add_message("user", "text", text)
        parts.append(text)
    elif photo is not None:
        parts.append(
            "What is this meal? Give me the calories and macros."
        )

    with st.spinner("Crunching the numbers..."):
        answer = ask_gemini(parts)

    add_message("assistant", "text", answer)


# -------------------------------
# SEND DETAILS TO WHATSAPP
# -------------------------------

st.divider()
st.subheader("📲 WhatsApp")

if st.button("Send details to WhatsApp", use_container_width=True):

    # Get the user's name and WhatsApp number
    name = (
        st.session_state.get("name")
        or st.session_state.get("user_name")
        or st.session_state.get("username")
    )

    phone = (
        st.session_state.get("whatsapp_number")
        or st.session_state.get("phone_number")
        or st.session_state.get("phone")
    )

    # Get chat history
    messages = st.session_state.get("messages", [])

    # Build a text summary from the chat
    chat_lines = []

    for message in messages:
        if isinstance(message, dict):
            role = message.get("role", "")
            content = message.get("content", "")

            if isinstance(content, str) and content.strip():
                if role in ("user", "assistant"):
                    speaker = "You" if role == "user" else "MacroSnap"
                    chat_lines.append(f"{speaker}: {content}")

    summary = "\n".join(chat_lines[-10:])

    if not name or not phone:
        st.error(
            "Name or WhatsApp number is missing. "
            "Please check your onboarding code."
        )

    elif not summary:
        st.warning("There is no chat summary to send yet.")

    else:
        try:
            # Read Twilio credentials
            account_sid = st.secrets["TWILIO_ACCOUNT_SID"]
            auth_token = st.secrets["TWILIO_AUTH_TOKEN"]
            whatsapp_from = st.secrets["TWILIO_WHATSAPP_FROM"]
            content_sid = st.secrets["TWILIO_CONTENT_SID"]

            # Format the recipient number
            phone = str(phone).strip()

            if not phone.startswith("whatsapp:"):
                phone = f"whatsapp:{phone}"

            # Connect to Twilio
            client = Client(account_sid, auth_token)

            # Send the WhatsApp template message
            message = client.messages.create(
                from_=whatsapp_from,
                to=phone,
                content_sid=content_sid,
                content_variables=json.dumps({
                    "1": str(name),
                    "2": summary[:1000]
                })
            )

            st.success("WhatsApp message sent successfully!")
            st.write("Message ID:", message.sid)

        except Exception as e:
            st.error("Unable to send the WhatsApp message.")
            st.code(str(e))
from dotenv import load_dotenv
import os
import gradio as gr
import sqlite3
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")

DB_NAME = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(""" 
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                thread_id INTEGER,
                ROLE TEXT,
                content TEXT
            )
    """)
    conn.commit()
    conn.close()

def save_message(thread_id , role , content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (thread_id , role , content) VALUES (?, ? , ?)",
        (thread_id , role , content)
    )
    conn.commit()
    conn.close()

def load_threads():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "SELECT DISTINCT thread_id FROM messages ORDER BY thread_id"
    )
    thread_ids = [row[0] for row in c.fetchall()]
    threads = []
    
    for tid in thread_ids:
        c.execute("SELECT role , content FROM messages WHERE thread_id = ? ORDER BY id"  , (tid ,))
        messages = [{"role":role , "content" : content} for role , content in c.fetchall()]
        threads.append({"thread_id" : tid , "messages" : messages})
    
    conn.commit()
    conn.close()
    return threads


def get_next_thread():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT MAX(thread_id) FROM messages")
    result = c.fetchone()
    max_id = result[0] if result[0] else 0
    conn.close()
    return max_id + 1


def chatbot(user_input , history , thread_id):
    prompt_history = ""
    if history :
        for msg in history:
            if msg["role"] == "user":
                prompt_history += f"User: {msg["content"]}\n"
            elif msg["role"] == "assistant":
                prompt_history += f"Assistant: {msg["content"]}\n"
    prompt_history += f"User: {user_input}\nAssistant:"

    try:
        response = model.generate_content(prompt_history)
        bot_response = response.text.strip()
        if not bot_response:
            bot_response = "Hmm , I couldn't come up with a response. Could you please rephrases your question?"
    except Exception as e:
        bot_response = F"Sorry ,something went wrong: {e}"
    
    save_message(thread_id , "user" , user_input)
    save_message(thread_id , "assistant" , bot_response)
    
    history.append({"role" : "assistant" , "content" : bot_response})  
    return bot_response , history

def format_chat_history(threads):
    if not threads:
        return "No conversation here"
    
    formatted = ""
    for idx, thread in enumerate(threads, 1):
        thread_content = ""
        for msg in thread['messages']:
            role = msg['role'].capitalize()
            thread_content += f"**{role}:** {msg['content']}\n\n"
        
        formatted += f"<details><summary><strong>Thread {idx}</strong></summary>\n{thread_content}</details>\n\n"
    
    return formatted


def reset_chat() :
    new_thread_id = get_next_thread()
    return [],"No conversation yet." , new_thread_id

init_db()    

with gr.Blocks() as demo:
    gr.Markdown(
        """
        <style>
            #new-chat-btn{
                position:absolute;
                top : 10px;
                right : 10px;
                z-index:1000;
                background-color:#0d6efd;
                color : white;
                padding : 8px 12px;
                border-radius : 6px;
                cursor:pointer;
                font-weight : bold;
            }
            #new-chat-btn:hover{
                background-color : #0b5ed7;
            }
        </style>
        """
    )
    
    gr.Markdown("# Gemini 2.0 Chatbot")
    new_chat_btn = gr.Button("🆕New Chat" , elem_id="new-chat-btn")
    
    with gr.Row():
        with gr.Column(scale = 3):
            chat = gr.Chatbot()
            user_input = gr.Textbox(label="Your message" , placeholder="Type here and press Send")
            submit_button = gr.Button("Send")
        with gr.Column(scale = 1):
            gr.Markdown("### Chat History")
            history_box = gr.Markdown("No conversation yet." , elem_id="history-box")
    history_state = gr.State([])
    thread_id_state = gr.State(get_next_thread())

    def respond(user_input , history , thread_id):
        history.append({"role":"user","content":user_input})
        bot_response , updated_history = chatbot(user_input , history , thread_id)
        chat_history = [(msg["content"],None) if msg["role"] == "user" else (None , msg["content"]) for msg in updated_history]
        threads = load_threads()
        sidebar_md = format_chat_history(threads)
        return chat_history , updated_history , sidebar_md , ""

    submit_button.click(
        respond , 
        inputs=[user_input,history_state,thread_id_state],
        outputs=[chat , history_state , history_box , user_input]
    )
        
    new_chat_btn.click(
        fn=reset_chat,
        outputs=[history_state , history_box , thread_id_state]
    )

    def load_sidebar_history():
        threads = load_threads()
        sidebar_md = format_chat_history(threads)
        return sidebar_md
    
    demo.load(
        fn=load_sidebar_history,
        outputs=[history_box]
    )
    

if __name__ == "__main__":
    demo.launch(share=True)
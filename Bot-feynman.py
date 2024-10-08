from typing import Sequence
from langchain_openai import OpenAIEmbeddings
import openai
from pydantic import BaseModel, Field
import bs4
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.document_loaders import WebBaseLoader
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.vectorstores import InMemoryVectorStore
from pinecone import Pinecone
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from dotenv import load_dotenv
import os
os.environ['USER_AGENT'] = 'FeynmanRagBot/1.0'
from langchain_community.embeddings import LlamaCppEmbeddings
from langchain_community.vectorstores import Pinecone as LangchainPinecone
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import pika


load_dotenv()
# Constants
PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
PINECONE_ENV = os.getenv('PINECONE_ENVIRONMENT')
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') 
EMBD_MODEL_PATH = r'E://AletheIA//proyectos//embeddings//nomic-embed-text-v1.5.Q4_K_S.gguf'


llm = ChatGroq(model="llama-3.1-70b-versatile", temperature=0, api_key=GROQ_API_KEY)
#embedding = LlamaCppEmbeddings(model_path=EMBD_MODEL_PATH, n_batch=512)

# Set OpenAI API key
openai.api_key = OPENAI_API_KEY

# Initialize OpenAIEmbeddings with the specific model
embeddingOpenIA = OpenAIEmbeddings(
    model="text-embedding-3-small",
    openai_api_key=OPENAI_API_KEY
)
# Initialize Pinecone and LLM
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
index_name = os.getenv('PINECONE_INDEX_NAME', 'feynman-rag1536')
index = pc.Index(index_name)


### Construct retriever ###
try:
    loader = WebBaseLoader(
        web_paths=("https://lilianweng.github.io/posts/2023-06-23-agent/",),
        bs_kwargs=dict(
            parse_only=bs4.SoupStrainer(
                class_=("post-content", "post-title", "post-header")
            )
        ),
    )
    docs = loader.load()
except Exception as e:
    print(f"Error loading web content: {e}")
    docs = []  # Initialize with empty list if loading fails

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
splits = text_splitter.split_documents(docs)

# Create Pinecone vectorstore

vectorstore = LangchainPinecone.from_documents(splits, embeddingOpenIA, index_name=index_name)

# Create retriever
retriever = vectorstore.as_retriever()

### Contextualize question ###
contextualize_q_system_prompt = (
    "Given a chat history and the latest user question, follow these steps:\n"
    "1. Perform retrieval using ONLY the user's latest question. Do not extract or use any additional context.\n"
    "2. If the retrieval yields relevant results, proceed to step 4.\n"
    "3. If the retrieval yields no results or irrelevant information, reformulate the question:\n"
    "   a. Analyze the chat history and the latest question.\n"
    "   b. Identify any references to previous context.\n"
    "   c. Create a standalone question that incorporates necessary context.\n"
    "   d. Ensure the reformulated question can be understood without the chat history.\n"
    "4. Output either the original question (if retrieval was successful) or the reformulated question (if needed).\n"
    "5. Do NOT answer the question or provide any additional information.\n"
    "6. Return only the question itself, either reformulated or as originally stated.\n\n"
    "Remember: Your task is to contextualize and potentially reformulate the question, not to answer it."
)
contextualize_q_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", contextualize_q_system_prompt),
        ("human", "{input}"),
    ]
)
history_aware_retriever = create_history_aware_retriever(
    llm, retriever, contextualize_q_prompt
)

### Answer question ###
system_prompt = (
    "You are the Feynman Graph AI assistant, designed to answer questions specifically about the Feynman Graph project. "
    "Adhere strictly to the following guidelines:\n\n"
    "1. Use ONLY the information provided in the context to answer questions, with one exception noted in point 11.\n"
    "2. Answer ONLY if the information is explicitly stated in the context.\n"
    "3. Provide concise, clear, and scientifically accurate responses.\n"
    "4. If the context lacks relevant information, respond ONLY with: 'Insufficient information to answer this question about Feynman Graph.'\n"
    "5. Do not infer, assume, or add any information not present in the context.\n"
    "6. Use a scientific and collaborative tone.\n"
    "7. Limit responses to three sentences maximum.\n"
    "8. If asked about topics unrelated to Feynman Graph, respond with: 'I can only provide information about the Feynman Graph project.'\n"
    "9. EXCEPTION: If the user greets you or asks about the project in a general way, respond in a friendly manner without relying on the context. "
    "For example: 'Hello! I'm the Feynman Graph AI assistant. I'm here to help you with any questions about the Feynman Graph project. How can I assist you today?'\n"
    "10. ALWAYS respond in SPANISH.\n"
    "11. EXCEPTION: If the user initiates a conversation informally or in a friendly manner, you may suggest questions that naturally guide the conversation towards the Feynman Graph project. For example: 'Would you like to know more about the objectives of the project or how experiments are conducted in Feynman Graph?'\n"
    "12. Do not mention at any point that the information has been extracted from any source or automated extraction process.\n\n"
    "Context:\n{context}\n\n"
    "Remember: You are an AI assistant for the Feynman Graph project. Stay focused on this topic and follow these guidelines carefully."
)
qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ]
)
question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)


### Statefully manage chat history ###


# We define a dict representing the state of the application.
# This state has the same input and output keys as `rag_chain`.
class State(TypedDict):
    input: str
    chat_history: Annotated[Sequence[BaseMessage], add_messages]
    context: str
    answer: str


# We then define a simple node that runs the `rag_chain`.
# The `return` values of the node update the graph state, so here we just
# update the chat history with the input message and response.
def call_model(state: State):
    response = rag_chain.invoke(state)
    return {
        "chat_history": [
            HumanMessage(state["input"]),
            AIMessage(response["answer"]),
        ],
        "context": response["context"],
        "answer": response["answer"],
    }


# Our graph consists only of one node:
workflow = StateGraph(state_schema=State)
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)





# Finally, we compile the graph with a checkpointer object.
# This persists the state, in this case in memory.
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

import pika
import json
import warnings

warnings.filterwarnings('ignore')

def process_chat_message(user_input, chat_history, user_id):
    # Esta función invoca la lógica del chatbot
    config = {"configurable": {"thread_id": user_id}}

    result = app.invoke(
        {
            "input": user_input,
            "chat_history": chat_history
        },
        config=config,
    )

    answer = result["answer"]
    return answer

def on_message(ch, method, properties, body):
    message = json.loads(body.decode())
    print(f"[x] Received from {method.routing_key}: {message}")
    captured_messages.append(message)

    user_id = message["number"]
    user_message = message["userMessage"]

    # Procesar el mensaje usando la función process_chat_message
    chat_history = []  # Ajusta según sea necesario
    response = process_chat_message(user_message, chat_history, user_id)

    # Enviar la respuesta a la cola chatbot_queue_regreso
    response_message = {
        "number": user_id,
        "response": response
    }
    send_response(json.dumps(response_message))

def send_response(response):
    try:
        # Conexión con RabbitMQ con credenciales guest y host localhost
        credentials = pika.PlainCredentials('guest', 'guest')
        connection_params = pika.ConnectionParameters('localhost', 5672, '/', credentials)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()

        # Declarar la cola de regreso
        channel.queue_declare(queue='chatbot_queue_regreso', durable=True)
        channel.basic_publish(
            exchange='',
            routing_key='chatbot_queue_regreso',
            body=response,
            properties=pika.BasicProperties(
                delivery_mode=2,  # hacer el mensaje persistente
            )
        )
        print(f"[x] Sent response to chatbot_queue_regreso: {response}")
    except Exception as e:
        print(f"Error al enviar la respuesta: {str(e)}")
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()

def main():
    try:
        # Conexión con RabbitMQ con credenciales guest y host localhost
        credentials = pika.PlainCredentials('guest', 'guest')
        connection_params = pika.ConnectionParameters('localhost', 5672, '/', credentials)
        connection = pika.BlockingConnection(connection_params)
        channel = connection.channel()

        # Declarar la cola chatbot_queue_Feynman sin cambiar la durabilidad si ya existe
        channel.queue_declare(queue='chatbot_queue_Feynman', durable=False, passive=True)
        channel.basic_consume(queue='chatbot_queue_Feynman', on_message_callback=on_message, auto_ack=True)
        print(f"[*] Waiting for messages in chatbot_queue_Feynman. To exit press CTRL+C")

        # Iniciar el consumo de mensajes
        channel.start_consuming()
    except Exception as e:
        print(f"Error en la conexión principal: {str(e)}")
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()

if __name__ == "__main__":
    captured_messages = []
    main()
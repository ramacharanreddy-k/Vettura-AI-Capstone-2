import json
import os
import logging
from pathlib import Path
import torch
from PIL import Image
from dotenv import load_dotenv
from transformers import CLIPProcessor, CLIPModel
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain.chains import (
    create_history_aware_retriever,
    create_retrieval_chain,
)
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.schema import Document
from langchain_core.messages import HumanMessage, AIMessage  # Add this import
import streamlit as st

# Disable Streamlit's file watcher
os.environ["STREAMLIT_SERVER_FILE_WATCHER_TYPE"] = "none"

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RenesasRAG:
    def __init__(self, data_file='data.json', base_dir='block_diagrams'):
        self.base_dir = Path(base_dir).resolve()
        self.data = self.load_data(data_file)
        self.clip_model, self.clip_processor = self.load_clip_model()
        self.documents, self.embeddings_list = self.prepare_documents()
        self.vectorstore = self.create_vectorstore()
        self.qa_chain = self.create_qa_chain()

    def load_data(self, data_file):
        try:
            with open(data_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading data file: {e}")
            return {}

    def load_clip_model(self):
        try:
            model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            return model, processor
        except Exception as e:
            logger.error(f"Error loading CLIP model: {e}")
            return None, None

    def generate_image_embedding(self, image_path):
        try:
            image = Image.open(image_path)
            inputs = self.clip_processor(images=image, return_tensors="pt", padding=True)
            with torch.no_grad():
                image_features = self.clip_model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)  # Normalize
            return image_features.squeeze().numpy()
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            return None

    def prepare_documents(self):
        documents = []
        embeddings_list = []
        for category, subcategories in self.data.items():
            for subcategory, applications in subcategories.items():
                for app_name, app_data in applications.items():
                    overview = app_data.get('block_diagram', {}).get('overview', 'No overview available.')
                    block_diagram_path = app_data.get('block_diagram', {}).get('block_diagram')
                    if not block_diagram_path:
                        logger.error(f"Block diagram path missing for {app_name}")
                        continue

                    content = f"Category: {category}\nSubcategory: {subcategory}\nApplication: {app_name}\n\n"
                    content += f"Overview: {overview}\n\n"

                    raw_image_path = Path(block_diagram_path)
                    image_path = self.base_dir / raw_image_path.relative_to(raw_image_path.parts[0])

                    logger.info(f"Trying to open image: {image_path}")

                    if not image_path.exists():
                        logger.error(f"ERROR: Image not found at {image_path}")
                        continue

                    image_embedding = self.generate_image_embedding(image_path)
                    if image_embedding is None:
                        continue

                    metadata = {
                        "source": app_name,
                        "image_path": str(image_path)
                    }

                    doc = Document(page_content=content, metadata=metadata)
                    documents.append(doc)
                    embeddings_list.append(image_embedding.tolist())

        return documents, embeddings_list

    def create_vectorstore(self):
        persist_dir = "vectorstore_db"
        if os.path.exists(persist_dir):
            logger.info("Loading existing vectorstore from disk.")
            return Chroma(persist_directory=persist_dir, embedding_function=OpenAIEmbeddings())
        else:
            logger.info("Creating new vectorstore.")
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
            split_docs = text_splitter.split_documents(self.documents)
            vectorstore = Chroma.from_documents(split_docs, OpenAIEmbeddings(), persist_directory=persist_dir)
            return vectorstore

    def create_qa_chain(self):
        llm = ChatOpenAI(openai_api_key=OPENAI_API_KEY, temperature=0)
        retriever = self.vectorstore.as_retriever(search_kwargs={"k": 3})

        # Define the prompt template for the history-aware retriever
        retriever_prompt = ChatPromptTemplate.from_messages([
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}")
        ])

        history_aware_retriever = create_history_aware_retriever(
            llm=llm,
            retriever=retriever,
            prompt=retriever_prompt
        )

        # Define the prompt template for the question-answering chain
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", "Answer the user's questions based on the context below. If you don't know the answer, say you don't know.\n\n{context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("user", "{input}")
        ])

        question_answer_chain = create_stuff_documents_chain(
            llm=llm,
            prompt=qa_prompt
        )

        return create_retrieval_chain(history_aware_retriever, question_answer_chain)

    def get_response(self, query, chat_history):
        result = self.qa_chain.invoke({"input": query, "chat_history": chat_history})
        return result['answer'], self.find_relevant_image(query)

    def find_relevant_image(self, query):
        query_embedding = self.clip_processor(text=[query], return_tensors="pt", padding=True)
        with torch.no_grad():
            text_features = self.clip_model.get_text_features(**query_embedding)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)  # Normalize

        best_similarity = -1
        best_image_path = None

        for doc, embedding in zip(self.documents, self.embeddings_list):
            image_embedding = torch.tensor(embedding)
            image_embedding = image_embedding / image_embedding.norm(dim=-1, keepdim=True)  # Normalize
            similarity = torch.cosine_similarity(text_features.squeeze(), image_embedding, dim=0)
            if similarity > best_similarity:
                best_similarity = similarity
                best_image_path = doc.metadata['image_path']

        return best_image_path

# Streamlit App
def main():
    st.title("Renesas RAG System")
    st.write("Ask questions about Renesas applications and get relevant answers and images.")

    # Initialize the RAG system
    if "rag" not in st.session_state:
        st.session_state.rag = RenesasRAG()

    # Initialize chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Input for user query
    query = st.text_input("Enter your question:")

    # Submit button
    if st.button("Submit"):
        if query:
            # Get response from RAG system
            response, image_path = st.session_state.rag.get_response(query, st.session_state.chat_history)

            # Update chat history
            st.session_state.chat_history.append(HumanMessage(content=query))  # Add user query
            st.session_state.chat_history.append(AIMessage(content=response))  # Add AI response

            # Display response
            st.write("**Response:**")
            st.write(response)

            # Display relevant image
            if image_path:
                st.write("**Relevant Image:**")
                st.image(image_path, caption="Relevant Image", use_container_width=True)
            else:
                st.write("No relevant image found.")

    # Display chat history
    st.write("**Chat History:**")
    for i, message in enumerate(st.session_state.chat_history):
        if isinstance(message, HumanMessage):
            st.write(f"**Q{i//2 + 1}:** {message.content}")
        elif isinstance(message, AIMessage):
            st.write(f"**A{i//2 + 1}:** {message.content}")
        st.write("---")

if __name__ == "__main__":
    main()
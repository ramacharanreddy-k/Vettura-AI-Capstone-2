# Renesas Applications RAG System

This project implements a Retrieval-Augmented Generation (RAG) system for Renesas applications, combining web scraping capabilities with an intelligent question-answering system. The system processes Renesas application data, stores it efficiently, and provides relevant responses along with associated block diagrams.

## Project Structure

The project consists of several key components:

### 1. Data Collection
- `urlFinder.py`: Crawls Renesas website to collect application URLs
- `webScraper.py`: Scrapes detailed content and block diagrams from application pages
- `jsonGenerator.py`: Generates consolidated JSON data from scraped content

### 2. RAG System
- `app.py`: Main application implementing the RAG system using:
  - LangChain for orchestrating the RAG pipeline
  - CLIP for image embedding and retrieval
  - ChromaDB for vector storage
  - OpenAI's chat models for generation

## Features

- **Smart Retrieval**: Uses semantic search to find relevant documentation based on user queries
- **Visual Context**: Incorporates block diagrams into responses
- **Conversational Interface**: Maintains chat history for contextual responses
- **Efficient Storage**: Utilizes ChromaDB for vector storage and fast retrieval

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd renesas-rag
```

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env file with your OpenAI API key
```

## Usage

### Data Collection

1. Collect application URLs:
```bash
python urlFinder.py
```

2. Scrape application content:
```bash
python webScraper.py
```

3. Generate consolidated data:
```bash
python jsonGenerator.py
```

### Running the RAG System

1. Start the Streamlit application:
```bash
streamlit run app.py
```

2. Access the web interface at `http://localhost:8501`

3. Enter your questions about Renesas applications in the text input field

## System Architecture

```
                                    +----------------+
                                    |  User Query    |
                                    +----------------+
                                           ↓
+----------------+    +-----------+    +-----------+    +----------------+
|   ChromaDB     |←---|  CLIP     |←---|   RAG     |←---|  ChatOpenAI    |
|  Vector Store  |    | Embeddings|    | Pipeline  |    |    Model       |
+----------------+    +-----------+    +-----------+    +----------------+
        ↑                                   ↓
+----------------+                    +-----------+
|  Block Diagrams|                    | Response  |
|  & Content     |                    | Generator |
+----------------+                    +-----------+
```

## Key Components

### Vector Store
- Uses ChromaDB for efficient storage and retrieval of embeddings
- Stores both text and image embeddings for comprehensive search

### Retrieval Chain
- Creates history-aware retrieval for contextual responses
- Implements custom retrieval logic for both text and images

### Response Generation
- Uses ChatOpenAI to generate natural language responses
- Incorporates retrieved context and chat history

## API Reference

### RenesasRAG Class

```python
class RenesasRAG:
    def __init__(self, data_file='data.json', base_dir='block_diagrams')
    def get_response(self, query, chat_history)
```

- `data_file`: Path to consolidated JSON data
- `base_dir`: Directory containing block diagrams
- `get_response`: Returns response and relevant image path

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to Renesas for providing comprehensive application documentation
- Built using OpenAI's powerful language models
- Utilizes the CLIP model for vision-language understanding

## Note

This is a research project and should be used accordingly. Always refer to official Renesas documentation for critical applications.
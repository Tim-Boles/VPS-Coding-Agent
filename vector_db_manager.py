from langchain.document_loaders import DirectoryLoader
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, Docx2txtLoader, CSVLoader
)
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from google.adk.tools import Tool
from pathlib import Path

class LocalVectorSearchTool(Tool):
    name = "local_faiss_search"
    description = "Search locally stored document embeddings."

    def __init__(self, index_path: str):
        self.embeddings = GoogleGenerativeAIEmbeddings(model_name="models/text-embedding-004")
        self.vstore = FAISS.load_local(index_path, self.embeddings)

    def _run(self, query: str, k: int = 4):          # ADK sync tool signature
        docs = self.vstore.similarity_search(query, k=k)
        return [d.page_content for d in docs]
    
class VectorDBLoader():

    def __init__(self, index_path: str):
        self.embeddings = GoogleGenerativeAIEmbeddings(model_name="models/text-embedding-004")
        self.user_path = index_path

    def load_files_into_VDB(self):
        loaders = []
        for path in Path("docs").rglob("*"):
            if path.suffix.lower() == ".pdf":
                loaders.append(PyPDFLoader(str(path)))
            elif path.suffix.lower() in {".md", ".txt"}:
                loaders.append(TextLoader(str(path)))
            elif path.suffix.lower() in {".docx"}:
                loaders.append(Docx2txtLoader(str(path)))
            elif path.suffix.lower() == ".csv":
                loaders.append(CSVLoader(str(path)))
            # add more as you go

        documents = []
        for ld in loaders:
            documents.extend(ld.load())
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", " ", ""]
        )

        chunks = splitter.split_documents(documents)

        embedder = GoogleGenerativeAIEmbeddings(
        model_name="models/text-embedding-004"  
        )

        faiss_store = FAISS.from_documents(chunks, embedder)
        faiss_store.save_local("rag.index")

        
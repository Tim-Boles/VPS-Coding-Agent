from langchain_community.document_loaders import DirectoryLoader # UPDATED import
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, Docx2txtLoader, CSVLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter # UPDATED import
from langchain_community.vectorstores import FAISS # UPDATED import
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from pathlib import Path

class LocalVectorSearchTool():
    name = "local_faiss_search"
    description = (
        "Searches a local FAISS vector store to find and retrieve text segments "
        "that are semantically similar to a given query. Useful for question answering "
        "over a local knowledge base or finding relevant information."
    )

    def __init__(self, index_path: str):
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
        self.vstore = FAISS.load_local(
            folder_path=index_path, 
            embeddings=self.embeddings,
            index_name="index", 
            allow_dangerous_deserialization=True
        )

    def run_vector_search(self, query: str, k: int) -> dict:
        """
        Retrieves the top k text segments from a local FAISS vector store
        that are most semantically similar to the input query.

        Use this tool when you need to find relevant information or answer questions
        based on a pre-existing collection of documents that have been indexed locally.
        For example, if a user asks a question about a specific topic covered in
        your local documents, use this tool to fetch relevant excerpts.

        Args:
            query: The text string to search for. This should be specific enough
                   to find relevant matches in the document embeddings.
            k: The number of most relevant document segments to retrieve. This must
               be a positive integer. Choose a smaller k (e.g., 2-5) for concise
               answers or a larger k if broader context is needed.

        Returns:
            A dictionary containing the outcome of the search operation.
            - On success:
                {'status': 'success', 'retrieved_documents': ['text segment 1', 'text segment 2', ...]}
                The 'retrieved_documents' list contains the page_content of the k most similar
                documents. If no documents are found for a valid query, 'retrieved_documents'
                will be an empty list.
            - On failure (e.g., issue with the vector store or invalid k):
                {'status': 'error', 'error_message': 'Description of the error.'}

            Example success with results:
            {'status': 'success', 'retrieved_documents': ['Photosynthesis is the process...', 'Chlorophyll captures light...']}

            Example success with no results:
            {'status': 'success', 'retrieved_documents': []}

            Example error:
            {'status': 'error', 'error_message': 'Invalid value for k: must be a positive integer.'}
        """
        if not isinstance(k, int) or k <= 0:
            return {
                "status": "error",
                "error_message": f"Invalid value for k: must be a positive integer, but got {k}."
            }

        try:
            docs = self.vstore.similarity_search(query, k=k)
            retrieved_contents = [d.page_content for d in docs]
            return {
                "status": "success",
                "retrieved_documents": retrieved_contents
            }
        except Exception as e:
            # Log the full error for debugging if necessary
            # logger.error(f"Error during FAISS similarity search: {e}", exc_info=True)
            return {
                "status": "error",
                "error_message": f"An error occurred during vector search: {str(e)}"
            }
    
import argparse
import os
from pathlib import Path

# Langchain and document processing imports
try:
    from langchain_community.document_loaders import (
        PyPDFLoader,
        TextLoader,
        Docx2txtLoader,
        CSVLoader,
    )
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    from langchain_community.vectorstores import FAISS
except ImportError:
    print(
        "Required Langchain packages are not installed. "
        "Please install them: pip install langchain langchain-google-genai "
        "langchain-community faiss-cpu pypdf docx2txt tiktoken"
    )
    exit(1)


class VectorDBLoader:
    def __init__(self, embedding_model_name: str = "models/text-embedding-004"):
        """
        Initializes the VectorDBLoader with the specified embedding model.

        Args:
            embedding_model_name (str): The name of the Google Generative AI embedding model.
        """
        try:
            self.embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model_name)
        except Exception as e:
            print(f"Error initializing embeddings (ensure GOOGLE_API_KEY is set): {e}")
            raise
        print(f"Embeddings initialized with model: {embedding_model_name}")

    def load_files_into_VDB(
        self,
        documents_dir: Path,
        output_faiss_dir: Path,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """
        Loads documents from various file types, splits them into chunks,
        embeds them, and saves them into a FAISS vector store.

        Args:
            documents_dir (Path): Directory containing the source documents.
            output_faiss_dir (Path): Directory where the FAISS index will be saved.
            chunk_size (int): Size of text chunks for splitting documents.
            chunk_overlap (int): Overlap between text chunks.
        """
        loaders = []
        print(f"Scanning for documents in: {documents_dir.resolve()}")

        supported_files_found = 0
        for item_path in documents_dir.rglob("*"):
            if item_path.is_file():
                suffix = item_path.suffix.lower()
                if suffix == ".pdf":
                    loaders.append(PyPDFLoader(str(item_path)))
                    supported_files_found += 1
                elif suffix in {".md", ".txt"}:
                    loaders.append(TextLoader(str(item_path)))
                    supported_files_found += 1
                elif suffix == ".docx":
                    loaders.append(Docx2txtLoader(str(item_path)))
                    supported_files_found += 1
                elif suffix == ".csv":
                    loaders.append(CSVLoader(str(item_path)))
                    supported_files_found += 1
        
        if not loaders:
            print(f"No supported document files found in {documents_dir}. Supported types: .pdf, .md, .txt, .docx, .csv")
            return

        print(f"Found {supported_files_found} supported document(s) to load.")

        documents = []
        for ld_idx, ld in enumerate(loaders):
            try:
                print(f"Loading from: {getattr(ld, 'file_path', 'Unknown file')} ({ld_idx+1}/{len(loaders)})")
                documents.extend(ld.load())
            except Exception as e:
                print(f"Warning: Could not load file {getattr(ld, 'file_path', 'Unknown file')}: {e}")
        
        if not documents:
            print("No documents were successfully loaded. Exiting.")
            return

        print(f"Successfully loaded {len(documents)} document sections.")
        print(f"Splitting documents with chunk_size={chunk_size}, chunk_overlap={chunk_overlap}...")
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", " ", ""],
            length_function=len,
        )
        chunks = splitter.split_documents(documents)

        if not chunks:
            print(
                "No documents were processed into chunks. "
                "Please check your document files and types, or splitter configuration."
            )
            return

        print(f"Embedding {len(chunks)} chunks and creating FAISS index...")
        try:
            faiss_store = FAISS.from_documents(chunks, self.embeddings)
        except Exception as e:
            print(f"Error creating FAISS index from documents: {e}")
            print("This might be due to issues with embedding generation (e.g., API key, network) or empty chunks.")
            return

        output_faiss_dir.mkdir(parents=True, exist_ok=True)
        try:
            faiss_store.save_local(folder_path=str(output_faiss_dir))
            print(f"FAISS index successfully saved to: {output_faiss_dir.resolve()}")
        except Exception as e:
            print(f"Error saving FAISS index to {output_faiss_dir.resolve()}: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Load documents into a FAISS vector database."
    )
    parser.add_argument(
        "--docs-dir",
        type=str,
        default="docs",
        help="Directory containing the documents to load (default: 'docs').",
    )
    parser.add_argument(
        "--index-dir",
        type=str,
        default="faiss_index",
        help="Directory where the FAISS index will be saved (default: 'faiss_index').",
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="models/text-embedding-004",
        help="Name of the embedding model to use (default: 'models/text-embedding-004').",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size for splitting documents (default: 1000).",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap for splitting documents (default: 200).",
    )

    args = parser.parse_args()

    # It's crucial that GOOGLE_API_KEY is set in your environment
    if not os.getenv("GOOGLE_API_KEY"):
        print("Error: The GOOGLE_API_KEY environment variable is not set.")
        print("Please set it before running the script.")
        # return # Exit if API key is not set, or let the embedding initialization fail

    docs_path = Path(args.docs_dir)
    index_save_path = Path(args.index_dir)

    if not docs_path.is_dir():
        print(f"Error: Documents directory not found: {docs_path.resolve()}")
        return

    try:
        loader_instance = VectorDBLoader(embedding_model_name=args.embedding_model)
        loader_instance.load_files_into_VDB(
            documents_dir=docs_path,
            output_faiss_dir=index_save_path,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
        print("Processing completed.")
    except Exception as e:
        print(f"An unexpected error occurred during the process: {e}")


if __name__ == "__main__":
    main()
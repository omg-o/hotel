"""
Document processing service for PDF extraction and indexing
"""

import os
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    PyPDF2 = None
import uuid
from typing import List, Dict, Optional, Tuple
from werkzeug.utils import secure_filename
from app import db
from app.models.document import Document, DocumentChunk
import json

try:
    from sentence_transformers import SentenceTransformer
    import faiss
    import numpy as np
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None
    faiss = None
    np = None

class DocumentService:
    def __init__(self):
        self.upload_folder = os.path.join(os.getcwd(), 'uploads', 'documents')
        self.allowed_extensions = {'pdf', 'txt', 'doc', 'docx'}
        self.chunk_size = 1000
        self.chunk_overlap = 200
        
        # Create upload directory
        os.makedirs(self.upload_folder, exist_ok=True)
        
        # Initialize embedding model if available
        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
                self.dimension = 384  # Dimension of all-MiniLM-L6-v2
                self.embeddings_available = True
            except Exception:
                self.embedding_model = None
                self.embeddings_available = False
        else:
            self.embedding_model = None
            self.embeddings_available = False
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def extract_text_from_pdf(self, file_path: str) -> Tuple[str, List[Dict]]:
        """Extract text from PDF file"""
        if not PDF_AVAILABLE:
            raise Exception("PyPDF2 not available. Please install with: pip install PyPDF2")
        
        try:
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text_content = ""
                pages_info = []
                
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text_content += page_text + "\n"
                    pages_info.append({
                        'page_number': page_num + 1,
                        'text': page_text,
                        'char_start': len(text_content) - len(page_text) - 1,
                        'char_end': len(text_content) - 1
                    })
                
                return text_content, pages_info
        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
    
    def chunk_text(self, text: str, pages_info: List[Dict]) -> List[Dict]:
        """Split text into chunks for better processing"""
        chunks = []
        words = text.split()
        
        current_chunk = []
        current_length = 0
        chunk_index = 0
        
        for word in words:
            if current_length + len(word) + 1 > self.chunk_size and current_chunk:
                # Create chunk
                chunk_text = ' '.join(current_chunk)
                chunk_start = text.find(chunk_text)
                chunk_end = chunk_start + len(chunk_text)
                
                # Find page number for this chunk
                page_number = 1
                for page_info in pages_info:
                    if chunk_start >= page_info['char_start'] and chunk_start <= page_info['char_end']:
                        page_number = page_info['page_number']
                        break
                
                chunks.append({
                    'index': chunk_index,
                    'content': chunk_text,
                    'start_char': chunk_start,
                    'end_char': chunk_end,
                    'page_number': page_number
                })
                
                # Start new chunk with overlap
                overlap_words = current_chunk[-self.chunk_overlap//10:] if len(current_chunk) > self.chunk_overlap//10 else []
                current_chunk = overlap_words + [word]
                current_length = sum(len(w) + 1 for w in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(word)
                current_length += len(word) + 1
        
        # Add final chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk_start = text.find(chunk_text)
            chunk_end = chunk_start + len(chunk_text)
            
            page_number = 1
            for page_info in pages_info:
                if chunk_start >= page_info['char_start'] and chunk_start <= page_info['char_end']:
                    page_number = page_info['page_number']
                    break
            
            chunks.append({
                'index': chunk_index,
                'content': chunk_text,
                'start_char': chunk_start,
                'end_char': chunk_end,
                'page_number': page_number
            })
        
        return chunks
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks"""
        if not self.embedding_model:
            return [[] for _ in texts]
        
        try:
            embeddings = self.embedding_model.encode(texts)
            return embeddings.tolist()
        except Exception:
            return [[] for _ in texts]
    
    def upload_document(self, file, category: str = 'policy', title: str = '', 
                       description: str = '', uploaded_by: str = 'admin') -> Document:
        """Upload and process a document"""
        if not file or not self.allowed_file(file.filename):
            raise ValueError("Invalid file type")
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[1].lower()
        new_filename = f"{file_id}.{file_extension}"
        file_path = os.path.join(self.upload_folder, new_filename)
        
        # Save file
        file.save(file_path)
        file_size = os.path.getsize(file_path)
        
        # Create document record
        document = Document(
            filename=new_filename,
            original_filename=filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=file.content_type,
            category=category,
            title=title or filename,
            description=description,
            uploaded_by=uploaded_by
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Process document asynchronously
        try:
            self.process_document(document.id)
        except Exception as e:
            print(f"Error processing document: {e}")
        
        return document
    
    def process_document(self, document_id: str) -> bool:
        """Process document: extract text, create chunks, generate embeddings"""
        document = Document.query.get(document_id)
        if not document:
            return False
        
        try:
            # Extract text from PDF
            if document.file_path.endswith('.pdf'):
                text_content, pages_info = self.extract_text_from_pdf(document.file_path)
            else:
                # For other file types, read as text
                with open(document.file_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                pages_info = [{'page_number': 1, 'char_start': 0, 'char_end': len(text_content)}]
            
            # Update document with extracted text
            document.content_text = text_content
            
            # Create chunks
            chunks_data = self.chunk_text(text_content, pages_info)
            
            # Generate embeddings
            chunk_texts = [chunk['content'] for chunk in chunks_data]
            embeddings = self.generate_embeddings(chunk_texts)
            
            # Save chunks to database
            for i, chunk_data in enumerate(chunks_data):
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_data['index'],
                    content=chunk_data['content'],
                    page_number=chunk_data['page_number'],
                    start_char=chunk_data['start_char'],
                    end_char=chunk_data['end_char'],
                    embedding=embeddings[i] if embeddings[i] else None
                )
                db.session.add(chunk)
            
            document.is_indexed = True
            db.session.commit()
            return True
            
        except Exception as e:
            print(f"Error processing document {document_id}: {e}")
            return False
    
    def search_documents(self, query: str, category: str = None, limit: int = 5) -> List[Dict]:
        """Search documents using semantic similarity"""
        if not query.strip():
            return []
        
        # Get query embedding
        query_embedding = None
        if self.embedding_model:
            try:
                query_embedding = self.embedding_model.encode([query])[0].tolist()
            except Exception:
                pass
        
        # Build base query
        chunks_query = DocumentChunk.query.join(Document)
        
        if category:
            chunks_query = chunks_query.filter(Document.category == category)
        
        chunks_query = chunks_query.filter(Document.is_active == True)
        
        # If we have embeddings, use semantic search
        if query_embedding and EMBEDDINGS_AVAILABLE:
            # Get all chunks with embeddings
            chunks = chunks_query.filter(DocumentChunk.embedding.isnot(None)).all()
            
            if chunks:
                # Calculate similarities
                similarities = []
                for chunk in chunks:
                    if chunk.embedding:
                        try:
                            chunk_embedding = np.array(chunk.embedding)
                            query_vec = np.array(query_embedding)
                            similarity = np.dot(chunk_embedding, query_vec) / (
                                np.linalg.norm(chunk_embedding) * np.linalg.norm(query_vec)
                            )
                            similarities.append((chunk, similarity))
                        except Exception:
                            similarities.append((chunk, 0))
                
                # Sort by similarity and return top results
                similarities.sort(key=lambda x: x[1], reverse=True)
                results = []
                
                for chunk, score in similarities[:limit]:
                    results.append({
                        'chunk': chunk.to_dict(),
                        'document': chunk.document.to_dict(),
                        'similarity_score': float(score),
                        'content': chunk.content
                    })
                
                return results
        
        # Fallback to text search
        chunks = chunks_query.filter(
            DocumentChunk.content.contains(query)
        ).limit(limit).all()
        
        results = []
        for chunk in chunks:
            results.append({
                'chunk': chunk.to_dict(),
                'document': chunk.document.to_dict(),
                'similarity_score': 0.5,  # Default score for text search
                'content': chunk.content
            })
        
        return results
    
    def get_document_content(self, document_id: str) -> Optional[str]:
        """Get full content of a document"""
        document = Document.query.get(document_id)
        return document.content_text if document else None
    
    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks"""
        document = Document.query.get(document_id)
        if not document:
            return False
        
        try:
            # Delete file
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
            
            # Delete from database (chunks will be deleted due to cascade)
            db.session.delete(document)
            db.session.commit()
            return True
        except Exception:
            return False

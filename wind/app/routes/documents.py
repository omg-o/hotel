"""
Document management routes for admin interface
"""

from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
from app import db
from app.models.document import Document, DocumentChunk, GuestRequest
from app.services.document_service import DocumentService
import os

documents_bp = Blueprint('documents', __name__)
document_service = DocumentService()

@documents_bp.route('/admin/documents')
def admin_documents():
    """Admin document management interface"""
    documents = Document.query.filter_by(is_active=True).order_by(Document.upload_date.desc()).all()
    return render_template('admin/documents.html', documents=documents)

@documents_bp.route('/admin/documents/upload', methods=['GET', 'POST'])
def upload_document():
    """Upload new document"""
    if request.method == 'POST':
        try:
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            if file and document_service.allowed_file(file.filename):
                category = request.form.get('category', 'policy')
                title = request.form.get('title', '')
                description = request.form.get('description', '')
                uploaded_by = request.form.get('uploaded_by', 'admin')
                
                document = document_service.upload_document(
                    file=file,
                    category=category,
                    title=title,
                    description=description,
                    uploaded_by=uploaded_by
                )
                
                flash(f'Document "{document.title}" uploaded successfully!', 'success')
                return redirect(url_for('documents.admin_documents'))
            else:
                flash('Invalid file type. Please upload PDF, TXT, DOC, or DOCX files.', 'error')
        
        except Exception as e:
            flash(f'Error uploading document: {str(e)}', 'error')
    
    return render_template('admin/upload_document.html')

@documents_bp.route('/admin/documents/<document_id>')
def view_document(document_id):
    """View document details and chunks"""
    document = Document.query.get_or_404(document_id)
    chunks = DocumentChunk.query.filter_by(document_id=document_id).order_by(DocumentChunk.chunk_index).all()
    return render_template('admin/document_detail.html', document=document, chunks=chunks)

@documents_bp.route('/admin/documents/<document_id>/delete', methods=['POST'])
def delete_document(document_id):
    """Delete document"""
    try:
        success = document_service.delete_document(document_id)
        if success:
            flash('Document deleted successfully!', 'success')
        else:
            flash('Error deleting document', 'error')
    except Exception as e:
        flash(f'Error deleting document: {str(e)}', 'error')
    
    return redirect(url_for('documents.admin_documents'))

@documents_bp.route('/admin/documents/<document_id>/reprocess', methods=['POST'])
def reprocess_document(document_id):
    """Reprocess document for indexing"""
    try:
        success = document_service.process_document(document_id)
        if success:
            flash('Document reprocessed successfully!', 'success')
        else:
            flash('Error reprocessing document', 'error')
    except Exception as e:
        flash(f'Error reprocessing document: {str(e)}', 'error')
    
    return redirect(url_for('documents.view_document', document_id=document_id))

@documents_bp.route('/api/documents/search')
def search_documents():
    """API endpoint for document search"""
    query = request.args.get('q', '')
    category = request.args.get('category', '')
    limit = int(request.args.get('limit', 5))
    
    if not query:
        return jsonify({'results': []})
    
    try:
        results = document_service.search_documents(
            query=query,
            category=category if category else None,
            limit=limit
        )
        
        return jsonify({
            'results': results,
            'query': query,
            'total': len(results)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@documents_bp.route('/admin/requests')
def admin_requests():
    """Admin interface for guest requests"""
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', 'all')
    
    query = GuestRequest.query
    
    if status_filter != 'all':
        query = query.filter(GuestRequest.status == status_filter)
    
    if priority_filter != 'all':
        query = query.filter(GuestRequest.priority == priority_filter)
    
    requests = query.order_by(GuestRequest.created_at.desc()).all()
    
    return render_template('admin/requests.html', 
                         requests=requests,
                         status_filter=status_filter,
                         priority_filter=priority_filter)

@documents_bp.route('/admin/requests/<request_id>/update', methods=['POST'])
def update_request(request_id):
    """Update guest request status"""
    guest_request = GuestRequest.query.get_or_404(request_id)
    
    try:
        guest_request.status = request.form.get('status', guest_request.status)
        guest_request.priority = request.form.get('priority', guest_request.priority)
        guest_request.assigned_to = request.form.get('assigned_to', guest_request.assigned_to)
        guest_request.notes = request.form.get('notes', guest_request.notes)
        
        if guest_request.status == 'completed' and not guest_request.completed_time:
            from datetime import datetime
            guest_request.completed_time = datetime.utcnow()
        
        db.session.commit()
        flash('Request updated successfully!', 'success')
    
    except Exception as e:
        flash(f'Error updating request: {str(e)}', 'error')
    
    return redirect(url_for('documents.admin_requests'))

@documents_bp.route('/api/requests/<request_id>/status', methods=['PUT'])
def update_request_status(request_id):
    """API endpoint to update request status"""
    guest_request = GuestRequest.query.get_or_404(request_id)
    
    try:
        data = request.get_json()
        guest_request.status = data.get('status', guest_request.status)
        guest_request.assigned_to = data.get('assigned_to', guest_request.assigned_to)
        guest_request.notes = data.get('notes', guest_request.notes)
        
        if guest_request.status == 'completed' and not guest_request.completed_time:
            from datetime import datetime
            guest_request.completed_time = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'request': guest_request.to_dict()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

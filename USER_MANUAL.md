# Plagiarism Checker Pro - User Manual

## Overview
Plagiarism Checker Pro is a web-based application that detects plagiarism in documents and provides AI-powered rephrasing to help users create original content. The tool supports PDF and DOCX file formats and can process documents of 10,000+ words.

## Features

### Core Capabilities
- **Batch Upload**: Upload 3-5 documents simultaneously in a single session
- **Sentence-Level Analysis**: Every sentence is compared against public web and academic indexes
- **Color-Coded Highlights**: Plagiarized sentences are highlighted in color for easy identification
- **AI Rephrasing**: Generate high-quality rephrased versions that preserve the author's intent
- **Accept/Reject Workflow**: Review and accept or reject each auto-generated rewrite
- **DOCX Export**: Download the fully updated document as a single DOCX file

### User Interface
- **Drag-and-Drop Upload Area**: Simply drag files or click to browse
- **Progress Indicators**: Real-time progress tracking during batch processing
- **Side-by-Side Comparison**: View original vs. rewritten sentences side-by-side
- **Accept/Reject Buttons**: Quickly approve or dismiss each rephrased sentence
- **One-Click DOCX Export**: Generate and download the final document

## Installation Guide

### Prerequisites
- Python 3.14 or higher
- pip (Python package manager)
- 4GB+ RAM recommended for processing large documents

### Quick Start

1. **Clone the repository**
   ```
   git clone https://github.com/your-repo/plagiarism-checker.git
   cd plagiarism-checker
   ```

2. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

3. **Download NLP models** (automatic on first run, or manually):
   ```
   python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
   ```

4. **Run the application**
   ```
   python app/main.py
   ```

5. **Access the web interface**
   Open your browser and navigate to `http://localhost:8000`

### Docker Deployment

1. **Build the Docker image**
   ```
   docker build -t plagiarism-checker .
   ```

2. **Run the container**
   ```
   docker run -p 8000:8000 plagiarism-checker
   ```

3. **Access the application**
   Open your browser and navigate to `http://localhost:8000`

## Working Workflow

### Step 1: Upload Documents
1. Navigate to the Plagiarism Checker Pro web interface
2. Drag and drop 3-5 DOCX or PDF files (10,000+ words recommended) into the upload area
   - Or click "Browse" to select files from your computer
3. The system will validate the upload (must be 3-5 files, .docx or .pdf only)

### Step 2: Processing
1. After uploading, the system begins automatic processing
2. A progress bar shows the batch processing status
3. The system extracts text, splits into sentences, and performs plagiarism analysis
4. For each sentence, an AI-generated rephrased version is created

   **Typical processing time**: 
   - 10,000 words: ~2-3 minutes
   - Five 10,000-word files: ~5 minutes (on 4-core machine)

### Step 3: Review Results
1. Once processing completes, results appear as color-coded cards
2. **Plagiarized sentences** are highlighted in yellow/orange
3. **Original sentences** (no plagiarism) have a different color scheme
4. Each sentence shows the original text and the AI-generated rephrased version

### Step 4: Accept or Reject Rephrases
For each sentence:
1. Review the original text and the rephrased version
2. Click the ✓ (Accept) button to keep the rephrased version
3. Click the ✗ (Reject) button to keep the original text
4. Accepted rephrases replace the original in the final document

   **Tip**: Use the side-by-side comparison view to see original and rewritten versions side-by-side for easier evaluation.

### Step 5: Export Final Document
1. After reviewing all sentences, click "Export Final DOCX"
2. The system generates a DOCX file that includes:
   - All non-plagiarized original sentences
   - Accepted rephrased sentences (marked as revisions)
   - Plagiarized sentences highlighted in yellow with red text
3. Download the file to your computer

## Acceptance Criteria

### Detection Accuracy
- The tool must flag ≥95% of intentionally plagiarized sentences when provided with a test set
- Sentence-level comparison provides precise detection of matching content

### Rephrase Quality
- Each auto-rewrite must pass a follow-up scan with ≤5% residual similarity to the same public sources
- The AI rephraser generates sufficiently different wording while preserving meaning

### Performance
- Batch processing of five 10,000-word DOCX files must complete in under five minutes on a 4-core machine
- In-memory processing avoids timeouts even with large documents

## Technical Notes

### Architecture
The application follows SOLID principles:
- **SRP**: Each class has a single responsibility (PlagiarismDetector, FileIngestor, Rephraser)
- **Dependency Injection**: Services are initialized and can be injected as needed
- **Separation of Concerns**: Frontend, backend, and NLP services are decoupled

### Technology Stack
- **Backend**: FastAPI with Python 3.14
- **NLP Models**: sentence-transformers for embeddings, transformers for rephrasing
- **File Processing**: pypdf for PDF, python-docx for DOCX
- **Frontend**: Vanilla HTML/CSS/JS with modern UI patterns
- **Deployment**: Docker-ready with multi-stage build

### Configuration
- **Similarity Threshold**: Adjustable in `app/core/plagiarism.py` (default: 0.75)
- **Rephrasing Model**: Configure in `app/core/rephrase.py` (OpenAI or local T5)
- **CORS**: Configured for development; restrict for production deployment

## Troubleshooting

### Common Issues

1. **Model loading errors**: 
   - Ensure sentence-transformers and transformers are installed
   - First run may download models automatically

2. **Memory errors with large files**:
   - The system processes documents in memory
   - For 10,000+ word documents, ensure 4GB+ RAM available

3. **Export fails**:
   - Ensure python-docx is installed (`pip install python-docx`)
   - Check that batch processing completed successfully

4. **Slow processing**:
   - Verify you're using Python 3.14+
   - Close other applications to free memory
   - Use Docker for consistent performance

### Performance Optimization
- The all-MiniLM-L6-v2 model is optimized for speed
- Batch processing uses asyncio for concurrent operations
- Sentence embeddings are cached during a single batch run

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Serve the web interface |
| `/api/upload` | POST | Upload and start batch processing |
| `/api/batch/{task_id}` | GET | Check batch processing status |
| `/api/accept-reject/{sentence_idx}` | POST | Accept/reject a rephrased sentence |
| `/api/export/{task_id}` | GET | Download the final DOCX document |

## License
This project is licensed under the MIT License.
Team #23 MONGE Alejandro - CHEN Jenny - BEJJANI Oliver

# Report Summarization and Data Visualization API

This project provides a FastAPI-powered backend API that processes PDF reports, generates summaries using AWS Bedrock, and visualizes historical stock data. The API saves results to AWS S3, enabling users to retrieve, view, and manage reports and summaries through a web interface.

## Features

- **PDF Report Upload**: Upload PDF files for text extraction and summarization.
- **Summarization with AWS Bedrock**: Generates a concise summary using Bedrock's Claude model.
- **Stock Data Visualization**: Retrieves stock data from Yahoo Finance and visualizes it.
- **S3 Storage**: Stores PDF files, summaries, and stock data as CSV files in an AWS S3 bucket.
- **Web Interface**: Provides a user-friendly frontend for report submission, summary viewing, and data visualization.

## Project Structure

```plaintext
.
├── app.py                   # FastAPI application with endpoints for report processing
├── pdf_processing.py        # Module for PDF text extraction and chunking
├── summerizer.py            # Summarization logic using AWS Bedrock API
├── get_data.py              # Function to fetch stock data from Yahoo Finance
├── static/                  # Contains static files for the frontend (HTML, JS)
│   ├── index.html           # Main HTML file for the frontend
│   └── script.js            # JavaScript file for frontend functionality
├── requirements.txt         # List of project dependencies
└── README.md                # Project documentation
```


#3 Running the Application in Amazon SageMaker

Follow these steps to run the application in Amazon SageMaker:

### 1. Open the Amazon SageMaker Console
- Go to the [Amazon SageMaker Console](https://aws.amazon.com/sagemaker/) and launch a new SageMaker Notebook Instance or open an existing one.

### 2. Clone the Repository
- Once inside the SageMaker Notebook environment, open a terminal and clone the repository containing the application code.

    ```bash
    git clone https://github.com/oliverbejj/-23---PolyFinance2024.git
    cd <REPO_NAME>
    ```

### 3. Install Dependencies
- Install the required Python packages specified in `requirements.txt`:

    ```bash
    pip install -r requirements.txt
    ```

### 4. Configure AWS Credentials (if needed for Bedrock access)
- The S3 bucket is public, no special configuration is needed for S3 access.
- For AWS Bedrock access, ensure your SageMaker instance has the proper permissions

### 5. Run the Application
- Start the FastAPI server using Uvicorn to serve the application on `http://localhost:8000`:

    ```bash
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
    ```

### 6. Access the Application
- Open a new browser tab and navigate to `http://<NOTEBOOK_INSTANCE_IP>/jupyter/default/proxy/8000/static/index.html` to access the FastAPI application. Replace `<NOTEBOOK_INSTANCE_IP>` with the public or private IP address of your SageMaker Notebook instance.

You can now interact with the API and use the frontend interface to upload reports, view summaries, and visualize stock data.

---

#### Important Notes
- **Public Access Caution**: The S3 bucket is public, anyone with the URL can access the data.
- The summary unfortunately takes very long time to generate 

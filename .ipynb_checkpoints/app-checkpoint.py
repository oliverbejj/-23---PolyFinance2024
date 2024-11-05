from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import boto3
import io
import csv
import os
from get_data import get_opening_values
import uuid
from summerizer import main as process_pdf_summary  


app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount("/static", StaticFiles(directory="static"), name="static")


s3_client = boto3.client("s3")
bucket_name = "polyfinanceajoo"  

@app.get("/")
async def read_index():
    return JSONResponse({"message": "Welcome to the report processing API."})

@app.post("/process")
async def process_pdf(file: UploadFile = File(...), ticker: str = Form(...)):
    print("start processing")
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    
    report_id = str(uuid.uuid4())
    original_filename = file.filename
    object_key = f"Reports/{report_id}.pdf"

   
    s3_client.upload_fileobj(file.file, bucket_name, object_key)

    
    try:
        summary = process_pdf_summary(bucket_name, object_key) 
    except Exception as e:
        print(f"Error generating summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing PDF summary: {e}")

    # Retrieve stock data points using the provided ticker symbol
    data_points = get_opening_values(ticker)  # Assuming this returns a dict of {date: opening value}

    # Save the summary to S3 with original filename in metadata
    summary_key = f"Summaries/{report_id}_summary.txt"
    s3_client.put_object(
        Bucket=bucket_name,
        Key=summary_key,
        Body=summary,
        Metadata={"original_filename": original_filename}  # Save original filename as metadata
    )

    # Save the data CSV to S3
    data_key = f"Data/{report_id}_data.csv"
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    writer.writerow(["Date", "Value"])  # Add CSV headers
    for date, value in data_points.items():
        writer.writerow([date, value])
    s3_client.put_object(Bucket=bucket_name, Key=data_key, Body=csv_buffer.getvalue())
    
    print("end processing")

    return JSONResponse({
        "message": "Report processed successfully",
        "summary": summary,
        "data": data_points,
        "report_id": report_id,
        "file_name": original_filename
    })

# Other endpoints remain unchanged
@app.get("/list_reports")
async def list_reports():
    try:
        objects = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="Summaries/")
        reports = []
        for obj in objects.get("Contents", []):
            report_key = obj["Key"]
            if report_key.endswith("_summary.txt"):
                report_id = report_key.split("/")[1].replace("_summary.txt", "")
                response = s3_client.head_object(Bucket=bucket_name, Key=report_key)
                original_filename = response["Metadata"].get("original_filename", "Unknown File")
                reports.append({"report_id": report_id, "file_name": original_filename})
        return JSONResponse({"reports": reports})
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to list reports") from e

@app.get("/get_summary/{report_id}")
async def get_summary(report_id: str):
    summary_key = f"Summaries/{report_id}_summary.txt"
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=summary_key)
        summary_text = response['Body'].read().decode('utf-8')
        return JSONResponse({"summary": summary_text})
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Summary not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve summary") from e

@app.get("/get_data/{report_id}")
async def get_data(report_id: str):
    data_key = f"Data/{report_id}_data.csv"
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=data_key)
        data_csv = response['Body'].read().decode('utf-8')
        data_points = {}
        reader = csv.reader(io.StringIO(data_csv))
        next(reader)
        for row in reader:
            date = row[0]
            value = float(row[1])
            data_points[date] = value
        return JSONResponse({"data": data_points})
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Data not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve data") from e

@app.delete("/delete_report/{report_id}")
async def delete_report(report_id: str):
    try:
        summary_key = f"Summaries/{report_id}_summary.txt"
        data_key = f"Data/{report_id}_data.csv"
        s3_client.delete_object(Bucket=bucket_name, Key=summary_key)
        s3_client.delete_object(Bucket=bucket_name, Key=data_key)
        return {"message": f"Report {report_id} and associated files deleted successfully"}
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Report not found in S3 bucket")
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete report") from e

# Run the API using Uvicorn if executed directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

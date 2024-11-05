# pdf_processing.py

import PyPDF2
import boto3
import pickle, os, re, json
import time
from queue import Queue
from threading import Thread
import json
import io

# Initialize the S3 client
s3_client = boto3.client("s3")


from anthropic import Anthropic
client = Anthropic()
def count_tokens(text):
    return client.count_tokens(text)
count_tokens("Hello world what is up?!")

CACHE_RESPONSES = True
if CACHE_RESPONSES: print("Warning: Clause Cache is enabled")

from botocore.config import Config

my_config = Config(
    connect_timeout=60*3,
    read_timeout=60*3,
)
bedrock = boto3.client(service_name="bedrock-runtime", config=my_config)
bedrock_service = boto3.client(service_name="bedrock", config=my_config)

models = bedrock_service.list_foundation_models()
if"anthropic.claude-3-sonnet-20240229-v1:0" in str(models):
    print("Claude-3-sonnet found")
else:
    print("na nai")
max_token_count = 12000


prompt_template = """
\nHuman: I am going to give you a text{{GUIDANCE_1}}. This text is extracted from:
<text>
{{TEXT}}
</text>
{{GUIDANCE_2}}
{{STYLE}}{{REQUEST}}{{FORMAT}}{{GUIDANCE_3}}
\nAssistant: Here is what you asked for:
"""

merge_prompt_template = """
\nHuman: Here are a number of related summaries:

{{TEXT}}
Please merge these summaries into a highly detailed single summary in {{FORMAT}} format, preserving key details.
\nAssistant: Here is what you asked for:
"""

guidance_template = """
Here is the additional guidance:
<guidance>
{{GUIDANCE}}
</guidance>
"""

reporter_prompt = """
\nHuman: You are a newspaper reporter, collecting facts to be used in writing an article:
<text>
{{TEXT}}
</text>
{{DOCS_DESCRIPTION}} Please create a {{FORMAT}} of all the relevant facts from this text which will be useful.\nAssistant: Here is the {{FORMAT}} of relevant facts:
"""

reporter_summary_prompt = """
\nHuman: You are a newspaper reporter, collecting facts to be used in:
<text>
{{TEXT}}
</text>
Please create a {{FORMAT}} of all the relevant facts and trends from these notes which will be useful.\nAssistant: Here is the list of relevant facts:
"""

reporter_final_prompt = """
\nHuman: You are a newspaper reporter, writing an article based on facts:
<text>
{{TEXT}}
</text>
Each summary is a collection of facts extracted from a number of source reports. Each source report contains:\nAssistant: Here is the narrative:
"""

def get_prompt(text, prompt_type, format_type, manual_guidance, style_guide, docs_description=""):
    '''
    text should be a single string of the raw text to be sent to the gen ai model.
    prompt_type must be "summary" or "interrogate" or "answers"
        - summary means summarize the text
        - interrogate means look at the text and ask questions about what is missing
        - answers means looking at the text, provide only details that may help answer the questions
        - merge_summaries takes 2 or more summaries and merges them together. The summaries to merge are passed in the text parameter.
        - reporter - like a news reporter, extract details that help answer the guidance questions
        - reporter_summary - like a news reporter looking at a bunch of notes, create a list summary of relevant facts
        - reporter_final - generate a narrative based on the reporter_summary outputs.
    format_type must be "narrative" or "list"
    manual_guidance Extra instructions to guide the process, usually from the user.
    style_guide TBD

    Note that merge_summaries is handled differently than all other options because it iteratively adds summaries.
    '''

    # Answers mode is a bit different, so handle that first.
    if prompt_type == "answers":
        format_type = "list format, using less than 1000 tokens."
        prompt_type_1 = "Please provide a list of any facts from the text that could be relevant to answering questions, and some guidance"
        guidance_1 = guidance_template.replace("{{GUIDANCE}}", manual_guidance)
        guidance_3 = "You should ignore any questions that cannot be answered by this text."
        return prompt_template.replace("{{TEXT}}", text).replace("{{FORMAT}}", format_type).replace("{{GUIDANCE_1}}", "").replace("{{GUIDANCE_2}}", guidance_1).replace("{{GUIDANCE_3}}", guidance_3)

    elif prompt_type == "reporter":
        return reporter_prompt.replace("{{TEXT}}", text).replace("{{FORMAT}}", format_type).replace("{{DOCS_DESCRIPTION}}", docs_description)

    elif prompt_type == "reporter_summary":
        summaries_text = ""
        for x, summary in enumerate(text):
            summaries_text += f"<note_{x+1}>\n{summary}\n</note_{x+1}>\n"
        final_prompt = reporter_summary_prompt.replace("{{TEXT}}", summaries_text).replace("{{FORMAT}}", format_type)
        return final_prompt

    elif prompt_type == "reporter_final":
        summaries_text = ""
        for x, summary in enumerate(text):
            summaries_text += f"<summary_{x+1}>\n{summary}\n</summary_{x+1}>\n"
        final_prompt = reporter_final_prompt.replace("{{TEXT}}", summaries_text).replace("{{FORMAT}}", format_type)
        return final_prompt

    elif prompt_type == "merge_summaries":
        summaries_text = ""
        for x, summary in enumerate(text):
            summaries_text += f"<summary_{x+1}>\n{summary}\n</summary_{x+1}>\n"
        final_prompt = merge_prompt_template.replace("{{TEXT}}", summaries_text).replace("{{FORMAT}}", format_type)
        return final_prompt

    elif prompt_type == "merge_answers":
        prompt_type_1 = "The text is a good summary which may lack a few details. However, the additional context helps."
        format_type = "list"
        guidance_1 = " and some guidance"
        guidance_2 = guidance_template.replace("{{GUIDANCE}}", manual_guidance)
        guidance_3 = "You should ignore any comments in the guidance section indicating that answers cannot be provided."

    else:
        # Based on the options passed in, grab the correct text to eventually use to build the prompt.
        # Select the correct type of output format desired, List or summary. Note that List for Interrogate is enforced.
        if prompt_type == "interrogate" and format_type != "list":
            raise ValueError("Only list format is supported for interrogate prompts.")
        if format_type == "list":
            if prompt_type == "interrogate":
                format_type = ""  # already in the prompt so no format needed.
            else:
                format_type = "in list format, using less than 1000 tokens."
        elif format_type == "narrative":
            format_type = "in narrative format, using less than 1000 tokens."
        else:
            raise ValueError("format_type must be 'narrative' or 'list'.")
            
    if manual_guidance == "":
        guidance_1 = ""
        guidance_2 = ""
        guidance_3 = ""
    else:
        guidance_1 = " and some guidance"
        guidance_2 = guidance_template.replace("{{GUIDANCE}}", manual_guidance)
        guidance_3 = " As much as possible, also follow the guidance from the guidance section."
    # Build the final prompt
    style_guide = ""
    final_prompt = prompt_template.replace("{{TEXT}}", text).replace("{{GUIDANCE_1}}", guidance_1).replace("{{GUIDANCE_2}}", guidance_2).replace("{{GUIDANCE_3}}", guidance_3)

    return final_prompt

    
    
claude_cache_pickle = "claude_cache.pkl"

def save_calls(claude_cache):
    with open(claude_cache_pickle, 'wb') as file:
        pickle.dump(claude_cache, file)

# Load our cached calls to Claude
def load_calls():
    with open(claude_cache_pickle, 'rb') as file:
        return pickle.load(file)

def clear_cache():
    claude_cache = {}
    save_calls(claude_cache)

# A cache of recent requests, to speed up iteration while testing
claude_cache = {}

if not os.path.exists(claude_cache_pickle):
    print("Creating new, empty cache of Claude calls.")
    save_calls(claude_cache)

if CACHE_RESPONSES:
    claude_cache = load_calls()

MAX_ATTEMPTS = 30  # how many times to retry if Claude is not working.

def ask_claude(prompt_text, DEBUG=False):
    '''
    Send a prompt to Bedrock, and return the response. Debug is used to see exactly what is being sent.
    TODO: Add error checking and retry on hitting the throttling limit.
    '''
    # Usually, the prompt will have "human" and "assistant" tags already. These are required, so add them if missing.
    if not "Assistant:" in prompt_text:
        prompt_text = "\n\nHuman:" + prompt_text + "\n\nAssistant: "

    prompt_json = {
        "prompt": prompt_text,
        "max_tokens_to_sample": 3000,
        "temperature": 0.7,
        "top_k": 250,
        "top_p": 0.7,
        "stop_sequences": ["\n\nHuman:"]
    }
    body = json.dumps(prompt_json)

    # Return cached results, if any
    if body in claude_cache:
        return claude_cache[body]

    if DEBUG: print("sending:", prompt_text)

    modelId = "anthropic.claude-v2"
    accept = 'application/json'
    contentType = 'application/json'

    start_time = time.time()
    attempt = 1
    while True:
        try:
            query_start_time = time.time()
            response = bedrock.invoke_model(body=body, modelId=modelId, accept=accept, contentType=contentType)
            response_body = json.loads(response.get('body').read())

            raw_results = response_body.get("completion").strip()

            # Strip out HTML tags that Claude sometimes adds, such as <text>
            results = re.sub('<[^>]+>', '', raw_results)
            request_time = round(time.time() - start_time, 2)
            if DEBUG:
                print("Received", results)
                print("request time (sec):", request_time)
            total_tokens = count_tokens(prompt_text + raw_results)
            output_tokens = count_tokens(raw_results)
            tokens_per_sec = round(total_tokens / request_time, 2)
            break
        except Exception as e:
            print("Error with calling Bedrock:" + str(e))
            attempt += 1
            if attempt > MAX_ATTEMPTS:
                print("Max attempts reached!")
                results = str(e)
                request_time = -1
                total_tokens = -1
                output_tokens = -1
                tokens_per_sec = -1
                break
            else:
                # Retry in 10 seconds
                time.sleep(10)

    # Store in cache only if it was not an error
    if request_time > 0:
        claude_cache[body] = (prompt_text, results, total_tokens, output_tokens, request_time, tokens_per_sec, query_start_time)

    return (prompt_text, results, total_tokens, output_tokens, request_time, tokens_per_sec, query_start_time)



def read_pdf(bucket_name, object_key):
    """Reads a PDF file from S3 and extracts its text content."""
    full_text = ""
    try:
        # Retrieve PDF content from S3
        obj = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        print("Successfully retrieved PDF from S3.")

        # Read the content into a BytesIO object
        pdf_buffer = io.BytesIO(obj["Body"].read())

        # Parse the PDF content
        reader = PyPDF2.PdfReader(pdf_buffer)
        for page in reader.pages:
            full_text += (page.extract_text() or "") + "\n"

        print(f"PDF text extracted. Total characters: {len(full_text)}")
    except Exception as e:
        print(f"Error retrieving or reading PDF from S3: {e}")
        raise

    return full_text


def get_chunks(full_text, overlap=True, debug=False):
    chunk_length_tokens = 2000
    overlap_tokens = 260
    if not overlap:
        overlap_tokens = 0

    token_per_character = 1 / 4
    chunk_length_chars = int(chunk_length_tokens / token_per_character)
    overlap_chars = int(overlap_tokens * token_per_character)

    chunks = []
    start_chunk = 0
    char_count = len(full_text)

    while start_chunk < char_count:
        end_chunk = start_chunk + chunk_length_chars
        if end_chunk >= char_count:
            end_chunk = char_count
            chunks.append(full_text[start_chunk:end_chunk])
            break
        chunks.append(full_text[start_chunk:end_chunk])
        start_chunk += chunk_length_chars - overlap_chars

    if debug:
        print(f"Created {len(chunks)} chunks.")
    
    return chunks

def generate_single_doc_summary(text, options, auto_refine=False, debug=False):
    response = ask_claude(text, DEBUG=debug)
    summary = response[1].split("Assistant:")[-1].strip()

    if auto_refine:
        refined_summary_prompt = f"Shorten the following summary:\n\n{summary}"
        refined_response = ask_claude(refined_summary_prompt, DEBUG=debug)
        refined_summary = refined_response[1].split("Assistant:")[-1].strip()
        return refined_summary

    return summary

def main(bucket_name, object_key):
    # Step 1: Extract text from PDF
    full_text = read_pdf(bucket_name, object_key)
    print(f"Document length (characters): {len(full_text)}")

    # Step 2: Split the text into chunks
    chunks = get_chunks(full_text, overlap=True, debug=False)

    # Step 3: Generate summaries for each chunk and combine them
    combined_summary = ""
    for chunk in chunks:
        chunk_summary = generate_single_doc_summary(chunk, {}, auto_refine=False, debug=False)
        combined_summary += chunk_summary + "\n"

    print("\nInitial Combined Summary:")
    print(combined_summary)

    # Step 4: Generate a refined summary by re-summarizing each chunk of the combined output
    refined_chunks = get_chunks(combined_summary, overlap=False, debug=False)
    refined_summary = ""
    for chunk in refined_chunks:
        chunk_resummary = generate_single_doc_summary(chunk, {}, auto_refine=False, debug=False)
        refined_summary += chunk_resummary + "\n"

    print("\nRefined Summary:")
    print(refined_summary)
    return refined_summary

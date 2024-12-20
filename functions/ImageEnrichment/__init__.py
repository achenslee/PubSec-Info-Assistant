import json
import logging
import os

import azure.functions as func
import requests
from azure.storage.blob import BlobServiceClient
from azure.core.credentials import AzureKeyCredential
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential, get_bearer_token_provider, AzureAuthorityHosts
from shared_code.status_log import State, StatusClassification, StatusLog
from shared_code.utilities import Utilities, MediaType
from azure.search.documents import SearchClient
from datetime import datetime

azure_blob_storage_account = os.environ["BLOB_STORAGE_ACCOUNT"]
azure_blob_drop_storage_container = os.environ[
    "BLOB_STORAGE_ACCOUNT_UPLOAD_CONTAINER_NAME"
]
azure_blob_content_storage_container = os.environ[
    "BLOB_STORAGE_ACCOUNT_OUTPUT_CONTAINER_NAME"
]
azure_blob_storage_endpoint = os.environ["BLOB_STORAGE_ACCOUNT_ENDPOINT"]
azure_blob_content_storage_container = os.environ[
    "BLOB_STORAGE_ACCOUNT_OUTPUT_CONTAINER_NAME"
]
azure_blob_content_storage_container = os.environ[
    "BLOB_STORAGE_ACCOUNT_OUTPUT_CONTAINER_NAME"
]
# Authentication settings
azure_authority_host = os.environ["AZURE_OPENAI_AUTHORITY_HOST"]
local_debug = os.environ.get("LOCAL_DEBUG", False)

# OpenAI Endpoint and Key
azure_openai_key = os.environ["AZURE_OPENAI_SERVICE_KEY"]
azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_model = os.environ["AZURE_OPENAI_MODEL"]
azure_openai_deployment_id = os.environ["AZURE_OPENAI_DEPLOYMENT_ID"]
azure_openai_api_version = os.environ["AZURE_OPENAI_API_VERSION"]
prompt = os.environ["GPT4O_PROMPT"]
system_message = os.environ["GPT4O_SYSTEM_MESSAGE"]
aoai_headers = {"api-key": azure_openai_key}


# Cosmos DB
cosmosdb_url = os.environ["COSMOSDB_URL"]
cosmosdb_log_database_name = os.environ["COSMOSDB_LOG_DATABASE_NAME"]
cosmosdb_log_container_name = os.environ["COSMOSDB_LOG_CONTAINER_NAME"]

# Cognitive Services
azure_ai_key = os.environ["AZURE_AI_KEY"]
azure_ai_endpoint = os.environ["AZURE_AI_ENDPOINT"]
azure_ai_location = os.environ["AZURE_AI_LOCATION"]
azure_ai_credential_domain = os.environ["AZURE_AI_CREDENTIAL_DOMAIN"]

# Search Service
AZURE_SEARCH_SERVICE_ENDPOINT = os.environ.get("AZURE_SEARCH_SERVICE_ENDPOINT")
AZURE_SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX") or "gptkbindex"

if azure_authority_host == "AzureUSGovernment":
    AUTHORITY = AzureAuthorityHosts.AZURE_GOVERNMENT
else:
    AUTHORITY = AzureAuthorityHosts.AZURE_PUBLIC_CLOUD
if local_debug:
    azure_credential = DefaultAzureCredential(authority=AUTHORITY)
else:
    azure_credential = ManagedIdentityCredential(authority=AUTHORITY)
token_provider = get_bearer_token_provider(azure_credential,
                                           f'https://{azure_ai_credential_domain}/.default')

# Translation params for OCR'd text
targetTranslationLanguage = os.environ["TARGET_TRANSLATION_LANGUAGE"]

API_DETECT_ENDPOINT = (
        f"{azure_ai_endpoint}language/:analyze-text?api-version=2023-04-01"
    )
API_TRANSLATE_ENDPOINT = (
        f"{azure_ai_endpoint}translator/text/v3.0/translate?api-version=3.0"
    )

MAX_CHARS_FOR_DETECTION = 1000
translator_api_headers = {
    "Ocp-Apim-Subscription-Key": azure_ai_key,
    "Content-type": "application/json",
    "Ocp-Apim-Subscription-Region": azure_ai_location,
}

# Note that "caption" and "denseCaptions" are only supported in Azure GPU regions (East US, France Central,
# Korea Central, North Europe, Southeast Asia, West Europe, West US). Remove "caption" and "denseCaptions"
# from the list below if your Computer Vision key is not from one of those regions.

if azure_ai_location in [
    "eastus",
    "francecentral",
    "koreacentral",
    "northeurope",
    "southeastasia",
    "westeurope",
    "westus",
]:
    GPU_REGION = True
    VISION_ENDPOINT = f"{azure_ai_endpoint}computervision/imageanalysis:analyze?api-version=2023-04-01-preview&features=caption,denseCaptions,objects,tags,read&gender-neutral-caption=true"
else:
    GPU_REGION = False
    VISION_ENDPOINT = f"{azure_ai_endpoint}computervision/imageanalysis:analyze?api-version=2023-04-01-preview&features=objects,tags,read&gender-neutral-caption=true"

vision_api_headers = {
    "Ocp-Apim-Subscription-Key": azure_ai_key,
    "Content-type": "application/octet-stream",
    "Accept": "application/json",
    "Ocp-Apim-Subscription-Region": azure_ai_location,
}

FUNCTION_NAME = "ImageEnrichment"

utilities = Utilities(
    azure_blob_storage_account=azure_blob_storage_account,
    azure_blob_storage_endpoint=azure_blob_storage_endpoint,
    azure_blob_drop_storage_container=azure_blob_drop_storage_container,
    azure_blob_content_storage_container=azure_blob_content_storage_container,
    azure_credential=azure_credential
)


def detect_language(text):
    data = {
        "kind": "LanguageDetection",
        "analysisInput":{
            "documents":[
                {
                    "id":"1",
                    "text": text[:MAX_CHARS_FOR_DETECTION]
                }
            ]
        }
    } 

    response = requests.post(
        API_DETECT_ENDPOINT, headers=translator_api_headers, json=data
    )
    if response.status_code == 200:
        print(response.json())
        detected_language = response.json()["results"]["documents"][0]["detectedLanguage"]["iso6391Name"]
        detection_confidence = response.json()["results"]["documents"][0]["detectedLanguage"]["confidenceScore"]

    return detected_language, detection_confidence


def translate_text(text, target_language):
    data = [{"text": text}]
    params = {"to": target_language}

    response = requests.post(
        API_TRANSLATE_ENDPOINT, headers=translator_api_headers, json=data, params=params
    )
    if response.status_code == 200:
        translated_content = response.json()[0]["translations"][0]["text"]
        return translated_content
    else:
        raise Exception(response.json())

# funtion to submit image to GPT4o
def submit_to_gpt4o(img_sas, prompt, system_message):
    aoai_json = {
    "messages": [
        {
            "role": "system",
            "content": f'{system_message}'},
        {
            "role": "user",
            "content": [
	            {
	                "type": "text",
	                "text": f"{prompt}"
	            },
	            {
	                "type": "image_url",
	                "image_url": {
                        "url":f"{img_sas}" 
                    }
                }
           ] 
        }
    ],
            "max_tokens": 100, 
            "stream": False
        }

    logging.info(f'{azure_openai_endpoint}/openai/deployments/{azure_openai_deployment_id}/completions?api-version={azure_openai_api_version}')
    
    response = requests.post(f'{azure_openai_endpoint}/openai/deployments/{azure_openai_deployment_id}/completions?api-version={azure_openai_api_version}', headers=aoai_headers, json=aoai_json)

    logging.info(response)

    if response.status_code == 200:
        return response.json()

#Function to get model response
def process_gpt4o_response(json_response):
    logging.info(json_response)
    text_resp = json_response['choices'][0]['message']['content']
    return text_resp


def main(msg: func.QueueMessage) -> None:
    """This function is triggered by a message in the image-enrichment-queue.
    It will first analyse the image. If the image contains text, it will then
    detect the language of the text and translate it to Target Language. """

    message_body = msg.get_body().decode("utf-8")
    message_json = json.loads(message_body)
    blob_path = message_json["blob_name"]
    blob_uri = message_json["blob_uri"]
    try:
        statusLog = StatusLog(
            cosmosdb_url, azure_credential, cosmosdb_log_database_name, cosmosdb_log_container_name
        )
        logging.info(
            "Python queue trigger function processed a queue item: %s",
            msg.get_body().decode("utf-8"),
        )
        # Receive message from the queue
        statusLog.upsert_document(
            blob_path,
            f"{FUNCTION_NAME} - Received message from image-enrichment-queue ",
            StatusClassification.DEBUG,
            State.PROCESSING,
        )

        # Run the image through the Computer Vision service
        file_name, file_extension, file_directory = utilities.get_filename_and_extension(
            blob_path)
        path = blob_path.split("/", 1)[1]

        #Added 11/19
        blob_path_plus_sas = utilities.get_blob_and_sas(blob_path)
        logging.info(blob_path_plus_sas)


        blob_service_client = BlobServiceClient(account_url=azure_blob_storage_endpoint,
                                                    credential=azure_credential)
        blob_client = blob_service_client.get_blob_client(container=azure_blob_drop_storage_container,
                                                              blob=path)
        image_data = blob_client.download_blob().readall()
        files = {"file": image_data}
        response = requests.post(VISION_ENDPOINT, 
                                 headers=vision_api_headers, 
                                 data=image_data)
    
        if response.status_code == 200:
            result = response.json()
            text_image_summary = ""
            index_content = ""
            complete_ocr_text = None

            ## submit image to gpt-4o, get response, add to index ##
            prompt = os.environ["GPT4O_PROMPT"]

            gpt4o_result = submit_to_gpt4o(blob_path_plus_sas, prompt, system_message)
            processed_gpt4o_response = process_gpt4o_response(gpt4o_result)

            logging.info(process_gpt4o_response)

            text_image_summary += f"{file_name} GPT-4o Response: {processed_gpt4o_response}\n"
            index_content += f"{file_name} GPT-4o Response: {processed_gpt4o_response}\n"
            logging.info(text_image_summary)

            if GPU_REGION:
                if result["captionResult"] is not None:
                    text_image_summary += "Caption:\n"
                    text_image_summary += "\t'{}', Confidence {:.4f}\n".format(
                        result["captionResult"]["text"], result["captionResult"]["confidence"]
                    )
                    index_content += "Caption: {}\n ".format(result["captionResult"]["text"])

                if result["denseCaptionsResult"] is not None:
                    text_image_summary += "Dense Captions:\n"
                    index_content += "DeepCaptions: "
                    for caption in result["denseCaptionsResult"]["values"]:
                        text_image_summary += "\t'{}', Confidence: {:.4f}\n".format(
                            caption["text"], caption["confidence"]
                        )
                        index_content += "{}\n ".format(caption["text"])

            if result["objectsResult"] is not None:
                text_image_summary += "Objects:\n"
                index_content += "Descriptions: "
                for object_detection in result["objectsResult"]["values"]:
                    text_image_summary += "\t'{}', Confidence: {:.4f}\n".format(
                        object_detection["name"], object_detection["confidence"]
                    )
                    index_content += "{}\n ".format(object_detection["name"])

            if result["tagsResult"] is not None:
                text_image_summary += "Tags:\n"
                for tag in result["tagsResult"]["values"]:
                    text_image_summary += "\t'{}', Confidence {:.4f}\n".format(
                        tag["name"], tag["confidence"]
                    )
                    index_content += "{}\n ".format(tag["name"])

            if result["readResult"] is not None:
                text_image_summary += "Raw OCR Text:\n"
                complete_ocr_text = ""
                for line in result["readResult"]["pages"][0]["words"]:
                    complete_ocr_text += "{}\n".format(line["content"])
                text_image_summary += complete_ocr_text

        else: 
            logging.error("%s - Image analysis failed for %s: %s",
                          FUNCTION_NAME,
                          blob_path,
                          str(response.json()))
            statusLog.upsert_document(
                blob_path,
                f"{FUNCTION_NAME} - Image analysis failed: {str(response.json())}",
                StatusClassification.ERROR,
                State.ERROR,
            )
            raise requests.exceptions.HTTPError(response.json())

        if complete_ocr_text not in [None, ""]:
            # Detect language
            output_text = ""

            detected_language, detection_confidence = detect_language(
                complete_ocr_text)
            text_image_summary += f"Raw OCR Text - Detected language: {detected_language}, Confidence: {detection_confidence}\n"

            if detected_language != targetTranslationLanguage:
                # Translate text
                output_text = translate_text(
                    text=complete_ocr_text, target_language=targetTranslationLanguage
                )
                text_image_summary += f"Translated OCR Text - Target language: {targetTranslationLanguage}\n"
                text_image_summary += output_text
                index_content += "OCR Text: {}\n ".format(output_text)

            else:
                # No translation required
                output_text = complete_ocr_text
                index_content += "OCR Text: {}\n ".format(complete_ocr_text)

        else:
            statusLog.upsert_document(
                blob_path,
                f"{FUNCTION_NAME} - No OCR text detected",
                StatusClassification.INFO,
                State.PROCESSING,
            )

        # Upload the output as a chunk to match document model
        utilities.write_chunk(
            myblob_name=blob_path,
            myblob_uri=blob_uri,
            file_number=0,
            chunk_size=utilities.token_count(text_image_summary),
            chunk_text=text_image_summary,
            page_list=[0],
            section_name="",
            title_name=file_name,
            subtitle_name="",
            file_class=MediaType.IMAGE
        )

        statusLog.upsert_document(
            blob_path,
            f"{FUNCTION_NAME} - Image enrichment is complete",
            StatusClassification.DEBUG,
            State.QUEUED,
        )

    except Exception as error:
        statusLog.upsert_document(
            blob_path,
            f"{FUNCTION_NAME} - An error occurred - {str(error)}",
            StatusClassification.ERROR,
            State.ERROR,
        )

    try:
        file_name, file_extension, file_directory = utilities.get_filename_and_extension(
            blob_path)

        # Get the tags from metadata on the blob
        path = file_directory + file_name + file_extension
        blob_service_client = BlobServiceClient(
            account_url=azure_blob_storage_endpoint, credential=azure_credential)
        blob_client = blob_service_client.get_blob_client(
            container=azure_blob_drop_storage_container, blob=path)
        blob_properties = blob_client.get_blob_properties()
        tags = blob_properties.metadata.get("tags")
        if tags is not None:
            if isinstance(tags, str):
                tags_list = [tags]
            else:
                tags_list = tags.split(",")
        else:
            tags_list = []
        # Write the tags to cosmos db
        statusLog.update_document_tags(blob_path, tags_list)

        # Only one chunk per image currently.
        chunk_file = utilities.build_chunk_filepath(
            file_directory, file_name, file_extension, '0')

        index_section(index_content, file_name, file_directory[:-1], statusLog.encode_document_id(
            chunk_file), chunk_file, blob_path, blob_uri, tags_list)

        statusLog.upsert_document(
            blob_path,
            f"{FUNCTION_NAME} - Image added to index.",
            StatusClassification.INFO,
            State.COMPLETE,
        )
    except Exception as err:
        statusLog.upsert_document(
            blob_path,
            f"{FUNCTION_NAME} - An error occurred while indexing - {str(err)}",
            StatusClassification.ERROR,
            State.ERROR,
        )

    statusLog.save_document(blob_path)


def index_section(index_content, file_name, file_directory, chunk_id, chunk_file, blob_path, blob_uri, tags):
    """ Pushes a batch of content to the search index
    """

    index_chunk = {}
    batch = []
    index_chunk['id'] = chunk_id
    azure_datetime = datetime.now().astimezone().isoformat()
    index_chunk['processed_datetime'] = azure_datetime
    index_chunk['file_name'] = blob_path
    index_chunk['file_uri'] = blob_uri
    index_chunk['folder'] = file_directory
    index_chunk['title'] = file_name
    index_chunk['content'] = index_content
    index_chunk['pages'] = [0]
    index_chunk['chunk_file'] = chunk_file
    index_chunk['file_class'] = MediaType.IMAGE
    index_chunk['tags'] = tags
    batch.append(index_chunk)

    search_client = SearchClient(endpoint=AZURE_SEARCH_SERVICE_ENDPOINT,
                                 index_name=AZURE_SEARCH_INDEX,
                                 credential=azure_credential)

    search_client.upload_documents(documents=batch)

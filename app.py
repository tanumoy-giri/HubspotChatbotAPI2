import os
import http.client
import json
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from dotenv import load_dotenv
load_dotenv()



# Load documents
docs = SimpleDirectoryReader("data\kbpdf").load_data()

# Create index
index = VectorStoreIndex.from_documents(docs)

# HubSpot API key
api_key = os.getenv('HUBSPOT_API_KEY')
#print(os.environ['HUBSPOT_API_KEY'])
#print(os.environ['OPENAI_API_KEY'])

# Define Flask app
app = Flask(__name__)
CORS(app)

# Function to query Knowledge Base
def query_kb(index_i, query_str):
    query_engine = index_i.as_query_engine()
    response = query_engine.query(query_str)
    responseAsText = str(response).strip()
    return responseAsText

# Function to get associate object details
def get_associate(values, properties, endpoint):
    method = 'post'
    # Define the request headers
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    body = {
        "filterGroups": [
            {
                "filters": [
                    {
                        "value": value,
                        "propertyName": "hs_object_id",
                        "operator": "EQ"
                    }
                    for value in values
                ]
            }
        ],
        "properties": properties
    }

    try:
        print(body)
        response = requests.request(method, endpoint, json=body, headers=headers)
        response.raise_for_status()  # Raise an error for non-2xx status codes
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making API call: {e}")
        return None

# Function to get Owner object details
def get_owner(owner_id):
    # Convert the owner ID to string
    id_string = str(owner_id)
    
    # Define the endpoint URL
    url = f'https://api.hubapi.com/crm/v3/owners/{id_string}'

    # Define the request headers
    headers = {
        'Authorization': f'Bearer {api_key}'
    }

    # Send the GET request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Function to get User details
def get_user(user_id):
    # Define the endpoint URL
    url = f'https://api.hubapi.com/settings/v3/users/{user_id}'

    # Define the request headers
    headers = {
        'Authorization': f'Bearer {api_key}'
    }

    # Send the GET request
    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

# Route for Knowledge Base query
@app.route("/kb", methods=['POST'])
def get_kb_response():
    user_question = request.json.get('question')
    result = query_kb(index, user_question)
    return result

# Route for fetching HubSpot ticket information
@app.route("/ticket", methods=['POST'])
def get_hubspot_response():
    data = request.json
    ticket_id = data.get('ticketId')
    if not ticket_id:
        return jsonify({'error': 'Ticket ID is missing'})

    conn = http.client.HTTPSConnection("api.hubapi.com")
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    # Update the propertiesWithHistory parameter
    properties_with_history = "hs_created_by_user_id,hubspot_owner_id,subject,content,hs_pipeline_stage,hs_ticket_priority,createdate,closed_date,magiccx_meeting_id,magiccx_meeting_summarize,meeting_record_link"
    endpoint = f"/crm/v3/objects/tickets/{ticket_id}?propertiesWithHistory={properties_with_history}&associations=email,task,note,meetings"
    conn.request("GET", endpoint, headers=headers)
    res = conn.getresponse()
    data = res.read().decode("utf-8")

    try:
        # Attempt to load data as JSON
        json_data = json.loads(data)
        hs_owner_history = json_data.get("propertiesWithHistory", {}).get("hubspot_owner_id", [])
        hs_created_by_history = json_data.get("propertiesWithHistory", {}).get("hs_created_by_user_id", [])
        subject_history = json_data.get("propertiesWithHistory", {}).get("subject", [])
        content_history = json_data.get("propertiesWithHistory", {}).get("content", [])
        hs_pipeline_stage_history = json_data.get("propertiesWithHistory", {}).get("hs_pipeline_stage", [])
        hs_ticket_priority_history = json_data.get("propertiesWithHistory", {}).get("hs_ticket_priority", [])
        createdate_history = json_data.get("propertiesWithHistory", {}).get("createdate", [])
        closed_date_history = json_data.get("propertiesWithHistory", {}).get("closed_date", [])
        magiccx_meeting_id_history = json_data.get("propertiesWithHistory", {}).get("magiccx_meeting_id", [])
        magiccx_meeting_summarize_history = json_data.get("propertiesWithHistory", {}).get("magiccx_meeting_summarize", [])
        meeting_record_link_history = json_data.get("propertiesWithHistory", {}).get("meeting_record_link", [])
        #get associate objects id, note,email.task
        emails = json_data.get("associations", {}).get("emails", {}).get("results",[])
        tasks = json_data.get("associations", {}).get("tasks", {}).get("results",[])
        notes = json_data.get("associations", {}).get("notes", {}).get("results",[])
        meetings = json_data.get("associations", {}).get("meetings", {}).get("results",[])
        print(magiccx_meeting_id_history)
        print(magiccx_meeting_summarize_history)
        print(meeting_record_link_history)
        #print(hs_created_by_history)
        #print(hs_owner_history)

        # Extract owner data
        owner_data = []
        for prop in hs_owner_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                owner_details = get_owner(prop["value"])
                if owner_details:  # Check if owner details exist
                    owner_data.append({"Time Stamp": prop["timestamp"],
                                        "First Name": owner_details.get("firstName"),
                                        "Last Name": owner_details.get("lastName"),
                                        "Email": owner_details.get("email")})

        # Extract created by Id
        created_by_Id = []
        for prop in hs_created_by_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                created_by_details = get_user(prop["value"])  # Use get_user function for user details
                if created_by_details:  # Check if created by details exist
                    created_by_Id.append({"Time Stamp": prop["timestamp"],
                                          "First Name": created_by_details.get("firstName"),
                                          "Last Name": created_by_details.get("lastName"),
                                          "Email": created_by_details.get("email")})

        # Extract Ticket Name
        ticket_name = []
        for prop in subject_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                ticket_name.append({"Time Stamp": prop["timestamp"],
                                    "Ticket Name/subject": prop["value"]})

        # Extract hs_pipeline_stage_history
        pipeline_stage_history = []
        for prop in hs_pipeline_stage_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                pipeline_stage_history.append({"Time Stamp": prop["timestamp"],
                                               "Pipeline Stage": prop["value"]})

        # Extract hs_ticket_priority_history
        ticket_priority_history = []
        for prop in hs_ticket_priority_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                ticket_priority_history.append({"Time Stamp": prop["timestamp"],
                                                "Ticket Priority": prop["value"]})

        # Extract createdate_history
        createdate_data = []
        for prop in createdate_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                createdate_data.append({"Time Stamp": prop["timestamp"],
                                        "Create Date": prop["value"]})

        # Extract closed_date_history
        closed_date_data = []
        for prop in closed_date_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                closed_date_data.append({"Time Stamp": prop["timestamp"],
                                         "Closed Date": prop["value"]})
                                         
        # Extract content_history
        content_data = []
        for prop in content_history:
            if isinstance(prop, dict) and prop.get("value") and prop.get("timestamp"):
                content_data.append({"Time Stamp": prop["timestamp"],
                                         "Ticket Description": prop["value"]}) 

        # Extract Emails Data
        emails_ids = []
        emails_data = []
        email_properties = ["hs_email_text", "hs_email_subject","hs_timestamp","hs_email_status","hs_email_to_email","hs_email_to_lastname","hs_email_to_firstname","hs_email_sender_lastname","hs_email_sender_firstname","hs_createdate"]
        for prop in emails:
          if isinstance(prop, dict) and prop.get("id"):
            emails_ids.append(prop["id"])
        #print(emails_ids)
        emails_details = get_associate(emails_ids, email_properties, 'https://api.hubapi.com/crm/v3/objects/emails/search')["results"]
        #print(emails_details)
        for prop in emails_details: 
            if isinstance(prop, dict) and prop.get("id"):
                email_detail = prop.get("properties") 
                emails_data.append({"Email Body": email_detail["hs_email_text"],
                                         "Email Subject": email_detail["hs_email_subject"],
                                         "Time Stamp" : email_detail["hs_timestamp"],
                                          "Email Status" : email_detail["hs_email_status"],
                                           "To Address" : email_detail["hs_email_to_email"],
                                            "To Address Last Name" : email_detail["hs_email_to_lastname"],
                                             "To Address First Name" : email_detail["hs_email_to_firstname"],
                                              "Sender Last Name" : email_detail["hs_email_sender_lastname"],
                                               "Sender first Name" : email_detail["hs_email_sender_firstname"],
                                                "email created date": email_detail["hs_createdate"] })
                
        # Extract Notes Data
        notes_ids = []
        notes_data = []
        notes_properties = ["hs_note_body", "hs_timestamp"]
        for prop in notes:
          if isinstance(prop, dict) and prop.get("id"):
            notes_ids.append(prop["id"])
        #print(notes_ids)
        notes_details = get_associate(notes_ids, notes_properties, 'https://api.hubapi.com/crm/v3/objects/notes/search')["results"]
        #print(notes_details)
        for prop in notes_details: 
            if isinstance(prop, dict) and prop.get("id"):
                note_detail = prop.get("properties") 
                notes_data.append({"Note Body": note_detail["hs_note_body"],
                                    "Time Stamp" : note_detail["hs_timestamp"]})

        # Extract Tasks Data
        tasks_ids = []
        tasks_data = []
        tasks_properties = ["hs_task_body", "hs_timestamp", "hs_task_status", "hs_task_subject", "hs_task_priority"]
        for prop in tasks:
          if isinstance(prop, dict) and prop.get("id"):
            tasks_ids.append(prop["id"])
        #print(tasks_ids)
        tasks_details = get_associate(tasks_ids, tasks_properties, 'https://api.hubapi.com/crm/v3/objects/tasks/search')["results"]
        #print(tasks_details)
        for prop in tasks_details: 
            if isinstance(prop, dict) and prop.get("id"):
                task_detail = prop.get("properties") 
                tasks_data.append({"Task Body": task_detail["hs_task_body"],
                                    "Time Stamp": task_detail["hs_timestamp"],
                                    "Task Status": task_detail["hs_task_status"],
                                    "Task Subject": task_detail["hs_task_subject"],
                                    "Task Priority": task_detail["hs_task_priority"]})
                
        # extraxt magiccx_meeting_id_history. to be done
        meeting_data = []
        for i in range(len(magiccx_meeting_id_history)):
            meeting_dict = {}
            meeting_dict["Meeting Id"] = magiccx_meeting_id_history[i]["value"]
            meeting_dict["Meeting conversation summary"] = magiccx_meeting_summarize_history[i]["value"]
            meeting_dict["Recording Link"] = meeting_record_link_history [i]["value"]
            meeting_data.append(meeting_dict)

       # print(meeting_data)
        
        #Extract Meetings data // to be done leter it's not working now.
        meetings_ids = []
        meetings_data = []
        meeting_properties = ["hs_meeting_body","hs_meeting_title","hs_meeting_outcome","hs_meeting_end_time","hs_meeting_location","hs_meeting_start_time","hs_meeting_external_url", "hs_timestamp"]
        for prop in meetings:
          if isinstance(prop, dict) and prop.get("id"):
            meetings_ids.append(prop["id"])
        print(meetings_ids)
        meeting_details = get_associate(meetings_ids, meeting_properties, 'https://api.hubapi.com/crm/v3/objects/meetings/search')["results"]
        print(meeting_details)
        
        

        # Return extracted data as JSON response
        return jsonify({"Ticket_owner_History": owner_data,
                        "Ticket_created_by_user_History": created_by_Id,
                        "ticket_name_History": ticket_name,
                        "pipeline_stage_History": pipeline_stage_history,
                        "ticket_priority_History": ticket_priority_history,
                        "createdate_History": createdate_data,
                        "closed_date_History": closed_date_data,
                        "Ticket Description": content_data,
                        "Email Data": emails_data,
                        "Notes Data": notes_data,
                        "Tasks Data": tasks_data})
    except json.JSONDecodeError as e:
        # If unable to decode JSON, return an error response
        return jsonify({'error': str(e)})

# Run the app
if __name__ == "__main__":
    app.run(debug=True)

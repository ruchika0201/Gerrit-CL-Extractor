from datetime import datetime
from urllib import response
from requests.auth import HTTPDigestAuth
from pygerrit2 import GerritRestAPI, HTTPBasicAuth
from prettytable import PrettyTable
import pandas as pd
import backoff
import requests
import json
import re


# Gerrit Endpoint
GERRIT_API_URL = "https://your-gerrit-instance.com/"
FILE_PATTERN = r"^projects/ui-libs/"

# User Credentials on Gerrit
username = "username"
password = "password"

# Repository details
project = "projectName"
branch = "branchName"
CL_URL = 'https://your-gerrit-instance.com/c/projectName/+/'



auth = HTTPBasicAuth(username, password)
rest = GerritRestAPI(url=GERRIT_API_URL, auth=auth)



@backoff.on_exception(backoff.expo, requests.exceptions.ConnectionError, max_time=10)
def invokeGerritAPI(target_date):

    # Query to fetch the CLs via Gerrit API
    query_params = {
        "q": f"status:MERGED AND project:{project} AND branch:{branch}"
    }

    # API call
    response = rest.get(
        "changes/", params=query_params, headers={"Content-Type": "application/json"}
    )
    cls_list = response


    # Filtering the change IDs after the target date
    change_ids_after_target_date = filterChangeIDsAfterTargetDate(cls_list, target_date)


    # Filtering the change IDs list based on the file pattern in the CLs
    # Note: we are interested in only files under ui-libs project,
    # So, here we are filtering the CLs who has change in ui-libs project only
    change_ids_list_matching_pattern = filterChangeIDsByFilePattern(change_ids_after_target_date)


    filtered_cls = [obj for obj in response if obj['change_id'] in change_ids_list_matching_pattern]

    # Fetching the author details of the filtered CLs
    user_list = fetchAuthorDetails(change_ids_list_matching_pattern)

    for item in filtered_cls:
        item_id = item["change_id"]

        # Appending the CL response with the author details
        if item_id in user_list:
            item.update(user_list[item_id])
            item.update({'cl_url': f'{CL_URL}{item["_number"]}'})



    cl_list = json.dumps(filtered_cls, indent=4)
    cl_list = json.loads(cl_list)
    return cl_list


# Function to filter out CLs after the target date
def filterChangeIDsAfterTargetDate(cl_list, target_date = datetime(2023, 9, 1)):
    change_ids = []
    for cl in cl_list:
        submitted_timestamp = cl["submitted"].split(".", 1)[0]
        cl_submitted_date = datetime.strptime(submitted_timestamp, "%Y-%m-%d %H:%M:%S")
        if cl_submitted_date >= target_date:
            change_ids.append(cl["change_id"])
    return change_ids


# Function to filter out CLs only those whose file changes has file path as "projects/ui-libs"
def filterChangeIDsByFilePattern(change_ids):
    final_change_ids_list = []
    for obj in change_ids:

        # API call to fetch the file detals of the CL
        response = rest.get(
            f"changes/?q={obj}&o=CURRENT_FILES&o=CURRENT_REVISION",
            headers={"Content-Type": "application/json"},
        )
        cls_list_with_file_details = response
        for elem in cls_list_with_file_details:
            files_obj = elem["revisions"][elem["current_revision"]]["files"]
            if isFilePatternValidForFiles(files_obj):
                final_change_ids_list.append(elem["change_id"])
    return final_change_ids_list


# Function to match the file pattern "projects/ui-libs"
def isFilePatternValidForFiles(files_obj):
    files_list = list(files_obj.keys())
    matches_pattern = False
    for file_name in files_list:
        if re.match(FILE_PATTERN, file_name):
            matches_pattern = True
            break

    return matches_pattern


# Function to fetch the author details of the CLs
def fetchAuthorDetails(change_ids):
    cl_owner_dict = {}
    for change_id in change_ids:
        # API call to fetch the author details of the CL
        changes = rest.get(
            f"changes/{change_id}/detail", headers={"Content-Type": "application/json"}
        )
        cl_owner_dict[change_id] = {
            'name': changes["owner"]["name"],
            'email': changes["owner"]["email"]
        }

    return cl_owner_dict

# Function to display the data in tabular format
def displayTable(cl_list):
    table = PrettyTable()
    columns = ["Sr. No", "CL", "Owner", "Change Description", "Date"]
    table.field_names = columns
    for index, item in enumerate(cl_list):
        row_data = [index+1, item["cl_url"], item["name"], item["subject"], datetime.strptime(item["submitted"].split(".", 1)[0], "%Y-%m-%d %H:%M:%S")]
        table.add_row(row_data)
        empty_row = ["", "", "", "", ""]
        table.add_row(empty_row)
    print(table)

# Function to save the data in excel file
def saveDataToExcel(cl_list):
    df = pd.DataFrame(cl_list)
    new_columns = {
    'cl_url': 'CL URL',
    'name': 'Owner',
    'subject': 'Change Description',
    'submitted': 'Date'
    }
    selected_columns = ['cl_url', 'name', 'subject', 'submitted']
    new_df = df[selected_columns].rename(columns=new_columns)
    # Specify the file path where you want to save the Excel file
    excel_file_path = 'demo.xlsx'

    try:
    # Export the DataFrame to an Excel file
        new_df.to_excel(excel_file_path, index=False)
        print(f"DataFrame has been exported to {excel_file_path}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")



# Main Function
if __name__ == "__main__":

    user_input = input("Please enter a date (YYYY-MM-DD) after which you want to extract the CLs: ")

    try:
        # Convert user input to date time format
        target_date = datetime.strptime(user_input, '%Y-%m-%d')
        print("Date entered:", target_date)
        cl_list = invokeGerritAPI(target_date)
        displayTable(cl_list)
        saveDataToExcel(cl_list)
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")



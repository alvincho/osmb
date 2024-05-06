import streamlit as st
import pandas as pd
import boto3
import json
import os
from auth0_component import login_button
from datetime import datetime

clientId = st.secrets["auth0"]["clientId"]
domain = st.secrets["auth0"]["domain"]

user_info = login_button(clientId, domain = domain)
if user_info:
    st.write("welcome", user_info['name'])
#st.write(user_info)

# Load configuration
@st.cache_resource
def load_config():
    with open("osmb.json", "r") as file:
        return json.load(file)

config = load_config()

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
table = dynamodb.Table('osmb_comments')

# Interface
st.title("Data Analysis and Commenting Tool")

# Multi-select for Test Plans
test_plan_options = [config['testplans'][plan] for plan in config['testplans'].keys()]
selected_test_plans = st.multiselect("Select Test Plans", test_plan_options, default=test_plan_options[0],format_func=lambda x: x['title'],key="selected_test_plans")
selected_plan_names=[plan['title'] for plan in selected_test_plans]

# Filter and load data
data_frames = []
testsets=[]
for plan in selected_test_plans:
    for test_set in plan['testsets']:
        testsets.append(test_set)

if not 'filter' in st.session_state:
    st.session_state.filter=""
selected_testsets=st.multiselect("Select Test Set",testsets,default=testsets[:1],format_func=lambda x: x['title'],key="selected_testsets")
selected_testset_names=[testset['title'] for testset in selected_testsets]

for testset in selected_testsets:
    file_path = testset['location']  # Assuming this is the correct key for CSV file path
    try:
        df = pd.read_csv(file_path)
        data_frames.append(df)
    except Exception as e:
        st.error(f"Failed to load data from {file_path}: {str(e)}")

# Combine all data
if data_frames:

    combined_data = pd.concat(data_frames, ignore_index=True)
    #st.dataframe(combined_data)

    if 'correctness' in combined_data:
        combined_data['correctness']=combined_data['correctness']*100
        combined_data.sort_values(by=['correctness'], ascending=False, inplace=True)

    # Filtering by model (assuming 'Model' column exists)
    model_options = combined_data['model'].unique()
    model_options.sort()
    llama3s = [model for model in model_options if model.lower().startswith('llama3')]
    selected_models=llama3s
    if 'selected_models' in st.session_state:
        selected_models=st.session_state.selected_models
    
    filtered_models=[]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.selectbox("Filter",["Top","Bottom","Model Name"],key="filter_type")
    with col2:
        st.text_input("",key="filter_text",value="10")
    invalid_input=False
    if st.session_state.filter_type=="Top":
        # select top models with highest correctness
        try:
            # Sort the DataFrame by 'correctness' and get the top N rows
            sorted_df = combined_data.sort_values(by='correctness', ascending=False).head(int(st.session_state.filter_text))

            # Use .loc to select the 'model' column from the sorted DataFrame
            filtered_models = sorted_df.loc[:, 'model']
            # filtered_models = combined_data['model'][combined_data['correctness'].sort_values(ascending=False).head(int(st.session_state.filter_text)).index]
        except:
            invlaid_input=True
    elif st.session_state.filter_type=="Bottom":
        try:
            # select bottom models with lowest correctness
            # Sort the DataFrame by 'correctness' and get the top N rows
            sorted_df = combined_data.sort_values(by='correctness', ascending=True).head(int(st.session_state.filter_text))

            # Use .loc to select the 'model' column from the sorted DataFrame
            filtered_models = sorted_df.loc[:, 'model']
            # filtered_models = combined_data['model'][combined_data['correctness'].sort_values(ascending=True).head(int(st.session_state.filter_text)).index]
        except:
            invlaid_input=True
    else:
        # select models with name containing filter_text
        filtered_models = combined_data['model'].unique()
        filtered_models = [model for model in filtered_models if st.session_state.filter_text.lower() in model.lower()]
    with col3:
        if st.button("Add",disabled=invalid_input):
            selected_models=st.session_state.selected_models+[  model for model in filtered_models if model not in st.session_state.selected_models]
            #st.write("selected",st.session_state.selected_models)
    with col4:
        if st.button("Replace",disabled=invalid_input):
            selected_models=filtered_models
            #st.write(filtered_models)
    st.write("Filtered Models",", ".join(filtered_models))
    selected_models=st.multiselect("Filter by Model", model_options,default=selected_models)
    #print(st.session_state.selected_models)
    st.session_state.final_data = combined_data[combined_data['model'].isin(selected_models)]
    #print("model set")
    st.write("Test Results")
    st.session_state.selected_models=selected_models
    #print(st.session_state.final_data)
    st.dataframe(st.session_state.final_data,use_container_width=True,
                 column_config={
                        "testset": {"max_width": 200},
                        "model": {"max_width": 400},
                        "correctness": st.column_config.NumberColumn(
                            "Correct %",
                            format="%.2f %%",
                            ),
                        "correct": {"max_width": 50},
                        "incorrect": {"max_width": 50},
                     "testplan": {"max_width": 100}
                 }
                 )
    try:
        if 'email' in user_info:
            # Comment section
            user_comment = st.text_area("Enter your comment")
            if st.button("Submit Comment"):
                # Save comment to DynamoDB
                response = table.put_item(
                Item={
                        'testplan': selected_plan_names,
                        'testsets': selected_testset_names,
                        'models': st.session_state.selected_models,
                        'user_email': user_info['email'],  # Assuming user_info is a dictionary with 'email' key
                        "user_name": user_info['name'],  # Assuming user_info is a dictionary with 'name' key
                        'comment': user_comment,
                        'data':st.session_state.final_data.to_json(),
                        'timestamp': str(datetime.now())
                    }
                )
                if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                    st.success("Comment submitted successfully!")
                else:
                    st.error("Failed to submit comment.")
    except Exception as ex:
        #st.write(ex)
        pass

        
    # Display relevant comments
    if st.checkbox("Show Comments", value=True):
        st.session_state.filter="("
        attrib={}
        # i=0
        # for plan in selected_plan_names:
        #     filter+=f"contains (testplan, :plan{i}) OR "
        #     attrib[f":plan{i}"]=plan
        #     i+=1
        i=0
        for testset in selected_testset_names:
            st.session_state.filter+=f"contains (testsets, :set{i}) OR "
            attrib[f":set{i}"]=testset
            i+=1
        if st.session_state.filter[-3:]=="OR ":
            st.session_state.filter=st.session_state.filter[:-3]
        st.session_state.filter+=") AND ("
        i=0
        for model in st.session_state.selected_models:
            st.session_state.filter+=f"contains (models, :model{i}) OR "
            attrib[f":model{i}"]=model
            i+=1
        if st.session_state.filter[-3:]=="OR ":
            st.session_state.filter=  st.session_state.filter[:-3]
        st.session_state.filter+=")"
        scan_kwargs = {
            'FilterExpression': st.session_state.filter,
            'ExpressionAttributeValues': attrib
        }
        comments = []
        start_key = None
        while True:
            if start_key:
                scan_kwargs['ExclusiveStartKey'] = start_key
            response = table.scan(**scan_kwargs)
            comments.extend(response.get('Items', []))
            start_key = response.get('LastEvaluatedKey', None)
            if start_key is None:
                break

        # Sort comments by timestamp
        comments = sorted(comments, key=lambda x: datetime.strptime(x['timestamp'], '%Y-%m-%d %H:%M:%S.%f'), reverse=True)

        comment_count=0
        # Display comments
        for idx, item in enumerate(comments):
            comment_count+=1
            st.write(f"*#{idx} **{item['user_name']}** {item['timestamp']}*  \n" + item['comment'])
            if 'data' in item:
                st.dataframe(pd.read_json(item['data']), use_container_width=True)

            # Check if the current logged-in user's email matches the comment's email
            if user_info and 'email' in user_info and user_info['email'] == item['user_email']:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Edit", key=f"edit{idx}"):
                        # Code to handle editing this comment
                        st.session_state['edit_comment'] = item['comment']  # Pre-fill the text area with this comment
                        st.session_state['edit_comment_id'] = idx  # Keep track of which comment is being edited
                with col2:
                    if st.button("Delete", key=f"delete{idx}"):
                        # Code to delete this comment from DynamoDB
                        response = table.delete_item(
                            Key={
                                'user_email': user_info['email'],
                                'timestamp': item['timestamp']
                                #'comment_id': item['comment_id']  # Ensure you have a unique identifier for comments
                            }
                        )
                        if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                            st.success("Comment deleted successfully!")
                        else:
                            st.error("Failed to delete comment.")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("👍", key=f"up{idx}"):
                        # Increment the vote count in DynamoDB
                        pass
                with col2:
                    if st.button("👎", key=f"down{idx}"):
                        # Decrement the vote count in DynamoDB
                        pass
        if comment_count==0:
            st.write("No comment")
        # Handle editing outside the loop to avoid conflicts with button presses
        if 'edit_comment' in st.session_state:
            st.text_area("Edit Comment", value=st.session_state['edit_comment'], key='new_comment')
            if st.button("Save Changes"):
                # Save the updated comment to DynamoDB
                response = table.update_item(
                    Key={
                        'comment_id': st.session_state['edit_comment_id']
                    },
                    UpdateExpression="set comment = :c",
                    ExpressionAttributeValues={
                        ':c': st.session_state['new_comment']
                    },
                    ReturnValues="UPDATED_NEW"
                )
                if response.get('ResponseMetadata', {}).get('HTTPStatusCode') == 200:
                    st.success("Comment updated successfully!")
                    del st.session_state['edit_comment']
                    del st.session_state['edit_comment_id']
                    del st.session_state['new_comment']
                else:
                    st.error("Failed to update comment.")
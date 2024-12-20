import streamlit as st
import json
import boto3
import pandas as pd

# Load JSON data
with open('osmb.json', 'r') as f:
    config = json.load(f)
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
table = dynamodb.Table('osmb_comments')
github_path="https://github.com/alvincho/osmb/"
github_blob_path="https://github.com/alvincho/osmb/blob/main/"
streamlit_path="https://osmb-viewer.streamlit.app/"
testplan=None
selected_testset=None
if "testset" in st.query_params:
    testset_name=st.query_params.testset
    for testplan_name in config['testplans']:
        testplan=config['testplans'][testplan_name]
        for testset in testplan['testsets']:
            if testset['title']==st.query_params.testset:
                #testplan = testplan_config
                selected_testset=testset
                #st.write(f"selected testplan {testplan['title']} {testset_name}")
                break
        if not selected_testset is None:
            break
    if selected_testset==None:
        st.write("Testset "+st.query_params.testset+" not found")
        st.stop()
    st.session_state.is_markdown=False
else:
    # Dropdown to select the test plan
    testplan = st.selectbox("Select a Test Plan", [config['testplans'][key] for key in config['testplans'] ],format_func=lambda x:x['title'])
    testplan_name=testplan['title']

    # Dropdown to select the test set from the selected test plan
    testset_name = st.selectbox("Select a Test Set", [ts['title'] for ts in testplan['testsets'] if ts['is_active']])

    # Find the selected test set details
    selected_testset = next(ts for ts in testplan['testsets'] if ts['title'] == testset_name)
    st.selectbox("Key Finding Results",["As Table","As Markdown"],key="table_format")
    st.session_state.is_markdown = st.session_state.table_format=="As Markdown"


st.title("Testset: "+selected_testset['title']+" "+ testplan['title'])
st.write("### Test Plan Details")
st.write(testplan['description'])
# Display the details of the selected test set
st.write("### Test Set Details")
st.write(selected_testset['description'])
st.write("*Date Published*", selected_testset.get('date_published', 'N/A'))
st.write("### Methodology")
st.write("See our [blog post](https://medium.com/@alvincho/unveiling-ai-expertise-in-finance-a-comparative-analysis-of-open-source-llms-5f231e42279e) to know more about our methodology")
st.write("### Key Finding")
key_finding=st.empty()
st.subheader("Datasets")
for ds in selected_testset['datasets']:
    dataset=config['datasets'][ds]
    st.write("#### "+dataset['title'])
    st.write(dataset['description'])
    st.write(f"[Download data]({github_blob_path}{dataset['location']})")

st.subheader("Prompt Template")
template=config['prompt_templates'][selected_testset['prompt_template']]
st.write("> "+template['prompt'].replace('\n','\n> '))

# Display CSV data if available
if 'location' in selected_testset:
    st.write("#### Results by Models")
    st.write(f"[Download data]({github_blob_path}{selected_testset['location']})")
    try:
        model_data = pd.read_csv(selected_testset['location'])
        model_data['correctness']=model_data['correct']/(model_data['correct']+model_data['incorrect'])*100
        if st.session_state.is_markdown:
            st.html("<pre>"+model_data.to_markdown()+"</pre>")
        else:
            st.dataframe(model_data,use_container_width=True,column_config={
                        "model": {"max_width": 400},
                        "correctness": st.column_config.NumberColumn(
                            "Correct %",
                            format="%.2f %%",
                            ),
                        "correct": {"max_width": 50},
                        "incorrect": {"max_width": 50}

        })
    except Exception as e:
        st.error(f"Failed to load model data: {e}")

if 'testdata' in selected_testset:
    st.write("#### Test Results")
    st.write(f"Display the first 100 rows. Full data can be downloaded from our [GitHub repository]({github_path}{selected_testset['testdata']})")
    try:
        test_data = pd.read_csv(selected_testset['testdata'])
        if st.session_state.is_markdown:
            st.html("<pre>"+test_data[:100].to_markdown()+"</pre>")
        else:
            st.dataframe(test_data[:100])
    except Exception as e:
        st.error(f"Failed to load test data: {e}")

# Display relevant comments
#if st.checkbox("Show Comments", value=True):
#sorted_by=st.selectbox("Sort by",["timestamp","models"])
sorted_by='timestamp'
reverse_order= sorted_by=="timestamp"
filter = "contains (testsets, :set) "
attrib = {":set": testset_name}
scan_kwargs = {
    'FilterExpression': filter,
    'ExpressionAttributeValues': attrib
}
comments = []
done = False
start_key = None
while not done:
    if start_key:
        scan_kwargs['ExclusiveStartKey'] = start_key
    response = table.scan(**scan_kwargs)
    comments.extend(response.get('Items', []))
    start_key = response.get('LastEvaluatedKey', None)
    done = start_key is None

# Sort comments by timestamp in ascending order
comments_sorted = sorted(comments, key=lambda x: x[sorted_by])

# Display comments
if comments_sorted:
    key_finding_str=""
    st.subheader("Key Findings")
    for idx, item in enumerate(comments_sorted):
        st.html(f"<h3 id=\"finding_{idx}\">"+item['comment']+"</h3>")
        #key_finding_str += f"[*{item['comment']}*](#finding_{idx})\n\n"
        key_finding_str += f"- [{item['comment']}\n]({streamlit_path}Test_Report?testset={testset_name}#{idx})\n"
        #st.subheader(item['comment'])
        if 'data' in item: 
            df=pd.read_json(item['data'])
            df=df.drop(['testplan','testset'],axis=1)
            df['correctness']=df['correct']/(df['correct']+df['incorrect'])*100
            if st.session_state.is_markdown:
                st.html("<pre>"+df.to_markdown()+"</pre>")
            else:
                st.dataframe(df, use_container_width=True,column_config=
                            {
                                                        "model": {"max_width": 400},
                            "correctness": st.column_config.NumberColumn(
                                "Correct %",
                                format="%.2f %%",
                                ),
                            "correct": {"max_width": 50},
                            "incorrect": {"max_width": 50}

                            }
                            )
        #st.write(f"*#{idx} **{item['user_name']}** {item['timestamp']}*")
    key_finding.write(key_finding_str)
else:
    st.write("No comments found")
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

# Load configuration JSON
#@st.cache_resource
def load_config():
    with open('osmb.json', 'r') as file:
        return json.load(file)

#@st.cache_resource
def load_data(path):
    return pd.read_csv(path)

config = load_config()

# Display header and latest results
st.title('Open Source Model Benchmarker')
#st.header('Latest Results')
#latest_result = config['latest_result']
#st.subheader(latest_result['name'])
#st.write(latest_result['description'])
#latest_data = load_data(latest_result['location'])
#st.write(latest_data.head())

# Setup columns for selections
st.write("This is a simple showcase of a Streamlit app that displays model performance comparison and detailed test results. Please visit our [GitHub repository](https://github.com/alvincho/osmb) for full published data and code.")

st.subheader('Select Topic')
topics = list(config['topics'].keys())
selected_topic = st.selectbox('Topic:', topics)
st.write(config['topics'][selected_topic]['description'])

col1, col2 = st.columns(2)

with col1:
    st.subheader('Select Dataset')
    datasets = {k: v for k, v in config['datasets'].items() if selected_topic in v['topics']}
    dataset_titles = [v['title'] for k, v in datasets.items()]
    selected_dataset = st.selectbox('Dataset:', datasets,format_func=lambda x: datasets[x]['title'])
    st.write(datasets[selected_dataset]['description'])

with col2:
    st.subheader('Select Test Plan')
    test_plans = {k:v for k, v in config['testplans'].items() if selected_dataset in v['datasets']}
    selected_test_plan = st.selectbox('Test Plan:', test_plans,format_func=lambda x: test_plans[x]['title'])
    st.write(config['testplans'][selected_test_plan]['description'])

# Load and display test sets from the selected test plan
test_sets = config['testplans'][selected_test_plan]['testsets']
test_set_options = [ts['title'] for ts in test_sets]
selected_test_set_titles = st.multiselect('Select Test Sets:', test_set_options, default=test_set_options)

# Load all test set data
all_data = pd.DataFrame()
for test_set in test_sets:
    if test_set['title'] in selected_test_set_titles:
        df = load_data(test_set['location'])
        df['test_set'] = test_set['title']  # Correct column name
        all_data = pd.concat([all_data, df], ignore_index=True)

# Determine top 5 models based on highest average correctness
top_models = all_data.groupby('model')['correctness'].mean().nlargest(5).index.tolist()
selected_models = st.multiselect('Select Models:', all_data['model'].unique(), default=top_models)
final_data = all_data[all_data['model'].isin(selected_models)]

# Visualization with corrected column names
if not final_data.empty:
    fig = px.bar(final_data, x='model', y='correctness', color='test_set',  # Corrected color attribute
                 barmode='group', title='Model Performance Comparison')
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(final_data)  # Displaying the data grid below the chart
else:
    st.write("No data available for the selected models or test sets.")

# Load consolidated test view data from selected test sets
test_view_data = pd.DataFrame()
for test_set in test_sets:
    if test_set['title'] in selected_test_set_titles:
        df = load_data(test_set['testdata'])
        test_view_data = pd.concat([test_view_data, df], ignore_index=True)

# Filters for different columns
st.header('Detailed Test Results')
st.write("Maximum 1000 records are displayed. Full data see [GitHub repository](https://github.com/alvincho/osmb).")
col1, col3, col4 = st.columns(3)
with col1:
    filter_test_set = st.multiselect('Filter by Test Set', options=test_view_data['testset'].unique())
with col3:
    filter_model = st.multiselect('Filter by Model', options=test_view_data['model'].unique())
with col4:
    filter_correct = st.multiselect('Filter by Correct', options=test_view_data['correct'].unique(), format_func=lambda x: 'Correct' if x else 'Incorrect')

# Apply filters to test_view_data
if filter_test_set:
    test_view_data = test_view_data[test_view_data['testset'].isin(filter_test_set)]
if filter_model:
    test_view_data = test_view_data[test_view_data['model'].isin(filter_model)]
if filter_correct:
    test_view_data = test_view_data[test_view_data['correct'].isin(filter_correct)]

# Display the filtered data
st.dataframe(test_view_data[:1000])
st.subheader("About Selected Test Sets")
for test_set in test_sets:
    st.subheader(f"**{test_set['title']}**")
    st.write(test_set['description'])

import streamlit as st

st.set_page_config(
    page_title="Home",
    page_icon="👋",
)

st.write("# Welcome to OSMB! 👋")
with open("home.md","r") as file:
    st.write(file.read())
st.image("images/Prompits-OSMB.jpg")
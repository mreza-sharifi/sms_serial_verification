from flask import Flask
app = Flask(__name__)


@app.route('/')
def mail_page():
    '''This the main page of the site
    '''
    return "hello"



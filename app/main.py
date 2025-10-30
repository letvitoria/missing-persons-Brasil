from flask import Flask
from mvc_flask import FlaskMVC
from app import routes 

def create_app():
    app = Flask(__name__,
                static_folder='static',
                template_folder='views')
    FlaskMVC(app)
    return app
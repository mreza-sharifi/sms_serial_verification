import os
import sqlite3
import re
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user
from pandas import read_excel

from flask import Flask, jsonify, request, Response, redirect, url_for, session, abort,flash

from werkzeug.utils import secure_filename
import requests
import config
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


UPLOAD_FOLDER = config.UPLOAD_FOLDER
ALLOWED_EXTENSIONS = config.ALLOWED_EXTENSIONS


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
limiter = Limiter(
    app,
    key_func=get_remote_address)

# config
app.config.update(
    SECRET_KEY = config.SECRET_KEY
)

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
CALL_BACK_TOKEN = config.CALL_BACK_TOKEN

# silly user model
class User(UserMixin):

    def __init__(self, id):
        self.id = id
        # self.name = "user" + str(id)
        # self.password = self.name + "_secret"
        
    def __repr__(self):
        return "%d" % (self.id)


# create some users with ids 1 to 20       
user = User(0)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@app.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            session['message'] = 'No selected file'
            return redirect(request.url)
        file = request.files['file']
        # if user does not select file, browser also
        # submit an empty part without filename
        if file.filename == '':
            flash('No selected file')
            session['message'] = 'No selected file'
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            rows, failures = import_database_from_excel(file_path)
            session['message'] = f'Imported {rows} rows of serials and {failures} rows of failure'
            os.remove(file_path)
            return redirect('/')
    message = session.get('message', '')
    session['message'] = ''
    return f'''
    <!doctype html>
    <title>Upload new File</title>
    <h1>Upload new File</h1>
    <h3>{message}<h3>
    <form method=post enctype=multipart/form-data>
      <input type=file name=file>
      <input type=submit value=Upload>
    </form>
    '''
 
# somewhere to login
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == 'POST': #TODO: stop the brute force
        username = request.form['username']
        password = request.form['password']        
        if password == config.PASSWORD and username == config.USERNAME:
            login_user(user)
            return redirect(request.args.get("next")) #TODO: check url validity
        else:
            return abort(401)
    else:
        return Response('''
        <form action="" method="post">
            <p><input type=text name=username>
            <p><input type=password name=password>
            <p><input type=submit value=Login>
        </form>
        ''')


# somewhere to logout
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return Response('<p>Logged out</p>')


# handle login failed
@app.errorhandler(401)
def page_not_found(error):
    return Response('<p>Login failed</p>')
     
    
# callback to reload the user object        
@login_manager.user_loader
def load_user(userid):
    return User(userid)
    
@app.route('/v1/ok')
def health_check():
    ret = {'message': 'ok'}
    return jsonify(ret), 200




def send_sms(receptor, message):
    """ this function will send sms
    """
    url = 'https://api.kavenegar.com/v1/{config.API-KEY}/sms/send.json'
    data = {"message": message,
            "receptor": receptor}
    res= request.post(data)
    print(f"message *{message}* sent. status code os {res.status_code}")


def normalize_string(data,fixed_size=30):
    from_persian_char = '۱۲۳۴۵۶۷۸۹۰'
    from_arabic_char = '١٢٣٤٥٦٧٨٩٠'
    to_char = '1234567890'
    for i in range(len(to_char)):
        data = data.replace(from_persian_char[i], to_char[i])
        data = data.replace(from_arabic_char[i], to_char[i])
    data = data.upper()
    data = re.sub(r'\W+', '', data) # remove any non alpha numeric  
    all_alpha = ''
    all_digit = ''
    for c in data:
        if c.isalpha():
            all_alpha += c
        elif c.isdigit():
            all_digit += c
    missing_zeros = fixed_size - len(all_digit) - len(all_alpha)
    data = all_alpha + '0'*missing_zeros + all_digit
    return(data)





def import_database_from_excel(filepath):
    """gets an excel file name and imports lookup data (data and failures) from it 
        the (1) sheet contains serial data like:
         Row	Reference_Number	Description	Start_Serial	End_Serial	Date
         and the (0) contains a column of invalid serials.
         This data will be wrriten into the qlite database located at config.DATABASE_FILE_PATH
        in two tables."serials" and "invalids" 
        
        return two integers: (number of serial rows, number of invalid rows)
        
        """
    # df contains lookup data in the form of

    # Row	Reference Number	Description	Start Serial	End Serial	Date
    
    # TODO: make sure that the data is imported correctly, we need to backup the old one.
    # TODO: do some normalization
    ## our sqlite database will contain two tables: serials and invalids
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()
    # remove the serials table if exists, then create new one
    cur.execute('DROP TABLE IF EXISTS serials')
    cur.execute("""CREATE TABLE IF NOT EXISTS serials (
        id INTEGER PRIMARY KEY,
        ref TEXT,
        desc TEXT,
        start_serial TEXT,
        end_serial TEXT,
        date DATE);""")
    
    df = read_excel(filepath, 0)
    serial_counter = 0
    for index,(line, ref, desc, start_serial, end_serial, date) in df.iterrows():
        start_serial = normalize_string(start_serial)
        end_serial = normalize_string(end_serial)
        query = f'INSERT INTO serials (id, ref, desc, start_serial, end_serial, date) VALUES("{line}", "{ref}", "{desc}", "{start_serial}", "{end_serial}", "{date}");'
        cur.execute(query)
        # TODO: do some more error handling
        if serial_counter % 10 == 0:
            conn.commit()

        serial_counter += 1
        #print(line, ref, desc, start_serial, end_serial, date)
    conn.commit()

     # remove the invalids table if exists, then create new one
    cur.execute('DROP TABLE IF EXISTS invalids')
    cur.execute("""CREATE TABLE IF NOT EXISTS invalids (
        invalid_serial TEXT PRIMARY KEY);""")
    conn.commit()
    # now lets save the invalid serials
    df = read_excel(filepath, 1) # sheet 1 contain failed serial numbers.only one column  exists.
    invalid_counter = 0
    for index, (failed_serial, ) in df.iterrows():
        #failed_serial = failed_serial_row[0]

        query = f'INSERT INTO invalids VALUES("{failed_serial}");'
        cur.execute(query)
        # TODO: do some more error handling
        if invalid_counter % 10 == 0:
            conn.commit()

        invalid_counter += 1
    conn.commit()
    cur.close()
    return (serial_counter, invalid_counter)


def check_serial(serial):
    ''' this function will check the serial'''
    conn = sqlite3.connect(config.DATABASE_FILE_PATH)
    cur = conn.cursor()
    query = f"SELECT * FROM invalids WHERE invalid_serial == '{serial}'"
    results = cur.execute(query)
    if len(results.fetchall()) > 0:
        return 'this serial is among failed ones' # TODO: return the string provided by the cutomer
    
    query = f"SELECT * FROM serials WHERE start_serial <= '{serial}' and end_serial >= '{serial}'"
    #print(query)
    results = cur.execute(query)
    if len(results.fetchall()) == 1:
        return 'I found your serial' # TODO: return the string provided by the cutomer

    return 'it was not in the db'

@app.route(f'/v1/{CALL_BACK_TOKEN}/process', methods=['POST'])
def process():
    """this is a callback from kavenegar. will get sender and message
    and will check if it is valid. then answer back
    """
    data = request.form
    # import pdb; pdb.set_trace()
    sender = data["from"]
    message = normalize_string(data["message"])
    print(f'message {message} recieved from {sender}') # logging
    answer = check_serial(message)
    send_sms(sender, answer)
    ret =  {"message": "processed"}
    return jsonify(ret), 200

if __name__ == "__main__":

    app.run("0.0.0.0", 5000, debug=True)